"""Standalone HTML dashboard for strategy research results."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import fields, is_dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from gupiao.backtest import BacktestConfig, BacktestResult
from gupiao.data import AuctionProfile, DailyBar, ValidationIssue, validate_daily_bars
from gupiao.reports import format_pct
from gupiao.signals import SignalPlan
from gupiao.strategies import ScreeningCandidate, ScreeningStrategy


def build_dashboard_html(
    *,
    title: str,
    candidate: ScreeningCandidate | None,
    signal: SignalPlan | None,
    backtest: BacktestResult,
    bars: Sequence[DailyBar] | None = None,
    strategy: ScreeningStrategy | None = None,
    backtest_config: BacktestConfig | None = None,
    auction_profile: AuctionProfile | None = None,
    source_path: str | Path | None = None,
    generated_at: datetime | None = None,
    commands: Sequence[str] | None = None,
) -> str:
    ordered_bars = sorted(bars or (), key=lambda item: item.trade_date)
    issues = validate_daily_bars(bars or ())
    generated = generated_at or datetime.now().astimezone()
    candidate_score = optional_score(candidate.score if candidate else None)
    signal_risk_reward = optional_ratio(signal.risk_reward if signal else None)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f6f8;
      --surface: #ffffff;
      --surface-soft: #f9fafb;
      --text: #18202c;
      --muted: #647083;
      --line: #d8dee8;
      --line-soft: #e8edf3;
      --accent: #1d5fd1;
      --accent-soft: #e9f1ff;
      --good: #0b7a53;
      --good-soft: #e8f6ef;
      --bad: #b42318;
      --bad-soft: #fdeceb;
      --warn: #a15c00;
      --warn-soft: #fff4df;
      --ink-soft: #eef1f5;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, "Noto Sans SC", "Microsoft YaHei", sans-serif;
      line-height: 1.5;
    }}
    a {{ color: inherit; }}
    header {{
      background: var(--surface);
      border-bottom: 1px solid var(--line);
    }}
    .wrap {{
      width: min(1240px, calc(100% - 32px));
      margin: 0 auto;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 24px;
      padding: 26px 0 18px;
      align-items: end;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: clamp(26px, 3vw, 38px);
      line-height: 1.12;
      letter-spacing: 0;
    }}
    h2 {{ margin: 0 0 16px; font-size: 20px; letter-spacing: 0; }}
    h3 {{ margin: 0 0 12px; font-size: 16px; letter-spacing: 0; }}
    p {{ margin: 0 0 12px; }}
    .muted {{ color: var(--muted); }}
    .meta-row, .status-row, nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 4px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--surface-soft);
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }}
    .status {{
      min-width: 92px;
      justify-content: center;
      font-weight: 700;
    }}
    .status.good {{ background: var(--good-soft); border-color: #b9e4ce; color: var(--good); }}
    .status.bad {{ background: var(--bad-soft); border-color: #fac5c0; color: var(--bad); }}
    .status.warn {{ background: var(--warn-soft); border-color: #f7d08a; color: var(--warn); }}
    .nav-band {{
      border-top: 1px solid var(--line-soft);
      padding: 10px 0 12px;
    }}
    nav a {{
      color: var(--muted);
      font-size: 14px;
      padding: 6px 0;
      margin-right: 16px;
      text-decoration: none;
      border-bottom: 2px solid transparent;
    }}
    nav a:hover {{ color: var(--accent); border-color: var(--accent); }}
    main {{ padding: 22px 0 40px; }}
    section.band {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin-bottom: 16px;
      padding: 18px;
      overflow: hidden;
    }}
    .grid {{
      display: grid;
      gap: 12px;
    }}
    .kpi-grid {{ grid-template-columns: repeat(6, minmax(0, 1fr)); }}
    .two-col {{ grid-template-columns: minmax(0, 1.5fr) minmax(300px, 0.9fr); }}
    .three-col {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .metric {{
      min-height: 104px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: var(--surface-soft);
    }}
    .metric .label {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
    }}
    .metric .value {{
      font-size: 24px;
      font-weight: 800;
      overflow-wrap: anywhere;
    }}
    .good {{ color: var(--good); }}
    .bad {{ color: var(--bad); }}
    .warn {{ color: var(--warn); }}
    .panel {{
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: var(--surface-soft);
      padding: 14px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line-soft);
      padding: 10px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-weight: 700;
      white-space: nowrap;
    }}
    tbody tr:last-child th, tbody tr:last-child td {{ border-bottom: 0; }}
    .right {{ text-align: right; }}
    .table-scroll {{ overflow-x: auto; }}
    ul.clean {{
      margin: 0;
      padding-left: 18px;
    }}
    ul.clean li {{ margin: 0 0 8px; }}
    .reason-list {{
      display: grid;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
    }}
    .reason-list li {{
      border-left: 3px solid var(--accent);
      background: var(--accent-soft);
      border-radius: 6px;
      padding: 9px 10px;
    }}
    .chart {{
      min-height: 260px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: #ffffff;
      overflow: hidden;
    }}
    svg {{ display: block; width: 100%; height: auto; }}
    code {{
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      font-size: 13px;
    }}
    pre {{
      margin: 0;
      overflow-x: auto;
      padding: 12px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: #111827;
      color: #e5e7eb;
      font-size: 13px;
      line-height: 1.55;
    }}
    details {{
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      padding: 10px 12px;
      background: var(--surface-soft);
    }}
    summary {{ cursor: pointer; font-weight: 700; }}
    .empty {{
      padding: 18px;
      color: var(--muted);
      background: var(--surface-soft);
      border: 1px dashed var(--line);
      border-radius: 8px;
    }}
    @media (max-width: 1080px) {{
      .kpi-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .two-col, .three-col {{ grid-template-columns: 1fr; }}
      .hero {{ grid-template-columns: 1fr; align-items: start; }}
    }}
    @media (max-width: 680px) {{
      .wrap {{ width: min(100% - 24px, 1240px); }}
      .kpi-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      section.band {{ padding: 14px; }}
      .metric .value {{ font-size: 20px; }}
      th, td {{ padding: 8px 6px; }}
      nav a {{ margin-right: 10px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="wrap hero">
      <div>
        <h1>{escape(title)}</h1>
        {metadata_row(backtest, ordered_bars, generated, source_path)}
      </div>
      {status_row(candidate, signal, backtest, issues, auction_profile)}
    </div>
    <div class="nav-band">
      <div class="wrap">
        <nav aria-label="Dashboard navigation">
          <a href="#overview">总览</a>
          <a href="#market">行情</a>
          <a href="#strategy">策略</a>
          <a href="#signal">买卖点</a>
          <a href="#backtest">回测</a>
          <a href="#trades">交易</a>
          <a href="#quality">质量</a>
          <a href="#commands">命令</a>
        </nav>
      </div>
    </div>
  </header>
  <main class="wrap">
    <section id="overview" class="grid kpi-grid">
      {kpi("总收益", format_pct(backtest.total_return), signed_class(backtest.total_return))}
      {kpi("最大回撤", format_pct(backtest.max_drawdown), "bad")}
      {kpi("胜率", format_pct(backtest.win_rate), signed_class(backtest.win_rate - 0.5))}
      {kpi("交易次数", str(backtest.trade_count), "")}
      {kpi("候选评分", candidate_score, score_class(candidate))}
      {kpi("风险收益比", signal_risk_reward, ratio_class(signal))}
    </section>
    {market_section(ordered_bars)}
    {strategy_section(candidate, strategy, auction_profile)}
    {signal_section(signal)}
    {backtest_section(backtest, backtest_config)}
    {trades_section(backtest)}
    {quality_section(issues)}
    {commands_section(commands)}
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
    <section class="grid kpi-grid">
      {kpi("总收益", format_pct(backtest.total_return), signed_class(backtest.total_return))}
      {kpi("最大回撤", format_pct(backtest.max_drawdown), "bad")}
      {kpi("胜率", format_pct(backtest.win_rate), signed_class(backtest.win_rate - 0.5))}
      {kpi("交易次数", str(backtest.trade_count), "")}
    </section>
    """


