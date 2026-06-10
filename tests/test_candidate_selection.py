from __future__ import annotations

from datetime import datetime, timedelta
from tempfile import TemporaryDirectory
from unittest import TestCase

from gupiao.data import AuctionProfile, DailyBar, Instrument, SQLiteStore
from gupiao.strategies import CandidateScreenConfig, run_cached_candidate_screen

from tests.test_backtest_engine import small_strategy
from tests.test_screening_strategy import breakout_bars


class CandidateSelectionTest(TestCase):
    def test_cached_candidate_screen_respects_as_of_and_injects_auction(self) -> None:
        with TemporaryDirectory() as directory:
            store = SQLiteStore(f"{directory}/screen.sqlite")
            store.upsert_instruments(
                [
                    Instrument(symbol="000001", name="平安银行", market="A股"),
                    Instrument(symbol="000002", name="空数据", market="A股"),
                ]
            )
            bars = breakout_bars()
            future = daily_bar_after(bars[-1])
            store.upsert_daily_bars([*bars, future])
            store.upsert_auction_profiles([auction_profile("000001", bars[-1].trade_date)])

            result = run_cached_candidate_screen(
                config=CandidateScreenConfig(
                    db_path=store.path,
                    as_of=bars[-1].trade_date,
                    lookback=20,
                    top=5,
                    auction_provider="local_jingjia",
                ),
                store=store,
                strategy=small_strategy(),
            )

            self.assertEqual(result.processed, 2)
            self.assertEqual(result.no_data, 1)
            self.assertEqual(result.candidate_count, 1)
            self.assertEqual(result.candidates[0].symbol, "000001")
            self.assertEqual(result.candidates[0].latest_trade_date, bars[-1].trade_date)
            assert result.candidates[0].candidate is not None
            self.assertIn("auction_strength_score", result.candidates[0].candidate.metrics)

    def test_cached_candidate_screen_returns_empty_candidates_for_empty_cache(self) -> None:
        with TemporaryDirectory() as directory:
            store = SQLiteStore(f"{directory}/screen.sqlite")

            result = run_cached_candidate_screen(
                config=CandidateScreenConfig(db_path=store.path, as_of=None),
                store=store,
                strategy=small_strategy(),
            )

            self.assertEqual(result.processed, 0)
            self.assertEqual(result.candidate_count, 0)
            self.assertEqual(result.candidates, ())


def daily_bar_after(bar: DailyBar) -> DailyBar:
    return DailyBar(
        symbol=bar.symbol,
        trade_date=bar.trade_date + timedelta(days=1),
        open=bar.open,
        high=bar.high + 1,
        low=bar.low,
        close=bar.close + 1,
        volume=bar.volume,
        amount=bar.amount,
        turnover=bar.turnover,
        adjust=bar.adjust,
        provider=bar.provider,
    )


def auction_profile(symbol: str, trade_date) -> AuctionProfile:
    return AuctionProfile(
        symbol=symbol,
        trade_date=trade_date,
        auction_time=datetime.combine(trade_date, datetime.min.time()).replace(hour=9, minute=25),
        indicative_price=12.6,
        open=12.6,
        high=12.7,
        low=12.5,
        volume=100_000.0,
        previous_close=12.35,
        gap_pct=0.02,
        range_pct=0.016,
        volume_ratio_to_daily=1.2,
        bid_ask_imbalance=0.4,
        strength_score=90.0,
        provider="local_jingjia",
    )
