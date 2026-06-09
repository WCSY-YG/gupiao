---
name: technical-signal-buy-sell
description: Use when creating or evaluating buy/sell point analysis from technical indicators, candlestick patterns, trend confirmation, stops, targets, and signal explanations.
---

# Technical Signal Buy/Sell

Use this skill when the task needs entry, exit, stop-loss, take-profit, or signal explanation logic.

## Signal Structure

Each buy/sell signal should include:

- Direction: buy, sell, reduce, add, hold, avoid.
- Confidence score: 0-100 or low/medium/high.
- Trigger condition: indicator or pattern rule.
- Confirmation: trend, volume, benchmark, sector, or money-flow confirmation.
- Risk control: stop-loss, trailing stop, take-profit, invalidation condition.
- Explanation: short human-readable reason.

## Indicator Groups

- Trend: MA/EMA alignment, MACD, BOLL middle band, Donchian channel.
- Momentum: RSI, KDJ, CCI, ROC, WR.
- Volatility: ATR, BOLL width, volatility contraction/expansion.
- Volume-price: OBV, volume ratio, turnover, amount breakout.
- Pattern: TA-Lib candlestick patterns and project-specific K-line rules.

## Reference Sources

- P0 notes: `docs/research/04_p0_reference_notes.md`
- TA-Lib Python GitHub: https://github.com/TA-Lib/ta-lib-python
- Upstream TA-Lib: https://ta-lib.org/
- License: BSD-2-Clause

## Indicator Implementation Notes

- Prefer TA-Lib Function API or Abstract API for MVP indicators when available.
- Keep TA-Lib optional; provide `ta` or pandas/numpy fallbacks for environments where the C library is unavailable.
- Preserve lookback NaN values and let strategy code explicitly drop or mask unavailable rows.
- Separate generic indicators from candlestick-pattern detection so strategy code can choose only what it needs.
- When mapping DataFrames into TA-Lib Abstract API, keep canonical OHLCV names stable.

## Default Rules

- A buy point should require at least one trigger and one confirmation.
- A sell point should fire on stop-loss, trend break, take-profit exhaustion, or signal invalidation.
- Always output invalidation conditions; a signal without an invalidation rule is incomplete.
- For A-shares, account for T+1 and limit-up/down when converting signals to simulated trades.

## Review Checklist

- Does the signal use only data available at decision time?
- Does the signal explain both upside thesis and downside risk?
- Are stop-loss and take-profit levels numeric and reproducible?
- Does the signal avoid contradicting the higher timeframe trend unless it is explicitly a reversal strategy?
- Are indicator warmup periods and NaN propagation handled deterministically?
