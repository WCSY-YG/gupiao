"""Recoverable market-wide backtest scan workflow."""

from __future__ import annotations

import json
import signal
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from threading import current_thread, main_thread
from typing import Any

from gupiao.backtest import BacktestConfig, run_breakout_backtest
from gupiao.data import (
    DailyBar,
    DataProvider,
    Instrument,
    SQLiteStore,
    has_errors,
    validate_daily_bars,
)
from gupiao.reports import format_pct
from gupiao.signals import build_breakout_signal
from gupiao.strategies import MovingAverageVolumeBreakoutStrategy

DEFAULT_SCAN_START = date(2023, 6, 10)
DEFAULT_SCAN_END = date(2026, 6, 10)


@dataclass(frozen=True)
class MarketScanConfig:
    start: date = DEFAULT_SCAN_START
    end: date = DEFAULT_SCAN_END
    adjust: str = "hfq"
    db_path: str | Path = "data/cache/market_scan.sqlite"
    output_dir: str | Path = "reports/generated/market_scan/latest"
    public_summary_path: str | Path = "reports/summaries/latest_market_scan.md"
    top: int = 30
    limit: int | None = None
    retries: int = 3
    retry_sleep_seconds: float = 1.0
    request_sleep_seconds: float = 0.0
    request_timeout_seconds: float | None = 60.0


@dataclass(frozen=True)
class ScanSymbolResult:
    symbol: str
    name: str
    status: str
    bars_count: int
    data_source: str
    latest_trade_date: date | None = None
    candidate_score: float | None = None
    signal_confidence: float | None = None
    total_return: float | None = None
    max_drawdown: float | None = None
    win_rate: float | None = None
    trade_count: int = 0
    error: str | None = None


@dataclass(frozen=True)
class MarketScanResult:
    started_at: datetime
    finished_at: datetime
    config: MarketScanConfig
    total_instruments: int
    processed: int
    succeeded: int
    failed: int
    no_data: int
    fetched: int
    cached: int
    candidate_count: int
    result_path: Path
    failure_path: Path
    public_summary_path: Path
    results: tuple[ScanSymbolResult, ...]


