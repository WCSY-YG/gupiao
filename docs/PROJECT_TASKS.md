# 项目任务清单

更新时间：2026-06-10 21:15 CST

本文档是项目自动推进的状态源。每一轮任务开始前先读取本文件；每完成一个任务，必须更新状态并本地提交。GitHub 推送若失败，记录 `push_pending` 后继续推进。

## 状态约定

| 状态 | 含义 |
|---|---|
| `pending` | 未开始，等待执行 |
| `in_progress` | 当前正在执行 |
| `done` | 已完成，并应已提交/推送 |
| `blocked` | 被外部条件阻塞，需要记录原因 |

## 当前指针

- 当前阶段：Phase 6。
- 下一项任务：P6-06 扩展竞价增强参数滚动验证；P6-02 全 A 股扫描仍可作为长期可恢复数据作业继续运行。
- 推进规则：从上到下选择第一个 `pending` 且依赖已完成的任务。
- GitHub 更新规则：每完成一个任务，更新本清单和相关项目记忆，执行一次本地 commit；远端推送失败时记录 `push_pending`，不阻塞后续任务。

## 任务列表

| ID | 状态 | 阶段 | 任务 | 完成标准 | 依赖 |
|---|---|---|---|---|---|
| M0-01 | done | 项目控制面 | 建立项目自动推进任务清单与运行规则 | 新增任务清单、运行规则，并更新项目记忆 | 无 |
| P0-01 | done | Phase 0 | 完成第一轮 GitHub 调研与项目规划 | 生成搜索清单、项目登记表、蒸馏计划和总体规划 | 无 |
| P0-02 | done | Phase 0 | 创建 P0 skills 初稿 | 数据接入、选股策略、买卖点、回测验证、绩效报告 5 个 skill 草案存在 | P0-01 |
| P0-03 | done | Phase 0 | 深读 P0 参考项目 README、docs、examples、license | 为 AKShare、myhhub/stock、TA-Lib、backtesting.py、QuantStats 形成可引用 notes | P0-02 |
| P0-04 | done | Phase 0 | 补充 P0 skills references | 每个 P0 skill 有来源、适用场景、关键 API/约束、后续实现提示 | P0-03 |
| P1-01 | done | Phase 1 | 搭建最小代码骨架 | 创建 `src/`、`configs/`、`data/`、`reports/`、`tests/`，并有基础包结构 | P0-04 |
| P1-02 | done | Phase 1 | 建立 Python 工程配置 | 明确依赖、运行入口、测试命令、格式化/类型检查策略 | P1-01 |
| P1-03 | done | Phase 1 | 实现股票列表与日线数据接入接口 | 能通过 CLI 或函数获取 A 股基础列表和日线样例数据 | P1-02 |
| P1-04 | done | Phase 1 | 设计并实现本地数据存储 | SQLite/DuckDB/Parquet 方案可写入、读取、增量更新 | P1-03 |
| P1-05 | done | Phase 1 | 加入数据质量检查 | 覆盖缺失值、停牌、复权、重复记录、时间顺序等基础校验 | P1-04 |
| P2-01 | done | Phase 2 | 实现技术指标层 | MA、EMA、MACD、KDJ、RSI、BOLL、ATR、OBV 等可计算 | P1-05 |
| P2-02 | done | Phase 2 | 实现第一个 MVP 选股策略 | 均线多头 + 放量突破策略输出候选股和命中原因 | P2-01 |
| P2-03 | done | Phase 2 | 实现买卖点解释 | 输出入场、加仓、减仓、止损、止盈、信号失效条件 | P2-02 |
| P3-01 | done | Phase 3 | 实现单策略回测闭环 | 支持手续费、滑点、基础收益/回撤/胜率指标 | P2-03 |
| P3-02 | done | Phase 3 | 加入 A 股交易约束 | T+1、涨跌停、停牌约束进入回测假设 | P3-01 |
| P3-03 | done | Phase 3 | 生成中文绩效报告 | 候选股、信号解释、回测指标、风险提示可落盘 | P3-02 |
| P4-01 | done | Phase 4 | 提供 CLI 任务入口 | 支持数据更新、选股、信号、回测、报告命令 | P3-03 |
| P4-02 | done | Phase 4 | 搭建 Web Dashboard 初版 | 可浏览候选池、K 线指标、回测图和报告摘要 | P4-01 |
| P5-01 | done | Phase 5 | 扩展多因子研究 | 价值、质量、成长、动量、波动率、流动性综合打分 | P4-02 |
| P5-02 | done | Phase 5 | 探索 ML 评分与组合优化 | 有实验脚手架、样本外验证和风险说明 | P5-01 |
| P6-01 | done | Phase 6 | 实现可恢复全 A 股市场扫描流水线 | `scan market` 支持 AKShare 全市场拉取、SQLite 缓存、逐股回测、失败不中断和轻量 Markdown 汇总 | P5-02 |
| P6-02 | in_progress | Phase 6 | 运行完整全 A 股扫描并提交轻量汇总 | 无 `--limit` 跑完 2023-06-10 至 2026-06-10 全 A 股，提交 `reports/summaries/latest_market_scan.md` | P6-01 |
| P6-03 | done | Phase 6 | 整合竞价数据增强选股与回测 | 支持 AKShare 盘前分钟数据、竞价画像、竞价增强策略评分、历史竞价画像注入回测和研究样本生成 | P2-02, P3-01 |
| P6-04 | done | Phase 6 | 导入本地历史竞价缓存 | 将 `cache/jingjia/*.rar` 解压/解析为竞价明细或竞价画像表，建立按股票和交易日查询接口 | P6-03 |
| P6-05 | done | Phase 6 | 基于 K 线与竞价数据迭代优化 skill | 用最近 K 线和历史竞价画像构建样本外回测，比较原策略与竞价增强策略并更新选股 skill 参数/阈值 | P6-04 |
| P6-06 | pending | Phase 6 | 扩展竞价增强参数滚动验证 | 对不同月份、不同 `min_auction_score` 和 `auction_score_weight` 做滚动对比，形成更稳健的参数建议 | P6-05 |
| P6-07 | done | Phase 6 | 补全 Web 端选股体验与多策略接口 | 支持策略注册表、按 `as_of` 日期选股、SQLite 缓存批量候选、Web action 和 README 使用说明 | P6-05 |
| P6-08 | done | Phase 6 | 增加市场日 K 缓存缺口检测与补齐入口 | 支持查看 SQLite 最新日 K 缺口、dry-run 预览缺失交易日，并自动拉取补齐到 AKShare 最近可用交易日 | P6-01 |
| P6-09 | done | Phase 6 | 重构 Web 工作台普通/专业模式体验 | 默认普通模式使用 SQLite 缓存给出可用结果，专业模式保留完整参数，结果区显示摘要和原始 JSON | P6-07 |
| P6-10 | done | Phase 6 | 早盘优先的多周期选股与买卖计划重构 | 默认早盘竞价决策，支持短线/中短线/中线策略、严格时间边界、买卖计划、早盘回测和 Web/CLI 入口 | P6-05, P6-09 |

