from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from gupiao.data import Instrument, SQLiteStore
from gupiao.research.morning_optimization import (
    MorningOptimizationConfig,
    auction_provider_range,
    ensure_auction_coverage,
    run_morning_strategy_optimization,
)

from tests.test_morning_workflow import auction_profile, trend_quality_bars


class MorningOptimizationTest(TestCase):
    def test_ensure_auction_coverage_uses_provider_range_before_importing(self) -> None:
        with TemporaryDirectory() as directory:
            store = SQLiteStore(f"{directory}/market.sqlite")
            store.upsert_auction_profiles(
                [
                    auction_profile("000001", date(2026, 1, 1)),
                    auction_profile("000001", date(2026, 1, 31)),
                ]
            )
            config = MorningOptimizationConfig(
                start=date(2026, 1, 1),
                end=date(2026, 1, 31),
                db_path=store.path,
            )

            with patch(
                "gupiao.research.morning_optimization.import_local_auction_cache",
                return_value="imported",
            ) as import_cache:
                self.assertIsNone(ensure_auction_coverage(config, store))
                import_cache.assert_not_called()

            missing_store = SQLiteStore(f"{directory}/missing.sqlite")
            with patch(
                "gupiao.research.morning_optimization.import_local_auction_cache",
                return_value="imported",
            ) as import_cache:
                self.assertEqual(ensure_auction_coverage(config, missing_store), "imported")
                import_cache.assert_called_once()

            self.assertEqual(
                auction_provider_range(store, "local_jingjia"),
                (date(2026, 1, 1), date(2026, 1, 31), 2),
            )

    def test_run_morning_strategy_optimization_writes_profiles_and_summary(self) -> None:
        with TemporaryDirectory() as directory:
            store = SQLiteStore(f"{directory}/market.sqlite")
            seed_optimization_store(store)
            output_dir = Path(directory) / "generated"
            summary_path = Path(directory) / "summary.md"
            profile_path = Path(directory) / "profiles.json"

            result = run_morning_strategy_optimization(
                MorningOptimizationConfig(
                    start=date(2026, 1, 1),
                    end=date(2026, 1, 10),
                    db_path=store.path,
                    output_dir=output_dir,
                    public_summary_path=summary_path,
                    profile_output_path=profile_path,
                    limit=1,
                    import_missing_auction=False,
                    min_trades=1,
                ),
                store=store,
            )

            self.assertEqual(len(result.profiles), 9)
            self.assertTrue(result.result_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertTrue(profile_path.exists())
            profile_payload = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(
                set(profile_payload["profiles"]),
                {"short_term", "mid_short_term", "mid_term"},
            )
            self.assertEqual(
                set(profile_payload["profiles"]["short_term"]),
                {"balanced", "win_rate", "return"},
            )
            self.assertIn("不硬选", summary_path.read_text(encoding="utf-8"))


def seed_optimization_store(store: SQLiteStore) -> None:
    trade_start = date(2026, 1, 1)
    bars = trend_quality_bars("000001", trade_start - timedelta(days=100), count=120)
    store.upsert_instruments([Instrument(symbol="000001", name="样本股", market="A股")])
    store.upsert_daily_bars(bars)
    store.upsert_auction_profiles(
        [
            auction_profile("000001", trade_start + timedelta(days=offset))
            for offset in range(10)
        ]
    )
