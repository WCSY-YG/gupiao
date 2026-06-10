# gupiao

A 股选股、买卖点分析、竞价数据增强与量化研究辅助工具。

`gupiao` 是一个面向 A 股的量化研究辅助项目，用来串起数据接入、指标计算、策略选股、买卖点解释、回测验证、中文报告和静态 Dashboard。项目只用于研究和决策支持，不构成投资建议，也不默认接入真实交易。

## 功能总览

### 数据接入与本地缓存

- A 股股票列表接入：通过 AKShare 获取股票代码、名称、市场和交易所信息。
- 单只股票日线接入：支持 `raw`、`qfq`、`hfq` 复权参数，输出 JSON Lines。
- 当日盘前竞价分钟数据接入：通过 AKShare 获取最近交易日 `09:15:00` 至 `09:25:00` 的盘前分钟数据。
- 本地日 K 缓存导入：支持 `cache/daily_k/market_data_cache/market_YYYY-MM-DD.csv` 导入 SQLite。
- 本地集合竞价缓存导入：支持 `cache/jingjia/*.rar` 流式解析，生成每日每股一条 `auction_profiles` 画像。
- SQLite 本地存储：支持 `instruments`、`bars_daily`、`auction_profiles` 建表、批量写入、增量覆盖和按日期查询。
- 可恢复数据作业：日 K 扫描和竞价导入都可以复用已写入缓存，避免重复拉取或重复解析。

### 数据质量与特征工程

- 股票基础信息校验：检查缺失字段、重复代码等问题。
- 日线数据校验：检查重复记录、时间顺序、OHLC 合法性、负成交量/成交额/换手率、零成交量停牌提示。
- 纯 Python 技术指标：SMA、EMA、MACD、KDJ、RSI、BOLL、ATR、OBV。
- 竞价画像特征：竞价缺口、竞价量比、竞价区间波动、委买委卖不平衡、0-100 竞价强度分。
- 竞价研究样本：可构建竞价特征与未来收益样本，用于样本外验证和轻量模型实验。

### 选股与买卖点

- MVP 选股策略：均线多头 + 放量突破，输出候选股、候选分、命中原因和关键指标。
- 竞价增强选股：策略可接收同日 `AuctionProfile`，用竞价强度、缺口、量比和委买委卖不平衡辅助排序或过滤。
- 竞价策略结论：最近验证显示 `min_auction_score=60` 硬过滤暂未稳定改善收益，当前建议优先软排序/解释，不默认强过滤。
- 买卖点解释：输出入场价、加仓价、减仓价、止损价、止盈价、信号失效条件、风险收益比和解释原因。
- CLI 选股/信号命令：支持从本地 JSONL 日线样本运行选股和买卖点解释。

### 回测与 A 股交易约束

- 单标的策略回测：复用选股策略和买卖点计划，输出收益、最大回撤、胜率、权益曲线和交易明细。
- 交易成本：支持初始资金、手续费、滑点、最长持有周期等参数。
- A 股约束：默认启用 T+1、涨停不可买、跌停不可卖、零成交量停牌不可成交。
- 历史竞价回测：可按 `symbol + trade_date` 注入 `AuctionProfile`，比较纯 K 线策略和竞价增强策略。
- 竞价增强对比实验：`research auction-compare` 可批量对比 baseline 与 auction-enhanced 两版回测，并生成小型汇总。

### 报告、Dashboard 与全市场扫描

- 中文 Markdown 绩效报告：覆盖候选股、买卖点计划、回测指标、交易明细、假设和风险提示。
- 静态 HTML Dashboard：自包含页面，包含 KPI、候选、买卖点、权益曲线 SVG、交易明细和风险提示。
- 可恢复全 A 股市场扫描：`scan market` 支持全市场逐股拉取/复用日 K、策略筛选、信号生成、回测和失败不中断。
- 扫描轻量汇总：完整逐股结果留在 `reports/generated/`，可提交小型 Markdown 汇总到 `reports/summaries/`。
- 竞价增强扫描：全市场扫描可通过 `--auction-provider local_jingjia` 使用本地竞价画像。

### 研究工具与策略迭代

