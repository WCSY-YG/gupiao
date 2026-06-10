from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from gupiao.backtest import BacktestConfig, run_breakout_backtest
from gupiao.data import Instrument, SQLiteStore
from gupiao.signals import build_breakout_signal
from gupiao.web import build_app_html, build_dashboard_html, run_web_action, write_dashboard_html

from tests.test_backtest_engine import replace_price, small_strategy
from tests.test_cli_workflows import write_bars_jsonl
from tests.test_morning_workflow import auction_profile
from tests.test_morning_optimization import seed_optimization_store
from tests.test_screening_strategy import breakout_bars


class WebDashboardTest(TestCase):
    def test_build_dashboard_html_contains_sections_and_svg(self) -> None:
        bars = breakout_bars()
        strategy = small_strategy()
        candidate = strategy.evaluate("000001", bars)
        signal = build_breakout_signal(candidate, bars, atr_window=3)
        backtest = run_breakout_backtest(
            "000001",
            bars,
            strategy=strategy,
            config=BacktestConfig(atr_window=3, max_holding_bars=2),
        )

        html = build_dashboard_html(
            title="Dashboard",
            candidate=candidate,
            signal=signal,
            backtest=backtest,
            bars=bars,
            strategy=strategy,
            backtest_config=BacktestConfig(atr_window=3, max_holding_bars=2),
            source_path="data/000001_daily.jsonl",
            commands=["gupiao web dashboard --bars data/000001_daily.jsonl --symbol 000001"],
        )

        self.assertIn("<!doctype html>", html)
        self.assertIn("行情走势", html)
        self.assertIn("策略与竞价", html)
        self.assertIn("买卖点计划", html)
        self.assertIn("回测表现", html)
        self.assertIn("数据质量", html)
        self.assertIn("命令面板", html)
        self.assertIn("<svg", html)
        self.assertIn("price and volume", html)
        self.assertIn("equity curve", html)

    def test_write_dashboard_html(self) -> None:
        with TemporaryDirectory() as directory:
            path = write_dashboard_html(f"{directory}/dashboard.html", "<html></html>")

            self.assertEqual(path.read_text(encoding="utf-8"), "<html></html>")

    def test_interactive_app_contains_core_actions(self) -> None:
        html = build_app_html()

        self.assertIn('data-action="screen_breakout"', html)
        self.assertIn('data-action="backtest_breakout"', html)
        self.assertIn('data-action="scan_market"', html)
        self.assertIn('data-action="factor_rank"', html)
        self.assertIn('data-action="screen_candidates"', html)
        self.assertIn('data-action="morning_screen"', html)
        self.assertIn('data-action="trade_plan"', html)
        self.assertIn('data-action="data_status"', html)
        self.assertIn('data-action="data_refresh_market_cache"', html)
        self.assertIn('data-action="data_monitor_auction"', html)
        self.assertIn('data-action="data_schedule_auction_monitor"', html)
        self.assertIn('data-action="data_auction_monitor_job"', html)
        self.assertIn('data-action="auction_rolling"', html)
        self.assertIn('data-action="optimize_morning_strategies"', html)
        self.assertIn('id="modeToggle"', html)
        self.assertIn('data-tab="home"', html)
        self.assertIn("普通模式", html)
        self.assertIn("开始选股", html)
        self.assertIn("早盘选股", html)
        self.assertIn("买卖计划", html)
        self.assertIn("预约竞价", html)
        self.assertNotIn("/tmp/gupiao_web_bars.jsonl", html)

    def test_run_web_action_lists_auction_monitor_jobs(self) -> None:
        with TemporaryDirectory() as directory:
            result = run_web_action("data_auction_monitor_job", {}, Path(directory))

            self.assertIn("auction_monitor_jobs", result)
            self.assertIsInstance(result["auction_monitor_jobs"], list)

    def test_run_web_action_quick_analysis(self) -> None:
        with TemporaryDirectory() as directory:
            bars_path = f"{directory}/bars.jsonl"
            output_dir = f"{directory}/web"
            write_bars_jsonl(bars_path)

            result = run_web_action(
                "quick_analysis",
                {
                    "symbol": "000001",
                    "bars_path": bars_path,
                    "output_dir": output_dir,
                    "short_window": "3",
                    "medium_window": "5",
                    "long_window": "8",
                    "volume_window": "5",
                    "breakout_window": "5",
                    "min_volume_ratio": "1.5",
                    "atr_window": "3",
                    "max_holding_bars": "2",
                },
                Path(directory),
            )

            self.assertIsNotNone(result["candidate"])
            self.assertIn("dashboard", result)
            self.assertTrue(Path(result["dashboard"]["path"]).exists())

    def test_run_web_action_strategy_status_and_screen_candidates(self) -> None:
        with TemporaryDirectory() as directory:
            db_path = f"{directory}/screen.sqlite"
            bars = breakout_bars()
            store = SQLiteStore(db_path)
            store.upsert_instruments([Instrument(symbol="000001", name="平安银行", market="A股")])
            store.upsert_daily_bars(bars)

            strategies = run_web_action("strategy_list", {}, Path(directory))
            self.assertGreaterEqual(len(strategies["strategies"]), 4)

            status = run_web_action("data_status", {"db_path": db_path}, Path(directory))
            self.assertEqual(status["status"]["daily_bars"]["rows"], len(bars))

            screen = run_web_action(
                "screen_candidates",
                {
                    "db_path": db_path,
                    "as_of": bars[-1].trade_date.isoformat(),
                    "strategy_id": "ma_volume_breakout",
                    "top": "5",
                    "limit": "1",
                    "short_window": "3",
                    "medium_window": "5",
                    "long_window": "8",
                    "volume_window": "5",
                    "breakout_window": "5",
                    "min_volume_ratio": "1.5",
                },
                Path(directory),
            )
            self.assertEqual(screen["screen"].candidate_count, 1)

    def test_run_web_action_morning_screen_and_trade_plan(self) -> None:
        with TemporaryDirectory() as directory:
            db_path = f"{directory}/morning.sqlite"
            bars = breakout_bars()
            trade_date = bars[-1].trade_date + timedelta(days=1)
            store = SQLiteStore(db_path)
            store.upsert_instruments([Instrument(symbol="000001", name="平安银行", market="A股")])
            store.upsert_daily_bars(bars)
            store.upsert_auction_profiles([auction_profile("000001", trade_date)])

            common = {
                "db_path": db_path,
                "trade_date": trade_date.isoformat(),
                "horizon": "short_term",
                "strategy_id": "auction_open_breakout_short",
                "symbols": "000001",
                "short_window": "3",
                "medium_window": "5",
                "long_window": "8",
                "volume_window": "5",
                "auction_provider": "local_jingjia",
            }

            screen = run_web_action("morning_screen", common, Path(directory))
            self.assertEqual(screen["morning_screen"].candidate_count, 1)

            plan = run_web_action(
                "trade_plan",
                {**common, "symbol": "000001"},
                Path(directory),
            )
            self.assertEqual(plan["status"], "candidate")
            self.assertIn("09:25", plan["trade_plan"].entry_timing)

    def test_run_web_action_auction_rolling(self) -> None:
        with TemporaryDirectory() as directory:
            db_path = f"{directory}/market.sqlite"
            bars = breakout_bars()
            bars.append(
                replace_price(
                    bars[-1],
                    close=14.0,
                    high=15.0,
                    low=13.8,
                    days_after=1,
                )
            )
            store = SQLiteStore(db_path)
            store.upsert_instruments([Instrument(symbol="000001", name="平安银行", market="A股")])
            store.upsert_daily_bars(bars)
            store.upsert_auction_profiles([auction_profile("000001", bars[-2].trade_date)])

            result = run_web_action(
                "auction_rolling",
                {
                    "start": bars[0].trade_date.isoformat(),
                    "end": bars[-1].trade_date.isoformat(),
                    "db_path": db_path,
                    "output_dir": f"{directory}/rolling",
                    "public_summary": f"{directory}/rolling.md",
                    "auction_provider": "local_jingjia",
                    "min_auction_scores": "none,80",
                    "auction_score_weights": "0",
                    "short_window": "3",
                    "medium_window": "5",
                    "long_window": "8",
                    "volume_window": "5",
                    "breakout_window": "5",
                    "min_volume_ratio": "1.5",
                    "atr_window": "3",
                    "max_holding_bars": "2",
                },
                Path(directory),
            )

            self.assertEqual(len(result["rolling"].windows), 1)
            self.assertEqual(len(result["rolling"].evaluations), 2)
            self.assertTrue(Path(result["public_summary"]["path"]).exists())

    def test_run_web_action_optimize_morning_strategies(self) -> None:
        with TemporaryDirectory() as directory:
            db_path = f"{directory}/market.sqlite"
            seed_optimization_store(SQLiteStore(db_path))

            result = run_web_action(
                "optimize_morning_strategies",
                {
                    "start": "2026-01-01",
                    "end": "2026-01-10",
                    "db_path": db_path,
                    "output_dir": f"{directory}/generated",
                    "public_summary": f"{directory}/summary.md",
                    "profile_output": f"{directory}/profiles.json",
                    "limit": "1",
                    "min_trades": "1",
                    "skip_auction_import": "true",
                },
                Path(directory),
            )

            self.assertEqual(len(result["morning_optimization"].profiles), 9)
            self.assertTrue(Path(result["public_summary"]["path"]).exists())
            self.assertTrue(Path(result["profile_output"]["path"]).exists())
