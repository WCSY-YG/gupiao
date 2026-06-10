"""Refresh local market daily cache to the latest available trade date."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from gupiao.data.providers import DataProvider
from gupiao.data.schema import DailyBar, Instrument
from gupiao.data.storage import SQLiteStore


@dataclass(frozen=True)
class MarketCacheRefreshConfig:
    db_path: str | Path = "data/cache/market_scan.sqlite"
    adjust: str = "hfq"
    end: date | None = None
    start: date | None = None
    probe_symbol: str = "000001"
    limit: int | None = None
    symbols: tuple[str, ...] = ()
    retries: int = 3
    retry_sleep_seconds: float = 1.0
    request_sleep_seconds: float = 0.0
    dry_run: bool = False


@dataclass(frozen=True)
class MarketCacheRefreshResult:
    db_path: Path
    adjust: str
    cached_start: date | None
    cached_end: date | None
    requested_end: date
    refresh_start: date
    latest_available_date: date | None
    missing_trade_dates: tuple[date, ...]
    missing_trade_days: int
    instrument_count: int
    processed: int
    succeeded: int
    failed: int
    no_data: int
    rows_written: int
    dry_run: bool
    failures: tuple[dict[str, str], ...] = ()


def refresh_market_daily_cache(
    provider: DataProvider,
    *,
    config: MarketCacheRefreshConfig | None = None,
    store: SQLiteStore | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> MarketCacheRefreshResult:
    config = config or MarketCacheRefreshConfig()
    validate_refresh_config(config)
    store = store or SQLiteStore(config.db_path)
    requested_end = config.end or date.today()
    cached_start, cached_end = store.daily_bar_date_range(adjust=config.adjust)
    refresh_start = config.start or next_day(cached_end) or requested_end
    instruments = resolve_refresh_instruments(provider, store, config)
    probe_symbol = config.probe_symbol or (instruments[0].symbol if instruments else "")
    probe_bars = fetch_bars_with_retries(
        provider,
        probe_symbol,
        refresh_start,
        requested_end,
        adjust=config.adjust,
        retries=config.retries,
        retry_sleep_seconds=config.retry_sleep_seconds,
        request_sleep_seconds=config.request_sleep_seconds,
        sleep=sleep,
    ) if probe_symbol else []
    missing_trade_dates = tuple(sorted({bar.trade_date for bar in probe_bars}))
    latest_available_date = missing_trade_dates[-1] if missing_trade_dates else cached_end

    if config.dry_run or not missing_trade_dates:
        return MarketCacheRefreshResult(
            db_path=Path(config.db_path),
            adjust=config.adjust,
            cached_start=cached_start,
            cached_end=cached_end,
            requested_end=requested_end,
            refresh_start=refresh_start,
            latest_available_date=latest_available_date,
            missing_trade_dates=missing_trade_dates,
            missing_trade_days=len(missing_trade_dates),
            instrument_count=len(instruments),
            processed=0,
            succeeded=0,
            failed=0,
            no_data=0,
            rows_written=0,
            dry_run=config.dry_run,
        )

    processed = 0
    succeeded = 0
    failed = 0
    no_data = 0
    rows_written = 0
    failures: list[dict[str, str]] = []
    refresh_end = latest_available_date or requested_end
    for instrument in instruments:
        processed += 1
        try:
            bars = fetch_bars_with_retries(
                provider,
                instrument.symbol,
                refresh_start,
                refresh_end,
                adjust=config.adjust,
                retries=config.retries,
                retry_sleep_seconds=config.retry_sleep_seconds,
                request_sleep_seconds=config.request_sleep_seconds,
                sleep=sleep,
            )
            bars = [bar for bar in bars if bar.trade_date in missing_trade_dates]
            if not bars:
                no_data += 1
                continue
            rows_written += store.upsert_daily_bars(bars)
            succeeded += 1
        except Exception as exc:  # noqa: BLE001 - one symbol should not stop cache refresh.
            failed += 1
            failures.append(
                {
                    "symbol": instrument.symbol,
                    "name": instrument.name,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    return MarketCacheRefreshResult(
        db_path=Path(config.db_path),
        adjust=config.adjust,
        cached_start=cached_start,
        cached_end=cached_end,
        requested_end=requested_end,
        refresh_start=refresh_start,
        latest_available_date=latest_available_date,
        missing_trade_dates=missing_trade_dates,
        missing_trade_days=len(missing_trade_dates),
        instrument_count=len(instruments),
        processed=processed,
        succeeded=succeeded,
        failed=failed,
        no_data=no_data,
        rows_written=rows_written,
        dry_run=False,
        failures=tuple(failures[:20]),
    )


def resolve_refresh_instruments(
    provider: DataProvider,
    store: SQLiteStore,
    config: MarketCacheRefreshConfig,
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


def fetch_bars_with_retries(
    provider: DataProvider,
    symbol: str,
    start: date,
    end: date,
    *,
    adjust: str,
    retries: int,
    retry_sleep_seconds: float,
    request_sleep_seconds: float,
    sleep: Callable[[float], None],
) -> list[DailyBar]:
    if start > end:
        return []
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            bars = list(provider.fetch_daily_bars(symbol, start, end, adjust=adjust))
            if request_sleep_seconds > 0:
                sleep(request_sleep_seconds)
            return bars
        except Exception as exc:  # noqa: BLE001 - provider adapters expose mixed exceptions.
            last_error = exc
            if request_sleep_seconds > 0:
                sleep(request_sleep_seconds)
            if attempt < retries and retry_sleep_seconds > 0:
                sleep(retry_sleep_seconds * attempt)
    if last_error is not None:
        raise last_error
    return []


def validate_refresh_config(config: MarketCacheRefreshConfig) -> None:
    if config.limit is not None and config.limit <= 0:
        raise ValueError("limit must be a positive integer")
    if config.retries <= 0:
        raise ValueError("retries must be a positive integer")
    if config.retry_sleep_seconds < 0:
        raise ValueError("retry_sleep_seconds must be non-negative")
    if config.request_sleep_seconds < 0:
        raise ValueError("request_sleep_seconds must be non-negative")
    if config.start is not None and config.end is not None and config.start > config.end:
        raise ValueError("start must be before or equal to end")


def next_day(value: date | None) -> date | None:
    if value is None:
        return None
    return value + timedelta(days=1)
