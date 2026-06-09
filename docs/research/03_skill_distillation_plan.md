# Skills 蒸馏计划

目标：把 GitHub 项目中的可复用工程经验蒸馏成项目内 skills，先服务本项目开发；稳定后再考虑安装成 Codex 全局 skills。

## 蒸馏原则

- 只抽象工作流、接口约定、验证清单和策略公式，不搬运大段源码。
- 每个 skill 保持短小：`SKILL.md` 写触发场景和步骤，复杂细节放到 `references/`。
- 所有策略必须保留数据需求、信号定义、回测假设、风险约束和反作弊检查。
- 实盘交易只做“模拟/风控/接口边界”skill，不做默认真实下单能力。

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
| `trading-gateway-risk-boundary` | vn.py、Lean、QUANTAXIS | 未来模拟/实盘边界、订单状态、风控闸门 | 交易接口边界、模拟交易规范 | P2 |

## 蒸馏步骤

1. 深读 P0 项目的 README、docs、examples、license。
2. 为每个 P0 skill 提炼：触发场景、输入数据、标准流程、输出文件、验证清单。
3. 写项目内 `skills/<skill-name>/SKILL.md` 初稿。
4. 用本项目真实任务验证 skill：如“新增一个突破平台选股策略并回测”。
5. 再读 P1/P2 项目，把高价值模式补入 references。
6. 稳定后再决定是否安装到 Codex 全局 skill 目录。

## 下一步默认动作

1. 先深读 `AKShare`、`myhhub/stock`、`TA-Lib`、`backtesting.py`、`QuantStats`。
2. 创建项目内 `skills/` 目录和 P0 五个 skill 初稿。
3. 以一个最小策略闭环验证：取 A 股日线 -> 算指标 -> 选股 -> 买卖点解释 -> 回测 -> 绩效报告。

