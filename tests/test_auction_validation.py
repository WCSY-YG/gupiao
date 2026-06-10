from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from gupiao.backtest import BacktestConfig
from gupiao.data import AuctionProfile, Instrument, SQLiteStore
from gupiao.research import (
    AuctionStrategyComparisonConfig,
    build_public_summary,
    run_auction_strategy_comparison,
)
from gupiao.strategies import MovingAverageVolumeBreakoutStrategy

from tests.test_backtest_engine import replace_price, small_strategy
from tests.test_screening_strategy import breakout_bars


class AuctionValidationTest(TestCase):
    def test_run_auction_strategy_comparison_writes_public_summary(self) -> None:
        with TemporaryDirectory() as directory:
            store = SQLiteStore(f"{directory}/market.sqlite")
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
            store.upsert_instruments(
                [Instrument(symbol="000001", name="平安银行", market="A股")]
            )
            store.upsert_daily_bars(bars)
            store.upsert_auction_profiles(
                [
                    AuctionProfile(
                        symbol="000001",
                        trade_date=bars[-2].trade_date,
                        auction_time=datetime(2026, 6, 10, 9, 25, 3),
                        indicative_price=12.6,
                        open=12.6,
                        high=12.7,
                        low=12.5,
                        volume=100_000.0,
                        gap_pct=0.02,
                        range_pct=0.016,
                        volume_ratio_to_daily=1.2,
                        bid_ask_imbalance=0.4,
                        strength_score=90.0,
                        provider="local_jingjia",
                    )
                ]
            )
            config = AuctionStrategyComparisonConfig(
                start=bars[0].trade_date,
                end=bars[-1].trade_date,
                db_path=f"{directory}/market.sqlite",
                output_dir=f"{directory}/generated",
                public_summary_path=f"{directory}/summary.md",
                top=5,
            )

            result = run_auction_strategy_comparison(
                config=config,
                store=store,
                baseline_strategy=small_strategy(),
                auction_strategy=MovingAverageVolumeBreakoutStrategy(
                    short_window=3,
                    medium_window=5,
                    long_window=8,
                    volume_window=5,
                    breakout_window=5,
                    min_volume_ratio=1.5,
                    min_auction_score=80.0,
                ),
                backtest_config=BacktestConfig(atr_window=3, max_holding_bars=2),
            )

            self.assertEqual(result.processed, 1)
            self.assertEqual(result.succeeded, 1)
            self.assertTrue(result.result_path.exists())
            summary = result.public_summary_path.read_text(encoding="utf-8")
            self.assertIn("# 竞价增强策略对比汇总", summary)
            self.assertIn("`000001`", summary)
            self.assertNotIn('"open"', summary)
            self.assertNotIn('"close"', summary)

    def test_public_summary_handles_small_sample_guidance(self) -> None:
        with TemporaryDirectory() as directory:
            config = AuctionStrategyComparisonConfig(
                start=breakout_bars()[0].trade_date,
                end=breakout_bars()[-1].trade_date,
                output_dir=f"{directory}/generated",
                public_summary_path=f"{directory}/summary.md",
            )

        summary = build_public_summary(
            run_empty_comparison(config)
        )

        self.assertIn("样本覆盖偏小", summary)


def run_empty_comparison(config: AuctionStrategyComparisonConfig):
    from datetime import UTC

    from gupiao.research.auction_validation import AuctionStrategyComparisonResult

    return AuctionStrategyComparisonResult(
        started_at=datetime(2026, 6, 10, tzinfo=UTC),
        finished_at=datetime(2026, 6, 10, tzinfo=UTC),
        config=config,
        total_symbols=0,
        processed=0,
        succeeded=0,
        failed=0,
        no_data=0,
        improved=0,
        worsened=0,
        result_path=Path(config.output_dir) / "results.jsonl",
        failure_path=Path(config.output_dir) / "failures.jsonl",
        public_summary_path=Path(config.public_summary_path),
        results=(),
    )
