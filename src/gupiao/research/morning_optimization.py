"""Walk-forward optimization for morning multi-horizon strategies."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from gupiao.backtest import BacktestConfig, BacktestResult, run_morning_plan_backtest
from gupiao.compat import UTC
from gupiao.data import LocalAuctionCacheImportConfig, SQLiteStore, import_local_auction_cache
from gupiao.reports import format_pct
from gupiao.research.auction_validation import AuctionRollingWindow, month_windows
from gupiao.strategies import build_screening_strategy
from gupiao.trade_plan import HORIZONS

OBJECTIVES = ("balanced", "win_rate", "return")


@dataclass(frozen=True)
class MorningStrategyVariant:
    label: str
    horizon: str
    strategy_id: str
    parameters: dict[str, Any]
    backtest: dict[str, Any]
    min_candidate_score: float


@dataclass(frozen=True)
class MorningOptimizationMetrics:
    win_rate: float
    avg_trade_return: float
    total_return: float
    max_drawdown: float
    trade_count: int
    symbol_count: int


@dataclass(frozen=True)
class MorningOptimizedProfile:
    objective: str
    horizon: str
    strategy_id: str
    parameters: dict[str, Any]
    backtest: dict[str, Any]
    min_candidate_score: float
    qualified: bool
    metrics: MorningOptimizationMetrics
    selected_windows: int
    label: str


@dataclass(frozen=True)
class MorningOptimizationConfig:
    start: date
    end: date
    db_path: str | Path = "data/cache/market_scan.sqlite"
    auction_source_dir: str | Path = "cache/jingjia"
    auction_provider: str = "local_jingjia"
    adjust: str = "hfq"
    output_dir: str | Path = "reports/generated/morning_optimization/latest"
    public_summary_path: str | Path = "reports/summaries/latest_morning_optimization.md"
    profile_output_path: str | Path = "configs/morning_strategy_profiles.json"
    limit: int | None = None
    import_missing_auction: bool = True
    training_days: int = 90
    min_trades: int = 10


@dataclass(frozen=True)
class MorningStrategyOptimizationResult:
    started_at: datetime
    finished_at: datetime
    config: MorningOptimizationConfig
    profiles: tuple[MorningOptimizedProfile, ...]
    auction_import: Any | None
    result_path: Path
    public_summary_path: Path
    profile_output_path: Path


def run_morning_strategy_optimization(
    config: MorningOptimizationConfig,
    *,
    store: SQLiteStore | None = None,
) -> MorningStrategyOptimizationResult:
    validate_config(config)
    started_at = utc_now()
    store = store or SQLiteStore(config.db_path)
    auction_import = ensure_auction_coverage(config, store)
    symbols = store.list_auction_profile_symbols(
        start=config.start,
        end=config.end,
        provider=config.auction_provider,
        limit=config.limit,
    )
    windows = tuple(month_windows(config.start, config.end, 1))
    profiles: list[MorningOptimizedProfile] = []
    for horizon in HORIZONS:
        for objective in OBJECTIVES:
            profiles.append(
                optimize_profile(
                    store=store,
                    symbols=symbols,
                    windows=windows,
                    config=config,
                    horizon=horizon,
                    objective=objective,
                )
            )

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "optimization_profiles.json"
    result_path.write_text(json.dumps(to_jsonable(profiles), ensure_ascii=False, indent=2), encoding="utf-8")
    profile_output_path = Path(config.profile_output_path)
    profile_output_path.parent.mkdir(parents=True, exist_ok=True)
    profile_output_path.write_text(build_profile_config(profiles), encoding="utf-8")
    public_summary_path = Path(config.public_summary_path)
    public_summary_path.parent.mkdir(parents=True, exist_ok=True)
    finished_at = utc_now()
    result = MorningStrategyOptimizationResult(
        started_at=started_at,
        finished_at=finished_at,
        config=config,
        profiles=tuple(profiles),
        auction_import=auction_import,
        result_path=result_path,
        public_summary_path=public_summary_path,
        profile_output_path=profile_output_path,
    )
    public_summary_path.write_text(build_public_summary(result), encoding="utf-8")
    return result


def ensure_auction_coverage(
    config: MorningOptimizationConfig,
    store: SQLiteStore,
) -> Any | None:
    if not config.import_missing_auction:
        return None
    provider_start, provider_end, provider_rows = auction_provider_range(
        store,
        config.auction_provider,
    )
    start_ok = provider_start is not None and provider_start <= config.start
    end_ok = provider_end is not None and provider_end >= config.end
    if provider_rows > 0 and start_ok and end_ok:
        return None
    return import_local_auction_cache(
        LocalAuctionCacheImportConfig(
            source_dir=config.auction_source_dir,
            db_path=config.db_path,
            start=config.start,
            end=config.end,
            provider=config.auction_provider,
            conflict="ignore",
        )
    )


def auction_provider_range(
    store: SQLiteStore,
    provider: str,
) -> tuple[date | None, date | None, int]:
    store.init_schema()
    with store.connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS rows,
                   MIN(trade_date) AS start,
                   MAX(trade_date) AS end
            FROM auction_profiles
            WHERE provider = ?
            """,
            (provider,),
        ).fetchone()
    return (
        date.fromisoformat(row["start"]) if row["start"] else None,
        date.fromisoformat(row["end"]) if row["end"] else None,
        int(row["rows"] or 0),
    )


