"""Interactive local web application for gupiao research workflows."""

# ruff: noqa: E501

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from gupiao.auction import build_auction_profile
from gupiao.backtest import (
    BacktestConfig,
    BacktestResult,
    run_breakout_backtest,
    run_morning_plan_backtest,
)
from gupiao.data import (
    AkshareProvider,
    AuctionProfile,
    DailyBar,
    LocalAuctionCacheImportConfig,
    LocalDailyCacheImportConfig,
    MarketCacheRefreshConfig,
    SQLiteStore,
    import_local_auction_cache,
    import_local_daily_cache,
    refresh_market_daily_cache,
    validate_daily_bars,
)
from gupiao.factors import FactorInput, rank_factors
from gupiao.indicators import atr, bollinger_bands, closes, ema, kdj, macd, obv, rsi, sma
from gupiao.reports import build_markdown_report, write_markdown_report
from gupiao.research import (
    AuctionStrategyComparisonConfig,
    ResearchSample,
    allocate_by_score,
    build_auction_research_samples,
    predict_linear_baseline,
    run_auction_strategy_comparison,
    split_train_validation,
    train_linear_baseline,
)
from gupiao.scan import DEFAULT_SCAN_END, DEFAULT_SCAN_START, MarketScanConfig, run_market_scan
from gupiao.signals import build_breakout_signal
from gupiao.strategies import (
    CandidateScreenConfig,
    MorningScreenConfig,
    ScreeningStrategy,
    available_strategy_specs,
    bars_up_to,
    build_screening_strategy,
    run_morning_screen,
    run_cached_candidate_screen,
)
from gupiao.web.dashboard import build_dashboard_html, write_dashboard_html

ActionHandler = Callable[[dict[str, Any], Path], dict[str, Any]]


def serve_app(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    workspace: str | Path | None = None,
) -> None:
    root = Path(workspace or Path.cwd()).resolve()
    handler = make_handler(root)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Serving gupiao web app on http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def make_handler(workspace: Path) -> type[BaseHTTPRequestHandler]:
    class GupiaoWebHandler(BaseHTTPRequestHandler):
        server_version = "GupiaoWeb/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in {"", "/"}:
                self.send_text(build_app_html(), content_type="text/html; charset=utf-8")
                return
            if parsed.path == "/api/health":
                self.send_json({"ok": True, "workspace": str(workspace)})
                return
            if parsed.path == "/file":
                self.send_file(parsed.query)
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/api/run":
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
            try:
                payload = self.read_json()
                action = str(payload.get("action", ""))
                params = payload.get("params", {})
                if not isinstance(params, dict):
                    raise ValueError("params must be an object")
                result = run_web_action(action, dict(params), workspace)
                self.send_json({"ok": True, "action": action, "result": result})
            except Exception as exc:  # noqa: BLE001 - surface local workflow errors in UI.
                self.send_json(
                    {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                    status=HTTPStatus.BAD_REQUEST,
                )

        def log_message(self, format: str, *args: Any) -> None:
            return

        def read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body or "{}")
            if not isinstance(payload, dict):
                raise ValueError("request body must be a JSON object")
            return payload

        def send_json(self, value: Any, *, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(to_jsonable(value), ensure_ascii=False, sort_keys=True).encode(
                "utf-8"
            )
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_text(
            self,
            value: str,
            *,
            content_type: str,
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            body = value.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_file(self, query: str) -> None:
            values = parse_qs(query)
            raw_path = values.get("path", [""])[0]
            if not raw_path:
                self.send_error(HTTPStatus.BAD_REQUEST, "missing path")
                return
            path = resolve_path(unquote(raw_path), workspace)
            allowed_roots = [workspace, Path("/tmp").resolve()]
            if not any(is_relative_to(path, root) for root in allowed_roots):
                self.send_error(HTTPStatus.FORBIDDEN, "path is outside allowed roots")
                return
            if not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "file not found")
                return
            content = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type_for(path))
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    return GupiaoWebHandler


def run_web_action(action: str, params: dict[str, Any], workspace: Path | None = None) -> dict[str, Any]:
    root = Path(workspace or Path.cwd()).resolve()
    handlers: dict[str, ActionHandler] = {
        "quick_analysis": action_quick_analysis,
        "data_instruments": action_data_instruments,
        "data_daily": action_data_daily,
        "data_pre_market": action_data_pre_market,
        "data_update_daily": action_data_update_daily,
        "data_status": action_data_status,
        "data_refresh_market_cache": action_data_refresh_market_cache,
        "import_daily_cache": action_import_daily_cache,
        "import_auction_cache": action_import_auction_cache,
        "strategy_list": action_strategy_list,
        "morning_screen": action_morning_screen,
        "trade_plan": action_trade_plan,
        "screen_candidates": action_screen_candidates,
        "validate_bars": action_validate_bars,
        "indicators": action_indicators,
        "screen_breakout": action_screen_breakout,
        "signal_breakout": action_signal_breakout,
        "backtest_breakout": action_backtest_breakout,
        "backtest_morning": action_backtest_morning,
        "report_breakout": action_report_breakout,
        "dashboard": action_dashboard,
        "scan_market": action_scan_market,
        "auction_compare": action_auction_compare,
        "factor_rank": action_factor_rank,
        "research_linear": action_research_linear,
        "auction_samples": action_auction_samples,
    }
    handler = handlers.get(action)
    if handler is None:
        raise ValueError(f"unknown action: {action}")
    return handler(params, root)


