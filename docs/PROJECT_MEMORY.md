# 项目记忆

更新时间：2026-06-10（Asia/Shanghai）

## 用户目标

用户要做一个炒股/股票量化研究项目，希望由 Codex 统筹推进。核心功能包括：

- 各种策略选股。
- 买卖点分析。
- GitHub 高星项目调研。
- 把优秀项目经验蒸馏成一系列可复用 skills。
- 后续由 Codex 继续规划并推动实现。

## 当前完成内容

已经完成第二轮 GitHub 调研与项目规划，生成并更新了以下文件：

- `docs/PROJECT_PLAN.md`：股票选股与买卖点分析项目总规划。
- `docs/research/01_github_search_checklist.md`：GitHub 搜索类型清单。
- `docs/research/02_github_project_registry.md`：高星/高相关 GitHub 项目地址登记表。
- `docs/research/03_skill_distillation_plan.md`：skills 蒸馏计划。

已经创建项目内 P0 skill 草案：

- `skills/stock-data-ingestion/SKILL.md`
- `skills/stock-screening-strategies/SKILL.md`
- `skills/technical-signal-buy-sell/SKILL.md`
- `skills/backtest-validation/SKILL.md`
- `skills/performance-risk-reporting/SKILL.md`

已经新增项目总 skill：

- `skills/stock-trading-research-master/SKILL.md`

当前版本：`0.2.1`。

## 固定工作约定

- README 必须保持中文。
- 后续所有 Python 命令默认使用 conda 的 `agent` 环境。
- 推荐命令形式：`conda run -n agent python ...`、`conda run -n agent pytest ...`。
- 如果新增 Python 脚本、测试、依赖安装或运行服务，优先确认命令是否在 `agent` 环境中执行。

## 当前调研结论

总 skill 蒸馏优先参考项目：

- nse-trading-skills：https://github.com/Bhala-Srinivash/nse-trading-skills
- TradingAgents-CN-SKILL：https://github.com/shaohk/TradingAgents-CN-SKILL
- tradingview-quantitative-skills：https://github.com/hypier/tradingview-quantitative-skills
- stock-trading-strategist：https://github.com/Alexzjt/stock-trading-strategist
- trading-skills：https://github.com/roman-rr/trading-skills
- hhxg-top-hhxg-python：https://github.com/Niceck/hhxg-top-hhxg-python

MVP 优先参考项目：

- AKShare：https://github.com/akfamily/akshare
- myhhub/stock：https://github.com/myhhub/stock
- TA-Lib Python：https://github.com/TA-Lib/ta-lib-python
- QuantStats：https://github.com/ranaroussi/quantstats
- Qlib：https://github.com/microsoft/qlib

架构设计优先参考项目：

- vn.py：https://github.com/vnpy/vnpy
- zvt：https://github.com/zvtvz/zvt
- hikyuu：https://github.com/fasiondog/hikyuu
- QUANTAXIS：https://github.com/yutiansut/QUANTAXIS

后期增强参考项目：

- vectorbt：https://github.com/polakowo/vectorbt
- backtesting.py：https://github.com/kernc/backtesting.py
- backtrader：https://github.com/mementum/backtrader
- FinRL：https://github.com/AI4Finance-Foundation/FinRL
- OpenBB：https://github.com/OpenBB-finance/OpenBB
- QuantConnect Lean：https://github.com/QuantConnect/Lean

许可证注意：GPL/AGPL/未声明许可证项目优先作为流程和架构参考，直接复用前必须单独评估。

## 建议技术路线

- Python 3.11/3.12。
- Python 运行环境：统一使用 conda 的 `agent` 环境。
- 数据处理：pandas，后期可引入 Polars。
- 存储：SQLite/DuckDB + Parquet。
- 数据源：AKShare 作为 MVP 主数据源。
- 指标：TA-Lib 优先，安装受阻时用 bukosabino/ta 兜底。
- 回测：优先选择许可证友好的实现路线；backtesting.py、vectorbt、backtrader、Lean 做 API 和流程参考。
- 报告：QuantStats + 自定义中文解释报告。
- UI：先 CLI，后 FastAPI + Web Dashboard。

## 下一步默认推进

1. 以 `stock-trading-research-master` 作为后续项目入口。
2. 深读 P0 skill/agent 项目的 README、SKILL.md、examples、license。
3. 深读 P0 工程项目的 README、docs、examples、license。
4. 将 P0 skill 草案补充 references。
5. 搭建最小代码骨架：`src/`、`data/`、`configs/`、`reports/`、`tests/`。
6. 实现第一个完整策略：均线多头 + 放量突破 + ATR 止损。
7. 跑通：获取数据 -> 计算指标 -> 选股 -> 买卖点解释 -> 回测 -> 报告。

## 注意事项

- 当前项目定位为研究与辅助分析工具，不默认接入真实交易。
- 必须防未来函数、幸存者偏差、财务数据偷看、参数过拟合。
- A 股回测必须考虑 T+1、涨跌停、停牌、手续费、印花税、滑点。
