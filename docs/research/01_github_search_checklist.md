# GitHub 搜索清单

检索日期：2026-06-10（Asia/Shanghai）

目标：为“股票选股 + 买卖点分析”项目寻找可借鉴的高星或高相关 GitHub 项目，并把后续蒸馏为 skills 的来源先固定下来。

## 筛选原则

- 优先高星项目：一般优先 `3k+ stars`，但 A 股选股、买卖点、K 线形态等强相关项目可放宽。
- 优先可复用设计：数据接口、因子工程、策略 DSL、回测引擎、技术指标、风险报告、UI 工作流。
- 优先 A 股适配：能处理 A 股代码体系、复权、涨跌停、T+1、行业/概念/资金流/财务数据的项目权重更高。
- 谨慎实盘交易：自动交易接口只作为架构和风控参考，MVP 不直接做真实下单。
- 记录许可证：AGPL/GPL 项目更多做架构参考，MIT/Apache/BSD 更适合直接复用思路。

## 要搜索的项目类型

| 编号 | 项目类型 | 搜索关键词 | 搜索目的 |
|---|---|---|---|
| S01 | A 股数据源/财经数据 API | `A股 数据 接口 akshare tushare stock-data finance-api` | 解决股票列表、日线、复权、财务、资金流、行业概念等数据获取 |
| S02 | 综合选股系统 | `A股 综合选股 技术指标 K线形态 策略 回测` | 借鉴条件组合、策略模板、选股结果验证、买卖点模块 |
| S03 | 国内量化框架 | `vnpy QUANTAXIS hikyuu zvt 量化交易 A股 回测` | 借鉴 A 股量化框架、数据存储、策略组件、交易风控架构 |
| S04 | 通用回测引擎 | `python backtesting engine trading strategy backtrader vectorbt` | 选择 MVP 回测实现方式，避免手写不可靠回测 |
| S05 | AI/多因子量化平台 | `qlib FinRL factor model Alpha158 Alpha360 stock prediction` | 借鉴因子工程、模型训练、信号评估、ML 策略流程 |
| S06 | 技术指标/K 线形态 | `technical analysis indicators TA-Lib candlestick pattern buy sell signal` | 支撑 MACD/KDJ/RSI/BOLL/CCI/ATR/K 线形态等买卖点信号 |
| S07 | 组合绩效/风险报告 | `quantstats pyfolio portfolio analytics sharpe drawdown tearsheet` | 输出回测报告、收益回撤、胜率、夏普、风险指标 |
| S08 | 交易平台/实盘架构 | `algorithmic trading platform live trading risk manager gateway` | 只借鉴事件驱动、风控、订单状态、模拟交易，不直接接真实资金 |
| S09 | 策略经验/awesome 清单 | `awesome quant trading strategy stock market GitHub` | 收集策略经验、论文资源、策略分类和避坑清单 |

## 本轮优先级

1. P0：数据源、综合选股、技术指标、回测、绩效报告。
2. P1：A 股量化框架、策略组件、多因子框架。
3. P2：AI 强化学习、实盘平台、跨市场数据平台。