def signal_panel(signal: SignalPlan | None) -> str:
    return signal_section(signal)


def equity_panel(backtest: BacktestResult) -> str:
    return band("equity", "权益曲线", equity_svg([point.equity for point in backtest.equity_curve]))


def trades_panel(backtest: BacktestResult) -> str:
    return trades_section(backtest)


def panel(title: str, body: str) -> str:
    return band("panel", title, body)


def metadata_row(
    backtest: BacktestResult,
    bars: Sequence[DailyBar],
    generated_at: datetime,
    source_path: str | Path | None,
) -> str:
    date_range = "无行情区间"
    if bars:
        date_range = f"{bars[0].trade_date.isoformat()} 至 {bars[-1].trade_date.isoformat()}"
    chips = [
        f"股票代码：{backtest.symbol}",
        f"区间：{date_range}",
        f"生成：{generated_at.strftime('%Y-%m-%d %H:%M:%S %Z').strip()}",
    ]
    if source_path is not None:
        chips.append(f"来源：{source_path}")
    return "<div class=\"meta-row\">" + "".join(chip(item) for item in chips) + "</div>"


def status_row(
    candidate: ScreeningCandidate | None,
    signal: SignalPlan | None,
    backtest: BacktestResult,
    issues: Sequence[ValidationIssue],
    auction_profile: AuctionProfile | None,
) -> str:
    quality_class = "good" if not issues else "bad" if has_error_issue(issues) else "warn"
    quality_label = "质量通过" if not issues else f"质量 {len(issues)} 项"
    auction_label = "竞价已接入" if auction_profile is not None else "竞价未接入"
    auction_class = "good" if auction_profile is not None else "warn"
    items = [
        status_chip("候选命中" if candidate else "无候选", "good" if candidate else "warn"),
        status_chip("信号可用" if signal else "无信号", "good" if signal else "warn"),
        status_chip("已回测" if backtest.equity_curve else "无回测", "good"),
        status_chip(auction_label, auction_class),
        status_chip(quality_label, quality_class),
    ]
    return "<div class=\"status-row\">" + "".join(items) + "</div>"


