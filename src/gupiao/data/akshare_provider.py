"""AKShare-backed market data provider."""

from __future__ import annotations

import importlib
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timezone
from typing import Any

from gupiao.data.schema import DailyBar, Instrument

Record = Mapping[str, Any]


class AkshareProvider:
    """Fetch A-share instruments and daily bars from AKShare."""

    name = "akshare"

    def __init__(self, akshare_module: Any | None = None) -> None:
        self._akshare_module = akshare_module

    def list_instruments(self) -> Iterable[Instrument]:
        frame = self._akshare().stock_info_a_code_name()
        for row in records_from_frame(frame):
            symbol = normalize_symbol(first_value(row, "code", "代码", "symbol", "股票代码"))
            yield Instrument(
                symbol=symbol,
                name=str(first_value(row, "name", "名称", "股票简称", default="")).strip(),
                market="A股",
                exchange=infer_exchange(symbol),
            )

    def fetch_daily_bars(
        self,
        symbol: str,
        start: date,
        end: date,
        *,
        adjust: str = "hfq",
    ) -> Iterable[DailyBar]:
        normalized_symbol = normalize_symbol(symbol)
        normalized_adjust = normalize_adjust(adjust)
        fetched_at = datetime.now(timezone.utc)
        frame = self._akshare().stock_zh_a_hist(
            symbol=normalized_symbol,
            period="daily",
            start_date=format_akshare_date(start),
            end_date=format_akshare_date(end),
            adjust=normalized_adjust,
        )
        for row in records_from_frame(frame):
            yield DailyBar(
                symbol=normalize_symbol(
                    first_value(row, "股票代码", "code", "symbol", default=normalized_symbol)
                ),
                trade_date=parse_date(first_value(row, "日期", "trade_date", "date")),
                open=required_float(row, "开盘", "open"),
                high=required_float(row, "最高", "high"),
                low=required_float(row, "最低", "low"),
                close=required_float(row, "收盘", "close"),
                volume=required_float(row, "成交量", "volume"),
                amount=optional_float(row, "成交额", "amount"),
                turnover=optional_float(row, "换手率", "turnover"),
                adjust=adjust,
                provider=self.name,
                fetched_at=fetched_at,
            )

    def _akshare(self) -> Any:
        if self._akshare_module is None:
            try:
                self._akshare_module = importlib.import_module("akshare")
            except ImportError as exc:
                raise RuntimeError(
                    "AKShare is not installed. Install data dependencies with "
                    'python -m pip install -e ".[data]".'
                ) from exc
        return self._akshare_module


def records_from_frame(frame: Any) -> list[Record]:
    """Convert a pandas-like DataFrame or record sequence into dictionaries."""

    if hasattr(frame, "to_dict"):
        records = frame.to_dict("records")
    else:
        records = frame

    if records is None:
        return []
    if isinstance(records, list):
        return [record for record in records if isinstance(record, Mapping)]
    if isinstance(records, tuple):
        return [record for record in records if isinstance(record, Mapping)]
    raise TypeError(f"Unsupported AKShare response type: {type(frame)!r}")


def first_value(row: Record, *keys: str, default: Any | None = None) -> Any:
    for key in keys:
        if key in row:
            value = row[key]
            if value is not None and str(value).strip() != "":
                return value
    if default is not None:
        return default
    raise KeyError(f"Missing required field; tried {keys!r}")


def normalize_symbol(value: Any) -> str:
    symbol = str(value).strip()
    if "." in symbol:
        left, right = symbol.split(".", 1)
        symbol = left if left.isdigit() else right
    symbol = symbol.removeprefix("SH").removeprefix("SZ").removeprefix("BJ")
    symbol = symbol.removeprefix("sh").removeprefix("sz").removeprefix("bj")
    return symbol.zfill(6) if symbol.isdigit() else symbol


def infer_exchange(symbol: str) -> str | None:
    normalized = normalize_symbol(symbol)
    if normalized.startswith(("6", "9")):
        return "SSE"
    if normalized.startswith(("0", "2", "3")):
        return "SZSE"
    if normalized.startswith(("4", "8")):
        return "BSE"
    return None


def normalize_adjust(adjust: str) -> str:
    normalized = adjust.strip().lower()
    if normalized == "raw":
        return ""
    if normalized in {"", "qfq", "hfq"}:
        return normalized
    raise ValueError("adjust must be one of: raw, qfq, hfq")


def format_akshare_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return date.fromisoformat(f"{text[:4]}-{text[4:6]}-{text[6:]}")
    return date.fromisoformat(text)


def required_float(row: Record, *keys: str) -> float:
    return float(first_value(row, *keys))


def optional_float(row: Record, *keys: str) -> float | None:
    try:
        return float(first_value(row, *keys))
    except KeyError:
        return None
