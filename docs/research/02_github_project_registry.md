# GitHub 项目地址登记表

检索日期：2026-06-10（Asia/Shanghai）

星级为检索时从 GitHub 页面、Star History、OSSInsight、GStars 等页面观察到的近似值；后续做深度蒸馏前需要再次核验。这里记录的是“值得读”的项目，不代表直接复制代码，也不构成任何投资建议。

## 核心项目

| 类型 | 项目 | 地址 | 观察星级 | 可蒸馏内容 | 优先级 |
|---|---|---|---:|---|---|
| 金融数据平台 | OpenBB | https://github.com/OpenBB-finance/OpenBB | 68.2k | 数据平台分层、金融数据适配、分析工作流；注意 AGPL 许可证 | P2 |
| AI 量化平台 | Qlib | https://github.com/microsoft/qlib | 43.5k+ | Alpha158/Alpha360、因子数据集、模型训练、信号回测、研究流水线 | P0 |
| 国内量化平台 | vn.py / VeighNa | https://github.com/vnpy/vnpy | 41.5k | 事件驱动、策略 app、A 股/ETF/期货网关、风控模块、AI 多因子模块 | P1 |
| 回测引擎 | backtrader | https://github.com/mementum/backtrader | 21.7k | 策略类、broker 模拟、订单类型、滑点/手续费、分析器 | P1 |
| A 股数据源 | AKShare | https://github.com/akfamily/akshare | 19.8k+ | A 股行情、财务、资金流、宏观等数据接口；MVP 首选数据源 | P0 |
| 算法交易引擎 | QuantConnect Lean | https://github.com/QuantConnect/Lean | 19.2k | 专业级事件驱动回测/实盘架构；主要做架构参考 | P2 |
| 强化学习交易 | FinRL | https://github.com/AI4Finance-Foundation/FinRL | 15.3k | 市场环境、DRL agent、训练/评估流程；后期 AI 策略参考 | P2 |
| 综合选股系统 | myhhub/stock | https://github.com/myhhub/stock | 12.9k | 综合选股、指标、筹码分布、K 线形态、买卖判断、策略回测 | P0 |
| 技术指标 | TA-Lib Python | https://github.com/TA-Lib/ta-lib-python | 12k | 150+ 技术指标、K 线形态识别、买卖点基础信号 | P0 |
| A 股量化平台 | QUANTAXIS | https://github.com/yutiansut/QUANTAXIS | 10.6k | 本地化数据/回测/模拟/交易/可视化、多账户设计 | P1 |
| 轻量回测 | backtesting.py | https://github.com/kernc/backtesting.py | 8.4k | 简洁策略 API、快速回测、参数优化；MVP 回测候选 | P0 |
| 向量化回测 | vectorbt | https://github.com/polakowo/vectorbt | 7.7k | 批量策略回测、参数网格、Numba/向量化性能 | P1 |
| 绩效报告 | QuantStats | https://github.com/ranaroussi/quantstats | 7.2k | Sharpe、Sortino、回撤、胜率、HTML 报告、Monte Carlo 风险 | P0 |
| 技术指标 | bukosabino/ta | https://github.com/bukosabino/ta | 5.1k | Pandas/Numpy 技术指标，TA-Lib 安装失败时的纯 Python 备选 | P1 |
| 模块化量化框架 | zvt | https://github.com/zvtvz/zvt | 4.1k | 数据持久化、stock pool、factor、signal、trader、Dash/Plotly UI | P1 |
| A 股高性能框架 | hikyuu | https://github.com/fasiondog/hikyuu | 3.2k | 策略部件化：市场环境、信号、止损/止盈、资金管理、滑点、组合 | P1 |
| 组合回测 | bt | https://github.com/pmorissette/bt | 2.9k | 组合策略树、Algo blocks、回测统计；适合组合层参考 | P2 |

## 备用/待二次核验项目

| 类型 | 项目 | 地址 | 备注 |
|---|---|---|---|
| A 股数据源 | Tushare | https://github.com/waditu/tushare | A 股常用数据源；需核验当前开源范围、接口限制和许可 |
| Yahoo 数据 | yfinance | https://github.com/ranaroussi/yfinance | 美股/ETF 数据便捷；A 股不是主线 |
| 米筐回测 | RQAlpha | https://github.com/ricequant/rqalpha | 国内回测生态参考；需核验维护状态 |
| 金融机器学习 | mlfinlab | https://github.com/hudson-and-thames/mlfinlab | Lopez de Prado 方法、特征/标签/验证思想参考；注意商业化状态 |
| Pandas 指标 | pandas-ta-classic | https://github.com/xgboosted/pandas-ta-classic | pandas-ta 社区维护替代；待核验稳定性 |
| InStock fork | ethqunzhong/InStock | https://github.com/ethqunzhong/InStock | myhhub/stock 的 fork，星级低但 README 对选股/买卖点说明很具体 |

## 当前结论

- MVP 技术路线优先读：`AKShare`、`myhhub/stock`、`TA-Lib`、`backtesting.py`、`QuantStats`。
- 框架设计优先读：`Qlib`、`vn.py`、`zvt`、`hikyuu`、`QUANTAXIS`。
- 后期增强优先读：`vectorbt`、`FinRL`、`OpenBB`、`QuantConnect Lean`。

