"""Local SQLite storage for normalized market data."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import date, datetime, timezone
from pathlib import Path

from gupiao.data.schema import DailyBar, Instrument


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
                """
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

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection


def now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def date_to_text(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def datetime_to_text(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def text_to_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def text_to_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None
