from __future__ import annotations

from unittest import TestCase

from gupiao.factors import FactorInput, rank_factors


class FactorScoringTest(TestCase):
    def test_rank_factors_orders_by_weighted_score(self) -> None:
        scores = rank_factors(
            [
                FactorInput(
                    symbol="000001",
                    factors={
                        "value": 0.8,
                        "quality": 0.9,
                        "growth": 0.7,
                        "momentum": 0.8,
                        "volatility": 0.2,
                        "liquidity": 0.9,
                    },
                ),
                FactorInput(
                    symbol="000002",
                    factors={
                        "value": 0.2,
                        "quality": 0.4,
                        "growth": 0.3,
                        "momentum": 0.2,
                        "volatility": 0.9,
                        "liquidity": 0.3,
                    },
                ),
            ]
        )

        self.assertEqual([score.symbol for score in scores], ["000001", "000002"])
        self.assertGreater(scores[0].total_score, scores[1].total_score)

    def test_rank_factors_handles_equal_values(self) -> None:
        scores = rank_factors(
            [
                FactorInput(symbol="000001", factors={"quality": 1.0}),
                FactorInput(symbol="000002", factors={"quality": 1.0}),
            ],
            weights={"quality": 1.0},
            higher_is_better={"quality": True},
        )

        self.assertEqual(scores[0].total_score, 50.0)
        self.assertEqual(scores[1].total_score, 50.0)
