"""Import local RAR-packed call-auction snapshots as daily auction profiles."""

from __future__ import annotations

import csv
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, TextIO

from gupiao.auction import score_auction_profile
from gupiao.data.akshare_provider import normalize_symbol
from gupiao.data.schema import AuctionProfile
from gupiao.data.storage import SQLiteStore, now_text


@dataclass(frozen=True)
class LocalAuctionCacheImportConfig:
    source_dir: str | Path = "cache/jingjia"
    db_path: str | Path = "data/cache/market_scan.sqlite"
    start: date | None = None
    end: date | None = None
    provider: str = "local_jingjia"
    start_time: str = "09:15:00"
    end_time: str = "09:25:03"
    conflict: str = "ignore"
    limit_archives: int | None = None
    limit_files: int | None = None
    dry_run: bool = False
    daily_volume_lookback_days: int = 60


@dataclass(frozen=True)
class LocalAuctionCacheImportResult:
    source_dir: Path
    db_path: Path
    start: date | None
    end: date | None
    provider: str
    start_time: str
    end_time: str
    conflict: str
    dry_run: bool
    archives_seen: int
    files_seen: int
    files_imported: int
    rows_seen: int
    rows_in_window: int
    profiles_built: int
    profiles_written: int
    invalid_rows: int
    first_trade_date: date | None
    last_trade_date: date | None


@dataclass(frozen=True)
class AuctionMember:
    archive_path: Path
    member_name: str
    trade_date: date


@dataclass(frozen=True)
class ParsedAuctionFile:
    trade_date: date
    rows_seen: int
    rows_in_window: int
    invalid_rows: int
    profiles: tuple[AuctionProfile, ...]


@dataclass
class AuctionState:
    symbol: str
    trade_date: date
    provider: str
    previous_close: float | None = None
    latest_time: int = 0
    indicative_price: float = 0.0
    open: float = 0.0
    latest_price: float | None = None
    high: float = 0.0
    low: float = 0.0
    volume_lots: float = 0.0
    amount: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None

    def update(self, row: dict[str, str], *, time_code: int) -> None:
        price = required_float(row, "last")
        if price <= 0:
            return
        self.previous_close = optional_float(row, "pre_close") or self.previous_close
        self.high = price if self.high <= 0 else max(self.high, price)
        self.low = price if self.low <= 0 else min(self.low, price)

        if time_code >= self.latest_time:
            self.latest_time = time_code
            self.indicative_price = price
            row_open = optional_float(row, "open")
            self.open = row_open if row_open and row_open > 0 else price
            self.latest_price = price
            self.volume_lots = optional_float(row, "total_volume_trade") or self.volume_lots
            self.amount = optional_float(row, "total_value_trade") or self.amount
            bid_size_1 = optional_float(row, "bid_size1") or 0.0
            bid_size_2 = optional_float(row, "bid_size2") or 0.0
            ask_size_1 = optional_float(row, "ask_size1") or 0.0
            ask_size_2 = optional_float(row, "ask_size2") or 0.0
            self.bid_size = bid_size_1 + bid_size_2
            self.ask_size = ask_size_1 + ask_size_2

    def to_profile(self, *, average_daily_volume: float | None = None) -> AuctionProfile | None:
        if self.latest_time <= 0 or self.indicative_price <= 0:
            return None
        volume = self.volume_lots * 100.0
        gap_pct = (
            (self.indicative_price / self.previous_close) - 1
            if self.previous_close and self.previous_close > 0
            else None
        )
        range_pct = (self.high / self.low) - 1 if self.low > 0 else None
        volume_ratio = (
            volume / average_daily_volume
            if average_daily_volume is not None and average_daily_volume > 0
            else None
        )
        imbalance = bid_ask_imbalance(self.bid_size, self.ask_size)
        return AuctionProfile(
            symbol=self.symbol,
            trade_date=self.trade_date,
            auction_time=datetime.combine(self.trade_date, time_from_code(self.latest_time)),
            indicative_price=self.indicative_price,
            open=self.open or self.indicative_price,
            high=self.high,
            low=self.low,
            volume=volume,
            amount=self.amount,
            latest_price=self.latest_price,
            previous_close=self.previous_close,
            gap_pct=gap_pct,
            range_pct=range_pct,
            volume_ratio_to_daily=volume_ratio,
            bid_ask_imbalance=imbalance,
            strength_score=score_auction_profile(
                gap_pct=gap_pct,
                range_pct=range_pct,
                volume_ratio_to_daily=volume_ratio,
                bid_ask_imbalance=imbalance,
            ),
            provider=self.provider,
        )


