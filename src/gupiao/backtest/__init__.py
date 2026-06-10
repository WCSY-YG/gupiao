"""Backtest validation layer."""

from gupiao.backtest.engine import (
    BacktestConfig,
    BacktestResult,
    EquityPoint,
    Trade,
    max_drawdown,
    run_breakout_backtest,
    win_rate,
)

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "EquityPoint",
    "Trade",
    "max_drawdown",
    "run_breakout_backtest",
    "win_rate",
]
