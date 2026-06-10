"""Data ingestion interfaces and schemas."""

from gupiao.data.akshare_provider import AkshareProvider
from gupiao.data.providers import DataProvider
from gupiao.data.schema import DailyBar, Instrument
from gupiao.data.storage import SQLiteStore

__all__ = ["AkshareProvider", "DailyBar", "DataProvider", "Instrument", "SQLiteStore"]
