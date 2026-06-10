"""Trade plan objects that separate screening from execution timing."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from gupiao.data import AuctionProfile, DailyBar
from gupiao.indicators import atr
from gupiao.strategies.screening import ScreeningCandidate

MORNING_AUCTION = "morning_auction"
AFTER_CLOSE = "after_close"
RESEARCH_CLOSE = "research_close"

SHORT_TERM = "short_term"
MID_SHORT_TERM = "mid_short_term"
MID_TERM = "mid_term"

DECISION_TIMES = (MORNING_AUCTION, AFTER_CLOSE, RESEARCH_CLOSE)
HORIZONS = (SHORT_TERM, MID_SHORT_TERM, MID_TERM)


@dataclass(frozen=True)
class HorizonProfile:
    id: str
    name: str
    description: str
    default_strategy_id: str
    max_holding_bars: int
    stop_atr_multiple: float
    fallback_stop_pct: float
    take_profit_r_multiple: float
    auction_importance: str


@dataclass(frozen=True)
class TradePlan:
    symbol: str
    horizon: str
    horizon_name: str
    decision_time: str
    strategy: str
    signal_date: date
    latest_data_date: date | None
    entry_date: date | None
    entry_timing: str
    entry_price_source: str
    reference_entry_price: float | None
    stop_loss: float | None
    take_profit: float | None
    reduce_price: float | None
    max_holding_bars: int
    confidence: float
    buy_conditions: tuple[str, ...]
    avoid_conditions: tuple[str, ...]
    sell_rules: tuple[str, ...]
    risk_notes: tuple[str, ...]


HORIZON_PROFILES = {
    SHORT_TERM: HorizonProfile(
        id=SHORT_TERM,
        name="短线",
        description="竞价强度优先，默认 1-3 个交易日内验证。",
        default_strategy_id="auction_open_breakout_short",
        max_holding_bars=3,
        stop_atr_multiple=1.2,
        fallback_stop_pct=0.035,
        take_profit_r_multiple=1.5,
        auction_importance="high",
    ),
    MID_SHORT_TERM: HorizonProfile(
        id=MID_SHORT_TERM,
        name="中短线",
        description="趋势与量价结构优先，竞价作为确认项，默认 3-10 个交易日。",
        default_strategy_id="volume_breakout_swing",
        max_holding_bars=10,
        stop_atr_multiple=1.8,
        fallback_stop_pct=0.06,
        take_profit_r_multiple=2.0,
        auction_importance="medium",
    ),
    MID_TERM: HorizonProfile(
        id=MID_TERM,
        name="中线",
        description="趋势质量和波动稳定性优先，竞价只做弱参考，默认 10-30 个交易日。",
        default_strategy_id="trend_quality_mid",
        max_holding_bars=30,
        stop_atr_multiple=2.4,
        fallback_stop_pct=0.09,
        take_profit_r_multiple=2.5,
        auction_importance="low",
    ),
}


def normalize_horizon(horizon: str | None) -> str:
    if not horizon:
        return SHORT_TERM
    aliases = {
        "short": SHORT_TERM,
        "day": SHORT_TERM,
        "swing": MID_SHORT_TERM,
        "mid_short": MID_SHORT_TERM,
        "medium_short": MID_SHORT_TERM,
        "mid": MID_TERM,
        "medium": MID_TERM,
    }
    normalized = aliases.get(horizon, horizon)
    if normalized not in HORIZON_PROFILES:
        choices = ", ".join(HORIZON_PROFILES)
        raise ValueError(f"unknown horizon '{horizon}', expected one of: {choices}")
    return normalized


def horizon_profile(horizon: str | None) -> HorizonProfile:
    return HORIZON_PROFILES[normalize_horizon(horizon)]


def default_strategy_for_horizon(horizon: str | None) -> str:
    return horizon_profile(horizon).default_strategy_id


def build_trade_plan(
    candidate: ScreeningCandidate,
    bars: Sequence[DailyBar],
    *,
    decision_time: str = MORNING_AUCTION,
    horizon: str = SHORT_TERM,
    signal_date: date | None = None,
    auction_profile: AuctionProfile | None = None,
    reference_entry_price: float | None = None,
    entry_price_source: str | None = None,
) -> TradePlan:
    if decision_time not in DECISION_TIMES:
        choices = ", ".join(DECISION_TIMES)
        raise ValueError(f"unknown decision_time '{decision_time}', expected one of: {choices}")
    profile = horizon_profile(horizon)
    ordered = sorted(bars, key=lambda item: item.trade_date)
    latest = ordered[-1] if ordered else None
    effective_signal_date = signal_date or candidate.trade_date

    entry_price = reference_entry_price
    price_source = entry_price_source
    if entry_price is None and decision_time == MORNING_AUCTION and auction_profile is not None:
        entry_price = auction_profile.indicative_price
        price_source = "auction_indicative_price"
    if entry_price is None and latest is not None:
        entry_price = latest.close
        price_source = "latest_close"
    if price_source is None:
        price_source = "unavailable"

    stop_loss = take_profit = reduce_price = None
    if entry_price is not None and entry_price > 0:
        scale_mismatch = price_scale_mismatch(price_source, latest)
        stop_distance = stop_distance_for_bars(
            ordered,
            entry_price=entry_price,
            stop_atr_multiple=profile.stop_atr_multiple,
            fallback_stop_pct=profile.fallback_stop_pct,
            use_atr=not scale_mismatch,
        )
        stop_loss = round(entry_price - stop_distance, 4)
        take_profit = round(entry_price + stop_distance * profile.take_profit_r_multiple, 4)
        reduce_price = round(entry_price + stop_distance, 4)
    else:
        scale_mismatch = False

    return TradePlan(
        symbol=candidate.symbol,
        horizon=profile.id,
        horizon_name=profile.name,
        decision_time=decision_time,
        strategy=candidate.strategy,
        signal_date=effective_signal_date,
        latest_data_date=latest.trade_date if latest is not None else None,
        entry_date=entry_date_for_decision(decision_time, effective_signal_date),
        entry_timing=entry_timing_for_decision(decision_time),
        entry_price_source=price_source,
        reference_entry_price=round(entry_price, 4) if entry_price is not None else None,
        stop_loss=stop_loss,
        take_profit=take_profit,
        reduce_price=reduce_price,
        max_holding_bars=profile.max_holding_bars,
        confidence=round(max(0.0, min(candidate.score, 100.0)), 2),
        buy_conditions=buy_conditions(decision_time, profile, auction_profile),
        avoid_conditions=avoid_conditions(decision_time, profile, auction_profile),
        sell_rules=sell_rules(profile),
        risk_notes=risk_notes(
            decision_time,
            profile,
            price_scale_mismatch=scale_mismatch,
            bars_adjust=latest.adjust if latest is not None else None,
        ),
    )


def stop_distance_for_bars(
    bars: Sequence[DailyBar],
    *,
    entry_price: float,
    stop_atr_multiple: float,
    fallback_stop_pct: float,
    use_atr: bool = True,
) -> float:
    latest_atr = latest_available(atr(bars, window=14)) if bars and use_atr else None
    if latest_atr is not None and latest_atr > 0:
        return max(latest_atr * stop_atr_multiple, entry_price * fallback_stop_pct * 0.5)
    return entry_price * fallback_stop_pct


def price_scale_mismatch(entry_price_source: str, latest_bar: DailyBar | None) -> bool:
    if latest_bar is None:
        return False
    if entry_price_source != "auction_indicative_price":
        return False
    return latest_bar.adjust not in {None, "", "raw"}


def latest_available(values: Sequence[float | None]) -> float | None:
    for value in reversed(values):
        if value is not None:
            return value
    return None


def entry_date_for_decision(decision_time: str, signal_date: date) -> date | None:
    if decision_time == MORNING_AUCTION:
        return signal_date
    return None


def entry_timing_for_decision(decision_time: str) -> str:
    if decision_time == MORNING_AUCTION:
        return "09:25 竞价结束后完成筛选，09:30 附近按开盘价/可成交价执行"
    if decision_time == AFTER_CLOSE:
        return "收盘后完成筛选，下一交易日开盘附近执行"
    return "研究模式，按信号收盘价模拟执行"


def buy_conditions(
    decision_time: str,
    profile: HorizonProfile,
    auction_profile: AuctionProfile | None,
) -> tuple[str, ...]:
    conditions = [
        f"策略周期为{profile.name}，计划持有不超过 {profile.max_holding_bars} 个交易日",
        "候选分数和形态条件仍然有效",
    ]
    if decision_time == MORNING_AUCTION:
        conditions.append("只使用前一交易日及以前的日K，加上当日 09:25 竞价画像")
        if auction_profile is not None:
            conditions.append(
                f"竞价强度 {auction_profile.strength_score:.2f}，参考价 "
                f"{auction_profile.indicative_price:.4f}"
            )
    return tuple(conditions)


def avoid_conditions(
    decision_time: str,
    profile: HorizonProfile,
    auction_profile: AuctionProfile | None,
) -> tuple[str, ...]:
    conditions = [
        "开盘一字涨停、停牌或流动性异常时不追",
        "开盘后快速跌破参考价且不能收回时放弃",
    ]
    if decision_time == MORNING_AUCTION:
        conditions.append("竞价结束后到开盘前出现明显撤单或价格跳变时放弃")
    if auction_profile is not None and auction_profile.gap_pct is not None:
        conditions.append(f"竞价缺口当前为 {auction_profile.gap_pct:.2%}，高开过大时降低仓位或放弃")
    if profile.id == MID_TERM:
        conditions.append("中线策略不因单日竞价强弱重仓追入")
    return tuple(conditions)


def sell_rules(profile: HorizonProfile) -> tuple[str, ...]:
    return (
        "跌破止损价后按 A 股 T+1 约束执行退出",
        "触及止盈价可分批止盈，触及减仓价可先降风险",
        f"超过 {profile.max_holding_bars} 个交易日仍未兑现则时间止损/止盈",
    )


def risk_notes(
    decision_time: str,
    profile: HorizonProfile,
    *,
    price_scale_mismatch: bool = False,
    bars_adjust: str | None = None,
) -> tuple[str, ...]:
    notes = [
        "该计划是研究和决策辅助，不构成投资建议",
        "回测成交价会加入手续费和滑点，实盘成交可能不同",
    ]
    if decision_time == MORNING_AUCTION:
        notes.append("早盘计划生成时不知道当日收盘价，禁止使用当日日K收盘信息")
    if price_scale_mismatch:
        notes.append(
            f"竞价参考价是未复权口径，日K为 {bars_adjust} 口径，止损止盈已改用百分比兜底"
        )
    if profile.auction_importance == "low":
        notes.append("中线策略以趋势质量为主，竞价只作为弱确认信号")
    return tuple(notes)
