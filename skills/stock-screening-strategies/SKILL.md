---
name: stock-screening-strategies
description: Use when designing, implementing, or reviewing stock selection strategies, including fundamental screens, technical screens, volume-price screens, candlestick pattern screens, multi-factor ranking, and strategy registries.
---

# Stock Screening Strategies

Use this skill when the task is to add or modify an automated stock selection strategy.

## Strategy Template

Every strategy must define:

- Universe: market, boards, industries, ST/exclusion rules.
- Required data: bars, fundamentals, money flow, indicators, index benchmark.
- Signal logic: exact filters or factor scoring formula.
- Ranking logic: tie-breakers, weights, top N, thresholds.
- Rebalance rule: daily, weekly, monthly, or signal-triggered.
- Risk filters: liquidity, volatility, drawdown, limit-up/down, suspension.
- Explanation fields: why each selected stock passed.

## MVP Strategy Families

- Fundamental: low PE/PB, high ROE, profit growth, healthy cash flow.
- Trend: moving average alignment, Donchian breakout, relative strength.
- Reversal: RSI/KDJ/CCI oversold recovery, low volatility contraction.
- Volume-price: volume breakout, price-volume divergence, money inflow.
- Pattern: candlestick patterns from TA-Lib or local pattern rules.
- Multi-factor: value, quality, growth, momentum, volatility, liquidity scoring.

## Validation

- Compare selections against a benchmark universe.
- Backtest with realistic costs, slippage, T+1, and limit-up/down constraints.
- Run out-of-sample or rolling-window validation before promoting a strategy.
- Report both top winners and failed selections; do not hide false positives.

## Anti-Patterns

- Do not use future financial data by report period alone.
- Do not select from only currently listed stocks when testing historical periods.
- Do not tune thresholds only on one bull or bear market segment.

