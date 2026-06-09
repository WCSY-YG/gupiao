# Skills 蒸馏计划

目标：把 GitHub skill/agent 项目的提示工程结构和高星量化项目的工程经验蒸馏成项目内 skills，先服务本项目开发；稳定后再考虑安装成 Codex 全局 skills。

## 蒸馏原则

- 只抽象工作流、接口约定、验证清单和策略公式，不搬运大段源码。
- 每个 skill 保持短小：`SKILL.md` 写触发场景和步骤，复杂细节放到 `references/`。
- 所有策略必须保留数据需求、信号定义、回测假设、风险约束和反作弊检查。
- 实盘交易只做“模拟/风控/接口边界”skill，不做默认真实下单能力。
- 先记录所有来源地址，再做深读和蒸馏；未记录来源的经验不进入正式 skill。
- 对 GPL/AGPL/未声明许可证项目，只蒸馏理念、流程和验证清单，不复制实现。

## 总 Skill

| Skill 名称 | 主要来源 | 作用 | 产出形态 | 优先级 |
|---|---|---|---|---|
| `stock-trading-research-master` | nse-trading-skills、TradingAgents-CN-SKILL、tradingview-quantitative-skills、stock-trading-strategist、AKShare、Qlib、myhhub/stock、TA-Lib、QuantStats、vn.py、hikyuu | 作为炒股项目总入口，负责调研登记、版本管理、任务分流、市场变化更新和最终质量检查 | 总控工作流、子 skill 路由、风险边界、持续迭代清单 | P0 |

## 候选 skills

| Skill 名称 | 主要来源 | 作用 | 产出形态 | 优先级 |
|---|---|---|---|---|
| `stock-data-ingestion` | AKShare、Tushare、OpenBB、yfinance | 获取股票列表、日线、复权、财务、资金流，落库并校验 | 数据接口规范、字段字典、更新任务流程 | P0 |
| `stock-screening-strategies` | myhhub/stock、zvt、Qlib | 构建基本面、技术面、资金面、趋势、反转、多因子选股策略 | 策略模板、筛选条件 DSL、策略登记规范 | P0 |
| `technical-signal-buy-sell` | TA-Lib、bukosabino/ta、myhhub/stock、hikyuu | 计算指标和 K 线形态，输出买卖点解释 | 指标清单、信号打分、止损止盈规则 | P0 |
| `backtest-validation` | backtesting.py、backtrader、vectorbt、RQAlpha | 回测单策略和批量策略，检查未来函数、费用、滑点、T+1 | 回测流程、反作弊清单、基准比较 | P0 |
| `performance-risk-reporting` | QuantStats、bt、pyfolio | 生成收益、回撤、胜率、夏普、风险报告 | HTML/Markdown 报告模板、指标解释 | P0 |
| `ml-factor-research` | Qlib、vn.py alpha、FinRL、mlfinlab | 多因子和机器学习研究流程 | 因子训练流水线、时序验证、特征重要性 | P1 |
| `strategy-component-system` | hikyuu、QUANTAXIS、bt | 把策略拆成环境、入场、出场、仓位、风控、组合部件 | 策略组件接口和组合规则 | P1 |
| `market-regime-update` | AKShare、OpenBB、Qlib、myhhub/stock、hhxg-top-hhxg-python | 根据行情、指数、行业、资金、题材、监管和数据源变化更新策略假设 | 市场状态字段、更新频率、策略失效复盘 | P1 |
| `trading-gateway-risk-boundary` | vn.py、Lean、QUANTAXIS | 未来模拟/实盘边界、订单状态、风控闸门 | 交易接口边界、模拟交易规范 | P2 |

## 蒸馏步骤

1. 搜集所有炒股、选股、量化交易、AI trading agent、Claude/Codex trading skill 相关 GitHub 项目。
2. 把项目地址、星级、许可证、最近更新时间和可蒸馏内容登记到 `02_github_project_registry.md`。
3. 深读 P0 skill 项目的 README、SKILL.md、agent prompts、examples、license，提炼提示结构。
4. 深读 P0 工程项目的 README、docs、examples、license，提炼数据、策略、回测和报告接口。
5. 为每个 skill 提炼：触发场景、输入数据、标准流程、输出文件、验证清单。
6. 写项目内 `skills/<skill-name>/SKILL.md` 初稿；总 skill 负责路由和质量门槛。
7. 用本项目真实任务验证 skill：如“新增一个突破平台选股策略并回测”。
8. 再读 P1/P2 项目，把高价值模式补入 skill 或 references。
9. 稳定后再决定是否安装到 Codex 全局 skill 目录。

## 总 Skill 验收标准

- 能提醒先做 Git 状态检查和分支隔离。
- 能要求先登记外部项目地址，再做深读蒸馏。
- 能根据任务调用数据、选股、买卖点、回测、报告子 skill。
- 能强制输出数据来源、信号定义、回测假设、风险说明和失效条件。
- 能在策略更新前检查最新市场变化、数据源变化、交易规则和许可证风险。

## 下一步默认动作

1. 先深读 `nse-trading-skills`、`TradingAgents-CN-SKILL`、`tradingview-quantitative-skills`、`stock-trading-strategist`。
2. 再深读 `AKShare`、`myhhub/stock`、`TA-Lib`、`QuantStats`、`Qlib`、`vn.py`、`hikyuu`。
3. 用 `stock-trading-research-master` 调度 P0 五个子 skill。
4. 以一个最小策略闭环验证：取 A 股日线 -> 算指标 -> 选股 -> 买卖点解释 -> 回测 -> 绩效报告。