def market_section(bars: Sequence[DailyBar]) -> str:
    if not bars:
        return band("market", "行情走势", "<div class=\"empty\">无日线数据。</div>")
    latest = bars[-1]
    previous = bars[-2] if len(bars) >= 2 else None
    change_pct = (latest.close / previous.close) - 1 if previous and previous.close > 0 else None
    change_class = signed_class(change_pct or 0.0)
    change_value = format_optional_pct(change_pct)
    body = f"""
    <div class="grid two-col">
      <div class="chart">{price_volume_svg(bars)}</div>
      <div class="grid">
        <div class="panel">
          <h3>最新交易日</h3>
          <table>
            <tbody>
              <tr><th>日期</th><td>{latest.trade_date.isoformat()}</td></tr>
              <tr><th>开盘</th><td>{format_number(latest.open)}</td></tr>
              <tr><th>最高</th><td>{format_number(latest.high)}</td></tr>
              <tr><th>最低</th><td>{format_number(latest.low)}</td></tr>
              <tr><th>收盘</th><td>{format_number(latest.close)}</td></tr>
              <tr><th>涨跌幅</th><td class="{change_class}">{change_value}</td></tr>
              <tr><th>成交量</th><td>{format_number(latest.volume)}</td></tr>
              <tr><th>成交额</th><td>{format_optional_number(latest.amount)}</td></tr>
              <tr><th>换手率</th><td>{format_optional_number(latest.turnover)}</td></tr>
            </tbody>
          </table>
        </div>
        <div class="panel">
          <h3>样本概览</h3>
          {bars_summary_table(bars)}
        </div>
      </div>
    </div>
    """
    return band("market", "行情走势", body)


def bars_summary_table(bars: Sequence[DailyBar]) -> str:
    closes = [bar.close for bar in bars]
    volumes = [bar.volume for bar in bars]
    body = rows(
        [
            ("日线数量", str(len(bars))),
            ("最高收盘", format_number(max(closes))),
            ("最低收盘", format_number(min(closes))),
            ("平均成交量", format_number(sum(volumes) / len(volumes))),
            ("复权", bars[-1].adjust or "-"),
            ("数据源", bars[-1].provider or "-"),
        ]
    )
    return f"<table><tbody>{body}</tbody></table>"


