---
name: auction-data-integration
description: Use when adding, reviewing, or iterating A-share call-auction data workflows, including AKShare pre-market minutes, local auction snapshot caches, auction feature engineering, auction-aware screening, and historical auction backtests.
---

# Auction Data Integration

Use this skill when a task touches A-share call-auction data, same-day pre-open selection, or auction-aware strategy iteration.

## Sources

- AKShare `stock_zh_a_hist_pre_min_em`: latest available pre-market minute bars, including call-auction minutes. Use `09:15:00` to `09:25:00` for the opening auction profile.
- Local `cache/jingjia/*.rar`: historical auction snapshots. Treat these as the main source for historical backtests after import.

## Canonical Features

Build an `AuctionProfile` per symbol and trade date:

- `indicative_price`: latest auction indicative or close-like price.
- `gap_pct`: indicative price versus previous close.
- `volume`: cumulative auction volume.
- `volume_ratio_to_daily`: auction volume versus recent average daily volume.
- `range_pct`: auction high-low instability.
- `strength_score`: bounded 0-100 score combining gap, volume, and stability.

When bid/ask levels are available from local snapshots, add bid/ask imbalance later as a separate feature; do not mix it into existing fields without recording the formula.

## Strategy Rules

- Auction data can boost ranking, filter weak candidates, or create a pre-open candidate pool.
- Require a decision timestamp. Pre-open decisions may use auction data up to that timestamp only.
- Avoid over-heated opens: a very high positive gap without volume support should be penalized or filtered.
- Keep auction scoring explainable: output gap, volume ratio, range, and score in candidate metrics.

## Backtest Rules

- Historical backtests must use historical auction snapshots keyed by `trade_date`.
- If only latest AKShare auction minutes are available, use them for live screening or smoke tests, not historical performance claims.
- Compare at least two variants: baseline K-line strategy and K-line plus auction-enhanced strategy.
- Run rolling or recent-window validation to detect auction-signal decay.

## Iteration Loop

1. Import or fetch auction data.
2. Build `AuctionProfile` features.
3. Run screening with and without auction filters.
4. Backtest both variants with A-share execution constraints.
5. Promote only if recent K-line plus auction performance improves risk-adjusted results without obvious overfitting.
