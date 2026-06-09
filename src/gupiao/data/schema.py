"""Core data records shared across the project."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    market: str
    exchange: str | None = None
    industry: str | None = None
    listed_date: date | None = None


@dataclass(frozen=True)
class DailyBar:
    symbol: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float | None = None
    turnover: float | None = None
    adjust: str | None = None
    provider: str | None = None
    fetched_at: datetime | None = None
