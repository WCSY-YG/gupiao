"""Compare baseline and auction-enhanced breakout strategy variants."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from gupiao.backtest import BacktestConfig, BacktestResult, run_breakout_backtest
from gupiao.compat import UTC
from gupiao.data import Instrument, SQLiteStore
from gupiao.reports import format_pct
from gupiao.strategies import MovingAverageVolumeBreakoutStrategy, ScreeningStrategy


@dataclass(frozen=True)
class AuctionStrategyComparisonConfig:
    start: date
    end: date
    db_path: str | Path = "data/cache/market_scan.sqlite"
    output_dir: str | Path = "reports/generated/auction_validation/latest"
    public_summary_path: str | Path = "reports/summaries/latest_auction_validation.md"
    adjust: str = "hfq"
    auction_provider: str = "local_jingjia"
    top: int = 30
    limit: int | None = None
    min_auction_score: float | None = 60.0
    auction_score_weight: float = 0.15


@dataclass(frozen=True)
class AuctionRollingValidationConfig:
    start: date
    end: date
    db_path: str | Path = "data/cache/market_scan.sqlite"
    output_dir: str | Path = "reports/generated/auction_rolling/latest"
    public_summary_path: str | Path = "reports/summaries/latest_auction_rolling.md"
    adjust: str = "hfq"
    auction_provider: str = "local_jingjia"
    top: int = 30
    limit: int | None = None
    min_auction_scores: tuple[float | None, ...] = (None, 50.0, 60.0, 70.0)
    auction_score_weights: tuple[float, ...] = (0.0, 0.10, 0.15, 0.25)
    window_months: int = 1


@dataclass(frozen=True)
class AuctionStrategySymbolResult:
    symbol: str
    name: str
    status: str
    bars_count: int
    auction_profile_count: int
    baseline_total_return: float | None = None
    baseline_max_drawdown: float | None = None
    baseline_win_rate: float | None = None
    baseline_trade_count: int = 0
    auction_total_return: float | None = None
    auction_max_drawdown: float | None = None
    auction_win_rate: float | None = None
    auction_trade_count: int = 0
    delta_total_return: float | None = None
    delta_max_drawdown: float | None = None
    delta_win_rate: float | None = None
    error: str | None = None


@dataclass(frozen=True)
class AuctionStrategyComparisonResult:
    started_at: datetime
    finished_at: datetime
    config: AuctionStrategyComparisonConfig
    total_symbols: int
    processed: int
    succeeded: int
    failed: int
    no_data: int
    improved: int
    worsened: int
    result_path: Path
    failure_path: Path
    public_summary_path: Path
    results: tuple[AuctionStrategySymbolResult, ...]


@dataclass(frozen=True)
class AuctionRollingWindow:
    label: str
    start: date
    end: date


@dataclass(frozen=True)
class AuctionRollingEvaluation:
    window_label: str
    start: date
    end: date
    min_auction_score: float | None
    auction_score_weight: float
    total_symbols: int
    processed: int
    succeeded: int
    failed: int
    no_data: int
    improved: int
    worsened: int
    avg_baseline_total_return: float | None
    avg_auction_total_return: float | None
    avg_delta_total_return: float | None
    positive_ratio: float | None
    result_path: Path
    failure_path: Path
    comparison_summary_path: Path


@dataclass(frozen=True)
class AuctionRollingValidationResult:
    started_at: datetime
    finished_at: datetime
    config: AuctionRollingValidationConfig
    windows: tuple[AuctionRollingWindow, ...]
    evaluations: tuple[AuctionRollingEvaluation, ...]
    output_dir: Path
    public_summary_path: Path


StrategyVariantFactory = Callable[[float | None, float], ScreeningStrategy]


def run_auction_strategy_comparison(
    *,
    config: AuctionStrategyComparisonConfig,
    store: SQLiteStore | None = None,
    baseline_strategy: ScreeningStrategy | None = None,
    auction_strategy: ScreeningStrategy | None = None,
    backtest_config: BacktestConfig | None = None,
) -> AuctionStrategyComparisonResult:
    validate_config(config)
    store = store or SQLiteStore(config.db_path)
    baseline_strategy = baseline_strategy or MovingAverageVolumeBreakoutStrategy(
        min_auction_score=None,
        auction_score_weight=0.0,
    )
    auction_strategy = auction_strategy or MovingAverageVolumeBreakoutStrategy(
        min_auction_score=config.min_auction_score,
        auction_score_weight=config.auction_score_weight,
    )
    backtest_config = backtest_config or BacktestConfig()
    started_at = utc_now()

    symbols = store.list_auction_profile_symbols(
        start=config.start,
        end=config.end,
        provider=config.auction_provider,
        limit=config.limit,
    )
    total_symbols = len(symbols)
    instruments = {instrument.symbol: instrument for instrument in store.list_instruments()}

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "results.jsonl"
    failure_path = output_dir / "failures.jsonl"

    results: list[AuctionStrategySymbolResult] = []
    with result_path.open("w", encoding="utf-8") as result_file, failure_path.open(
        "w", encoding="utf-8"
    ) as failure_file:
        for symbol in symbols:
            result = compare_symbol(
                symbol,
                instrument=instruments.get(symbol),
                store=store,
                config=config,
                baseline_strategy=baseline_strategy,
                auction_strategy=auction_strategy,
                backtest_config=backtest_config,
            )
            results.append(result)
            write_json_line(result_file, result)
            if result.status == "failed":
                write_json_line(failure_file, result)

    finished_at = utc_now()
    summary = summarize_comparison(
        started_at=started_at,
        finished_at=finished_at,
        config=config,
        total_symbols=total_symbols,
        result_path=result_path,
        failure_path=failure_path,
        results=results,
    )
    write_public_summary(summary.public_summary_path, build_public_summary(summary))
    return summary


def run_auction_rolling_validation(
    *,
    config: AuctionRollingValidationConfig,
    store: SQLiteStore | None = None,
    baseline_strategy: ScreeningStrategy | None = None,
    auction_strategy_factory: StrategyVariantFactory | None = None,
    backtest_config: BacktestConfig | None = None,
) -> AuctionRollingValidationResult:
    validate_rolling_config(config)
    store = store or SQLiteStore(config.db_path)
    baseline_strategy = baseline_strategy or MovingAverageVolumeBreakoutStrategy(
        min_auction_score=None,
        auction_score_weight=0.0,
    )
    auction_strategy_factory = auction_strategy_factory or default_auction_strategy_factory
    backtest_config = backtest_config or BacktestConfig()
    windows = tuple(month_windows(config.start, config.end, config.window_months))
    parameters = parameter_grid(config)
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()

    evaluations: list[AuctionRollingEvaluation] = []
    rolling_result_path = output_dir / "rolling_results.jsonl"
    with rolling_result_path.open("w", encoding="utf-8") as result_file:
        for window in windows:
            for min_auction_score, auction_score_weight in parameters:
                comparison_config = comparison_config_for_window(
                    config,
                    window=window,
                    min_auction_score=min_auction_score,
                    auction_score_weight=auction_score_weight,
                )
                comparison = run_auction_strategy_comparison(
                    config=comparison_config,
                    store=store,
                    baseline_strategy=baseline_strategy,
                    auction_strategy=auction_strategy_factory(
                        min_auction_score,
                        auction_score_weight,
                    ),
                    backtest_config=backtest_config,
                )
                evaluation = rolling_evaluation_from_comparison(
                    comparison,
                    window=window,
                    min_auction_score=min_auction_score,
                    auction_score_weight=auction_score_weight,
                )
                evaluations.append(evaluation)
                write_json_line(result_file, evaluation)

    finished_at = utc_now()
    result = AuctionRollingValidationResult(
        started_at=started_at,
        finished_at=finished_at,
        config=config,
        windows=windows,
        evaluations=tuple(evaluations),
        output_dir=output_dir,
        public_summary_path=Path(config.public_summary_path),
    )
    write_public_summary(result.public_summary_path, build_rolling_public_summary(result))
    return result


def default_auction_strategy_factory(
    min_auction_score: float | None,
    auction_score_weight: float,
) -> ScreeningStrategy:
    return MovingAverageVolumeBreakoutStrategy(
        min_auction_score=min_auction_score,
        auction_score_weight=auction_score_weight,
    )


def comparison_config_for_window(
    config: AuctionRollingValidationConfig,
    *,
    window: AuctionRollingWindow,
    min_auction_score: float | None,
    auction_score_weight: float,
) -> AuctionStrategyComparisonConfig:
    variant_dir = (
        Path(config.output_dir)
        / safe_path_segment(window.label)
        / parameter_label(min_auction_score, auction_score_weight)
    )
    return AuctionStrategyComparisonConfig(
        start=window.start,
        end=window.end,
        db_path=config.db_path,
        output_dir=variant_dir,
        public_summary_path=variant_dir / "summary.md",
        adjust=config.adjust,
        auction_provider=config.auction_provider,
        top=config.top,
        limit=config.limit,
        min_auction_score=min_auction_score,
        auction_score_weight=auction_score_weight,
    )


def rolling_evaluation_from_comparison(
    comparison: AuctionStrategyComparisonResult,
    *,
    window: AuctionRollingWindow,
    min_auction_score: float | None,
    auction_score_weight: float,
) -> AuctionRollingEvaluation:
    succeeded = [result for result in comparison.results if result.status == "success"]
    avg_baseline = average_optional(result.baseline_total_return for result in succeeded)
    avg_auction = average_optional(result.auction_total_return for result in succeeded)
    avg_delta = average_optional(result.delta_total_return for result in succeeded)
    positive_ratio = comparison.improved / comparison.succeeded if comparison.succeeded else None
    return AuctionRollingEvaluation(
        window_label=window.label,
        start=window.start,
        end=window.end,
        min_auction_score=min_auction_score,
        auction_score_weight=auction_score_weight,
        total_symbols=comparison.total_symbols,
        processed=comparison.processed,
        succeeded=comparison.succeeded,
        failed=comparison.failed,
        no_data=comparison.no_data,
        improved=comparison.improved,
        worsened=comparison.worsened,
        avg_baseline_total_return=avg_baseline,
        avg_auction_total_return=avg_auction,
        avg_delta_total_return=avg_delta,
        positive_ratio=positive_ratio,
        result_path=comparison.result_path,
        failure_path=comparison.failure_path,
        comparison_summary_path=comparison.public_summary_path,
    )


def compare_symbol(
    symbol: str,
    *,
    instrument: Instrument | None,
    store: SQLiteStore,
    config: AuctionStrategyComparisonConfig,
    baseline_strategy: ScreeningStrategy,
    auction_strategy: ScreeningStrategy,
    backtest_config: BacktestConfig,
) -> AuctionStrategySymbolResult:
    name = instrument.name if instrument is not None else symbol
    try:
        bars = store.get_daily_bars(
            symbol,
            start=config.start,
            end=config.end,
            adjust=config.adjust,
        )
        auction_profiles = {
            profile.trade_date: profile
            for profile in store.get_auction_profiles(
                symbol,
                start=config.start,
                end=config.end,
                provider=config.auction_provider,
            )
        }
        if not bars:
            return AuctionStrategySymbolResult(
                symbol=symbol,
                name=name,
                status="no_data",
                bars_count=0,
                auction_profile_count=len(auction_profiles),
                error="no_daily_bars",
            )
        if not auction_profiles:
            return AuctionStrategySymbolResult(
                symbol=symbol,
                name=name,
                status="no_data",
                bars_count=len(bars),
                auction_profile_count=0,
                error="no_auction_profiles",
            )

        baseline = run_breakout_backtest(
            symbol,
            bars,
            strategy=baseline_strategy,
            config=backtest_config,
        )
        auction = run_breakout_backtest(
            symbol,
            bars,
            strategy=auction_strategy,
            config=backtest_config,
            auction_profiles=auction_profiles,
        )
        return build_symbol_result(
            symbol=symbol,
            name=name,
            bars_count=len(bars),
            auction_profile_count=len(auction_profiles),
            baseline=baseline,
            auction=auction,
        )
    except Exception as exc:  # noqa: BLE001 - per-symbol validation should continue.
        return AuctionStrategySymbolResult(
            symbol=symbol,
            name=name,
            status="failed",
            bars_count=0,
            auction_profile_count=0,
            error=f"{type(exc).__name__}: {exc}",
        )


def build_symbol_result(
    *,
    symbol: str,
    name: str,
    bars_count: int,
    auction_profile_count: int,
    baseline: BacktestResult,
    auction: BacktestResult,
) -> AuctionStrategySymbolResult:
    return AuctionStrategySymbolResult(
        symbol=symbol,
        name=name,
        status="success",
        bars_count=bars_count,
        auction_profile_count=auction_profile_count,
        baseline_total_return=baseline.total_return,
        baseline_max_drawdown=baseline.max_drawdown,
        baseline_win_rate=baseline.win_rate,
        baseline_trade_count=baseline.trade_count,
        auction_total_return=auction.total_return,
        auction_max_drawdown=auction.max_drawdown,
        auction_win_rate=auction.win_rate,
        auction_trade_count=auction.trade_count,
        delta_total_return=auction.total_return - baseline.total_return,
        delta_max_drawdown=auction.max_drawdown - baseline.max_drawdown,
        delta_win_rate=auction.win_rate - baseline.win_rate,
    )


def summarize_comparison(
    *,
    started_at: datetime,
    finished_at: datetime,
    config: AuctionStrategyComparisonConfig,
    total_symbols: int,
    result_path: Path,
    failure_path: Path,
    results: Sequence[AuctionStrategySymbolResult],
) -> AuctionStrategyComparisonResult:
    succeeded = [result for result in results if result.status == "success"]
    failed = sum(1 for result in results if result.status == "failed")
    no_data = sum(1 for result in results if result.status == "no_data")
    improved = sum(1 for result in succeeded if (result.delta_total_return or 0.0) > 0)
    worsened = sum(1 for result in succeeded if (result.delta_total_return or 0.0) < 0)
    return AuctionStrategyComparisonResult(
        started_at=started_at,
        finished_at=finished_at,
        config=config,
        total_symbols=total_symbols,
        processed=len(results),
        succeeded=len(succeeded),
        failed=failed,
        no_data=no_data,
        improved=improved,
        worsened=worsened,
        result_path=result_path,
        failure_path=failure_path,
        public_summary_path=Path(config.public_summary_path),
        results=tuple(results),
    )


def build_public_summary(comparison: AuctionStrategyComparisonResult) -> str:
    succeeded = [result for result in comparison.results if result.status == "success"]
    ranked = ranked_improvements(succeeded)[: comparison.config.top]
    avg_baseline = average_optional(result.baseline_total_return for result in succeeded)
    avg_auction = average_optional(result.auction_total_return for result in succeeded)
    avg_delta = average_optional(result.delta_total_return for result in succeeded)
    profile_count = sum(result.auction_profile_count for result in succeeded)
    lines = [
        "# 竞价增强策略对比汇总",
        "",
        f"- 生成时间：{comparison.finished_at.isoformat()}",
        f"- 回测区间：{comparison.config.start.isoformat()} 至 "
        f"{comparison.config.end.isoformat()}",
        f"- 复权方式：`{comparison.config.adjust}`",
        f"- 竞价画像源：`{comparison.config.auction_provider}`",
        f"- 最低竞价强度：{format_optional_float(comparison.config.min_auction_score)}",
        f"- 竞价分混合权重：{comparison.config.auction_score_weight:.2f}",
        f"- 本地完整结果：`{comparison.result_path}`",
        f"- 本地失败明细：`{comparison.failure_path}`",
        "",
        "## 样本统计",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| 有竞价画像股票数 | {comparison.total_symbols} |",
        f"| 本次处理 | {comparison.processed} |",
        f"| 成功对比 | {comparison.succeeded} |",
        f"| 无数据 | {comparison.no_data} |",
        f"| 失败 | {comparison.failed} |",
        f"| 竞价画像条数 | {profile_count} |",
        f"| 竞价增强收益更高 | {comparison.improved} |",
        f"| 竞价增强收益更低 | {comparison.worsened} |",
        f"| baseline 平均收益 | {format_optional_pct(avg_baseline)} |",
        f"| auction 平均收益 | {format_optional_pct(avg_auction)} |",
        f"| 平均收益差 | {format_optional_pct(avg_delta)} |",
        "",
        f"## Top {comparison.config.top} 改善样本",
        "",
    ]
    if ranked:
        lines.extend(
            [
                "| 排名 | 代码 | 名称 | 画像数 | baseline收益 | "
                "auction收益 | 收益差 | baseline交易 | auction交易 |",
                "|---:|---|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for index, result in enumerate(ranked, start=1):
            lines.append(
                "| "
                f"{index} | `{result.symbol}` | {escape_table_text(result.name)} | "
                f"{result.auction_profile_count} | "
                f"{format_optional_pct(result.baseline_total_return)} | "
                f"{format_optional_pct(result.auction_total_return)} | "
                f"{format_optional_pct(result.delta_total_return)} | "
                f"{result.baseline_trade_count} | {result.auction_trade_count} |"
            )
    else:
        lines.append("当前样本未产生可排序的成功对比结果。")
    lines.extend(iteration_guidance(comparison, avg_delta, profile_count))
    lines.extend(
        [
            "",
            "## 风险提示",
            "",
            "- 本汇总仅用于研究和辅助分析，不构成投资建议。",
            "- 竞价画像覆盖不足、日 K 成交量估算、停牌、涨跌停和交易成本都会影响结果。",
            "- 参数只能在样本外和滚动验证持续稳定后再提升为默认策略配置。",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_rolling_public_summary(result: AuctionRollingValidationResult) -> str:
    aggregates = aggregate_rolling_evaluations(result.evaluations)
    ranked_aggregates = sorted(
        aggregates,
        key=lambda item: (
            item["avg_delta_total_return"]
            if item["avg_delta_total_return"] is not None
            else -999.0,
            item["positive_window_ratio"]
            if item["positive_window_ratio"] is not None
            else -1.0,
            item["total_succeeded"],
        ),
        reverse=True,
    )
    best = ranked_aggregates[0] if ranked_aggregates else None
    lines = [
        "# 竞价参数滚动验证汇总",
        "",
        f"- 生成时间：{result.finished_at.isoformat()}",
        f"- 验证区间：{result.config.start.isoformat()} 至 {result.config.end.isoformat()}",
        f"- 窗口数量：{len(result.windows)}",
        f"- 窗口跨度：{result.config.window_months} 月",
        f"- 竞价画像源：`{result.config.auction_provider}`",
        f"- 复权方式：`{result.config.adjust}`",
        f"- 参数组合数：{len(parameter_grid(result.config))}",
        f"- 本地完整结果：`{result.output_dir}`",
        "",
        "## 参数稳定性排名",
        "",
    ]
    if ranked_aggregates:
        lines.extend(
            [
                "| 排名 | 最低竞价强度 | 竞价权重 | 窗口数 | 正向窗口 | "
                "正向比例 | 成功样本 | 平均收益差 | baseline均值 | auction均值 |",
                "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for index, item in enumerate(ranked_aggregates, start=1):
            lines.append(
                "| "
                f"{index} | {format_optional_float(item['min_auction_score'])} | "
                f"{item['auction_score_weight']:.2f} | {item['window_count']} | "
                f"{item['positive_windows']} | {format_optional_pct(item['positive_window_ratio'])} | "
                f"{item['total_succeeded']} | "
                f"{format_optional_pct(item['avg_delta_total_return'])} | "
                f"{format_optional_pct(item['avg_baseline_total_return'])} | "
                f"{format_optional_pct(item['avg_auction_total_return'])} |"
            )
    else:
        lines.append("当前没有可汇总的参数组合。")

    lines.extend(rolling_parameter_guidance(best, len(result.windows)))
    lines.extend(
        [
            "",
            "## 分窗口明细",
            "",
            "| 窗口 | 最低竞价强度 | 竞价权重 | 成功样本 | 正向/负向 | 平均收益差 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for evaluation in result.evaluations:
        lines.append(
            "| "
            f"{evaluation.window_label} | "
            f"{format_optional_float(evaluation.min_auction_score)} | "
            f"{evaluation.auction_score_weight:.2f} | "
            f"{evaluation.succeeded} | {evaluation.improved}/{evaluation.worsened} | "
            f"{format_optional_pct(evaluation.avg_delta_total_return)} |"
        )

    lines.extend(
        [
            "",
            "## 风险提示",
            "",
            "- 滚动验证只说明历史样本里的相对表现，不构成投资建议。",
            "- 若正向窗口比例不稳定，不应把竞价阈值设为默认硬过滤。",
            "- 推荐先把竞价强度、缺口、量比和委买委卖不平衡用于排序与解释，再用样本外数据继续验证。",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def aggregate_rolling_evaluations(
    evaluations: Sequence[AuctionRollingEvaluation],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[float | None, float], list[AuctionRollingEvaluation]] = {}
    for evaluation in evaluations:
        key = (evaluation.min_auction_score, evaluation.auction_score_weight)
        grouped.setdefault(key, []).append(evaluation)

    aggregates: list[dict[str, Any]] = []
    for (min_auction_score, auction_score_weight), rows in grouped.items():
        usable = [row for row in rows if row.succeeded > 0]
        aggregates.append(
            {
                "min_auction_score": min_auction_score,
                "auction_score_weight": auction_score_weight,
                "window_count": len(rows),
                "positive_windows": sum(
                    1
                    for row in usable
                    if row.avg_delta_total_return is not None and row.avg_delta_total_return > 0
                ),
                "positive_window_ratio": (
                    sum(
                        1
                        for row in usable
                        if row.avg_delta_total_return is not None and row.avg_delta_total_return > 0
                    )
                    / len(usable)
                    if usable
                    else None
                ),
                "total_succeeded": sum(row.succeeded for row in rows),
                "total_improved": sum(row.improved for row in rows),
                "total_worsened": sum(row.worsened for row in rows),
                "avg_baseline_total_return": average_optional(
                    row.avg_baseline_total_return for row in usable
                ),
                "avg_auction_total_return": average_optional(
                    row.avg_auction_total_return for row in usable
                ),
                "avg_delta_total_return": average_optional(
                    row.avg_delta_total_return for row in usable
                ),
            }
        )
    return aggregates


def rolling_parameter_guidance(best: dict[str, Any] | None, window_count: int) -> list[str]:
    lines = ["", "## 参数建议", ""]
    if best is None or not best["total_succeeded"]:
        lines.append("- 当前样本不足，暂不更新竞价参数建议。")
        return lines

    avg_delta = best["avg_delta_total_return"]
    positive_ratio = best["positive_window_ratio"] or 0.0
    if avg_delta is not None and avg_delta > 0 and positive_ratio >= 0.6:
        lines.append(
            "- 当前排名第一的参数在滚动窗口里相对稳定，可作为下一轮实验配置："
            f"`min_auction_score={format_optional_float(best['min_auction_score'])}`，"
            f"`auction_score_weight={best['auction_score_weight']:.2f}`。"
        )
        if best["min_auction_score"] is not None:
            lines.append("- 仍建议先用于专业模式或研究模式，暂不直接作为普通模式默认硬过滤。")
    else:
        lines.append(
            "- 当前参数没有达到稳定正向标准，继续保持竞价软排序和解释辅助，"
            "不把 `min_auction_score` 作为普通模式默认硬过滤。"
        )
    if window_count < 3:
        lines.append("- 当前滚动窗口少于 3 个，建议继续补充更多月份后再固化参数。")
    return lines


def iteration_guidance(
    comparison: AuctionStrategyComparisonResult,
    avg_delta: float | None,
    profile_count: int,
) -> list[str]:
    lines = ["", "## Skill 迭代建议", ""]
    if comparison.succeeded < 20 or profile_count < 100:
        lines.append(
            "- 当前样本覆盖偏小，暂不把竞价阈值提升为正式默认；先扩大 "
            "`local_jingjia` 导入区间后再滚动验证。"
        )
        return lines
    if avg_delta is not None and avg_delta > 0:
        lines.append(
            "- 当前窗口中竞价增强平均收益更高，可继续保留 "
            f"`min_auction_score={format_optional_float(comparison.config.min_auction_score)}` "
            f"和 `auction_score_weight={comparison.config.auction_score_weight:.2f}` "
            "作为候选实验配置。"
        )
    else:
        lines.append(
            "- 当前窗口中竞价增强未体现稳定收益改善，应降低竞价硬过滤强度，"
            "优先把竞价分作为排序辅助而非强制门槛。"
        )
    return lines


def ranked_improvements(
    results: Sequence[AuctionStrategySymbolResult],
) -> list[AuctionStrategySymbolResult]:
    return sorted(
        results,
        key=lambda result: (
            result.delta_total_return if result.delta_total_return is not None else -999.0,
            result.auction_total_return if result.auction_total_return is not None else -999.0,
            result.auction_trade_count,
        ),
        reverse=True,
    )


def write_public_summary(path: str | Path, content: str) -> Path:
    summary_path = Path(path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(content, encoding="utf-8")
    return summary_path


def write_json_line(file: Any, value: Any) -> None:
    file.write(json.dumps(to_jsonable(value), ensure_ascii=False, sort_keys=True) + "\n")


def validate_rolling_config(config: AuctionRollingValidationConfig) -> None:
    if config.start > config.end:
        raise ValueError("rolling validation start date must be before or equal to end date")
    if config.top <= 0:
        raise ValueError("top must be a positive integer")
    if config.limit is not None and config.limit <= 0:
        raise ValueError("limit must be a positive integer")
    if config.window_months <= 0:
        raise ValueError("window_months must be a positive integer")
    if not config.min_auction_scores:
        raise ValueError("min_auction_scores must not be empty")
    if not config.auction_score_weights:
        raise ValueError("auction_score_weights must not be empty")
    for score in config.min_auction_scores:
        if score is not None and not 0 <= score <= 100:
            raise ValueError("min_auction_scores must be between 0 and 100")
    for weight in config.auction_score_weights:
        if not 0 <= weight <= 1:
            raise ValueError("auction_score_weights must be between 0 and 1")


def validate_config(config: AuctionStrategyComparisonConfig) -> None:
    if config.start > config.end:
        raise ValueError("comparison start date must be before or equal to end date")
    if config.top <= 0:
        raise ValueError("top must be a positive integer")
    if config.limit is not None and config.limit <= 0:
        raise ValueError("limit must be a positive integer")
    if not 0 <= config.auction_score_weight <= 1:
        raise ValueError("auction_score_weight must be between 0 and 1")


def month_windows(start: date, end: date, window_months: int = 1) -> list[AuctionRollingWindow]:
    if window_months <= 0:
        raise ValueError("window_months must be a positive integer")
    if start > end:
        return []

    windows: list[AuctionRollingWindow] = []
    current = start
    while current <= end:
        next_period = first_day_after_month_window(current, window_months)
        window_end = min(end, next_period - timedelta(days=1))
        windows.append(
            AuctionRollingWindow(
                label=window_label(current, window_end),
                start=current,
                end=window_end,
            )
        )
        current = window_end + timedelta(days=1)
    return windows


def first_day_after_month_window(start: date, window_months: int) -> date:
    month_index = (start.year * 12) + (start.month - 1) + window_months
    return date(month_index // 12, (month_index % 12) + 1, 1)


def window_label(start: date, end: date) -> str:
    if start.year == end.year and start.month == end.month:
        return f"{start.year:04d}-{start.month:02d}"
    return f"{start.year:04d}-{start.month:02d}_to_{end.year:04d}-{end.month:02d}"


def parameter_grid(
    config: AuctionRollingValidationConfig,
) -> tuple[tuple[float | None, float], ...]:
    seen: set[tuple[float | None, float]] = set()
    grid: list[tuple[float | None, float]] = []
    for score in config.min_auction_scores:
        for weight in config.auction_score_weights:
            key = (score, round(weight, 6))
            if key not in seen:
                seen.add(key)
                grid.append((score, weight))
    return tuple(grid)


def parameter_label(min_auction_score: float | None, auction_score_weight: float) -> str:
    score = "none" if min_auction_score is None else f"{min_auction_score:g}"
    weight = f"{auction_score_weight:.2f}".replace(".", "p")
    return f"score_{score}_weight_{weight}"


def safe_path_segment(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)


def average_optional(values: Sequence[float | None] | Any) -> float | None:
    parsed = [value for value in values if value is not None]
    if not parsed:
        return None
    return sum(parsed) / len(parsed)


def format_optional_pct(value: float | None) -> str:
    return format_pct(value) if value is not None else "-"


def format_optional_float(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "-"


def escape_table_text(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return to_jsonable(asdict(value))  # type: ignore[arg-type]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)
