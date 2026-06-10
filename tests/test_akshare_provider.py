from __future__ import annotations

from datetime import date
from unittest import TestCase

from gupiao.cli import build_parser, parse_cli_date, positive_float, positive_int, to_jsonable
from gupiao.data.akshare_provider import (
    AkshareProvider,
    infer_exchange,
    normalize_adjust,
    normalize_symbol,
)
from gupiao.data.schema import AuctionMinuteBar, DailyBar
from gupiao.scan import DEFAULT_SCAN_END, DEFAULT_SCAN_START


class FakeFrame:
    def __init__(self, records):
        self.records = records

    def to_dict(self, orient):
        assert orient == "records"
        return self.records


class FakeAkshare:
    def __init__(self):
        self.daily_args = None
        self.pre_market_args = None

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

    def stock_zh_a_hist_pre_min_em(self, **kwargs):
        self.pre_market_args = kwargs
        return FakeFrame(
            [
                {
                    "时间": "2026-06-10 09:25:00",
                    "开盘": "10.20",
                    "收盘": "10.35",
                    "最高": "10.40",
                    "最低": "10.18",
                    "成交量": "1200",
                    "成交额": "1242000",
                    "最新价": "10.35",
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

    def test_fetch_pre_market_minutes_maps_akshare_rows(self) -> None:
        fake = FakeAkshare()
        provider = AkshareProvider(fake)

        minutes = list(
            provider.fetch_pre_market_minutes(
                "SZ000001",
                start_time="09:15:00",
                end_time="09:25:00",
            )
        )

        self.assertEqual(
            fake.pre_market_args,
            {
                "symbol": "000001",
                "start_time": "09:15:00",
                "end_time": "09:25:00",
            },
        )
        self.assertEqual(
            minutes,
            [
                AuctionMinuteBar(
                    symbol="000001",
                    trade_time=minutes[0].trade_time,
                    open=10.2,
                    close=10.35,
                    high=10.4,
                    low=10.18,
                    volume=1200.0,
                    amount=1242000.0,
                    latest_price=10.35,
                    provider="akshare",
                    fetched_at=minutes[0].fetched_at,
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
        self.assertEqual(positive_float("0.5"), 0.5)
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

    def test_cli_pre_market_arguments_parse_without_fetching(self) -> None:
        args = build_parser().parse_args(
            [
                "data",
                "pre-market",
                "000001",
                "--start-time",
                "09:15:00",
                "--end-time",
                "09:25:00",
                "--limit",
                "2",
            ]
        )

        self.assertEqual(args.symbol, "000001")
        self.assertEqual(args.start_time, "09:15:00")
        self.assertEqual(args.end_time, "09:25:00")
        self.assertEqual(args.limit, 2)

    def test_cli_scan_market_defaults_parse_without_fetching(self) -> None:
        args = build_parser().parse_args(["scan", "market"])

        self.assertEqual(args.start, DEFAULT_SCAN_START)
        self.assertEqual(args.end, DEFAULT_SCAN_END)
        self.assertEqual(args.adjust, "hfq")
        self.assertEqual(args.db, "data/cache/market_scan.sqlite")
        self.assertEqual(args.output, "reports/generated/market_scan/latest")
        self.assertEqual(args.public_summary, "reports/summaries/latest_market_scan.md")
        self.assertEqual(args.top, 30)
        self.assertEqual(args.retries, 3)
        self.assertEqual(args.request_sleep, 0.0)
        self.assertEqual(args.request_timeout, 60.0)
        self.assertIsNone(args.auction_provider)
        self.assertIsNone(args.min_auction_score)
        self.assertEqual(args.auction_score_weight, 0.15)

    def test_cli_refresh_market_cache_arguments_parse_without_fetching(self) -> None:
        args = build_parser().parse_args(
            [
                "data",
                "refresh-market-cache",
                "--db",
                "data/cache/market_scan.sqlite",
                "--end",
                "2026-06-10",
                "--limit",
                "10",
                "--request-sleep",
                "0.2",
                "--dry-run",
            ]
        )

        self.assertEqual(args.db, "data/cache/market_scan.sqlite")
        self.assertEqual(args.end, date(2026, 6, 10))
        self.assertEqual(args.limit, 10)
        self.assertEqual(args.request_sleep, 0.2)
        self.assertTrue(args.dry_run)

    def test_cli_scan_market_auction_arguments_parse_without_fetching(self) -> None:
        args = build_parser().parse_args(
            [
                "scan",
                "market",
                "--auction-provider",
                "local_jingjia",
                "--min-auction-score",
                "65",
                "--auction-score-weight",
                "0.25",
            ]
        )

        self.assertEqual(args.auction_provider, "local_jingjia")
        self.assertEqual(args.min_auction_score, 65.0)
        self.assertEqual(args.auction_score_weight, 0.25)

    def test_cli_import_auction_cache_arguments_parse_without_importing(self) -> None:
        args = build_parser().parse_args(
            [
                "data",
                "import-auction-cache",
                "--source",
                "cache/jingjia",
                "--start",
                "2026-05-06",
                "--end",
                "2026-05-29",
                "--limit-files",
                "2",
                "--dry-run",
            ]
        )

        self.assertEqual(args.source, "cache/jingjia")
        self.assertEqual(args.start, date(2026, 5, 6))
        self.assertEqual(args.end, date(2026, 5, 29))
        self.assertEqual(args.limit_files, 2)
        self.assertTrue(args.dry_run)

    def test_cli_research_auction_compare_arguments_parse_without_running(self) -> None:
        args = build_parser().parse_args(
            [
                "research",
                "auction-compare",
                "--start",
                "2026-01-01",
                "--end",
                "2026-05-31",
                "--auction-provider",
                "local_jingjia",
                "--limit",
                "10",
            ]
        )

        self.assertEqual(args.start, date(2026, 1, 1))
        self.assertEqual(args.end, date(2026, 5, 31))
        self.assertEqual(args.auction_provider, "local_jingjia")
        self.assertEqual(args.limit, 10)
        self.assertEqual(args.public_summary, "reports/summaries/latest_auction_validation.md")
