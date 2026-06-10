"""Helpers for date-bounded screening from local caches."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from gupiao.data import AuctionProfile, DailyBar, Instrument, SQLiteStore
from gupiao.strategies.screening import ScreeningCandidate, ScreeningStrategy


@dataclass(frozen=True)
class CandidateScreenConfig:
    db_path: str | Path = "data/cache/market_scan.sqlite"
    as_of: date | None = None
    adjust: str = "hfq"
    lookback: int | None = 180
    top: int = 30
    limit: int | None = None
    auction_provider: str | None = None
    symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateScreenRow:
    symbol: str
    name: str
    status: str
    bars_count: int
    latest_trade_date: date | None = None
    candidate: ScreeningCandidate | None = None
    auction_profile: AuctionProfile | None = None
    error: str | None = None


@dataclass(frozen=True)
class CandidateScreenResult:
    config: CandidateScreenConfig
    processed: int
    candidate_count: int
    no_data: int
    failed: int
    candidates: tuple[CandidateScreenRow, ...]
    results: tuple[CandidateScreenRow, ...]


def run_cached_candidate_screen(
    *,
    config: CandidateScreenConfig,
    strategy: ScreeningStrategy,
    store: SQLiteStore | None = None,
) -> CandidateScreenResult:
    if config.top <= 0:
        raise ValueError("top must be a positive integer")
    if config.limit is not None and config.limit <= 0:
        raise ValueError("limit must be a positive integer")
    if config.lookback is not None and config.lookback <= 0:
        raise ValueError("lookback must be a positive integer")

    store = store or SQLiteStore(config.db_path)
    instruments = instruments_for_screen(store, config)
    rows: list[CandidateScreenRow] = []
    for instrument in instruments:
        rows.append(screen_cached_symbol(instrument, store=store, config=config, strategy=strategy))

    ranked = sorted(
        [row for row in rows if row.candidate is not None],
        key=lambda row: (
            row.candidate.score if row.candidate is not None else -1.0,
            row.latest_trade_date or date.min,
            row.symbol,
        ),
        reverse=True,
    )
    return CandidateScreenResult(
        config=config,
        processed=len(rows),
        candidate_count=len(ranked),
        no_data=sum(1 for row in rows if row.status == "no_data"),
        failed=sum(1 for row in rows if row.status == "failed"),
        candidates=tuple(ranked[: config.top]),
        results=tuple(rows),
    )


def screen_cached_symbol(
    instrument: Instrument,
    *,
    store: SQLiteStore,
    config: CandidateScreenConfig,
    strategy: ScreeningStrategy,
) -> CandidateScreenRow:
    try:
        bars = store.get_daily_bars(
            instrument.symbol,
            end=config.as_of,
            adjust=config.adjust,
        )
        bars = bars_up_to(bars, as_of=config.as_of, lookback=config.lookback)
        if not bars:
            return CandidateScreenRow(
                symbol=instrument.symbol,
                name=instrument.name,
                status="no_data",
                bars_count=0,
            )

        auction_profile = latest_matching_auction_profile(
            store,
            symbol=instrument.symbol,
            bars=bars,
            provider=config.auction_provider,
        )
        candidate = strategy.evaluate(
            instrument.symbol,
            bars,
            auction_profile=auction_profile,
        )
        return CandidateScreenRow(
            symbol=instrument.symbol,
            name=instrument.name,
            status="candidate" if candidate is not None else "no_candidate",
            bars_count=len(bars),
            latest_trade_date=bars[-1].trade_date,
            candidate=candidate,
            auction_profile=auction_profile,
        )
    except Exception as exc:  # noqa: BLE001 - one bad symbol should not stop a batch.
        return CandidateScreenRow(
            symbol=instrument.symbol,
            name=instrument.name,
            status="failed",
            bars_count=0,
            error=f"{type(exc).__name__}: {exc}",
        )


def bars_up_to(
    bars: Sequence[DailyBar],
    *,
    as_of: date | None,
    lookback: int | None,
) -> list[DailyBar]:
    ordered = sorted(
        [bar for bar in bars if as_of is None or bar.trade_date <= as_of],
        key=lambda item: item.trade_date,
    )
    if lookback is not None:
        return ordered[-lookback:]
    return ordered


def latest_matching_auction_profile(
    store: SQLiteStore,
    *,
    symbol: str,
    bars: Sequence[DailyBar],
    provider: str | None,
) -> AuctionProfile | None:
    if not provider or not bars:
        return None
    latest_trade_date = bars[-1].trade_date
    profiles = store.get_auction_profiles(
        symbol,
        start=latest_trade_date,
        end=latest_trade_date,
        provider=provider,
    )
    return profiles[-1] if profiles else None


def instruments_for_screen(
    store: SQLiteStore,
    config: CandidateScreenConfig,
) -> list[Instrument]:
    if config.symbols:
        names = {instrument.symbol: instrument.name for instrument in store.list_instruments()}
        return [
            Instrument(symbol=symbol, name=names.get(symbol, symbol), market="A股")
            for symbol in config.symbols[: config.limit]
        ]

    instruments = store.list_instruments()
    if instruments:
        return instruments[: config.limit] if config.limit is not None else instruments

    symbols = store.list_daily_bar_symbols(
        end=config.as_of,
        adjust=config.adjust,
        limit=config.limit,
    )
    return [Instrument(symbol=symbol, name=symbol, market="A股") for symbol in symbols]
