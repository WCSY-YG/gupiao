"""Command-line entry points for project tasks."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from typing import Any

from gupiao.data import AkshareProvider


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


def write_json_lines(records: Any, *, limit: int | None = None) -> None:
    count = 0
    for record in records:
        if limit is not None and count >= limit:
            break
        print(json.dumps(to_jsonable(record), ensure_ascii=False, sort_keys=True))
        count += 1


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


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


if __name__ == "__main__":
    raise SystemExit(main())
