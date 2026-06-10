"""MVP stock screening strategies."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from gupiao.data import DailyBar, has_errors, validate_daily_bars
from gupiao.indicators import closes, sma


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

    def evaluate(self, symbol: str, bars: Sequence[DailyBar]) -> ScreeningCandidate | None:
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

        reasons = (
            f"close above MA stack: close={latest.close:.4f}, "
            f"ma{self.short_window}={short_ma:.4f}, "
            f"ma{self.medium_window}={medium_ma:.4f}, ma{self.long_window}={long_ma:.4f}",
            f"close breakout above prior {self.breakout_window}-bar high {previous_high:.4f}",
            f"volume ratio {volume_ratio:.2f} >= {self.min_volume_ratio:.2f}",
        )
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
        return ScreeningCandidate(
            symbol=symbol,
            trade_date=latest.trade_date,
            strategy=self.name,
            score=score,
            reasons=reasons,
            metrics=metrics,
        )

    @property
    def required_bars(self) -> int:
        return max(self.long_window, self.volume_window + 1, self.breakout_window + 1)


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
