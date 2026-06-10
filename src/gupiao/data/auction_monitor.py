"""One-shot live call-auction monitor that writes incremental local cache."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path

from gupiao.auction import build_auction_profile
from gupiao.data.providers import DataProvider
from gupiao.data.schema import AuctionMinuteBar, AuctionProfile, DailyBar, Instrument
from gupiao.data.storage import SQLiteStore


@dataclass(frozen=True)
class AuctionMonitorConfig:
    db_path: str | Path = "data/cache/market_scan.sqlite"
    trade_date: date | None = None
    auction_provider: str = "akshare_live"
    daily_adjust: str = "raw"
    start_time: str = "09:15:00"
    end_time: str = "09:25:00"
    average_volume_window: int = 20
    daily_lookback_days: int = 45
    limit: int | None = None
    symbols: tuple[str, ...] = ()
    retries: int = 3
    retry_sleep_seconds: float = 1.0
    request_sleep_seconds: float = 0.0
    cache_daily_bars: bool = True
    cache_auction_minutes: bool = True


@dataclass(frozen=True)
class AuctionMonitorSymbolResult:
    symbol: str
    name: str
    status: str
    auction_trade_date: date | None = None
    previous_trade_date: date | None = None
    minutes_count: int = 0
    daily_bars_written: int = 0
    auction_minutes_written: int = 0
    auction_profile_written: int = 0
    previous_open: float | None = None
    previous_close: float | None = None
    strength_score: float | None = None
    gap_pct: float | None = None
    error: str | None = None


@dataclass(frozen=True)
class AuctionMonitorResult:
    db_path: Path
    requested_trade_date: date | None
    auction_provider: str
    daily_adjust: str
    instrument_count: int
    processed: int
    succeeded: int
    failed: int
    no_data: int
    date_mismatch: int
    daily_rows_written: int
    auction_minutes_written: int
    auction_profiles_written: int
    results: tuple[AuctionMonitorSymbolResult, ...]


@dataclass(frozen=True)
class DailyContext:
    bars: tuple[DailyBar, ...]
    fetched_bars: tuple[DailyBar, ...]


def monitor_live_auction(
    provider: DataProvider,
    *,
    config: AuctionMonitorConfig | None = None,
    store: SQLiteStore | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> AuctionMonitorResult:
    config = config or AuctionMonitorConfig()
    validate_monitor_config(config)
    store = store or SQLiteStore(config.db_path)
    instruments = resolve_monitor_instruments(provider, store, config)

    results: list[AuctionMonitorSymbolResult] = []
    daily_rows_written = 0
    auction_minutes_written = 0
    auction_profiles_written = 0
    for instrument in instruments:
        result = monitor_symbol(
            provider,
            store=store,
            instrument=instrument,
            config=config,
            sleep=sleep,
        )
        results.append(result)
        daily_rows_written += result.daily_bars_written
        auction_minutes_written += result.auction_minutes_written
        auction_profiles_written += result.auction_profile_written

    return AuctionMonitorResult(
        db_path=Path(config.db_path),
        requested_trade_date=config.trade_date,
        auction_provider=config.auction_provider,
        daily_adjust=config.daily_adjust,
        instrument_count=len(instruments),
        processed=len(results),
        succeeded=sum(1 for result in results if result.status == "success"),
        failed=sum(1 for result in results if result.status == "failed"),
        no_data=sum(1 for result in results if result.status == "no_data"),
        date_mismatch=sum(1 for result in results if result.status == "date_mismatch"),
        daily_rows_written=daily_rows_written,
        auction_minutes_written=auction_minutes_written,
        auction_profiles_written=auction_profiles_written,
        results=tuple(results),
    )


def monitor_symbol(
    provider: DataProvider,
    *,
    store: SQLiteStore,
    instrument: Instrument,
    config: AuctionMonitorConfig,
    sleep: Callable[[float], None],
) -> AuctionMonitorSymbolResult:
    try:
        daily_context = daily_context_for_symbol(
            provider,
            store,
            instrument.symbol,
            config,
            sleep,
        )
        daily_bars = list(daily_context.bars)
        minutes = fetch_minutes_with_retries(
            provider,
            instrument.symbol,
            config=config,
            sleep=sleep,
        )
        if not minutes:
            return AuctionMonitorSymbolResult(
                symbol=instrument.symbol,
                name=instrument.name,
                status="no_data",
                previous_trade_date=latest_daily_date_before(daily_bars, config.trade_date),
                error="no_pre_market_minutes",
            )

        actual_trade_date = minutes[-1].trade_date
        daily_bars = [bar for bar in daily_bars if bar.trade_date < actual_trade_date]
        if config.trade_date is not None and actual_trade_date != config.trade_date:
            return AuctionMonitorSymbolResult(
                symbol=instrument.symbol,
                name=instrument.name,
                status="date_mismatch",
                auction_trade_date=actual_trade_date,
                previous_trade_date=latest_daily_date_before(daily_bars, actual_trade_date),
                minutes_count=len(minutes),
                error=f"expected {config.trade_date.isoformat()}, got {actual_trade_date.isoformat()}",
            )

        previous_bar = latest_daily_bar_before(daily_bars, actual_trade_date)
        average_volume = average_daily_volume_before(
            daily_bars,
            actual_trade_date,
            window=config.average_volume_window,
        )
        minutes = [replace(minute, provider=config.auction_provider) for minute in minutes]
        profile = build_auction_profile(
            instrument.symbol,
            minutes,
            previous_close=previous_bar.close if previous_bar is not None else None,
            average_daily_volume=average_volume,
        )
        if profile is None:
            return AuctionMonitorSymbolResult(
                symbol=instrument.symbol,
                name=instrument.name,
                status="no_data",
                auction_trade_date=actual_trade_date,
                previous_trade_date=previous_bar.trade_date if previous_bar is not None else None,
                minutes_count=len(minutes),
                error="cannot_build_profile",
            )

        profile = replace(profile, provider=config.auction_provider)
        minute_rows = (
            store.upsert_auction_minutes(minutes) if config.cache_auction_minutes else 0
        )
        profile_rows = store.upsert_auction_profiles([profile])
        daily_rows = (
            store.upsert_daily_bars(
                [
                    bar
                    for bar in daily_context.fetched_bars
                    if bar.trade_date < actual_trade_date
                ]
            )
            if config.cache_daily_bars
            else 0
        )
        return AuctionMonitorSymbolResult(
            symbol=instrument.symbol,
            name=instrument.name,
            status="success",
            auction_trade_date=profile.trade_date,
            previous_trade_date=previous_bar.trade_date if previous_bar is not None else None,
            minutes_count=len(minutes),
            daily_bars_written=daily_rows,
            auction_minutes_written=minute_rows,
            auction_profile_written=profile_rows,
            previous_open=previous_bar.open if previous_bar is not None else None,
            previous_close=previous_bar.close if previous_bar is not None else None,
            strength_score=profile.strength_score,
            gap_pct=profile.gap_pct,
        )
    except Exception as exc:  # noqa: BLE001 - one symbol should not stop a monitor round.
        return AuctionMonitorSymbolResult(
            symbol=instrument.symbol,
            name=instrument.name,
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
        )


def daily_context_for_symbol(
    provider: DataProvider,
    store: SQLiteStore,
    symbol: str,
    config: AuctionMonitorConfig,
    sleep: Callable[[float], None],
) -> DailyContext:
    end = (config.trade_date - timedelta(days=1)) if config.trade_date else date.today()
    start = end - timedelta(days=config.daily_lookback_days)
    cached = store.get_daily_bars(symbol, start=start, end=end, adjust=config.daily_adjust)
    if cached and not needs_daily_context_refresh(cached, end, config):
        return DailyContext(bars=tuple(cached), fetched_bars=())
    fetch_start = next_daily_fetch_start(cached, start)
    fetched = fetch_daily_with_retries(
        provider,
        symbol,
        fetch_start,
        end,
        config=config,
        sleep=sleep,
    )
    merged = merge_daily_bars(cached, fetched)
    return DailyContext(bars=tuple(merged or cached), fetched_bars=tuple(fetched))


def resolve_monitor_instruments(
    provider: DataProvider,
    store: SQLiteStore,
    config: AuctionMonitorConfig,
) -> list[Instrument]:
    if config.symbols:
        names = {instrument.symbol: instrument.name for instrument in store.list_instruments()}
        instruments = [
            Instrument(symbol=symbol, name=names.get(symbol, symbol), market="A股")
            for symbol in config.symbols
        ]
    else:
        instruments = store.list_instruments()
        if not instruments:
            instruments = list(provider.list_instruments())
            store.upsert_instruments(instruments)
    if config.limit is not None:
        return instruments[: config.limit]
    return instruments


def fetch_daily_with_retries(
    provider: DataProvider,
    symbol: str,
    start: date,
    end: date,
    *,
    config: AuctionMonitorConfig,
    sleep: Callable[[float], None],
) -> list[DailyBar]:
    if start > end:
        return []
    last_error: Exception | None = None
    for attempt in range(1, config.retries + 1):
        try:
            bars = list(
                provider.fetch_daily_bars(
                    symbol,
                    start,
                    end,
                    adjust=config.daily_adjust,
                )
            )
            if config.request_sleep_seconds > 0:
                sleep(config.request_sleep_seconds)
            return bars
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            sleep_after_attempt(attempt, config, sleep)
    if last_error is not None:
        raise last_error
    return []


def fetch_minutes_with_retries(
    provider: DataProvider,
    symbol: str,
    *,
    config: AuctionMonitorConfig,
    sleep: Callable[[float], None],
) -> list[AuctionMinuteBar]:
    last_error: Exception | None = None
    for attempt in range(1, config.retries + 1):
        try:
            minutes = list(
                provider.fetch_pre_market_minutes(
                    symbol,
                    start_time=config.start_time,
                    end_time=config.end_time,
                )
            )
            if config.request_sleep_seconds > 0:
                sleep(config.request_sleep_seconds)
            return sorted(minutes, key=lambda item: item.trade_time)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            sleep_after_attempt(attempt, config, sleep)
    if last_error is not None:
        raise last_error
    return []


def sleep_after_attempt(
    attempt: int,
    config: AuctionMonitorConfig,
    sleep: Callable[[float], None],
) -> None:
    if config.request_sleep_seconds > 0:
        sleep(config.request_sleep_seconds)
    if attempt < config.retries and config.retry_sleep_seconds > 0:
        sleep(config.retry_sleep_seconds * attempt)


def latest_daily_bar_before(bars: Sequence[DailyBar], trade_date: date) -> DailyBar | None:
    candidates = [bar for bar in bars if bar.trade_date < trade_date]
    return max(candidates, key=lambda item: item.trade_date) if candidates else None


def latest_daily_date_before(bars: Sequence[DailyBar], trade_date: date | None) -> date | None:
    if trade_date is None:
        return bars[-1].trade_date if bars else None
    latest = latest_daily_bar_before(bars, trade_date)
    return latest.trade_date if latest is not None else None


def average_daily_volume_before(
    bars: Sequence[DailyBar],
    trade_date: date,
    *,
    window: int,
) -> float | None:
    candidates = [
        bar
        for bar in sorted(bars, key=lambda item: item.trade_date)
        if bar.trade_date < trade_date
    ]
    if not candidates:
        return None
    volumes = [bar.volume for bar in candidates[-window:] if bar.volume > 0]
    if not volumes:
        return None
    return sum(volumes) / len(volumes)


def needs_daily_context_refresh(
    cached: Sequence[DailyBar],
    end: date,
    config: AuctionMonitorConfig,
) -> bool:
    latest = max((bar.trade_date for bar in cached), default=None)
    if latest is not None and latest >= end:
        return False
    return True


def next_daily_fetch_start(cached: Sequence[DailyBar], fallback: date) -> date:
    latest = max((bar.trade_date for bar in cached), default=None)
    return latest + timedelta(days=1) if latest is not None else fallback


def merge_daily_bars(
    cached: Sequence[DailyBar],
    fetched: Sequence[DailyBar],
) -> list[DailyBar]:
    by_key = {(bar.symbol, bar.trade_date, bar.adjust): bar for bar in cached}
    for bar in fetched:
        by_key[(bar.symbol, bar.trade_date, bar.adjust)] = bar
    return sorted(by_key.values(), key=lambda item: item.trade_date)


def validate_monitor_config(config: AuctionMonitorConfig) -> None:
    if config.limit is not None and config.limit <= 0:
        raise ValueError("limit must be a positive integer")
    if config.retries <= 0:
        raise ValueError("retries must be a positive integer")
    if config.retry_sleep_seconds < 0:
        raise ValueError("retry_sleep_seconds must be non-negative")
    if config.request_sleep_seconds < 0:
        raise ValueError("request_sleep_seconds must be non-negative")
    if config.average_volume_window <= 0:
        raise ValueError("average_volume_window must be a positive integer")
    if config.daily_lookback_days <= 0:
        raise ValueError("daily_lookback_days must be a positive integer")
