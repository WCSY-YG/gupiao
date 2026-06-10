from __future__ import annotations

from datetime import date
from unittest import TestCase

from gupiao.cli import build_parser, parse_cli_date, positive_int, to_jsonable
from gupiao.data.akshare_provider import (
    AkshareProvider,
    infer_exchange,
    normalize_adjust,
    normalize_symbol,
)
from gupiao.data.schema import DailyBar


class FakeFrame:
    def __init__(self, records):
        self.records = records

    def to_dict(self, orient):
        assert orient == "records"
        return self.records


class FakeAkshare:
    def __init__(self):
        self.daily_args = None

    def stock_info_a_code_name(self):
        return FakeFrame(
            [
                {"code": "000001", "name": "平安银行"},
                {"代码": 600000, "名称": "浦发银行"},
                {"code": "830799", "name": "艾融软件"},
            ]
        )

    def stock_zh_a_hist(self, **kwargs):
        self.daily_args = kwargs
        return FakeFrame(
            [
                {
                    "日期": "2026-06-09",
                    "股票代码": "000001",
                    "开盘": "10.1",
                    "最高": "10.5",
                    "最低": "9.9",
                    "收盘": "10.3",
                    "成交量": "123456",
                    "成交额": "7890000",
                    "换手率": "1.23",
                }
            ]
        )


class AkshareProviderTest(TestCase):
    def test_list_instruments_maps_code_name_and_exchange(self) -> None:
        provider = AkshareProvider(FakeAkshare())

        instruments = list(provider.list_instruments())

        self.assertEqual(
            [instrument.symbol for instrument in instruments],
            ["000001", "600000", "830799"],
        )
        self.assertEqual(
            [instrument.exchange for instrument in instruments],
            ["SZSE", "SSE", "BSE"],
        )
        self.assertEqual(instruments[0].name, "平安银行")
        self.assertEqual(instruments[0].market, "A股")

    def test_fetch_daily_bars_maps_akshare_rows(self) -> None:
        fake = FakeAkshare()
        provider = AkshareProvider(fake)

        bars = list(
            provider.fetch_daily_bars(
                "SZ000001",
                date(2026, 6, 1),
                date(2026, 6, 9),
                adjust="raw",
            )
        )

        self.assertEqual(
            fake.daily_args,
            {
                "symbol": "000001",
                "period": "daily",
                "start_date": "20260601",
                "end_date": "20260609",
                "adjust": "",
            },
        )
        self.assertEqual(
            bars,
            [
                DailyBar(
                    symbol="000001",
                    trade_date=date(2026, 6, 9),
                    open=10.1,
                    high=10.5,
                    low=9.9,
                    close=10.3,
                    volume=123456.0,
                    amount=7890000.0,
                    turnover=1.23,
                    adjust="raw",
                    provider="akshare",
                    fetched_at=bars[0].fetched_at,
                )
            ],
        )

    def test_normalization_helpers(self) -> None:
        self.assertEqual(normalize_symbol("000001.SZ"), "000001")
        self.assertEqual(normalize_symbol("SH600000"), "600000")
        self.assertEqual(infer_exchange("600000"), "SSE")
        self.assertEqual(infer_exchange("300750"), "SZSE")
        self.assertEqual(infer_exchange("830799"), "BSE")
        self.assertEqual(normalize_adjust("raw"), "")
        self.assertEqual(normalize_adjust("hfq"), "hfq")

    def test_cli_helpers_and_json_conversion(self) -> None:
        self.assertEqual(parse_cli_date("2026-06-10"), date(2026, 6, 10))
        self.assertEqual(positive_int("5"), 5)
        self.assertEqual(to_jsonable({"date": date(2026, 6, 10)}), {"date": "2026-06-10"})

    def test_cli_data_arguments_parse_without_fetching(self) -> None:
        args = build_parser().parse_args(
            [
                "data",
                "daily",
                "000001",
                "--start",
                "2026-06-01",
                "--end",
                "2026-06-09",
                "--limit",
                "5",
            ]
        )

        self.assertEqual(args.symbol, "000001")
        self.assertEqual(args.start, date(2026, 6, 1))
        self.assertEqual(args.end, date(2026, 6, 9))
        self.assertEqual(args.limit, 5)
