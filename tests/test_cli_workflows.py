from __future__ import annotations

import json
from contextlib import redirect_stdout
from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from gupiao.cli import main, to_jsonable
from gupiao.data import Instrument, SQLiteStore

from tests.test_morning_workflow import auction_profile
from tests.test_screening_strategy import breakout_bars


class CliWorkflowsTest(TestCase):
    def test_screen_signal_backtest_and_report_from_jsonl(self) -> None:
        with TemporaryDirectory() as directory:
            bars_path = f"{directory}/bars.jsonl"
            report_path = f"{directory}/report.md"
            dashboard_path = f"{directory}/dashboard.html"
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

            dashboard = run_cli(
                [
                    "web",
                    "dashboard",
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
                    dashboard_path,
                ]
            )
            self.assertEqual(json.loads(dashboard)["path"], dashboard_path)
            dashboard_html = Path(dashboard_path).read_text(encoding="utf-8")
            self.assertIn("A 股策略研究 Dashboard", dashboard_html)
            self.assertIn("行情走势", dashboard_html)
            self.assertIn("命令面板", dashboard_html)

    def test_screen_list_run_candidates_and_data_status(self) -> None:
        with TemporaryDirectory() as directory:
            bars_path = f"{directory}/bars.jsonl"
            db_path = f"{directory}/screen.sqlite"
            write_bars_jsonl(bars_path)
            bars = breakout_bars()
            store = SQLiteStore(db_path)
            store.upsert_instruments([Instrument(symbol="000001", name="平安银行", market="A股")])
            store.upsert_daily_bars(bars)

            strategies = run_cli(["screen", "list"])
            first_strategy = json.loads(strategies.splitlines()[0])
            self.assertIn("id", first_strategy)

            screen_run = run_cli(
                [
                    "screen",
                    "run",
                    "--bars",
                    bars_path,
                    "--symbol",
                    "000001",
                    "--as-of",
                    bars[-1].trade_date.isoformat(),
                    "--strategy",
                    "low_volatility_breakout",
                    *small_strategy_args(),
                ]
            )
            self.assertEqual(
                json.loads(screen_run)["candidate"]["strategy"],
                "low_volatility_breakout",
            )

            candidates = run_cli(
                [
                    "screen",
                    "candidates",
                    "--db",
                    db_path,
                    "--as-of",
                    bars[-1].trade_date.isoformat(),
                    "--strategy",
                    "ma_volume_breakout",
                    "--limit",
                    "1",
                    *small_strategy_args(),
                ]
            )
            self.assertEqual(json.loads(candidates)["screen"]["candidate_count"], 1)

            status = run_cli(["data", "status", "--db", db_path])
            self.assertEqual(json.loads(status)["daily_bars"]["rows"], len(bars))

    def test_morning_screen_and_trade_plan_cli(self) -> None:
        with TemporaryDirectory() as directory:
            db_path = f"{directory}/morning.sqlite"
            bars = breakout_bars()
            trade_date = bars[-1].trade_date + timedelta(days=1)
            store = SQLiteStore(db_path)
            store.upsert_instruments([Instrument(symbol="000001", name="平安银行", market="A股")])
            store.upsert_daily_bars(bars)
            store.upsert_auction_profiles([auction_profile("000001", trade_date)])

            morning = run_cli(
                [
                    "screen",
                    "morning",
                    "--db",
                    db_path,
                    "--trade-date",
                    trade_date.isoformat(),
                    "--horizon",
                    "short_term",
                    "--strategy",
                    "auction_open_breakout_short",
                    "--symbol",
                    "000001",
                    *small_strategy_args(),
                ]
            )
            self.assertEqual(json.loads(morning)["morning_screen"]["candidate_count"], 1)

            plan = run_cli(
                [
                    "plan",
                    "trade",
                    "--db",
                    db_path,
                    "--trade-date",
                    trade_date.isoformat(),
                    "--symbol",
                    "000001",
                    "--horizon",
                    "short_term",
                    "--strategy",
                    "auction_open_breakout_short",
                    *small_strategy_args(),
                ]
            )
            self.assertEqual(json.loads(plan)["status"], "candidate")
            self.assertIn("09:25", json.loads(plan)["trade_plan"]["entry_timing"])


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
