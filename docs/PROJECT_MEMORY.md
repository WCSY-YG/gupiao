# 项目记忆

更新时间：2026-06-10 21:49 CST（Asia/Shanghai）

## 用户目标

用户要做一个炒股/股票量化研究项目，希望由 Codex 统筹推进。核心功能包括：

- 各种策略选股。
- 买卖点分析。
- GitHub 高星项目调研。
- 把优秀项目经验蒸馏成一系列可复用 skills。
- 后续由 Codex 继续规划并推动实现。

## 当前完成内容

已经完成第一轮 GitHub 调研与项目规划，生成了以下文件：

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

已经启动项目自动推进控制面：

- `docs/PROJECT_TASKS.md`：项目任务清单，记录 `pending` / `in_progress` / `done` / `blocked` 状态。
- `docs/AUTOMATION_RUNBOOK.md`：每轮自动推进规则、GitHub 更新规则和阻塞处理方式。

已经完成 P0 参考项目深读：

- `docs/research/04_p0_reference_notes.md`：AKShare、myhhub/stock、TA-Lib Python、backtesting.py、QuantStats 的 README/docs/examples/license 深读笔记和落地建议。

已经完成 P0 skills references 补充：

- 5 个项目 skill 均已补充来源链接、许可证、关键 API/约束和实现提示。

已经完成最小代码骨架：

- `src/gupiao/`：基础包、CLI 入口、数据 provider 协议、核心数据记录、指标/策略/信号/回测/报告模块边界。
- `configs/`、`data/`、`reports/`：目录说明。
- `tests/test_package_import.py`：最小导入和 CLI version 测试。
- 验证：`pytest` 尚未安装；已使用 `PYTHONPATH=src python -c ...` 完成导入/CLI 冒烟检查。

已经完成 Python 工程配置：

- `pyproject.toml`：`src/` layout、CLI entry point、可选依赖、pytest/ruff/mypy 配置。
- `docs/DEVELOPMENT.md`：环境安装、测试、格式化、类型检查和打包命令。
- 验证：`pyproject.toml` 可解析，`PYTHONPATH=src python -m compileall -q src tests` 通过，`PYTHONPATH=src python -m gupiao.cli --version` 输出 `0.1.0`。

已经完成股票列表与日线数据接入接口：

- `AkshareProvider` 懒加载 AKShare，支持 A 股股票列表和日线行情映射。
- CLI 支持 `gupiao data instruments --limit 10` 和 `gupiao data daily 000001 --start YYYY-MM-DD --end YYYY-MM-DD --limit 5`，输出 JSON Lines。
- 新增不依赖 AKShare/pandas 的 provider 映射、日期解析、交易所推断和 CLI helper 测试。
- 验证：`PYTHONPATH=src python -m compileall -q src tests` 通过，`PYTHONPATH=src python -m gupiao.cli --version` 输出 `0.1.0`，`PYTHONPATH=src python -m unittest discover -s tests` 通过 7 项；`pytest` 与 AKShare 当前未安装，真实 AKShare smoke test 跳过。

已经完成 SQLite 本地数据存储：

- `SQLiteStore` 支持 instruments 和 daily bars 的 schema 初始化、批量 upsert、查询和重复写入覆盖。
- 存储层仅使用 Python 标准库 `sqlite3`，DuckDB/Parquet 留作后续扩展。
- 新增临时 SQLite 文件测试，覆盖写入、读取和增量更新。
- 验证：`compileall`、CLI version、`PYTHONPATH=src python -m unittest discover -s tests` 通过 9 项。

已经完成数据质量检查层：

- `validate_instruments` 覆盖股票基础信息缺失和重复 symbol。
- `validate_daily_bars` 覆盖重复记录、时间顺序、OHLC 合法性、负成交量/成交额/换手率和零成交量停牌提示。
- `ValidationIssue` 提供结构化 `code`、`message`、`severity`、`symbol`、`trade_date`、`field`。
- 验证：`compileall`、CLI version、`PYTHONPATH=src python -m unittest discover -s tests` 通过 14 项。

已经完成技术指标层：

