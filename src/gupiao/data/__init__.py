"""Data ingestion interfaces and schemas."""

from gupiao.data.akshare_provider import AkshareProvider
from gupiao.data.local_daily_cache import (
    LocalDailyCacheImportConfig,
    LocalDailyCacheImportResult,
    import_local_daily_cache,
)
from gupiao.data.providers import DataProvider
from gupiao.data.quality import (
    ValidationIssue,
    has_errors,
    validate_daily_bars,
    validate_instruments,
)
from gupiao.data.schema import AuctionMinuteBar, AuctionProfile, DailyBar, Instrument
from gupiao.data.storage import SQLiteStore

__all__ = [
    "AkshareProvider",
    "AuctionMinuteBar",
    "AuctionProfile",
    "DailyBar",
    "DataProvider",
    "Instrument",
    "LocalDailyCacheImportConfig",
    "LocalDailyCacheImportResult",
    "SQLiteStore",
    "ValidationIssue",
    "has_errors",
    "import_local_daily_cache",
    "validate_daily_bars",
    "validate_instruments",
]
