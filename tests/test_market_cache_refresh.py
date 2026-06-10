from __future__ import annotations

from datetime import date
from tempfile import TemporaryDirectory
from unittest import TestCase

from gupiao.data import (
    DailyBar,
    Instrument,
    MarketCacheRefreshConfig,
    SQLiteStore,
    refresh_market_daily_cache,
)

from tests.test_screening_strategy import breakout_bars


class FakeRefreshProvider:
    name = "fake"

    def __init__(self, bars_by_symbol: dict[str, list[DailyBar]]) -> None:
        self.bars_by_symbol = bars_by_symbol
        self.fetch_calls: list[tuple[str, date, date]] = []

    def list_instruments(self):
        return [
            Instrument(symbol="000001", name="平安银行", market="A股"),
            Instrument(symbol="000002", name="万科A", market="A股"),
        ]

    def fetch_daily_bars(self, symbol, start, end, *, adjust="hfq"):
        self.fetch_calls.append((symbol, start, end))
        return [
            bar
            for bar in self.bars_by_symbol.get(symbol, [])
            if start <= bar.trade_date <= end and (bar.adjust or "") == adjust
        ]


class MarketCacheRefreshTest(TestCase):
    def test_refresh_market_cache_dry_run_reports_missing_trade_dates(self) -> None:
        with TemporaryDirectory() as directory:
            store = SQLiteStore(f"{directory}/market.sqlite")
            cached = breakout_bars()[:8]
            store.upsert_daily_bars(cached)
            provider = FakeRefreshProvider({"000001": breakout_bars()})

            result = refresh_market_daily_cache(
                provider,
                store=store,
                config=MarketCacheRefreshConfig(
                    db_path=store.path,
                    end=date(2026, 6, 10),
                    dry_run=True,
                ),
                sleep=lambda _: None,
            )

            self.assertEqual(result.cached_end, date(2026, 6, 8))
            self.assertEqual(result.refresh_start, date(2026, 6, 9))
            self.assertEqual(
                result.missing_trade_dates,
                (date(2026, 6, 9), date(2026, 6, 10)),
            )
            self.assertEqual(result.missing_trade_days, 2)
            self.assertEqual(result.processed, 0)
            self.assertEqual(result.rows_written, 0)

    def test_refresh_market_cache_writes_missing_bars_for_instruments(self) -> None:
        with TemporaryDirectory() as directory:
            store = SQLiteStore(f"{directory}/market.sqlite")
            bars_000001 = breakout_bars()
            bars_000002 = [with_symbol(bar, "000002") for bar in breakout_bars()]
            store.upsert_instruments(
                [
                    Instrument(symbol="000001", name="平安银行", market="A股"),
                    Instrument(symbol="000002", name="万科A", market="A股"),
                ]
            )
            store.upsert_daily_bars(bars_000001[:8])
            provider = FakeRefreshProvider({"000001": bars_000001, "000002": bars_000002})

            result = refresh_market_daily_cache(
                provider,
                store=store,
                config=MarketCacheRefreshConfig(
                    db_path=store.path,
                    end=date(2026, 6, 10),
                ),
                sleep=lambda _: None,
            )

            self.assertEqual(result.missing_trade_days, 2)
            self.assertEqual(result.processed, 2)
            self.assertEqual(result.succeeded, 2)
            self.assertEqual(result.rows_written, 4)
            self.assertEqual(
                store.daily_bar_date_range(adjust="hfq"),
                (date(2026, 6, 1), date(2026, 6, 10)),
            )
            self.assertEqual(len(store.get_daily_bars("000002", adjust="hfq")), 2)

    def test_refresh_market_cache_does_nothing_when_probe_has_no_new_dates(self) -> None:
        with TemporaryDirectory() as directory:
            store = SQLiteStore(f"{directory}/market.sqlite")
            bars = breakout_bars()
            store.upsert_daily_bars(bars)
            provider = FakeRefreshProvider({"000001": bars})

            result = refresh_market_daily_cache(
                provider,
                store=store,
                config=MarketCacheRefreshConfig(
                    db_path=store.path,
                    end=date(2026, 6, 10),
                ),
                sleep=lambda _: None,
            )

            self.assertEqual(result.missing_trade_days, 0)
            self.assertEqual(result.processed, 0)
            self.assertEqual(result.rows_written, 0)


def with_symbol(bar: DailyBar, symbol: str) -> DailyBar:
    return DailyBar(
        symbol=symbol,
        trade_date=bar.trade_date,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,
        amount=bar.amount,
        turnover=bar.turnover,
        adjust=bar.adjust,
        provider=bar.provider,
        fetched_at=bar.fetched_at,
    )
