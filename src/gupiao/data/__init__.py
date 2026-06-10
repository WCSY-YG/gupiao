"""Data ingestion interfaces and schemas."""

from gupiao.data.akshare_provider import AkshareProvider
from gupiao.data.auction_monitor import (
    AuctionMonitorConfig,
    AuctionMonitorResult,
    AuctionMonitorSymbolResult,
    monitor_live_auction,
)
from gupiao.data.local_auction_cache import (
    LocalAuctionCacheImportConfig,
    LocalAuctionCacheImportResult,
    import_local_auction_cache,
)
from gupiao.data.local_daily_cache import (
    LocalDailyCacheImportConfig,
    LocalDailyCacheImportResult,
    import_local_daily_cache,
)
from gupiao.data.market_cache import (
    MarketCacheRefreshConfig,
    MarketCacheRefreshResult,
    refresh_market_daily_cache,
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
    "AuctionMonitorConfig",
    "AuctionMonitorResult",
    "AuctionMonitorSymbolResult",
    "AuctionMinuteBar",
    "AuctionProfile",
    "DailyBar",
    "DataProvider",
    "Instrument",
    "LocalAuctionCacheImportConfig",
    "LocalAuctionCacheImportResult",
    "LocalDailyCacheImportConfig",
    "LocalDailyCacheImportResult",
    "MarketCacheRefreshConfig",
    "MarketCacheRefreshResult",
    "SQLiteStore",
    "ValidationIssue",
    "has_errors",
    "import_local_auction_cache",
    "import_local_daily_cache",
    "monitor_live_auction",
    "refresh_market_daily_cache",
    "validate_daily_bars",
    "validate_instruments",
]
