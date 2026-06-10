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
- Optional auction data: same-day call-auction profile with indicative price, gap, volume ratio, range, bid/ask imbalance, and strength score.
- Signal logic: exact filters or factor scoring formula.
- Ranking logic: tie-breakers, weights, top N, thresholds.
- Rebalance rule: daily, weekly, monthly, or signal-triggered.
- Risk filters: liquidity, volatility, drawdown, limit-up/down, suspension.
- Explanation fields: why each selected stock passed.

## Reference Sources

- P0 notes: `docs/research/04_p0_reference_notes.md`
- myhhub/stock GitHub: https://github.com/myhhub/stock
- InStock Docker image: https://hub.docker.com/r/mayanghua/instock
- License: Apache-2.0

## MVP Strategy Families

- Fundamental: low PE/PB, high ROE, profit growth, healthy cash flow.
- Trend: moving average alignment, Donchian breakout, relative strength.
- Reversal: RSI/KDJ/CCI oversold recovery, low volatility contraction.
- Volume-price: volume breakout, price-volume divergence, money inflow.
- Call auction: positive but not overheated gap, meaningful auction volume, stable indicative price range, and supportive bid/ask imbalance from `auction_profiles` when available.
- Pattern: candlestick patterns from TA-Lib or local pattern rules.
- Multi-factor: value, quality, growth, momentum, volatility, liquidity scoring.

## Job Boundaries

Borrow the batch-job split from myhhub/stock without copying its full deployment complexity:

- Data refresh jobs update instruments, bars, fundamentals, and money flow.
- Indicator jobs compute reusable features before strategy screening.
- Strategy jobs produce candidate rows with score, rank, and explanation fields.
- Validation jobs backtest selected candidates and record false positives.
- Report jobs summarize candidate lists, signal reasons, and risk caveats.

## Current MVP Auction Enhancement

- Baseline strategy: `MovingAverageVolumeBreakoutStrategy`.
- Stored auction provider: `local_jingjia` in SQLite `auction_profiles`.
- Use `auction_score_weight` as a bounded blend into candidate score; keep `min_auction_score` as an experiment-only hard filter until rolling validation proves it helps.
- Keep auction metrics in candidate explanations: `auction_strength_score`, `auction_gap_pct`, `auction_volume_ratio_to_daily`, and `auction_bid_ask_imbalance`.
- Latest validation note: 2026-01-01 to 2026-05-29 with May 2026 `local_jingjia` profiles showed `min_auction_score=60` and `auction_score_weight=0.15` did not improve average return, so prefer soft ranking/diagnostics over default hard filtering.

## Morning Multi-Horizon Strategy Rules

- `short_term`: pre-open decision after 09:25 call auction; use only prior daily bars plus same-day auction profile; auction is required; default strategies are `auction_open_breakout_short` and `auction_gap_reversal_short`.
- `mid_short_term`: 3-10 day swing decision; use prior daily volume-price structure first and same-day auction as confirmation; default strategies are `volume_breakout_swing` and `pullback_recovery_swing`.
- `mid_term`: 10-30 day trend-quality decision; use moving-average trend, volatility stability, liquidity, and drawdown filters first; auction has low weight and must not be a hard requirement by default; default strategy is `trend_quality_mid`.
- Every selected candidate should have a separate `TradePlan` describing decision time, visible data boundary, reference entry price, entry timing, stop loss, take profit, reduce price, max holding bars, buy conditions, avoid conditions, and risk notes.
- In `morning_auction` mode, daily bars for the decision must satisfy `trade_date < decision trade_date`; the trade date daily open may be used only as a backtest execution price, never as a selection feature.

## Validation

- Compare selections against a benchmark universe.
- Backtest with realistic costs, slippage, T+1, and limit-up/down constraints.
- When using same-day call-auction signals, verify the decision timestamp and do not let post-open K-line data leak into pre-open selection.
- Run out-of-sample or rolling-window validation before promoting a strategy.
- Report both top winners and failed selections; do not hide false positives.

## Anti-Patterns

- Do not use future financial data by report period alone.
- Do not select from only currently listed stocks when testing historical periods.
- Do not tune thresholds only on one bull or bear market segment.
- Do not add real trading or broker automation to MVP strategy code.