def optimize_profile(
    *,
    store: SQLiteStore,
    symbols: Sequence[str],
    windows: Sequence[AuctionRollingWindow],
    config: MorningOptimizationConfig,
    horizon: str,
    objective: str,
) -> MorningOptimizedProfile:
    variants = variants_for_horizon(horizon)
    selected: list[tuple[MorningStrategyVariant, MorningOptimizationMetrics]] = []
    for window in windows:
        train_end = window.start - timedelta(days=1)
        train_start = max(config.start, train_end - timedelta(days=config.training_days))
        if train_start > train_end:
            continue
        training_scores = [
            (
                variant,
                evaluate_variant(
                    store=store,
                    symbols=symbols,
                    start=train_start,
                    end=train_end,
                    config=config,
                    variant=variant,
                ),
            )
            for variant in variants
        ]
        best_variant, _ = max(
            training_scores,
            key=lambda item: objective_score(item[1], objective, min_trades=config.min_trades),
        )
        selected.append(
            (
                best_variant,
                evaluate_variant(
                    store=store,
                    symbols=symbols,
                    start=window.start,
                    end=window.end,
                    config=config,
                    variant=best_variant,
                ),
            )
        )

    if not selected:
        whole_range = [
            (
                variant,
                evaluate_variant(
                    store=store,
                    symbols=symbols,
                    start=config.start,
                    end=config.end,
                    config=config,
                    variant=variant,
                ),
            )
            for variant in variants
        ]
        best_variant, metrics = max(
            whole_range,
            key=lambda item: objective_score(item[1], objective, min_trades=config.min_trades),
        )
        return profile_from_variant(
            best_variant,
            objective=objective,
            metrics=metrics,
            selected_windows=0,
            min_trades=config.min_trades,
        )

    label_counts = Counter(variant.label for variant, _ in selected)
    metrics_by_label = {
        label: aggregate_metrics(
            metrics for variant, metrics in selected if variant.label == label
        )
        for label in label_counts
    }
    best_label = max(
        metrics_by_label,
        key=lambda label: (
            label_counts[label],
            objective_score(metrics_by_label[label], objective, min_trades=config.min_trades),
        ),
    )
    best_variant = next(variant for variant, _ in selected if variant.label == best_label)
    return profile_from_variant(
        best_variant,
        objective=objective,
        metrics=metrics_by_label[best_label],
        selected_windows=label_counts[best_label],
        min_trades=config.min_trades,
    )


def evaluate_variant(
    *,
    store: SQLiteStore,
    symbols: Sequence[str],
    start: date,
    end: date,
    config: MorningOptimizationConfig,
    variant: MorningStrategyVariant,
) -> MorningOptimizationMetrics:
    strategy = build_screening_strategy(
        variant.strategy_id,
        min_volume_ratio=float(variant.parameters.get("min_volume_ratio", 1.5)),
        min_auction_score=optional_float(variant.parameters.get("min_auction_score")),
        auction_score_weight=float(variant.parameters.get("auction_score_weight", 0.15)),
    )
    backtest_config = BacktestConfig(
        max_holding_bars=int(variant.backtest.get("max_holding_bars", 20)),
        stop_atr_multiple=float(variant.backtest.get("stop_atr_multiple", 2.0)),
        take_profit_r_multiple=float(variant.backtest.get("take_profit_r_multiple", 2.0)),
    )
    trades = []
    returns: list[float] = []
    drawdowns: list[float] = []
    total_returns: list[float] = []
    traded_symbols = 0
    warmup_start = start - timedelta(days=180)
    for symbol in symbols:
        bars = store.get_daily_bars(symbol, start=warmup_start, end=end, adjust=config.adjust)
        profiles = {
            profile.trade_date: profile
            for profile in store.get_auction_profiles(
                symbol,
                start=start,
                end=end,
                provider=config.auction_provider,
            )
        }
        if not bars or not profiles:
            continue
        result = run_morning_plan_backtest(
            symbol,
            bars,
            horizon=variant.horizon,
            strategy=strategy,
            config=backtest_config,
            auction_profiles=profiles,
        )
        if result.trade_count:
            traded_symbols += 1
            trades.extend(result.trades)
            returns.extend(trade.return_pct for trade in result.trades)
            drawdowns.append(result.max_drawdown)
            total_returns.append(result.total_return)
    win_rate = sum(1 for trade in trades if trade.pnl > 0) / len(trades) if trades else 0.0
    return MorningOptimizationMetrics(
        win_rate=win_rate,
        avg_trade_return=average(returns),
        total_return=average(total_returns),
        max_drawdown=min(drawdowns) if drawdowns else 0.0,
        trade_count=len(trades),
        symbol_count=traded_symbols,
    )


