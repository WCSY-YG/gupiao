from __future__ import annotations

from tempfile import TemporaryDirectory
from unittest import TestCase

from gupiao.backtest import BacktestConfig, run_breakout_backtest
from gupiao.signals import build_breakout_signal
from gupiao.web import build_dashboard_html, write_dashboard_html
from tests.test_backtest_engine import small_strategy
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
        )

        self.assertIn("<!doctype html>", html)
        self.assertIn("候选股与指标", html)
        self.assertIn("买卖点计划", html)
        self.assertIn("权益曲线", html)
        self.assertIn("<svg", html)

    def test_write_dashboard_html(self) -> None:
        with TemporaryDirectory() as directory:
            path = write_dashboard_html(f"{directory}/dashboard.html", "<html></html>")

            self.assertEqual(path.read_text(encoding="utf-8"), "<html></html>")