- 纯 Python 实现 SMA、EMA、MACD、KDJ、RSI、BOLL、ATR、OBV 和 `closes`。
- 指标输出与输入等长，暖机期使用 `None`，方便后续策略按行情索引对齐。
- TA-Lib 仍作为后续可选依赖，不阻塞当前 MVP。
- 验证：`compileall`、CLI version、`PYTHONPATH=src python -m unittest discover -s tests` 通过 20 项。

已经完成第一个 MVP 选股策略：

- `MovingAverageVolumeBreakoutStrategy` 实现均线多头 + 放量突破 + 成交量放大过滤。
- 输出 `ScreeningCandidate`，包含 symbol、trade_date、strategy、score、reasons、metrics。
- 策略会先检查日线数据质量；存在 error 时跳过候选。
- 验证：`compileall`、CLI version、`PYTHONPATH=src python -m unittest discover -s tests` 通过 24 项。

已经完成买卖点信号解释：

- `build_breakout_signal` 将选股候选和行情转换为 `SignalPlan`。
- 输出入场价、加仓价、减仓价、止损价、止盈价、信号失效条件、原因列表、风险收益比。
- ATR 可用时使用 ATR 止损；ATR 不足时使用百分比兜底止损。
- 验证：`compileall`、CLI version、`PYTHONPATH=src python -m unittest discover -s tests` 通过 27 项。

已经完成单策略回测闭环：

- `run_breakout_backtest` 复用 MVP 选股策略和信号计划，输出 `BacktestResult`。
- 支持手续费、滑点、止损、止盈、最长持有、收益、最大回撤、胜率、权益曲线和交易明细。
- 当前假设为单标的、全仓、信号收盘价成交。
- 验证：`compileall`、CLI version、`PYTHONPATH=src python -m unittest discover -s tests` 通过 30 项。

已经完成 A 股交易约束：

- `BacktestConfig` 增加 A 股约束开关和参数。
- 回测默认启用 T+1 最短持有、涨停不可买、跌停不可卖、零成交量停牌不可成交。
- 暴露 `can_enter`、`can_exit`、`is_limit_up`、`is_limit_down`、`is_suspended` 便于测试和后续报告解释。
- 验证：`compileall`、CLI version、`PYTHONPATH=src python -m unittest discover -s tests` 通过 33 项。

已经完成中文绩效报告：

- `build_markdown_report` 输出中文 Markdown，覆盖候选股、信号解释、回测指标、交易明细、风险提示和回测假设。
- `write_markdown_report` 支持报告落盘。
- QuantStats HTML 报告仍作为后续增强，不阻塞当前 MVP。
- 验证：`compileall`、CLI version、`PYTHONPATH=src python -m unittest discover -s tests` 通过 36 项。

已经完成 CLI 任务入口：

- `data update-daily` 支持 AKShare 拉取日线并写入 SQLite。
- `screen breakout`、`signal breakout`、`backtest breakout`、`report breakout` 支持读取本地 JSONL bars。
- CLI 输出 JSON，报告命令生成 Markdown 文件。
- 验证：`compileall`、CLI version、`PYTHONPATH=src python -m unittest discover -s tests` 通过 37 项。

已经完成 Web Dashboard 初版：

- `build_dashboard_html` 输出自包含静态 HTML，包含 KPI、候选指标、买卖点、权益曲线 SVG、交易明细和风险提示。
- `write_dashboard_html` 支持仪表盘落盘。
- 暂不引入前端构建链；后续如需交互式 Dashboard，再接 FastAPI/Web UI。
- 验证：`compileall`、CLI version、`PYTHONPATH=src python -m unittest discover -s tests` 通过 39 项。

已经完成多因子研究工具：

- `rank_factors` 支持价值、质量、成长、动量、波动率、流动性等因子的归一化和加权排名。
- `volatility` 默认越低越好，其余默认越高越好。
- 输出 `FactorScore`，包含综合得分、分项得分和原始因子。
- 验证：`compileall`、CLI version、`PYTHONPATH=src python -m unittest discover -s tests` 通过 41 项。

已经完成 ML 评分与组合优化研究脚手架：

- `split_train_validation` 提供样本外验证切分。
- `train_linear_baseline` / `predict_linear_baseline` 提供无外部依赖的线性基线评分。
- `allocate_by_score` 支持按预测评分生成 top N 组合权重并做权重上限控制。
- 验证：`compileall`、CLI version、`PYTHONPATH=src python -m unittest discover -s tests` 通过 45 项。

