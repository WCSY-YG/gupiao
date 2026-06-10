"""Standalone HTML dashboard for strategy research results."""

from __future__ import annotations

from html import escape
from pathlib import Path

from gupiao.backtest import BacktestResult
from gupiao.reports import format_pct
from gupiao.signals import SignalPlan
from gupiao.strategies import ScreeningCandidate


def build_dashboard_html(
    *,
    title: str,
    candidate: ScreeningCandidate | None,
    signal: SignalPlan | None,
    backtest: BacktestResult,
) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #1d2430;
      --muted: #687385;
      --line: #d9dee7;
      --good: #0f8b62;
      --bad: #b42318;
      --accent: #2563eb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, "Noto Sans SC", sans-serif;
      line-height: 1.5;
    }}
    header, main {{ max-width: 1180px; margin: 0 auto; padding: 20px; }}
    header {{ padding-top: 28px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    h2 {{ margin: 0 0 14px; font-size: 18px; }}
    .muted {{ color: var(--muted); }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;
    }}
    .kpi .label {{ color: var(--muted); font-size: 12px; }}
    .kpi .value {{ font-size: 24px; font-weight: 700; }}
    .good {{ color: var(--good); }}
    .bad {{ color: var(--bad); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px; text-align: left; }}
    th {{ color: var(--muted); font-weight: 600; }}
    ul {{ margin: 8px 0 0; padding-left: 20px; }}
    svg {{ display: block; width: 100%; height: auto; }}
    @media (max-width: 760px) {{
      .grid {{ grid-template-columns: repeat(2, 1fr); }}
      header, main {{ padding: 14px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(title)}</h1>
    <div class="muted">股票代码：{escape(backtest.symbol)}</div>
  </header>
  <main>
    {kpi_grid(backtest)}
    {candidate_panel(candidate)}
    {signal_panel(signal)}
    {equity_panel(backtest)}
    {trades_panel(backtest)}
    {risk_panel(backtest)}
  </main>
</body>
</html>
"""


def write_dashboard_html(path: str | Path, content: str) -> Path:
    dashboard_path = Path(path)
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text(content, encoding="utf-8")
    return dashboard_path


def kpi_grid(backtest: BacktestResult) -> str:
    return f"""
    <section class="grid">
      {kpi("总收益", format_pct(backtest.total_return), signed_class(backtest.total_return))}
      {kpi("最大回撤", format_pct(backtest.max_drawdown), "bad")}
      {kpi("胜率", format_pct(backtest.win_rate), "")}
      {kpi("交易次数", str(backtest.trade_count), "")}
    </section>
    """


def kpi(label: str, value: str, css_class: str) -> str:
    return f"""
    <div class="panel kpi">
      <div class="label">{escape(label)}</div>
      <div class="value {escape(css_class)}">{escape(value)}</div>
    </div>
    """


def candidate_panel(candidate: ScreeningCandidate | None) -> str:
    if candidate is None:
        return panel("候选股", "<p class=\"muted\">无候选结果。</p>")
    reasons = "".join(f"<li>{escape(reason)}</li>" for reason in candidate.reasons)
    metrics = "".join(
        f"<tr><td>{escape(key)}</td><td>{value:.4f}</td></tr>"
        for key, value in sorted(candidate.metrics.items())
    )
    body = f"""
    <p>策略：<strong>{escape(candidate.strategy)}</strong>，评分：{candidate.score:.2f}</p>
    <ul>{reasons}</ul>
    <table><tbody>{metrics}</tbody></table>
    """
    return panel("候选股与指标", body)


def signal_panel(signal: SignalPlan | None) -> str:
    if signal is None:
        return panel("买卖点", "<p class=\"muted\">无信号计划。</p>")
    body = f"""
    <table>
      <tbody>
        <tr><th>方向</th><td>{escape(signal.direction)}</td></tr>
        <tr><th>入场</th><td>{signal.entry_price:.4f}</td></tr>
        <tr><th>加仓</th><td>{signal.add_price:.4f}</td></tr>
        <tr><th>减仓</th><td>{signal.reduce_price:.4f}</td></tr>
        <tr><th>止损</th><td>{signal.stop_loss:.4f}</td></tr>
        <tr><th>止盈</th><td>{signal.take_profit:.4f}</td></tr>
        <tr><th>失效</th><td>{escape(signal.invalidation)}</td></tr>
      </tbody>
    </table>
    """
    return panel("买卖点计划", body)


def equity_panel(backtest: BacktestResult) -> str:
    return panel("权益曲线", equity_svg([point.equity for point in backtest.equity_curve]))


def trades_panel(backtest: BacktestResult) -> str:
    rows = ""
    for trade in backtest.trades:
        rows += (
            "<tr>"
            f"<td>{trade.entry_date.isoformat()}</td>"
            f"<td>{trade.exit_date.isoformat()}</td>"
            f"<td>{trade.entry_price:.4f}</td>"
            f"<td>{trade.exit_price:.4f}</td>"
            f"<td>{format_pct(trade.return_pct)}</td>"
            f"<td>{escape(trade.exit_reason)}</td>"
            "</tr>"
        )
    if not rows:
        rows = "<tr><td colspan=\"6\" class=\"muted\">无交易</td></tr>"
    body = f"""
    <table>
      <thead>
        <tr><th>入场日</th><th>出场日</th><th>入场价</th><th>出场价</th><th>收益</th><th>原因</th></tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """
    return panel("交易明细", body)


def risk_panel(backtest: BacktestResult) -> str:
    assumptions = "".join(f"<li>{escape(item)}</li>" for item in backtest.assumptions)
    body = f"""
    <ul>
      <li>本页面仅用于研究和辅助分析，不构成投资建议。</li>
      <li>历史回测不代表未来收益，需警惕过拟合和数据偏差。</li>
      {assumptions}
    </ul>
    """
    return panel("风险提示", body)


def panel(title: str, body: str) -> str:
    return f"<section class=\"panel\"><h2>{escape(title)}</h2>{body}</section>"


def equity_svg(values: list[float]) -> str:
    if not values:
        return "<p class=\"muted\">无权益数据。</p>"
    width = 900
    height = 260
    padding = 24
    low = min(values)
    high = max(values)
    span = high - low or 1.0
    points = []
    for index, value in enumerate(values):
        x = padding + (index / max(len(values) - 1, 1)) * (width - padding * 2)
        y = height - padding - ((value - low) / span) * (height - padding * 2)
        points.append(f"{x:.2f},{y:.2f}")
    return f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="equity curve">
      <rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>
      <polyline points="{' '.join(points)}" fill="none" stroke="#2563eb" stroke-width="3"/>
      <text x="{padding}" y="{padding}" fill="#687385">{high:.2f}</text>
      <text x="{padding}" y="{height - 8}" fill="#687385">{low:.2f}</text>
    </svg>
    """


def signed_class(value: float) -> str:
    if value > 0:
        return "good"
    if value < 0:
        return "bad"
    return ""
