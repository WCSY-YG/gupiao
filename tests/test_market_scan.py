from __future__ import annotations

import time
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from gupiao.backtest import BacktestConfig
from gupiao.data import DailyBar, Instrument, SQLiteStore
from gupiao.scan import (
    MarketScanConfig,
    MarketScanResult,
    ScanSymbolResult,
    build_public_summary,
    run_market_scan,
)
from gupiao.scan.market import ranked_candidates
from tests.test_backtest_engine import small_strategy
from tests.test_screening_strategy import breakout_bars


class FakeMarketProvider:
    name = "fake"

    def __init__(self, bars_by_symbol: dict[str, list[DailyBar]], failures: set[str] | None = None):
        self.bars_by_symbol = bars_by_symbol
        self.failures = failures or set()
        self.fetch_calls: list[str] = []

    def list_instruments(self):
        return [
            Instrument(symbol="000001", name="平安银行", market="A股", exchange="SZSE"),
            Instrument(symbol="000002", name="万科A", market="A股", exchange="SZSE"),
            Instrument(symbol="000003", name="空数据", market="A股", exchange="SZSE"),
        ]

    def fetch_daily_bars(self, symbol, start, end, *, adjust="hfq"):
        self.fetch_calls.append(symbol)
        if symbol in self.failures:
            raise RuntimeError("provider unavailable")
        return self.bars_by_symbol.get(symbol, [])


class SlowMarketProvider(FakeMarketProvider):
    def __init__(self, bars_by_symbol: dict[str, list[DailyBar]], slow_symbols: set[str]):
        super().__init__(bars_by_symbol)
        self.slow_symbols = slow_symbols

    def fetch_daily_bars(self, symbol, start, end, *, adjust="hfq"):
        self.fetch_calls.append(symbol)
        if symbol in self.slow_symbols:
            time.sleep(1.0)
        return self.bars_by_symbol.get(symbol, [])