def strategy_section(
    candidate: ScreeningCandidate | None,
    strategy: ScreeningStrategy | None,
    auction_profile: AuctionProfile | None,
) -> str:
    parameter_panel = ""
    if strategy is not None:
        parameter_panel = f"""
        <div class="panel">
          <h3>策略参数</h3>
          {mapping_table(dataclass_public_values(strategy))}
        </div>
        """
    candidate_panel_html = candidate_panel(candidate)
    auction_panel_html = auction_panel(auction_profile, candidate)
    fallback_parameter_panel = (
        '<div class="panel"><h3>策略参数</h3>'
        '<div class="empty">无参数快照。</div></div>'
    )
    body = f"""
    <div class="grid three-col">
      {parameter_panel or fallback_parameter_panel}
      {candidate_panel_html}
      {auction_panel_html}
    </div>
    """
    return band("strategy", "策略与竞价", body)


def candidate_panel(candidate: ScreeningCandidate | None) -> str:
    if candidate is None:
        return '<div class="panel"><h3>候选股</h3><div class="empty">无候选结果。</div></div>'
    reasons = "".join(f"<li>{escape(reason)}</li>" for reason in candidate.reasons)
    metrics = "".join(
        f"<tr><td>{escape(key)}</td><td class=\"right\">{format_number(value)}</td></tr>"
        for key, value in sorted(candidate.metrics.items())
    )
    return f"""
    <div class="panel">
      <h3>候选股</h3>
      <table>
        <tbody>
          <tr><th>策略</th><td>{escape(candidate.strategy)}</td></tr>
          <tr><th>交易日</th><td>{candidate.trade_date.isoformat()}</td></tr>
          <tr><th>评分</th><td>{candidate.score:.2f}</td></tr>
        </tbody>
      </table>
      <h3>命中原因</h3>
      <ul class="reason-list">{reasons}</ul>
      <details>
        <summary>关键指标</summary>
        <div class="table-scroll"><table><tbody>{metrics}</tbody></table></div>
      </details>
    </div>
    """


def auction_panel(
    auction_profile: AuctionProfile | None,
    candidate: ScreeningCandidate | None,
) -> str:
    if auction_profile is None:
        candidate_metrics = candidate.metrics if candidate is not None else {}
        auction_metrics = {
            key: value for key, value in candidate_metrics.items() if key.startswith("auction_")
        }
        if not auction_metrics:
            return (
                '<div class="panel"><h3>竞价画像</h3>'
                '<div class="empty">当前结果未注入竞价画像。</div></div>'
            )
        return f"""
        <div class="panel">
          <h3>竞价画像</h3>
          {mapping_table(auction_metrics)}
        </div>
        """
    values = {
        "交易日": auction_profile.trade_date.isoformat(),
        "竞价时间": auction_profile.auction_time.strftime("%H:%M:%S"),
        "竞价价": format_number(auction_profile.indicative_price),
        "竞价量": format_number(auction_profile.volume),
        "强度分": format_number(auction_profile.strength_score),
        "缺口": format_optional_pct(auction_profile.gap_pct),
        "区间波动": format_optional_pct(auction_profile.range_pct),
        "量比": format_optional_number(auction_profile.volume_ratio_to_daily),
        "委买委卖": format_optional_number(auction_profile.bid_ask_imbalance),
        "数据源": auction_profile.provider or "-",
    }
    return f"""
    <div class="panel">
      <h3>竞价画像</h3>
      {mapping_table(values)}
    </div>
    """


def signal_section(signal: SignalPlan | None) -> str:
    if signal is None:
        return band("signal", "买卖点计划", "<div class=\"empty\">无信号计划。</div>")
    rows_html = rows(
        [
            ("方向", signal.direction),
            ("交易日", signal.trade_date.isoformat()),
            ("置信度", f"{signal.confidence:.2f}"),
            ("入场", format_number(signal.entry_price)),
            ("加仓", format_number(signal.add_price)),
            ("减仓", format_number(signal.reduce_price)),
            ("止损", format_number(signal.stop_loss)),
            ("止盈", format_number(signal.take_profit)),
            ("风险收益比", format_number(signal.risk_reward)),
            ("失效条件", signal.invalidation),
        ]
    )
    reasons = "".join(f"<li>{escape(reason)}</li>" for reason in signal.reasons)
    body = f"""
    <div class="grid two-col">
      <div class="panel">
        <h3>价格计划</h3>
        <table><tbody>{rows_html}</tbody></table>
      </div>
      <div class="panel">
        <h3>信号解释</h3>
        <ul class="reason-list">{reasons}</ul>
      </div>
    </div>
    """
    return band("signal", "买卖点计划", body)