已经完成可恢复全 A 股市场扫描自动化入口：

- `scan market` 支持通过 AKShare 获取全 A 股列表，逐只拉取日线并写入 SQLite 缓存。
- 支持中断后复用已有 SQLite 日线数据；单只股票失败不会终止全局扫描。
- 每只股票执行数据质量检查、MVP 策略筛选、买卖点生成和回测。
- 本地完整结果写入 `reports/generated/market_scan/...`，原始行情和 SQLite 写入 `data/cache/...`，这些路径继续被 Git 忽略。
- 可提交的小型 Markdown 汇总写入 `reports/summaries/...`。
- 新增 5 项扫描测试，覆盖成功扫描、单只失败、空数据、缓存复用、Top N 汇总和 CLI 默认参数。
- 验证：`compileall` 通过，`PYTHONPATH=src python -m unittest discover -s tests` 通过 50 项，`PYTHONPATH=src python -m gupiao.cli scan market --help` 正常。
- 已安装 AKShare data extras，并完成 3 只股票真实 smoke test：处理 3、成功 3、失败 0、无数据 0、当前候选 0；提交小汇总 `reports/summaries/smoke_market_scan.md`。

## 同步状态

- GitHub 推送已恢复；README 中文使用说明提交已成功推送到 `main`。
- 本轮 Phase 6 代码、文档和 smoke 小汇总已提交并推送：`1942e2a feat: add recoverable market scan workflow`。
- 若后续 GitHub push 是网络问题，重试；若是 SSH/403 权限问题，记录 `push_pending` 并继续任务。

## 当前调研结论

MVP 优先参考项目：

- AKShare：https://github.com/akfamily/akshare
- myhhub/stock：https://github.com/myhhub/stock
- TA-Lib Python：https://github.com/TA-Lib/ta-lib-python
- backtesting.py：https://github.com/kernc/backtesting.py
- QuantStats：https://github.com/ranaroussi/quantstats

架构设计优先参考项目：

- Qlib：https://github.com/microsoft/qlib
- vn.py：https://github.com/vnpy/vnpy
- zvt：https://github.com/zvtvz/zvt
- hikyuu：https://github.com/fasiondog/hikyuu
- QUANTAXIS：https://github.com/yutiansut/QUANTAXIS

后期增强参考项目：

- vectorbt：https://github.com/polakowo/vectorbt
- FinRL：https://github.com/AI4Finance-Foundation/FinRL
- OpenBB：https://github.com/OpenBB-finance/OpenBB
- QuantConnect Lean：https://github.com/QuantConnect/Lean

## 建议技术路线

- Python 3.11/3.12。
- 后续所有 Python 命令默认使用 conda 的 `agent` 环境，例如 `conda run -n agent python -m unittest discover -s tests`。
- 数据处理：pandas，后期可引入 Polars。
- 存储：SQLite/DuckDB + Parquet。
- 数据源：AKShare 作为 MVP 主数据源。
- 指标：TA-Lib 优先，安装受阻时用 bukosabino/ta 兜底。
- 回测：backtesting.py 做 MVP，vectorbt 做批量参数回测增强。
- 报告：QuantStats + 自定义中文解释报告。
- UI：先 CLI，后 FastAPI + Web Dashboard。

## 下一步默认推进

每轮恢复时先读取 `docs/AUTOMATION_RUNBOOK.md` 和 `docs/PROJECT_TASKS.md`，再推进下一项 `pending` 任务。

当前下一项任务：

1. P6-02 完整全 A 股扫描仍是长期可恢复数据作业；需要时继续使用 `PYTHONPATH=src python -m gupiao.cli scan market --start 2023-06-10 --end 2026-06-10 --adjust hfq --db data/cache/market_scan.sqlite --output reports/generated/market_scan/latest --public-summary reports/summaries/latest_market_scan.md --top 30 --request-sleep 2.0 --retry-sleep 3 --request-timeout 60`。
2. 原始行情、SQLite、逐股完整结果继续留在 `data/cache/` 和 `reports/generated/`，不提交 GitHub。
3. 若全量扫描或竞价导入耗时过长或中断，重复运行同一命令即可复用 SQLite 缓存继续推进。
4. 当前无新的非长任务 `pending`；后续可继续扩展策略实验、报告模板、组合优化和模拟交易风控。

