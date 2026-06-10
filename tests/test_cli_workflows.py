from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from gupiao.cli import main, to_jsonable
from tests.test_screening_strategy import breakout_bars


class CliWorkflowsTest(TestCase):
    def test_screen_signal_backtest_and_report_from_jsonl(self) -> None:
        with TemporaryDirectory() as directory:
            bars_path = f"{directory}/bars.jsonl"
            report_path = f"{directory}/report.md"
            write_bars_jsonl(bars_path)

            screen = run_cli(
                [
                    "screen",
                    "breakout",
                    "--bars",
                    bars_path,
                    "--symbol",
                    "000001",
                    *small_strategy_args(),
                ]
            )
            self.assertIsNotNone(json.loads(screen)["candidate"])

            signal = run_cli(
                [
                    "signal",
                    "breakout",
                    "--bars",
                    bars_path,
                    "--symbol",
                    "000001",
                    *small_strategy_args(),
                    "--atr-window",
                    "3",
                ]
            )
            self.assertEqual(json.loads(signal)["signal"]["direction"], "buy")

            backtest = run_cli(
                [
                    "backtest",
                    "breakout",
                    "--bars",
                    bars_path,
                    "--symbol",
                    "000001",
                    *small_strategy_args(),
                    "--atr-window",
                    "3",
                    "--max-holding-bars",
                    "2",
                ]
            )
            self.assertIn("total_return", json.loads(backtest)["backtest"])

            report = run_cli(
                [
                    "report",
                    "breakout",
                    "--bars",
                    bars_path,
                    "--symbol",
                    "000001",
                    *small_strategy_args(),
                    "--atr-window",
                    "3",
                    "--max-holding-bars",
                    "2",
                    "--output",
                    report_path,
                ]
            )
            self.assertEqual(json.loads(report)["path"], report_path)
            self.assertIn("## 回测结果", Path(report_path).read_text(encoding="utf-8"))


def run_cli(args: list[str]) -> str:
    stdout = StringIO()
    with redirect_stdout(stdout):
        assert main(args) == 0
    return stdout.getvalue().strip()


def write_bars_jsonl(path: str) -> None:
    with open(path, "w", encoding="utf-8") as file:
        for bar in breakout_bars():
            file.write(json.dumps(to_jsonable(bar), ensure_ascii=False) + "\n")


def small_strategy_args() -> list[str]:
    return [
        "--short-window",
        "3",
        "--medium-window",
        "5",
        "--long-window",
        "8",
        "--volume-window",
        "5",
        "--breakout-window",
        "5",
        "--min-volume-ratio",
        "1.5",
    ]
