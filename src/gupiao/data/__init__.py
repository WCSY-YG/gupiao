"""Data ingestion interfaces and schemas."""

from gupiao.data.providers import DataProvider
from gupiao.data.schema import DailyBar, Instrument

__all__ = ["DailyBar", "DataProvider", "Instrument"]
