"""Local SQLite storage for normalized market data."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

from gupiao.compat import UTC
from gupiao.data.schema import AuctionMinuteBar, AuctionProfile, DailyBar, Instrument


class SQLiteStore:
    """Small local store used before DuckDB/Parquet expansion."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def init_schema(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS instruments (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    market TEXT NOT NULL,
                    exchange TEXT,
                    industry TEXT,
                    listed_date TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bars_daily (
                    symbol TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    amount REAL,
                    turnover REAL,
                    adjust TEXT NOT NULL,
                    provider TEXT,
                    fetched_at TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (symbol, trade_date, adjust)
                );

                CREATE TABLE IF NOT EXISTS auction_profiles (
                    symbol TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    auction_time TEXT NOT NULL,
                    indicative_price REAL NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    volume REAL NOT NULL,
                    amount REAL,
                    latest_price REAL,
                    previous_close REAL,
                    gap_pct REAL,
                    range_pct REAL,
                    volume_ratio_to_daily REAL,
                    bid_ask_imbalance REAL,
                    strength_score REAL NOT NULL,
                    provider TEXT NOT NULL,
                    fetched_at TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (symbol, trade_date, provider)
                );

                CREATE TABLE IF NOT EXISTS auction_minutes (
                    symbol TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    trade_time TEXT NOT NULL,
                    open REAL NOT NULL,
                    close REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    volume REAL NOT NULL,
                    amount REAL,
                    latest_price REAL,
                    provider TEXT NOT NULL,
                    fetched_at TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (symbol, trade_time, provider)
                );
                """
            )
            ensure_column(
                connection,
                table="auction_profiles",
                column="bid_ask_imbalance",
                definition="REAL",
            )

    def upsert_instruments(self, instruments: Iterable[Instrument]) -> int:
        rows = [
            (
                instrument.symbol,
                instrument.name,
                instrument.market,
                instrument.exchange,
                instrument.industry,
                date_to_text(instrument.listed_date),
                now_text(),
            )
            for instrument in instruments
        ]
        if not rows:
            return 0

        self.init_schema()
        with self.connect() as connection:
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
                    industry = excluded.industry,
                    listed_date = excluded.listed_date,
                    updated_at = excluded.updated_at
                """,
                rows,
            )
        return len(rows)

    def list_instruments(self, *, limit: int | None = None) -> list[Instrument]:
        self.init_schema()
        sql = """
            SELECT symbol, name, market, exchange, industry, listed_date
            FROM instruments
            ORDER BY symbol
        """
        parameters: tuple[int, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            parameters = (limit,)
        with self.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [
            Instrument(
                symbol=row["symbol"],
                name=row["name"],
                market=row["market"],
                exchange=row["exchange"],
                industry=row["industry"],
                listed_date=text_to_date(row["listed_date"]),
            )
            for row in rows
        ]

    def list_daily_bar_symbols(
        self,
        *,
        start: date | None = None,
        end: date | None = None,
        adjust: str | None = None,
        limit: int | None = None,
    ) -> list[str]:
        self.init_schema()
        sql = """
            SELECT DISTINCT symbol
            FROM bars_daily
            WHERE 1 = 1
        """
        parameters: list[str | int] = []
        if start is not None:
            sql += " AND trade_date >= ?"
            parameters.append(date_to_text(start) or "")
        if end is not None:
            sql += " AND trade_date <= ?"
            parameters.append(date_to_text(end) or "")
        if adjust is not None:
            sql += " AND adjust = ?"
            parameters.append(adjust)
        sql += " ORDER BY symbol"
        if limit is not None:
            sql += " LIMIT ?"
            parameters.append(limit)

        with self.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [row["symbol"] for row in rows]

    def daily_bar_date_range(self, *, adjust: str | None = None) -> tuple[date | None, date | None]:
        self.init_schema()
        sql = "SELECT MIN(trade_date) AS start, MAX(trade_date) AS end FROM bars_daily"
        parameters: list[str] = []
        if adjust is not None:
            sql += " WHERE adjust = ?"
            parameters.append(adjust)
        with self.connect() as connection:
            row = connection.execute(sql, parameters).fetchone()
        return text_to_date(row["start"]), text_to_date(row["end"])

    def list_daily_bar_dates(
        self,
        *,
        start: date | None = None,
        end: date | None = None,
        adjust: str | None = None,
    ) -> list[date]:
        self.init_schema()
        sql = "SELECT DISTINCT trade_date FROM bars_daily WHERE 1 = 1"
        parameters: list[str] = []
        if start is not None:
            sql += " AND trade_date >= ?"
            parameters.append(date_to_text(start) or "")
        if end is not None:
            sql += " AND trade_date <= ?"
            parameters.append(date_to_text(end) or "")
        if adjust is not None:
            sql += " AND adjust = ?"
            parameters.append(adjust)
        sql += " ORDER BY trade_date"
        with self.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [text_to_date(row["trade_date"]) or date.min for row in rows]

    def data_status(self) -> dict[str, object]:
        self.init_schema()
        with self.connect() as connection:
            instrument_count = connection.execute(
                "SELECT COUNT(*) AS count FROM instruments"
            ).fetchone()["count"]
            daily = connection.execute(
                """
                SELECT COUNT(*) AS rows,
                       COUNT(DISTINCT symbol) AS symbols,
                       MIN(trade_date) AS start,
                       MAX(trade_date) AS end
                FROM bars_daily
                """
            ).fetchone()
            auction = connection.execute(
                """
                SELECT COUNT(*) AS rows,
                       COUNT(DISTINCT symbol) AS symbols,
                       MIN(trade_date) AS start,
                       MAX(trade_date) AS end
                FROM auction_profiles
                """
            ).fetchone()
            auction_minutes = connection.execute(
                """
                SELECT COUNT(*) AS rows,
                       COUNT(DISTINCT symbol) AS symbols,
                       MIN(trade_date) AS start,
                       MAX(trade_date) AS end
                FROM auction_minutes
                """
            ).fetchone()
            adjusts = [
                row["adjust"]
                for row in connection.execute(
                    "SELECT DISTINCT adjust FROM bars_daily ORDER BY adjust"
                ).fetchall()
            ]
            auction_providers = [
                row["provider"]
                for row in connection.execute(
                    "SELECT DISTINCT provider FROM auction_profiles ORDER BY provider"
                ).fetchall()
            ]
            auction_minute_providers = [
                row["provider"]
                for row in connection.execute(
                    "SELECT DISTINCT provider FROM auction_minutes ORDER BY provider"
                ).fetchall()
            ]
        return {
            "db_path": str(self.path),
            "instruments": {"count": instrument_count},
            "daily_bars": {
                "rows": daily["rows"],
                "symbols": daily["symbols"],
                "start": daily["start"],
                "end": daily["end"],
                "adjusts": adjusts,
            },
            "auction_profiles": {
                "rows": auction["rows"],
                "symbols": auction["symbols"],
                "start": auction["start"],
                "end": auction["end"],
                "providers": auction_providers,
            },
            "auction_minutes": {
                "rows": auction_minutes["rows"],
                "symbols": auction_minutes["symbols"],
                "start": auction_minutes["start"],
                "end": auction_minutes["end"],
                "providers": auction_minute_providers,
            },
        }

    def upsert_daily_bars(self, bars: Iterable[DailyBar]) -> int:
        rows = [
            (
                bar.symbol,
                date_to_text(bar.trade_date),
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
                bar.amount,
                bar.turnover,
                bar.adjust or "",
                bar.provider,
                datetime_to_text(bar.fetched_at),
                now_text(),
            )
            for bar in bars
        ]
        if not rows:
            return 0

        self.init_schema()
        with self.connect() as connection:
            connection.executemany(
                """
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
                """,
                rows,
            )
        return len(rows)

    def get_daily_bars(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        adjust: str | None = None,
    ) -> list[DailyBar]:
        self.init_schema()
        sql = """
            SELECT symbol, trade_date, open, high, low, close, volume, amount,
                   turnover, adjust, provider, fetched_at
            FROM bars_daily
            WHERE symbol = ?
        """
        parameters: list[str] = [symbol]
        if start is not None:
            sql += " AND trade_date >= ?"
            parameters.append(date_to_text(start) or "")
        if end is not None:
            sql += " AND trade_date <= ?"
            parameters.append(date_to_text(end) or "")
        if adjust is not None:
            sql += " AND adjust = ?"
            parameters.append(adjust)
        sql += " ORDER BY trade_date"

        with self.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [
            DailyBar(
                symbol=row["symbol"],
                trade_date=text_to_date(row["trade_date"]) or date.min,
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
                amount=row["amount"],
                turnover=row["turnover"],
                adjust=row["adjust"] or None,
                provider=row["provider"],
                fetched_at=text_to_datetime(row["fetched_at"]),
            )
            for row in rows
        ]

    def upsert_auction_profiles(self, profiles: Iterable[AuctionProfile]) -> int:
        rows = [
            (
                profile.symbol,
                date_to_text(profile.trade_date),
                datetime_to_text(profile.auction_time),
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
                datetime_to_text(profile.fetched_at),
                now_text(),
            )
            for profile in profiles
        ]
        if not rows:
            return 0

        self.init_schema()
        with self.connect() as connection:
            connection.executemany(
                """
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
                """,
                rows,
            )
        return len(rows)

    def upsert_auction_minutes(self, minutes: Iterable[AuctionMinuteBar]) -> int:
        rows = [
            (
                minute.symbol,
                date_to_text(minute.trade_date),
                datetime_to_text(minute.trade_time),
                minute.open,
                minute.close,
                minute.high,
                minute.low,
                minute.volume,
                minute.amount,
                minute.latest_price,
                minute.provider or "",
                datetime_to_text(minute.fetched_at),
                now_text(),
            )
            for minute in minutes
        ]
        if not rows:
            return 0

        self.init_schema()
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO auction_minutes (
                    symbol, trade_date, trade_time, open, close, high, low,
                    volume, amount, latest_price, provider, fetched_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, trade_time, provider) DO UPDATE SET
                    open = excluded.open,
                    close = excluded.close,
                    high = excluded.high,
                    low = excluded.low,
                    volume = excluded.volume,
                    amount = excluded.amount,
                    latest_price = excluded.latest_price,
                    fetched_at = excluded.fetched_at,
                    updated_at = excluded.updated_at
                """,
                rows,
            )
        return len(rows)

    def get_auction_minutes(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        provider: str | None = None,
    ) -> list[AuctionMinuteBar]:
        self.init_schema()
        sql = """
            SELECT symbol, trade_time, open, close, high, low, volume, amount,
                   latest_price, provider, fetched_at
            FROM auction_minutes
            WHERE symbol = ?
        """
        parameters: list[str] = [symbol]
        if start is not None:
            sql += " AND trade_date >= ?"
            parameters.append(date_to_text(start) or "")
        if end is not None:
            sql += " AND trade_date <= ?"
            parameters.append(date_to_text(end) or "")
        if provider is not None:
            sql += " AND provider = ?"
            parameters.append(provider)
        sql += " ORDER BY trade_time"

        with self.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [
            AuctionMinuteBar(
                symbol=row["symbol"],
                trade_time=text_to_datetime(row["trade_time"]) or datetime.min,
                open=row["open"],
                close=row["close"],
                high=row["high"],
                low=row["low"],
                volume=row["volume"],
                amount=row["amount"],
                latest_price=row["latest_price"],
                provider=row["provider"] or None,
                fetched_at=text_to_datetime(row["fetched_at"]),
            )
            for row in rows
        ]

    def get_auction_profiles(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        provider: str | None = None,
    ) -> list[AuctionProfile]:
        self.init_schema()
        sql = """
            SELECT symbol, trade_date, auction_time, indicative_price, open, high,
                   low, volume, amount, latest_price, previous_close, gap_pct,
                   range_pct, volume_ratio_to_daily, bid_ask_imbalance,
                   strength_score, provider, fetched_at
            FROM auction_profiles
            WHERE symbol = ?
        """
        parameters: list[str] = [symbol]
        if start is not None:
            sql += " AND trade_date >= ?"
            parameters.append(date_to_text(start) or "")
        if end is not None:
            sql += " AND trade_date <= ?"
            parameters.append(date_to_text(end) or "")
        if provider is not None:
            sql += " AND provider = ?"
            parameters.append(provider)
        sql += " ORDER BY trade_date"

        with self.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [auction_profile_from_row(row) for row in rows]

    def list_auction_profile_symbols(
        self,
        *,
        start: date | None = None,
        end: date | None = None,
        provider: str | None = None,
        limit: int | None = None,
    ) -> list[str]:
        self.init_schema()
        sql = """
            SELECT DISTINCT symbol
            FROM auction_profiles
            WHERE 1 = 1
        """
        parameters: list[str | int] = []
        if start is not None:
            sql += " AND trade_date >= ?"
            parameters.append(date_to_text(start) or "")
        if end is not None:
            sql += " AND trade_date <= ?"
            parameters.append(date_to_text(end) or "")
        if provider is not None:
            sql += " AND provider = ?"
            parameters.append(provider)
        sql += " ORDER BY symbol"
        if limit is not None:
            sql += " LIMIT ?"
            parameters.append(limit)

        with self.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [row["symbol"] for row in rows]

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection


def now_text() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def date_to_text(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def datetime_to_text(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def text_to_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def text_to_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def ensure_column(
    connection: sqlite3.Connection,
    *,
    table: str,
    column: str,
    definition: str,
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def auction_profile_from_row(row: sqlite3.Row) -> AuctionProfile:
    return AuctionProfile(
        symbol=row["symbol"],
        trade_date=text_to_date(row["trade_date"]) or date.min,
        auction_time=text_to_datetime(row["auction_time"]) or datetime.min,
        indicative_price=row["indicative_price"],
        open=row["open"],
        high=row["high"],
        low=row["low"],
        volume=row["volume"],
        amount=row["amount"],
        latest_price=row["latest_price"],
        previous_close=row["previous_close"],
        gap_pct=row["gap_pct"],
        range_pct=row["range_pct"],
        volume_ratio_to_daily=row["volume_ratio_to_daily"],
        bid_ask_imbalance=row["bid_ask_imbalance"],
        strength_score=row["strength_score"],
        provider=row["provider"] or None,
        fetched_at=text_to_datetime(row["fetched_at"]),
    )