class MarketScanTest(TestCase):
    def test_market_scan_continues_after_symbol_failure_and_writes_summary(self) -> None:
        with TemporaryDirectory() as directory:
            provider = FakeMarketProvider(
                {"000001": breakout_bars(), "000003": []},
                failures={"000002"},
            )
            config = MarketScanConfig(
                start=date(2026, 6, 1),
                end=date(2026, 6, 20),
                db_path=f"{directory}/scan.sqlite",
                output_dir=f"{directory}/generated",
                public_summary_path=f"{directory}/summary.md",
                top=1,
                retries=2,
                retry_sleep_seconds=0,
            )

            result = run_market_scan(
                provider,
                config=config,
                strategy=small_strategy(),
                backtest_config=BacktestConfig(atr_window=3, max_holding_bars=2),
                sleep=lambda _: None,
            )

            self.assertEqual(result.processed, 3)
            self.assertEqual(result.succeeded, 1)
            self.assertEqual(result.failed, 1)
            self.assertEqual(result.no_data, 1)
            self.assertEqual(result.fetched, 2)
            self.assertEqual(result.candidate_count, 1)
            self.assertEqual(provider.fetch_calls.count("000002"), 2)
            self.assertTrue(result.result_path.exists())
            self.assertTrue(result.failure_path.exists())
            summary = result.public_summary_path.read_text(encoding="utf-8")
            self.assertIn("# 全 A 股市场扫描汇总", summary)
            self.assertIn("`000001`", summary)
            self.assertIn("RuntimeError", summary)
            self.assertNotIn('"open"', summary)
            self.assertNotIn('"close"', summary)

    def test_market_scan_reuses_cached_bars(self) -> None:
        with TemporaryDirectory() as directory:
            db_path = f"{directory}/scan.sqlite"
            store = SQLiteStore(db_path)
            store.upsert_daily_bars(breakout_bars())
            provider = FakeMarketProvider({})
            config = MarketScanConfig(
                start=date(2026, 6, 1),
                end=date(2026, 6, 20),
                db_path=db_path,
                output_dir=f"{directory}/generated",
                public_summary_path=f"{directory}/summary.md",
                limit=1,
                retry_sleep_seconds=0,
            )

            result = run_market_scan(
                provider,
                config=config,
                strategy=small_strategy(),
                backtest_config=BacktestConfig(atr_window=3, max_holding_bars=2),
                sleep=lambda _: None,
            )

            self.assertEqual(provider.fetch_calls, [])
            self.assertEqual(result.cached, 1)
            self.assertEqual(result.fetched, 0)
            self.assertEqual(result.results[0].status, "success")

    def test_market_scan_sleeps_after_external_fetch_only(self) -> None:
        with TemporaryDirectory() as directory:
            sleeps: list[float] = []
            provider = FakeMarketProvider({"000001": breakout_bars()})
            config = MarketScanConfig(
                start=date(2026, 6, 1),
                end=date(2026, 6, 20),
                db_path=f"{directory}/scan.sqlite",
                output_dir=f"{directory}/generated",
                public_summary_path=f"{directory}/summary.md",
                limit=1,
                retry_sleep_seconds=0,
                request_sleep_seconds=0.25,
            )

            run_market_scan(
                provider,
                config=config,
                strategy=small_strategy(),
                backtest_config=BacktestConfig(atr_window=3, max_holding_bars=2),
                sleep=sleeps.append,
            )

            self.assertEqual(sleeps, [0.25])

    def test_market_scan_records_request_timeout_and_continues(self) -> None:
        with TemporaryDirectory() as directory:
            provider = SlowMarketProvider({"000002": breakout_bars()}, slow_symbols={"000001"})
            config = MarketScanConfig(
                start=date(2026, 6, 1),
                end=date(2026, 6, 20),
                db_path=f"{directory}/scan.sqlite",
                output_dir=f"{directory}/generated",
                public_summary_path=f"{directory}/summary.md",
                limit=2,
                retries=1,
                retry_sleep_seconds=0,
                request_timeout_seconds=0.01,
            )

            result = run_market_scan(
                provider,
                config=config,
                strategy=small_strategy(),
                backtest_config=BacktestConfig(atr_window=3, max_holding_bars=2),
                sleep=lambda _: None,
            )

            self.assertEqual(result.processed, 2)
            self.assertEqual(result.succeeded, 1)
            self.assertEqual(result.failed, 1)
            self.assertIn("TimeoutError", result.results[0].error or "")
            self.assertEqual(result.results[1].symbol, "000002")

    def test_ranked_candidates_sort_by_score_then_return(self) -> None:
        rows = [
            ScanSymbolResult(
                symbol="000001",
                name="A",
                status="success",
                bars_count=10,
                data_source="fetched",
                candidate_score=80.0,
                total_return=0.20,
            ),
            ScanSymbolResult(
                symbol="000002",
                name="B",
                status="success",
                bars_count=10,
                data_source="fetched",
                candidate_score=90.0,
                total_return=-0.10,
            ),
            ScanSymbolResult(
                symbol="000003",
                name="C",
                status="success",
                bars_count=10,
                data_source="fetched",
                candidate_score=80.0,
                total_return=0.30,
            ),
        ]

        self.assertEqual(
            [row.symbol for row in ranked_candidates(rows)],
            ["000002", "000003", "000001"],
        )

    def test_public_summary_respects_top_limit(self) -> None:
        scan = MarketScanResult(
            started_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
            finished_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
            config=MarketScanConfig(top=1),
            total_instruments=2,
            processed=2,
            succeeded=2,
            failed=0,
            no_data=0,
            fetched=2,
            cached=0,
            candidate_count=2,
            result_path=Path("reports/generated/results.jsonl"),
            failure_path=Path("reports/generated/failures.jsonl"),
            public_summary_path=Path("reports/summaries/latest.md"),
            results=(
                ScanSymbolResult(
                    symbol="000001",
                    name="A",
                    status="success",
                    bars_count=10,
                    data_source="fetched",
                    candidate_score=80.0,
                    total_return=0.20,
                ),
                ScanSymbolResult(
                    symbol="000002",
                    name="B",
                    status="success",
                    bars_count=10,
                    data_source="fetched",
                    candidate_score=90.0,
                    total_return=0.10,
                ),
            ),
        )

        summary = build_public_summary(scan)

        self.assertIn("`000002`", summary)
        self.assertNotIn("`000001`", summary)
