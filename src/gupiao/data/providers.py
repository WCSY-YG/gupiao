"""Provider interfaces for market data ingestion."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Protocol

from gupiao.data.schema import DailyBar, Instrument


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
