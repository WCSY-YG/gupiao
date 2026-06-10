"""Markdown performance and risk reports."""

from __future__ import annotations

from pathlib import Path

from gupiao.backtest import BacktestResult
from gupiao.signals import SignalPlan
from gupiao.strategies import ScreeningCandidate


def build_markdown_report(
    *,
    title: str,
    candidate: ScreeningCandidate | None,
    signal: SignalPlan | None,
    backtest: BacktestResult,
) -> str:
    lines = [
        f"# {title}",
        "",
        "## 摘要",
        "",
        f"- 股票代码：`{backtest.symbol}`",
        f"- 总收益：{format_pct(backtest.total_return)}",
        f"- 最大回撤：{format_pct(backtest.max_drawdown)}",
        f"- 胜率：{format_pct(backtest.win_rate)}",
        f"- 交易次数：{backtest.trade_count}",
        "",
    ]
    if candidate is not None:
        lines.extend(candidate_section(candidate))
    if signal is not None:
        lines.extend(signal_section(signal))
    lines.extend(backtest_section(backtest))
    lines.extend(risk_section(backtest))
    return "\n".join(lines).rstrip() + "\n"


def write_markdown_report(path: str | Path, content: str) -> Path:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(content, encoding="utf-8")
    return report_path


def candidate_section(candidate: ScreeningCandidate) -> list[str]:
    lines = [
        "## 候选股与命中原因",
        "",
        f"- 策略：`{candidate.strategy}`",
        f"- 交易日：{candidate.trade_date.isoformat()}",
        f"- 评分：{candidate.score:.2f}",
        "",
        "命中原因：",
    ]
    lines.extend(f"- {reason}" for reason in candidate.reasons)
    lines.append("")
    if candidate.metrics:
        lines.append("关键指标：")
        for key, value in sorted(candidate.metrics.items()):
            lines.append(f"- `{key}`：{value:.4f}")
        lines.append("")
    return lines


def signal_section(signal: SignalPlan) -> list[str]:
    lines = [
        "## 买卖点计划",
        "",
        f"- 方向：`{signal.direction}`",
        f"- 置信度：{signal.confidence:.2f}",
        f"- 入场价：{signal.entry_price:.4f}",
        f"- 加仓价：{signal.add_price:.4f}",
        f"- 减仓价：{signal.reduce_price:.4f}",
        f"- 止损价：{signal.stop_loss:.4f}",
        f"- 止盈价：{signal.take_profit:.4f}",
        f"- 风险收益比：{signal.risk_reward:.2f}",
        f"- 失效条件：{signal.invalidation}",
        "",
        "信号解释：",
    ]
    lines.extend(f"- {reason}" for reason in signal.reasons)
    lines.append("")
    return lines


def backtest_section(backtest: BacktestResult) -> list[str]:
    lines = [
        "## 回测结果",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| 总收益 | {format_pct(backtest.total_return)} |",
        f"| 最大回撤 | {format_pct(backtest.max_drawdown)} |",
        f"| 胜率 | {format_pct(backtest.win_rate)} |",
        f"| 交易次数 | {backtest.trade_count} |",
        "",
        "交易明细：",
        "",
        "| 入场日 | 出场日 | 入场价 | 出场价 | 收益 | 原因 |",
        "|---|---|---:|---:|---:|---|",
    ]
    if not backtest.trades:
        lines.append("| - | - | - | - | - | 无交易 |")
    else:
        for trade in backtest.trades:
            lines.append(
                "| "
                f"{trade.entry_date.isoformat()} | {trade.exit_date.isoformat()} | "
                f"{trade.entry_price:.4f} | {trade.exit_price:.4f} | "
                f"{format_pct(trade.return_pct)} | {trade.exit_reason} |"
            )
    lines.append("")
    return lines


def risk_section(backtest: BacktestResult) -> list[str]:
    lines = [
        "## 风险提示与假设",
        "",
        "- 本报告仅用于研究和辅助分析，不构成投资建议。",
        "- 历史回测不代表未来收益，参数可能存在过拟合风险。",
        "- 数据质量、复权方式、停牌、涨跌停和成交假设会显著影响结果。",
        "",
        "回测假设：",
    ]
    lines.extend(f"- {assumption}" for assumption in backtest.assumptions)
    lines.append("")
    return lines


def format_pct(value: float) -> str:
    return f"{value * 100:.2f}%"