每完成一个任务，必须更新 `docs/PROJECT_TASKS.md` 和本文件，并提交本地 Git。GitHub 推送恢复后再同步 `push_pending` 提交。

## 2026-06-10 12:56 CST 运行记忆

- P6-02 完整扫描已多次从 `data/cache/market_scan.sqlite` 恢复，缓存保留成功行情；`reports/generated/market_scan/latest/` 继续作为本地完整结果目录。
- 前序全量尝试主要失败模式为 AKShare 远端断连和单只请求长时间挂起；本轮新增 `scan market --request-timeout`，默认 60 秒，配合 3 次重试和请求节流继续推进。
- 当前 GitHub 同步策略不变：代码、文档和小型 Markdown 汇总可本地提交；原始行情、SQLite、逐股 JSONL/CSV 和完整生成目录不提交；推送失败只记录 `push_pending`，不停止任务。

## 2026-06-10 16:16 CST 本地缓存整合记忆

- 用户已放入本地数据目录：`cache/daily_k/market_data_cache` 为按交易日拆分的全市场日 K CSV，`cache/jingjia` 为集合竞价快照 RAR 月包。
- 新增 `PYTHONPATH=src python -m gupiao.cli data import-daily-cache`，支持按日期范围导入本地日 K、`--dry-run` 统计、`--conflict ignore|replace` 冲突策略。
- 已导入 `2023-06-10` 至 `2026-04-23` 范围的本地日 K：读取 694 个交易日文件、3,523,364 行，3,523,329 行可导入，写入 2,810,490 条新日线；35 行无效记录跳过。
- 导入后 `data/cache/market_scan.sqlite` 共有 5,206 只股票、3,555,670 条日线，日期范围为 `2023-06-12` 至 `2026-06-10`；其中 `akshare` 745,180 条、`local_daily_k_estimated_volume` 2,798,064 条、`local_daily_k` 12,426 条。
- `daily_k` 老格式缺少真实成交量，导入器用 `amount / close` 估算并标记 provider；后续使用放量策略时要把该估算风险写进报告。
- `cache/jingjia/*.rar` 已确认可用 `unrar` 读取，字段包含 `security_id, md_date, md_time, pre_close, last, open, total_volume_trade, total_value_trade, bid/ask` 等集合竞价快照；当前不混入日 K 表，后续应新建竞价专用表或按需抽取特征。
- 扫描缓存逻辑已加完整性保护：只有缓存最新交易日覆盖扫描 `--end` 时才直接复用，避免本地日 K 只到 `2026-04-23` 却被误用于 `2026-06-10` 全区间扫描。

## 2026-06-10 16:55 CST 竞价增强记忆

- AKShare 源码/文档确认 `stock_zh_a_hist_pre_min_em` 为东方财富盘前分时接口，单次返回最近一个交易日分钟数据，包含盘前数据；适合实时/当日竞价画像，不适合单独声明历史回测。
- 新增 `AuctionMinuteBar` 和 `AuctionProfile`，支持从盘前分钟数据生成竞价画像：竞价缺口、竞价量比、竞价波动和 0-100 竞价强度分。
- `AkshareProvider.fetch_pre_market_minutes` 已对接 AKShare 盘前分钟接口，CLI 新增 `data pre-market`。
- `MovingAverageVolumeBreakoutStrategy` 可选接收 `auction_profile`，将竞价强度分数、竞价缺口和竞价成交量写入候选指标，并可用 `min_auction_score` 过滤。
- `run_breakout_backtest` 可按交易日注入历史 `AuctionProfile`，用于对比“纯 K 线策略”和“竞价增强策略”。
- `build_auction_research_samples` 可生成竞价特征与未来收益样本，供后续滚动验证和轻量 ML 评分迭代。
- 历史竞价回测应优先导入本地 `cache/jingjia/*.rar` 的历史快照，按 `symbol + trade_date` 生成 `AuctionProfile` 后注入回测。
- 竞价增强策略必须保留时间边界：开盘前决策只能使用竞价时间戳之前的数据，不能用同日收盘/最高/最低反推。