- 多因子评分：支持价值、质量、成长、动量、波动率、流动性等因子的归一化和加权排名。
- 轻量 ML 基线：支持训练/验证切分、线性基线预测和样本外评分。
- 组合权重研究：支持按预测评分选 Top N，并做权重上限控制。
- 竞价增强近期验证：已用 `2026-01-01` 至 `2026-05-29` 日 K 和 `2026-05` 本地竞价画像完成一次 baseline vs auction 对比。
- 后续滚动验证：任务清单已规划 P6-06，对不同月份和竞价参数做滚动对比，形成更稳健的参数建议。

### 项目规划、skills 与自动化

- GitHub 高星项目调研：已参考 AKShare、myhhub/stock、TA-Lib Python、backtesting.py、QuantStats 等项目。
- 项目内 skills：沉淀数据接入、竞价数据、选股策略、买卖点、回测验证、绩效报告等可复用工作流。
- 自动推进任务清单：`docs/PROJECT_TASKS.md` 记录 `pending` / `in_progress` / `done` / `blocked` 状态。
- 项目记忆：`docs/PROJECT_MEMORY.md` 记录关键决策、数据导入结果、验证结论和后续路线。
- GitHub 同步策略：代码、文档和小型汇总提交；原始行情、SQLite、逐股结果和大文件不提交。

### CLI 命令总览

| 命令 | 功能 | 主要产物 |
|---|---|---|
| `data instruments` | 获取 A 股股票列表 | JSON Lines |
| `data daily` | 获取单只股票日线 | JSON Lines |
| `data pre-market` | 获取最近交易日盘前竞价分钟数据 | JSON Lines |
| `data update-daily` | 拉取日线并写入 SQLite | `bars_daily` |
| `data import-daily-cache` | 导入本地全市场日 K CSV | `bars_daily` |
| `data import-auction-cache` | 导入本地集合竞价 RAR | `auction_profiles` |
| `screen breakout` | 运行 MVP 选股策略 | JSON |
| `signal breakout` | 生成买卖点解释 | JSON |
| `backtest breakout` | 运行单标的回测 | JSON |
| `report breakout` | 生成中文 Markdown 报告 | Markdown |
| `scan market` | 运行可恢复全市场扫描 | JSONL + Markdown 汇总 |
| `research auction-compare` | 对比纯 K 线和竞价增强策略 | JSONL + Markdown 汇总 |

### 目前不做的事情

- 不提供真实交易、券商下单或自动交易。
- 不把候选股、买卖点、回测收益解释为投资建议。
- 不提交原始行情、SQLite、RAR、逐股 JSONL/CSV 或大体积生成目录。

## 安装

建议使用 Python 3.11 或 3.12。后续所有 Python 命令默认使用 conda 的 `agent` 环境。

```bash
conda run -n agent python -m pip install -U pip
conda run -n agent python -m pip install -e ".[dev]"
```

如果需要从 AKShare 拉取真实行情，再安装数据相关依赖：

```bash
conda run -n agent python -m pip install -e ".[data]"
```

也可以一次安装研究、回测和报告相关可选依赖：

```bash
conda run -n agent python -m pip install -e ".[data,analysis,backtest,report,dev]"
```

## 基础验证

```bash
conda run -n agent python -m compileall -q src tests
conda run -n agent env PYTHONPATH=src python -m unittest discover -s tests
conda run -n agent env PYTHONPATH=src python -m gupiao.cli --version
```

当前版本：

```bash
0.2.0
```

## 命令行使用方法

以下命令都可以用 `conda run -n agent env PYTHONPATH=src python -m gupiao.cli ...` 运行；安装为 editable 包之后，也可以直接使用 `gupiao ...`。

### 查看 A 股股票列表

需要先安装 `akshare`：

```bash
conda run -n agent env PYTHONPATH=src python -m gupiao.cli data instruments --limit 10
```

输出格式为 JSON Lines，每一行是一只股票，便于后续脚本继续处理。

### 获取单只股票日线

```bash
conda run -n agent env PYTHONPATH=src python -m gupiao.cli data daily 000001 --start 2026-01-01 --end 2026-06-10 --adjust hfq --limit 5
```

`--adjust` 可选：

- `hfq`：后复权，默认值。
- `qfq`：前复权。
- `raw`：不复权。

保存为本地 JSONL 样例：

```bash
conda run -n agent env PYTHONPATH=src python -m gupiao.cli data daily 000001 --start 2026-01-01 --end 2026-06-10 --adjust hfq > data/000001_daily.jsonl
```

### 获取当日盘前竞价分钟数据

