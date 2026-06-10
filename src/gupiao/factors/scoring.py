"""Generic multi-factor ranking utilities."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FactorInput:
    symbol: str
    factors: Mapping[str, float]


@dataclass(frozen=True)
class FactorScore:
    symbol: str
    total_score: float
    factor_scores: dict[str, float] = field(default_factory=dict)
    raw_factors: dict[str, float] = field(default_factory=dict)


def rank_factors(
    rows: Sequence[FactorInput],
    *,
    weights: Mapping[str, float] | None = None,
    higher_is_better: Mapping[str, bool] | None = None,
) -> list[FactorScore]:
    if not rows:
        return []
    weights = dict(weights or default_factor_weights())
    higher_is_better = dict(higher_is_better or default_factor_directions())
    normalized = normalize_factors(rows, list(weights), higher_is_better)
    scores = []
    total_weight = sum(abs(weight) for weight in weights.values()) or 1.0

    for row in rows:
        factor_scores = {
            factor: normalized[row.symbol].get(factor, 0.0) * weight
            for factor, weight in weights.items()
        }
        total_score = sum(factor_scores.values()) / total_weight * 100
        scores.append(
            FactorScore(
                symbol=row.symbol,
                total_score=round(total_score, 2),
                factor_scores={key: round(value * 100, 2) for key, value in factor_scores.items()},
                raw_factors=dict(row.factors),
            )
        )

    return sorted(scores, key=lambda item: item.total_score, reverse=True)


def normalize_factors(
    rows: Sequence[FactorInput],
    factors: Sequence[str],
    higher_is_better: Mapping[str, bool],
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {row.symbol: {} for row in rows}
    for factor in factors:
        values = [row.factors[factor] for row in rows if factor in row.factors]
        if not values:
            continue
        low = min(values)
        high = max(values)
        span = high - low
        for row in rows:
            if factor not in row.factors:
                continue
            if span == 0:
                score = 0.5
            else:
                score = (row.factors[factor] - low) / span
            if not higher_is_better.get(factor, True):
                score = 1 - score
            result[row.symbol][factor] = score
    return result


def default_factor_weights() -> dict[str, float]:
    return {
        "value": 1.0,
        "quality": 1.0,
        "growth": 1.0,
        "momentum": 1.0,
        "volatility": 0.8,
        "liquidity": 0.8,
    }


def default_factor_directions() -> dict[str, bool]:
    return {
        "value": True,
        "quality": True,
        "growth": True,
        "momentum": True,
        "volatility": False,
        "liquidity": True,
    }
