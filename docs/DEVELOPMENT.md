# Development

## Environment

Use Python 3.11 or 3.12.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

Optional feature dependencies:

```bash
python -m pip install -e ".[data,analysis,backtest,report]"
```

`TA-Lib` is intentionally not part of the default extras because local C-library availability varies. Add it only after confirming the target environment can install it.

## Commands

```bash
python -m pytest
python -m ruff check .
python -m ruff format .
python -m mypy src/gupiao
python -m gupiao.cli --version
```

## Packaging

The package uses a `src/` layout with `setuptools`. The CLI entry point is:

```bash
gupiao --version
```

Generated data and reports are ignored by Git. Commit only source code, tests, documentation, configuration examples, and small fixtures that are safe to share.
