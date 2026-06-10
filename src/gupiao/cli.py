"""Command-line entry points for project tasks."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from gupiao.backtest import BacktestConfig, run_breakout_backtest
from gupiao.data import (
    AkshareProvider,
    AuctionMinuteBar,
    DailyBar,
    LocalAuctionCacheImportConfig,
    LocalDailyCacheImportConfig,
    SQLiteStore,
    import_local_auction_cache,
    import_local_daily_cache,
)
from gupiao.reports import build_markdown_report, write_markdown_report
from gupiao.research import AuctionStrategyComparisonConfig, run_auction_strategy_comparison
from gupiao.scan import DEFAULT_SCAN_END, DEFAULT_SCAN_START, MarketScanConfig, run_market_scan
from gupiao.signals import build_breakout_signal
from gupiao.strategies import MovingAverageVolumeBreakoutStrategy


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

    screen_parser = subparsers.add_parser("screen", help="Run stock screening tasks.")
    screen_subparsers = screen_parser.add_subparsers(dest="screen_command", required=True)
    screen_breakout = screen_subparsers.add_parser("breakout")
    add_bars_args(screen_breakout)
    add_strategy_args(screen_breakout)
    screen_breakout.set_defaults(handler=handle_screen_breakout)

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

    report_parser = subparsers.add_parser("report", help="Generate research reports.")
    report_subparsers = report_parser.add_subparsers(dest="report_command", required=True)
    report_breakout = report_subparsers.add_parser("breakout")
    add_bars_args(report_breakout)
    add_strategy_args(report_breakout)
    add_backtest_args(report_breakout)
    report_breakout.add_argument("--title", default="MVP 策略报告")
    report_breakout.add_argument("--output", required=True)
    report_breakout.set_defaults(handler=handle_report_breakout)

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


def handle_screen_breakout(args: argparse.Namespace) -> None:
    bars = read_daily_bars_jsonl(args.bars)
    candidate = strategy_from_args(args).evaluate(args.symbol, bars)
    write_json_object({"candidate": candidate})


def handle_signal_breakout(args: argparse.Namespace) -> None:
    bars = read_daily_bars_jsonl(args.bars)
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
    bars = read_daily_bars_jsonl(args.bars)
    result = run_breakout_backtest(
        args.symbol,
        bars,
        strategy=strategy_from_args(args),
        config=backtest_config_from_args(args),
    )
    write_json_object({"backtest": result})


def handle_report_breakout(args: argparse.Namespace) -> None:
    bars = read_daily_bars_jsonl(args.bars)
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


def add_strategy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--short-window", type=positive_int, default=5)
    parser.add_argument("--medium-window", type=positive_int, default=20)
    parser.add_argument("--long-window", type=positive_int, default=60)
    parser.add_argument("--volume-window", type=positive_int, default=20)
    parser.add_argument("--breakout-window", type=positive_int, default=20)
    parser.add_argument("--min-volume-ratio", type=float, default=1.5)
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
) -> MovingAverageVolumeBreakoutStrategy:
    min_auction_score = args.min_auction_score if use_auction_filters else None
    auction_score_weight = args.auction_score_weight if use_auction_filters else 0.0
    return MovingAverageVolumeBreakoutStrategy(
        short_window=args.short_window,
        medium_window=args.medium_window,
        long_window=args.long_window,
        volume_window=args.volume_window,
        breakout_window=args.breakout_window,
        min_volume_ratio=args.min_volume_ratio,
        min_auction_score=min_auction_score,
        auction_score_weight=auction_score_weight,
    )


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
        return to_jsonable(asdict(value))
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
