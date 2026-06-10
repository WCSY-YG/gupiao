from __future__ import annotations

from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from gupiao.data import AuctionProfile, SQLiteStore
from gupiao.data.local_auction_cache import (
    bid_ask_imbalance,
    date_from_member,
    insert_auction_profiles,
    parse_auction_csv,
    parse_hhmmss_to_code,
)


class LocalAuctionCacheTest(TestCase):
    def test_parse_auction_csv_builds_profiles_with_imbalance(self) -> None:
        csv_text = "\n".join(
            [
                "security_id,md_date,md_time,min,max,pre_close,last,open,num_trades,total_volume_trade,total_value_trade,bid1,bid2,bid_size1,bid_size2,ask1,ask2,ask_size1,ask_size2",
                "000001.SZ,20260506,92457000,10.34,12.64,11.49,11.50,0.0,0,0,0,11.50,0.0,900,0,11.50,0.0,900,300",
                "000001.SZ,20260506,92503000,10.34,12.64,11.49,11.55,11.55,300,1000,1155000,11.55,11.54,700,300,11.56,11.57,200,100",
                "600000.SH,20260506,92503000,8.34,10.20,9.27,9.20,9.20,100,2000,1840000,9.20,9.19,50,50,9.21,9.22,300,300",
            ]
        )

        parsed = parse_auction_csv(
            StringIO(csv_text),
            trade_date=date(2026, 5, 6),
            provider="local_jingjia",
            start_code=parse_hhmmss_to_code("09:15:00"),
            end_code=parse_hhmmss_to_code("09:25:03"),
            average_daily_volume_by_symbol={"000001": 100_000.0},
        )

        self.assertEqual(parsed.rows_seen, 3)
        self.assertEqual(parsed.rows_in_window, 3)
        self.assertEqual(len(parsed.profiles), 2)
        first = parsed.profiles[0]
        self.assertEqual(first.symbol, "000001")
        self.assertEqual(first.volume, 100_000.0)
        self.assertAlmostEqual(first.gap_pct or 0.0, (11.55 / 11.49) - 1)
        self.assertAlmostEqual(first.volume_ratio_to_daily or 0.0, 1.0)
        self.assertAlmostEqual(first.bid_ask_imbalance or 0.0, 700 / 1300)
        self.assertGreater(first.strength_score, 50.0)

    def test_insert_auction_profiles_can_ignore_conflicts(self) -> None:
        with TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "market.sqlite")
            store.init_schema()
            profile = AuctionProfile(
                symbol="000001",
                trade_date=date(2026, 5, 6),
                auction_time=parse_auction_time("2026-05-06T09:25:03"),
                indicative_price=10.0,
                open=10.0,
                high=10.0,
                low=9.9,
                volume=1000.0,
                strength_score=60.0,
                provider="local_jingjia",
            )
            replacement = AuctionProfile(
                symbol="000001",
                trade_date=date(2026, 5, 6),
                auction_time=parse_auction_time("2026-05-06T09:25:03"),
                indicative_price=11.0,
                open=11.0,
                high=11.0,
                low=10.9,
                volume=2000.0,
                strength_score=80.0,
                provider="local_jingjia",
            )

            with store.connect() as connection:
                self.assertEqual(
                    insert_auction_profiles(connection, (profile,), conflict="ignore"),
                    1,
                )
                self.assertEqual(
                    insert_auction_profiles(connection, (replacement,), conflict="ignore"),
                    0,
                )
                connection.commit()

            stored = store.get_auction_profiles("000001", provider="local_jingjia")
            self.assertEqual(stored[0].indicative_price, 10.0)

    def test_date_and_imbalance_helpers(self) -> None:
        self.assertEqual(date_from_member("202605/20260506.csv"), date(2026, 5, 6))
        self.assertAlmostEqual(bid_ask_imbalance(75, 25) or 0.0, 0.5)
        self.assertIsNone(bid_ask_imbalance(0, 0))


def parse_auction_time(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value)
