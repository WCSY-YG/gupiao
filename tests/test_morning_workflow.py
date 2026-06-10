from __future__ import annotations

from datetime import date, datetime, timedelta
from tempfile import TemporaryDirectory
from unittest import TestCase

from gupiao.backtest import BacktestConfig, run_morning_plan_backtest
from gupiao.data import AuctionProfile, DailyBar, Instrument, SQLiteStore
from gupiao.strategies import MorningScreenConfig, build_screening_strategy, run_morning_screen

from tests.test_screening_strategy import breakout_bars


class MorningWorkflowTest(TestCase):
    def test_morning_screen_uses_prior_daily_bars_and_same_day_auction(self) -> None:
        with TemporaryDirectory() as directory:
            store = SQLiteStore(f"{directory}/morning.sqlite")
            bars = breakout_bars()
            trade_date = bars[-1].trade_date + timedelta(days=1)
            future_bar = daily_bar(
                symbol="000001",
                trade_date=trade_date,
                open=100.0,
                high=110.0,
                low=99.0,
                close=108.0,
                volume=99_000.0,
            )
            store.upsert_instruments([Instrument(symbol="000001", name="平安银行", market="A股")])
            store.upsert_daily_bars([*bars, future_bar])
            store.upsert_auction_profiles([auction_profile("000001", trade_date)])

            result = run_morning_screen(
                config=MorningScreenConfig(
                    db_path=store.path,
                    trade_date=trade_date,
                    horizon="short_term",
                    strategy_id="auction_open_breakout_short",
                    symbols=("000001",),
                ),
                store=store,
                strategy=build_screening_strategy(
                    "auction_open_breakout_short",
                    short_window=3,
                    medium_window=5,
                    long_window=8,
                    volume_window=5,
                    min_auction_score=55.0,
                ),
            )

            self.assertEqual(result.candidate_count, 1)
            row = result.candidates[0]
            self.assertEqual(row.latest_daily_date, bars[-1].trade_date)
            assert row.candidate is not None
            self.assertEqual(row.candidate.trade_date, trade_date)
            self.assertEqual(row.candidate.metrics["previous_close"], bars[-1].close)
            self.assertNotEqual(row.candidate.metrics["previous_close"], future_bar.close)
            assert row.trade_plan is not None
            self.assertEqual(row.trade_plan.decision_time, "morning_auction")
            self.assertEqual(row.trade_plan.entry_date, trade_date)
            self.assertIn("09:25", row.trade_plan.entry_timing)
            self.assertEqual(row.trade_plan.entry_price_source, "auction_indicative_price")

    def test_short_term_requires_auction_but_mid_term_can_continue_without_it(self) -> None:
        with TemporaryDirectory() as directory:
            store = SQLiteStore(f"{directory}/morning.sqlite")
            trade_date = date(2026, 6, 10)
            bars = trend_quality_bars("000001", trade_date - timedelta(days=70), count=70)
            store.upsert_instruments([Instrument(symbol="000001", name="趋势股", market="A股")])
            store.upsert_daily_bars(bars)

            short_result = run_morning_screen(
                config=MorningScreenConfig(
                    db_path=store.path,
                    trade_date=trade_date,
                    horizon="short_term",
                    symbols=("000001",),
                ),
                store=store,
            )
            self.assertEqual(short_result.no_auction, 1)

            mid_result = run_morning_screen(
                config=MorningScreenConfig(
                    db_path=store.path,
                    trade_date=trade_date,
                    horizon="mid_term",
                    strategy_id="trend_quality_mid",
                    symbols=("000001",),
                ),
                store=store,
            )
            self.assertEqual(mid_result.no_auction, 0)
            self.assertEqual(mid_result.candidate_count, 1)
            assert mid_result.candidates[0].trade_plan is not None
            self.assertEqual(mid_result.candidates[0].trade_plan.horizon, "mid_term")

    def test_morning_backtest_enters_on_trade_date_open(self) -> None:
        bars = breakout_bars()
        entry_date = bars[-1].trade_date + timedelta(days=1)
        bars.append(
            daily_bar(
                symbol="000001",
                trade_date=entry_date,
                open=12.6,
                high=12.9,
                low=12.3,
                close=12.8,
                volume=3_000.0,
            )
        )
        bars.append(
            daily_bar(
                symbol="000001",
                trade_date=entry_date + timedelta(days=1),
                open=13.0,
                high=15.5,
                low=12.9,
                close=15.0,
                volume=4_000.0,
            )
        )

        result = run_morning_plan_backtest(
            "000001",
            bars,
            strategy=build_screening_strategy(
                "auction_open_breakout_short",
                short_window=3,
                medium_window=5,
                long_window=8,
                volume_window=5,
                min_auction_score=55.0,
            ),
            config=BacktestConfig(atr_window=3, slippage_rate=0.001, max_holding_bars=3),
            auction_profiles={entry_date: auction_profile("000001", entry_date)},
        )

        self.assertEqual(result.trade_count, 1)
        self.assertEqual(result.trades[0].entry_date, entry_date)
        self.assertAlmostEqual(result.trades[0].entry_price, 12.6 * 1.001)
        self.assertTrue(any("trade-date open" in item for item in result.assumptions))


def auction_profile(symbol: str, trade_date: date) -> AuctionProfile:
    return AuctionProfile(
        symbol=symbol,
        trade_date=trade_date,
        auction_time=datetime.combine(trade_date, datetime.min.time()).replace(hour=9, minute=25),
        indicative_price=12.7,
        open=12.6,
        high=12.8,
        low=12.5,
        volume=100_000.0,
        amount=1_270_000.0,
        previous_close=12.4,
        gap_pct=0.024,
        range_pct=0.024,
        volume_ratio_to_daily=0.02,
        bid_ask_imbalance=0.35,
        strength_score=88.0,
        provider="local_jingjia",
    )


def daily_bar(
    *,
    symbol: str,
    trade_date: date,
    open: float,
    high: float,
    low: float,
    close: float,
    volume: float,
) -> DailyBar:
    return DailyBar(
        symbol=symbol,
        trade_date=trade_date,
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
        amount=volume * close,
        turnover=1.0,
        adjust="hfq",
        provider="test",
    )


def trend_quality_bars(symbol: str, start: date, *, count: int) -> list[DailyBar]:
    bars: list[DailyBar] = []
    for index in range(count):
        close = 10.0 + (index * 0.05)
        bars.append(
            daily_bar(
                symbol=symbol,
                trade_date=start + timedelta(days=index),
                open=close - 0.03,
                high=close + 0.06,
                low=close - 0.08,
                close=close,
                volume=2_000.0 + index,
            )
        )
    return bars
