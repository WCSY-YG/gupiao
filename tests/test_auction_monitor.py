from __future__ import annotations

from datetime import date, datetime
from tempfile import TemporaryDirectory
from unittest import TestCase

from gupiao.data import (
    AuctionMinuteBar,
    AuctionMonitorConfig,
    DailyBar,
    Instrument,
    SQLiteStore,
    monitor_live_auction,
)


class FakeAuctionMonitorProvider:
    name = "fake"

    def __init__(
        self,
        *,
        bars_by_symbol: dict[str, list[DailyBar]] | None = None,
        minutes_by_symbol: dict[str, list[AuctionMinuteBar]] | None = None,
        minute_errors: set[str] | None = None,
    ) -> None:
        self.bars_by_symbol = bars_by_symbol or {}
        self.minutes_by_symbol = minutes_by_symbol or {}
        self.minute_errors = minute_errors or set()
        self.daily_calls: list[tuple[str, date, date, str]] = []
        self.minute_calls: list[str] = []

    def list_instruments(self):
        return [
            Instrument(symbol="000001", name="平安银行", market="A股"),
            Instrument(symbol="000002", name="万科A", market="A股"),
        ]

    def fetch_daily_bars(self, symbol, start, end, *, adjust="hfq"):
        self.daily_calls.append((symbol, start, end, adjust))
        return [
            bar
            for bar in self.bars_by_symbol.get(symbol, [])
            if start <= bar.trade_date <= end and (bar.adjust or "") == adjust
        ]

    def fetch_pre_market_minutes(self, symbol, *, start_time="09:15:00", end_time="09:25:00"):
        del start_time, end_time
        self.minute_calls.append(symbol)
        if symbol in self.minute_errors:
            raise RuntimeError("pre-market endpoint failed")
        return self.minutes_by_symbol.get(symbol, [])


class AuctionMonitorTest(TestCase):
    def test_monitor_writes_today_auction_and_previous_daily_context(self) -> None:
        with TemporaryDirectory() as directory:
            db_path = f"{directory}/market.sqlite"
            store = SQLiteStore(db_path)
            provider = FakeAuctionMonitorProvider(
                bars_by_symbol={"000001": raw_bars("000001")},
                minutes_by_symbol={"000001": auction_minutes("000001", date(2026, 6, 10))},
            )

            result = monitor_live_auction(
                provider,
                store=store,
                config=AuctionMonitorConfig(
                    db_path=db_path,
                    trade_date=date(2026, 6, 10),
                    symbols=("000001",),
                    average_volume_window=2,
                    daily_lookback_days=10,
                    retries=1,
                ),
                sleep=lambda _: None,
            )

            self.assertEqual(result.succeeded, 1)
            self.assertEqual(result.auction_minutes_written, 2)
            self.assertEqual(result.auction_profiles_written, 1)
            self.assertEqual(result.daily_rows_written, 3)
            self.assertEqual(provider.daily_calls[0][2], date(2026, 6, 9))
            self.assertEqual(provider.daily_calls[0][3], "raw")

            daily_bars = store.get_daily_bars("000001", adjust="raw")
            self.assertEqual([bar.trade_date for bar in daily_bars], [
                date(2026, 6, 5),
                date(2026, 6, 8),
                date(2026, 6, 9),
            ])
            minutes = store.get_auction_minutes(
                "000001",
                start=date(2026, 6, 10),
                end=date(2026, 6, 10),
                provider="akshare_live",
            )
            self.assertEqual(len(minutes), 2)
            profiles = store.get_auction_profiles(
                "000001",
                start=date(2026, 6, 10),
                end=date(2026, 6, 10),
                provider="akshare_live",
            )
            self.assertEqual(len(profiles), 1)
            self.assertAlmostEqual(profiles[0].previous_close or 0.0, 10.5)
            self.assertEqual(result.results[0].previous_open, 10.2)
            self.assertEqual(result.results[0].previous_close, 10.5)

    def test_monitor_reuses_cached_daily_context_without_refetching(self) -> None:
        with TemporaryDirectory() as directory:
            db_path = f"{directory}/market.sqlite"
            store = SQLiteStore(db_path)
            store.upsert_daily_bars(raw_bars("000001"))
            provider = FakeAuctionMonitorProvider(
                minutes_by_symbol={"000001": auction_minutes("000001", date(2026, 6, 10))},
            )

            result = monitor_live_auction(
                provider,
                store=store,
                config=AuctionMonitorConfig(
                    db_path=db_path,
                    trade_date=date(2026, 6, 10),
                    symbols=("000001",),
                    retries=1,
                ),
                sleep=lambda _: None,
            )

            self.assertEqual(result.succeeded, 1)
            self.assertEqual(provider.daily_calls, [])
            self.assertEqual(result.daily_rows_written, 0)

    def test_monitor_date_mismatch_does_not_write_rows(self) -> None:
        with TemporaryDirectory() as directory:
            db_path = f"{directory}/market.sqlite"
            store = SQLiteStore(db_path)
            provider = FakeAuctionMonitorProvider(
                bars_by_symbol={"000001": raw_bars("000001")},
                minutes_by_symbol={"000001": auction_minutes("000001", date(2026, 6, 10))},
            )

            result = monitor_live_auction(
                provider,
                store=store,
                config=AuctionMonitorConfig(
                    db_path=db_path,
                    trade_date=date(2026, 6, 11),
                    symbols=("000001",),
                    retries=1,
                ),
                sleep=lambda _: None,
            )

            self.assertEqual(result.date_mismatch, 1)
            self.assertEqual(result.auction_minutes_written, 0)
            self.assertEqual(result.auction_profiles_written, 0)
            self.assertEqual(store.get_auction_profiles("000001"), [])
            self.assertEqual(store.get_auction_minutes("000001"), [])

    def test_monitor_one_symbol_failure_does_not_stop_batch(self) -> None:
        with TemporaryDirectory() as directory:
            db_path = f"{directory}/market.sqlite"
            provider = FakeAuctionMonitorProvider(
                bars_by_symbol={
                    "000001": raw_bars("000001"),
                    "000002": raw_bars("000002"),
                },
                minutes_by_symbol={"000001": auction_minutes("000001", date(2026, 6, 10))},
                minute_errors={"000002"},
            )

            result = monitor_live_auction(
                provider,
                config=AuctionMonitorConfig(
                    db_path=db_path,
                    trade_date=date(2026, 6, 10),
                    symbols=("000001", "000002"),
                    retries=1,
                ),
                sleep=lambda _: None,
            )

            self.assertEqual(result.processed, 2)
            self.assertEqual(result.succeeded, 1)
            self.assertEqual(result.failed, 1)
            self.assertEqual([item.status for item in result.results], ["success", "failed"])


