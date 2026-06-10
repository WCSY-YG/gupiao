# gupiao

A-share stock screening and buy/sell signal research project.

## Current Scope

- Multi-strategy stock screening.
- Buy/sell point analysis with signal explanations.
- Backtest validation and risk reporting.
- GitHub project research distilled into reusable project skills.

## Project Documents

- `docs/PROJECT_PLAN.md`: overall project plan.
- `docs/PROJECT_MEMORY.md`: current project memory and decisions.
- `docs/PROJECT_TASKS.md`: tracked project task list with completion status.
- `docs/AUTOMATION_RUNBOOK.md`: resumable automation and GitHub update rules.
- `docs/DEVELOPMENT.md`: local setup, test, lint, type-check, and packaging commands.
- `docs/research/01_github_search_checklist.md`: GitHub search checklist.
- `docs/research/02_github_project_registry.md`: researched GitHub project registry.
- `docs/research/03_skill_distillation_plan.md`: skill distillation plan.
- `docs/research/04_p0_reference_notes.md`: P0 reference project notes for implementation.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m gupiao.cli --version
python -m gupiao.cli data instruments --limit 10
python -m gupiao.cli data daily 000001 --start 2026-01-01 --end 2026-06-10 --limit 5
python -m gupiao.cli screen breakout --bars data/sample_bars.jsonl --symbol 000001
python -m gupiao.cli backtest breakout --bars data/sample_bars.jsonl --symbol 000001
python -m gupiao.cli report breakout --bars data/sample_bars.jsonl --symbol 000001 --output reports/generated/mvp.md
```

## Project Skills

- `skills/stock-data-ingestion`
- `skills/stock-screening-strategies`
- `skills/technical-signal-buy-sell`
- `skills/backtest-validation`
- `skills/performance-risk-reporting`

## Status

Version: `0.1.0`

This project is currently in planning and research distillation stage. It is for research and decision support only, not investment advice.
