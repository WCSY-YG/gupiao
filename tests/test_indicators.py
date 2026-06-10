from __future__ import annotations

from datetime import date, timedelta
from unittest import TestCase

from gupiao.data import DailyBar
from gupiao.indicators import atr, bollinger_bands, closes, ema, kdj, macd, obv, rsi, sma


class IndicatorsTest(TestCase):
    def test_sma_and_ema(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0]

        self.assertEqual(sma(values, 3), [None, None, 2.0, 3.0])
        self.assertEqual(ema(values, 3), [1.0, 1.5, 2.25, 3.125])

    def test_macd_returns_aligned_points(self) -> None:
        values = [float(item) for item in range(1, 31)]

        points = macd(values, fast=3, slow=6, signal=3)

        self.assertEqual(len(points), len(values))
        self.assertIsNotNone(points[-1])

    def test_rsi_handles_gains_and_losses(self) -> None:
        values = [1.0, 2.0, 3.0, 2.0, 2.5, 3.5]

        values_rsi = rsi(values, window=3)

        self.assertEqual(values_rsi[:3], [None, None, None])
        self.assertGreater(values_rsi[-1] or 0.0, 50.0)

    def test_bollinger_bands(self) -> None:
        bands = bollinger_bands([1.0, 2.0, 3.0], window=3, multiplier=2.0)

        self.assertIsNone(bands[0])
        self.assertIsNone(bands[1])
        self.assertAlmostEqual(bands[2].middle, 2.0)  # type: ignore[union-attr]

    def test_atr_obv_kdj_and_closes(self) -> None:
        bars = make_bars([10.0, 11.0, 10.5, 12.0])

        self.assertEqual(closes(bars), [10.0, 11.0, 10.5, 12.0])
        self.assertEqual(atr(bars, window=2)[0], None)
        self.assertEqual(obv(bars), [0.0, 1100.0, -100.0, 1200.0])
        self.assertEqual(len(kdj(bars, window=3)), len(bars))
        self.assertIsNotNone(kdj(bars, window=3)[-1])

    def test_invalid_window_raises(self) -> None:
        with self.assertRaises(ValueError):
            sma([1.0], 0)


def make_bars(closing_prices: list[float]) -> list[DailyBar]:
    start = date(2026, 6, 1)
    bars = []
    for index, close in enumerate(closing_prices):
        bars.append(
            DailyBar(
                symbol="000001",
                trade_date=start + timedelta(days=index),
                open=close - 0.2,
                high=close + 0.5,
                low=close - 0.5,
                close=close,
                volume=1000.0 + (index * 100),
                amount=10000.0,
                turnover=1.0,
                adjust="hfq",
                provider="test",
            )
        )
    return bars
