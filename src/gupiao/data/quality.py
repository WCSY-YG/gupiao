"""Data quality checks for normalized market records."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Literal

from gupiao.data.schema import DailyBar, Instrument

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: Severity
    symbol: str | None = None
    trade_date: date | None = None
    field: str | None = None


def validate_instruments(instruments: Iterable[Instrument]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen_symbols: set[str] = set()

    for instrument in instruments:
        if not instrument.symbol:
            issues.append(
                ValidationIssue(
                    code="instrument_missing_symbol",
                    message="Instrument symbol is required.",
                    severity="error",
                    field="symbol",
                )
            )
        elif instrument.symbol in seen_symbols:
            issues.append(
                ValidationIssue(
                    code="instrument_duplicate_symbol",
                    message="Instrument symbol appears more than once.",
                    severity="error",
                    symbol=instrument.symbol,
                    field="symbol",
                )
            )
        else:
            seen_symbols.add(instrument.symbol)

        if not instrument.name:
            issues.append(
                ValidationIssue(
                    code="instrument_missing_name",
                    message="Instrument name is required.",
                    severity="error",
                    symbol=instrument.symbol or None,
                    field="name",
                )
            )
        if not instrument.market:
            issues.append(
                ValidationIssue(
                    code="instrument_missing_market",
                    message="Instrument market is required.",
                    severity="error",
                    symbol=instrument.symbol or None,
                    field="market",
                )
            )

    return issues


def validate_daily_bars(bars: Iterable[DailyBar]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen_keys: set[tuple[str, date, str]] = set()
    last_date_by_series: dict[tuple[str, str], date] = {}

    for bar in bars:
        adjust = bar.adjust or ""
        key = (bar.symbol, bar.trade_date, adjust)
        series_key = (bar.symbol, adjust)

        if key in seen_keys:
            issues.append(
                issue(
                    "daily_duplicate_bar",
                    "Daily bar appears more than once for symbol/date/adjust.",
                    "error",
                    bar,
                )
            )
        else:
            seen_keys.add(key)

        last_date = last_date_by_series.get(series_key)
        if last_date is not None and bar.trade_date < last_date:
            issues.append(
                issue(
                    "daily_non_monotonic_date",
                    "Daily bars must be ordered by ascending trade_date per symbol/adjust.",
                    "error",
                    bar,
                    field="trade_date",
                )
            )
        last_date_by_series[series_key] = bar.trade_date

        issues.extend(validate_ohlcv(bar))

    return issues


def validate_ohlcv(bar: DailyBar) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    required_fields = {
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
    }

    for field, value in required_fields.items():
        if value is None:
            issues.append(
                issue(
                    "daily_missing_required_value",
                    "Daily bar has a missing required OHLCV value.",
                    "error",
                    bar,
                    field=field,
                )
            )
    if any(value is None for value in required_fields.values()):
        return issues

    if bar.high < bar.low:
        issues.append(
            issue("daily_high_below_low", "High price is lower than low price.", "error", bar)
        )
    if bar.high < max(bar.open, bar.close):
        issues.append(
            issue(
                "daily_high_below_open_or_close",
                "High price is lower than open or close.",
                "error",
                bar,
                field="high",
            )
        )
    if bar.low > min(bar.open, bar.close):
        issues.append(
            issue(
                "daily_low_above_open_or_close",
                "Low price is higher than open or close.",
                "error",
                bar,
                field="low",
            )
        )
    if bar.volume < 0:
        issues.append(issue("daily_negative_volume", "Volume cannot be negative.", "error", bar))
    elif bar.volume == 0:
        issues.append(
            issue(
                "daily_zero_volume",
                "Zero volume may indicate suspension or missing trading data.",
                "warning",
                bar,
                field="volume",
            )
        )
    if bar.amount is not None and bar.amount < 0:
        issues.append(issue("daily_negative_amount", "Amount cannot be negative.", "error", bar))
    if bar.turnover is not None and bar.turnover < 0:
        issues.append(
            issue("daily_negative_turnover", "Turnover cannot be negative.", "error", bar)
        )

    return issues


def has_errors(issues: Iterable[ValidationIssue]) -> bool:
    return any(item.severity == "error" for item in issues)


def issue(
    code: str,
    message: str,
    severity: Severity,
    bar: DailyBar,
    *,
    field: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        message=message,
        severity=severity,
        symbol=bar.symbol,
        trade_date=bar.trade_date,
        field=field,
    )