def backtest_section(
    backtest: BacktestResult,
    backtest_config: BacktestConfig | None,
) -> str:
    metrics = rows(
        [
            ("总收益", format_pct(backtest.total_return)),
            ("最大回撤", format_pct(backtest.max_drawdown)),
            ("胜率", format_pct(backtest.win_rate)),
            ("交易次数", str(backtest.trade_count)),
            ("权益点数", str(len(backtest.equity_curve))),
        ]
    )
    config_panel = ""
    if backtest_config is not None:
        config_panel = f"""
        <div class="panel">
          <h3>回测配置</h3>
          {mapping_table(dataclass_public_values(backtest_config))}
        </div>
        """
    assumptions = "".join(f"<li>{escape(item)}</li>" for item in backtest.assumptions)
    body = f"""
    <div class="grid two-col">
      <div class="chart">{equity_svg([point.equity for point in backtest.equity_curve])}</div>
      <div class="grid">
        <div class="panel">
          <h3>回测指标</h3>
          <table><tbody>{metrics}</tbody></table>
        </div>
        {config_panel}
        <div class="panel">
          <h3>回测假设</h3>
          <ul class="clean">{assumptions}</ul>
        </div>
      </div>
    </div>
    """
    return band("backtest", "回测表现", body)


def trades_section(backtest: BacktestResult) -> str:
    rows_html = ""
    for trade in backtest.trades:
        pnl_class = signed_class(trade.pnl)
        return_class = signed_class(trade.return_pct)
        return_value = format_pct(trade.return_pct)
        rows_html += (
            "<tr>"
            f"<td>{trade.entry_date.isoformat()}</td>"
            f"<td>{trade.exit_date.isoformat()}</td>"
            f"<td class=\"right\">{format_number(trade.entry_price)}</td>"
            f"<td class=\"right\">{format_number(trade.exit_price)}</td>"
            f"<td class=\"right\">{format_number(trade.quantity)}</td>"
            f"<td class=\"right {pnl_class}\">{format_number(trade.pnl)}</td>"
            f"<td class=\"right {return_class}\">{return_value}</td>"
            f"<td class=\"right\">{trade.holding_bars}</td>"
            f"<td>{escape(trade.exit_reason)}</td>"
            "</tr>"
        )
    if not rows_html:
        rows_html = "<tr><td colspan=\"9\" class=\"muted\">无交易</td></tr>"
    body = f"""
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>入场日</th><th>出场日</th><th class="right">入场价</th>
            <th class="right">出场价</th><th class="right">数量</th>
            <th class="right">盈亏</th><th class="right">收益</th>
            <th class="right">持有</th><th>原因</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    """
    return band("trades", "交易明细", body)


def quality_section(issues: Sequence[ValidationIssue]) -> str:
    if not issues:
        return band("quality", "数据质量", "<div class=\"empty\">未发现数据质量问题。</div>")
    rows_html = ""
    for item in issues:
        rows_html += (
            "<tr>"
            f"<td>{escape(item.severity)}</td>"
            f"<td>{escape(item.code)}</td>"
            f"<td>{escape(item.symbol or '-')}</td>"
            f"<td>{item.trade_date.isoformat() if item.trade_date else '-'}</td>"
            f"<td>{escape(item.field or '-')}</td>"
            f"<td>{escape(item.message)}</td>"
            "</tr>"
        )
    body = f"""
    <div class="table-scroll">
      <table>
        <thead>
          <tr><th>级别</th><th>代码</th><th>股票</th><th>日期</th><th>字段</th><th>说明</th></tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    """
    return band("quality", "数据质量", body)


