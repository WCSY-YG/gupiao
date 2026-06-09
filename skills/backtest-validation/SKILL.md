---
name: backtest-validation
description: Use when implementing or reviewing strategy backtests, including data alignment, transaction costs, slippage, T+1, limit-up/down constraints, benchmark comparison, optimization, and anti-lookahead checks.
---

# Backtest Validation

Use this skill whenever a strategy result is produced, changed, optimized, or compared.

## Preferred MVP Tools

- Use `backtesting.py` for simple single-instrument or compact strategy validation.
- Use `vectorbt` for batch signals, parameter grids, and portfolio-level vectorized tests.
- Use `backtrader`, `RQAlpha`, `hikyuu`, or `Lean` as architecture references when the event model becomes complex.

## Minimum Assumptions

Backtests must specify:

- Universe and benchmark.
- Date range and rebalance frequency.
- Price adjustment mode.
- Execution price rule.
- Commission, tax, slippage, and minimum fee.
- A-share T+1 and limit-up/down handling.
- Position sizing and maximum holdings.

## Anti-Cheating Checks

- No future bars in indicators.
- Financial data must use release date, not only report period.
- No survivorship bias in historical universes.
- Parameter optimization must be separated from final evaluation.
- Include failed trades and unfilled trades.

## Required Outputs

- Total return, annualized return, max drawdown, Sharpe, win rate.
- Trade count, average holding period, turnover, exposure.
- Equity curve and drawdown curve.
- Benchmark comparison.
- Key assumptions and known limitations.