## 完成记录

- 2026-06-10 02:26 CST：启动项目自动推进控制面，建立任务清单和运行规则。
- 2026-06-10 02:32 CST：完成 P0 参考项目深读，新增 `docs/research/04_p0_reference_notes.md`。
- 2026-06-10 02:32 CST：完成 P0 skills references 补充，更新 5 个项目 skill。
- 2026-06-10 02:33 CST：完成最小代码骨架，新增 `src/gupiao` 包、配置/数据/报告目录说明和导入测试；`pytest` 尚未安装，已用 `PYTHONPATH=src python -c ...` 完成冒烟检查。
- 2026-06-10 02:34 CST：完成 Python 工程配置，新增 `pyproject.toml`、开发命令文档、CLI entry point 和 pytest/ruff/mypy 配置；已验证 TOML 解析、`compileall` 和 CLI version。
- 2026-06-10 09:12 CST：完成 AKShare 股票列表与日线数据接入口，新增 JSON Lines CLI 子命令和不依赖 AKShare/pandas 的映射测试；已通过 `compileall`、CLI version、`unittest` 7 项；`pytest` 与 AKShare 当前未安装；GitHub 远端同步暂记为 `push_pending`。
- 2026-06-10 09:13 CST：完成 SQLite 本地存储，支持 instruments 和 daily bars 建表、upsert、查询与增量覆盖；已通过 `compileall`、CLI version、`unittest` 9 项；GitHub 远端同步继续记为 `push_pending`。
- 2026-06-10 09:23 CST：完成数据质量检查层，覆盖 instruments 重复/缺失、日线重复、时间顺序、OHLC、负成交量/成交额/换手率、零成交量停牌提示；已通过 `compileall`、CLI version、`unittest` 14 项；GitHub 远端同步继续记为 `push_pending`。
- 2026-06-10 09:27 CST：完成纯 Python 技术指标层，支持 SMA/EMA/MACD/KDJ/RSI/BOLL/ATR/OBV 和收盘价抽取；已通过 `compileall`、CLI version、`unittest` 20 项；GitHub 远端同步继续记为 `push_pending`。
- 2026-06-10 09:30 CST：完成均线多头 + 放量突破 MVP 选股策略，输出候选股、分数、命中原因和关键指标；已通过 `compileall`、CLI version、`unittest` 24 项；GitHub 远端同步继续记为 `push_pending`。
- 2026-06-10 09:34 CST：完成买卖点信号解释，输出 entry/add/reduce/stop/take-profit/invalidation/reasons/risk-reward；已通过 `compileall`、CLI version、`unittest` 27 项；GitHub 远端同步继续记为 `push_pending`。
- 2026-06-10 09:37 CST：完成单策略回测闭环，支持手续费、滑点、止损/止盈/最长持有、收益、回撤、胜率和交易明细；已通过 `compileall`、CLI version、`unittest` 30 项；GitHub 远端同步继续记为 `push_pending`。
- 2026-06-10 09:43 CST：完成 A 股交易约束接入，支持 T+1 最短持有、涨停不可买、跌停不可卖、零成交量停牌不可成交；已通过 `compileall`、CLI version、`unittest` 33 项；GitHub 远端同步继续记为 `push_pending`。
- 2026-06-10 09:47 CST：完成中文 Markdown 绩效报告，覆盖候选股、信号解释、回测指标、交易明细、假设和风险提示；已通过 `compileall`、CLI version、`unittest` 36 项；GitHub 远端同步继续记为 `push_pending`。
- 2026-06-10 09:50 CST：完成 CLI 任务入口，支持数据更新、选股、信号、回测和报告命令；已通过 `compileall`、CLI version、`unittest` 37 项；GitHub 远端同步继续记为 `push_pending`。
- 2026-06-10 09:56 CST：完成静态 Web Dashboard 初版，支持 KPI、候选、买卖点、权益曲线 SVG、交易明细和风险提示；已通过 `compileall`、CLI version、`unittest` 39 项；GitHub 远端同步继续记为 `push_pending`。
- 2026-06-10 10:00 CST：完成多因子研究工具，支持价值、质量、成长、动量、波动率、流动性加权归一化排名；已通过 `compileall`、CLI version、`unittest` 41 项；GitHub 远端同步继续记为 `push_pending`。
- 2026-06-10 10:03 CST：完成 ML 评分与组合优化研究脚手架，支持训练/验证切分、线性基线预测和按评分分配组合权重；已通过 `compileall`、CLI version、`unittest` 45 项；GitHub 远端同步继续记为 `push_pending`。
- 2026-06-10 11:20 CST：完成可恢复全 A 股市场扫描入口，新增 `scan market`、SQLite 缓存复用、逐股失败不中断、轻量公开汇总和 5 项扫描测试；已通过 `compileall`、CLI help、`unittest` 50 项；已安装 AKShare 并完成 3 只股票真实 smoke test，生成 `reports/summaries/smoke_market_scan.md`。
- 2026-06-10 11:24 CST：本轮 Phase 6 提交 `1942e2a feat: add recoverable market scan workflow` 已成功推送到 GitHub `main`；下一项仍为 P6-02 完整全 A 股扫描。
- 2026-06-10 11:29 CST：启动 P6-02 完整全 A 股扫描，使用 `data/cache/market_scan.sqlite` 和 `reports/generated/market_scan/latest/` 作为本地缓存/完整结果路径，只提交 `reports/summaries/latest_market_scan.md`。
- 2026-06-10 12:02 CST：首轮全量扫描在 708 条结果、147 条远端断连失败后暂停，已保留 SQLite 成功缓存；新增 `--request-sleep` 请求节流参数并通过 51 项测试，准备从缓存恢复扫描。
- 2026-06-10 12:56 CST：后续恢复扫描曾因单只 AKShare 请求长时间挂起暂停；新增 `--request-timeout` 单次请求超时参数，推荐用 `--request-sleep 2.0 --retry-sleep 3 --request-timeout 60` 从 SQLite 缓存继续推进，GitHub 推送仍不阻塞任务。
- 2026-06-10 16:16 CST：新增 `data import-daily-cache` 本地日 K CSV 导入命令，已将 `cache/daily_k/market_data_cache` 中 2023-06-12 至 2026-04-23 的本地日 K 整合进 `data/cache/market_scan.sqlite`；新增扫描缓存完整性保护，避免半截缓存覆盖全区间扫描判断。
- 2026-06-10 16:55 CST：完成 P6-03 竞价数据增强第一阶段，新增 AKShare 盘前分钟数据接入、竞价画像/评分、选股策略竞价加权、回测竞价画像注入、研究样本生成和 `skills/auction-data-integration`；后续 P6-04/P6-05 继续导入本地历史竞价缓存并做样本外迭代。
- 2026-06-10 17:19 CST：完成 P6-04 本地历史竞价缓存导入入口，新增 `data import-auction-cache`、SQLite `auction_profiles` 存储/查询、RAR 流式解析、委买委卖不平衡特征、扫描 `--auction-provider` 接入和竞价增强扫描参数；已对 `2026-05-06` 做真实小导入，写入 5,490 条 `local_jingjia` 竞价画像，29 个月全量导入留作可恢复数据作业。
- 2026-06-10 17:40 CST：完成 P6-05 竞价增强策略对比与 skill 迭代，新增 `research auction-compare`，导入 2026-05-06 至 2026-05-29 的 98,958 条竞价画像，并用 2026-01-01 至 2026-05-29 的日 K 对 5,510 只有竞价画像的股票跑 baseline vs auction 对比；结果显示 `min_auction_score=60` + `auction_score_weight=0.15` 平均收益差为 -0.18%，已将 skill 建议调整为优先软排序/解释，不默认硬过滤。
- 2026-06-10 19:13 CST：完成 Web 端选股体验与多策略接口补全，新增 `screen list`、`screen run`、`screen candidates`、`data status`，支持 `ma_volume_breakout`、`momentum_pullback`、`low_volatility_breakout`、`auction_assisted_breakout`，`as_of` 截止日期和 SQLite 缓存候选；Web 新增 `strategy_list`、`data_status`、`screen_candidates` action 和页面入口；已通过 `compileall` 与 `unittest` 86 项。
- 2026-06-10 19:30 CST：完成市场日 K 缓存缺口检测与补齐入口，新增 `data refresh-market-cache`、`MarketCacheRefreshConfig`、`refresh_market_daily_cache` 和 Web action `data_refresh_market_cache`；支持 `--dry-run` 查看缺失交易日、`--probe-symbol` 探测最近可用交易日、`--limit/--symbol` 小范围补齐；已通过 `compileall`、`unittest` 90 项和 CLI help 验证。
- 2026-06-10 19:44 CST：按用户反馈重构 Web 工作台体验，新增默认普通模式首页（查看缓存、批量选股、单股分析、查看日K缺口），完整参数收进专业模式；修复默认 `/tmp/gupiao_web_bars.jsonl` 不存在导致按钮无结果的问题，改为默认使用 `data/cache/market_scan.sqlite`；结果区新增摘要卡片和 Top 候选表，原始 JSON 保留；已通过 `compileall`、`unittest` 90 项、HTTP `/api/health` 与 `/api/run data_status` 验证。
- 2026-06-10 21:15 CST：完成早盘优先的多周期选股与买卖计划重构，新增 `screen morning`、`plan trade`、`backtest morning`，短线强依赖竞价，中短线以量价结构为主，中线弱化竞价；早盘模式只使用交易日之前的日 K 与交易日当天竞价画像，回测用交易日开盘价加滑点成交；Web 普通模式新增早盘选股和买卖计划摘要；已通过 `compileall`、`unittest` 95 项和 CLI version 验证。
