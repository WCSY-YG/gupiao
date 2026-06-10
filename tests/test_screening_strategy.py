from __future__ import annotations

from datetime import date, timedelta
from unittest import TestCase

from gupiao.data import DailyBar
from gupiao.strategies import MovingAverageVolumeBreakoutStrategy, score_candidate


class ScreeningStrategyTest(TestCase):
    def test_ma_volume_breakout_returns_candidate(self) -> None:
        strategy = MovingAverageVolumeBreakoutStrategy(
            short_window=3,
            medium_window=5,
            long_window=8,
            volume_window=5,
            breakout_window=5,
            min_volume_ratio=1.5,
        )

        candidate = strategy.evaluate("000001", breakout_bars())

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.symbol, "000001")
        self.assertEqual(candidate.strategy, "ma_volume_breakout")
        self.assertGreater(candidate.score, 60)
        self.assertEqual(len(candidate.reasons), 3)
        self.assertIn("volume_ratio", candidate.metrics)

    def test_ma_volume_breakout_rejects_low_volume(self) -> None:
        strategy = MovingAverageVolumeBreakoutStrategy(
            short_window=3,
            medium_window=5,
            long_window=8,
            volume_window=5,
            breakout_window=5,
            min_volume_ratio=3.0,
        )

        self.assertIsNone(strategy.evaluate("000001", breakout_bars()))

    def test_ma_volume_breakout_rejects_bad_quality_data(self) -> None:
        strategy = MovingAverageVolumeBreakoutStrategy(
            short_window=3,
            medium_window=5,
            long_window=8,
            volume_window=5,
            breakout_window=5,
        )
        bars = breakout_bars()
        bars.append(bars[-1])

        self.assertIsNone(strategy.evaluate("000001", bars))

    def test_score_candidate_is_bounded(self) -> None:
        self.assertEqual(
            score_candidate(
                close=10.0,
                short_ma=9.0,
                medium_ma=8.0,
                long_ma=7.0,
                volume_ratio=10.0,
                min_volume_ratio=1.5,
            ),
            100.0,
        )


def breakout_bars() -> list[DailyBar]:
    start = date(2026, 6, 1)
    closes = [10.0, 10.1, 10.2, 10.4, 10.6, 10.9, 11.1, 11.3, 11.5, 12.4]
    bars = []
    for index, close in enumerate(closes):
        volume = 1000.0 if index < len(closes) - 1 else 2200.0
        bars.append(
            DailyBar(
                symbol="000001",
                trade_date=start + timedelta(days=index),
                open=close - 0.2,
                high=close + 0.1,
                low=close - 0.4,
                close=close,
                volume=volume,
                amount=volume * close,
                turnover=1.0,
                adjust="hfq",
                provider="test",
            )
        )
    return bars