def run_market_scan(
    provider: DataProvider,
    *,
    config: MarketScanConfig | None = None,
    store: SQLiteStore | None = None,
    strategy: MovingAverageVolumeBreakoutStrategy | None = None,
    backtest_config: BacktestConfig | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> MarketScanResult:
    config = config or MarketScanConfig()
    validate_config(config)
    store = store or SQLiteStore(config.db_path)
    strategy = strategy or MovingAverageVolumeBreakoutStrategy()
    backtest_config = backtest_config or BacktestConfig()
    started_at = utc_now()

    instruments = list(provider.list_instruments())
    total_instruments = len(instruments)
    if config.limit is not None:
        instruments = instruments[: config.limit]
    if instruments:
        store.upsert_instruments(instruments)

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "results.jsonl"
    failure_path = output_dir / "failures.jsonl"
    results: list[ScanSymbolResult] = []

    with result_path.open("w", encoding="utf-8") as result_file, failure_path.open(
        "w", encoding="utf-8"
    ) as failure_file:
        for instrument in instruments:
            result = scan_instrument(
                instrument,
                provider=provider,
                store=store,
                config=config,
                strategy=strategy,
                backtest_config=backtest_config,
                sleep=sleep,
            )
            results.append(result)
            write_json_line(result_file, result)
            if result.status == "failed":
                write_json_line(failure_file, result)

    finished_at = utc_now()
    summary = summarize_result(
        started_at=started_at,
        finished_at=finished_at,
        config=config,
        total_instruments=total_instruments,
        result_path=result_path,
        failure_path=failure_path,
        results=results,
    )
    write_public_summary(summary.public_summary_path, build_public_summary(summary))
    return summary


def scan_instrument(
    instrument: Instrument,
    *,
    provider: DataProvider,
    store: SQLiteStore,
    config: MarketScanConfig,
    strategy: MovingAverageVolumeBreakoutStrategy,
    backtest_config: BacktestConfig,
    sleep: Callable[[float], None],
) -> ScanSymbolResult:
    try:
        cached_bars = store.get_daily_bars(
            instrument.symbol,
            start=config.start,
            end=config.end,
            adjust=config.adjust,
        )
        if cached_bars and cached_bars_cover_end(cached_bars, config.end):
            bars = cached_bars
            data_source = "cached"
        else:
            bars = fetch_daily_bars_with_retries(
                provider,
                instrument.symbol,
                config.start,
                config.end,
                adjust=config.adjust,
                retries=config.retries,
                retry_sleep_seconds=config.retry_sleep_seconds,
                request_sleep_seconds=config.request_sleep_seconds,
                request_timeout_seconds=config.request_timeout_seconds,
                sleep=sleep,
            )
            data_source = "fetched"
            if bars:
                store.upsert_daily_bars(bars)

        if not bars:
            return ScanSymbolResult(
                symbol=instrument.symbol,
                name=instrument.name,
                status="no_data",
                bars_count=0,
                data_source=data_source,
            )

        quality_issues = validate_daily_bars(bars)
        if has_errors(quality_issues):
            errors = [issue for issue in quality_issues if issue.severity == "error"]
            return ScanSymbolResult(
                symbol=instrument.symbol,
                name=instrument.name,
                status="failed",
                bars_count=len(bars),
                data_source=data_source,
                latest_trade_date=max(bar.trade_date for bar in bars),
                error=f"data_quality_errors={len(errors)}",
            )

        candidate = strategy.evaluate(instrument.symbol, bars)
        signal = (
            build_breakout_signal(
                candidate,
                bars,
                atr_window=backtest_config.atr_window,
                stop_atr_multiple=backtest_config.stop_atr_multiple,
                take_profit_r_multiple=backtest_config.take_profit_r_multiple,
            )
            if candidate is not None
            else None
        )
        backtest = run_breakout_backtest(
            instrument.symbol,
            bars,
            strategy=strategy,
            config=backtest_config,
        )
        return ScanSymbolResult(
            symbol=instrument.symbol,
            name=instrument.name,
            status="success",
            bars_count=len(bars),
            data_source=data_source,
            latest_trade_date=max(bar.trade_date for bar in bars),
            candidate_score=candidate.score if candidate is not None else None,
            signal_confidence=signal.confidence if signal is not None else None,
            total_return=backtest.total_return,
            max_drawdown=backtest.max_drawdown,
            win_rate=backtest.win_rate,
            trade_count=backtest.trade_count,
        )
    except Exception as exc:  # noqa: BLE001 - per-symbol failures should not stop the scan.
        return ScanSymbolResult(
            symbol=instrument.symbol,
            name=instrument.name,
            status="failed",
            bars_count=0,
            data_source="error",
            error=f"{type(exc).__name__}: {exc}",
        )


def fetch_daily_bars_with_retries(
    provider: DataProvider,
    symbol: str,
    start: date,
    end: date,
    *,
    adjust: str,
    retries: int,
    retry_sleep_seconds: float,
    request_sleep_seconds: float,
    request_timeout_seconds: float | None,
    sleep: Callable[[float], None],
) -> list[DailyBar]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            bars = fetch_daily_bars_once(
                provider,
                symbol,
                start,
                end,
                adjust=adjust,
                request_timeout_seconds=request_timeout_seconds,
            )
            sleep_after_request(request_sleep_seconds, sleep)
            return bars
        except Exception as exc:  # noqa: BLE001 - provider adapters expose mixed exceptions.
            last_error = exc
            sleep_after_request(request_sleep_seconds, sleep)
            if attempt >= retries:
                break
            sleep(retry_sleep_seconds * attempt)
    if last_error is not None:
        raise last_error
    return []


def cached_bars_cover_end(bars: Sequence[DailyBar], end: date) -> bool:
    return max(bar.trade_date for bar in bars) >= end


def fetch_daily_bars_once(
    provider: DataProvider,
    symbol: str,
    start: date,
    end: date,
    *,
    adjust: str,
    request_timeout_seconds: float | None,
) -> list[DailyBar]:
    fetch = lambda: list(provider.fetch_daily_bars(symbol, start, end, adjust=adjust))
    if request_timeout_seconds is None:
        return fetch()
    return call_with_timeout(
        fetch,
        timeout_seconds=request_timeout_seconds,
        label=f"daily bars request for {symbol}",
    )


def call_with_timeout(
    action: Callable[[], list[DailyBar]],
    *,
    timeout_seconds: float,
    label: str,
) -> list[DailyBar]:
    if current_thread() is not main_thread() or not hasattr(signal, "setitimer"):
        return action()

    previous_handler = signal.getsignal(signal.SIGALRM)

    def raise_timeout(_signum: int, _frame: Any) -> None:
        raise TimeoutError(f"{label} timed out after {timeout_seconds:g} seconds")

    signal.signal(signal.SIGALRM, raise_timeout)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        return action()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0 or previous_timer[1] > 0:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def summarize_result(
    *,
    started_at: datetime,
    finished_at: datetime,
    config: MarketScanConfig,
    total_instruments: int,
    result_path: Path,
    failure_path: Path,
    results: Sequence[ScanSymbolResult],
) -> MarketScanResult:
    succeeded = sum(1 for result in results if result.status == "success")
    failed = sum(1 for result in results if result.status == "failed")
    no_data = sum(1 for result in results if result.status == "no_data")
    fetched = sum(1 for result in results if result.data_source == "fetched")
    cached = sum(1 for result in results if result.data_source == "cached")
    candidate_count = sum(1 for result in results if result.candidate_score is not None)
    return MarketScanResult(
        started_at=started_at,
        finished_at=finished_at,
        config=config,
        total_instruments=total_instruments,
        processed=len(results),
        succeeded=succeeded,
        failed=failed,
        no_data=no_data,
        fetched=fetched,
        cached=cached,
        candidate_count=candidate_count,
        result_path=result_path,
        failure_path=failure_path,
        public_summary_path=Path(config.public_summary_path),
        results=tuple(results),
    )


def build_public_summary(scan: MarketScanResult) -> str:
    ranked = ranked_candidates(scan.results)[: scan.config.top]
    lines = [
        "# 全 A 股市场扫描汇总",
        "",
        f"- 生成时间：{scan.finished_at.isoformat()}",
        f"- 回测区间：{scan.config.start.isoformat()} 至 {scan.config.end.isoformat()}",
        f"- 复权方式：`{scan.config.adjust}`",
        f"- 股票范围：{'前 ' + str(scan.config.limit) + ' 只' if scan.config.limit else '全 A 股'}",
        f"- 重试次数：{scan.config.retries}",
        f"- 请求节流：{scan.config.request_sleep_seconds:g} 秒",
        f"- 重试退避：{scan.config.retry_sleep_seconds:g} 秒",
        f"- 单次请求超时：{format_timeout(scan.config.request_timeout_seconds)}",
        f"- 本地完整结果：`{scan.result_path}`",
        f"- 本地失败明细：`{scan.failure_path}`",
        "",
        "## 扫描统计",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| 全市场股票数 | {scan.total_instruments} |",
        f"| 本次处理 | {scan.processed} |",
        f"| 成功 | {scan.succeeded} |",
        f"| 无数据 | {scan.no_data} |",
        f"| 失败 | {scan.failed} |",
        f"| 使用缓存 | {scan.cached} |",
        f"| 新拉取 | {scan.fetched} |",
        f"| 当前候选 | {scan.candidate_count} |",
        "",
        f"## Top {scan.config.top} 候选",
        "",
    ]
    if ranked:
        lines.extend(
            [
                "| 排名 | 代码 | 名称 | 候选分 | 总收益 | 最大回撤 | 胜率 | 交易次数 | 最新交易日 |",
                "|---:|---|---|---:|---:|---:|---:|---:|---|",
            ]
        )
        for index, result in enumerate(ranked, start=1):
            lines.append(
                "| "
                f"{index} | `{result.symbol}` | {escape_table_text(result.name)} | "
                f"{format_optional_float(result.candidate_score)} | "
                f"{format_optional_pct(result.total_return)} | "
                f"{format_optional_pct(result.max_drawdown)} | "
                f"{format_optional_pct(result.win_rate)} | "
                f"{result.trade_count} | "
                f"{result.latest_trade_date.isoformat() if result.latest_trade_date else '-'} |"
            )
    else:
        lines.append("本次扫描未产生当前候选。")
    lines.extend(failure_section(scan.results))
    lines.extend(
        [
            "",
            "## 风险提示",
            "",
            "- 本汇总仅用于研究和辅助分析，不构成投资建议。",
            "- 全市场批量回测可能受到数据缺失、复权方式、停牌、涨跌停和接口限流影响。",
            "- Top 排名优先依据当前候选分数，不代表未来收益排序。",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def ranked_candidates(results: Sequence[ScanSymbolResult]) -> list[ScanSymbolResult]:
    candidates = [result for result in results if result.candidate_score is not None]
    return sorted(
        candidates,
        key=lambda result: (
            result.candidate_score if result.candidate_score is not None else -1.0,
            result.total_return if result.total_return is not None else -1.0,
            result.trade_count,
        ),
        reverse=True,
    )


def failure_section(results: Sequence[ScanSymbolResult]) -> list[str]:
    failures = [result for result in results if result.status == "failed"]
    if not failures:
        return ["", "## 失败样例", "", "无失败记录。"]
    lines = [
        "",
        "## 失败样例",
        "",
        "| 代码 | 名称 | 原因 |",
        "|---|---|---|",
    ]
    for result in failures[:10]:
        lines.append(
            "| "
            f"`{result.symbol}` | {escape_table_text(result.name)} | "
            f"{escape_table_text(result.error or '')} |"
        )
    if len(failures) > 10:
        lines.append(f"| ... | ... | 另有 {len(failures) - 10} 条失败记录见本地失败明细 |")
    return lines


def write_public_summary(path: str | Path, content: str) -> Path:
    summary_path = Path(path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(content, encoding="utf-8")
    return summary_path


def write_json_line(file: Any, value: Any) -> None:
    file.write(json.dumps(to_jsonable(value), ensure_ascii=False, sort_keys=True) + "\n")


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def validate_config(config: MarketScanConfig) -> None:
    if config.start > config.end:
        raise ValueError("scan start date must be before or equal to end date")
    if config.top <= 0:
        raise ValueError("top must be a positive integer")
    if config.limit is not None and config.limit <= 0:
        raise ValueError("limit must be a positive integer")
    if config.retries <= 0:
        raise ValueError("retries must be a positive integer")
    if config.retry_sleep_seconds < 0:
        raise ValueError("retry_sleep_seconds must be non-negative")
    if config.request_sleep_seconds < 0:
        raise ValueError("request_sleep_seconds must be non-negative")
    if config.request_timeout_seconds is not None and config.request_timeout_seconds <= 0:
        raise ValueError("request_timeout_seconds must be positive")


def format_optional_pct(value: float | None) -> str:
    return format_pct(value) if value is not None else "-"


def format_optional_float(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "-"


def format_timeout(value: float | None) -> str:
    return "禁用" if value is None else f"{value:g} 秒"


def escape_table_text(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def sleep_after_request(seconds: float, sleep: Callable[[float], None]) -> None:
    if seconds > 0:
        sleep(seconds)
