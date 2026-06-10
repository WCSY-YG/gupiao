from __future__ import annotations

from unittest import TestCase

from gupiao.signals import build_breakout_signal, confidence_from_score
from gupiao.strategies import MovingAverageVolumeBreakoutStrategy

from tests.test_screening_strategy import breakout_bars


class TechnicalSignalsTest(TestCase):
    def test_build_breakout_signal_from_candidate(self) -> None:
        bars = breakout_bars()
        candidate = MovingAverageVolumeBreakoutStrategy(
            short_window=3,
            medium_window=5,
            long_window=8,
            volume_window=5,
            breakout_window=5,
            min_volume_ratio=1.5,
        ).evaluate("000001", bars)
        self.assertIsNotNone(candidate)

        signal = build_breakout_signal(candidate, bars, atr_window=3)

        self.assertIsNotNone(signal)
        self.assertEqual(signal.symbol, "000001")
        self.assertEqual(signal.direction, "buy")
        self.assertGreater(signal.entry_price, signal.stop_loss)
        self.assertGreater(signal.take_profit, signal.entry_price)
        self.assertGreater(signal.add_price, signal.entry_price)
        self.assertGreater(signal.reduce_price, signal.add_price)
        self.assertGreaterEqual(signal.risk_reward, 2.0)
        self.assertIn("stop_loss", signal.invalidation)

    def test_build_breakout_signal_rejects_bad_bars(self) -> None:
        bars = breakout_bars()
        candidate = MovingAverageVolumeBreakoutStrategy(
            short_window=3,
            medium_window=5,
            long_window=8,
            volume_window=5,
            breakout_window=5,
        ).evaluate("000001", bars)
        bars.append(bars[-1])

        self.assertIsNone(build_breakout_signal(candidate, bars, atr_window=3))

    def test_confidence_from_score_is_bounded(self) -> None:
        self.assertEqual(confidence_from_score(-1), 0.0)
        self.assertEqual(confidence_from_score(101), 100.0)
        self.assertEqual(confidence_from_score(88.888), 88.89)