AKShare 的 `stock_zh_a_hist_pre_min_em` 当前返回最近一个交易日的盘前分钟数据，可用于生成竞价画像：

```bash
conda run -n agent env PYTHONPATH=src python -m gupiao.cli data pre-market 000001 --start-time 09:15:00 --end-time 09:25:00
```

后续历史竞价回测应优先从本地 `cache/jingjia/` 或专门竞价表导入历史快照，再按交易日注入回测。

### 拉取日线并写入 SQLite

```bash
conda run -n agent env PYTHONPATH=src python -m gupiao.cli data update-daily 000001 --start 2026-01-01 --end 2026-06-10 --adjust hfq --db data/gupiao.sqlite
```

命令会输出写入的数据库路径、股票代码和写入行数。

### 运行 MVP 选股策略

选股输入为日线 JSONL 文件：

```bash
conda run -n agent env PYTHONPATH=src python -m gupiao.cli screen breakout --bars data/000001_daily.jsonl --symbol 000001
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
conda run -n agent env PYTHONPATH=src python -m gupiao.cli signal breakout --bars data/000001_daily.jsonl --symbol 000001
```

可调信号参数：

```bash
--atr-window 14
--stop-atr-multiple 2.0
--take-profit-r-multiple 2.0
```

### 运行回测

```bash
conda run -n agent env PYTHONPATH=src python -m gupiao.cli backtest breakout --bars data/000001_daily.jsonl --symbol 000001
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
conda run -n agent env PYTHONPATH=src python -m gupiao.cli report breakout --bars data/000001_daily.jsonl --symbol 000001 --output reports/generated/000001_breakout.md
```

报告内容包括候选股、买卖点计划、回测指标、交易明细、风险提示和回测假设。

### 导入本地日 K 缓存

如果已有按交易日拆分的全市场日 K CSV，例如 `cache/daily_k/market_data_cache/market_YYYY-MM-DD.csv`，可以先导入 SQLite，减少 AKShare 远端断连影响：

```bash
conda run -n agent env PYTHONPATH=src python -m gupiao.cli data import-daily-cache \
  --source cache/daily_k/market_data_cache \
  --db data/cache/market_scan.sqlite \
  --start 2023-06-10 \
  --end 2026-04-23 \
  --adjust hfq \
  --conflict ignore
```

建议先 dry-run 统计可导入规模：

```bash
conda run -n agent env PYTHONPATH=src python -m gupiao.cli data import-daily-cache \
  --source cache/daily_k/market_data_cache \
  --start 2023-06-10 \
  --end 2026-04-23 \
  --dry-run
```

导入规则：

- 默认 `--conflict ignore`，已有 AKShare 行不会被本地 CSV 覆盖。
- 新格式 CSV 使用真实 `成交量`；老格式缺少成交量时用 `amount / close` 估算，并把 provider 标记为 `local_daily_k_estimated_volume`。
- 本地日 K 当前覆盖到 `2026-04-23`；若扫描结束日晚于缓存最新日，系统不会把半截缓存误当完整数据。

### 导入本地集合竞价缓存

`cache/jingjia/*.rar` 是按月份打包的集合竞价快照。导入器会用 `unrar` 流式读取压缩包，把 `09:15:00` 至 `09:25:03` 的快照压成每只股票每天一条 `auction_profiles` 画像，写入 `data/cache/market_scan.sqlite`。

建议先 dry-run 看规模：

```bash
conda run -n agent env PYTHONPATH=src python -m gupiao.cli data import-auction-cache \
  --source cache/jingjia \
  --db data/cache/market_scan.sqlite \
  --start 2024-01-01 \
  --end 2026-05-31 \
  --dry-run
```

确认后再导入：

```bash
conda run -n agent env PYTHONPATH=src python -m gupiao.cli data import-auction-cache \
  --source cache/jingjia \
  --db data/cache/market_scan.sqlite \
  --start 2024-01-01 \
  --end 2026-05-31 \
  --provider local_jingjia \
  --conflict ignore
```

导入规则：

- 默认只保存竞价画像，不提交原始 RAR、SQLite 或完整逐股结果。
- `total_volume_trade` 按竞价快照口径视为手数，导入时转换为股数。
- 画像字段包括竞价价格、缺口、区间波动、竞价量比、委买委卖不平衡和竞价强度分。
- `--conflict ignore` 保留已有画像；需要重算竞价特征时可改用 `--conflict replace`。