## 2026-06-10 17:08 CST 竞价增强交接记录

- 本轮在 `main` 完成并推送提交 `c27459a feat: add auction-aware screening workflow`，远端 `origin/main` 已同步；远端地址为 `ssh://git@ssh.github.com:443/WCSY-YG/gupiao.git`。
- 已按用户要求保持 README 中文说明，并记录后续 Python 命令默认使用 conda `agent` 环境。
- 新增/更新的核心能力：AKShare 当日盘前分钟数据接入、竞价画像与评分、放量突破策略竞价加权/过滤、回测按交易日注入 `AuctionProfile`、竞价研究样本生成、`skills/auction-data-integration`。
- 已修正研究样本的未来函数隐患：竞价日样本特征只使用竞价画像和前一交易日 K 线特征，目标收益从竞价日开盘价向后计算；不能把当天收盘相对开盘等盘后信息作为盘前特征。
- 已执行并通过验证：`conda run -n agent ruff check src/gupiao/auction src/gupiao/strategies/screening.py src/gupiao/backtest/engine.py src/gupiao/research/experiments.py tests/test_auction_features.py tests/test_screening_strategy.py tests/test_backtest_engine.py tests/test_research_experiments.py`、`conda run -n agent python -m compileall -q src tests`、`conda run -n agent env PYTHONPATH=src python -m unittest discover -s tests`（66 项通过）、`conda run -n agent env PYTHONPATH=src python -m gupiao.cli --version`（输出 `0.2.0`）。
- 当前工作区在提交后应保持 `main...origin/main` 干净；若其他线程接手，先运行 `git status --short --branch` 复核。
- 当时下一步建议为 P6-04：将 `cache/jingjia/*.rar` 历史集合竞价快照解析成专门表或画像缓存，再执行 P6-05 对比“纯 K 线策略”和“竞价增强策略”的近期滚动回测，迭代 skill 阈值和评分权重。

## 2026-06-10 17:19 CST 本地竞价缓存导入记忆

- 新增 `PYTHONPATH=src python -m gupiao.cli data import-auction-cache`，支持从 `cache/jingjia/*.rar` 流式读取集合竞价快照，按 `symbol + trade_date + provider` 写入 SQLite `auction_profiles`。
- 画像字段包括竞价价格、竞价缺口、竞价区间波动、竞价量比、委买委卖不平衡和 0-100 竞价强度分；`total_volume_trade` 按手数导入并转换为股数。
- `SQLiteStore` 新增 `upsert_auction_profiles` 和 `get_auction_profiles`；`scan market` 新增 `--auction-provider`，会按交易日把竞价画像注入当前候选评估和逐股回测。
- 策略 CLI 新增 `--min-auction-score` 和 `--auction-score-weight`，用于竞价硬过滤与候选分混合；公开扫描汇总会显示竞价画像源、竞价分和竞价缺口。
- 已做真实小导入验证：`2026-05-06` 一个日文件读取 416,710 行快照，时间窗内 415,732 行，构建并写入 5,490 条 `local_jingjia` 竞价画像；当前 `auction_profiles` 覆盖日期为 `2026-05-06`。
- `cache/jingjia` 当前有 29 个 RAR 月包（`202401.rar` 至 `202605.rar`），约 1.3G；29 个月全量导入是较长数据作业，建议先 dry-run，再按日期范围运行同一导入命令，原始 RAR 和 SQLite 不提交 GitHub。
- 下一步 P6-05 应优先用已导入或继续导入后的竞价画像，对比 baseline 与 `local_jingjia` 竞价增强策略的近期样本外表现，再更新 `skills/stock-screening-strategies` 的阈值建议。

## 2026-06-10 17:40 CST 竞价增强回测与 skill 迭代记忆

