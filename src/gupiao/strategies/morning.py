"""Morning call-auction screening from local caches."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from gupiao.data import AuctionProfile, DailyBar, Instrument, SQLiteStore
from gupiao.strategies.screening import ScreeningCandidate, ScreeningStrategy, build_screening_strategy
from gupiao.strategies.selection import bars_up_to
from gupiao.trade_plan import (
    MORNING_AUCTION,
    SHORT_TERM,
    TradePlan,
    build_trade_plan,
    default_strategy_for_horizon,
    normalize_horizon,
)


@dataclass(frozen=True)
class MorningScreenConfig:
    db_path: str | Path = "data/cache/market_scan.sqlite"
    trade_date: date | None = None
    horizon: str = SHORT_TERM
    strategy_id: str | None = None
    adjust: str = "hfq"
    lookback: int | None = 180
    top: int = 20
    limit: int | None = None
    auction_provider: str = "local_jingjia"
    symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class MorningScreenRow:
    symbol: str
    name: str
    status: str
    daily_bars_count: int
    trade_date: date
    latest_daily_date: date | None = None
    candidate: ScreeningCandidate | None = None
    trade_plan: TradePlan | None = None
    auction_profile: AuctionProfile | None = None
    error: str | None = None


@dataclass(frozen=True)
class MorningScreenResult:
    config: MorningScreenConfig
    strategy_id: str
    processed: int
    candidate_count: int
    no_data: int
    no_auction: int
    failed: int
    candidates: tuple[MorningScreenRow, ...]
    results: tuple[MorningScreenRow, ...]


def run_morning_screen(
    *,
    config: MorningScreenConfig,
    strategy: ScreeningStrategy | None = None,
    store: SQLiteStore | None = None,
) -> MorningScreenResult:
    if config.trade_date is None:
        raise ValueError("trade_date is required for morning screening")
    if config.top <= 0:
        raise ValueError("top must be a positive integer")
    if config.limit is not None and config.limit <= 0:
        raise ValueError("limit must be a positive integer")
    if config.lookback is not None and config.lookback <= 0:
        raise ValueError("lookback must be a positive integer")

    horizon = normalize_horizon(config.horizon)
    strategy_id = config.strategy_id or default_strategy_for_horizon(horizon)
    strategy = strategy or build_screening_strategy(strategy_id)
    store = store or SQLiteStore(config.db_path)

    instruments = instruments_for_morning_screen(store, config)
    rows = [
        screen_morning_symbol(instrument, store=store, config=config, strategy=strategy)
        for instrument in instruments
    ]
    ranked = sorted(
        [row for row in rows if row.candidate is not None],
        key=lambda row: (
            row.candidate.score if row.candidate is not None else -1.0,
            row.symbol,
        ),
        reverse=True,
    )
    return MorningScreenResult(
        config=MorningScreenConfig(
            db_path=config.db_path,
            trade_date=config.trade_date,
            horizon=horizon,
            strategy_id=strategy_id,
            adjust=config.adjust,
            lookback=config.lookback,
            top=config.top,
            limit=config.limit,
            auction_provider=config.auction_provider,
            symbols=config.symbols,
        ),
        strategy_id=strategy_id,
        processed=len(rows),
        candidate_count=len(ranked),
        no_data=sum(1 for row in rows if row.status == "no_data"),
        no_auction=sum(1 for row in rows if row.status == "no_auction"),
        failed=sum(1 for row in rows if row.status == "failed"),
        candidates=tuple(ranked[: config.top]),
        results=tuple(rows),
    )


def screen_morning_symbol(
    instrument: Instrument,
    *,
    store: SQLiteStore,
    config: MorningScreenConfig,
    strategy: ScreeningStrategy,
) -> MorningScreenRow:
    assert config.trade_date is not None
    try:
        auction_profile = auction_profile_for_trade_date(
            store,
            symbol=instrument.symbol,
            trade_date=config.trade_date,
            provider=config.auction_provider,
        )
        if auction_profile is None and horizon_requires_auction(config.horizon):
            return MorningScreenRow(
                symbol=instrument.symbol,
                name=instrument.name,
                status="no_auction",
                daily_bars_count=0,
                trade_date=config.trade_date,
            )

        bars = daily_bars_visible_before_decision(
            store,
            symbol=instrument.symbol,
            trade_date=config.trade_date,
            adjust=config.adjust,
            lookback=config.lookback,
        )
        if not bars:
            return MorningScreenRow(
                symbol=instrument.symbol,
                name=instrument.name,
                status="no_data",
                daily_bars_count=0,
                trade_date=config.trade_date,
                auction_profile=auction_profile,
            )

        candidate = strategy.evaluate(
            instrument.symbol,
            bars,
            auction_profile=auction_profile,
        )
        trade_plan = (
            build_trade_plan(
                candidate,
                bars,
                decision_time=MORNING_AUCTION,
                horizon=config.horizon,
                signal_date=config.trade_date,
                auction_profile=auction_profile,
                reference_entry_price=auction_profile.indicative_price
                if auction_profile is not None
                else None,
                entry_price_source="auction_indicative_price"
                if auction_profile is not None
                else None,
            )
            if candidate is not None
            else None
        )
        return MorningScreenRow(
            symbol=instrument.symbol,
            name=instrument.name,
            status="candidate" if candidate is not None else "no_candidate",
            daily_bars_count=len(bars),
            trade_date=config.trade_date,
            latest_daily_date=bars[-1].trade_date,
            candidate=candidate,
            trade_plan=trade_plan,
            auction_profile=auction_profile,
        )
    except Exception as exc:  # noqa: BLE001 - one bad symbol should not stop the batch.
        return MorningScreenRow(
            symbol=instrument.symbol,
            name=instrument.name,
            status="failed",
            daily_bars_count=0,
            trade_date=config.trade_date,
            error=f"{type(exc).__name__}: {exc}",
        )


def daily_bars_visible_before_decision(
    store: SQLiteStore,
    *,
    symbol: str,
    trade_date: date,
    adjust: str,
    lookback: int | None,
) -> list[DailyBar]:
    bars = store.get_daily_bars(symbol, end=trade_date, adjust=adjust)
    visible = [bar for bar in bars if bar.trade_date < trade_date]
    return bars_up_to(visible, as_of=None, lookback=lookback)


def auction_profile_for_trade_date(
    store: SQLiteStore,
    *,
    symbol: str,
    trade_date: date,
    provider: str,
) -> AuctionProfile | None:
    profiles = store.get_auction_profiles(
        symbol,
        start=trade_date,
        end=trade_date,
        provider=provider,
    )
    return profiles[-1] if profiles else None


def instruments_for_morning_screen(
    store: SQLiteStore,
    config: MorningScreenConfig,
) -> list[Instrument]:
    assert config.trade_date is not None
    names = {instrument.symbol: instrument.name for instrument in store.list_instruments()}
    if config.symbols:
        return [
            Instrument(symbol=symbol, name=names.get(symbol, symbol), market="A股")
            for symbol in config.symbols[: config.limit]
        ]

    if horizon_requires_auction(config.horizon):
        symbols = store.list_auction_profile_symbols(
            start=config.trade_date,
            end=config.trade_date,
            provider=config.auction_provider,
            limit=config.limit,
        )
    else:
        symbols = []
    if not symbols:
        symbols = store.list_daily_bar_symbols(
            end=config.trade_date,
            adjust=config.adjust,
            limit=config.limit,
        )
    return [Instrument(symbol=symbol, name=names.get(symbol, symbol), market="A股") for symbol in symbols]


def horizon_requires_auction(horizon: str | None) -> bool:
    return normalize_horizon(horizon) == SHORT_TERM
