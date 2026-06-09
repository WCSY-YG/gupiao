---
name: stock-trading-research-master
description: Use as the master workflow for this stock trading research project when planning, researching GitHub trading skills/projects, updating market-aware assumptions, routing to data/screening/signal/backtest/report skills, or coordinating versioned A-share quant research work.
---

# Stock Trading Research Master

Use this skill as the entry point for project-level stock research tasks. It coordinates Git hygiene, external GitHub research, market-change awareness, child skill routing, and final quality checks.

This project is for research, simulation, and decision support only. Do not present outputs as investment advice or guaranteed returns.

## Start Every Substantial Task

1. Check Git status and current branch.
2. If the work is more than a tiny note, use a topic branch named `codex/<topic>`.
3. Record any external research date and source URLs in `docs/research/`.
4. Keep `VERSION`, `CHANGELOG.md`, and project memory aligned when the change affects project direction, skill structure, or delivered capability.
5. Keep README content in Chinese.
6. Run Python commands through the conda `agent` environment, preferably `conda run -n agent python ...` or `conda run -n agent pytest ...`.

## External Research First

Before adding or revising trading skills, gather and record relevant GitHub sources:

- Native skill/agent projects: Claude/Codex trading skills, stock-analysis skills, TradingView skills, MCP trading orchestration.
- Data projects: AKShare, Tushare, OpenBB, yfinance.
- A-share/quant frameworks: myhhub/stock, vn.py, zvt, hikyuu, QUANTAXIS.
- AI/factor projects: Qlib, FinRL, AgentQuant, stock prediction paper lists.
- Indicator projects: TA-Lib Python, bukosabino/ta, pandas-ta-classic.
- Backtest/report projects: QuantStats, Lean, vectorbt, backtesting.py, backtrader, bt, RQAlpha.

For each source, record:

- Repository name and URL.
- Star snapshot, license, and last push date when available.
- What to distill: workflow, API shape, validation checklist, strategy template, report structure, or risk controls.
- Reuse status: direct candidate, architecture reference, prompt structure reference, or license-sensitive reference.

## Child Skill Routing

- Data ingestion, schema, refresh jobs, and data quality: use `stock-data-ingestion`.
- Stock screens, factor definitions, ranking, and candidate pools: use `stock-screening-strategies`.
- Buy/sell points, stops, targets, technical explanation: use `technical-signal-buy-sell`.
- Backtest assumptions, anti-lookahead checks, costs, T+1 and limit rules: use `backtest-validation`.
- Performance, risk, benchmark comparison, Chinese reports: use `performance-risk-reporting`.

When a task spans multiple areas, call the child skills in this order:

1. Data.
2. Strategy.
3. Signal.
4. Backtest.
5. Report.

## Market Update Discipline

Before strategy or signal changes, check whether assumptions need updating:

- Data source availability, field definitions, rate limits, and adjustment modes.
- A-share trading rules: T+1, limit-up/down, ST/delisting treatment, fees, tax, suspension handling.
- Market regime: index trend, market breadth, turnover, volatility, industry rotation, theme activity, money flow.
- Strategy decay: recent false positives, drawdown, benchmark underperformance, parameter instability.
- Regulatory or market-structure changes that affect execution or backtest assumptions.

If a market update changes assumptions, document the change before changing strategy logic.

## Strategy Quality Gate

Every strategy or signal must define:

- Universe and exclusions.
- Required data and source.
- Exact signal formula.
- Ranking or position sizing rule.
- Execution assumption.
- Stop-loss, take-profit, and invalidation condition.
- Backtest date range, benchmark, costs, slippage, T+1, and limit handling.
- Known failure modes.

Reject or revise work that uses future data, hides failed trades, omits transaction costs, or lacks a numeric invalidation rule.

## Distillation Rules

- Distill workflows, interfaces, validation rules, formulas, and report structures.
- Do not copy large code blocks from external projects.
- For GPL, AGPL, or undeclared-license projects, treat them as architecture references unless licensing is explicitly reviewed.
- Keep each skill concise. Put detailed domain references in `references/` only when needed.

## Final Output Check

Before handing off a completed project task, verify:

- Git status is understood and no unrelated files were changed.
- External source URLs were recorded when research was performed.
- Relevant child skills were updated or used.
- The output includes data assumptions, strategy assumptions, risk boundaries, and next verification step.
- Tests or validation commands were run when code changed; if not, say why.
