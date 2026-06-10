from __future__ import annotations

from tempfile import TemporaryDirectory
from unittest import TestCase

from gupiao.backtest import BacktestConfig, run_breakout_backtest
from gupiao.reports import build_markdown_report, format_pct, write_markdown_report
from gupiao.signals import build_breakout_signal
from tests.test_backtest_engine import small_strategy
from tests.test_screening_strategy import breakout_bars


class ReportsTest(TestCase):
    def test_build_markdown_report_contains_core_sections(self) -> None:
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

        report = build_markdown_report(
            title="MVP 策略报告",
            candidate=candidate,
            signal=signal,
            backtest=backtest,
        )

        self.assertIn("# MVP 策略报告", report)
        self.assertIn("## 候选股与命中原因", report)
        self.assertIn("## 买卖点计划", report)
        self.assertIn("## 回测结果", report)
        self.assertIn("## 风险提示与假设", report)

    def test_write_markdown_report(self) -> None:
        with TemporaryDirectory() as directory:
            path = write_markdown_report(f"{directory}/report.md", "# report\n")

            self.assertEqual(path.read_text(encoding="utf-8"), "# report\n")

    def test_format_pct(self) -> None:
        self.assertEqual(format_pct(0.1234), "12.34%")
