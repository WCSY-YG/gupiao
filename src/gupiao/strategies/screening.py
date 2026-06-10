"""Stock screening strategies."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from statistics import pstdev
from typing import Protocol

from gupiao.data import AuctionProfile, DailyBar, has_errors, validate_daily_bars
from gupiao.indicators import closes, sma


class ScreeningStrategy(Protocol):
    name: str

    def evaluate(
        self,
        symbol: str,
        bars: Sequence[DailyBar],
        *,
        auction_profile: AuctionProfile | None = None,
    ) -> "ScreeningCandidate | None":
        """Evaluate one symbol from daily bars."""

    @property
    def required_bars(self) -> int:
        """Minimum number of daily bars needed by the strategy."""


@dataclass(frozen=True)
class ScreeningCandidate:
    symbol: str
    trade_date: date
    strategy: str
    score: float
    reasons: tuple[str, ...]
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class MovingAverageVolumeBreakoutStrategy:
    name: str = "ma_volume_breakout"
    short_window: int = 5
    medium_window: int = 20
    long_window: int = 60
    volume_window: int = 20
    breakout_window: int = 20
    min_volume_ratio: float = 1.5
    min_auction_score: float | None = None
    auction_score_weight: float = 0.15
    require_auction_profile: bool = False

    def evaluate(
        self,
        symbol: str,
        bars: Sequence[DailyBar],
        *,
        auction_profile: AuctionProfile | None = None,
    ) -> ScreeningCandidate | None:
        if len(bars) < self.required_bars:
            return None

        quality_issues = validate_daily_bars(bars)
        if has_errors(quality_issues):
            return None

        ordered_bars = sorted(bars, key=lambda item: item.trade_date)
        close_values = closes(ordered_bars)
        short_ma = sma(close_values, self.short_window)[-1]
        medium_ma = sma(close_values, self.medium_window)[-1]
        long_ma = sma(close_values, self.long_window)[-1]
        latest = ordered_bars[-1]

        if short_ma is None or medium_ma is None or long_ma is None:
            return None

        previous_bars = ordered_bars[-self.breakout_window - 1 : -1]
        previous_high = max(bar.high for bar in previous_bars)
        previous_volumes = [bar.volume for bar in ordered_bars[-self.volume_window - 1 : -1]]
        average_volume = sum(previous_volumes) / len(previous_volumes)
        volume_ratio = latest.volume / average_volume if average_volume > 0 else 0.0

        trend_ok = latest.close > short_ma > medium_ma > long_ma
        breakout_ok = latest.close > previous_high
        volume_ok = volume_ratio >= self.min_volume_ratio

        if not (trend_ok and breakout_ok and volume_ok):
            return None

        if not auction_gate_allows(
            auction_profile,
            min_auction_score=self.min_auction_score,
            require_auction_profile=self.require_auction_profile,
        ):
            return None

        reasons = [
            f"close above MA stack: close={latest.close:.4f}, "
            f"ma{self.short_window}={short_ma:.4f}, "
            f"ma{self.medium_window}={medium_ma:.4f}, ma{self.long_window}={long_ma:.4f}",
            f"close breakout above prior {self.breakout_window}-bar high {previous_high:.4f}",
            f"volume ratio {volume_ratio:.2f} >= {self.min_volume_ratio:.2f}",
        ]
        metrics = {
            "close": latest.close,
            f"ma{self.short_window}": short_ma,
            f"ma{self.medium_window}": medium_ma,
            f"ma{self.long_window}": long_ma,
            "previous_high": previous_high,
            "volume_ratio": volume_ratio,
        }
        score = score_candidate(
            close=latest.close,
            short_ma=short_ma,
            medium_ma=medium_ma,
            long_ma=long_ma,
            volume_ratio=volume_ratio,
            min_volume_ratio=self.min_volume_ratio,
        )
        return build_candidate(
            symbol=symbol,
            trade_date=latest.trade_date,
            strategy=self.name,
            score=score,
            reasons=tuple(reasons),
            metrics=metrics,
            auction_profile=auction_profile,
            auction_score_weight=self.auction_score_weight,
        )

    @property
    def required_bars(self) -> int:
        return max(self.long_window, self.volume_window + 1, self.breakout_window + 1)


@dataclass(frozen=True)
class MomentumPullbackStrategy:
    name: str = "momentum_pullback"
    short_window: int = 5
    medium_window: int = 20
    long_window: int = 60
    volume_window: int = 20
    pullback_window: int = 8
    min_volume_ratio: float = 1.2
    max_pullback_distance: float = 0.04
    min_auction_score: float | None = None
    auction_score_weight: float = 0.15
    require_auction_profile: bool = False

    def evaluate(
        self,
        symbol: str,
        bars: Sequence[DailyBar],
        *,
        auction_profile: AuctionProfile | None = None,
    ) -> ScreeningCandidate | None:
        ordered_bars = prepare_bars(bars, required_bars=self.required_bars)
        if ordered_bars is None:
            return None

        close_values = closes(ordered_bars)
        short_ma = sma(close_values, self.short_window)[-1]
        medium_ma = sma(close_values, self.medium_window)[-1]
        long_ma = sma(close_values, self.long_window)[-1]
        latest = ordered_bars[-1]
        previous = ordered_bars[-2]
        if short_ma is None or medium_ma is None or long_ma is None:
            return None

        recent_bars = ordered_bars[-self.pullback_window - 1 : -1]
        recent_low = min(bar.low for bar in recent_bars)
        previous_volumes = [bar.volume for bar in ordered_bars[-self.volume_window - 1 : -1]]
        average_volume = sum(previous_volumes) / len(previous_volumes)
        volume_ratio = latest.volume / average_volume if average_volume > 0 else 0.0
        distance_to_medium = abs(recent_low / medium_ma - 1) if medium_ma > 0 else 1.0

        trend_ok = latest.close > short_ma >= medium_ma > long_ma
        pullback_ok = recent_low <= medium_ma * (1 + self.max_pullback_distance)
        recovery_ok = latest.close > previous.close and latest.close > latest.open
        volume_ok = volume_ratio >= self.min_volume_ratio
        if not (trend_ok and pullback_ok and recovery_ok and volume_ok):
            return None
        if not auction_gate_allows(
            auction_profile,
            min_auction_score=self.min_auction_score,
            require_auction_profile=self.require_auction_profile,
        ):
            return None

        trend_spread = ((short_ma / medium_ma) - 1) + ((medium_ma / long_ma) - 1)
        recovery_strength = (latest.close / previous.close) - 1 if previous.close > 0 else 0.0
        pullback_score = max(0.0, 1 - (distance_to_medium / self.max_pullback_distance))
        score = 58 + (trend_spread * 90) + (recovery_strength * 150)
        score += pullback_score * 12
        score += min(volume_ratio / self.min_volume_ratio, 2.5) * 6
        metrics = {
            "close": latest.close,
            f"ma{self.short_window}": short_ma,
            f"ma{self.medium_window}": medium_ma,
            f"ma{self.long_window}": long_ma,
            "recent_low": recent_low,
            "distance_to_medium_ma": distance_to_medium,
            "volume_ratio": volume_ratio,
        }
        reasons = (
            f"trend remains positive: close={latest.close:.4f}, "
            f"ma{self.short_window}={short_ma:.4f}, ma{self.medium_window}={medium_ma:.4f}",
            f"recent pullback stayed near ma{self.medium_window}: "
            f"low={recent_low:.4f}, distance={distance_to_medium:.2%}",
            f"recovery day with volume ratio {volume_ratio:.2f} >= {self.min_volume_ratio:.2f}",
        )
        return build_candidate(
            symbol=symbol,
            trade_date=latest.trade_date,
            strategy=self.name,
            score=round(max(0.0, min(score, 100.0)), 2),
            reasons=reasons,
            metrics=metrics,
            auction_profile=auction_profile,
            auction_score_weight=self.auction_score_weight,
        )

    @property
    def required_bars(self) -> int:
        return max(self.long_window, self.volume_window + 1, self.pullback_window + 1)


@dataclass(frozen=True)
class LowVolatilityBreakoutStrategy:
    name: str = "low_volatility_breakout"
    short_window: int = 5
    medium_window: int = 20
    long_window: int = 60
    volume_window: int = 20
    breakout_window: int = 20
    min_volume_ratio: float = 1.4
    max_compression_pct: float = 0.08
    min_auction_score: float | None = None
    auction_score_weight: float = 0.15
    require_auction_profile: bool = False

    def evaluate(
        self,
        symbol: str,
        bars: Sequence[DailyBar],
        *,
        auction_profile: AuctionProfile | None = None,
    ) -> ScreeningCandidate | None:
        ordered_bars = prepare_bars(bars, required_bars=self.required_bars)
        if ordered_bars is None:
            return None

        close_values = closes(ordered_bars)
        medium_ma = sma(close_values, self.medium_window)[-1]
        long_ma = sma(close_values, self.long_window)[-1]
        latest = ordered_bars[-1]
        if medium_ma is None or long_ma is None:
            return None

        previous_bars = ordered_bars[-self.breakout_window - 1 : -1]
        previous_closes = [bar.close for bar in previous_bars]
        previous_high = max(bar.high for bar in previous_bars)
        average_close = sum(previous_closes) / len(previous_closes)
        compression_pct = pstdev(previous_closes) / average_close if average_close > 0 else 1.0
        previous_volumes = [bar.volume for bar in ordered_bars[-self.volume_window - 1 : -1]]
        average_volume = sum(previous_volumes) / len(previous_volumes)
        volume_ratio = latest.volume / average_volume if average_volume > 0 else 0.0

        trend_ok = latest.close > medium_ma > long_ma
        compression_ok = compression_pct <= self.max_compression_pct
        breakout_ok = latest.close > previous_high
        volume_ok = volume_ratio >= self.min_volume_ratio
        if not (trend_ok and compression_ok and breakout_ok and volume_ok):
            return None
        if not auction_gate_allows(
            auction_profile,
            min_auction_score=self.min_auction_score,
            require_auction_profile=self.require_auction_profile,
        ):
            return None

        breakout_strength = (latest.close / previous_high) - 1 if previous_high > 0 else 0.0
        compression_score = max(0.0, 1 - (compression_pct / self.max_compression_pct))
        trend_spread = (medium_ma / long_ma) - 1
        score = 58 + (breakout_strength * 160) + (compression_score * 16)
        score += (trend_spread * 100) + (min(volume_ratio / self.min_volume_ratio, 2.5) * 7)
        metrics = {
            "close": latest.close,
            f"ma{self.medium_window}": medium_ma,
            f"ma{self.long_window}": long_ma,
            "previous_high": previous_high,
            "compression_pct": compression_pct,
            "volume_ratio": volume_ratio,
        }
        reasons = (
            f"low volatility base: compression={compression_pct:.2%} <= "
            f"{self.max_compression_pct:.2%}",
            f"close breakout above prior {self.breakout_window}-bar high {previous_high:.4f}",
            f"volume ratio {volume_ratio:.2f} >= {self.min_volume_ratio:.2f}",
        )
        return build_candidate(
            symbol=symbol,
            trade_date=latest.trade_date,
            strategy=self.name,
            score=round(max(0.0, min(score, 100.0)), 2),
            reasons=reasons,
            metrics=metrics,
            auction_profile=auction_profile,
            auction_score_weight=self.auction_score_weight,
        )

    @property
    def required_bars(self) -> int:
        return max(self.long_window, self.volume_window + 1, self.breakout_window + 1)


@dataclass(frozen=True)
class AuctionOpenBreakoutShortStrategy:
    name: str = "auction_open_breakout_short"
    short_window: int = 5
    medium_window: int = 20
    long_window: int = 60
    volume_window: int = 20
    min_auction_score: float | None = 55.0
    max_gap_pct: float = 0.07
    min_gap_pct: float = -0.02
    min_auction_volume_ratio: float = 0.001
    auction_score_weight: float = 0.35

    def evaluate(
        self,
        symbol: str,
        bars: Sequence[DailyBar],
        *,
        auction_profile: AuctionProfile | None = None,
    ) -> ScreeningCandidate | None:
        ordered_bars = prepare_bars(bars, required_bars=self.required_bars)
        if ordered_bars is None or auction_profile is None:
            return None

        if self.min_auction_score is not None and auction_profile.strength_score < self.min_auction_score:
            return None

        close_values = closes(ordered_bars)
        short_ma = sma(close_values, self.short_window)[-1]
        medium_ma = sma(close_values, self.medium_window)[-1]
        long_ma = sma(close_values, self.long_window)[-1]
        if short_ma is None or medium_ma is None or long_ma is None:
            return None

        latest = ordered_bars[-1]
        previous = ordered_bars[-2]
        recent_high = max(bar.high for bar in ordered_bars[-self.medium_window :])
        gap_pct = auction_profile.gap_pct
        auction_volume_ratio = auction_profile.volume_ratio_to_daily

        trend_ok = latest.close > short_ma >= medium_ma > long_ma
        prior_strength_ok = latest.close >= previous.close and latest.close >= recent_high * 0.96
        gap_ok = gap_pct is None or self.min_gap_pct <= gap_pct <= self.max_gap_pct
        volume_ok = (
            auction_volume_ratio is None
            or auction_volume_ratio >= self.min_auction_volume_ratio
        )
        if not (trend_ok and prior_strength_ok and gap_ok and volume_ok):
            return None

        trend_spread = ((short_ma / medium_ma) - 1) + ((medium_ma / long_ma) - 1)
        gap_score = 0.0 if gap_pct is None else max(0.0, min(gap_pct / self.max_gap_pct, 1.0))
        volume_score = (
            0.5
            if auction_volume_ratio is None
            else max(0.0, min(auction_volume_ratio / max(self.min_auction_volume_ratio, 0.001), 3.0))
            / 3.0
        )
        score = 58 + trend_spread * 90 + gap_score * 10 + volume_score * 10
        metrics = {
            "previous_close": latest.close,
            f"ma{self.short_window}": short_ma,
            f"ma{self.medium_window}": medium_ma,
            f"ma{self.long_window}": long_ma,
            "recent_high": recent_high,
            "auction_strength_score": auction_profile.strength_score,
            "auction_indicative_price": auction_profile.indicative_price,
            "auction_volume": auction_profile.volume,
        }
        if gap_pct is not None:
            metrics["auction_gap_pct"] = gap_pct
        if auction_volume_ratio is not None:
            metrics["auction_volume_ratio_to_daily"] = auction_volume_ratio
        if auction_profile.bid_ask_imbalance is not None:
            metrics["auction_bid_ask_imbalance"] = auction_profile.bid_ask_imbalance

        reasons = (
            f"pre-open decision uses bars through {latest.trade_date.isoformat()} "
            f"and auction on {auction_profile.trade_date.isoformat()}",
            f"trend stack holds: close={latest.close:.4f}, "
            f"ma{self.short_window}={short_ma:.4f}, ma{self.medium_window}={medium_ma:.4f}",
            f"auction strength {auction_profile.strength_score:.2f} supports open entry",
        )
        return build_candidate(
            symbol=symbol,
            trade_date=auction_profile.trade_date,
            strategy=self.name,
            score=round(max(0.0, min(score, 100.0)), 2),
            reasons=reasons,
            metrics=metrics,
            auction_profile=None,
            auction_score_weight=0.0,
        )

    @property
    def required_bars(self) -> int:
        return max(self.long_window, self.medium_window, self.volume_window)


@dataclass(frozen=True)
class AuctionGapReversalShortStrategy:
    name: str = "auction_gap_reversal_short"
    short_window: int = 5
    medium_window: int = 20
    long_window: int = 60
    min_auction_score: float | None = 60.0
    min_gap_pct: float = -0.035
    max_gap_pct: float = 0.035
    auction_score_weight: float = 0.4

    def evaluate(
        self,
        symbol: str,
        bars: Sequence[DailyBar],
        *,
        auction_profile: AuctionProfile | None = None,
    ) -> ScreeningCandidate | None:
        ordered_bars = prepare_bars(bars, required_bars=self.required_bars)
        if ordered_bars is None or auction_profile is None:
            return None
        if self.min_auction_score is not None and auction_profile.strength_score < self.min_auction_score:
            return None

        close_values = closes(ordered_bars)
        short_ma = sma(close_values, self.short_window)[-1]
        medium_ma = sma(close_values, self.medium_window)[-1]
        long_ma = sma(close_values, self.long_window)[-1]
        if short_ma is None or medium_ma is None or long_ma is None:
            return None

        latest = ordered_bars[-1]
        previous = ordered_bars[-2]
        gap_pct = auction_profile.gap_pct
        gap_ok = gap_pct is None or self.min_gap_pct <= gap_pct <= self.max_gap_pct
        trend_ok = latest.close > medium_ma > long_ma
        reversal_ok = latest.close >= previous.close or latest.close >= short_ma
        if not (gap_ok and trend_ok and reversal_ok):
            return None

        recovery_strength = (latest.close / previous.close) - 1 if previous.close > 0 else 0.0
        score = 56 + recovery_strength * 160 + (auction_profile.strength_score * 0.25)
        metrics = {
            "previous_close": latest.close,
            f"ma{self.medium_window}": medium_ma,
            f"ma{self.long_window}": long_ma,
            "auction_strength_score": auction_profile.strength_score,
            "auction_indicative_price": auction_profile.indicative_price,
        }
        if gap_pct is not None:
            metrics["auction_gap_pct"] = gap_pct
        reasons = (
            "mild auction gap avoids chasing an excessive open",
            f"trend remains above ma{self.medium_window} and ma{self.long_window}",
            f"auction strength {auction_profile.strength_score:.2f} confirms early interest",
        )
        return build_candidate(
            symbol=symbol,
            trade_date=auction_profile.trade_date,
            strategy=self.name,
            score=round(max(0.0, min(score, 100.0)), 2),
            reasons=reasons,
            metrics=metrics,
            auction_profile=None,
            auction_score_weight=0.0,
        )

    @property
    def required_bars(self) -> int:
        return max(self.long_window, self.medium_window, self.short_window)


@dataclass(frozen=True)
class TrendQualityMidStrategy:
    name: str = "trend_quality_mid"
    medium_window: int = 20
    long_window: int = 60
    quality_window: int = 60
    max_volatility_pct: float = 0.18
    min_trend_spread: float = 0.015
    auction_score_weight: float = 0.05
    min_auction_score: float | None = None

    def evaluate(
        self,
        symbol: str,
        bars: Sequence[DailyBar],
        *,
        auction_profile: AuctionProfile | None = None,
    ) -> ScreeningCandidate | None:
        ordered_bars = prepare_bars(bars, required_bars=self.required_bars)
        if ordered_bars is None:
            return None

        close_values = closes(ordered_bars)
        medium_ma = sma(close_values, self.medium_window)[-1]
        long_ma = sma(close_values, self.long_window)[-1]
        if medium_ma is None or long_ma is None:
            return None

        latest = ordered_bars[-1]
        quality_closes = close_values[-self.quality_window :]
        average_close = sum(quality_closes) / len(quality_closes)
        volatility_pct = pstdev(quality_closes) / average_close if average_close > 0 else 1.0
        trend_spread = (medium_ma / long_ma) - 1 if long_ma > 0 else 0.0
        trend_ok = latest.close > medium_ma > long_ma
        quality_ok = volatility_pct <= self.max_volatility_pct and trend_spread >= self.min_trend_spread
        if not (trend_ok and quality_ok):
            return None
        if not auction_gate_allows(
            auction_profile,
            min_auction_score=self.min_auction_score,
            require_auction_profile=False,
        ):
            return None

        score = 58 + trend_spread * 220 + max(0.0, 1 - volatility_pct / self.max_volatility_pct) * 20
        metrics = {
            "close": latest.close,
            f"ma{self.medium_window}": medium_ma,
            f"ma{self.long_window}": long_ma,
            "trend_spread": trend_spread,
            "volatility_pct": volatility_pct,
        }
        reasons = (
            f"medium-term trend quality: close={latest.close:.4f}, "
            f"ma{self.medium_window}={medium_ma:.4f}, ma{self.long_window}={long_ma:.4f}",
            f"volatility {volatility_pct:.2%} <= {self.max_volatility_pct:.2%}",
            "auction data is used only as a weak confirmation for mid-term decisions",
        )
        return build_candidate(
            symbol=symbol,
            trade_date=latest.trade_date,
            strategy=self.name,
            score=round(max(0.0, min(score, 100.0)), 2),
            reasons=reasons,
            metrics=metrics,
            auction_profile=auction_profile,
            auction_score_weight=self.auction_score_weight,
        )

    @property
    def required_bars(self) -> int:
        return max(self.long_window, self.quality_window)


@dataclass(frozen=True)
class StrategySpec:
    id: str
    name: str
    category: str
    description: str
    horizon: str = "mid_short_term"
    decision_time: str = "after_close"
    entry_timing: str = "next_open"
    requires_auction_profile: bool = False


STRATEGY_SPECS = (
    StrategySpec(
        id="auction_open_breakout_short",
        name="短线竞价开盘突破",
        category="auction_open",
        horizon="short_term",
        decision_time="morning_auction",
        entry_timing="same_day_open",
        description="uses previous daily bars plus same-day auction strength to prepare an open entry.",
        requires_auction_profile=True,
    ),
    StrategySpec(
        id="auction_gap_reversal_short",
        name="短线竞价温和缺口修复",
        category="auction_reversal",
        horizon="short_term",
        decision_time="morning_auction",
        entry_timing="same_day_open",
        description="looks for a mild auction gap with strong early interest and intact trend.",
        requires_auction_profile=True,
    ),
    StrategySpec(
        id="volume_breakout_swing",
        name="中短线放量突破",
        category="trend_breakout",
        horizon="mid_short_term",
        decision_time="morning_auction",
        entry_timing="same_day_open",
        description="uses prior-day breakout structure; auction is a confirmation rather than a hard gate.",
    ),
    StrategySpec(
        id="pullback_recovery_swing",
        name="中短线回踩修复",
        category="trend_pullback",
        horizon="mid_short_term",
        decision_time="morning_auction",
        entry_timing="same_day_open",
        description="uses prior-day pullback recovery; auction can improve ranking and explanation.",
    ),
    StrategySpec(
        id="trend_quality_mid",
        name="中线趋势质量",
        category="trend_quality",
        horizon="mid_term",
        decision_time="morning_auction",
        entry_timing="same_day_open_or_plan",
        description="focuses on trend quality and volatility stability; auction has low weight.",
    ),
    StrategySpec(
        id="ma_volume_breakout",
        name="均线多头放量突破",
        category="trend_breakout",
        description="close above MA stack, breaks recent high, and volume expands.",
        horizon="mid_short_term",
    ),
    StrategySpec(
        id="momentum_pullback",
        name="趋势回踩修复",
        category="trend_pullback",
        description="uptrend remains intact, recent pullback stays near medium MA, then recovers.",
        horizon="mid_short_term",
    ),
    StrategySpec(
        id="low_volatility_breakout",
        name="低波动突破",
        category="volatility_breakout",
        description="recent closes compress, then price breaks out with volume expansion.",
        horizon="mid_short_term",
    ),
    StrategySpec(
        id="auction_assisted_breakout",
        name="竞价辅助突破",
        category="auction_assisted",
        description="MA breakout with a same-day auction profile used for ranking/explanation.",
        horizon="short_term",
        requires_auction_profile=True,
    ),
)


def available_strategy_specs() -> tuple[StrategySpec, ...]:
    return STRATEGY_SPECS


def get_strategy_spec(strategy_id: str) -> StrategySpec:
    normalized = normalize_strategy_id(strategy_id)
    for spec in STRATEGY_SPECS:
        if spec.id == normalized:
            return spec
    choices = ", ".join(spec.id for spec in STRATEGY_SPECS)
    raise ValueError(f"unknown strategy '{strategy_id}', expected one of: {choices}")


def build_screening_strategy(
    strategy_id: str = "ma_volume_breakout",
    *,
    short_window: int = 5,
    medium_window: int = 20,
    long_window: int = 60,
    volume_window: int = 20,
    breakout_window: int = 20,
    min_volume_ratio: float = 1.5,
    min_auction_score: float | None = None,
    auction_score_weight: float = 0.15,
) -> ScreeningStrategy:
    normalized = normalize_strategy_id(strategy_id)
    get_strategy_spec(normalized)
    if normalized == "auction_open_breakout_short":
        return AuctionOpenBreakoutShortStrategy(
            short_window=short_window,
            medium_window=medium_window,
            long_window=long_window,
            volume_window=volume_window,
            min_auction_score=55.0 if min_auction_score is None else min_auction_score,
            auction_score_weight=auction_score_weight,
        )
    if normalized == "auction_gap_reversal_short":
        return AuctionGapReversalShortStrategy(
            short_window=short_window,
            medium_window=medium_window,
            long_window=long_window,
            min_auction_score=60.0 if min_auction_score is None else min_auction_score,
            auction_score_weight=auction_score_weight,
        )
    if normalized == "trend_quality_mid":
        return TrendQualityMidStrategy(
            medium_window=medium_window,
            long_window=long_window,
            min_auction_score=min_auction_score,
            auction_score_weight=min(auction_score_weight, 0.08),
        )
    if normalized == "volume_breakout_swing":
        return MovingAverageVolumeBreakoutStrategy(
            name=normalized,
            short_window=short_window,
            medium_window=medium_window,
            long_window=long_window,
            volume_window=volume_window,
            breakout_window=breakout_window,
            min_volume_ratio=min_volume_ratio,
            min_auction_score=min_auction_score,
            auction_score_weight=auction_score_weight,
        )
    if normalized == "pullback_recovery_swing":
        return MomentumPullbackStrategy(
            name=normalized,
            short_window=short_window,
            medium_window=medium_window,
            long_window=long_window,
            volume_window=volume_window,
            min_volume_ratio=min_volume_ratio,
            min_auction_score=min_auction_score,
            auction_score_weight=auction_score_weight,
        )
    if normalized == "momentum_pullback":
        return MomentumPullbackStrategy(
            short_window=short_window,
            medium_window=medium_window,
            long_window=long_window,
            volume_window=volume_window,
            min_volume_ratio=min_volume_ratio,
            min_auction_score=min_auction_score,
            auction_score_weight=auction_score_weight,
        )
    if normalized == "low_volatility_breakout":
        return LowVolatilityBreakoutStrategy(
            short_window=short_window,
            medium_window=medium_window,
            long_window=long_window,
            volume_window=volume_window,
            breakout_window=breakout_window,
            min_volume_ratio=min_volume_ratio,
            min_auction_score=min_auction_score,
            auction_score_weight=auction_score_weight,
        )
    return MovingAverageVolumeBreakoutStrategy(
        name=normalized,
        short_window=short_window,
        medium_window=medium_window,
        long_window=long_window,
        volume_window=volume_window,
        breakout_window=breakout_window,
        min_volume_ratio=min_volume_ratio,
        min_auction_score=min_auction_score,
        auction_score_weight=auction_score_weight,
        require_auction_profile=normalized == "auction_assisted_breakout",
    )


def normalize_strategy_id(strategy_id: str | None) -> str:
    if not strategy_id:
        return "ma_volume_breakout"
    aliases = {
        "breakout": "ma_volume_breakout",
        "mvp": "ma_volume_breakout",
        "trend_breakout": "ma_volume_breakout",
        "short": "auction_open_breakout_short",
        "short_term": "auction_open_breakout_short",
        "swing": "volume_breakout_swing",
        "mid_short": "volume_breakout_swing",
        "mid_short_term": "volume_breakout_swing",
        "mid": "trend_quality_mid",
        "mid_term": "trend_quality_mid",
    }
    return aliases.get(strategy_id, strategy_id)


def prepare_bars(bars: Sequence[DailyBar], *, required_bars: int) -> list[DailyBar] | None:
    if len(bars) < required_bars:
        return None
    quality_issues = validate_daily_bars(bars)
    if has_errors(quality_issues):
        return None
    return sorted(bars, key=lambda item: item.trade_date)


def auction_gate_allows(
    auction_profile: AuctionProfile | None,
    *,
    min_auction_score: float | None,
    require_auction_profile: bool,
) -> bool:
    if require_auction_profile and auction_profile is None:
        return False
    if min_auction_score is None:
        return True
    if auction_profile is None:
        return False
    return auction_profile.strength_score >= min_auction_score


def build_candidate(
    *,
    symbol: str,
    trade_date: date,
    strategy: str,
    score: float,
    reasons: Sequence[str],
    metrics: dict[str, float],
    auction_profile: AuctionProfile | None,
    auction_score_weight: float,
) -> ScreeningCandidate:
    final_reasons = list(reasons)
    final_metrics = dict(metrics)
    final_score = score
    if auction_profile is not None:
        final_reasons.append(
            "auction strength "
            f"{auction_profile.strength_score:.2f}"
            + (
                f", gap={auction_profile.gap_pct:.2%}"
                if auction_profile.gap_pct is not None
                else ""
            )
        )
        final_metrics.update(
            {
                "auction_strength_score": auction_profile.strength_score,
                "auction_indicative_price": auction_profile.indicative_price,
                "auction_volume": auction_profile.volume,
            }
        )
        if auction_profile.gap_pct is not None:
            final_metrics["auction_gap_pct"] = auction_profile.gap_pct
        if auction_profile.volume_ratio_to_daily is not None:
            final_metrics["auction_volume_ratio_to_daily"] = auction_profile.volume_ratio_to_daily
        if auction_profile.bid_ask_imbalance is not None:
            final_metrics["auction_bid_ask_imbalance"] = auction_profile.bid_ask_imbalance
        final_score = score_with_auction(
            base_score=score,
            auction_score=auction_profile.strength_score,
            weight=auction_score_weight,
        )
    return ScreeningCandidate(
        symbol=symbol,
        trade_date=trade_date,
        strategy=strategy,
        score=round(max(0.0, min(final_score, 100.0)), 2),
        reasons=tuple(final_reasons),
        metrics=final_metrics,
    )


def score_candidate(
    *,
    close: float,
    short_ma: float,
    medium_ma: float,
    long_ma: float,
    volume_ratio: float,
    min_volume_ratio: float,
) -> float:
    trend_spread = ((short_ma / medium_ma) - 1) + ((medium_ma / long_ma) - 1)
    breakout_strength = (close / short_ma) - 1
    volume_strength = min(volume_ratio / min_volume_ratio, 3.0) / 3.0
    raw_score = 60 + (trend_spread * 100) + (breakout_strength * 100) + (volume_strength * 20)
    return round(max(0.0, min(raw_score, 100.0)), 2)


def score_with_auction(*, base_score: float, auction_score: float, weight: float) -> float:
    bounded_weight = max(0.0, min(weight, 1.0))
    raw_score = (base_score * (1 - bounded_weight)) + (auction_score * bounded_weight)
    return round(max(0.0, min(raw_score, 100.0)), 2)
