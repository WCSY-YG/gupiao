"""Import local market-wide daily K-line CSV caches."""

from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from gupiao.data.akshare_provider import infer_exchange, normalize_symbol
from gupiao.data.storage import SQLiteStore

MARKET_FILE_RE = re.compile(r"market_(\d{4}-\d{2}-\d{2})\.csv$")


@dataclass(frozen=True)
class LocalDailyCacheImportConfig:
    source_dir: str | Path = "cache/daily_k/market_data_cache"
    db_path: str | Path = "data/cache/market_scan.sqlite"
    start: date | None = None
    end: date | None = None
    adjust: str = "hfq"
    provider: str = "local_daily_k"
    conflict: str = "ignore"
    limit_files: int | None = None
    dry_run: bool = False


@dataclass(frozen=True)
class LocalDailyCacheImportResult:
    source_dir: Path
    db_path: Path
    start: date | None
    end: date | None
    adjust: str
    conflict: str
    dry_run: bool
    files_seen: int
    files_imported: int
    rows_seen: int
    rows_importable: int
    bars_written: int
    instruments_written: int
    estimated_volume_rows: int
    invalid_rows: int
    first_trade_date: date | None
    last_trade_date: date | None


def import_local_daily_cache(config: LocalDailyCacheImportConfig) -> LocalDailyCacheImportResult:
    source_dir = Path(config.source_dir)
    db_path = Path(config.db_path)
    files = list(iter_market_files(source_dir, start=config.start, end=config.end))
    if config.limit_files is not None:
        files = files[: config.limit_files]

    files_seen = len(files)
    rows_seen = 0
    rows_importable = 0
    bars_written = 0
    instruments_written = 0
    estimated_volume_rows = 0
    invalid_rows = 0
    first_trade_date: date | None = None
    last_trade_date: date | None = None

    connection: sqlite3.Connection | None = None
    if not config.dry_run:
        store = SQLiteStore(db_path)
        store.init_schema()
        connection = store.connect()

    try:
        for trade_date, path in files:
            parsed = parse_daily_cache_file(
                path,
                trade_date=trade_date,
                adjust=config.adjust,
                provider=config.provider,
            )
            rows_seen += parsed.rows_seen
            rows_importable += len(parsed.bars)
            estimated_volume_rows += parsed.estimated_volume_rows
            invalid_rows += parsed.invalid_rows
            if parsed.bars:
                first_trade_date = min_date(first_trade_date, trade_date)
                last_trade_date = max_date(last_trade_date, trade_date)

            if connection is not None:
                instruments_written += insert_instruments(connection, parsed.instruments)
                bars_written += insert_bars(
                    connection,
                    parsed.bars,
                    conflict=config.conflict,
                )
                connection.commit()
    finally:
        if connection is not None:
            connection.close()

    return LocalDailyCacheImportResult(
        source_dir=source_dir,
        db_path=db_path,
        start=config.start,
        end=config.end,
        adjust=config.adjust,
        conflict=config.conflict,
        dry_run=config.dry_run,
        files_seen=files_seen,
        files_imported=files_seen,
        rows_seen=rows_seen,
        rows_importable=rows_importable,
        bars_written=bars_written,
        instruments_written=instruments_written,
        estimated_volume_rows=estimated_volume_rows,
        invalid_rows=invalid_rows,
        first_trade_date=first_trade_date,
        last_trade_date=last_trade_date,
    )


@dataclass(frozen=True)
class ParsedDailyCacheFile:
    rows_seen: int
    bars: tuple[tuple[Any, ...], ...]
    instruments: tuple[tuple[Any, ...], ...]
    estimated_volume_rows: int
    invalid_rows: int


def iter_market_files(
    source_dir: str | Path,
    *,
    start: date | None = None,
    end: date | None = None,
) -> list[tuple[date, Path]]:
    files: list[tuple[date, Path]] = []
    for path in Path(source_dir).glob("market_*.csv"):
        match = MARKET_FILE_RE.search(path.name)
        if match is None:
            continue
        trade_date = date.fromisoformat(match.group(1))
        if start is not None and trade_date < start:
            continue
        if end is not None and trade_date > end:
            continue
        files.append((trade_date, path))
    return sorted(files, key=lambda item: item[0])


