"""Provider interfaces for market data ingestion."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Protocol

from gupiao.data.schema import AuctionMinuteBar, DailyBar, Instrument


class DataProvider(Protocol):
    """Minimal provider boundary used by strategies and jobs."""

    name: str

    def list_instruments(self) -> Iterable[Instrument]:
        """Return the tradable instrument universe."""

    def fetch_daily_bars(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        adjust: str = "hfq",
    ) -> Iterable[DailyBar]:
        """Return daily OHLCV bars for one symbol."""

    def fetch_pre_market_minutes(
        self,
        symbol: str,
        *,
        start_time: str = "09:15:00",
        end_time: str = "09:25:00",
    ) -> Iterable[AuctionMinuteBar]:
        """Return the latest available pre-market call-auction minute bars."""
