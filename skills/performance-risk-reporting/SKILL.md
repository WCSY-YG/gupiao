---
name: performance-risk-reporting
description: Use when generating, reviewing, or improving strategy performance reports, including QuantStats-style metrics, drawdown analysis, benchmark comparison, trade summaries, and Chinese signal explanations.
---

# Performance Risk Reporting

Use this skill when the task needs a strategy report, candidate-stock report, or risk explanation.

## Report Sections

- Summary: strategy name, universe, date range, benchmark, assumptions.
- Returns: total return, annualized return, monthly/yearly returns.
- Risk: max drawdown, volatility, Sharpe, Sortino, Calmar.
- Trades: count, win rate, average win/loss, holding period, turnover.
- Exposure: cash ratio, position concentration, industry/sector exposure if available.
- Signals: selected stocks, buy/sell reasons, stop-loss/take-profit/invalidation rules.
- Caveats: data limitations, lookahead checks, market regime sensitivity.

## Preferred Tools

- Use QuantStats for tearsheet-style metrics and HTML reports.
- Use custom Markdown/HTML for Chinese explanations and strategy-specific diagnostics.
- Add charts only when they clarify decisions: equity curve, drawdown, monthly heatmap, trade distribution.

## Reference Sources

- P0 notes: `docs/research/04_p0_reference_notes.md`
- QuantStats GitHub: https://github.com/ranaroussi/quantstats
- QuantStats docs directory: https://github.com/ranaroussi/quantstats/tree/main/docs
- License: Apache-2.0

## QuantStats MVP Contract

- Convert backtest equity or trade results into a clean returns Series before report generation.
- Use `quantstats.stats` for metrics, `quantstats.plots` for visuals, and `quantstats.reports` for reports.
- Generate project-native Markdown/JSON first, then optionally produce QuantStats HTML tearsheets.
- Replace any default US-market benchmark assumptions with project-provided A-share benchmark returns.
- Keep Monte Carlo and advanced risk analytics as post-MVP enhancements.

## Quality Bar

- Report failed assumptions clearly.
- Do not present high return without drawdown and sample length.
- Include benchmark and cash/idle exposure.
- If a metric cannot be computed reliably, mark it as unavailable instead of guessing.
- Make Chinese explanations specific to the strategy, not generic performance boilerplate.