def action_quick_analysis(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    symbol = symbol_param(params)
    bars = load_bars(params, workspace, symbol=symbol)
    strategy = strategy_from_params(params)
    config = backtest_config_from_params(params)
    auction_profiles = load_auction_profiles(params, workspace, symbol, bars)
    candidate = strategy.evaluate(symbol, bars, auction_profile=latest_auction_profile(auction_profiles))
    signal = build_signal_if_candidate(candidate, bars, params)
    backtest = run_breakout_backtest(
        symbol,
        bars,
        strategy=strategy,
        config=config,
        auction_profiles=auction_profiles,
    )
    output_dir = resolve_path(str_param(params, "output_dir", "reports/generated/web"), workspace)
    report_path = output_dir / f"{safe_name(symbol)}_report.md"
    dashboard_path = output_dir / f"{safe_name(symbol)}_dashboard.html"
    report_content = build_markdown_report(
        title=str_param(params, "report_title", "MVP 策略报告"),
        candidate=candidate,
        signal=signal,
        backtest=backtest,
    )
    write_markdown_report(report_path, report_content)
    dashboard_content = build_dashboard_html(
        title=str_param(params, "dashboard_title", "A 股策略研究 Dashboard"),
        candidate=candidate,
        signal=signal,
        backtest=backtest,
        bars=bars,
        strategy=strategy,
        backtest_config=config,
        auction_profile=latest_auction_profile(auction_profiles),
        source_path=params.get("bars_path") or params.get("db_path") or "",
    )
    write_dashboard_html(dashboard_path, dashboard_content)
    return {
        "candidate": candidate,
        "signal": signal,
        "backtest": summarize_backtest(backtest),
        "report": path_result(report_path),
        "dashboard": path_result(dashboard_path),
    }


def action_data_instruments(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    del workspace
    limit = int_param(params, "limit", 20)
    records = list_limited(AkshareProvider().list_instruments(), limit)
    return {"count": len(records), "records": records}


def action_data_daily(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    symbol = symbol_param(params)
    bars = list(
        AkshareProvider().fetch_daily_bars(
            symbol,
            required_date(params, "start"),
            required_date(params, "end"),
            adjust=str_param(params, "adjust", "hfq"),
        )
    )
    save_path_text = str_param(params, "save_path", "")
    result: dict[str, Any] = {
        "symbol": symbol,
        "count": len(bars),
        "preview": bars[: int_param(params, "preview_limit", 20)],
    }
    if save_path_text:
        path = resolve_path(save_path_text, workspace)
        write_jsonl(path, bars)
        result["saved"] = path_result(path)
    return result


def action_data_pre_market(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    symbol = symbol_param(params)
    minutes = list(
        AkshareProvider().fetch_pre_market_minutes(
            symbol,
            start_time=str_param(params, "start_time", "09:15:00"),
            end_time=str_param(params, "end_time", "09:25:00"),
        )
    )
    profile = build_auction_profile(
        symbol,
        minutes,
        previous_close=float_param(params, "previous_close", None),
        average_daily_volume=float_param(params, "average_daily_volume", None),
    )
    save_path_text = str_param(params, "save_path", "")
    result: dict[str, Any] = {"count": len(minutes), "preview": minutes[:20], "profile": profile}
    if save_path_text:
        path = resolve_path(save_path_text, workspace)
        write_jsonl(path, minutes)
        result["saved"] = path_result(path)
    return result


def action_data_update_daily(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    symbol = symbol_param(params)
    bars = list(
        AkshareProvider().fetch_daily_bars(
            symbol,
            required_date(params, "start"),
            required_date(params, "end"),
            adjust=str_param(params, "adjust", "hfq"),
        )
    )
    db_path = resolve_path(str_param(params, "db_path", "data/gupiao.sqlite"), workspace)
    rows = SQLiteStore(db_path).upsert_daily_bars(bars)
    return {"db": str(db_path), "symbol": symbol, "rows": rows}


def action_data_status(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    db_path = resolve_path(str_param(params, "db_path", "data/cache/market_scan.sqlite"), workspace)
    return {"status": SQLiteStore(db_path).data_status()}


def action_data_refresh_market_cache(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    db_path = resolve_path(str_param(params, "db_path", "data/cache/market_scan.sqlite"), workspace)
    result = refresh_market_daily_cache(
        AkshareProvider(),
        config=MarketCacheRefreshConfig(
            db_path=db_path,
            adjust=str_param(params, "adjust", "hfq"),
            start=date_param(params, "start"),
            end=date_param(params, "end"),
            probe_symbol=str_param(params, "probe_symbol", "000001"),
            limit=int_param(params, "limit", None),
            symbols=tuple(
                item.strip()
                for item in str_param(params, "symbols", "").split(",")
                if item.strip()
            ),
            retries=int_param(params, "retries", 3) or 3,
            retry_sleep_seconds=float_param(params, "retry_sleep", 1.0) or 0.0,
            request_sleep_seconds=float_param(params, "request_sleep", 0.0) or 0.0,
            dry_run=bool_param(params, "dry_run", True),
        ),
    )
    return {"refresh": result}


def action_import_daily_cache(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    config = LocalDailyCacheImportConfig(
        source_dir=resolve_path(str_param(params, "source_dir", "cache/daily_k/market_data_cache"), workspace),
        db_path=resolve_path(str_param(params, "db_path", "data/cache/market_scan.sqlite"), workspace),
        start=date_param(params, "start"),
        end=date_param(params, "end"),
        adjust=str_param(params, "adjust", "hfq"),
        provider=str_param(params, "provider", "local_daily_k"),
        conflict=str_param(params, "conflict", "ignore"),
        limit_files=int_param(params, "limit_files", None),
        dry_run=bool_param(params, "dry_run", True),
    )
    return {"import": import_local_daily_cache(config)}


def action_import_auction_cache(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    source_dir = optional_str(params, "auction_source_dir") or str_param(params, "source_dir", "cache/jingjia")
    config = LocalAuctionCacheImportConfig(
        source_dir=resolve_path(source_dir, workspace),
        db_path=resolve_path(str_param(params, "db_path", "data/cache/market_scan.sqlite"), workspace),
        start=date_param(params, "start"),
        end=date_param(params, "end"),
        provider=str_param(params, "provider", "local_jingjia"),
        start_time=str_param(params, "start_time", "09:15:00"),
        end_time=str_param(params, "end_time", "09:25:03"),
        conflict=str_param(params, "conflict", "ignore"),
        limit_archives=int_param(params, "limit_archives", None),
        limit_files=int_param(params, "limit_files", None),
        dry_run=bool_param(params, "dry_run", True),
    )
    return {"import": import_local_auction_cache(config)}


def action_strategy_list(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    del params, workspace
    return {"strategies": available_strategy_specs()}


def action_screen_candidates(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    as_of = effective_end_param(params)
    db_path = resolve_path(str_param(params, "db_path", "data/cache/market_scan.sqlite"), workspace)
    symbols = tuple(item.strip() for item in str_param(params, "symbols", "").split(",") if item.strip())
    result = run_cached_candidate_screen(
        config=CandidateScreenConfig(
            db_path=db_path,
            as_of=as_of,
            adjust=str_param(params, "adjust", "hfq"),
            lookback=int_param(params, "lookback", 180),
            top=int_param(params, "top", 30) or 30,
            limit=int_param(params, "limit", 500),
            auction_provider=optional_str(params, "auction_provider"),
            symbols=symbols,
        ),
        strategy=strategy_from_params(params),
    )
    return {"screen": result}


def action_morning_screen(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    db_path = resolve_path(str_param(params, "db_path", "data/cache/market_scan.sqlite"), workspace)
    symbols = tuple(item.strip() for item in str_param(params, "symbols", "").split(",") if item.strip())
    result = run_morning_screen(
        config=MorningScreenConfig(
            db_path=db_path,
            trade_date=required_date(params, "trade_date"),
            horizon=str_param(params, "horizon", "short_term"),
            strategy_id=optional_str(params, "strategy_id") or optional_str(params, "strategy"),
            adjust=str_param(params, "adjust", "hfq"),
            lookback=int_param(params, "lookback", 180),
            top=int_param(params, "top", 20) or 20,
            limit=int_param(params, "limit", 500),
            auction_provider=str_param(params, "auction_provider", "local_jingjia"),
            symbols=symbols,
        ),
        strategy=morning_strategy_from_params(params),
    )
    return {"morning_screen": result}


def action_trade_plan(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    symbol = symbol_param(params)
    db_path = resolve_path(str_param(params, "db_path", "data/cache/market_scan.sqlite"), workspace)
    result = run_morning_screen(
        config=MorningScreenConfig(
            db_path=db_path,
            trade_date=required_date(params, "trade_date"),
            horizon=str_param(params, "horizon", "short_term"),
            strategy_id=optional_str(params, "strategy_id") or optional_str(params, "strategy"),
            adjust=str_param(params, "adjust", "hfq"),
            lookback=int_param(params, "lookback", 180),
            top=1,
            limit=1,
            auction_provider=str_param(params, "auction_provider", "local_jingjia"),
            symbols=(symbol,),
        ),
        strategy=morning_strategy_from_params(params),
    )
    row = result.results[0] if result.results else None
    return {
        "symbol": symbol,
        "trade_date": required_date(params, "trade_date"),
        "horizon": str_param(params, "horizon", "short_term"),
        "strategy_id": result.strategy_id,
        "status": row.status if row is not None else "not_found",
        "candidate": row.candidate if row is not None else None,
        "trade_plan": row.trade_plan if row is not None else None,
        "auction_profile": row.auction_profile if row is not None else None,
        "latest_daily_date": row.latest_daily_date if row is not None else None,
        "error": row.error if row is not None else None,
    }


def action_validate_bars(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    bars = load_bars(params, workspace, symbol=symbol_param(params, required=False))
    issues = validate_daily_bars(bars)
    return {"bar_count": len(bars), "issue_count": len(issues), "issues": issues}


def action_indicators(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    bars = load_bars(params, workspace, symbol=symbol_param(params, required=False))
    ordered = sorted(bars, key=lambda item: item.trade_date)
    close_values = closes(ordered)
    window = int_param(params, "window", 14) or 14
    macd_values = macd(close_values)
    kdj_values = kdj(ordered)
    boll_values = bollinger_bands(close_values)
    return {
        "latest_date": ordered[-1].trade_date if ordered else None,
        "sma": latest_value(sma(close_values, window)),
        "ema": latest_value(ema(close_values, window)),
        "macd": latest_value(macd_values),
        "kdj": latest_value(kdj_values),
        "rsi": latest_value(rsi(close_values, window)),
        "boll": latest_value(boll_values),
        "atr": latest_value(atr(ordered, window)),
        "obv": latest_value(obv(ordered)),
    }


def action_screen_breakout(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    symbol = symbol_param(params)
    bars = load_bars(params, workspace, symbol=symbol)
    strategy = strategy_from_params(params)
    auction_profile = latest_auction_profile(load_auction_profiles(params, workspace, symbol, bars))
    candidate = strategy.evaluate(symbol, bars, auction_profile=auction_profile)
    return {"candidate": candidate, "auction_profile": auction_profile}


def action_signal_breakout(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    symbol = symbol_param(params)
    bars = load_bars(params, workspace, symbol=symbol)
    strategy = strategy_from_params(params)
    auction_profile = latest_auction_profile(load_auction_profiles(params, workspace, symbol, bars))
    candidate = strategy.evaluate(symbol, bars, auction_profile=auction_profile)
    signal = build_signal_if_candidate(candidate, bars, params)
    return {"candidate": candidate, "signal": signal, "auction_profile": auction_profile}


def action_backtest_breakout(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    symbol = symbol_param(params)
    bars = load_bars(params, workspace, symbol=symbol)
    result = run_breakout_backtest(
        symbol,
        bars,
        strategy=strategy_from_params(params),
        config=backtest_config_from_params(params),
        auction_profiles=load_auction_profiles(params, workspace, symbol, bars),
    )
    return {"backtest": result, "summary": summarize_backtest(result)}


def action_backtest_morning(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    symbol = symbol_param(params)
    db_path = resolve_path(str_param(params, "db_path", "data/cache/market_scan.sqlite"), workspace)
    store = SQLiteStore(db_path)
    start = required_date(params, "start")
    end = required_date(params, "end")
    bars = store.get_daily_bars(
        symbol,
        start=start,
        end=end,
        adjust=str_param(params, "adjust", "hfq"),
    )
    profiles = store.get_auction_profiles(
        symbol,
        start=start,
        end=end,
        provider=str_param(params, "auction_provider", "local_jingjia"),
    )
    result = run_morning_plan_backtest(
        symbol,
        bars,
        horizon=str_param(params, "horizon", "short_term"),
        strategy=morning_strategy_from_params(params),
        config=backtest_config_from_params(params),
        auction_profiles={profile.trade_date: profile for profile in profiles},
    )
    return {"backtest": result, "summary": summarize_backtest(result)}


def action_report_breakout(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    symbol = symbol_param(params)
    bars = load_bars(params, workspace, symbol=symbol)
    strategy = strategy_from_params(params)
    config = backtest_config_from_params(params)
    auction_profiles = load_auction_profiles(params, workspace, symbol, bars)
    candidate = strategy.evaluate(symbol, bars, auction_profile=latest_auction_profile(auction_profiles))
    signal = build_signal_if_candidate(candidate, bars, params)
    backtest = run_breakout_backtest(
        symbol,
        bars,
        strategy=strategy,
        config=config,
        auction_profiles=auction_profiles,
    )
    output_path = resolve_path(
        str_param(params, "output_path", f"reports/generated/web/{safe_name(symbol)}_report.md"),
        workspace,
    )
    content = build_markdown_report(
        title=str_param(params, "title", "MVP 策略报告"),
        candidate=candidate,
        signal=signal,
        backtest=backtest,
    )
    write_markdown_report(output_path, content)
    return {"path": path_result(output_path), "candidate": candidate, "signal": signal}


def action_dashboard(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    symbol = symbol_param(params)
    bars = load_bars(params, workspace, symbol=symbol)
    strategy = strategy_from_params(params)
    config = backtest_config_from_params(params)
    auction_profiles = load_auction_profiles(params, workspace, symbol, bars)
    candidate = strategy.evaluate(symbol, bars, auction_profile=latest_auction_profile(auction_profiles))
    signal = build_signal_if_candidate(candidate, bars, params)
    backtest = run_breakout_backtest(
        symbol,
        bars,
        strategy=strategy,
        config=config,
        auction_profiles=auction_profiles,
    )
    output_path = resolve_path(
        str_param(params, "output_path", f"reports/generated/web/{safe_name(symbol)}_dashboard.html"),
        workspace,
    )
    content = build_dashboard_html(
        title=str_param(params, "title", "A 股策略研究 Dashboard"),
        candidate=candidate,
        signal=signal,
        backtest=backtest,
        bars=bars,
        strategy=strategy,
        backtest_config=config,
        auction_profile=latest_auction_profile(auction_profiles),
        source_path=params.get("bars_path") or params.get("db_path") or "",
    )
    write_dashboard_html(output_path, content)
    return {"path": path_result(output_path), "summary": summarize_backtest(backtest)}


def action_scan_market(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    config = MarketScanConfig(
        start=date_param(params, "start") or DEFAULT_SCAN_START,
        end=date_param(params, "end") or DEFAULT_SCAN_END,
        adjust=str_param(params, "adjust", "hfq"),
        db_path=resolve_path(str_param(params, "db_path", "data/cache/market_scan.sqlite"), workspace),
        output_dir=resolve_path(str_param(params, "output_dir", "reports/generated/market_scan/web"), workspace),
        public_summary_path=resolve_path(
            str_param(params, "public_summary", "reports/summaries/web_market_scan.md"),
            workspace,
        ),
        top=int_param(params, "top", 30) or 30,
        limit=int_param(params, "limit", 3),
        retries=int_param(params, "retries", 3) or 3,
        retry_sleep_seconds=float_param(params, "retry_sleep", 1.0) or 0.0,
        request_sleep_seconds=float_param(params, "request_sleep", 0.0) or 0.0,
        request_timeout_seconds=float_param(params, "request_timeout", 60.0) or 60.0,
        auction_provider=optional_str(params, "auction_provider"),
    )
    result = run_market_scan(
        AkshareProvider(),
        config=config,
        strategy=strategy_from_params(params),
        backtest_config=backtest_config_from_params(params),
    )
    return {
        "scan": result,
        "public_summary": path_result(Path(result.public_summary_path)),
        "result_path": path_result(Path(result.result_path)),
        "failure_path": path_result(Path(result.failure_path)),
    }


def action_auction_compare(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    min_auction_score = float_param(params, "min_auction_score", 60.0)
    base_params = dict(params)
    base_params["min_auction_score"] = ""
    auction_params = dict(params)
    auction_params["min_auction_score"] = min_auction_score
    config = AuctionStrategyComparisonConfig(
        start=required_date(params, "start"),
        end=required_date(params, "end"),
        adjust=str_param(params, "adjust", "hfq"),
        db_path=resolve_path(str_param(params, "db_path", "data/cache/market_scan.sqlite"), workspace),
        output_dir=resolve_path(
            str_param(params, "output_dir", "reports/generated/auction_validation/web"),
            workspace,
        ),
        public_summary_path=resolve_path(
            str_param(params, "public_summary", "reports/summaries/web_auction_validation.md"),
            workspace,
        ),
        auction_provider=str_param(params, "auction_provider", "local_jingjia"),
        top=int_param(params, "top", 30) or 30,
        limit=int_param(params, "limit", None),
        min_auction_score=min_auction_score,
        auction_score_weight=float_param(params, "auction_score_weight", 0.15) or 0.15,
    )
    result = run_auction_strategy_comparison(
        config=config,
        baseline_strategy=strategy_from_params(base_params),
        auction_strategy=strategy_from_params(auction_params),
        backtest_config=backtest_config_from_params(params),
    )
    return {
        "comparison": result,
        "public_summary": path_result(Path(result.public_summary_path)),
        "result_path": path_result(Path(result.result_path)),
        "failure_path": path_result(Path(result.failure_path)),
    }


def action_factor_rank(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    del workspace
    rows_json = json_text(params, "rows_json", [])
    if not isinstance(rows_json, list):
        raise ValueError("factor rows must be a JSON array")
    rows = [
        FactorInput(symbol=str(item["symbol"]), factors=dict(item.get("factors", {})))
        for item in rows_json
        if isinstance(item, dict)
    ]
    weights_json = json_text(params, "weights_json", None)
    directions_json = json_text(params, "directions_json", None)
    scores = rank_factors(
        rows,
        weights=dict(weights_json) if isinstance(weights_json, dict) else None,
        higher_is_better=dict(directions_json) if isinstance(directions_json, dict) else None,
    )
    return {"scores": scores}


def action_research_linear(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    del workspace
    samples_json = json_text(params, "samples_json", [])
    if not isinstance(samples_json, list):
        raise ValueError("samples must be a JSON array")
    samples = [
        ResearchSample(
            symbol=str(item["symbol"]),
            features=dict(item.get("features", {})),
            target_return=float(item["target_return"]),
        )
        for item in samples_json
        if isinstance(item, dict)
    ]
    train, validation = split_train_validation(
        samples,
        train_ratio=float_param(params, "train_ratio", 0.7) or 0.7,
    )
    model = train_linear_baseline(train)
    predictions = predict_linear_baseline(model, validation)
    allocation = allocate_by_score(
        predictions,
        top_n=int_param(params, "top_n", 10) or 10,
        max_weight=float_param(params, "max_weight", 0.2) or 0.2,
    )
    return {
        "train_count": len(train),
        "validation_count": len(validation),
        "model": model,
        "predictions": predictions,
        "allocation": allocation,
    }


def action_auction_samples(params: dict[str, Any], workspace: Path) -> dict[str, Any]:
    symbol = symbol_param(params)
    bars = load_bars(params, workspace, symbol=symbol)
    profiles = load_auction_profiles(params, workspace, symbol, bars)
    samples = build_auction_research_samples(
        symbol,
        bars,
        profiles,
        lookahead_bars=int_param(params, "lookahead_bars", 1) or 1,
    )
    return {"sample_count": len(samples), "samples": samples[: int_param(params, "limit", 50)]}


def load_bars(
    params: Mapping[str, Any],
    workspace: Path,
    *,
    symbol: str | None = None,
) -> list[DailyBar]:
    end = effective_end_param(params)
    start = date_param(params, "start")
    lookback = int_param(params, "lookback", None)
    bars_path = optional_str(params, "bars_path")
    if bars_path:
        bars = read_daily_bars_jsonl(resolve_path(bars_path, workspace))
        if start is not None:
            bars = [bar for bar in bars if bar.trade_date >= start]
        return bars_up_to(bars, as_of=end, lookback=lookback)
    db_path_text = optional_str(params, "db_path")
    if db_path_text:
        db_symbol = symbol or symbol_param(params)
        bars = SQLiteStore(resolve_path(db_path_text, workspace)).get_daily_bars(
            db_symbol,
            start=start,
            end=end,
            adjust=optional_str(params, "adjust"),
        )
        return bars_up_to(bars, as_of=end, lookback=lookback)
    raise ValueError("需要填写 bars_path，或填写 db_path + symbol")


def load_auction_profiles(
    params: Mapping[str, Any],
    workspace: Path,
    symbol: str,
    bars: Sequence[DailyBar],
) -> dict[date, AuctionProfile]:
    provider = optional_str(params, "auction_provider")
    db_path_text = optional_str(params, "auction_db_path") or optional_str(params, "db_path")
    if not provider or not db_path_text:
        return {}
    start = bars[0].trade_date if bars else date_param(params, "start")
    end = bars[-1].trade_date if bars else date_param(params, "end")
    profiles = SQLiteStore(resolve_path(db_path_text, workspace)).get_auction_profiles(
        symbol,
        start=start,
        end=end,
        provider=provider,
    )
    return {profile.trade_date: profile for profile in profiles}


def latest_auction_profile(profiles: Mapping[date, AuctionProfile]) -> AuctionProfile | None:
    if not profiles:
        return None
    return profiles[max(profiles)]


def build_signal_if_candidate(
    candidate: Any,
    bars: Sequence[DailyBar],
    params: Mapping[str, Any],
) -> Any:
    if candidate is None:
        return None
    return build_breakout_signal(
        candidate,
        bars,
        atr_window=int_param(params, "atr_window", 14) or 14,
        stop_atr_multiple=float_param(params, "stop_atr_multiple", 2.0) or 2.0,
        take_profit_r_multiple=float_param(params, "take_profit_r_multiple", 2.0) or 2.0,
    )


def strategy_from_params(params: Mapping[str, Any]) -> ScreeningStrategy:
    return build_screening_strategy(
        str_param(params, "strategy_id", str_param(params, "strategy", "ma_volume_breakout")),
        short_window=int_param(params, "short_window", 5) or 5,
        medium_window=int_param(params, "medium_window", 20) or 20,
        long_window=int_param(params, "long_window", 60) or 60,
        volume_window=int_param(params, "volume_window", 20) or 20,
        breakout_window=int_param(params, "breakout_window", 20) or 20,
        min_volume_ratio=float_param(params, "min_volume_ratio", 1.5) or 1.5,
        min_auction_score=float_param(params, "min_auction_score", None),
        auction_score_weight=float_param(params, "auction_score_weight", 0.15) or 0.15,
    )


def morning_strategy_from_params(params: Mapping[str, Any]) -> ScreeningStrategy | None:
    if not (optional_str(params, "strategy_id") or optional_str(params, "strategy")):
        return None
    return strategy_from_params(params)


def backtest_config_from_params(params: Mapping[str, Any]) -> BacktestConfig:
    return BacktestConfig(
        initial_cash=float_param(params, "initial_cash", 100_000.0) or 100_000.0,
        commission_rate=float_param(params, "commission_rate", 0.0003) or 0.0,
        slippage_rate=float_param(params, "slippage_rate", 0.0005) or 0.0,
        max_holding_bars=int_param(params, "max_holding_bars", 20) or 20,
        atr_window=int_param(params, "atr_window", 14) or 14,
        stop_atr_multiple=float_param(params, "stop_atr_multiple", 2.0) or 2.0,
        take_profit_r_multiple=float_param(params, "take_profit_r_multiple", 2.0) or 2.0,
    )


def read_daily_bars_jsonl(path: Path) -> list[DailyBar]:
    bars: list[DailyBar] = []
    with path.open(encoding="utf-8") as file:
        for line in file:
            if line.strip():
                bars.append(daily_bar_from_mapping(json.loads(line)))
    return bars


def daily_bar_from_mapping(row: Mapping[str, Any]) -> DailyBar:
    fetched_at = row.get("fetched_at")
    return DailyBar(
        symbol=str(row["symbol"]),
        trade_date=date.fromisoformat(str(row["trade_date"])),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        volume=float(row["volume"]),
        amount=optional_float(row.get("amount")),
        turnover=optional_float(row.get("turnover")),
        adjust=optional_str(row, "adjust"),
        provider=optional_str(row, "provider"),
        fetched_at=datetime.fromisoformat(str(fetched_at)) if fetched_at else None,
    )


def write_jsonl(path: Path, records: Sequence[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(to_jsonable(record), ensure_ascii=False, sort_keys=True) + "\n")


def summarize_backtest(backtest: BacktestResult) -> dict[str, Any]:
    return {
        "symbol": backtest.symbol,
        "total_return": backtest.total_return,
        "max_drawdown": backtest.max_drawdown,
        "win_rate": backtest.win_rate,
        "trade_count": backtest.trade_count,
        "equity_points": len(backtest.equity_curve),
        "trades": backtest.trades,
    }


def latest_value(values: Sequence[Any]) -> Any:
    for value in reversed(values):
        if value is not None:
            return value
    return None


def list_limited(records: Sequence[Any] | Any, limit: int | None) -> list[Any]:
    result: list[Any] = []
    for index, record in enumerate(records):
        if limit is not None and index >= limit:
            break
        result.append(record)
    return result


def resolve_path(value: str | Path, workspace: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = workspace / path
    return path.resolve()


def path_result(path: Path) -> dict[str, str]:
    return {"path": str(path), "url": f"/file?path={quote(str(path))}"}


def content_type_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm"}:
        return "text/html; charset=utf-8"
    if suffix == ".md":
        return "text/markdown; charset=utf-8"
    if suffix in {".json", ".jsonl"}:
        return "application/json; charset=utf-8"
    return "text/plain; charset=utf-8"


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def symbol_param(params: Mapping[str, Any], *, required: bool = True) -> str:
    symbol = optional_str(params, "symbol")
    if not symbol and required:
        raise ValueError("symbol is required")
    return symbol or ""


def str_param(params: Mapping[str, Any], key: str, default: str) -> str:
    value = params.get(key)
    if value is None or value == "":
        return default
    return str(value)


def optional_str(params: Mapping[str, Any], key: str) -> str | None:
    value = params.get(key)
    if value is None or value == "":
        return None
    return str(value)


def int_param(params: Mapping[str, Any], key: str, default: int | None) -> int | None:
    value = params.get(key)
    if value is None or value == "":
        return default
    return int(value)


def float_param(params: Mapping[str, Any], key: str, default: float | None) -> float | None:
    value = params.get(key)
    if value is None or value == "":
        return default
    return float(value)


def bool_param(params: Mapping[str, Any], key: str, default: bool = False) -> bool:
    value = params.get(key)
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}


def date_param(params: Mapping[str, Any], key: str) -> date | None:
    value = optional_str(params, key)
    if value is None:
        return None
    return date.fromisoformat(value)


def required_date(params: Mapping[str, Any], key: str) -> date:
    value = date_param(params, key)
    if value is None:
        raise ValueError(f"{key} is required")
    return value


def effective_end_param(params: Mapping[str, Any]) -> date | None:
    end = date_param(params, "end")
    as_of = date_param(params, "as_of")
    if end is not None and as_of is not None and end != as_of:
        raise ValueError("end and as_of must match when both are provided")
    return as_of or end


def optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def json_text(params: Mapping[str, Any], key: str, default: Any) -> Any:
    text = optional_str(params, key)
    if text is None:
        return default
    return json.loads(text)


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value)


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return to_jsonable(asdict(value))  # type: ignore[arg-type]
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


def build_app_html() -> str:
    return APP_HTML


APP_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>gupiao Web 工作台</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f6f8;
      --surface: #ffffff;
      --soft: #f9fafb;
      --text: #17202c;
      --muted: #657284;
      --line: #d9e0ea;
      --accent: #1d5fd1;
      --good: #08764f;
      --bad: #b42318;
      --warn: #9a5b00;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, "Noto Sans SC", "Microsoft YaHei", sans-serif;
      line-height: 1.5;
    }
    header {
      position: sticky;
      top: 0;
      z-index: 2;
      background: var(--surface);
      border-bottom: 1px solid var(--line);
    }
    .wrap { width: min(1380px, calc(100% - 32px)); margin: 0 auto; }
    .topbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 16px 0 12px;
    }
    h1 { margin: 0; font-size: 24px; letter-spacing: 0; }
    .status {
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      padding: 4px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      background: var(--soft);
      font-size: 13px;
      white-space: nowrap;
    }
    .modebar {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .modebar button {
      border: 1px solid var(--accent);
      background: var(--surface);
      color: var(--accent);
      border-radius: 7px;
      min-height: 32px;
      padding: 5px 10px;
      cursor: pointer;
      font-weight: 800;
    }
    body.advanced .modebar button {
      background: var(--accent);
      color: #fff;
    }
    body:not(.advanced) .advanced-only { display: none !important; }
    nav {
      display: flex;
      overflow-x: auto;
      gap: 8px;
      padding-bottom: 10px;
    }
    nav button {
      border: 1px solid var(--line);
      background: var(--soft);
      color: var(--text);
      border-radius: 7px;
      min-height: 34px;
      padding: 6px 12px;
      cursor: pointer;
      font-weight: 700;
      white-space: nowrap;
    }
    nav button.active { background: var(--accent); border-color: var(--accent); color: #fff; }
    main {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(360px, 0.44fr);
      gap: 16px;
      padding: 18px 0 42px;
    }
    .tabs > section { display: none; }
    .tabs > section.active { display: block; }
    h2 { margin: 0 0 14px; font-size: 20px; letter-spacing: 0; }
    h3 { margin: 0 0 10px; font-size: 15px; letter-spacing: 0; }
    .grid { display: grid; gap: 12px; }
    .two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .four { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .panel {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      margin-bottom: 14px;
    }
    .action-card {
      display: grid;
      align-content: start;
      min-height: 210px;
      border-top: 4px solid var(--accent);
    }
    .mini {
      color: var(--muted);
      font-size: 13px;
      margin: -4px 0 0;
    }
    .hidden-fields { display: none; }
    label {
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    input, select, textarea {
      width: 100%;
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 7px 9px;
      color: var(--text);
      background: #fff;
      font: inherit;
      font-size: 14px;
    }
    textarea {
      min-height: 128px;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      resize: vertical;
    }
    .row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin-top: 12px;
    }
    .row button {
      border: 1px solid var(--accent);
      background: var(--accent);
      color: #fff;
      border-radius: 7px;
      min-height: 36px;
      padding: 7px 12px;
      cursor: pointer;
      font-weight: 800;
    }
    .row button.secondary {
      background: var(--surface);
      color: var(--accent);
    }
    .result {
      position: sticky;
      top: 112px;
      align-self: start;
      background: #111827;
      color: #e5e7eb;
      border-radius: 8px;
      min-height: 520px;
      overflow: hidden;
      border: 1px solid #202938;
    }
    .result-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      padding: 10px 12px;
      border-bottom: 1px solid #263244;
      color: #cbd5e1;
    }
    .result-head button {
      min-height: 30px;
      border-radius: 6px;
      border: 1px solid #334155;
      background: #1f2937;
      color: #e5e7eb;
      cursor: pointer;
    }
    pre {
      margin: 0;
      padding: 12px;
      max-height: calc(100vh - 190px);
      overflow: auto;
      font-size: 13px;
      line-height: 1.55;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .links {
      display: grid;
      gap: 8px;
      padding: 10px 12px;
      border-bottom: 1px solid #263244;
    }
    .links a { color: #93c5fd; }
    .summary {
      display: grid;
      gap: 10px;
      padding: 12px;
      border-bottom: 1px solid #263244;
      background: #172033;
    }
    .summary:empty { display: none; }
    .summary-card {
      border: 1px solid #334155;
      border-radius: 7px;
      padding: 10px;
      background: #111827;
    }
    .summary-card h3 {
      margin: 0 0 8px;
      color: #f8fafc;
      font-size: 14px;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }
    .summary-item {
      border: 1px solid #263244;
      border-radius: 6px;
      padding: 8px;
      background: #0f172a;
      color: #cbd5e1;
      font-size: 12px;
    }
    .summary-item strong {
      display: block;
      color: #f8fafc;
      font-size: 16px;
    }
    .summary table {
      width: 100%;
      border-collapse: collapse;
      color: #dbeafe;
      font-size: 12px;
    }
    .summary th, .summary td {
      border-bottom: 1px solid #263244;
      padding: 6px;
      text-align: left;
    }
    .summary th { color: #93c5fd; }
    .muted { color: var(--muted); }
    @media (max-width: 980px) {
      main { grid-template-columns: 1fr; }
      .result { position: static; }
      .two, .three, .four, .summary-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div class="wrap">
      <div class="topbar">
        <h1>gupiao Web 工作台</h1>
        <div class="modebar">
          <button id="modeToggle" type="button" title="显示或隐藏完整参数">普通模式</button>
          <span class="status" id="health">连接中</span>
        </div>
      </div>
      <nav id="tabs">
        <button class="active" data-tab="home">工作台</button>
        <button class="advanced-only" data-tab="quick">快速分析</button>
        <button class="advanced-only" data-tab="data">数据</button>
        <button class="advanced-only" data-tab="strategy">策略</button>
        <button class="advanced-only" data-tab="scan">扫描</button>
        <button class="advanced-only" data-tab="research">研究</button>
      </nav>
    </div>
  </header>
  <main class="wrap">
    <div class="tabs">
      <section id="home" class="active">
        <div class="panel">
          <h2>常用操作</h2>
          <div class="grid four">
            <form id="homeStatusForm" class="panel action-card">
              <h3>缓存状态</h3>
              <p class="mini">查看本地日K和竞价数据覆盖到哪一天。</p>
              <div class="hidden-fields">
                <input name="db_path" value="data/cache/market_scan.sqlite">
              </div>
              <div class="row">
                <button type="button" data-action="data_status" data-form="homeStatusForm">查看缓存</button>
              </div>
            </form>
            <form id="homeCandidateForm" class="panel action-card">
              <h3>早盘选股</h3>
              <p class="mini">用交易日竞价和前一日K线选出可开盘观察的候选。</p>
              <label>交易日期<input name="trade_date" value="2026-05-29"></label>
              <label>周期<select name="horizon">
                <option value="short_term">短线</option>
                <option value="mid_short_term">中短线</option>
                <option value="mid_term">中线</option>
              </select></label>
              <div class="hidden-fields">
                <input name="db_path" value="data/cache/market_scan.sqlite">
                <input name="adjust" value="hfq">
                <input name="top" value="20">
                <input name="limit" value="500">
                <input name="lookback" value="180">
                <input name="auction_provider" value="local_jingjia">
              </div>
              <div class="row">
                <button type="button" data-action="morning_screen" data-form="homeCandidateForm">开始选股</button>
              </div>
            </form>
            <form id="homeSingleForm" class="panel action-card">
              <h3>买卖计划</h3>
              <p class="mini">查看单只股票早盘是否命中，以及什么时候买、怎么卖。</p>
              <label>股票代码<input name="symbol" value="000001"></label>
              <label>交易日期<input name="trade_date" value="2026-05-29"></label>
              <label>周期<select name="horizon">
                <option value="short_term">短线</option>
                <option value="mid_short_term">中短线</option>
                <option value="mid_term">中线</option>
              </select></label>
              <div class="hidden-fields">
                <input name="db_path" value="data/cache/market_scan.sqlite">
                <input name="adjust" value="hfq">
                <input name="lookback" value="180">
                <input name="auction_provider" value="local_jingjia">
              </div>
              <div class="row">
                <button type="button" data-action="trade_plan" data-form="homeSingleForm">查看计划</button>
              </div>
            </form>
            <form id="homeRefreshForm" class="panel action-card">
              <h3>补齐日K</h3>
              <p class="mini">先预览缺口，确认后在专业模式执行写入。</p>
              <label>补到日期<input name="end" value="2026-06-10"></label>
              <label>探针股票<input name="probe_symbol" value="000001"></label>
              <div class="hidden-fields">
                <input name="db_path" value="data/cache/market_scan.sqlite">
                <input name="adjust" value="hfq">
                <input name="dry_run" value="true">
                <input name="request_sleep" value="0">
                <input name="retry_sleep" value="1">
                <input name="retries" value="3">
              </div>
              <div class="row">
                <button type="button" data-action="data_refresh_market_cache" data-form="homeRefreshForm">查看缺口</button>
              </div>
            </form>
          </div>
        </div>
      </section>
      <section id="quick" class="advanced-only">
        <div class="panel">
          <h2>快速分析</h2>
          <form id="quickForm" class="grid">
            <div class="grid two">
              <label>股票代码<input name="symbol" value="000001"></label>
              <label>日线 JSONL<input name="bars_path" value=""></label>
              <label>SQLite DB<input name="db_path" value="data/cache/market_scan.sqlite"></label>
              <label>输出目录<input name="output_dir" value="reports/generated/web"></label>
              <label>截至日期<input name="as_of" value=""></label>
              <label>lookback<input name="lookback" value=""></label>
            </div>
            <div data-common="strategy"></div>
            <div data-common="backtest"></div>
            <div class="grid three">
              <label>竞价 DB<input name="auction_db_path" value="data/cache/market_scan.sqlite"></label>
              <label>竞价 provider<input name="auction_provider" value=""></label>
              <label>报告标题<input name="report_title" value="MVP 策略报告"></label>
            </div>
            <div class="row">
              <button type="button" data-action="quick_analysis" data-form="quickForm">一键选股/信号/回测/报告</button>
              <button type="button" class="secondary" data-action="validate_bars" data-form="quickForm">数据质量</button>
              <button type="button" class="secondary" data-action="indicators" data-form="quickForm">技术指标</button>
            </div>
          </form>
        </div>
      </section>
      <section id="data" class="advanced-only">
        <div class="panel">
          <h2>数据接入</h2>
          <form id="dataForm" class="grid">
            <div class="grid three">
              <label>股票代码<input name="symbol" value="000001"></label>
              <label>开始日期<input name="start" value="2026-01-01"></label>
              <label>结束日期<input name="end" value="2026-06-10"></label>
              <label>复权<select name="adjust"><option>hfq</option><option>qfq</option><option>raw</option></select></label>
              <label>保存 JSONL<input name="save_path" value="data/000001_daily.jsonl"></label>
              <label>DB 路径<input name="db_path" value="data/gupiao.sqlite"></label>
              <label>列表 limit<input name="limit" value="20"></label>
              <label>预览 limit<input name="preview_limit" value="20"></label>
            </div>
            <div class="row">
              <button type="button" data-action="data_instruments" data-form="dataForm">股票列表</button>
              <button type="button" data-action="data_daily" data-form="dataForm">拉取日线</button>
              <button type="button" data-action="data_update_daily" data-form="dataForm">写入 SQLite</button>
              <button type="button" class="secondary" data-action="data_status" data-form="dataForm">缓存状态</button>
            </div>
          </form>
        </div>
        <div class="panel">
          <h2>竞价与缓存</h2>
          <form id="cacheForm" class="grid">
            <div class="grid three">
              <label>股票代码<input name="symbol" value="000001"></label>
              <label>开始时间<input name="start_time" value="09:15:00"></label>
              <label>结束时间<input name="end_time" value="09:25:03"></label>
              <label>昨收<input name="previous_close" value=""></label>
              <label>平均日量<input name="average_daily_volume" value=""></label>
              <label>竞价保存 JSONL<input name="save_path" value=""></label>
              <label>日K缓存目录<input name="source_dir" value="cache/daily_k/market_data_cache"></label>
              <label>竞价缓存目录<input name="auction_source_dir" value="cache/jingjia"></label>
              <label>DB 路径<input name="db_path" value="data/cache/market_scan.sqlite"></label>
              <label>开始日期<input name="start" value=""></label>
              <label>结束日期<input name="end" value=""></label>
              <label>探针股票<input name="probe_symbol" value="000001"></label>
              <label>股票列表<input name="symbols" value=""></label>
              <label>provider<input name="provider" value="local_jingjia"></label>
              <label>冲突<select name="conflict"><option>ignore</option><option>replace</option></select></label>
              <label>limit files<input name="limit_files" value=""></label>
              <label>limit archives<input name="limit_archives" value=""></label>
              <label>处理上限<input name="limit" value=""></label>
              <label>重试<input name="retries" value="3"></label>
              <label>请求间隔<input name="request_sleep" value="0"></label>
              <label>重试间隔<input name="retry_sleep" value="1"></label>
              <label>dry-run<select name="dry_run"><option value="true">true</option><option value="false">false</option></select></label>
            </div>
            <div class="row">
              <button type="button" data-action="data_pre_market" data-form="cacheForm">拉取竞价</button>
              <button type="button" class="secondary" data-action="import_daily_cache" data-form="cacheForm">导入日K缓存</button>
              <button type="button" class="secondary" data-action="data_refresh_market_cache" data-form="cacheForm">补齐日K缺口</button>
              <button type="button" class="secondary" data-action="import_auction_cache" data-form="cacheForm">导入竞价缓存</button>
            </div>
          </form>
        </div>
      </section>
      <section id="strategy" class="advanced-only">
        <div class="panel">
          <h2>选股与回测</h2>
          <form id="strategyForm" class="grid">
            <div class="grid three">
              <label>股票代码<input name="symbol" value="000001"></label>
              <label>日线 JSONL<input name="bars_path" value=""></label>
              <label>SQLite DB<input name="db_path" value="data/cache/market_scan.sqlite"></label>
              <label>开始日期<input name="start" value=""></label>
              <label>结束日期<input name="end" value=""></label>
              <label>截至日期<input name="as_of" value=""></label>
              <label>lookback<input name="lookback" value=""></label>
              <label>复权<input name="adjust" value="hfq"></label>
            </div>
            <div data-common="strategy"></div>
            <div data-common="backtest"></div>
            <div class="grid three">
              <label>竞价 DB<input name="auction_db_path" value="data/cache/market_scan.sqlite"></label>
              <label>竞价 provider<input name="auction_provider" value=""></label>
              <label>产物路径<input name="output_path" value="reports/generated/web/000001_dashboard.html"></label>
            </div>
            <div class="row">
              <button type="button" data-action="screen_breakout" data-form="strategyForm">选股</button>
              <button type="button" data-action="signal_breakout" data-form="strategyForm">买卖点</button>
              <button type="button" data-action="backtest_breakout" data-form="strategyForm">回测</button>
              <button type="button" class="secondary" data-action="report_breakout" data-form="strategyForm">报告</button>
              <button type="button" class="secondary" data-action="dashboard" data-form="strategyForm">Dashboard</button>
            </div>
          </form>
        </div>
        <div class="panel">
          <h2>缓存批量选股</h2>
          <form id="candidateForm" class="grid">
            <div class="grid three">
              <label>SQLite DB<input name="db_path" value="data/cache/market_scan.sqlite"></label>
              <label>截至日期<input name="as_of" value="2026-05-29"></label>
              <label>复权<input name="adjust" value="hfq"></label>
              <label>Top<input name="top" value="30"></label>
              <label>处理上限<input name="limit" value="500"></label>
              <label>lookback<input name="lookback" value="180"></label>
              <label>股票列表<input name="symbols" value=""></label>
              <label>竞价 provider<input name="auction_provider" value="local_jingjia"></label>
            </div>
            <div data-common="strategy"></div>
            <div class="row">
              <button type="button" data-action="screen_candidates" data-form="candidateForm">缓存候选</button>
              <button type="button" class="secondary" data-action="strategy_list" data-form="candidateForm">策略列表</button>
              <button type="button" class="secondary" data-action="data_status" data-form="candidateForm">缓存状态</button>
            </div>
          </form>
        </div>
      </section>
      <section id="scan" class="advanced-only">
        <div class="panel">
          <h2>全市场扫描</h2>
          <form id="scanForm" class="grid">
            <div class="grid three">
              <label>开始日期<input name="start" value="2026-01-01"></label>
              <label>结束日期<input name="end" value="2026-06-10"></label>
              <label>复权<input name="adjust" value="hfq"></label>
              <label>DB 路径<input name="db_path" value="data/cache/market_scan.sqlite"></label>
              <label>输出目录<input name="output_dir" value="reports/generated/market_scan/web"></label>
              <label>公开汇总<input name="public_summary" value="reports/summaries/web_market_scan.md"></label>
              <label>Top<input name="top" value="30"></label>
              <label>Limit<input name="limit" value="3"></label>
              <label>竞价 provider<input name="auction_provider" value=""></label>
              <label>重试<input name="retries" value="3"></label>
              <label>请求间隔<input name="request_sleep" value="0"></label>
              <label>超时<input name="request_timeout" value="60"></label>
            </div>
            <div data-common="strategy"></div>
            <div data-common="backtest"></div>
            <div class="row">
              <button type="button" data-action="scan_market" data-form="scanForm">运行扫描</button>
            </div>
          </form>
        </div>
        <div class="panel">
          <h2>竞价增强对比</h2>
          <form id="auctionCompareForm" class="grid">
            <div class="grid three">
              <label>开始日期<input name="start" value="2026-01-01"></label>
              <label>结束日期<input name="end" value="2026-05-29"></label>
              <label>DB 路径<input name="db_path" value="data/cache/market_scan.sqlite"></label>
              <label>输出目录<input name="output_dir" value="reports/generated/auction_validation/web"></label>
              <label>公开汇总<input name="public_summary" value="reports/summaries/web_auction_validation.md"></label>
              <label>竞价 provider<input name="auction_provider" value="local_jingjia"></label>
              <label>Top<input name="top" value="30"></label>
              <label>Limit<input name="limit" value=""></label>
            </div>
            <div data-common="strategy"></div>
            <div data-common="backtest"></div>
            <div class="row">
              <button type="button" data-action="auction_compare" data-form="auctionCompareForm">运行对比</button>
            </div>
          </form>
        </div>
      </section>
      <section id="research" class="advanced-only">
        <div class="panel">
          <h2>多因子评分</h2>
          <form id="factorForm" class="grid">
            <label>因子数据<textarea name="rows_json">[
  {"symbol":"000001","factors":{"value":0.8,"quality":0.9,"growth":0.7,"momentum":0.8,"volatility":0.2,"liquidity":0.9}},
  {"symbol":"000002","factors":{"value":0.2,"quality":0.4,"growth":0.3,"momentum":0.2,"volatility":0.9,"liquidity":0.3}}
]</textarea></label>
            <div class="grid two">
              <label>权重 JSON<textarea name="weights_json"></textarea></label>
              <label>方向 JSON<textarea name="directions_json"></textarea></label>
            </div>
            <div class="row">
              <button type="button" data-action="factor_rank" data-form="factorForm">因子排名</button>
            </div>
          </form>
        </div>
        <div class="panel">
          <h2>轻量研究</h2>
          <form id="researchForm" class="grid">
            <label>样本 JSON<textarea name="samples_json">[
  {"symbol":"000001","features":{"momentum":0.1,"quality":0.2},"target_return":0.01},
  {"symbol":"000002","features":{"momentum":0.2,"quality":0.3},"target_return":0.02},
  {"symbol":"000003","features":{"momentum":0.3,"quality":0.4},"target_return":0.03},
  {"symbol":"000004","features":{"momentum":0.4,"quality":0.5},"target_return":0.04},
  {"symbol":"000005","features":{"momentum":0.5,"quality":0.6},"target_return":0.05}
]</textarea></label>
            <div class="grid three">
              <label>训练比例<input name="train_ratio" value="0.7"></label>
              <label>Top N<input name="top_n" value="10"></label>
              <label>权重上限<input name="max_weight" value="0.2"></label>
            </div>
            <div class="row">
              <button type="button" data-action="research_linear" data-form="researchForm">训练/预测/配置权重</button>
            </div>
          </form>
        </div>
        <div class="panel">
          <h2>竞价研究样本</h2>
          <form id="auctionSampleForm" class="grid">
            <div class="grid three">
              <label>股票代码<input name="symbol" value="000001"></label>
              <label>日线 JSONL<input name="bars_path" value=""></label>
              <label>DB 路径<input name="db_path" value="data/cache/market_scan.sqlite"></label>
              <label>竞价 provider<input name="auction_provider" value="local_jingjia"></label>
              <label>lookahead<input name="lookahead_bars" value="1"></label>
              <label>返回 limit<input name="limit" value="50"></label>
            </div>
            <div class="row">
              <button type="button" data-action="auction_samples" data-form="auctionSampleForm">生成样本</button>
            </div>
          </form>
        </div>
      </section>
    </div>
    <aside class="result">
      <div class="result-head">
        <strong>结果</strong>
        <button id="clearResult" type="button">清空</button>
      </div>
      <div id="links" class="links"></div>
      <div id="summary" class="summary"></div>
      <pre id="output">等待操作</pre>
    </aside>
  </main>
  <template id="strategyTemplate">
    <div class="grid three">
      <label>策略<select name="strategy_id">
        <option value="auction_open_breakout_short">短线竞价开盘突破</option>
        <option value="auction_gap_reversal_short">短线竞价温和缺口修复</option>
        <option value="volume_breakout_swing">中短线放量突破</option>
        <option value="pullback_recovery_swing">中短线回踩修复</option>
        <option value="trend_quality_mid">中线趋势质量</option>
        <option value="ma_volume_breakout">均线多头放量突破</option>
        <option value="momentum_pullback">趋势回踩修复</option>
        <option value="low_volatility_breakout">低波动突破</option>
        <option value="auction_assisted_breakout">竞价辅助突破</option>
      </select></label>
      <label>短均线<input name="short_window" value="5"></label>
      <label>中均线<input name="medium_window" value="20"></label>
      <label>长均线<input name="long_window" value="60"></label>
      <label>量均线<input name="volume_window" value="20"></label>
      <label>突破窗口<input name="breakout_window" value="20"></label>
      <label>最小量比<input name="min_volume_ratio" value="1.5"></label>
      <label>最小竞价分<input name="min_auction_score" value=""></label>
      <label>竞价权重<input name="auction_score_weight" value="0.15"></label>
      <label>指标窗口<input name="window" value="14"></label>
    </div>
  </template>
  <template id="backtestTemplate">
    <div class="grid three">
      <label>ATR窗口<input name="atr_window" value="14"></label>
      <label>止损ATR倍数<input name="stop_atr_multiple" value="2.0"></label>
      <label>止盈R倍数<input name="take_profit_r_multiple" value="2.0"></label>
      <label>初始资金<input name="initial_cash" value="100000"></label>
      <label>手续费<input name="commission_rate" value="0.0003"></label>
      <label>滑点<input name="slippage_rate" value="0.0005"></label>
      <label>最长持有<input name="max_holding_bars" value="20"></label>
    </div>
  </template>
  <script>
    const output = document.querySelector("#output");
    const links = document.querySelector("#links");
    const summary = document.querySelector("#summary");
    const health = document.querySelector("#health");
    const modeToggle = document.querySelector("#modeToggle");

    document.querySelectorAll("[data-common='strategy']").forEach((node) => {
      node.append(document.querySelector("#strategyTemplate").content.cloneNode(true));
    });
    document.querySelectorAll("[data-common='backtest']").forEach((node) => {
      node.append(document.querySelector("#backtestTemplate").content.cloneNode(true));
    });

    document.querySelectorAll("#tabs button").forEach((button) => {
      button.addEventListener("click", () => {
        document.querySelectorAll("#tabs button").forEach((item) => item.classList.remove("active"));
        document.querySelectorAll(".tabs > section").forEach((item) => item.classList.remove("active"));
        button.classList.add("active");
        document.querySelector("#" + button.dataset.tab).classList.add("active");
      });
    });

    document.querySelectorAll("[data-action]").forEach((button) => {
      button.addEventListener("click", () => runAction(button.dataset.action, button.dataset.form));
    });

    document.querySelector("#clearResult").addEventListener("click", () => {
      links.innerHTML = "";
      summary.innerHTML = "";
      output.textContent = "等待操作";
    });

    modeToggle.addEventListener("click", () => {
      document.body.classList.toggle("advanced");
      const advanced = document.body.classList.contains("advanced");
      modeToggle.textContent = advanced ? "专业模式" : "普通模式";
      if (!advanced) {
        activateTab("home");
      }
    });

    async function runAction(action, formId) {
      const form = document.querySelector("#" + formId);
      const params = collectForm(form);
      output.textContent = "运行中: " + action;
      links.innerHTML = "";
      summary.innerHTML = "";
      try {
        const response = await fetch("/api/run", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({action, params})
        });
        const payload = await response.json();
        renderLinks(payload);
        renderSummary(payload);
        output.textContent = JSON.stringify(payload, null, 2);
      } catch (error) {
        summary.innerHTML = errorCard(String(error));
        output.textContent = String(error);
      }
    }

    function collectForm(form) {
      const params = {};
      new FormData(form).forEach((value, key) => {
        if (value !== "") params[key] = value;
      });
      return params;
    }

    function activateTab(tabId) {
      document.querySelectorAll("#tabs button").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".tabs > section").forEach((item) => item.classList.remove("active"));
      const button = document.querySelector(`#tabs button[data-tab="${tabId}"]`);
      const section = document.querySelector("#" + tabId);
      if (button) button.classList.add("active");
      if (section) section.classList.add("active");
    }

    function renderLinks(value) {
      const found = [];
      visit(value, found);
      links.innerHTML = found.map((item) => `<a href="${item.url}" target="_blank">${item.path}</a>`).join("");
    }

    function visit(value, found) {
      if (!value || typeof value !== "object") return;
      if (value.path && value.url) found.push(value);
      if (Array.isArray(value)) {
        value.forEach((item) => visit(item, found));
      } else {
        Object.values(value).forEach((item) => visit(item, found));
      }
    }

    function renderSummary(payload) {
      if (!payload.ok) {
        summary.innerHTML = errorCard(payload.error || "操作失败");
        return;
      }
      const result = payload.result || {};
      if (result.morning_screen) {
        summary.innerHTML = morningScreenSummary(result.morning_screen);
      } else if (result.trade_plan || result.strategy_id) {
        summary.innerHTML = tradePlanSummary(result);
      } else if (result.status && typeof result.status === "object") {
        summary.innerHTML = statusSummary(result.status);
      } else if (result.screen) {
        summary.innerHTML = screenSummary(result.screen);
      } else if (result.candidate || result.signal || result.backtest) {
        summary.innerHTML = analysisSummary(result);
      } else if (result.refresh) {
        summary.innerHTML = refreshSummary(result.refresh);
      } else if (result.strategies) {
        summary.innerHTML = strategySummary(result.strategies);
      } else {
        summary.innerHTML = card("完成", `<div class="summary-item"><strong>OK</strong>${escapeHtml(payload.action || "操作完成")}</div>`);
      }
    }

    function statusSummary(status) {
      const daily = status.daily_bars || {};
      const auction = status.auction_profiles || {};
      return card("缓存状态", grid([
        ["日K最新", daily.end || "-"],
        ["日K股票", daily.symbols ?? "-"],
        ["日K行数", daily.rows ?? "-"],
        ["竞价最新", auction.end || "-"],
        ["竞价股票", auction.symbols ?? "-"],
        ["竞价行数", auction.rows ?? "-"]
      ]));
    }

    function screenSummary(screen) {
      const rows = (screen.candidates || []).slice(0, 10);
      const tableRows = rows.map((row, index) => {
        const candidate = row.candidate || {};
        return `<tr><td>${index + 1}</td><td>${escapeHtml(row.symbol || "")}</td><td>${escapeHtml(row.name || "")}</td><td>${escapeHtml(candidate.strategy || "")}</td><td>${candidate.score ?? "-"}</td><td>${escapeHtml(candidate.trade_date || "")}</td></tr>`;
      }).join("");
      const table = tableRows ? `<table><thead><tr><th>#</th><th>代码</th><th>名称</th><th>策略</th><th>分数</th><th>日期</th></tr></thead><tbody>${tableRows}</tbody></table>` : `<div class="summary-item"><strong>0</strong>暂无候选</div>`;
      return card("批量选股", grid([
        ["处理", screen.processed ?? "-"],
        ["候选", screen.candidate_count ?? "-"],
        ["无数据", screen.no_data ?? "-"]
      ]) + table);
    }

    function morningScreenSummary(screen) {
      const rows = (screen.candidates || []).slice(0, 10);
      const tableRows = rows.map((row, index) => {
        const candidate = row.candidate || {};
        const plan = row.trade_plan || {};
        return `<tr><td>${index + 1}</td><td>${escapeHtml(row.symbol || "")}</td><td>${escapeHtml(row.name || "")}</td><td>${escapeHtml(plan.horizon_name || "")}</td><td>${escapeHtml(candidate.strategy || "")}</td><td>${candidate.score ?? "-"}</td><td>${formatPrice(plan.reference_entry_price)}</td><td>${formatPrice(plan.stop_loss)}</td></tr>`;
      }).join("");
      const table = tableRows ? `<table><thead><tr><th>#</th><th>代码</th><th>名称</th><th>周期</th><th>策略</th><th>分数</th><th>参考买入</th><th>止损</th></tr></thead><tbody>${tableRows}</tbody></table>` : `<div class="summary-item"><strong>0</strong>暂无早盘候选</div>`;
      return card("早盘选股", grid([
        ["交易日", screen.config ? screen.config.trade_date : "-"],
        ["策略", screen.strategy_id || "-"],
        ["候选", screen.candidate_count ?? "-"],
        ["缺竞价", screen.no_auction ?? "-"],
        ["无日K", screen.no_data ?? "-"],
        ["处理", screen.processed ?? "-"]
      ]) + table);
    }

    function tradePlanSummary(result) {
      const plan = result.trade_plan || {};
      const candidate = result.candidate || {};
      const conditionItems = (plan.buy_conditions || []).slice(0, 4).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
      const avoidItems = (plan.avoid_conditions || []).slice(0, 4).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
      const details = plan.entry_timing ? `<div class="summary-item"><strong>买入时点</strong>${escapeHtml(plan.entry_timing)}</div>` : "";
      const lists = `<div class="summary-item"><strong>买入条件</strong><ul>${conditionItems || "<li>-</li>"}</ul></div><div class="summary-item"><strong>不买条件</strong><ul>${avoidItems || "<li>-</li>"}</ul></div>`;
      return card("买卖计划", grid([
        ["状态", result.status || "-"],
        ["周期", plan.horizon_name || result.horizon || "-"],
        ["策略", result.strategy_id || candidate.strategy || "-"],
        ["参考买入", formatPrice(plan.reference_entry_price)],
        ["止损", formatPrice(plan.stop_loss)],
        ["止盈", formatPrice(plan.take_profit)]
      ]) + details + lists);
    }

    function analysisSummary(result) {
      const candidate = result.candidate;
      const signal = result.signal;
      const backtest = result.summary || result.backtest || {};
      const items = [
        ["候选", candidate ? "命中" : "未命中"],
        ["策略", candidate ? candidate.strategy : "-"],
        ["分数", candidate ? candidate.score : "-"],
        ["信号", signal ? signal.direction : "-"],
        ["收益", formatPct(backtest.total_return)],
        ["交易数", backtest.trade_count ?? "-"]
      ];
      return card("单股分析", grid(items));
    }

    function refreshSummary(refresh) {
      const dates = (refresh.missing_trade_dates || []).slice(0, 8).join(", ");
      return card("日K缺口", grid([
        ["缓存最新", refresh.cached_end || "-"],
        ["可补到", refresh.latest_available_date || refresh.requested_end || "-"],
        ["缺失天数", refresh.missing_trade_days ?? "-"],
        ["已处理", refresh.processed ?? "-"],
        ["写入行数", refresh.rows_written ?? "-"],
        ["dry-run", String(refresh.dry_run)]
      ]) + `<div class="summary-item"><strong>缺失日期</strong>${escapeHtml(dates || "-")}</div>`);
    }

    function strategySummary(strategies) {
      const rows = strategies.map((item) => `<tr><td>${escapeHtml(item.id)}</td><td>${escapeHtml(item.name)}</td><td>${escapeHtml(item.category)}</td></tr>`).join("");
      return card("策略列表", `<table><thead><tr><th>ID</th><th>名称</th><th>分类</th></tr></thead><tbody>${rows}</tbody></table>`);
    }

    function grid(items) {
      return `<div class="summary-grid">${items.map(([label, value]) => `<div class="summary-item"><strong>${escapeHtml(value)}</strong>${escapeHtml(label)}</div>`).join("")}</div>`;
    }

    function card(title, body) {
      return `<div class="summary-card"><h3>${escapeHtml(title)}</h3>${body}</div>`;
    }

    function errorCard(message) {
      return card("错误", `<div class="summary-item"><strong>失败</strong>${escapeHtml(message)}</div>`);
    }

    function formatPct(value) {
      if (typeof value !== "number") return "-";
      return (value * 100).toFixed(2) + "%";
    }

    function formatPrice(value) {
      if (typeof value !== "number") return "-";
      return value.toFixed(4);
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    fetch("/api/health")
      .then((response) => response.json())
      .then((payload) => {
        health.textContent = payload.ok ? "已连接" : "未连接";
      })
      .catch(() => {
        health.textContent = "未连接";
      });
  </script>
</body>
</html>
"""