def parse_daily_cache_file(
    path: str | Path,
    *,
    trade_date: date,
    adjust: str,
    provider: str,
) -> ParsedDailyCacheFile:
    rows_seen = 0
    bars: list[tuple[Any, ...]] = []
    instruments: dict[str, tuple[Any, ...]] = {}
    estimated_volume_rows = 0
    invalid_rows = 0
    now = now_text()

    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            rows_seen += 1
            try:
                parsed = row_to_bar(
                    row,
                    trade_date=trade_date,
                    adjust=adjust,
                    provider=provider,
                    updated_at=now,
                )
            except (KeyError, TypeError, ValueError):
                invalid_rows += 1
                continue
            bars.append(parsed.bar)
            if parsed.estimated_volume:
                estimated_volume_rows += 1
            instruments[parsed.instrument[0]] = parsed.instrument

    return ParsedDailyCacheFile(
        rows_seen=rows_seen,
        bars=tuple(bars),
        instruments=tuple(instruments.values()),
        estimated_volume_rows=estimated_volume_rows,
        invalid_rows=invalid_rows,
    )


@dataclass(frozen=True)
class ParsedDailyRow:
    bar: tuple[Any, ...]
    instrument: tuple[Any, ...]
    estimated_volume: bool


def row_to_bar(
    row: dict[str, str],
    *,
    trade_date: date,
    adjust: str,
    provider: str,
    updated_at: str,
) -> ParsedDailyRow:
    symbol = normalize_symbol(required_text(row, "code"))
    name = required_text(row, "name")
    close = required_float(row, "trade", "close", "收盘")
    open_ = required_float(row, "open", "开盘")
    high = required_float(row, "high", "最高")
    low = required_float(row, "low", "最低")
    amount = optional_float(row, "amount", "成交额")
    turnover = optional_float(row, "turnoverratio", "turnover", "换手率")
    volume, estimated_volume = parse_volume(row, close=close, amount=amount)
    row_provider = f"{provider}_estimated_volume" if estimated_volume else provider

    if close <= 0 or open_ <= 0 or high <= 0 or low <= 0:
        raise ValueError("prices must be positive")
    if high < low:
        raise ValueError("high must be greater than or equal to low")

    bar = (
        symbol,
        trade_date.isoformat(),
        open_,
        high,
        low,
        close,
        volume,
        amount,
        turnover,
        adjust,
        row_provider,
        None,
        updated_at,
    )
    instrument = (
        symbol,
        name,
        "A股",
        infer_exchange(symbol),
        None,
        None,
        updated_at,
    )
    return ParsedDailyRow(bar=bar, instrument=instrument, estimated_volume=estimated_volume)


def parse_volume(row: dict[str, str], *, close: float, amount: float | None) -> tuple[float, bool]:
    volume = optional_float(row, "volume", "成交量")
    if volume is not None:
        return volume, False
    if amount is None or close <= 0:
        return 0.0, True
    return amount / close, True


def required_text(row: dict[str, str], key: str) -> str:
    value = row.get(key)
    if value is None or value == "":
        raise KeyError(key)
    return value.strip()


def required_float(row: dict[str, str], *keys: str) -> float:
    value = optional_float(row, *keys)
    if value is None:
        raise KeyError(keys[0])
    return value


def optional_float(row: dict[str, str], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if value is None or value == "":
            continue
        return float(value)
    return None


def insert_instruments(connection: sqlite3.Connection, rows: tuple[tuple[Any, ...], ...]) -> int:
    if not rows:
        return 0
    before = connection.total_changes
    connection.executemany(
        """
        INSERT INTO instruments (
            symbol, name, market, exchange, industry, listed_date, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            name = excluded.name,
            market = excluded.market,
            exchange = excluded.exchange,
            updated_at = excluded.updated_at
        """,
        rows,
    )
    return connection.total_changes - before


def insert_bars(
    connection: sqlite3.Connection,
    rows: tuple[tuple[Any, ...], ...],
    *,
    conflict: str,
) -> int:
    if not rows:
        return 0
    before = connection.total_changes
    if conflict == "ignore":
        sql = """
            INSERT OR IGNORE INTO bars_daily (
                symbol, trade_date, open, high, low, close, volume, amount,
                turnover, adjust, provider, fetched_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    elif conflict == "replace":
        sql = """
            INSERT INTO bars_daily (
                symbol, trade_date, open, high, low, close, volume, amount,
                turnover, adjust, provider, fetched_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, trade_date, adjust) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                amount = excluded.amount,
                turnover = excluded.turnover,
                provider = excluded.provider,
                fetched_at = excluded.fetched_at,
                updated_at = excluded.updated_at
        """
    else:
        raise ValueError("conflict must be 'ignore' or 'replace'")
    connection.executemany(sql, rows)
    return connection.total_changes - before


def min_date(left: date | None, right: date) -> date:
    return right if left is None or right < left else left


def max_date(left: date | None, right: date) -> date:
    return right if left is None or right > left else left


def now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
