"""Technical buy/sell signal explanations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

from gupiao.data import DailyBar, has_errors, validate_daily_bars
from gupiao.indicators import atr
from gupiao.strategies import ScreeningCandidate

SignalDirection = Literal["buy", "sell", "reduce", "add", "hold", "avoid"]


@dataclass(frozen=True)
class SignalPlan:
    symbol: str
    trade_date: date
    direction: SignalDirection
    confidence: float
    entry_price: float
    add_price: float
    reduce_price: float
    stop_loss: float
    take_profit: float
    invalidation: str
    reasons: tuple[str, ...]
    risk_reward: float


def build_breakout_signal(
    candidate: ScreeningCandidate,
    bars: Sequence[DailyBar],
    *,
    atr_window: int = 14,
    stop_atr_multiple: float = 2.0,
    take_profit_r_multiple: float = 2.0,
    fallback_stop_pct: float = 0.06,
) -> SignalPlan | None:
    if not bars:
        return None
    quality_issues = validate_daily_bars(bars)
    if has_errors(quality_issues):
        return None

    ordered_bars = sorted(bars, key=lambda item: item.trade_date)
    latest = ordered_bars[-1]
    latest_atr = latest_available(atr(ordered_bars, window=atr_window))
    if latest_atr is None or latest_atr <= 0:
        stop_distance = latest.close * fallback_stop_pct
        stop_reason = f"fallback {fallback_stop_pct:.0%} stop because ATR is unavailable"
    else:
        stop_distance = latest_atr * stop_atr_multiple
        stop_reason = f"{stop_atr_multiple:.1f} ATR stop, ATR={latest_atr:.4f}"

    entry_price = latest.close
    stop_loss = round(entry_price - stop_distance, 4)
    risk = entry_price - stop_loss
    take_profit = round(entry_price + (risk * take_profit_r_multiple), 4)
    add_price = round(entry_price + (risk * 0.5), 4)
    reduce_price = round(entry_price + risk, 4)
    confidence = confidence_from_score(candidate.score)
    risk_reward = round((take_profit - entry_price) / risk, 2) if risk > 0 else 0.0

    reasons = (
        f"candidate from {candidate.strategy}, score={candidate.score:.2f}",
        *candidate.reasons,
        stop_reason,
    )
    invalidation = (
        f"signal fails if close falls below stop_loss {stop_loss:.4f} "
        "or breaks back under the breakout area"
    )
    return SignalPlan(
        symbol=candidate.symbol,
        trade_date=latest.trade_date,
        direction="buy",
        confidence=confidence,
        entry_price=round(entry_price, 4),
        add_price=add_price,
        reduce_price=reduce_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        invalidation=invalidation,
        reasons=reasons,
        risk_reward=risk_reward,
    )


def confidence_from_score(score: float) -> float:
    return round(max(0.0, min(score, 100.0)), 2)


def latest_available(values: Sequence[float | None]) -> float | None:
    for value in reversed(values):
        if value is not None:
            return value
    return None