def import_local_auction_cache(
    config: LocalAuctionCacheImportConfig,
) -> LocalAuctionCacheImportResult:
    require_unrar()
    members = iter_auction_members(
        config.source_dir,
        start=config.start,
        end=config.end,
        limit_archives=config.limit_archives,
        limit_files=config.limit_files,
    )
    files_seen = len(members)
    archives_seen = len({member.archive_path for member in members})
    start_code = parse_hhmmss_to_code(config.start_time)
    end_code = parse_hhmmss_to_code(config.end_time)

    connection: sqlite3.Connection | None = None
    if not config.dry_run:
        store = SQLiteStore(config.db_path)
        store.init_schema()
        connection = store.connect()
    elif Path(config.db_path).exists():
        connection = SQLiteStore(config.db_path).connect()

    rows_seen = 0
    rows_in_window = 0
    invalid_rows = 0
    profiles_built = 0
    profiles_written = 0
    first_trade_date: date | None = None
    last_trade_date: date | None = None

    try:
        for member in members:
            averages = (
                average_daily_volume_by_symbol(
                    connection,
                    member.trade_date,
                    lookback_days=config.daily_volume_lookback_days,
                )
                if connection is not None
                else {}
            )
            parsed = parse_auction_member(
                member,
                provider=config.provider,
                start_code=start_code,
                end_code=end_code,
                average_daily_volume_by_symbol=averages,
            )
            rows_seen += parsed.rows_seen
            rows_in_window += parsed.rows_in_window
            invalid_rows += parsed.invalid_rows
            profiles_built += len(parsed.profiles)
            if parsed.profiles:
                first_trade_date = min_date(first_trade_date, member.trade_date)
                last_trade_date = max_date(last_trade_date, member.trade_date)
            if connection is not None and not config.dry_run:
                profiles_written += insert_auction_profiles(
                    connection,
                    parsed.profiles,
                    conflict=config.conflict,
                )
                connection.commit()
    finally:
        if connection is not None:
            connection.close()

    return LocalAuctionCacheImportResult(
        source_dir=Path(config.source_dir),
        db_path=Path(config.db_path),
        start=config.start,
        end=config.end,
        provider=config.provider,
        start_time=config.start_time,
        end_time=config.end_time,
        conflict=config.conflict,
        dry_run=config.dry_run,
        archives_seen=archives_seen,
        files_seen=files_seen,
        files_imported=files_seen,
        rows_seen=rows_seen,
        rows_in_window=rows_in_window,
        profiles_built=profiles_built,
        profiles_written=profiles_written,
        invalid_rows=invalid_rows,
        first_trade_date=first_trade_date,
        last_trade_date=last_trade_date,
    )


def iter_auction_members(
    source_dir: str | Path,
    *,
    start: date | None = None,
    end: date | None = None,
    limit_archives: int | None = None,
    limit_files: int | None = None,
) -> list[AuctionMember]:
    archives = sorted(Path(source_dir).glob("*.rar"))
    if limit_archives is not None:
        archives = archives[:limit_archives]
    members: list[AuctionMember] = []
    for archive in archives:
        for member_name in list_rar_members(archive):
            if not member_name.endswith(".csv"):
                continue
            trade_date = date_from_member(member_name)
            if trade_date is None:
                continue
            if start is not None and trade_date < start:
                continue
            if end is not None and trade_date > end:
                continue
            members.append(
                AuctionMember(
                    archive_path=archive,
                    member_name=member_name,
                    trade_date=trade_date,
                )
            )
    members = sorted(members, key=lambda item: (item.trade_date, item.member_name))
    if limit_files is not None:
        members = members[:limit_files]
    return members


