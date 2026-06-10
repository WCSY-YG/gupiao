"""Lightweight ML-scoring and portfolio-allocation experiments."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

from gupiao.data import AuctionProfile, DailyBar


@dataclass(frozen=True)
class ResearchSample:
    symbol: str
    features: Mapping[str, float]
    target_return: float


@dataclass(frozen=True)
class LinearBaselineModel:
    feature_weights: dict[str, float] = field(default_factory=dict)
    intercept: float = 0.0


@dataclass(frozen=True)
class Prediction:
    symbol: str
    score: float
    features: dict[str, float] = field(default_factory=dict)


def split_train_validation(
    samples: Sequence[ResearchSample],
    *,
    train_ratio: float = 0.7,
) -> tuple[list[ResearchSample], list[ResearchSample]]:
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1")
    split_index = max(1, min(len(samples) - 1, int(len(samples) * train_ratio)))
    return list(samples[:split_index]), list(samples[split_index:])


def train_linear_baseline(samples: Sequence[ResearchSample]) -> LinearBaselineModel:
    if not samples:
        return LinearBaselineModel()
    feature_names = sorted({name for sample in samples for name in sample.features})
    target_mean = sum(sample.target_return for sample in samples) / len(samples)
    weights = {}
    for feature in feature_names:
        values = [sample.features.get(feature, 0.0) for sample in samples]
        value_mean = sum(values) / len(values)
        variance = sum((value - value_mean) ** 2 for value in values)
        if variance == 0:
            weights[feature] = 0.0
            continue
        covariance = sum(
            (value - value_mean) * (sample.target_return - target_mean)
            for value, sample in zip(values, samples, strict=True)
        )
        weights[feature] = covariance / variance
    intercept = target_mean - sum(
        weights[feature] * feature_mean(samples, feature) for feature in feature_names
    )
    return LinearBaselineModel(feature_weights=weights, intercept=intercept)


def predict_linear_baseline(
    model: LinearBaselineModel,
    samples: Sequence[ResearchSample],
) -> list[Prediction]:
    predictions = []
    for sample in samples:
        score = model.intercept + sum(
            model.feature_weights.get(feature, 0.0) * value
            for feature, value in sample.features.items()
        )
        predictions.append(
            Prediction(
                symbol=sample.symbol,
                score=round(score, 6),
                features=dict(sample.features),
            )
        )
    return sorted(predictions, key=lambda item: item.score, reverse=True)


def allocate_by_score(
    predictions: Sequence[Prediction],
    *,
    top_n: int = 10,
    max_weight: float = 0.2,
) -> dict[str, float]:
    if top_n <= 0:
        raise ValueError("top_n must be positive")
    if not 0 < max_weight <= 1:
        raise ValueError("max_weight must be in (0, 1]")
    selected = [item for item in predictions if item.score > 0][:top_n]
    if not selected:
        return {}
    score_sum = sum(item.score for item in selected)
    if score_sum <= 0:
        equal_weight = round(1 / len(selected), 6)
        return {item.symbol: equal_weight for item in selected}
    raw_weights = {item.symbol: item.score / score_sum for item in selected}
    capped = {symbol: min(weight, max_weight) for symbol, weight in raw_weights.items()}
    capped_sum = sum(capped.values())
    if capped_sum == 0:
        return {}
    return {symbol: round(weight / capped_sum, 6) for symbol, weight in capped.items()}


def build_auction_research_samples(
    symbol: str,
    bars: Sequence[DailyBar],
    auction_profiles: Mapping[date, AuctionProfile],
    *,
    lookahead_bars: int = 1,
) -> list[ResearchSample]:
    if lookahead_bars <= 0:
        raise ValueError("lookahead_bars must be positive")
    ordered_bars = sorted(bars, key=lambda item: item.trade_date)
    samples: list[ResearchSample] = []
    for index, bar in enumerate(ordered_bars):
        if index == 0:
            continue
        future_index = index + lookahead_bars
        if future_index >= len(ordered_bars):
            break
        profile = auction_profiles.get(bar.trade_date)
        if profile is None:
            continue
        previous_bar = ordered_bars[index - 1]
        future_bar = ordered_bars[future_index]
        target_return = (future_bar.close / bar.open) - 1 if bar.open > 0 else 0.0
        samples.append(
            ResearchSample(
                symbol=symbol,
                features={
                    "auction_strength_score": profile.strength_score,
                    "auction_gap_pct": profile.gap_pct or 0.0,
                    "auction_range_pct": profile.range_pct or 0.0,
                    "auction_volume_ratio_to_daily": profile.volume_ratio_to_daily or 0.0,
                    "previous_daily_return": (
                        (previous_bar.close / previous_bar.open) - 1
                        if previous_bar.open > 0
                        else 0.0
                    ),
                    "previous_range_pct": (
                        (previous_bar.high - previous_bar.low) / previous_bar.close
                        if previous_bar.close > 0
                        else 0.0
                    ),
                    "previous_volume": previous_bar.volume,
                },
                target_return=target_return,
            )
        )
    return samples


def feature_mean(samples: Sequence[ResearchSample], feature: str) -> float:
    return sum(sample.features.get(feature, 0.0) for sample in samples) / len(samples)
