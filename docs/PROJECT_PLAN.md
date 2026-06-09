# 股票选股与买卖点分析项目总规划

规划版本：0.2.0
最近调研：2026-06-10（Asia/Shanghai）

## 定位

本项目建设一个面向 A 股、可扩展到港股/美股/ETF 的量化研究与辅助决策系统。核心目标不是“自动荐股”，而是把数据、策略、买卖点、回测、风控和报告串成可复查的研究闭环。

项目默认只做研究、模拟和报告，不输出收益承诺，不默认接入真实交易。任何策略结论都必须附带数据来源、信号定义、回测假设、风险说明和失效条件。

## 启动顺序

1. 搜集所有与炒股、选股、量化交易、AI 交易 agent、Claude/Codex trading skill 相关的 GitHub 项目。
2. 把项目地址、星级、许可证、最近更新时间、可蒸馏内容登记到 `docs/research/02_github_project_registry.md`。
3. 先吸收高相关 skill 项目的提示工程结构，再吸收高星量化项目的工程规范。
4. 将核心能力整合到项目内总 skill：`skills/stock-trading-research-master`。
5. 用总 skill 调度 P0 子 skill，逐步落地数据、策略、信号、回测和报告代码。

## GitHub 与版本管理

- 每轮较大变更先从干净工作区创建 `codex/<topic>` 分支。
- 文档、skill、代码、测试分批提交；提交信息用 `docs:`, `skill:`, `feat:`, `test:`, `chore:` 前缀。
- 每次功能性变更同步更新 `VERSION`、`CHANGELOG.md` 和相关项目记忆。
- 外部项目调研必须记录检索日期；星级和维护状态只作为当日快照。
- 不把数据缓存、回测大文件、报告图片批量提交到 Git；后续用 `.gitignore` 和可复现任务管理。
- 进入可运行阶段后，默认节奏为：小步分支 -> 本地验证 -> 合并前复核 -> tag 版本。

## 总体架构

```text
外部调研与总 skill
  -> 数据源(AKShare/Tushare/OpenBB/yfinance)
  -> 数据层(SQLite/DuckDB/Parquet)
  -> 数据质量与市场状态层(交易日历/复权/停牌/ST/涨跌停/风格轮动)
  -> 因子与指标层(TA-Lib/ta/pandas/Polars)
  -> 策略层(规则选股/多因子/形态/ML)
  -> 信号层(买点/卖点/仓位/止损/失效条件)
  -> 回测层(事件驱动或向量化)
  -> 风险与绩效报告层(QuantStats/自定义中文解释)
  -> CLI/API/Web Dashboard
```

## Skill 体系

总 skill：`stock-trading-research-master`

- 负责项目入口、调研更新、任务分流、版本管理提醒、风险边界和最终产出检查。
- 先调用调研登记流程，再按任务类型调用子 skill。
- 每次策略或数据逻辑变更前，要求核对最新市场制度、数据源状态和外部项目维护情况。

P0 子 skill：

- `stock-data-ingestion`：数据接入、落库、字段规范、质量校验。
- `stock-screening-strategies`：基本面、技术面、资金面、形态、多因子选股。
- `technical-signal-buy-sell`：买卖点、止损止盈、信号解释。
- `backtest-validation`：回测假设、反作弊、A 股交易约束、样本外验证。
- `performance-risk-reporting`：收益、回撤、胜率、风险和中文报告。

P1/P2 待扩展 skill：

- `ml-factor-research`：Qlib/FinRL 风格的因子、模型和时序验证。
- `strategy-component-system`：hikyuu/bt 风格的策略组件化。
- `market-regime-update`：宏观、指数、行业、资金、情绪和监管变化的更新机制。
- `trading-gateway-risk-boundary`：未来模拟/实盘边界、订单状态和风控闸门。

## GitHub 调研路线

优先高星且仍活跃的工程项目：

- 数据：AKShare、Tushare、OpenBB、yfinance。
- A 股综合：myhhub/stock、zvt、hikyuu、QUANTAXIS、vn.py。
- AI/多因子：Qlib、FinRL、AgentQuant、stock-top-papers。
- 指标：TA-Lib Python、bukosabino/ta、pandas-ta-classic。
- 回测：backtesting.py、vectorbt、backtrader、Lean、RQAlpha、bt。
- 绩效：QuantStats、pyfolio 类项目。
- Agent/Skill：nse-trading-skills、TradingAgents-CN-SKILL、tradingview-quantitative-skills、stock-trading-strategist、trading-skills、hhxg-top-hhxg-python、quantconnect-mcp。

蒸馏顺序：

1. 先登记所有项目地址和元信息。
2. P0 深读：AKShare、myhhub/stock、TA-Lib、QuantStats、Qlib、vn.py、hikyuu。
3. 将 skill 项目的任务拆解、提示组织、风险提示格式整合进总 skill。
4. 将高星量化项目的数据模型、策略接口、回测假设和报告指标整合进子 skill。
5. 每月或遇到市场制度/数据源变化时复查登记表。

## MVP 范围