def list_rar_members(archive_path: Path) -> list[str]:
    completed = subprocess.run(
        ["unrar", "lb", str(archive_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def parse_auction_member(
    member: AuctionMember,
    *,
    provider: str,
    start_code: int,
    end_code: int,
    average_daily_volume_by_symbol: dict[str, float],
) -> ParsedAuctionFile:
    process = subprocess.Popen(
        ["unrar", "p", "-inul", str(member.archive_path), member.member_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8-sig",
    )
    assert process.stdout is not None
    try:
        parsed = parse_auction_csv(
            process.stdout,
            trade_date=member.trade_date,
            provider=provider,
            start_code=start_code,
            end_code=end_code,
            average_daily_volume_by_symbol=average_daily_volume_by_symbol,
        )
    finally:
        stderr = process.stderr.read() if process.stderr is not None else ""
        return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(
            f"unrar failed for {member.archive_path}:{member.member_name}: {stderr.strip()}"
        )
    return parsed


def parse_auction_csv(
    file: TextIO,
    *,
    trade_date: date,
    provider: str,
    start_code: int,
    end_code: int,
    average_daily_volume_by_symbol: dict[str, float] | None = None,
) -> ParsedAuctionFile:
    averages = average_daily_volume_by_symbol or {}
    reader = csv.DictReader(file)
    states: dict[str, AuctionState] = {}
    rows_seen = 0
    rows_in_window = 0
    invalid_rows = 0

    for row in reader:
        rows_seen += 1
        try:
            time_code = int(required_text(row, "md_time"))
            if time_code < start_code or time_code > end_code:
                continue
            rows_in_window += 1
            symbol = normalize_symbol(required_text(row, "security_id"))
            state = states.setdefault(
                symbol,
                AuctionState(symbol=symbol, trade_date=trade_date, provider=provider),
            )
            state.update(row, time_code=time_code)
        except (KeyError, TypeError, ValueError):
            invalid_rows += 1

    profiles = [
        profile
        for state in states.values()
        if (
            profile := state.to_profile(
                average_daily_volume=averages.get(state.symbol),
            )
        )
        is not None
    ]
    return ParsedAuctionFile(
        trade_date=trade_date,
        rows_seen=rows_seen,
        rows_in_window=rows_in_window,
        invalid_rows=invalid_rows,
        profiles=tuple(sorted(profiles, key=lambda item: item.symbol)),
    )


def average_daily_volume_by_symbol(
    connection: sqlite3.Connection,
    trade_date: date,
    *,
    lookback_days: int,
) -> dict[str, float]:
    rows = connection.execute(
        """
        SELECT symbol, AVG(volume) AS average_volume
        FROM bars_daily
        WHERE trade_date < ?
          AND trade_date >= date(?, ?)
          AND adjust = 'hfq'
        GROUP BY symbol
        """,
        (trade_date.isoformat(), trade_date.isoformat(), f"-{lookback_days} day"),
    ).fetchall()
    return {
        row["symbol"]: row["average_volume"]
        for row in rows
        if row["average_volume"] is not None and row["average_volume"] > 0
    }


def insert_auction_profiles(
    connection: sqlite3.Connection,
    profiles: tuple[AuctionProfile, ...],
    *,
    conflict: str,
) -> int:
    if not profiles:
        return 0
    rows = [auction_profile_row(profile) for profile in profiles]
    before = connection.total_changes
    if conflict == "ignore":
        sql = """
            INSERT OR IGNORE INTO auction_profiles (
                symbol, trade_date, auction_time, indicative_price, open, high,
                low, volume, amount, latest_price, previous_close, gap_pct,
                range_pct, volume_ratio_to_daily, bid_ask_imbalance,
                strength_score, provider, fetched_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    elif conflict == "replace":
        sql = """
            INSERT INTO auction_profiles (
                symbol, trade_date, auction_time, indicative_price, open, high,
                low, volume, amount, latest_price, previous_close, gap_pct,
                range_pct, volume_ratio_to_daily, bid_ask_imbalance,
                strength_score, provider, fetched_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, trade_date, provider) DO UPDATE SET
                auction_time = excluded.auction_time,
                indicative_price = excluded.indicative_price,
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                volume = excluded.volume,
                amount = excluded.amount,
                latest_price = excluded.latest_price,
                previous_close = excluded.previous_close,
                gap_pct = excluded.gap_pct,
                range_pct = excluded.range_pct,
                volume_ratio_to_daily = excluded.volume_ratio_to_daily,
                bid_ask_imbalance = excluded.bid_ask_imbalance,
                strength_score = excluded.strength_score,
                fetched_at = excluded.fetched_at,
                updated_at = excluded.updated_at
        """
    else:
        raise ValueError("conflict must be 'ignore' or 'replace'")
    connection.executemany(sql, rows)
    return connection.total_changes - before


def auction_profile_row(profile: AuctionProfile) -> tuple[Any, ...]:
    return (
        profile.symbol,
        profile.trade_date.isoformat(),
        profile.auction_time.isoformat(),
        profile.indicative_price,
        profile.open,
        profile.high,
        profile.low,
        profile.volume,
        profile.amount,
        profile.latest_price,
        profile.previous_close,
        profile.gap_pct,
        profile.range_pct,
        profile.volume_ratio_to_daily,
        profile.bid_ask_imbalance,
        profile.strength_score,
        profile.provider or "",
        profile.fetched_at.isoformat() if profile.fetched_at else None,
        now_text(),
    )


def bid_ask_imbalance(bid_size: float | None, ask_size: float | None) -> float | None:
    if bid_size is None or ask_size is None:
        return None
    total = bid_size + ask_size
    if total <= 0:
        return None
    return (bid_size - ask_size) / total


def date_from_member(member_name: str) -> date | None:
    stem = Path(member_name).stem
    if len(stem) != 8 or not stem.isdigit():
        return None
    return date.fromisoformat(f"{stem[:4]}-{stem[4:6]}-{stem[6:]}")


def parse_hhmmss_to_code(value: str) -> int:
    hour, minute, second = (int(part) for part in value.split(":"))
    return ((hour * 10_000) + (minute * 100) + second) * 1000


def time_from_code(value: int):
    text = str(value).zfill(9)
    return datetime.strptime(text[:6], "%H%M%S").time()


def required_text(row: dict[str, str], key: str) -> str:
    value = row.get(key)
    if value is None or value == "":
        raise KeyError(key)
    return value.strip()


def required_float(row: dict[str, str], key: str) -> float:
    return float(required_text(row, key))


def optional_float(row: dict[str, str], key: str) -> float | None:
    value = row.get(key)
    if value is None or value == "":
        return None
    return float(value)


def min_date(left: date | None, right: date) -> date:
    return right if left is None or right < left else left


def max_date(left: date | None, right: date) -> date:
    return right if left is None or right > left else left


def require_unrar() -> None:
    if shutil.which("unrar") is None:
        raise RuntimeError("unrar is required to import cache/jingjia RAR archives")
