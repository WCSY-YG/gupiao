# 项目记忆

更新时间：2026-06-10 09:34 CST（Asia/Shanghai）

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

## 同步状态

- `push_pending`：GitHub 推送凭据暂不可用，按用户最新指令先继续推进任务。
- 待推送本地提交起点：`85225e2 build: add python project tooling` 及其后的本地提交。

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

1. `P3-01`：跑通单策略回测闭环。
2. `P3-02`：加入 A 股交易约束。
3. `P3-03`：生成中文绩效报告。
4. `P4-01`：提供 CLI 任务入口。
5. 跑通：获取数据 -> 计算指标 -> 选股 -> 买卖点解释 -> 回测 -> 报告。

每完成一个任务，必须更新 `docs/PROJECT_TASKS.md` 和本文件，并提交本地 Git。GitHub 推送恢复后再同步 `push_pending` 提交。

## 注意事项

- 当前项目定位为研究与辅助分析工具，不默认接入真实交易。
- 必须防未来函数、幸存者偏差、财务数据偷看、参数过拟合。
- A 股回测必须考虑 T+1、涨跌停、停牌、手续费、印花税、滑点。
