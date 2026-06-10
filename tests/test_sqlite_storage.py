from __future__ import annotations

from datetime import date, datetime
from tempfile import TemporaryDirectory
from unittest import TestCase

from gupiao.data import AuctionProfile, DailyBar, Instrument, SQLiteStore


class SQLiteStoreTest(TestCase):
    def test_upsert_and_list_instruments(self) -> None:
        with TemporaryDirectory() as directory:
            store = SQLiteStore(f"{directory}/gupiao.sqlite")

            count = store.upsert_instruments(
                [
                    Instrument(
                        symbol="000001",
                        name="平安银行",
                        market="A股",
                        exchange="SZSE",
                        industry="银行",
                        listed_date=date(1991, 4, 3),
                    )
                ]
            )

            self.assertEqual(count, 1)
            self.assertEqual(
                store.list_instruments(),
                [
                    Instrument(
                        symbol="000001",
                        name="平安银行",
                        market="A股",
                        exchange="SZSE",
                        industry="银行",
                        listed_date=date(1991, 4, 3),
                    )
                ],
            )

    def test_daily_bar_upsert_updates_existing_row(self) -> None:
        with TemporaryDirectory() as directory:
            store = SQLiteStore(f"{directory}/gupiao.sqlite")
            fetched_at = datetime(2026, 6, 10, 9, 15)

            first = DailyBar(
                symbol="000001",
                trade_date=date(2026, 6, 9),
                open=10.0,
                high=10.5,
                low=9.9,
                close=10.2,
                volume=1000.0,
                amount=10000.0,
                turnover=1.0,
                adjust="hfq",
                provider="akshare",
                fetched_at=fetched_at,
            )
            second = DailyBar(
                symbol="000001",
                trade_date=date(2026, 6, 9),
                open=10.1,
                high=10.6,
                low=10.0,
                close=10.4,
                volume=1200.0,
                amount=12000.0,
                turnover=1.2,
                adjust="hfq",
                provider="akshare",
                fetched_at=fetched_at,
            )

            self.assertEqual(store.upsert_daily_bars([first]), 1)
            self.assertEqual(store.upsert_daily_bars([second]), 1)

            bars = store.get_daily_bars(
                "000001",
                start=date(2026, 6, 1),
                end=date(2026, 6, 30),
                adjust="hfq",
            )
            self.assertEqual(bars, [second])

    def test_auction_profile_upsert_and_query(self) -> None:
        with TemporaryDirectory() as directory:
            store = SQLiteStore(f"{directory}/gupiao.sqlite")
            profile = AuctionProfile(
                symbol="000001",
                trade_date=date(2026, 5, 6),
                auction_time=datetime(2026, 5, 6, 9, 25, 3),
                indicative_price=11.55,
                open=11.55,
                high=11.6,
                low=11.5,
                volume=100_000.0,
                amount=1_155_000.0,
                latest_price=11.55,
                previous_close=11.49,
                gap_pct=(11.55 / 11.49) - 1,
                range_pct=(11.6 / 11.5) - 1,
                volume_ratio_to_daily=1.2,
                bid_ask_imbalance=0.4,
                strength_score=88.0,
                provider="local_jingjia",
            )

            self.assertEqual(store.upsert_auction_profiles([profile]), 1)

            profiles = store.get_auction_profiles(
                "000001",
                start=date(2026, 5, 1),
                end=date(2026, 5, 31),
                provider="local_jingjia",
            )
            self.assertEqual(profiles, [profile])
