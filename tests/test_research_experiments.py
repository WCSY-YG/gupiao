from __future__ import annotations

from unittest import TestCase

from gupiao.auction import build_auction_profile
from gupiao.research import (
    ResearchSample,
    allocate_by_score,
    build_auction_research_samples,
    predict_linear_baseline,
    split_train_validation,
    train_linear_baseline,
)

from tests.test_auction_features import auction_minutes
from tests.test_screening_strategy import breakout_bars


class ResearchExperimentsTest(TestCase):
    def test_split_train_validation(self) -> None:
        samples = sample_data()

        train, validation = split_train_validation(samples, train_ratio=0.6)

        self.assertEqual(len(train), 3)
        self.assertEqual(len(validation), 2)

    def test_linear_baseline_predicts_and_sorts(self) -> None:
        samples = sample_data()
        model = train_linear_baseline(samples[:4])

        predictions = predict_linear_baseline(model, samples[4:])

        self.assertEqual(predictions[0].symbol, "000005")
        self.assertGreater(predictions[0].score, 0)

    def test_allocate_by_score_caps_and_normalizes(self) -> None:
        predictions = predict_linear_baseline(train_linear_baseline(sample_data()), sample_data())

        weights = allocate_by_score(predictions, top_n=3, max_weight=0.5)

        self.assertLessEqual(max(weights.values()), 1.0)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=5)
        self.assertLessEqual(len(weights), 3)

    def test_build_auction_research_samples(self) -> None:
        bars = breakout_bars()
        profile = build_auction_profile(
            "000001",
            auction_minutes(),
            previous_close=10.0,
            average_daily_volume=10_000.0,
        )
        assert profile is not None

        samples = build_auction_research_samples(
            "000001",
            bars,
            {bars[-2].trade_date: profile},
            lookahead_bars=1,
        )

        self.assertEqual(len(samples), 1)
        self.assertIn("auction_strength_score", samples[0].features)
        self.assertIn("previous_daily_return", samples[0].features)
        self.assertNotIn("daily_close_to_open", samples[0].features)
        self.assertNotEqual(samples[0].target_return, 0.0)

    def test_invalid_settings_raise(self) -> None:
        with self.assertRaises(ValueError):
            split_train_validation(sample_data(), train_ratio=1.0)
        with self.assertRaises(ValueError):
            allocate_by_score([], top_n=0)


def sample_data() -> list[ResearchSample]:
    return [
        ResearchSample("000001", {"momentum": 0.1, "quality": 0.2}, 0.01),
        ResearchSample("000002", {"momentum": 0.2, "quality": 0.3}, 0.02),
        ResearchSample("000003", {"momentum": 0.3, "quality": 0.4}, 0.03),
        ResearchSample("000004", {"momentum": 0.4, "quality": 0.5}, 0.04),
        ResearchSample("000005", {"momentum": 0.5, "quality": 0.6}, 0.05),
    ]