def commands_section(commands: Sequence[str] | None) -> str:
    if not commands:
        return band("commands", "命令面板", "<div class=\"empty\">无命令快照。</div>")
    blocks = "".join(f"<pre><code>{escape(command)}</code></pre>" for command in commands)
    return band("commands", "命令面板", f"<div class=\"grid\">{blocks}</div>")


def risk_panel(backtest: BacktestResult) -> str:
    assumptions = "".join(f"<li>{escape(item)}</li>" for item in backtest.assumptions)
    body = f"""
    <ul class="clean">
      <li>本页面仅用于研究和辅助分析，不构成投资建议。</li>
      <li>历史回测不代表未来收益，需警惕过拟合和数据偏差。</li>
      <li>交易成本、停牌、涨跌停、复权口径和样本区间都会影响结果。</li>
      {assumptions}
    </ul>
    """
    return band("risk", "风险提示", body)


def band(section_id: str, title: str, body: str) -> str:
    return (
        f"<section id=\"{escape(section_id)}\" class=\"band\">"
        f"<h2>{escape(title)}</h2>{body}</section>"
    )


def kpi(label: str, value: str, css_class: str) -> str:
    return f"""
    <div class="metric">
      <div class="label">{escape(label)}</div>
      <div class="value {escape(css_class)}">{escape(value)}</div>
    </div>
    """


def chip(label: str) -> str:
    return f"<span class=\"chip\">{escape(label)}</span>"


def status_chip(label: str, css_class: str) -> str:
    return f"<span class=\"chip status {escape(css_class)}\">{escape(label)}</span>"


def rows(items: Sequence[tuple[str, str]]) -> str:
    return "".join(
        f"<tr><th>{escape(label)}</th><td>{escape(value)}</td></tr>" for label, value in items
    )


def mapping_table(mapping: dict[str, Any]) -> str:
    rows_html = "".join(
        f"<tr><th>{escape(str(key))}</th><td>{escape(format_value(value))}</td></tr>"
        for key, value in mapping.items()
    )
    return f"<table><tbody>{rows_html}</tbody></table>"


def dataclass_public_values(instance: Any) -> dict[str, Any]:
    if not is_dataclass(instance):
        return {}
    return {field.name: getattr(instance, field.name) for field in fields(instance)}


