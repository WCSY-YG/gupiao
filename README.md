# gupiao

A-share stock screening and buy/sell signal research toolkit.

`gupiao` 是一个面向 A 股的量化研究辅助项目，用来串起数据接入、指标计算、策略选股、买卖点解释、回测验证、中文报告和静态 Dashboard。项目只用于研究和决策支持，不构成投资建议，也不默认接入真实交易。

## 当前能力

- A 股股票列表和日线行情接入，MVP 数据源为 AKShare。
- 本地 SQLite 存储，支持股票基础信息和日线数据写入/查询。
- 数据质量检查，覆盖缺失、重复、时间顺序、异常 OHLC、停牌提示等。
- 纯 Python 技术指标：SMA、EMA、MACD、KDJ、RSI、BOLL、ATR、OBV。
- MVP 选股策略：均线多头 + 放量突破。
- 买卖点解释：入场、加仓、减仓、止损、止盈、信号失效条件。
- A 股约束回测：T+1、涨跌停、停牌、手续费、滑点。
- 中文 Markdown 绩效报告和自包含静态 HTML Dashboard。
- 多因子评分、轻量 ML 评分和组合权重研究脚手架。
- 可恢复的全 A 股市场扫描，批量拉取日线、回测并生成轻量汇总。
- GitHub 高星项目调研，并蒸馏为项目内 reusable skills。

## 安装

建议使用 Python 3.11 或 3.12。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

如果需要从 AKShare 拉取真实行情，再安装数据相关依赖：

```bash
python -m pip install -e ".[data]"
```

也可以一次安装研究、回测和报告相关可选依赖：

```bash
python -m pip install -e ".[data,analysis,backtest,report,dev]"
```

## 基础验证

```bash
PYTHONPATH=src python -m compileall -q src tests
PYTHONPATH=src python -m unittest discover -s tests
PYTHONPATH=src python -m gupiao.cli --version
```

当前版本：

```bash
0.1.0
```

## 命令行使用方法

以下命令都可以用 `PYTHONPATH=src python -m gupiao.cli ...` 运行；安装为 editable 包之后，也可以直接使用 `gupiao ...`。

### 查看 A 股股票列表

需要先安装 `akshare`：

```bash
PYTHONPATH=src python -m gupiao.cli data instruments --limit 10
```

输出格式为 JSON Lines，每一行是一只股票，便于后续脚本继续处理。

### 获取单只股票日线

```bash
PYTHONPATH=src python -m gupiao.cli data daily 000001 --start 2026-01-01 --end 2026-06-10 --adjust hfq --limit 5
```

`--adjust` 可选：

- `hfq`：后复权，默认值。
- `qfq`：前复权。
- `raw`：不复权。

保存为本地 JSONL 样例：

```bash
PYTHONPATH=src python -m gupiao.cli data daily 000001 --start 2026-01-01 --end 2026-06-10 --adjust hfq > data/000001_daily.jsonl
```

### 拉取日线并写入 SQLite

```bash
PYTHONPATH=src python -m gupiao.cli data update-daily 000001 --start 2026-01-01 --end 2026-06-10 --adjust hfq --db data/gupiao.sqlite
```

命令会输出写入的数据库路径、股票代码和写入行数。

### 运行 MVP 选股策略

选股输入为日线 JSONL 文件：

```bash
PYTHONPATH=src python -m gupiao.cli screen breakout --bars data/000001_daily.jsonl --symbol 000001
```

常用参数：

```bash
--short-window 5
--medium-window 20
--long-window 60
--volume-window 20
--breakout-window 20
--min-volume-ratio 1.5
```

### 生成买卖点解释

```bash
PYTHONPATH=src python -m gupiao.cli signal breakout --bars data/000001_daily.jsonl --symbol 000001
```

可调信号参数：

```bash
--atr-window 14
--stop-atr-multiple 2.0
--take-profit-r-multiple 2.0
```

### 运行回测

```bash
PYTHONPATH=src python -m gupiao.cli backtest breakout --bars data/000001_daily.jsonl --symbol 000001
```

可调回测参数：