- 新增 `PYTHONPATH=src python -m gupiao.cli research auction-compare`，从 SQLite 中读取日 K 和 `auction_profiles`，逐股对比 baseline 均线放量突破与竞价增强版本，并输出 `reports/generated/auction_validation/latest/` 完整结果和 `reports/summaries/latest_auction_validation.md` 小型汇总。
- 已继续导入最近竞价缓存：`2026-05-06` 至 `2026-05-29` 共 18 个交易日文件，读取 7,461,068 行快照，时间窗内 7,448,345 行，构建 98,958 条画像，新增写入 93,468 条；当前 `auction_profiles` 覆盖 `2026-05-06` 至 `2026-05-29`、5,510 只股票。
- 已完成近期真实对比：回测区间 `2026-01-01` 至 `2026-05-29`，竞价源 `local_jingjia`，参数 `min_auction_score=60`、`auction_score_weight=0.15`；处理 5,510 只，成功对比 5,187，只读/写本地完整结果，不提交逐股 JSONL。
- 对比结论：baseline 平均收益 0.12%，auction 平均收益 -0.06%，平均收益差 -0.18%；竞价增强收益更高 249 只、更低 204 只，多数股票无交易差异。
- Skill 迭代：不要把 `min_auction_score=60` 直接作为默认硬过滤；当前更合理的是把竞价强度、缺口、量比和委买委卖不平衡作为候选排序/解释辅助，待 P6-06 多月份滚动验证后再考虑默认阈值。
- 已更新 `skills/stock-screening-strategies` 和 `skills/auction-data-integration`：竞价分可做软加权，硬过滤保持实验配置；`research auction-compare` 的 Markdown 汇总作为后续 skill 参数变更的证据来源。

## 2026-06-10 19:13 CST Web 与多策略接口补全记忆

- 新增轻量策略注册表，当前策略 ID：`ma_volume_breakout`、`momentum_pullback`、`low_volatility_breakout`、`auction_assisted_breakout`。
- `auction_assisted_breakout` 要求同日竞价画像存在，但不默认设置 `min_auction_score=60` 硬过滤；竞价强度、缺口、量比和委买委卖不平衡继续作为候选排序/解释辅助。
- 新增日期边界语义：`as_of` 表示只使用该日期及之前的 K 线；若 `end` 与 `as_of` 同时传入且不一致，会直接报错以避免未来函数。
- 新增 CLI：`screen list`、`screen run --strategy ... --as-of ...`、`screen candidates --db ... --as-of ...`、`data status --db ...`；旧 `screen breakout`、`signal breakout`、`backtest breakout`、`report breakout` 继续兼容，并支持 `--strategy` 与 `--as-of`。
- 新增 Web action：`strategy_list`、`data_status`、`screen_candidates`；现有单股分析 action 支持 `strategy_id`、`as_of`、`lookback`、`auction_provider`。
- Web 工作台已补策略下拉、截至日期、lookback、缓存状态和缓存批量选股入口；README 已补中文功能说明、CLI 示例和 Web `/api/run` payload。
- 本轮只做功能和文档补全，没有启动全 A 股长扫描、没有重新下载行情、没有提交 SQLite 或缓存大文件。
- 已执行并通过验证：`conda run -n agent env PYTHONPATH=src python -m compileall -q src tests`、`conda run -n agent env PYTHONPATH=src python -m unittest discover -s tests`（86 项通过）。

## 2026-06-10 19:30 CST 市场日 K 缓存刷新记忆

- 新增 `PYTHONPATH=src python -m gupiao.cli data refresh-market-cache`，用于检测 SQLite `bars_daily` 当前最新日期到目标日期之间缺少的交易日，并自动补齐到 AKShare 能返回的最近交易日。
- 刷新逻辑：读取本地 `daily_bar_date_range`，默认从缓存最新日期下一天开始；用 `--probe-symbol`（默认 `000001`）探测实际缺失交易日；`--dry-run` 只输出 `missing_trade_dates` 和 `missing_trade_days`；正式运行逐只股票拉取缺口区间并 upsert，单只失败记录在 `failures` 且不中断整体任务。
- 新增 Web action `data_refresh_market_cache`，Web 工作台“竞价与缓存”面板已有“补齐日K缺口”按钮；Web 默认 `dry_run=true`，前端确认后可改为 `false` 执行真实补齐。
- README 已补 CLI 与 Web payload 示例；建议真实全市场补齐前先执行 `--dry-run`，再用 `--limit` 或 `--symbol` 小范围验证，最后放开全市场。
- 本轮未启动真实 AKShare 全市场补齐，没有写入项目缓存数据库或提交大文件。
- 已执行并通过验证：`conda run -n agent env PYTHONPATH=src python -m compileall -q src tests`、`conda run -n agent env PYTHONPATH=src python -m unittest discover -s tests`（90 项通过）、`conda run -n agent env PYTHONPATH=src python -m gupiao.cli data refresh-market-cache --help`。