def variants_for_horizon(horizon: str) -> tuple[MorningStrategyVariant, ...]:
    if horizon == "short_term":
        return (
            MorningStrategyVariant("short_balanced", horizon, "auction_open_breakout_short", {"min_auction_score": 58.0, "auction_score_weight": 0.35}, {"max_holding_bars": 3, "stop_atr_multiple": 1.1, "take_profit_r_multiple": 1.5}, 68.0),
            MorningStrategyVariant("short_win", horizon, "auction_gap_reversal_short", {"min_auction_score": 65.0, "auction_score_weight": 0.4}, {"max_holding_bars": 2, "stop_atr_multiple": 1.0, "take_profit_r_multiple": 1.2}, 72.0),
            MorningStrategyVariant("short_return", horizon, "auction_open_breakout_short", {"min_auction_score": 55.0, "auction_score_weight": 0.3}, {"max_holding_bars": 3, "stop_atr_multiple": 1.1, "take_profit_r_multiple": 2.0}, 70.0),
        )
    if horizon == "mid_short_term":
        return (
            MorningStrategyVariant("swing_pullback_balanced", horizon, "pullback_recovery_swing", {"min_volume_ratio": 1.3, "auction_score_weight": 0.12}, {"max_holding_bars": 8, "stop_atr_multiple": 1.6, "take_profit_r_multiple": 1.8}, 70.0),
            MorningStrategyVariant("swing_pullback_win", horizon, "pullback_recovery_swing", {"min_volume_ratio": 1.5, "min_auction_score": 55.0, "auction_score_weight": 0.18}, {"max_holding_bars": 6, "stop_atr_multiple": 1.4, "take_profit_r_multiple": 1.4}, 74.0),
            MorningStrategyVariant("swing_lowvol_return", horizon, "low_volatility_breakout", {"min_volume_ratio": 1.4, "auction_score_weight": 0.1}, {"max_holding_bars": 10, "stop_atr_multiple": 1.7, "take_profit_r_multiple": 2.2}, 72.0),
        )
    return (
        MorningStrategyVariant("mid_balanced", horizon, "trend_quality_mid", {"auction_score_weight": 0.04}, {"max_holding_bars": 24, "stop_atr_multiple": 2.0, "take_profit_r_multiple": 1.8}, 72.0),
        MorningStrategyVariant("mid_win", horizon, "trend_quality_mid", {"auction_score_weight": 0.02}, {"max_holding_bars": 18, "stop_atr_multiple": 1.8, "take_profit_r_multiple": 1.4}, 76.0),
        MorningStrategyVariant("mid_return", horizon, "trend_quality_mid", {"auction_score_weight": 0.03}, {"max_holding_bars": 30, "stop_atr_multiple": 2.2, "take_profit_r_multiple": 2.4}, 74.0),
    )


def profile_from_variant(
    variant: MorningStrategyVariant,
    *,
    objective: str,
    metrics: MorningOptimizationMetrics,
    selected_windows: int,
    min_trades: int,
) -> MorningOptimizedProfile:
    return MorningOptimizedProfile(
        objective=objective,
        horizon=variant.horizon,
        strategy_id=variant.strategy_id,
        parameters=variant.parameters,
        backtest=variant.backtest,
        min_candidate_score=variant.min_candidate_score,
        qualified=profile_qualified(metrics, objective, min_trades=min_trades),
        metrics=metrics,
        selected_windows=selected_windows,
        label=variant.label,
    )


