from __future__ import annotations

from datetime import timedelta
from unittest import TestCase

from gupiao.backtest import (
    BacktestConfig,
    can_enter,
    can_exit,
    is_limit_down,
    is_limit_up,
    max_drawdown,
    run_breakout_backtest,
    win_rate,
)
from gupiao.strategies import MovingAverageVolumeBreakoutStrategy
from tests.test_screening_strategy import breakout_bars


class BacktestEngineTest(TestCase):
    def test_run_breakout_backtest_produces_metrics_and_trade(self) -> None:
        bars = breakout_bars()
        bars[-1] = replace_price(bars[-1], close=12.4, high=12.5, low=12.0)
        bars.append(
            replace_price(
                bars[-1],
                close=14.0,
                high=15.0,
                low=13.8,
                days_after=1,
            )
        )

        result = run_breakout_backtest(
            "000001",
            bars,
            strategy=small_strategy(),
            config=BacktestConfig(
                commission_rate=0.001,
                slippage_rate=0.001,
                max_holding_bars=5,
                atr_window=3,
                stop_atr_multiple=1.0,
                take_profit_r_multiple=1.0,
            ),
        )

        self.assertEqual(result.symbol, "000001")
        self.assertEqual(result.trade_count, 1)
        self.assertEqual(result.trades[0].exit_reason, "take_profit")
        self.assertGreater(result.total_return, 0)
        self.assertGreaterEqual(result.win_rate, 1.0)
        self.assertEqual(len(result.equity_curve), len(bars))
        self.assertIn("Long-only", result.assumptions[0])

    def test_run_breakout_backtest_rejects_bad_quality_bars(self) -> None:
        bars = breakout_bars()
        bars.append(bars[-1])

        with self.assertRaises(ValueError):
            run_breakout_backtest("000001", bars, strategy=small_strategy())

    def test_metric_helpers(self) -> None:
        self.assertAlmostEqual(max_drawdown([100.0, 120.0, 90.0, 130.0]), -0.25)
        self.assertEqual(win_rate(()), 0.0)

    def test_a_share_constraints_block_limit_up_entry(self) -> None:
        bar = replace_price(breakout_bars()[-1], close=11.0, high=11.0, low=10.8)

        self.assertTrue(is_limit_up(11.0, 10.0, 0.10))
        self.assertFalse(can_enter(bar, previous_close=10.0, config=BacktestConfig()))

    def test_a_share_constraints_block_limit_down_exit(self) -> None:
        bar = replace_price(breakout_bars()[-1], close=9.0, high=9.2, low=9.0)

        self.assertTrue(is_limit_down(9.0, 10.0, 0.10))
        self.assertFalse(
            can_exit(
                bar,
                previous_close=10.0,
                holding_bars=1,
                config=BacktestConfig(),
            )
        )

    def test_a_share_constraints_block_same_day_exit_and_suspension(self) -> None:
        suspended = replace_price(breakout_bars()[-1], close=10.0, high=10.2, low=9.8)
        suspended = type(suspended)(
            symbol=suspended.symbol,
            trade_date=suspended.trade_date,
            open=suspended.open,
            high=suspended.high,
            low=suspended.low,
            close=suspended.close,
            volume=0.0,
            amount=suspended.amount,
            turnover=suspended.turnover,
            adjust=suspended.adjust,
            provider=suspended.provider,
            fetched_at=suspended.fetched_at,
        )

        self.assertFalse(can_enter(suspended, previous_close=10.0, config=BacktestConfig()))
        self.assertFalse(
            can_exit(
                suspended,
                previous_close=10.0,
                holding_bars=0,
                config=BacktestConfig(),
            )
        )


def small_strategy() -> MovingAverageVolumeBreakoutStrategy:
    return MovingAverageVolumeBreakoutStrategy(
        short_window=3,
        medium_window=5,
        long_window=8,
        volume_window=5,
        breakout_window=5,
        min_volume_ratio=1.5,
    )


def replace_price(bar, *, close: float, high: float, low: float, days_after: int = 0):
    return type(bar)(
        symbol=bar.symbol,
        trade_date=bar.trade_date + timedelta(days=days_after),
        open=close - 0.2,
        high=high,
        low=low,
        close=close,
        volume=bar.volume,
        amount=bar.amount,
        turnover=bar.turnover,
        adjust=bar.adjust,
        provider=bar.provider,
        fetched_at=bar.fetched_at,
    )