## 2026-06-10 19:44 CST Web 普通/专业模式重构记忆

- 用户反馈 Web 端默认不能正常给结果、参数过多、按钮功能不清晰；已将默认入口改为普通模式首页，提供 4 个高频卡片：`查看缓存`、`开始选股`、`分析股票`、`查看缺口`。
- 普通模式默认使用 `data/cache/market_scan.sqlite`，不再填写不存在的 `/tmp/gupiao_web_bars.jsonl`；高级表单中的 JSONL 字段也改为空，SQLite DB 默认使用本地缓存。
- 右上角新增 `普通模式/专业模式` 切换；专业模式才显示原来的数据、策略、扫描、研究完整参数表单。
- 结果区新增摘要层：缓存状态显示最新日期/股票数/行数，批量选股显示处理数、候选数和 Top 候选表，单股分析显示候选/策略/分数/信号/收益/交易数，日K补齐显示缺失日期和写入状态；原始 JSON 仍保留在下方。
- 已用真实本地缓存验证：`data_status` 返回日K最新 `2026-06-10`、5206 只；`screen_candidates` 默认 500 只可返回候选；`quick_analysis` 对 `000001` 可生成回测和 Dashboard。
- HTTP 验证：临时启动 `127.0.0.1:8876`，`/api/health` 和 `/api/run data_status` 正常；`8765` 当时已被占用，说明若用户看不到新页面，需要重启旧 Web 进程或换端口启动。
- 已执行并通过验证：`compileall`、`unittest` 90 项、`gupiao.cli --version`、`git diff --check`。

## 2026-06-10 21:15 CST 早盘优先多周期重构记忆

- 用户指出原先“截止日期选股”更像收盘后研究，缺少早盘什么时候买、怎么卖的执行计划；本轮已将默认主流程规范为早盘竞价决策，收盘后研究流程继续保留为辅助入口。
- 新增 `src/gupiao/trade_plan.py`，统一定义 `decision_time`、`signal_date`、`entry_date`、`entry_timing`、`entry_price_source`、止损、止盈、减仓、最长持有和不买条件，明确“选出来”不等于“立刻无条件买入”。
- 新增 `src/gupiao/strategies/morning.py`，早盘模式以交易日 D 为决策日：日 K 只允许使用 `trade_date < D` 的历史数据，可匹配 D 日 `local_jingjia` 竞价画像；短线缺少竞价画像时直接跳过，中线缺少竞价仍可评估。
- 策略体系已扩展为多周期：`short_term` 默认 `auction_open_breakout_short`，强依赖竞价；`mid_short_term` 默认 `volume_breakout_swing`，以趋势和量价结构为主、竞价确认；`mid_term` 默认 `trend_quality_mid`，趋势质量优先、竞价弱参考。
- 新增 CLI：`screen morning` 用缓存批量早盘选股，`plan trade` 输出单只股票早盘买卖计划，`backtest morning` 用 D-1 及以前日 K + D 日竞价判断、D 日开盘价加滑点模拟买入。
- Web `/api/run` 新增/补齐 `morning_screen`、`trade_plan`、`backtest_morning`，普通模式首页改为“早盘选股”和“买卖计划”优先展示，结果摘要先显示执行建议、参考买入价、止损、止盈和不买条件，再保留原始 JSON。
- README 已补中文说明：早盘数据边界、买入时点、短线/中短线/中线周期含义、CLI 命令和 Web payload；`skills/stock-screening-strategies` 也记录早盘模式禁止使用当日完整日 K 的约束。
- 本轮未启动全市场扫描、未重新下载行情、未写入或提交 SQLite/缓存大文件；只复用现有 `data/cache/market_scan.sqlite` 和 `local_jingjia` 画像做接口与测试验证。
- 已执行并通过验证：`conda run -n agent env PYTHONPATH=src python -m compileall -q src tests`、`conda run -n agent env PYTHONPATH=src python -m unittest discover -s tests`（95 项通过）、`conda run -n agent env PYTHONPATH=src python -m gupiao.cli --version`（输出 `0.2.0`）。

