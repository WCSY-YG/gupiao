"""Command-line entry points for project tasks."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from gupiao.backtest import BacktestConfig, run_breakout_backtest, run_morning_plan_backtest
from gupiao.data import (
    AkshareProvider,
    AuctionMonitorConfig,
    AuctionMinuteBar,
    DailyBar,
    LocalAuctionCacheImportConfig,
    LocalDailyCacheImportConfig,
    MarketCacheRefreshConfig,
    SQLiteStore,
    import_local_auction_cache,
    import_local_daily_cache,
    monitor_live_auction,
    refresh_market_daily_cache,
)
from gupiao.reports import build_markdown_report, write_markdown_report
from gupiao.research import (
    AuctionRollingValidationConfig,
    AuctionStrategyComparisonConfig,
    run_auction_rolling_validation,
    run_auction_strategy_comparison,
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
from gupiao.trade_plan import HORIZONS, SHORT_TERM
from gupiao.web import build_dashboard_html, serve_app, write_dashboard_html


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gupiao")
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show package version and exit.",
    )
    subparsers = parser.add_subparsers(dest="command")

    data_parser = subparsers.add_parser("data", help="Fetch market data samples.")
    data_subparsers = data_parser.add_subparsers(dest="data_command", required=True)

    instruments_parser = data_subparsers.add_parser(
        "instruments",
        help="List A-share instruments from AKShare.",
    )
    instruments_parser.add_argument("--limit", type=positive_int, default=None)
    instruments_parser.set_defaults(handler=handle_data_instruments)

    daily_parser = data_subparsers.add_parser(
        "daily",
        help="Fetch daily bars for one A-share symbol from AKShare.",
    )
    daily_parser.add_argument("symbol")
    daily_parser.add_argument("--start", required=True, type=parse_cli_date)
    daily_parser.add_argument("--end", required=True, type=parse_cli_date)
    daily_parser.add_argument("--adjust", choices=["raw", "qfq", "hfq"], default="hfq")
    daily_parser.add_argument("--limit", type=positive_int, default=None)
    daily_parser.set_defaults(handler=handle_data_daily)

    pre_market_parser = data_subparsers.add_parser(
        "pre-market",
        help="Fetch latest available pre-market call-auction minute bars from AKShare.",
    )
    pre_market_parser.add_argument("symbol")
    pre_market_parser.add_argument("--start-time", default="09:15:00")
    pre_market_parser.add_argument("--end-time", default="09:25:00")
    pre_market_parser.add_argument("--limit", type=positive_int, default=None)
    pre_market_parser.set_defaults(handler=handle_data_pre_market)

    monitor_auction_parser = data_subparsers.add_parser(
        "monitor-auction",
        help="Fetch live call-auction data, write auction and previous-day context into SQLite.",
    )
    monitor_auction_parser.add_argument("--db", default="data/cache/market_scan.sqlite")
    monitor_auction_parser.add_argument("--trade-date", type=parse_cli_date, default=None)
    monitor_auction_parser.add_argument("--auction-provider", default="akshare_live")
    monitor_auction_parser.add_argument(
        "--daily-adjust",
        choices=["raw", "qfq", "hfq"],
        default="raw",
    )
    monitor_auction_parser.add_argument("--start-time", default="09:15:00")
    monitor_auction_parser.add_argument("--end-time", default="09:25:00")
    monitor_auction_parser.add_argument("--average-volume-window", type=positive_int, default=20)
    monitor_auction_parser.add_argument("--daily-lookback-days", type=positive_int, default=45)
    monitor_auction_parser.add_argument("--limit", type=positive_int, default=None)
    monitor_auction_parser.add_argument("--symbol", action="append", default=[])
    monitor_auction_parser.add_argument("--retries", type=positive_int, default=3)
    monitor_auction_parser.add_argument("--retry-sleep", type=non_negative_float, default=1.0)
    monitor_auction_parser.add_argument("--request-sleep", type=non_negative_float, default=0.0)
    monitor_auction_parser.add_argument("--detail-limit", type=positive_int, default=20)
    monitor_auction_parser.add_argument(
        "--no-cache-daily-bars",
        action="store_false",
        dest="cache_daily_bars",
        help="Do not write the previous-day daily context fetched for scoring.",
    )
    monitor_auction_parser.add_argument(
        "--no-cache-auction-minutes",
        action="store_false",
        dest="cache_auction_minutes",
        help="Only write auction profiles, not raw auction minute rows.",
    )
    monitor_auction_parser.set_defaults(
        handler=handle_data_monitor_auction,
        cache_daily_bars=True,
        cache_auction_minutes=True,
    )

    update_daily_parser = data_subparsers.add_parser(
        "update-daily",
        help="Fetch daily bars from AKShare and store them in SQLite.",
    )
    update_daily_parser.add_argument("symbol")
    update_daily_parser.add_argument("--start", required=True, type=parse_cli_date)
    update_daily_parser.add_argument("--end", required=True, type=parse_cli_date)
    update_daily_parser.add_argument("--adjust", choices=["raw", "qfq", "hfq"], default="hfq")
    update_daily_parser.add_argument("--db", default="data/gupiao.sqlite")
    update_daily_parser.set_defaults(handler=handle_data_update_daily)

    import_daily_cache = data_subparsers.add_parser(
        "import-daily-cache",
        help="Import local market_YYYY-MM-DD.csv daily K-line cache into SQLite.",
    )
    import_daily_cache.add_argument("--source", default="cache/daily_k/market_data_cache")
    import_daily_cache.add_argument("--db", default="data/cache/market_scan.sqlite")
    import_daily_cache.add_argument("--start", type=parse_cli_date, default=None)
    import_daily_cache.add_argument("--end", type=parse_cli_date, default=None)
    import_daily_cache.add_argument("--adjust", default="hfq")
    import_daily_cache.add_argument("--provider", default="local_daily_k")
    import_daily_cache.add_argument("--conflict", choices=["ignore", "replace"], default="ignore")
    import_daily_cache.add_argument("--limit-files", type=positive_int, default=None)
    import_daily_cache.add_argument("--dry-run", action="store_true")
    import_daily_cache.set_defaults(handler=handle_data_import_daily_cache)

    import_auction_cache = data_subparsers.add_parser(
        "import-auction-cache",
        help="Import local cache/jingjia RAR call-auction snapshots into SQLite profiles.",
    )
    import_auction_cache.add_argument("--source", default="cache/jingjia")
    import_auction_cache.add_argument("--db", default="data/cache/market_scan.sqlite")
    import_auction_cache.add_argument("--start", type=parse_cli_date, default=None)
    import_auction_cache.add_argument("--end", type=parse_cli_date, default=None)
    import_auction_cache.add_argument("--provider", default="local_jingjia")
    import_auction_cache.add_argument("--start-time", default="09:15:00")
    import_auction_cache.add_argument("--end-time", default="09:25:03")
    import_auction_cache.add_argument("--conflict", choices=["ignore", "replace"], default="ignore")
    import_auction_cache.add_argument("--limit-archives", type=positive_int, default=None)
    import_auction_cache.add_argument("--limit-files", type=positive_int, default=None)
    import_auction_cache.add_argument("--dry-run", action="store_true")
    import_auction_cache.set_defaults(handler=handle_data_import_auction_cache)

    data_status = data_subparsers.add_parser(
        "status",
        help="Summarize local SQLite cache coverage.",
    )
    data_status.add_argument("--db", default="data/cache/market_scan.sqlite")
    data_status.set_defaults(handler=handle_data_status)

    refresh_market_cache = data_subparsers.add_parser(
        "refresh-market-cache",
        help="Detect missing market daily dates and fetch them into SQLite.",
    )
    refresh_market_cache.add_argument("--db", default="data/cache/market_scan.sqlite")
    refresh_market_cache.add_argument("--adjust", choices=["raw", "qfq", "hfq"], default="hfq")
    refresh_market_cache.add_argument("--start", type=parse_cli_date, default=None)
    refresh_market_cache.add_argument("--end", type=parse_cli_date, default=None)
    refresh_market_cache.add_argument("--probe-symbol", default="000001")
    refresh_market_cache.add_argument("--limit", type=positive_int, default=None)
    refresh_market_cache.add_argument("--symbol", action="append", default=[])
    refresh_market_cache.add_argument("--retries", type=positive_int, default=3)
    refresh_market_cache.add_argument("--retry-sleep", type=non_negative_float, default=1.0)
    refresh_market_cache.add_argument("--request-sleep", type=non_negative_float, default=0.0)
    refresh_market_cache.add_argument("--dry-run", action="store_true")
    refresh_market_cache.set_defaults(handler=handle_data_refresh_market_cache)

    screen_parser = subparsers.add_parser("screen", help="Run stock screening tasks.")
    screen_subparsers = screen_parser.add_subparsers(dest="screen_command", required=True)
    screen_list = screen_subparsers.add_parser("list", help="List available screen strategies.")
    screen_list.set_defaults(handler=handle_screen_list)

    screen_run = screen_subparsers.add_parser(
        "run",
        help="Run one strategy for one symbol from JSONL or SQLite cache.",
    )
    add_screen_source_args(screen_run)
    add_strategy_args(screen_run)
    screen_run.set_defaults(handler=handle_screen_run)

    screen_candidates = screen_subparsers.add_parser(
        "candidates",
        help="Rank candidates from local SQLite cache without fetching remote data.",
    )
    screen_candidates.add_argument("--db", default="data/cache/market_scan.sqlite")
    screen_candidates.add_argument("--as-of", type=parse_cli_date, default=None)
    screen_candidates.add_argument("--end", type=parse_cli_date, default=None)
    screen_candidates.add_argument("--lookback", type=positive_int, default=180)
    screen_candidates.add_argument("--adjust", choices=["raw", "qfq", "hfq"], default="hfq")
    screen_candidates.add_argument("--top", type=positive_int, default=30)
    screen_candidates.add_argument("--limit", type=positive_int, default=None)
    screen_candidates.add_argument("--symbol", action="append", default=[])
    screen_candidates.add_argument("--auction-provider", default=None)
    add_strategy_args(screen_candidates)
    screen_candidates.set_defaults(handler=handle_screen_candidates)

    screen_morning = screen_subparsers.add_parser(
        "morning",
        help="Run morning call-auction screening from local SQLite cache.",
    )
    add_morning_screen_args(screen_morning)
    screen_morning.set_defaults(handler=handle_screen_morning)

    screen_breakout = screen_subparsers.add_parser("breakout")
    add_bars_args(screen_breakout)
    add_strategy_args(screen_breakout)
    screen_breakout.set_defaults(handler=handle_screen_breakout)

    plan_parser = subparsers.add_parser("plan", help="Build actionable trade plans.")
    plan_subparsers = plan_parser.add_subparsers(dest="plan_command", required=True)
    plan_trade = plan_subparsers.add_parser(
        "trade",
        help="Build one trade plan from morning call-auction context.",
    )
    add_trade_plan_args(plan_trade)
    plan_trade.set_defaults(handler=handle_plan_trade)

    signal_parser = subparsers.add_parser("signal", help="Generate buy/sell signals.")
    signal_subparsers = signal_parser.add_subparsers(dest="signal_command", required=True)
    signal_breakout = signal_subparsers.add_parser("breakout")
    add_bars_args(signal_breakout)
    add_strategy_args(signal_breakout)
    add_signal_args(signal_breakout)
    signal_breakout.set_defaults(handler=handle_signal_breakout)

    backtest_parser = subparsers.add_parser("backtest", help="Run backtests.")
    backtest_subparsers = backtest_parser.add_subparsers(dest="backtest_command", required=True)
    backtest_breakout = backtest_subparsers.add_parser("breakout")
    add_bars_args(backtest_breakout)
    add_strategy_args(backtest_breakout)
    add_backtest_args(backtest_breakout)
    backtest_breakout.set_defaults(handler=handle_backtest_breakout)
    backtest_morning = backtest_subparsers.add_parser(
        "morning",
        help="Backtest morning call-auction decisions with trade-date open entries.",
    )
    add_morning_backtest_args(backtest_morning)
    backtest_morning.set_defaults(handler=handle_backtest_morning)

    report_parser = subparsers.add_parser("report", help="Generate research reports.")
    report_subparsers = report_parser.add_subparsers(dest="report_command", required=True)
    report_breakout = report_subparsers.add_parser("breakout")
    add_bars_args(report_breakout)
    add_strategy_args(report_breakout)
    add_backtest_args(report_breakout)
    report_breakout.add_argument("--title", default="MVP 策略报告")
    report_breakout.add_argument("--output", required=True)
    report_breakout.set_defaults(handler=handle_report_breakout)

    web_parser = subparsers.add_parser("web", help="Generate browser-ready web pages.")
    web_subparsers = web_parser.add_subparsers(dest="web_command", required=True)
    web_dashboard = web_subparsers.add_parser(
        "dashboard",
        help="Generate a standalone HTML research dashboard.",
    )
    add_bars_args(web_dashboard)
    add_strategy_args(web_dashboard)
    add_backtest_args(web_dashboard)
    web_dashboard.add_argument("--title", default="A 股策略研究 Dashboard")
    web_dashboard.add_argument("--output", required=True)
    web_dashboard.set_defaults(handler=handle_web_dashboard)

    web_serve = web_subparsers.add_parser(
        "serve",
        help="Run the interactive local web app.",
    )
    web_serve.add_argument("--host", default="127.0.0.1")
    web_serve.add_argument("--port", type=positive_int, default=8765)
    web_serve.set_defaults(handler=handle_web_serve)

    research_parser = subparsers.add_parser("research", help="Run research experiments.")
    research_subparsers = research_parser.add_subparsers(dest="research_command", required=True)
    auction_compare = research_subparsers.add_parser(
        "auction-compare",
        help="Compare baseline and auction-enhanced breakout backtests from SQLite cache.",
    )
    auction_compare.add_argument("--start", required=True, type=parse_cli_date)
    auction_compare.add_argument("--end", required=True, type=parse_cli_date)
    auction_compare.add_argument("--adjust", choices=["raw", "qfq", "hfq"], default="hfq")
    auction_compare.add_argument("--db", default="data/cache/market_scan.sqlite")
    auction_compare.add_argument("--output", default="reports/generated/auction_validation/latest")
    auction_compare.add_argument(
        "--public-summary",
        default="reports/summaries/latest_auction_validation.md",
    )
    auction_compare.add_argument("--auction-provider", default="local_jingjia")
    auction_compare.add_argument("--top", type=positive_int, default=30)
    auction_compare.add_argument("--limit", type=positive_int, default=None)
    add_strategy_args(auction_compare)
    add_backtest_args(auction_compare)
    auction_compare.set_defaults(handler=handle_research_auction_compare)

    auction_rolling = research_subparsers.add_parser(
        "auction-rolling",
        help="Run monthly rolling validation for auction score thresholds and weights.",
    )
    auction_rolling.add_argument("--start", required=True, type=parse_cli_date)
    auction_rolling.add_argument("--end", required=True, type=parse_cli_date)
    auction_rolling.add_argument("--adjust", choices=["raw", "qfq", "hfq"], default="hfq")
    auction_rolling.add_argument("--db", default="data/cache/market_scan.sqlite")
    auction_rolling.add_argument("--output", default="reports/generated/auction_rolling/latest")
    auction_rolling.add_argument(
        "--public-summary",
        default="reports/summaries/latest_auction_rolling.md",
    )
    auction_rolling.add_argument("--auction-provider", default="local_jingjia")
    auction_rolling.add_argument("--top", type=positive_int, default=30)
    auction_rolling.add_argument("--limit", type=positive_int, default=None)
    auction_rolling.add_argument(
        "--min-auction-scores",
        default="none,50,60,70",
        help="Comma-separated thresholds; use none for soft ranking without a hard gate.",
    )
    auction_rolling.add_argument(
        "--auction-score-weights",
        default="0,0.10,0.15,0.25",
        help="Comma-separated auction score weights between 0 and 1.",
    )
    auction_rolling.add_argument("--window-months", type=positive_int, default=1)
    add_strategy_args(auction_rolling, include_auction_params=False)
    add_backtest_args(auction_rolling)
    auction_rolling.set_defaults(handler=handle_research_auction_rolling)

    scan_parser = subparsers.add_parser("scan", help="Run market-wide automation tasks.")
    scan_subparsers = scan_parser.add_subparsers(dest="scan_command", required=True)
    scan_market = scan_subparsers.add_parser(
        "market",
        help="Fetch A-share daily bars and run a recoverable market scan.",
    )
    scan_market.add_argument("--start", type=parse_cli_date, default=DEFAULT_SCAN_START)
    scan_market.add_argument("--end", type=parse_cli_date, default=DEFAULT_SCAN_END)
    scan_market.add_argument("--adjust", choices=["raw", "qfq", "hfq"], default="hfq")
    scan_market.add_argument("--db", default="data/cache/market_scan.sqlite")
    scan_market.add_argument("--output", default="reports/generated/market_scan/latest")
    scan_market.add_argument("--public-summary", default="reports/summaries/latest_market_scan.md")
    scan_market.add_argument("--top", type=positive_int, default=30)
    scan_market.add_argument("--limit", type=positive_int, default=None)
    scan_market.add_argument("--retries", type=positive_int, default=3)
    scan_market.add_argument("--retry-sleep", type=non_negative_float, default=1.0)
    scan_market.add_argument("--request-sleep", type=non_negative_float, default=0.0)
    scan_market.add_argument("--request-timeout", type=positive_float, default=60.0)
    scan_market.add_argument(
        "--auction-provider",
        default=None,
        help="Use stored auction profiles from this provider, for example local_jingjia.",
    )
    add_strategy_args(scan_market)
    add_backtest_args(scan_market)
    scan_market.set_defaults(handler=handle_scan_market)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        from gupiao import __version__

        print(__version__)

    handler = getattr(args, "handler", None)
    if handler is not None:
        handler(args)

    return 0


def handle_data_instruments(args: argparse.Namespace) -> None:
    provider = AkshareProvider()
    write_json_lines(provider.list_instruments(), limit=args.limit)


def handle_data_daily(args: argparse.Namespace) -> None:
    provider = AkshareProvider()
    write_json_lines(
        provider.fetch_daily_bars(
            args.symbol,
            args.start,
            args.end,
            adjust=args.adjust,
        ),
        limit=args.limit,
    )


def handle_data_pre_market(args: argparse.Namespace) -> None:
    provider = AkshareProvider()
    write_json_lines(
        provider.fetch_pre_market_minutes(
            args.symbol,
            start_time=args.start_time,
            end_time=args.end_time,
        ),
        limit=args.limit,
    )


def handle_data_monitor_auction(args: argparse.Namespace) -> None:
    result = monitor_live_auction(
        AkshareProvider(),
        config=AuctionMonitorConfig(
            db_path=args.db,
            trade_date=args.trade_date,
            auction_provider=args.auction_provider,
            daily_adjust=args.daily_adjust,
            start_time=args.start_time,
            end_time=args.end_time,
            average_volume_window=args.average_volume_window,
            daily_lookback_days=args.daily_lookback_days,
            limit=args.limit,
            symbols=tuple(args.symbol),
            retries=args.retries,
            retry_sleep_seconds=args.retry_sleep,
            request_sleep_seconds=args.request_sleep,
            cache_daily_bars=args.cache_daily_bars,
            cache_auction_minutes=args.cache_auction_minutes,
        ),
    )
    write_json_object({"auction_monitor": auction_monitor_summary(result, args.detail_limit)})


def handle_data_update_daily(args: argparse.Namespace) -> None:
    provider = AkshareProvider()
    bars = list(
        provider.fetch_daily_bars(
            args.symbol,
            args.start,
            args.end,
            adjust=args.adjust,
        )
    )
    store = SQLiteStore(args.db)
    rows = store.upsert_daily_bars(bars)
    write_json_object({"db": args.db, "rows": rows, "symbol": args.symbol})


def handle_data_import_daily_cache(args: argparse.Namespace) -> None:
    result = import_local_daily_cache(
        LocalDailyCacheImportConfig(
            source_dir=args.source,
            db_path=args.db,
            start=args.start,
            end=args.end,
            adjust=args.adjust,
            provider=args.provider,
            conflict=args.conflict,
            limit_files=args.limit_files,
            dry_run=args.dry_run,
        )
    )
    write_json_object(result)


def handle_data_import_auction_cache(args: argparse.Namespace) -> None:
    result = import_local_auction_cache(
        LocalAuctionCacheImportConfig(
            source_dir=args.source,
            db_path=args.db,
            start=args.start,
            end=args.end,
            provider=args.provider,
            start_time=args.start_time,
            end_time=args.end_time,
            conflict=args.conflict,
            limit_archives=args.limit_archives,
            limit_files=args.limit_files,
            dry_run=args.dry_run,
        )
    )
    write_json_object(result)


def handle_data_status(args: argparse.Namespace) -> None:
    write_json_object(SQLiteStore(args.db).data_status())


def handle_data_refresh_market_cache(args: argparse.Namespace) -> None:
    result = refresh_market_daily_cache(
        AkshareProvider(),
        config=MarketCacheRefreshConfig(
            db_path=args.db,
            adjust=args.adjust,
            start=args.start,
            end=args.end,
            probe_symbol=args.probe_symbol,
            limit=args.limit,
            symbols=tuple(args.symbol),
            retries=args.retries,
            retry_sleep_seconds=args.retry_sleep,
            request_sleep_seconds=args.request_sleep,
            dry_run=args.dry_run,
        ),
    )
    write_json_object({"refresh": result})


def handle_screen_list(args: argparse.Namespace) -> None:
    del args
    write_json_lines(available_strategy_specs())


def handle_screen_run(args: argparse.Namespace) -> None:
    bars = load_screen_bars(args)
    auction_profile = load_latest_auction_profile(args, bars)
    candidate = strategy_from_args(args).evaluate(
        args.symbol,
        bars,
        auction_profile=auction_profile,
    )
    write_json_object(
        {
            "symbol": args.symbol,
            "strategy": args.strategy,
            "as_of": effective_end(args),
            "bar_count": len(bars),
            "candidate": candidate,
            "auction_profile": auction_profile,
        }
    )


def handle_screen_candidates(args: argparse.Namespace) -> None:
    as_of = effective_end(args)
    result = run_cached_candidate_screen(
        config=CandidateScreenConfig(
            db_path=args.db,
            as_of=as_of,
            adjust=args.adjust,
            lookback=args.lookback,
            top=args.top,
            limit=args.limit,
            auction_provider=args.auction_provider,
            symbols=tuple(args.symbol),
        ),
        strategy=strategy_from_args(args),
    )
    write_json_object({"screen": result})


def handle_screen_morning(args: argparse.Namespace) -> None:
    result = run_morning_screen(
        config=MorningScreenConfig(
            db_path=args.db,
            trade_date=args.trade_date,
            horizon=args.horizon,
            strategy_id=args.strategy,
            adjust=args.adjust,
            lookback=args.lookback,
            top=args.top,
            limit=args.limit,
            auction_provider=args.auction_provider,
            symbols=tuple(args.symbol),
        ),
        strategy=morning_strategy_from_args(args),
    )
    write_json_object({"morning_screen": result})


def handle_plan_trade(args: argparse.Namespace) -> None:
    result = run_morning_screen(
        config=MorningScreenConfig(
            db_path=args.db,
            trade_date=args.trade_date,
            horizon=args.horizon,
            strategy_id=args.strategy,
            adjust=args.adjust,
            lookback=args.lookback,
            top=1,
            limit=1,
            auction_provider=args.auction_provider,
            symbols=(args.symbol,),
        ),
        strategy=morning_strategy_from_args(args),
    )
    row = result.results[0] if result.results else None
    write_json_object(
        {
            "symbol": args.symbol,
            "trade_date": args.trade_date,
            "horizon": args.horizon,
            "strategy_id": result.strategy_id,
            "status": row.status if row is not None else "not_found",
            "candidate": row.candidate if row is not None else None,
            "trade_plan": row.trade_plan if row is not None else None,
            "auction_profile": row.auction_profile if row is not None else None,
            "latest_daily_date": row.latest_daily_date if row is not None else None,
            "error": row.error if row is not None else None,
        }
    )


def handle_screen_breakout(args: argparse.Namespace) -> None:
    bars = load_jsonl_bars_for_args(args)
    candidate = strategy_from_args(args).evaluate(args.symbol, bars)
    write_json_object({"candidate": candidate})


def handle_signal_breakout(args: argparse.Namespace) -> None:
    bars = load_jsonl_bars_for_args(args)
    strategy = strategy_from_args(args)
    candidate = strategy.evaluate(args.symbol, bars)
    signal = None
    if candidate is not None:
        signal = build_breakout_signal(
            candidate,
            bars,
            atr_window=args.atr_window,
            stop_atr_multiple=args.stop_atr_multiple,
            take_profit_r_multiple=args.take_profit_r_multiple,
        )
    write_json_object({"candidate": candidate, "signal": signal})


def handle_backtest_breakout(args: argparse.Namespace) -> None:
    bars = load_jsonl_bars_for_args(args)
    result = run_breakout_backtest(
        args.symbol,
        bars,
        strategy=strategy_from_args(args),
        config=backtest_config_from_args(args),
    )
    write_json_object({"backtest": result})


def handle_backtest_morning(args: argparse.Namespace) -> None:
    bars = SQLiteStore(args.db).get_daily_bars(
        args.symbol,
        start=args.start,
        end=args.end,
        adjust=args.adjust,
    )
    auction_profiles = load_auction_profile_map(
        db_path=args.db,
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        provider=args.auction_provider,
    )
    result = run_morning_plan_backtest(
        args.symbol,
        bars,
        horizon=args.horizon,
        strategy=morning_strategy_from_args(args),
        config=backtest_config_from_args(args),
        auction_profiles=auction_profiles,
    )
    write_json_object({"backtest": result})


def handle_report_breakout(args: argparse.Namespace) -> None:
    bars = load_jsonl_bars_for_args(args)
    strategy = strategy_from_args(args)
    candidate = strategy.evaluate(args.symbol, bars)
    signal = None
    if candidate is not None:
        signal = build_breakout_signal(
            candidate,
            bars,
            atr_window=args.atr_window,
            stop_atr_multiple=args.stop_atr_multiple,
            take_profit_r_multiple=args.take_profit_r_multiple,
        )
    backtest = run_breakout_backtest(
        args.symbol,
        bars,
        strategy=strategy,
        config=backtest_config_from_args(args),
    )
    content = build_markdown_report(
        title=args.title,
        candidate=candidate,
        signal=signal,
        backtest=backtest,
    )
    path = write_markdown_report(args.output, content)
    write_json_object({"path": str(path), "symbol": args.symbol})


def handle_web_dashboard(args: argparse.Namespace) -> None:
    bars = load_jsonl_bars_for_args(args)
    strategy = strategy_from_args(args)
    backtest_config = backtest_config_from_args(args)
    candidate = strategy.evaluate(args.symbol, bars)
    signal = None
    if candidate is not None:
        signal = build_breakout_signal(
            candidate,
            bars,
            atr_window=args.atr_window,
            stop_atr_multiple=args.stop_atr_multiple,
            take_profit_r_multiple=args.take_profit_r_multiple,
        )
    backtest = run_breakout_backtest(
        args.symbol,
        bars,
        strategy=strategy,
        config=backtest_config,
    )
    commands = dashboard_commands(args)
    content = build_dashboard_html(
        title=args.title,
        candidate=candidate,
        signal=signal,
        backtest=backtest,
        bars=bars,
        strategy=strategy,
        backtest_config=backtest_config,
        source_path=args.bars,
        commands=commands,
    )
    path = write_dashboard_html(args.output, content)
    write_json_object({"path": str(path), "symbol": args.symbol})


def handle_web_serve(args: argparse.Namespace) -> None:
    serve_app(host=args.host, port=args.port, workspace=Path.cwd())


def handle_research_auction_compare(args: argparse.Namespace) -> None:
    baseline_strategy = strategy_from_args(args, use_auction_filters=False)
    min_auction_score = 60.0 if args.min_auction_score is None else args.min_auction_score
    args.min_auction_score = min_auction_score
    auction_strategy = strategy_from_args(args, use_auction_filters=True)
    config = AuctionStrategyComparisonConfig(
        start=args.start,
        end=args.end,
        adjust=args.adjust,
        db_path=args.db,
        output_dir=args.output,
        public_summary_path=args.public_summary,
        auction_provider=args.auction_provider,
        top=args.top,
        limit=args.limit,
        min_auction_score=min_auction_score,
        auction_score_weight=args.auction_score_weight,
    )
    result = run_auction_strategy_comparison(
        config=config,
        baseline_strategy=baseline_strategy,
        auction_strategy=auction_strategy,
        backtest_config=backtest_config_from_args(args),
    )
    write_json_object(
        {
            "public_summary": result.public_summary_path,
            "result_path": result.result_path,
            "failure_path": result.failure_path,
            "processed": result.processed,
            "succeeded": result.succeeded,
            "failed": result.failed,
            "no_data": result.no_data,
            "improved": result.improved,
            "worsened": result.worsened,
        }
    )


def handle_research_auction_rolling(args: argparse.Namespace) -> None:
    baseline_strategy = strategy_from_args(args, use_auction_filters=False)

    def auction_strategy_factory(
        min_auction_score: float | None,
        auction_score_weight: float,
    ) -> ScreeningStrategy:
        variant_args = argparse.Namespace(**vars(args))
        variant_args.min_auction_score = min_auction_score
        variant_args.auction_score_weight = auction_score_weight
        return strategy_from_args(variant_args, use_auction_filters=True)

    config = AuctionRollingValidationConfig(
        start=args.start,
        end=args.end,
        adjust=args.adjust,
        db_path=args.db,
        output_dir=args.output,
        public_summary_path=args.public_summary,
        auction_provider=args.auction_provider,
        top=args.top,
        limit=args.limit,
        min_auction_scores=parse_optional_float_csv(args.min_auction_scores),
        auction_score_weights=parse_float_csv(args.auction_score_weights),
        window_months=args.window_months,
    )
    result = run_auction_rolling_validation(
        config=config,
        baseline_strategy=baseline_strategy,
        auction_strategy_factory=auction_strategy_factory,
        backtest_config=backtest_config_from_args(args),
    )
    write_json_object(
        {
            "public_summary": result.public_summary_path,
            "output_dir": result.output_dir,
            "window_count": len(result.windows),
            "evaluation_count": len(result.evaluations),
        }
    )


def handle_scan_market(args: argparse.Namespace) -> None:
    config = MarketScanConfig(
        start=args.start,
        end=args.end,
        adjust=args.adjust,
        db_path=args.db,
        output_dir=args.output,
        public_summary_path=args.public_summary,
        top=args.top,
        limit=args.limit,
        retries=args.retries,
        retry_sleep_seconds=args.retry_sleep,
        request_sleep_seconds=args.request_sleep,
        request_timeout_seconds=args.request_timeout,
        auction_provider=args.auction_provider,
    )
    result = run_market_scan(
        AkshareProvider(),
        config=config,
        strategy=strategy_from_args(args),
        backtest_config=backtest_config_from_args(args),
    )
    write_json_object(
        {
            "public_summary": result.public_summary_path,
            "result_path": result.result_path,
            "failure_path": result.failure_path,
            "processed": result.processed,
            "succeeded": result.succeeded,
            "failed": result.failed,
            "no_data": result.no_data,
            "candidate_count": result.candidate_count,
        }
    )


def add_bars_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--bars", required=True, help="Path to daily bars JSONL.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--as-of", type=parse_cli_date, default=None)


def add_screen_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--bars", default=None, help="Path to daily bars JSONL.")
    parser.add_argument("--db", default=None, help="SQLite cache path.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", type=parse_cli_date, default=None)
    parser.add_argument("--end", type=parse_cli_date, default=None)
    parser.add_argument("--as-of", type=parse_cli_date, default=None)
    parser.add_argument("--lookback", type=positive_int, default=180)
    parser.add_argument("--adjust", choices=["raw", "qfq", "hfq"], default="hfq")
    parser.add_argument("--auction-provider", default=None)
    parser.add_argument("--auction-db", default=None)


def add_morning_screen_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", default="data/cache/market_scan.sqlite")
    parser.add_argument("--trade-date", required=True, type=parse_cli_date)
    parser.add_argument("--horizon", choices=HORIZONS, default=SHORT_TERM)
    parser.add_argument("--adjust", choices=["raw", "qfq", "hfq"], default="hfq")
    parser.add_argument("--lookback", type=positive_int, default=180)
    parser.add_argument("--top", type=positive_int, default=20)
    parser.add_argument("--limit", type=positive_int, default=500)
    parser.add_argument("--symbol", action="append", default=[])
    parser.add_argument("--auction-provider", default="local_jingjia")
    add_strategy_args(parser, default=None)


def add_trade_plan_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--db", default="data/cache/market_scan.sqlite")
    parser.add_argument("--trade-date", required=True, type=parse_cli_date)
    parser.add_argument("--horizon", choices=HORIZONS, default=SHORT_TERM)
    parser.add_argument("--adjust", choices=["raw", "qfq", "hfq"], default="hfq")
    parser.add_argument("--lookback", type=positive_int, default=180)
    parser.add_argument("--auction-provider", default="local_jingjia")
    add_strategy_args(parser, default=None)


def add_morning_backtest_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--db", default="data/cache/market_scan.sqlite")
    parser.add_argument("--start", required=True, type=parse_cli_date)
    parser.add_argument("--end", required=True, type=parse_cli_date)
    parser.add_argument("--horizon", choices=HORIZONS, default=SHORT_TERM)
    parser.add_argument("--adjust", choices=["raw", "qfq", "hfq"], default="hfq")
    parser.add_argument("--auction-provider", default="local_jingjia")
    add_strategy_args(parser, default=None)
    add_backtest_args(parser)


def add_strategy_args(
    parser: argparse.ArgumentParser,
    *,
    default: str | None = "ma_volume_breakout",
    include_auction_params: bool = True,
) -> None:
    parser.add_argument("--strategy", default=default)
    parser.add_argument("--short-window", type=positive_int, default=5)
    parser.add_argument("--medium-window", type=positive_int, default=20)
    parser.add_argument("--long-window", type=positive_int, default=60)
    parser.add_argument("--volume-window", type=positive_int, default=20)
    parser.add_argument("--breakout-window", type=positive_int, default=20)
    parser.add_argument("--min-volume-ratio", type=float, default=1.5)
    if include_auction_params:
        parser.add_argument("--min-auction-score", type=float, default=None)
        parser.add_argument("--auction-score-weight", type=float, default=0.15)


def add_signal_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--atr-window", type=positive_int, default=14)
    parser.add_argument("--stop-atr-multiple", type=float, default=2.0)
    parser.add_argument("--take-profit-r-multiple", type=float, default=2.0)


def add_backtest_args(parser: argparse.ArgumentParser) -> None:
    add_signal_args(parser)
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--commission-rate", type=float, default=0.0003)
    parser.add_argument("--slippage-rate", type=float, default=0.0005)
    parser.add_argument("--max-holding-bars", type=positive_int, default=20)


def strategy_from_args(
    args: argparse.Namespace,
    *,
    use_auction_filters: bool = True,
) -> ScreeningStrategy:
    min_auction_score = getattr(args, "min_auction_score", None) if use_auction_filters else None
    auction_score_weight = getattr(args, "auction_score_weight", 0.15) if use_auction_filters else 0.0
    strategy_id = getattr(args, "strategy", "ma_volume_breakout")
    if not use_auction_filters and strategy_id == "auction_assisted_breakout":
        strategy_id = "ma_volume_breakout"
    return build_screening_strategy(
        strategy_id,
        short_window=args.short_window,
        medium_window=args.medium_window,
        long_window=args.long_window,
        volume_window=args.volume_window,
        breakout_window=args.breakout_window,
        min_volume_ratio=args.min_volume_ratio,
        min_auction_score=min_auction_score,
        auction_score_weight=auction_score_weight,
    )


def morning_strategy_from_args(args: argparse.Namespace) -> ScreeningStrategy | None:
    if not getattr(args, "strategy", None):
        return None
    return strategy_from_args(args)


def load_screen_bars(args: argparse.Namespace) -> list[DailyBar]:
    if args.bars:
        return load_jsonl_bars_for_args(args)
    if args.db:
        end = effective_end(args)
        bars = SQLiteStore(args.db).get_daily_bars(
            args.symbol,
            start=args.start,
            end=end,
            adjust=args.adjust,
        )
        return bars_up_to(bars, as_of=end, lookback=args.lookback)
    raise ValueError("screen run needs --bars or --db")


def load_jsonl_bars_for_args(args: argparse.Namespace) -> list[DailyBar]:
    bars = read_daily_bars_jsonl(args.bars)
    end = effective_end(args)
    start = getattr(args, "start", None)
    filtered = [bar for bar in bars if start is None or bar.trade_date >= start]
    return bars_up_to(
        filtered,
        as_of=end,
        lookback=getattr(args, "lookback", None),
    )


def load_latest_auction_profile(
    args: argparse.Namespace,
    bars: Sequence[DailyBar],
) -> Any:
    provider = getattr(args, "auction_provider", None)
    if not provider or not bars:
        return None
    db_path = getattr(args, "auction_db", None) or getattr(args, "db", None)
    if not db_path:
        return None
    profiles = SQLiteStore(db_path).get_auction_profiles(
        args.symbol,
        start=bars[-1].trade_date,
        end=bars[-1].trade_date,
        provider=provider,
    )
    return profiles[-1] if profiles else None


def load_auction_profile_map(
    *,
    db_path: str,
    symbol: str,
    start: date | None,
    end: date | None,
    provider: str | None,
) -> dict[date, Any]:
    if not provider:
        return {}
    profiles = SQLiteStore(db_path).get_auction_profiles(
        symbol,
        start=start,
        end=end,
        provider=provider,
    )
    return {profile.trade_date: profile for profile in profiles}


def effective_end(args: argparse.Namespace) -> date | None:
    end = getattr(args, "end", None)
    as_of = getattr(args, "as_of", None)
    if end is not None and as_of is not None and end != as_of:
        raise ValueError("--end and --as-of must match when both are provided")
    return as_of or end


def backtest_config_from_args(args: argparse.Namespace) -> BacktestConfig:
    return BacktestConfig(
        initial_cash=args.initial_cash,
        commission_rate=args.commission_rate,
        slippage_rate=args.slippage_rate,
        max_holding_bars=args.max_holding_bars,
        atr_window=args.atr_window,
        stop_atr_multiple=args.stop_atr_multiple,
        take_profit_r_multiple=args.take_profit_r_multiple,
    )


def dashboard_commands(args: argparse.Namespace) -> list[str]:
    base = [
        "conda",
        "run",
        "-n",
        "agent",
        "env",
        "PYTHONPATH=src",
        "python",
        "-m",
        "gupiao.cli",
    ]
    strategy_args = [
        "--strategy",
        getattr(args, "strategy", "ma_volume_breakout"),
        "--short-window",
        str(args.short_window),
        "--medium-window",
        str(args.medium_window),
        "--long-window",
        str(args.long_window),
        "--volume-window",
        str(args.volume_window),
        "--breakout-window",
        str(args.breakout_window),
        "--min-volume-ratio",
        str(args.min_volume_ratio),
    ]
    if args.min_auction_score is not None:
        strategy_args.extend(["--min-auction-score", str(args.min_auction_score)])
    strategy_args.extend(["--auction-score-weight", str(args.auction_score_weight)])
    signal_args = [
        "--atr-window",
        str(args.atr_window),
        "--stop-atr-multiple",
        str(args.stop_atr_multiple),
        "--take-profit-r-multiple",
        str(args.take_profit_r_multiple),
    ]
    backtest_args = [
        "--initial-cash",
        str(args.initial_cash),
        "--commission-rate",
        str(args.commission_rate),
        "--slippage-rate",
        str(args.slippage_rate),
        "--max-holding-bars",
        str(args.max_holding_bars),
    ]
    common = ["--bars", args.bars, "--symbol", args.symbol]
    if getattr(args, "as_of", None) is not None:
        common.extend(["--as-of", args.as_of.isoformat()])
    return [
        shell_command([*base, "screen", "breakout", *common, *strategy_args]),
        shell_command([*base, "signal", "breakout", *common, *strategy_args, *signal_args]),
        shell_command(
            [
                *base,
                "backtest",
                "breakout",
                *common,
                *strategy_args,
                *signal_args,
                *backtest_args,
            ]
        ),
        shell_command(
            [
                *base,
                "web",
                "dashboard",
                *common,
                *strategy_args,
                *signal_args,
                *backtest_args,
                "--title",
                args.title,
                "--output",
                args.output,
            ]
        ),
    ]


def shell_command(parts: Sequence[str]) -> str:
    return " ".join(shell_quote(part) for part in parts)


def shell_quote(value: str) -> str:
    if value and all(item.isalnum() or item in "._/:=-" for item in value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def auction_monitor_summary(result: Any, detail_limit: int) -> dict[str, Any]:
    failures = [
        item
        for item in result.results
        if item.status in {"failed", "no_data", "date_mismatch"}
    ][:detail_limit]
    return {
        "db_path": result.db_path,
        "requested_trade_date": result.requested_trade_date,
        "auction_provider": result.auction_provider,
        "daily_adjust": result.daily_adjust,
        "instrument_count": result.instrument_count,
        "processed": result.processed,
        "succeeded": result.succeeded,
        "failed": result.failed,
        "no_data": result.no_data,
        "date_mismatch": result.date_mismatch,
        "daily_rows_written": result.daily_rows_written,
        "auction_minutes_written": result.auction_minutes_written,
        "auction_profiles_written": result.auction_profiles_written,
        "results_sample": result.results[:detail_limit],
        "failure_sample": failures,
    }


def write_json_lines(records: Any, *, limit: int | None = None) -> None:
    count = 0
    for record in records:
        if limit is not None and count >= limit:
            break
        print(json.dumps(to_jsonable(record), ensure_ascii=False, sort_keys=True))
        count += 1


def write_json_object(record: Any) -> None:
    print(json.dumps(to_jsonable(record), ensure_ascii=False, sort_keys=True))


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return to_jsonable(asdict(value))  # type: ignore[arg-type]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


def read_daily_bars_jsonl(path: str | Path) -> list[DailyBar]:
    bars = []
    with Path(path).open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            bars.append(daily_bar_from_mapping(json.loads(line)))
    return bars


def read_auction_minutes_jsonl(path: str | Path) -> list[AuctionMinuteBar]:
    minutes = []
    with Path(path).open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            minutes.append(auction_minute_from_mapping(json.loads(line)))
    return minutes


def daily_bar_from_mapping(row: dict[str, Any]) -> DailyBar:
    fetched_at = row.get("fetched_at")
    return DailyBar(
        symbol=str(row["symbol"]),
        trade_date=parse_cli_date(str(row["trade_date"])),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        volume=float(row["volume"]),
        amount=optional_float(row.get("amount")),
        turnover=optional_float(row.get("turnover")),
        adjust=row.get("adjust"),
        provider=row.get("provider"),
        fetched_at=datetime.fromisoformat(fetched_at) if fetched_at else None,
    )


def auction_minute_from_mapping(row: dict[str, Any]) -> AuctionMinuteBar:
    fetched_at = row.get("fetched_at")
    return AuctionMinuteBar(
        symbol=str(row["symbol"]),
        trade_time=datetime.fromisoformat(str(row["trade_time"])),
        open=float(row["open"]),
        close=float(row["close"]),
        high=float(row["high"]),
        low=float(row["low"]),
        volume=float(row["volume"]),
        amount=optional_float(row.get("amount")),
        latest_price=optional_float(row.get("latest_price")),
        provider=row.get("provider"),
        fetched_at=datetime.fromisoformat(fetched_at) if fetched_at else None,
    )


def optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def parse_optional_float_csv(value: str) -> tuple[float | None, ...]:
    parsed: list[float | None] = []
    for item in csv_tokens(value):
        lowered = item.lower()
        if lowered in {"none", "null", "soft", "off"}:
            parsed.append(None)
        else:
            parsed.append(float(item))
    if not parsed:
        raise argparse.ArgumentTypeError("expected at least one value")
    return tuple(unique_preserve_order(parsed))


def parse_float_csv(value: str) -> tuple[float, ...]:
    parsed = [float(item) for item in csv_tokens(value)]
    if not parsed:
        raise argparse.ArgumentTypeError("expected at least one value")
    return tuple(unique_preserve_order(parsed))


def csv_tokens(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def unique_preserve_order(values: Sequence[Any]) -> list[Any]:
    unique: list[Any] = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique


def parse_cli_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected date in YYYY-MM-DD format") from exc


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return parsed


def non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("expected a non-negative float")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("expected a positive float")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