def price_volume_svg(bars: Sequence[DailyBar]) -> str:
    if not bars:
        return "<p class=\"muted\">无行情数据。</p>"
    width = 960
    height = 360
    padding_left = 54
    padding_right = 20
    padding_top = 24
    price_bottom = 230
    volume_top = 258
    padding_bottom = 28
    closes = [bar.close for bar in bars]
    volumes = [bar.volume for bar in bars]
    low = min(min(bar.low for bar in bars), min(closes))
    high = max(max(bar.high for bar in bars), max(closes))
    price_span = high - low or 1.0
    max_volume = max(volumes) or 1.0
    chart_width = width - padding_left - padding_right
    price_height = price_bottom - padding_top
    volume_height = height - volume_top - padding_bottom
    close_points = []
    for index, bar in enumerate(bars):
        x = padding_left + (index / max(len(bars) - 1, 1)) * chart_width
        y = price_bottom - ((bar.close - low) / price_span) * price_height
        close_points.append(f"{x:.2f},{y:.2f}")
    volume_bars = []
    bar_width = max(2.0, chart_width / max(len(bars), 1) * 0.55)
    for index, bar in enumerate(bars):
        x = padding_left + (index / max(len(bars) - 1, 1)) * chart_width - (bar_width / 2)
        height_value = (bar.volume / max_volume) * volume_height
        y = height - padding_bottom - height_value
        color = "#0b7a53" if bar.close >= bar.open else "#b42318"
        volume_bars.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" '
            f'height="{height_value:.2f}" fill="{color}" opacity="0.45"/>'
        )
    right_edge = width - padding_right
    bottom_edge = height - padding_bottom
    last_x, last_y = close_points[-1].split(",")
    volume_markup = "".join(volume_bars)
    close_markup = " ".join(close_points)
    first_date = bars[0].trade_date.isoformat()
    last_date = bars[-1].trade_date.isoformat()
    return f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="price and volume">
      <rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>
      <line
        x1="{padding_left}" y1="{price_bottom}"
        x2="{right_edge}" y2="{price_bottom}"
        stroke="#d8dee8"
      />
      <line
        x1="{padding_left}" y1="{padding_top}"
        x2="{padding_left}" y2="{price_bottom}"
        stroke="#d8dee8"
      />
      <line
        x1="{padding_left}" y1="{bottom_edge}"
        x2="{right_edge}" y2="{bottom_edge}"
        stroke="#d8dee8"
      />
      <text x="12" y="{padding_top + 8}" fill="#647083" font-size="12">{high:.2f}</text>
      <text x="12" y="{price_bottom}" fill="#647083" font-size="12">{low:.2f}</text>
      <text x="12" y="{bottom_edge}" fill="#647083" font-size="12">{max_volume:.0f}</text>
      {volume_markup}
      <polyline points="{close_markup}" fill="none" stroke="#1d5fd1" stroke-width="3"/>
      <circle cx="{last_x}" cy="{last_y}" r="4" fill="#1d5fd1"/>
      <text x="{padding_left}" y="{height - 8}" fill="#647083" font-size="12">
        {first_date}
      </text>
      <text x="{width - 116}" y="{height - 8}" fill="#647083" font-size="12">
        {last_date}
      </text>
    </svg>
    """


def equity_svg(values: list[float]) -> str:
    if not values:
        return "<p class=\"muted\">无权益数据。</p>"
    width = 960
    height = 320
    padding_left = 58
    padding_right = 22
    padding_top = 24
    padding_bottom = 34
    low = min(values)
    high = max(values)
    span = high - low or 1.0
    chart_width = width - padding_left - padding_right
    chart_height = height - padding_top - padding_bottom
    points = []
    area_points = [f"{padding_left},{height - padding_bottom}"]
    for index, value in enumerate(values):
        x = padding_left + (index / max(len(values) - 1, 1)) * chart_width
        y = height - padding_bottom - ((value - low) / span) * chart_height
        point = f"{x:.2f},{y:.2f}"
        points.append(point)
        area_points.append(point)
    area_points.append(f"{width - padding_right},{height - padding_bottom}")
    right_edge = width - padding_right
    bottom_edge = height - padding_bottom
    area_markup = " ".join(area_points)
    points_markup = " ".join(points)
    return f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="equity curve">
      <rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>
      <line
        x1="{padding_left}" y1="{bottom_edge}"
        x2="{right_edge}" y2="{bottom_edge}"
        stroke="#d8dee8"
      />
      <line
        x1="{padding_left}" y1="{padding_top}"
        x2="{padding_left}" y2="{bottom_edge}"
        stroke="#d8dee8"
      />
      <polygon points="{area_markup}" fill="#e9f1ff"/>
      <polyline points="{points_markup}" fill="none" stroke="#1d5fd1" stroke-width="3"/>
      <text x="12" y="{padding_top + 8}" fill="#647083" font-size="12">{high:.2f}</text>
      <text x="12" y="{bottom_edge}" fill="#647083" font-size="12">{low:.2f}</text>
      <text x="{padding_left}" y="{height - 10}" fill="#647083" font-size="12">start</text>
      <text x="{width - 48}" y="{height - 10}" fill="#647083" font-size="12">end</text>
    </svg>
    """


def optional_score(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def optional_ratio(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def format_number(value: float) -> str:
    return f"{value:,.4f}".rstrip("0").rstrip(".")


def format_optional_number(value: float | None) -> str:
    if value is None:
        return "-"
    return format_number(value)


def format_optional_pct(value: float | None) -> str:
    if value is None:
        return "-"
    return format_pct(value)


def format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        return format_number(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def signed_class(value: float) -> str:
    if value > 0:
        return "good"
    if value < 0:
        return "bad"
    return ""


def score_class(candidate: ScreeningCandidate | None) -> str:
    if candidate is None:
        return "warn"
    if candidate.score >= 70:
        return "good"
    return "warn"


def ratio_class(signal: SignalPlan | None) -> str:
    if signal is None:
        return "warn"
    if signal.risk_reward >= 1.5:
        return "good"
    return "warn"


def has_error_issue(issues: Sequence[ValidationIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)