## 2026-06-10 21:39 CST 竞价参数滚动验证记忆

- P6-06 已完成，新增 `PYTHONPATH=src python -m gupiao.cli research auction-rolling`，用于按自然月滚动验证多组 `min_auction_score` 与 `auction_score_weight`。
- 新增 `AuctionRollingValidationConfig`、`AuctionRollingWindow`、`AuctionRollingEvaluation` 和 `run_auction_rolling_validation`；执行时复用现有 `run_auction_strategy_comparison`，每个窗口和参数组合的逐股明细写入 `reports/generated/auction_rolling/...`。
- 默认参数网格：`min_auction_scores=(None, 50, 60, 70)`，`auction_score_weights=(0, 0.10, 0.15, 0.25)`；`None + 0` 可作为软排序/无硬过滤控制组。
- 公开汇总 `reports/summaries/latest_auction_rolling.md` 只包含参数稳定性排名、正向窗口比例、成功样本数、平均收益差和风险提示，不包含逐股原始 OHLC 或大体积结果。
- Web 专业模式新增 `auction_rolling` action 和“竞价参数滚动验证”表单；普通模式不增加复杂参数，继续保持早盘选股和买卖计划为主。
- README 已补 CLI 命令、Web payload、产物边界和推荐工作流；P6-06 完成后当前无新的非长任务 `pending`，仅 P6-02 全市场完整扫描仍是可恢复长期作业。
- 本轮没有启动真实全市场滚动验证，只使用单元测试小样本验证功能路径，避免生成大文件或消耗远端行情接口。
- 已执行并通过验证：`conda run -n agent env PYTHONPATH=src python -m compileall -q src tests`、`conda run -n agent env PYTHONPATH=src python -m unittest discover -s tests`（99 项通过）、`conda run -n agent env PYTHONPATH=src python -m gupiao.cli --version`（输出 `0.2.0`）、`conda run -n agent env PYTHONPATH=src python -m gupiao.cli research auction-rolling --help`。

## 2026-06-10 21:49 CST 早盘计划价格口径修正记忆

- 目标完成审计时用真实缓存执行 `screen morning --trade-date 2026-05-29 --horizon short_term --limit 20`，命中候选 `000027`；该 smoke 暴露一个风险：竞价参考价是未复权价格，而默认日 K 为 `hfq` 复权价格，若用复权 ATR 直接计算止损/止盈，会产生明显不合理的交易计划。
- 已修正 `build_trade_plan`：当 `entry_price_source="auction_indicative_price"` 且最新日 K `adjust` 不是 `raw` 时，不使用 ATR 距离，改用周期配置的百分比止损/止盈兜底。
- 早盘计划现在会在 `risk_notes` 中说明“竞价参考价是未复权口径，日K为 hfq/qfq 口径，止损止盈已改用百分比兜底”；README 早盘数据边界也增加了价格口径说明。
- 已补测试：`tests/test_morning_workflow.py` 断言复权日 K + 竞价价时止损使用百分比兜底并输出风险提示。
- 已验证：`conda run -n agent env PYTHONPATH=src python -m compileall -q src tests`、`conda run -n agent env PYTHONPATH=src python -m unittest discover -s tests`（99 项通过）、`conda run -n agent env PYTHONPATH=src python -m gupiao.cli --version`（输出 `0.2.0`）；真实缓存 `screen morning` smoke 中 `000027` 计划已输出参考买入 7.98、止损 7.7007、减仓 8.2593、止盈 8.399，价格口径恢复合理；`research auction-rolling` 小型 smoke 写入 `/tmp/gupiao_goal_audit/auction_rolling.md`，1 个窗口、4 个参数组合。

## 注意事项

- 当前项目定位为研究与辅助分析工具，不默认接入真实交易。
- 必须防未来函数、幸存者偏差、财务数据偷看、参数过拟合。
- A 股回测必须考虑 T+1、涨跌停、停牌、手续费、印花税、滑点。