def profile_qualified(
    metrics: MorningOptimizationMetrics,
    objective: str,
    *,
    min_trades: int,
) -> bool:
    if metrics.trade_count < min_trades:
        return False
    if objective == "win_rate":
        return metrics.win_rate >= 0.45 and metrics.avg_trade_return >= 0
    if objective == "return":
        return metrics.avg_trade_return > 0 and metrics.total_return > 0
    return metrics.avg_trade_return > 0 and metrics.max_drawdown >= -0.18


def objective_score(
    metrics: MorningOptimizationMetrics,
    objective: str,
    *,
    min_trades: int,
) -> float:
    trade_penalty = 0.0 if metrics.trade_count >= min_trades else -100.0
    if objective == "win_rate":
        return trade_penalty + metrics.win_rate * 100 + metrics.avg_trade_return * 200
    if objective == "return":
        return trade_penalty + metrics.avg_trade_return * 400 + metrics.total_return * 100
    return (
        trade_penalty
        + metrics.avg_trade_return * 250
        + metrics.win_rate * 40
        + metrics.total_return * 40
        + metrics.max_drawdown * 25
    )


def aggregate_metrics(metrics_values: Sequence[MorningOptimizationMetrics]) -> MorningOptimizationMetrics:
    rows = list(metrics_values)
    if not rows:
        return MorningOptimizationMetrics(0.0, 0.0, 0.0, 0.0, 0, 0)
    return MorningOptimizationMetrics(
        win_rate=average(row.win_rate for row in rows),
        avg_trade_return=average(row.avg_trade_return for row in rows),
        total_return=average(row.total_return for row in rows),
        max_drawdown=min(row.max_drawdown for row in rows),
        trade_count=sum(row.trade_count for row in rows),
        symbol_count=sum(row.symbol_count for row in rows),
    )


def build_profile_config(profiles: Sequence[MorningOptimizedProfile]) -> str:
    grouped: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        grouped.setdefault(profile.horizon, {})[profile.objective] = {
            "objective": profile.objective,
            "horizon": profile.horizon,
            "strategy_id": profile.strategy_id,
            "parameters": profile.parameters,
            "backtest": profile.backtest,
            "min_candidate_score": profile.min_candidate_score,
            "qualified": profile.qualified,
            "metrics": to_jsonable(profile.metrics),
            "selected_windows": profile.selected_windows,
            "label": profile.label,
        }
    payload = {
        "generated_at": utc_now().isoformat(),
        "source": "research optimize-morning-strategies",
        "profiles": grouped,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def build_public_summary(result: MorningStrategyOptimizationResult) -> str:
    lines = [
        "# 早盘多目标策略优化汇总",
        "",
        f"- 区间：`{result.config.start}` 至 `{result.config.end}`",
        f"- 竞价源：`{result.config.auction_provider}`",
        f"- 股票上限：{result.config.limit if result.config.limit is not None else '全量'}",
        f"- Profile：`{result.profile_output_path}`",
        "",
        "| 周期 | 目标 | 策略 | 合格 | 胜率 | 平均单笔 | 总收益 | 最大回撤 | 交易数 | 最低分 |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for profile in result.profiles:
        lines.append(
            f"| {profile.horizon} | {profile.objective} | {profile.strategy_id} | "
            f"{'yes' if profile.qualified else 'no'} | {format_pct(profile.metrics.win_rate)} | "
            f"{format_pct(profile.metrics.avg_trade_return)} | {format_pct(profile.metrics.total_return)} | "
            f"{format_pct(profile.metrics.max_drawdown)} | {profile.metrics.trade_count} | "
            f"{profile.min_candidate_score:.1f} |"
        )
    lines.extend(
        [
            "",
            "## 使用说明",
            "",
            "- `balanced`、`win_rate`、`return` 会分别输出候选；不合格或未达最低分时不硬选。",
            "- 该优化结果是研究辅助，不构成投资建议。",
        ]
    )
    return "\n".join(lines) + "\n"


def validate_config(config: MorningOptimizationConfig) -> None:
    if config.start > config.end:
        raise ValueError("start must be before or equal to end")
    if config.limit is not None and config.limit <= 0:
        raise ValueError("limit must be a positive integer")
    if config.training_days <= 0:
        raise ValueError("training_days must be a positive integer")
    if config.min_trades <= 0:
        raise ValueError("min_trades must be a positive integer")


def average(values: Sequence[float] | Any) -> float:
    rows = list(values)
    return sum(rows) / len(rows) if rows else 0.0


def optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value
