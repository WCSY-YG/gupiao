# gupiao

A 股选股、买卖点分析与量化研究项目。

## 当前范围

- 多策略选股：技术面、基本面、资金面、形态、多因子与机器学习方向。
- 买卖点分析：入场、加仓、减仓、止损、止盈、失效条件和中文解释。
- 回测验证：手续费、滑点、T+1、涨跌停、样本外验证和风险报告。
- GitHub 项目调研：把高星量化项目和交易 skill/agent 项目蒸馏为项目内 skills。

## 项目文档

- `docs/PROJECT_PLAN.md`：项目总规划。
- `docs/PROJECT_MEMORY.md`：项目记忆、约定和当前决策。
- `docs/research/01_github_search_checklist.md`：GitHub 搜索清单。
- `docs/research/02_github_project_registry.md`：GitHub 项目地址登记表。
- `docs/research/03_skill_distillation_plan.md`：skills 蒸馏计划。

## 项目 Skills

- `skills/stock-data-ingestion`
- `skills/stock-screening-strategies`
- `skills/technical-signal-buy-sell`
- `skills/backtest-validation`
- `skills/performance-risk-reporting`
- `skills/stock-trading-research-master`

## 环境约定

- 后续所有 Python 命令默认使用 conda 的 `agent` 环境。
- 推荐命令形式：`conda run -n agent python ...`、`conda run -n agent pytest ...`。
- 不默认接入真实交易账户，本项目只做研究、模拟和辅助分析。

## 状态

版本：`0.2.1`

当前处于规划、GitHub 调研和 skill 蒸馏阶段。本项目只用于研究和决策辅助，不构成投资建议。
