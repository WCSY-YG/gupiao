# 项目任务清单

更新时间：2026-06-10 02:26 CST

本文档是项目自动推进的状态源。每一轮任务开始前先读取本文件；每完成一个任务，必须更新状态并提交、推送到 GitHub。

## 状态约定

| 状态 | 含义 |
|---|---|
| `pending` | 未开始，等待执行 |
| `in_progress` | 当前正在执行 |
| `done` | 已完成，并应已提交/推送 |
| `blocked` | 被外部条件阻塞，需要记录原因 |

## 当前指针

- 当前阶段：Phase 0 -> Phase 1 过渡。
- 下一项任务：`P0-03` 深读 P0 参考项目并补充可执行 references。
- 推进规则：从上到下选择第一个 `pending` 且依赖已完成的任务。
- GitHub 更新规则：每完成一个任务，更新本清单和相关项目记忆，执行一次 commit，并推送到 `origin`。

## 任务列表

| ID | 状态 | 阶段 | 任务 | 完成标准 | 依赖 |
|---|---|---|---|---|---|
| M0-01 | done | 项目控制面 | 建立项目自动推进任务清单与运行规则 | 新增任务清单、运行规则，并更新项目记忆 | 无 |
| P0-01 | done | Phase 0 | 完成第一轮 GitHub 调研与项目规划 | 生成搜索清单、项目登记表、蒸馏计划和总体规划 | 无 |
| P0-02 | done | Phase 0 | 创建 P0 skills 初稿 | 数据接入、选股策略、买卖点、回测验证、绩效报告 5 个 skill 草案存在 | P0-01 |
| P0-03 | pending | Phase 0 | 深读 P0 参考项目 README、docs、examples、license | 为 AKShare、myhhub/stock、TA-Lib、backtesting.py、QuantStats 形成可引用 notes | P0-02 |
| P0-04 | pending | Phase 0 | 补充 P0 skills references | 每个 P0 skill 有来源、适用场景、关键 API/约束、后续实现提示 | P0-03 |
| P1-01 | pending | Phase 1 | 搭建最小代码骨架 | 创建 `src/`、`configs/`、`data/`、`reports/`、`tests/`，并有基础包结构 | P0-04 |
| P1-02 | pending | Phase 1 | 建立 Python 工程配置 | 明确依赖、运行入口、测试命令、格式化/类型检查策略 | P1-01 |
| P1-03 | pending | Phase 1 | 实现股票列表与日线数据接入接口 | 能通过 CLI 或函数获取 A 股基础列表和日线样例数据 | P1-02 |
| P1-04 | pending | Phase 1 | 设计并实现本地数据存储 | SQLite/DuckDB/Parquet 方案可写入、读取、增量更新 | P1-03 |
| P1-05 | pending | Phase 1 | 加入数据质量检查 | 覆盖缺失值、停牌、复权、重复记录、时间顺序等基础校验 | P1-04 |
| P2-01 | pending | Phase 2 | 实现技术指标层 | MA、EMA、MACD、KDJ、RSI、BOLL、ATR、OBV 等可计算 | P1-05 |
| P2-02 | pending | Phase 2 | 实现第一个 MVP 选股策略 | 均线多头 + 放量突破策略输出候选股和命中原因 | P2-01 |
| P2-03 | pending | Phase 2 | 实现买卖点解释 | 输出入场、加仓、减仓、止损、止盈、信号失效条件 | P2-02 |
| P3-01 | pending | Phase 3 | 实现单策略回测闭环 | 支持手续费、滑点、基础收益/回撤/胜率指标 | P2-03 |
| P3-02 | pending | Phase 3 | 加入 A 股交易约束 | T+1、涨跌停、停牌约束进入回测假设 | P3-01 |
| P3-03 | pending | Phase 3 | 生成中文绩效报告 | 候选股、信号解释、回测指标、风险提示可落盘 | P3-02 |
| P4-01 | pending | Phase 4 | 提供 CLI 任务入口 | 支持数据更新、选股、信号、回测、报告命令 | P3-03 |
| P4-02 | pending | Phase 4 | 搭建 Web Dashboard 初版 | 可浏览候选池、K 线指标、回测图和报告摘要 | P4-01 |
| P5-01 | pending | Phase 5 | 扩展多因子研究 | 价值、质量、成长、动量、波动率、流动性综合打分 | P4-02 |
| P5-02 | pending | Phase 5 | 探索 ML 评分与组合优化 | 有实验脚手架、样本外验证和风险说明 | P5-01 |

## 完成记录

- 2026-06-10 02:26 CST：启动项目自动推进控制面，建立任务清单和运行规则。
