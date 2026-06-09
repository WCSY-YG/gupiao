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

## Reference Sources

- P0 notes: `docs/research/04_p0_reference_notes.md`
- backtesting.py GitHub: https://github.com/kernc/backtesting.py
- Quick Start: https://kernc.github.io/backtesting.py/doc/examples/Quick%20Start%20User%20Guide.html
- API docs: https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html
- License: AGPL-3.0

## backtesting.py MVP Contract

- Input data must map canonical bars to `Open`, `High`, `Low`, `Close`, and optional `Volume`.
- Use `Strategy.init()` for vectorized indicator precomputation.
- Use `Strategy.next()` for bar-by-bar decisions using only information available at that point.
- Remember that default order timing is next-bar execution unless explicitly configured.
- backtesting.py is not a full stock screener or portfolio rebalancer; batch multiple symbols outside the engine.

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

## Licensing Note

backtesting.py is AGPL-3.0. It is acceptable as a local research dependency during MVP exploration, but before packaging a Web/API product or distributing derived work, review the license boundary and consider an adapter or alternate engine if needed.