```bash
--initial-cash 100000
--commission-rate 0.0003
--slippage-rate 0.0005
--max-holding-bars 20
```

回测默认包含 A 股常见交易约束：T+1、涨停不可买、跌停不可卖、零成交量停牌不可成交。

### 生成中文 Markdown 报告

```bash
PYTHONPATH=src python -m gupiao.cli report breakout --bars data/000001_daily.jsonl --symbol 000001 --output reports/generated/000001_breakout.md
```

报告内容包括候选股、买卖点计划、回测指标、交易明细、风险提示和回测假设。

### 运行全 A 股市场扫描

需要先安装 `akshare`：

```bash
python -m pip install -e ".[data]"
```

默认扫描区间为 `2023-06-10` 至 `2026-06-10`，复权方式为 `hfq`。完整扫描命令：

```bash
PYTHONPATH=src python -m gupiao.cli scan market \
  --start 2023-06-10 \
  --end 2026-06-10 \
  --adjust hfq \
  --db data/cache/market_scan.sqlite \
  --output reports/generated/market_scan/latest \
  --public-summary reports/summaries/latest_market_scan.md \
  --top 30
```

先做 3 只股票 smoke test：

```bash
PYTHONPATH=src python -m gupiao.cli scan market --limit 3 --retry-sleep 0 --public-summary reports/summaries/smoke_market_scan.md
```

产物规则：

- `data/cache/market_scan.sqlite`：本地行情缓存和可恢复扫描状态，不提交。
- `reports/generated/market_scan/latest/`：本地完整逐股结果和失败明细，不提交。
- `reports/summaries/latest_market_scan.md`：轻量公开汇总，可提交到 GitHub。

## 推荐工作流

1. 安装开发依赖和数据依赖。
2. 用 `data instruments` 查看股票基础列表。
3. 用 `data daily` 保存单只股票日线 JSONL。
4. 用 `screen breakout` 产生候选股。
5. 用 `signal breakout` 解释买卖点。
6. 用 `backtest breakout` 验证策略表现。
7. 用 `report breakout` 生成中文研究报告。
8. 用 `scan market` 批量扫描全 A 股，并提交小型汇总。
9. 扩展策略、指标、因子或报告模板，并补充测试。

## 项目文档

- `docs/PROJECT_PLAN.md`：项目总规划。
- `docs/PROJECT_MEMORY.md`：项目记忆、当前状态和关键决策。
- `docs/PROJECT_TASKS.md`：自动推进任务清单与完成状态。
- `docs/AUTOMATION_RUNBOOK.md`：自动推进规则和 GitHub 更新规则。
- `docs/DEVELOPMENT.md`：开发、测试、格式化、类型检查和打包命令。
- `docs/research/01_github_search_checklist.md`：GitHub 搜索清单。
- `docs/research/02_github_project_registry.md`：调研项目登记表。
- `docs/research/03_skill_distillation_plan.md`：skill 蒸馏计划。
- `docs/research/04_p0_reference_notes.md`：P0 参考项目深读笔记。

## 项目 Skills

已根据 AKShare、myhhub/stock、TA-Lib Python、backtesting.py、QuantStats 等高星/高相关项目蒸馏出以下项目内 skills：

- `skills/stock-data-ingestion`
- `skills/stock-screening-strategies`
- `skills/technical-signal-buy-sell`
- `skills/backtest-validation`
- `skills/performance-risk-reporting`

## GitHub 同步状态

项目会优先保证本地任务推进和本地提交。若 GitHub 凭据或网络暂不可用，远端推送会记录为 `push_pending`，不会阻塞后续开发。

当前已知情况：

- 本地任务已完成并提交。
- GitHub 推送需要可用的 SSH key 或 HTTPS 权限。
- 网络临时失败时可以重试；权限失败需要先恢复凭据。

## 风险提示

本项目输出的候选股、买卖点、回测和报告仅用于量化研究辅助。任何策略都可能受到未来函数、幸存者偏差、参数过拟合、流动性、交易成本、停牌、涨跌停和市场环境变化影响。请不要把本项目输出直接视为买卖建议。
