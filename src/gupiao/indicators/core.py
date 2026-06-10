"""Pure Python technical indicators used by MVP strategies."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import sqrt

from gupiao.data.schema import DailyBar


@dataclass(frozen=True)
class MacdPoint:
    dif: float
    dea: float
    histogram: float


@dataclass(frozen=True)
class BollingerBands:
    middle: float
    upper: float
    lower: float


@dataclass(frozen=True)
class KdjPoint:
    k: float
    d: float
    j: float


def sma(values: Sequence[float], window: int) -> list[float | None]:
    ensure_window(window)
    result: list[float | None] = []
    rolling_sum = 0.0
    for index, value in enumerate(values):
        rolling_sum += value
        if index >= window:
            rolling_sum -= values[index - window]
        if index + 1 < window:
            result.append(None)
        else:
            result.append(rolling_sum / window)
    return result


def ema(values: Sequence[float], window: int) -> list[float | None]:
    ensure_window(window)
    if not values:
        return []

    alpha = 2 / (window + 1)
    result: list[float | None] = []
    previous = values[0]
    for value in values:
        previous = (value * alpha) + (previous * (1 - alpha))
        result.append(previous)
    return result


def macd(
    values: Sequence[float],
    *,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> list[MacdPoint | None]:
    ensure_window(fast)
    ensure_window(slow)
    ensure_window(signal)
    if fast >= slow:
        raise ValueError("fast window must be smaller than slow window")

    fast_ema = ema(values, fast)
    slow_ema = ema(values, slow)
    dif_values = [
        fast_value - slow_value
        for fast_value, slow_value in zip(fast_ema, slow_ema, strict=True)
        if fast_value is not None and slow_value is not None
    ]
    dea_values = ema(dif_values, signal)
    points: list[MacdPoint | None] = []
    for dif_value, dea_value in zip(dif_values, dea_values, strict=True):
        if dea_value is None:
            points.append(None)
        else:
            points.append(MacdPoint(dif=dif_value, dea=dea_value, histogram=dif_value - dea_value))
    return points


def rsi(values: Sequence[float], window: int = 14) -> list[float | None]:
    ensure_window(window)
    if len(values) <= window:
        return [None] * len(values)

    result: list[float | None] = [None] * window
    gains = []
    losses = []
    for index in range(1, window + 1):
        change = values[index] - values[index - 1]
        gains.append(max(change, 0.0))
        losses.append(abs(min(change, 0.0)))

    average_gain = sum(gains) / window
    average_loss = sum(losses) / window
    result.append(rsi_value(average_gain, average_loss))

    for index in range(window + 1, len(values)):
        change = values[index] - values[index - 1]
        gain = max(change, 0.0)
        loss = abs(min(change, 0.0))
        average_gain = ((average_gain * (window - 1)) + gain) / window
        average_loss = ((average_loss * (window - 1)) + loss) / window
        result.append(rsi_value(average_gain, average_loss))

    return result


def bollinger_bands(
    values: Sequence[float],
    *,
    window: int = 20,
    multiplier: float = 2.0,
) -> list[BollingerBands | None]:
    ensure_window(window)
    result: list[BollingerBands | None] = []
    for index, _ in enumerate(values):
        if index + 1 < window:
            result.append(None)
            continue
        sample = values[index + 1 - window : index + 1]
        middle = sum(sample) / window
        deviation = sqrt(sum((value - middle) ** 2 for value in sample) / window)
        result.append(
            BollingerBands(
                middle=middle,
                upper=middle + (multiplier * deviation),
                lower=middle - (multiplier * deviation),
            )
        )
    return result


def atr(bars: Sequence[DailyBar], window: int = 14) -> list[float | None]:
    ensure_window(window)
    true_ranges: list[float] = []
    previous_close: float | None = None
    for bar in bars:
        if previous_close is None:
            true_range = bar.high - bar.low
        else:
            true_range = max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        true_ranges.append(true_range)
        previous_close = bar.close
    return sma(true_ranges, window)


def obv(bars: Sequence[DailyBar]) -> list[float]:
    if not bars:
        return []
    result = [0.0]
    for previous, current in zip(bars, bars[1:], strict=False):
        if current.close > previous.close:
            result.append(result[-1] + current.volume)
        elif current.close < previous.close:
            result.append(result[-1] - current.volume)
        else:
            result.append(result[-1])
    return result


def kdj(
    bars: Sequence[DailyBar],
    *,
    window: int = 9,
    k_period: int = 3,
    d_period: int = 3,
) -> list[KdjPoint | None]:
    ensure_window(window)
    ensure_window(k_period)
    ensure_window(d_period)
    result: list[KdjPoint | None] = []
    previous_k = 50.0
    previous_d = 50.0

    for index, bar in enumerate(bars):
        if index + 1 < window:
            result.append(None)
            continue
        sample = bars[index + 1 - window : index + 1]
        lowest_low = min(item.low for item in sample)
        highest_high = max(item.high for item in sample)
        if highest_high == lowest_low:
            rsv = 50.0
        else:
            rsv = ((bar.close - lowest_low) / (highest_high - lowest_low)) * 100
        k_value = ((k_period - 1) * previous_k + rsv) / k_period
        d_value = ((d_period - 1) * previous_d + k_value) / d_period
        j_value = (3 * k_value) - (2 * d_value)
        point = KdjPoint(k=k_value, d=d_value, j=j_value)
        result.append(point)
        previous_k = k_value
        previous_d = d_value

    return result


def closes(bars: Sequence[DailyBar]) -> list[float]:
    return [bar.close for bar in bars]


def ensure_window(window: int) -> None:
    if window <= 0:
        raise ValueError("window must be positive")


def rsi_value(average_gain: float, average_loss: float) -> float:
    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))
