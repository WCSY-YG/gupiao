"""Backtest validation layer."""

from gupiao.backtest.engine import (
    BacktestConfig,
    BacktestResult,
    EquityPoint,
    Trade,
    can_enter,
    can_exit,
    is_limit_down,
    is_limit_up,
    is_suspended,
    max_drawdown,
    run_breakout_backtest,
    run_morning_plan_backtest,
    win_rate,
)

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "EquityPoint",
    "Trade",
    "can_enter",
    "can_exit",
    "is_limit_down",
    "is_limit_up",
    "is_suspended",
    "max_drawdown",
    "run_breakout_backtest",
    "run_morning_plan_backtest",
    "win_rate",
]
