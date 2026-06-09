# P0 参考项目深读笔记

调研时间：2026-06-10 02:35 CST

本文件对应任务 `P0-03`，目标是把 P0 参考项目的 README、docs、examples、license 信息转化为后续实现可直接使用的 references。

## 总览

| 项目 | MVP 角色 | 许可证 | 主要参考内容 | 本项目采用方式 |
|---|---|---|---|---|
| AKShare | A 股数据主入口 | MIT | 股票列表、历史行情、财务指标、资金流、数据风险声明 | 封装为 `DataProvider`，做字段标准化、缓存、质量检查 |
| myhhub/stock | 完整股票系统参考 | Apache-2.0 | 批处理作业、指标/形态/策略/回测/Web 展示流程 | 参考作业编排和模块边界，不接入真实交易 |
| TA-Lib Python | 技术指标与 K 线形态 | BSD-2-Clause | Function API、Abstract API、指标分组、安装约束 | 指标层优先适配，安装失败时用 `ta`/pandas 兜底 |
| backtesting.py | MVP 单策略回测 | AGPL-3.0 | `Strategy.init()` / `next()`、OHLC 输入、指标包装、优化、结果统计 | 先用于本地研究；分发前评估 AGPL 义务 |
| QuantStats | 绩效指标与 HTML 报告 | Apache-2.0 | `stats` / `plots` / `reports` 三模块、tearsheet、Monte Carlo | 报告层输出收益、回撤、风险指标和 HTML 报告 |

## AKShare

来源：

- GitHub：https://github.com/akfamily/akshare
- 股票数据字典：https://akshare.akfamily.xyz/data/stock/stock.html
- 快速入门：https://akshare.akfamily.xyz/tutorial.html
- License：MIT

深读要点：

- README 标明 AKShare 需要 Python 3.9+，目标是简化金融数据获取，示例直接使用 `ak.stock_zh_a_hist(...)` 获取 A 股日线。
- 官方股票数据字典覆盖 A 股、港股、美股、财务指标、资金流、股票列表、技术指标等大量接口。
- `stock_info_a_code_name` 可一次获取沪深京 A 股代码和简称，适合作为 `instruments` MVP 起点。
- `stock_zh_a_hist` 提供沪深京 A 股日频历史行情，返回日期、股票代码、开高低收、成交量、成交额、振幅、涨跌幅、换手率等字段。
- 官方文档明确提示复权选择会影响研究用途，并说明量化研究中常采用后复权数据。
- `stock_individual_fund_flow` 可获取指定市场和股票近约 100 个交易日资金流数据。
- `stock_financial_analysis_indicator` 可按股票和起始年份获取财务指标历史数据。
- README 声明数据仅用于学术研究/参考，不构成投资建议，且部分接口可能因不可控因素移除。

落地建议：

- 第一版数据层建立 `AkshareProvider`，只暴露项目需要的稳定方法：`list_instruments()`、`fetch_daily_bars()`、`fetch_fundamentals()`、`fetch_money_flow()`。
- 所有 AKShare 中文字段在 provider 边界转换为内部英文 schema，例如 `日期 -> trade_date`、`开盘 -> open`、`成交量 -> volume`。
- 保存原始字段快照或 provider metadata，避免后续接口字段变动时难以追溯。
- 单元测试使用固定 CSV/Parquet fixture，不依赖实时网络；集成测试再访问 AKShare。
- 日线默认同时记录 `adjust` 参数，MVP 可优先使用 `hfq` 做收益研究，并保留 `raw/qfq/hfq` 扩展位。

## myhhub/stock

来源：

- GitHub：https://github.com/myhhub/stock
- Docker 镜像：https://hub.docker.com/r/mayanghua/instock
- License：Apache-2.0

深读要点：

- README 描述 InStock 能抓取股票/ETF 每日关键数据，计算技术指标、筹码分布，识别 K 线形态，综合选股，内置多种选股策略，支持选股验证回测、自动交易、批量任务和 Web 展示。
- 功能模块覆盖综合选股、指标、形态、策略、回测、关注、代理/Cookie、数据库存储、Web 展示、日志调试。
- 批处理示例区分整体作业和单功能作业，例如基础数据、指标、K 线形态、策略、回测等每日作业。
- README 提到数据库设计可保存历史数据并支持扩展分析，Web 展示通过配置视图字典扩展业务表单。
- 项目包含自动交易功能，但其 README 也提示股市有风险，本系统仅用于学习、股票分析，投资盈亏概不负责。

落地建议：

- 借鉴它的“每日作业”拆分：数据更新、指标计算、策略筛选、回测刷新、报告生成应是独立 CLI 命令。
- 借鉴日志边界：数据抓取、分析作业、Web 服务分别记录运行日志。
- 不在本项目 MVP 接入自动交易；若未来探索，也必须作为独立模拟/沙盒模块，默认关闭。
- Web Dashboard 初版可参考“配置驱动表格/视图”的思路，但先保持轻量，不复制大型系统结构。
- 由于本项目计划使用 SQLite/DuckDB/Parquet，暂不引入 InStock 的 MySQL 部署复杂度。

## TA-Lib Python

来源：

- GitHub：https://github.com/TA-Lib/ta-lib-python
- 上游 TA-Lib：https://ta-lib.org/
- License：BSD-2-Clause

深读要点：