1. 数据：A 股股票列表、日线行情、复权价格、基础财务指标、资金流、交易日历。
2. 指标：MA、EMA、MACD、KDJ、RSI、BOLL、CCI、ATR、OBV、量价指标、K 线形态。
3. 选股策略：均线多头、放量突破、平台突破、回踩年线、低估值高 ROE。
4. 买卖点：技术指标打分、趋势确认、仓位建议、止损止盈、信号失效说明。
5. 回测：单策略与批量选股验证、手续费、印花税、滑点、T+1、涨跌停无法成交。
6. 报告：候选股票列表、选中原因、买卖点解释、回测指标、最大回撤、收益曲线。

## 策略库规划

- 基本面：PE/PB/ROE、利润增长、经营现金流、股息率、负债率、财报发布日期。
- 趋势类：均线多头、Donchian 突破、相对强度、平台突破、高而窄旗形。
- 反转类：RSI/KDJ/CCI/WR 超卖修复、缩量回踩、ATR 低波动收缩。
- 量价类：放量上涨、量价背离、资金净流入、涨停后整理、下跌无量。
- 形态类：TA-Lib K 线形态、吞没、锤头、早晨之星、乌云盖顶、自定义 A 股形态。
- 多因子：价值、质量、成长、动量、波动率、流动性和行业中性评分。
- ML 类：Qlib 风格 Alpha158/Alpha360、LightGBM/MLP/Lasso、滚动训练和样本外评估。

## 数据模型草案

- `instruments`：股票基础信息、市场、板块、行业、概念、上市/退市状态、ST 状态。
- `trading_calendar`：交易日、节假日、半日市、市场。
- `bars_daily`：OHLCV、成交额、换手率、复权因子、数据源和抓取时间。
- `fundamentals`：估值、盈利、成长、偿债、股东信息、报告期和发布日期。
- `money_flow`：主力/散户/北向/行业/概念资金流。
- `indicators_daily`：技术指标和 K 线形态。
- `market_regime`：指数趋势、行业轮动、风险偏好、成交活跃度、市场宽度。
- `screening_results`：策略选股结果、评分、命中原因、排除原因。
- `signals`：买点、卖点、止损、止盈、失效条件、信号置信度。
- `backtest_runs`：回测参数、日期范围、交易成本、约束、结果摘要。
- `reports`：报告元数据、策略版本、图表路径、结论和风险提示。

## 技术栈建议

- 语言：Python 3.11/3.12。
- 数据处理：pandas MVP，后期引入 Polars 提升批量处理性能。
- 存储：SQLite/DuckDB + Parquet，先本地轻量化，后续可扩展对象存储。
- 数据源：AKShare 作为 MVP 主数据源，Tushare/OpenBB/yfinance 作为扩展。
- 指标：TA-Lib 优先；安装或许可证受限时用 bukosabino/ta 或自实现少量核心指标兜底。
- 回测：优先选择许可证友好的实现路线；AGPL/GPL 项目做流程参考，直接复用前单独评估。
- 报告：QuantStats + 自定义中文解释报告。
- 服务/UI：先 CLI，后 FastAPI + Web Dashboard。

## 持续适应市场变化

- 每个交易日可更新：行情、资金流、交易日历、候选池和信号。
- 每周更新：策略表现、市场宽度、行业轮动、参数稳定性。
- 每月更新：GitHub 外部项目状态、数据源接口变化、依赖版本、策略失效复盘。
- 每季度更新：财报字段、基本面因子、样本外回测、组合风险暴露。
- 遇到制度变化、交易规则变化、重大数据源变更时，优先更新 `market-regime-update` 和回测假设。

## 里程碑

| 阶段 | 目标 | 交付物 |
|---|---|---|
| Phase 0 | GitHub 调研与总 skill 蒸馏 | 搜索清单、项目登记表、总 skill、P0 子 skill |
| Phase 1 | 数据闭环 | 股票列表、日线、财务、资金流、交易日历采集与落库 |
| Phase 2 | 策略闭环 | 指标计算、选股策略、买卖点解释、候选池 |
| Phase 3 | 回测闭环 | 单策略和批量回测、A 股约束、风险指标、中文报告 |
| Phase 4 | 使用界面 | CLI 任务、Web 候选池、K 线、回测和报告页面 |
| Phase 5 | 高级研究 | 多因子、ML 评分、组合优化、模拟交易风控 |
| Phase 6 | 持续迭代 | 市场状态更新、策略失效检测、版本化策略库 |

## 风险与约束

- 数据质量：复权、停牌、涨跌停、财务发布日期、指数成分历史变化都要校验。
- 回测偏差：必须防未来函数、幸存者偏差、参数过拟合、偷看财务数据。
- 交易约束：A 股 T+1、涨跌停无法成交、手续费、印花税、滑点必须写入假设。
- 许可证：GPL/AGPL 项目优先做架构和流程参考，直接复用前必须评估开源义务。
- 策略风险：任何高胜率结果都必须经过样本外验证、滚动验证和压力测试。
- 合规边界：默认只做研究、模拟和报告，不默认真实下单。

## 下一步执行

1. 以 `stock-trading-research-master` 总 skill 作为后续任务入口。
2. 深读 P0/P1 核心项目 README、docs、examples、license，补充登记表。
3. 搭建代码骨架：`src/`、`configs/`、`tests/`、`reports/`、数据目录和 `.gitignore`。
4. 实现第一个完整策略：均线多头 + 放量突破 + ATR 止损。
5. 跑通：获取数据 -> 计算指标 -> 选股 -> 买卖点解释 -> 回测 -> 绩效报告。
