"""Feature engineering for A-share call-auction data."""

from __future__ import annotations

from collections.abc import Sequence

from gupiao.data.schema import AuctionMinuteBar, AuctionProfile


def build_auction_profile(
    symbol: str,
    minutes: Sequence[AuctionMinuteBar],
    *,
    previous_close: float | None = None,
    average_daily_volume: float | None = None,
    bid_ask_imbalance: float | None = None,
) -> AuctionProfile | None:
    if not minutes:
        return None
    ordered = sorted(minutes, key=lambda item: item.trade_time)
    latest = ordered[-1]
    high = max(item.high for item in ordered)
    low = min(item.low for item in ordered)
    volume = sum(item.volume for item in ordered)
    amount_values = [item.amount for item in ordered if item.amount is not None]
    amount = sum(amount_values) if amount_values else None
    gap_pct = (latest.close / previous_close) - 1 if previous_close and previous_close > 0 else None
    range_pct = (high / low) - 1 if low > 0 else None
    volume_ratio = (
        volume / average_daily_volume
        if average_daily_volume is not None and average_daily_volume > 0
        else None
    )
    return AuctionProfile(
        symbol=symbol,
        trade_date=latest.trade_date,
        auction_time=latest.trade_time,
        indicative_price=latest.close,
        open=ordered[0].open,
        high=high,
        low=low,
        volume=volume,
        amount=amount,
        latest_price=latest.latest_price,
        previous_close=previous_close,
        gap_pct=gap_pct,
        range_pct=range_pct,
        volume_ratio_to_daily=volume_ratio,
        bid_ask_imbalance=bid_ask_imbalance,
        strength_score=score_auction_profile(
            gap_pct=gap_pct,
            range_pct=range_pct,
            volume_ratio_to_daily=volume_ratio,
            bid_ask_imbalance=bid_ask_imbalance,
        ),
        provider=latest.provider,
        fetched_at=latest.fetched_at,
    )


def score_auction_profile(
    *,
    gap_pct: float | None,
    range_pct: float | None,
    volume_ratio_to_daily: float | None,
    bid_ask_imbalance: float | None = None,
) -> float:
    score = 50.0
    if gap_pct is not None:
        score += clamp(gap_pct * 500, -25.0, 25.0)
    if volume_ratio_to_daily is not None:
        score += clamp(volume_ratio_to_daily * 100, 0.0, 25.0)
    if range_pct is not None:
        score -= clamp(range_pct * 200, 0.0, 15.0)
    if bid_ask_imbalance is not None:
        score += clamp(bid_ask_imbalance * 12, -12.0, 12.0)
    return round(clamp(score, 0.0, 100.0), 2)


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))