- README 说明该项目是 TA-Lib 的 Python wrapper，基于 Cython 而不是 SWIG，并支持 Pandas/Polars。
- 上游 TA-Lib 包含 150+ 指标，覆盖 MACD、RSI、Stochastic、Bollinger Bands 和 K 线形态识别等。
- 安装可通过 `python -m pip install TA-Lib` 或 conda，但底层 TA-Lib C 库/二进制 wheel 是关键约束。
- README 明确 Function API 支持 `numpy.ndarray`、`pandas.Series`、`polars.Series` 输入，典型示例包括 `SMA`、`BBANDS`、`MOM`。
- Abstract API 接收 OHLCV 命名输入或 DataFrame，适合把内部行情 schema 直接传给指标函数。
- README 提醒 TA-Lib 对 NaN 的传播行为与 pandas rolling 结果不同，这会影响指标起始区间和数据质量检查。

落地建议：

- 指标层定义统一接口，优先用 TA-Lib 实现；如果安装失败，用 `ta` 或 pandas/numpy fallback。
- 所有指标输出都要保留 lookback 产生的 NaN，并在策略层显式过滤可用区间。
- K 线形态识别放在独立模块，避免与基础指标计算耦合。
- CI 环境先不强制依赖 TA-Lib C 库，等工程骨架稳定后再加入可选 extras。

## backtesting.py

来源：

- GitHub：https://github.com/kernc/backtesting.py
- Quick Start：https://kernc.github.io/backtesting.py/doc/examples/Quick%20Start%20User%20Guide.html
- API 文档：https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html
- License：AGPL-3.0

深读要点：

- README 示例使用 `Backtest`、`Strategy` 和 `crossover` 实现均线交叉策略，`bt.run()` 返回收益、回撤、胜率、交易次数等统计，`bt.plot()` 可视化。
- 官方 Quick Start 说明输入数据是带 `Open`、`High`、`Low`、`Close` 和可选 `Volume` 列的 pandas DataFrame。
- Quick Start 明确 backtesting.py 不负责选股或多资产组合再平衡，更适合单个可交易标的的进出场信号优化与可视化。
- `Strategy.init()` 用于向量化预计算指标，`Strategy.next()` 逐根 K 线模拟信息逐步可得。
- 文档说明默认无法在一根 K 线内部做交易决策，新订单通常下一根 K 线开盘成交，或使用 `trade_on_close=True`。
- 优化示例使用 `Backtest.optimize()`，同时提醒真实优化要防过拟合。

落地建议：

- 本项目 MVP 回测先使用单标的策略验证，然后再做“选股结果 -> 多只股票逐一回测 -> 汇总”的批处理。
- 内部数据进入 backtesting.py 前做列名映射：`open/high/low/close/volume -> Open/High/Low/Close/Volume`。
- A 股 T+1、涨跌停、停牌等限制不是 backtesting.py 默认模型，需要在 broker 假设或自定义约束层补充。
- AGPL-3.0 对分发和网络服务场景有强约束；在项目早期可用于本地研究，但 Web/API 分发前要评估替代方案或隔离边界。

## QuantStats

来源：

- GitHub：https://github.com/ranaroussi/quantstats
- Docs 目录：https://github.com/ranaroussi/quantstats/tree/main/docs
- License：Apache-2.0

深读要点：

- README 定位为给量化研究者和投资组合经理做组合画像，提供深入 analytics 和 risk metrics。
- README 将 QuantStats 分为三个主模块：`quantstats.stats` 计算绩效指标，`quantstats.plots` 可视化，`quantstats.reports` 生成指标报告和 HTML tear sheet。
- Quick Start 示例展示 `qs.extend_pandas()`、`qs.stats.sharpe(...)`、`qs.plots.snapshot(...)`。
- 报告功能包括 `qs.reports.metrics(...)`、`qs.reports.plots(...)`、`qs.reports.basic(...)`、`qs.reports.full(...)`、`qs.reports.html(...)`。
- 当前 README 要求 Python >= 3.10，并依赖 pandas、numpy、scipy、matplotlib、seaborn、tabulate、yfinance 等。
- README 还包含 Monte Carlo 风险分析能力，后期可用于报告增强。

落地建议：

- 回测层输出标准 returns Series，再交给报告层生成 metrics、plots 和 HTML。
- MVP 报告先输出基础中文 markdown/JSON，再可选调用 QuantStats 生成 HTML tear sheet。
- 对 A 股基准要替换默认美股 ticker 逻辑，使用本项目数据源提供的指数收益序列。
- Web Dashboard 初版只展示本项目生成的报告摘要，QuantStats HTML 可作为下载/详情页。

## 对后续任务的直接输入

`P0-04` 补充 skills references 时，应把本文件拆进 5 个 P0 skill：

- `stock-data-ingestion`：AKShare 数据接口、字段映射、复权、缓存、数据风险声明。
- `stock-screening-strategies`：myhhub/stock 的综合选股模块边界和批作业拆分。
- `technical-signal-buy-sell`：TA-Lib Function API / Abstract API、NaN/lookback 处理、K 线形态分层。
- `backtest-validation`：backtesting.py 的数据输入、Strategy 生命周期、成交时点、过拟合风险、AGPL 注意。
- `performance-risk-reporting`：QuantStats 的 stats/plots/reports、HTML tear sheet、A 股基准替换。

## 实现优先级建议

1. 先实现 AKShare provider 的股票列表和日线行情，确保 schema 稳定。
2. 再实现指标层接口，TA-Lib 作为 optional dependency。
3. 用 backtesting.py 跑通单标的策略回测，先不做复杂组合。
4. 输出标准 returns 和 trade log 后接入 QuantStats 报告。
5. 最后再借鉴 myhhub/stock 的批作业和 Web 展示结构，把单次研究流程扩成可重复任务。
