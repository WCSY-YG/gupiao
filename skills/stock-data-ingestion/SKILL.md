---
name: stock-data-ingestion
description: Use when building or changing stock market data ingestion for A-share or multi-market quant research, including instruments, daily bars, adjusted prices, fundamentals, money flow, storage, and data quality checks.
---

# Stock Data Ingestion

Use this skill when the task needs market data collection, refresh jobs, storage schemas, or data quality validation for the stock project.

## Default Sources

- MVP: use AKShare first for A-share instruments, daily bars, adjusted prices, fundamentals, and money flow.
- Extensions: evaluate Tushare for A-share paid/limited datasets, OpenBB for broad financial data, and yfinance for US stocks/ETF.
- Never assume a source is complete. Record source name, fetch time, adjustment mode, and field definitions.

## Reference Sources

- P0 notes: `docs/research/04_p0_reference_notes.md`
- AKShare GitHub: https://github.com/akfamily/akshare
- AKShare stock data dictionary: https://akshare.akfamily.xyz/data/stock/stock.html
- AKShare quick start: https://akshare.akfamily.xyz/tutorial.html
- License: MIT

## AKShare MVP Interfaces

- `stock_info_a_code_name`: A-share instrument code/name universe.
- `stock_zh_a_hist`: daily OHLCV and turnover data; always record `adjust`.
- `stock_individual_fund_flow`: recent individual-stock money flow.
- `stock_financial_analysis_indicator`: historical financial indicators by symbol and start year.

Normalize provider-specific Chinese fields at the ingestion boundary. Keep source metadata so schema or API changes can be audited later.

## Workflow

1. Define the target universe: market, board, industry, concept, index membership, listing status.
2. Fetch raw data into a staging table or file before transformation.
3. Normalize symbols, dates, OHLCV fields, turnover, amount, and adjustment factors.
4. Store cleaned data in `SQLite/DuckDB + Parquet` for the MVP.
5. Add quality checks before any strategy uses the data.

## Required Checks

- Missing trading dates and suspended stocks.
- Forward/backward adjusted price consistency.
- Duplicate symbol/date rows.
- OHLC validity: high >= max(open, close), low <= min(open, close), volume >= 0.
- Financial data release date versus report period to avoid lookahead bias.
- A-share constraints: T+1, limit up/down, ST status, delisting risk.

## Output Contract

Data tasks should document:

- Source API and parameters.
- Target table or file.
- Date range.
- Adjustment mode.
- Row count and validation failures.

## Implementation Notes

- Create provider adapters instead of calling AKShare directly from strategies.
- Unit tests should use fixture files; live AKShare calls belong in integration tests or manual smoke checks.
- Store `provider`, `fetched_at`, `adjust`, and source parameters with each batch.
- Preserve raw provider output when practical, then write normalized tables for downstream code.
- Treat AKShare data as research input only; do not represent it as investment advice or guaranteed complete data.