def raw_bars(symbol: str) -> list[DailyBar]:
    return [
        DailyBar(
            symbol=symbol,
            trade_date=date(2026, 6, 5),
            open=9.8,
            high=10.1,
            low=9.7,
            close=10.0,
            volume=10_000.0,
            adjust="raw",
            provider="fake",
        ),
        DailyBar(
            symbol=symbol,
            trade_date=date(2026, 6, 8),
            open=10.0,
            high=10.4,
            low=9.9,
            close=10.2,
            volume=12_000.0,
            adjust="raw",
            provider="fake",
        ),
        DailyBar(
            symbol=symbol,
            trade_date=date(2026, 6, 9),
            open=10.2,
            high=10.6,
            low=10.1,
            close=10.5,
            volume=14_000.0,
            adjust="raw",
            provider="fake",
        ),
        DailyBar(
            symbol=symbol,
            trade_date=date(2026, 6, 10),
            open=10.7,
            high=10.8,
            low=10.3,
            close=10.4,
            volume=13_000.0,
            adjust="raw",
            provider="fake",
        ),
    ]


def auction_minutes(symbol: str, trade_date: date) -> list[AuctionMinuteBar]:
    return [
        AuctionMinuteBar(
            symbol=symbol,
            trade_time=datetime(trade_date.year, trade_date.month, trade_date.day, 9, 24),
            open=10.5,
            close=10.6,
            high=10.6,
            low=10.5,
            volume=1000.0,
            amount=1_060_000.0,
            latest_price=10.6,
            provider="fake",
        ),
        AuctionMinuteBar(
            symbol=symbol,
            trade_time=datetime(trade_date.year, trade_date.month, trade_date.day, 9, 25),
            open=10.6,
            close=10.7,
            high=10.72,
            low=10.58,
            volume=1500.0,
            amount=1_605_000.0,
            latest_price=10.7,
            provider="fake",
        ),
    ]