### 运行全 A 股市场扫描

需要先安装 `akshare`：

```bash
conda run -n agent python -m pip install -e ".[data]"
```

默认扫描区间为 `2023-06-10` 至 `2026-06-10`，复权方式为 `hfq`。完整扫描命令：

```bash
conda run -n agent env PYTHONPATH=src python -m gupiao.cli scan market \
  --start 2023-06-10 \
  --end 2026-06-10 \
  --adjust hfq \
  --db data/cache/market_scan.sqlite \
  --output reports/generated/market_scan/latest \
  --public-summary reports/summaries/latest_market_scan.md \
  --top 30 \
  --request-sleep 2.0 \
  --retry-sleep 3 \
  --request-timeout 60
```

若已经导入本地竞价画像，可以让扫描和回测使用同日竞价表现：

```bash
conda run -n agent env PYTHONPATH=src python -m gupiao.cli scan market \
  --start 2024-01-01 \
  --end 2026-05-31 \
  --adjust hfq \
  --db data/cache/market_scan.sqlite \
  --output reports/generated/market_scan/latest \
  --public-summary reports/summaries/latest_market_scan.md \
  --top 30 \
  --auction-provider local_jingjia \
  --min-auction-score 60 \
  --auction-score-weight 0.15 \
  --request-sleep 2.0 \
  --retry-sleep 3 \
  --request-timeout 60
```

先做 3 只股票 smoke test：

```bash
conda run -n agent env PYTHONPATH=src python -m gupiao.cli scan market --limit 3 --retry-sleep 0 --request-sleep 0.1 --request-timeout 30 --public-summary reports/summaries/smoke_market_scan.md
```

产物规则：

- `data/cache/market_scan.sqlite`：本地行情缓存和可恢复扫描状态，不提交。
- `reports/generated/market_scan/latest/`：本地完整逐股结果和失败明细，不提交。
- `reports/summaries/latest_market_scan.md`：轻量公开汇总，可提交到 GitHub。
- `--request-sleep`：每次真实行情请求后的节流秒数，缓存命中不会等待；接口断连较多时可调大。
- `--retry-sleep`：失败重试之间的线性退避基准秒数。
- `--request-timeout`：单只股票单次行情请求超时秒数，防止 AKShare 或远端连接长时间挂起。
- `--auction-provider`：启用 SQLite 中对应 provider 的竞价画像，例如 `local_jingjia`。
- `--min-auction-score`：要求候选日存在竞价画像且竞价强度不低于阈值。
- `--auction-score-weight`：候选排序分中竞价分的混合权重。

### 对比竞价增强策略表现

导入本地竞价画像后，可以用同一批股票、同一区间对比“纯 K 线均线放量突破”和“竞价增强版本”：

```bash
conda run -n agent env PYTHONPATH=src python -m gupiao.cli research auction-compare \
  --start 2026-01-01 \
  --end 2026-05-29 \
  --db data/cache/market_scan.sqlite \
  --auction-provider local_jingjia \
  --output reports/generated/auction_validation/latest \
  --public-summary reports/summaries/latest_auction_validation.md \
  --top 30 \
  --min-auction-score 60 \
  --auction-score-weight 0.15
```

产物规则：

- `reports/generated/auction_validation/latest/`：逐股完整对比结果，不提交。
- `reports/summaries/latest_auction_validation.md`：可提交的小型汇总，用来记录本轮 skill 迭代证据。
- 若汇总显示竞价硬过滤没有稳定改善，应先把竞价作为排序和解释辅助，而不是直接提升为默认强过滤。

## 推荐工作流

1. 安装开发依赖和数据依赖。
2. 用 `data instruments` 查看股票基础列表。
3. 用 `data daily` 保存单只股票日线 JSONL。
4. 用 `screen breakout` 产生候选股。
5. 用 `signal breakout` 解释买卖点。
6. 用 `backtest breakout` 验证策略表现。
7. 用 `report breakout` 生成中文研究报告。
8. 用 `data import-daily-cache` 和 `data import-auction-cache` 整合本地缓存。
9. 用 `scan market` 批量扫描全 A 股，并提交小型汇总。
10. 用 `research auction-compare` 对比竞价增强策略并更新 skill 阈值建议。
11. 扩展策略、指标、因子或报告模板，并补充测试。

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
- `skills/auction-data-integration`
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
