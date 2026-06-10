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


@dataclass(frozen=True)
class AuctionMinuteBar:
    symbol: str
    trade_time: datetime
    open: float
    close: float
    high: float
    low: float
    volume: float
    amount: float | None = None
    latest_price: float | None = None
    provider: str | None = None
    fetched_at: datetime | None = None

    @property
    def trade_date(self) -> date:
        return self.trade_time.date()


@dataclass(frozen=True)
class AuctionProfile:
    symbol: str
    trade_date: date
    auction_time: datetime
    indicative_price: float
    open: float
    high: float
    low: float
    volume: float
    amount: float | None = None
    latest_price: float | None = None
    previous_close: float | None = None
    gap_pct: float | None = None
    range_pct: float | None = None
    volume_ratio_to_daily: float | None = None
    bid_ask_imbalance: float | None = None
    strength_score: float = 50.0
    provider: str | None = None
    fetched_at: datetime | None = None
