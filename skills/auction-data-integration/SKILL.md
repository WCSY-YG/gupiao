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
- `bid_ask_imbalance`: `(bid_size1 + bid_size2 - ask_size1 - ask_size2) / total_size` when local snapshots include bid/ask depth.
- `strength_score`: bounded 0-100 score combining gap, volume, and stability.

For local `cache/jingjia` snapshots, `total_volume_trade` is treated as lots and converted to shares with `* 100`.

## Local RAR Import

Use the project command before historical auction backtests:

```bash
PYTHONPATH=src python -m gupiao.cli data import-auction-cache \
  --source cache/jingjia \
  --db data/cache/market_scan.sqlite \
  --provider local_jingjia \
  --conflict ignore
```

Run with `--dry-run` first for counts. Use `--conflict replace` only when intentionally recalculating features.

## Strategy Rules

- Auction data can boost ranking, filter weak candidates, or create a pre-open candidate pool.
- Require a decision timestamp. Pre-open decisions may use auction data up to that timestamp only.
- Avoid over-heated opens: a very high positive gap without volume support should be penalized or filtered.
- Keep auction scoring explainable: output gap, volume ratio, range, and score in candidate metrics.
- Market scans can opt into stored profiles with `scan market --auction-provider local_jingjia --min-auction-score 60 --auction-score-weight 0.15`.
- Treat `min_auction_score` as experimental. The 2026-05 validation run favored using auction score as a soft ranking signal before making it a hard gate.

## Backtest Rules

- Historical backtests must use historical auction snapshots keyed by `trade_date`.
- Load stored profiles from SQLite `auction_profiles` by `symbol + trade_date + provider`, then pass them into `run_breakout_backtest(..., auction_profiles=...)`.
- If only latest AKShare auction minutes are available, use them for live screening or smoke tests, not historical performance claims.
- Compare at least two variants: baseline K-line strategy and K-line plus auction-enhanced strategy.
- Run rolling or recent-window validation to detect auction-signal decay.
- Use `research auction-compare` to produce `reports/summaries/latest_auction_validation.md`; update strategy defaults only from that kind of out-of-sample evidence.

## Iteration Loop

1. Import or fetch auction data.
2. Build `AuctionProfile` features.
3. Run screening with and without auction filters.
4. Backtest both variants with A-share execution constraints.
5. Promote only if recent K-line plus auction performance improves risk-adjusted results without obvious overfitting.
