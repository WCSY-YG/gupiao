"""Morning call-auction screening from local caches."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

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

OBJECTIVES = ("balanced", "win_rate", "return")
ALL_OBJECTIVES = "all"
OBJECTIVE_LABELS = {
    "balanced": "稳健综合",
    "win_rate": "高胜率",
    "return": "高收益",
}
DEFAULT_PROFILE_PATH = "configs/morning_strategy_profiles.json"


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
    objective: str = "balanced"
    profile_path: str | Path = DEFAULT_PROFILE_PATH


@dataclass(frozen=True)
class MorningObjectiveProfile:
    objective: str
    horizon: str
    strategy_id: str
    parameters: dict[str, Any]
    backtest: dict[str, Any]
    min_candidate_score: float
    qualified: bool
    metrics: dict[str, float]


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
    objective: str
    processed: int
    candidate_count: int
    no_data: int
    no_auction: int
    failed: int
    candidates: tuple[MorningScreenRow, ...]
    results: tuple[MorningScreenRow, ...]
    objective_groups: tuple["MorningObjectiveGroup", ...] = ()


@dataclass(frozen=True)
class MorningObjectiveGroup:
    objective: str
    label: str
    horizon: str
    strategy_id: str
    min_candidate_score: float | None
    profile_qualified: bool
    profile_metrics: dict[str, float]
    candidate_count: int
    reason: str | None
    candidates: tuple[MorningScreenRow, ...]


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

    store = store or SQLiteStore(config.db_path)
    horizon = normalize_horizon(config.horizon)
    objective = normalize_objective(config.objective)

    if objective == ALL_OBJECTIVES:
        groups: list[MorningObjectiveGroup] = []
        balanced_result: MorningScreenResult | None = None
        for item in OBJECTIVES:
            item_result = run_morning_screen(
                config=MorningScreenConfig(
                    db_path=config.db_path,
                    trade_date=config.trade_date,
                    horizon=horizon,
                    strategy_id=config.strategy_id,
                    adjust=config.adjust,
                    lookback=config.lookback,
                    top=config.top,
                    limit=config.limit,
                    auction_provider=config.auction_provider,
                    symbols=config.symbols,
                    objective=item,
                    profile_path=config.profile_path,
                ),
                strategy=None,
                store=store,
            )
            groups.extend(item_result.objective_groups)
            if item == "balanced":
                balanced_result = item_result
        base = balanced_result or item_result
        return MorningScreenResult(
            config=MorningScreenConfig(
                db_path=config.db_path,
                trade_date=config.trade_date,
                horizon=horizon,
                strategy_id=config.strategy_id,
                adjust=config.adjust,
                lookback=config.lookback,
                top=config.top,
                limit=config.limit,
                auction_provider=config.auction_provider,
                symbols=config.symbols,
                objective=ALL_OBJECTIVES,
                profile_path=config.profile_path,
            ),
            strategy_id=base.strategy_id,
            objective=ALL_OBJECTIVES,
            processed=base.processed,
            candidate_count=sum(group.candidate_count for group in groups),
            no_data=base.no_data,
            no_auction=base.no_auction,
            failed=base.failed,
            candidates=tuple(row for group in groups for row in group.candidates),
            results=base.results,
            objective_groups=tuple(groups),
        )

    profile = load_morning_objective_profile(horizon, objective, config.profile_path)
    strategy_id = config.strategy_id or (
        profile.strategy_id if profile is not None else default_strategy_for_horizon(horizon)
    )
    strategy = strategy or strategy_for_profile(strategy_id, profile)

    instruments = instruments_for_morning_screen(store, config)
    rows = [
        screen_morning_symbol(
            instrument,
            store=store,
            config=config,
            strategy=strategy,
            profile=profile,
        )
        for instrument in instruments
    ]
    eligible_rows = [
        row for row in rows if candidate_passes_profile(row.candidate, profile)
    ]
    ranked = sorted(
        eligible_rows,
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
            objective=objective,
            profile_path=config.profile_path,
        ),
        strategy_id=strategy_id,
        objective=objective,
        processed=len(rows),
        candidate_count=len(ranked),
        no_data=sum(1 for row in rows if row.status == "no_data"),
        no_auction=sum(1 for row in rows if row.status == "no_auction"),
        failed=sum(1 for row in rows if row.status == "failed"),
        candidates=tuple(ranked[: config.top]),
        results=tuple(rows),
        objective_groups=(
            MorningObjectiveGroup(
                objective=objective,
                label=OBJECTIVE_LABELS[objective],
                horizon=horizon,
                strategy_id=strategy_id,
                min_candidate_score=profile.min_candidate_score if profile is not None else None,
                profile_qualified=profile.qualified if profile is not None else True,
                profile_metrics=profile.metrics if profile is not None else {},
                candidate_count=len(ranked[: config.top]),
                reason=objective_group_reason(profile, ranked),
                candidates=tuple(ranked[: config.top]),
            ),
        ),
    )


def screen_morning_symbol(
    instrument: Instrument,
    *,
    store: SQLiteStore,
    config: MorningScreenConfig,
    strategy: ScreeningStrategy,
    profile: MorningObjectiveProfile | None = None,
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
                **trade_plan_overrides(profile),
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


def normalize_objective(objective: str | None) -> str:
    if not objective:
        return "balanced"
    aliases = {
        "稳健": "balanced",
        "balanced": "balanced",
        "胜率": "win_rate",
        "win": "win_rate",
        "winrate": "win_rate",
        "收益": "return",
        "profit": "return",
        "returns": "return",
        "all": ALL_OBJECTIVES,
        "全部": ALL_OBJECTIVES,
    }
    normalized = aliases.get(objective, objective)
    if normalized != ALL_OBJECTIVES and normalized not in OBJECTIVES:
        choices = ", ".join((*OBJECTIVES, ALL_OBJECTIVES))
        raise ValueError(f"unknown objective '{objective}', expected one of: {choices}")
    return normalized


def load_morning_objective_profile(
    horizon: str,
    objective: str,
    profile_path: str | Path = DEFAULT_PROFILE_PATH,
) -> MorningObjectiveProfile | None:
    path = Path(profile_path)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    profile = payload.get("profiles", {}).get(horizon, {}).get(objective)
    if not isinstance(profile, dict):
        return None
    return MorningObjectiveProfile(
        objective=str(profile.get("objective", objective)),
        horizon=str(profile.get("horizon", horizon)),
        strategy_id=str(profile.get("strategy_id", default_strategy_for_horizon(horizon))),
        parameters=dict(profile.get("parameters", {})),
        backtest=dict(profile.get("backtest", {})),
        min_candidate_score=float(profile.get("min_candidate_score", 0.0)),
        qualified=bool(profile.get("qualified", True)),
        metrics={
            key: float(value)
            for key, value in dict(profile.get("metrics", {})).items()
            if isinstance(value, int | float)
        },
    )


def strategy_for_profile(
    strategy_id: str,
    profile: MorningObjectiveProfile | None,
) -> ScreeningStrategy:
    parameters = profile.parameters if profile is not None else {}
    return build_screening_strategy(
        strategy_id,
        short_window=int(parameters.get("short_window", 5)),
        medium_window=int(parameters.get("medium_window", 20)),
        long_window=int(parameters.get("long_window", 60)),
        volume_window=int(parameters.get("volume_window", 20)),
        breakout_window=int(parameters.get("breakout_window", 20)),
        min_volume_ratio=float(parameters.get("min_volume_ratio", 1.5)),
        min_auction_score=optional_float(parameters.get("min_auction_score")),
        auction_score_weight=float(parameters.get("auction_score_weight", 0.15)),
    )


def trade_plan_overrides(profile: MorningObjectiveProfile | None) -> dict[str, Any]:
    if profile is None:
        return {}
    backtest = profile.backtest
    return {
        "max_holding_bars": optional_int(backtest.get("max_holding_bars")),
        "stop_atr_multiple": optional_float(backtest.get("stop_atr_multiple")),
        "fallback_stop_pct": optional_float(backtest.get("fallback_stop_pct")),
        "take_profit_r_multiple": optional_float(backtest.get("take_profit_r_multiple")),
    }


def candidate_passes_profile(
    candidate: ScreeningCandidate | None,
    profile: MorningObjectiveProfile | None,
) -> bool:
    if candidate is None:
        return False
    if profile is None:
        return True
    if not profile.qualified:
        return False
    return candidate.score >= profile.min_candidate_score


def objective_group_reason(
    profile: MorningObjectiveProfile | None,
    ranked: Sequence[MorningScreenRow],
) -> str | None:
    if profile is not None and not profile.qualified:
        return "该目标的优化 profile 未通过最低回测要求，本组不硬选股票"
    if not ranked:
        if profile is None:
            return "没有候选股命中当前策略"
        return f"没有候选股达到最低分 {profile.min_candidate_score:.2f}，本组不硬选股票"
    return None


def optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
