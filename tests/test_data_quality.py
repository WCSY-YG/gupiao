from __future__ import annotations

from datetime import date
from unittest import TestCase

from gupiao.data import DailyBar, Instrument, has_errors, validate_daily_bars, validate_instruments


class DataQualityTest(TestCase):
    def test_validate_instruments_detects_duplicates_and_missing_fields(self) -> None:
        issues = validate_instruments(
            [
                Instrument(symbol="000001", name="平安银行", market="A股"),
                Instrument(symbol="000001", name="", market=""),
            ]
        )

        self.assertTrue(has_errors(issues))
        self.assertEqual(
            {item.code for item in issues},
            {
                "instrument_duplicate_symbol",
                "instrument_missing_name",
                "instrument_missing_market",
            },
        )

    def test_validate_daily_bars_accepts_clean_series(self) -> None:
        issues = validate_daily_bars(
            [
                daily_bar(date(2026, 6, 9), close=10.2),
                daily_bar(date(2026, 6, 10), close=10.4),
            ]
        )

        self.assertEqual(issues, [])

    def test_validate_daily_bars_detects_price_and_volume_errors(self) -> None:
        issues = validate_daily_bars(
            [
                daily_bar(
                    date(2026, 6, 9),
                    open_=10.0,
                    high=9.8,
                    low=10.1,
                    close=10.2,
                    volume=-1.0,
                    amount=-10.0,
                    turnover=-0.1,
                )
            ]
        )

        self.assertTrue(has_errors(issues))
        self.assertIn("daily_high_below_low", {item.code for item in issues})
        self.assertIn("daily_high_below_open_or_close", {item.code for item in issues})
        self.assertIn("daily_low_above_open_or_close", {item.code for item in issues})
        self.assertIn("daily_negative_volume", {item.code for item in issues})
        self.assertIn("daily_negative_amount", {item.code for item in issues})
        self.assertIn("daily_negative_turnover", {item.code for item in issues})

    def test_validate_daily_bars_detects_missing_required_value(self) -> None:
        issues = validate_daily_bars([daily_bar(date(2026, 6, 9), open_=None)])

        self.assertEqual({item.code for item in issues}, {"daily_missing_required_value"})
        self.assertTrue(has_errors(issues))

    def test_validate_daily_bars_detects_duplicates_order_and_zero_volume(self) -> None:
        issues = validate_daily_bars(
            [
                daily_bar(date(2026, 6, 10), volume=1.0),
                daily_bar(date(2026, 6, 9), volume=0.0),
                daily_bar(date(2026, 6, 9), volume=0.0),
            ]
        )

        self.assertIn("daily_non_monotonic_date", {item.code for item in issues})
        self.assertIn("daily_duplicate_bar", {item.code for item in issues})
        self.assertIn("daily_zero_volume", {item.code for item in issues})


def daily_bar(
    trade_date: date,
    *,
    open_: float | None = 10.0,
    high: float | None = 10.5,
    low: float | None = 9.8,
    close: float | None = 10.1,
    volume: float | None = 1000.0,
    amount: float = 10000.0,
    turnover: float = 1.0,
) -> DailyBar:
    return DailyBar(
        symbol="000001",
        trade_date=trade_date,
        open=open_,  # type: ignore[arg-type]
        high=high,  # type: ignore[arg-type]
        low=low,  # type: ignore[arg-type]
        close=close,  # type: ignore[arg-type]
        volume=volume,  # type: ignore[arg-type]
        amount=amount,
        turnover=turnover,
        adjust="hfq",
        provider="test",
    )
