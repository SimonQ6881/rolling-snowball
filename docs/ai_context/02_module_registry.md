---
doc_id: zijin-daily-module-registry
title: 紫金矿业日报模块登记册（历史模块）
doc_type: module_registry
project: rolling-snowball
generated_on: 2026-07-07
last_verified_on: 2026-07-07
maintainer_owner: 待补充
status: legacy
keywords:
  - 模块登记册
  - 输入输出
  - 核心函数
  - 异常处理
  - 元数据标签
---

# 紫金矿业日报模块登记册

> 说明：本文档描述的是仓库中的历史“紫金日报”模块，不属于当前 rolling-snowball 控制台主线。

## 1. 元数据规范

每个模块使用统一元数据字段，便于 AI 检索与记忆：

| 字段 | 含义 |
| --- | --- |
| `module_id` | 唯一模块标识，建议使用相对路径 |
| `business_domain` | 所属业务域 |
| `keywords` | 功能关键词 |
| `tech_stack` | 技术栈标签 |
| `entrypoints` | 对外暴露的关键函数/入口 |
| `upstream_inputs` | 上游数据来源 |
| `downstream_outputs` | 下游输出位置 |
| `exceptions` | 异常处理规则 |
| `tests` | 对应测试文件 |
| `owner` | 当前维护责任人，未知则为 `待补充` |

## 2. 模块总表

| 模块 | 业务域 | 功能关键词 | 状态 | 责任人 |
| --- | --- | --- | --- | --- |
| `src/zijin_daily_report.py` | 日报编排/渲染 | 日报生成、Tushare、HTML、调度入口 | active | 待补充 |
| `src/pipeline_ops.py` | 运维调度 | 交易日、归档、完整性校验 | active | 待补充 |
| `src/report_extra.py` | 外部采集 | FRED、美债、央行政策、WGC、缓存 | active | 待补充 |
| `src/report_server.py` | 服务发布 | HTTP 服务、刷新、健康检查 | active | 待补充 |
| `src/translation_service.py` | 翻译 | OpenAI 兼容翻译、术语表、缓存、告警 | active | 待补充 |
| `src/research_tracker.py` | 研究追踪 | 主题分类、可信度、增量更新 | active | 待补充 |
| `src/commodity_insights.py` | 商品分析 | 金铜锂、价格、供给、营收、预测 | active | 待补充 |
| `src/central_bank_insights.py` | 央行购金 | WGC 纠偏、国家维度、购金趋势 | active | 待补充 |
| `src/international_mining_db.py` | 国际矿企 | 产量标准化、SQLite、专题分析 | active | 待补充 |
| `scripts/run_daily_report.sh` | 运行脚本 | 加载环境、启动日报 | active | 待补充 |
| `scripts/run_report_server.sh` | 运行脚本 | 启动本地报告服务 | active | 待补充 |
| `scripts/run_test_suite.sh` | 测试脚本 | unittest 全量执行 | active | 待补充 |
| `scripts/run_stability_test.sh` | 运维脚本 | 稳定性测试、循环执行 | active | 待补充 |
| `scripts/run_international_mining_pipeline.sh` | 数据脚本 | 国际矿企流水线 | active | 待补充 |

## 3. 核心模块标准化记录

### 3.1 `src/zijin_daily_report.py`

```yaml
module_id: src/zijin_daily_report.py
business_domain: report_orchestration
keywords: [日报生成, 数据采集编排, HTML渲染, Tushare, 调度入口, 美元代理, 国际矿企]
tech_stack: [Python, pandas, tushare, dataclass, HTML]
entrypoints: [load_config, collect_report_data, render_html_report, build_report, save_report, main]
upstream_inputs: [config/portfolio.json, Tushare接口, data/cache/*, 外部抓取模块输出]
downstream_outputs: [reports/YYYY/MM/zijin_daily_YYYYMMDD.html, data/archive/YYYY/MM/DD/*]
tests: [tests/test_zijin_daily_report.py]
owner: 待补充
```

- 功能说明
  - 作为系统总入口，聚合配置、数据采集、分析计算、HTML 渲染和调度分支。
  - 定义 `ReportData` 数据对象，作为全局结构化中间层。
  - 负责金、铜、锂、美元与美债、国际矿企、多资产图表等业务块的最终拼装。
- 输入
  - `config/portfolio.json`
  - Tushare 行情/财务/公告/研报/交易日历
  - `report_extra.py` 返回的 FRED、美债、政策、WGC 条目
  - `data/cache` 中的翻译、供给、研究、美元代理缓存
- 输出
  - HTML 日报
  - `ReportData` 用于归档
  - 调度状态信息 `QueryResult`
- 核心函数
  - `collect_report_data()`：采集编排中心
  - `render_html_report()`：页面总渲染器
  - `build_dollar_bond_analysis()`：美元与美债板块
  - `build_international_peer_analysis()`：国际矿企对标
  - `build_commodity_theme_analysis()`：金铜锂主题分析
  - `resolve_dollar_proxy_frame()`：美元代理主源/替代/缓存兜底
- 核心算法与规则
  - 使用 `ReportData` 隔离“采集”和“渲染”阶段。
  - 美元代理按 `FRED -> USDCNH -> 本地 CSV 缓存` 顺序兜底。
  - 相关性计算在 `compute_correlation()` 中先重命名列，避免 `merge` 同名列冲突。
  - 图表渲染采用纯 HTML/SVG 生成，不依赖前端框架。
- 异常处理
  - 缺失数据默认回退为空表或 `N/A`，保持日报可生成。
  - Tushare 接口通过 `TushareFetcher` 记录成功/失败状态。
  - `main()` 在无 `TUSHARE_TOKEN` 时直接退出。

### 3.2 `src/pipeline_ops.py`

```yaml
module_id: src/pipeline_ops.py
business_domain: scheduling_and_archive
keywords: [交易日判断, 归档, manifest, 数据完整性, 调度窗口]
tech_stack: [Python, pandas, json, dataclass-introspection]
entrypoints: [current_trade_date, archive_trading_snapshot, is_trading_day, should_run_hourly_update, should_archive_after_close]
upstream_inputs: [ReportData, 交易日历数据, 调度时间]
downstream_outputs: [data/archive/YYYY/MM/DD/*.json, *.manifest.json]
tests: [tests/test_pipeline_ops.py, tests/test_pipeline_integration.py]
owner: 待补充
```

- 功能说明
  - 为日报主流程提供调度判断和归档落盘能力。
- 输入输出
  - 输入：`datetime now`、交易日历 `calendar_df`、`ReportData`
  - 输出：归档 JSON 和 manifest
- 核心规则
  - 交易日内 `9-15` 点允许小时级更新。
  - 交易日 `16` 点后允许归档。
  - manifest 会检查记录主键缺失和重复，失败则拒绝写盘。
- 异常处理
  - 如果归档完整性不通过，`archive_trading_snapshot()` 抛出 `ValueError`。
  - 若交易日历缺失，则以工作日近似替代。

### 3.3 `src/report_extra.py`

```yaml
module_id: src/report_extra.py
business_domain: external_collection
keywords: [FRED, Treasury, RSS, WGC, SSL回退, 缓存去重, 宏观外部源]
tech_stack: [Python, pandas, urllib, xml, ssl, regex]
entrypoints: [fetch_fred_series, fetch_treasury_curve, fetch_fed_policy_events, fetch_boj_policy_events, fetch_boe_policy_events, fetch_goldhub_gold_purchase_entries, cache_json_records]
upstream_inputs: [公网HTTP接口, RSS/XML/HTML/CSV]
downstream_outputs: [DataFrame, 结构化列表, data/cache/*.json]
tests: [tests/test_report_extra.py]
owner: 待补充
```

- 功能说明
  - 负责系统中非 Tushare 外部源的抓取、轻清洗和缓存合并。
- 输入输出参数
  - `fetch_fred_series(series_id, label)` 输出标准行情 DataFrame。
  - `fetch_treasury_curve()` 输出动态双年份合并后的美债期限结构表。
  - `cache_json_records(path, records, key_fields)` 对记录做去重缓存。
- 核心算法
  - `open_url()` 在 SSL 证书验证失败时降级到未校验上下文重试。
  - `fetch_treasury_curve()` 抓取当前年和上一年，适配跨年。
  - RSS 和 WGC 条目会做文本清洗、日期标准化和标签分类。
- 异常处理
  - HTTP 失败向上抛出，由主流程决定是否降级。
  - 无表格/无数据时返回空 DataFrame。

### 3.4 `src/report_server.py`

```yaml
module_id: src/report_server.py
business_domain: serving_and_refresh
keywords: [本地服务, 最新日报, 刷新接口, 健康检查, HTTP]
tech_stack: [Python, http.server, subprocess, threading]
entrypoints: [run_refresh, ReportHandler, main]
upstream_inputs: [reports目录, scripts/run_daily_report.sh]
downstream_outputs: [HTTP响应, 最新HTML访问, 手动刷新]
tests: [tests/test_report_server.py]
owner: 待补充
```

- 功能说明
  - 作为本地预览层，提供 `/`、`/latest`、`/healthz` 和 `POST /api/refresh-report`。
- 输入输出
  - 输入：HTML 报告文件、刷新请求
  - 输出：文件内容或 JSON 响应
- 核心规则
  - 通过 `REFRESH_LOCK` 避免并发刷新。
  - 刷新逻辑内部调用 `bash scripts/run_daily_report.sh --force`。
  - 使用 `SummaryCardParser` 从 HTML 顶部卡片抽取摘要，直接用于接口回传。
- 异常处理
  - 刷新超时返回 `504`。
  - 已有刷新任务进行中时返回 `409`。
  - 非法路径经 `safe_local_path()` 拦截，防止目录穿越。

### 3.5 `src/translation_service.py`

```yaml
module_id: src/translation_service.py
business_domain: translation
keywords: [翻译, 术语表, OpenAI兼容接口, 缓存映射, 告警]
tech_stack: [Python, urllib, json, dataclass, sha1]
entrypoints: [TranslationConfig, translate_text, translate_entry_fields, translate_entries]
upstream_inputs: [英文标题摘要, .env, glossary]
downstream_outputs: [translated entries, data/cache/translations/*.json, data/alerts/*]
tests: [tests/test_translation_service.py]
owner: 待补充
```

- 功能说明
  - 对研究、政策和购金类条目做“原文清洗 -> 翻译 -> 术语校正 -> 缓存 -> 告警”。
- 输入输出
  - 输入：文本或记录列表、翻译配置、缓存路径
  - 输出：带 `*_zh`、`*_translation_status` 等字段的记录
- 核心规则
  - 中文占比高的文本直接视为原生文本，不调用外部翻译。
  - 生成 `record_key` 做缓存映射，避免重复调用。
  - 翻译后继续应用术语表，保证金融名词口径统一。
- 异常处理
  - 未启用翻译时返回 `skipped`。
  - 多次重试失败则保留原文并记录告警。

### 3.6 `src/research_tracker.py`

```yaml
module_id: src/research_tracker.py
business_domain: research_tracking
keywords: [研报分类, 主题打标, 可信度, 增量更新, 告警]
tech_stack: [Python, regex, json, dataclass]
entrypoints: [ThemeRule, classify_theme, filter_target_research, track_research_updates]
upstream_inputs: [翻译后的研报/资讯条目]
downstream_outputs: [主题化研究列表, research_updates_latest.json, research_tracking_state.json]
tests: [tests/test_research_tracker.py]
owner: 待补充
```

- 功能说明
  - 对研报与资讯做主题过滤、可信度分类和新增提醒。
- 输入输出
  - 输入：条目列表、状态文件路径、告警文件路径
  - 输出：带 `core_theme`、`credibility`、`record_id` 的记录和告警列表
- 核心规则
  - 预置三大主题：`贵金属`、`美元利率`、`央行购金`。
  - 来源可信度按机构映射表打高/中/观察标签。
  - `record_id` 由主题、日期、机构、标题拼接，供增量判断使用。
- 异常处理
  - 状态文件损坏时回退为空状态。
  - 非目标主题记录直接过滤掉，不进入日报主体。

### 3.7 `src/commodity_insights.py`

```yaml
module_id: src/commodity_insights.py
business_domain: commodity_analysis
keywords: [黄金, 铜, 锂, 价格分析, 供给规划, 营收结构, 收入预测]
tech_stack: [Python, pandas, regex, math]
entrypoints: [build_price_analysis, build_supply_plan_analysis, build_revenue_analysis, build_forecast_analysis]
upstream_inputs: [商品行情, commodity_supply_plans.json, 财务数据, 产量目标]
downstream_outputs: [价格主题分析结构, 供给分析结构, 营收结构结构, 预测结构]
tests: [tests/test_commodity_insights.py]
owner: 待补充
```

- 功能说明
  - 负责金、铜、锂三条核心商品业务线的价格、供给、营收和预测分析。
- 输入输出
  - 输入：价格序列 DataFrame、主营构成、利润表、供给事实库、管理层产量目标
  - 输出：多个用于 HTML 渲染的字典结构
- 核心算法
  - `build_price_analysis()` 按月均价生成归一化走势、拐点和事件标记。
  - `build_supply_plan_analysis()` 对国际矿企未来三年产量披露做覆盖率和缺口统计。
  - `build_revenue_analysis()` 从主营构成拆分黄金、铜、锂收入占比，并对锂收入做估算。
  - `build_forecast_analysis()` 在既有营收结构基础上推演未来区间。
- 异常处理
  - 缺少主营构成或利润表时返回“无法生成”说明而非报错。
  - 价格数据不完整时相应序列留空。

### 3.8 `src/central_bank_insights.py`

```yaml
module_id: src/central_bank_insights.py
business_domain: central_bank_gold
keywords: [央行购金, WGC, 月度纠偏, 国家分布, 黄金收益]
tech_stack: [Python, pandas, regex]
entrypoints: [build_central_bank_gold_analysis]
upstream_inputs: [WGC条目, 黄金价格序列]
downstream_outputs: [购金结构分析字典]
tests: [tests/test_central_bank_insights.py]
owner: 待补充
```

- 功能说明
  - 对世界黄金协会月度购金记录做结构化解释，补齐国家维度、同比趋势和中国央行连续购金状态。
- 输入输出
  - 输入：WGC 条目列表、黄金价格 DataFrame
  - 输出：摘要卡片、国家排名、月度趋势、价格联动观察
- 核心算法
  - `OFFICIAL_MONTH_OVERRIDES` 用于校正缓存或解析缺口。
  - 通过正则从原文句子中提取国家购金/售金吨数和 YTD 数据。
  - 将购金变化与黄金 20/60 日收益做联动分析。
- 异常处理
  - 若无法识别月份或数值，则保留原始条目但弱化结构化推断。

### 3.9 `src/international_mining_db.py`

```yaml
module_id: src/international_mining_db.py
business_domain: international_mining
keywords: [国际矿企, 产量标准化, 金铜锂, SQLite, 竞争格局, HHI, CR3]
tech_stack: [Python, pandas, sqlite3, dataclass, regex]
entrypoints: [parse_production_text, standardize_mining_records, build_analysis_markdown, write_sqlite_database, run_pipeline]
upstream_inputs: [data/cache/commodity_supply_plans.json]
downstream_outputs: [data/international_mining/*.csv, *.json, *.db, reports/international_mining/*.md]
tests: [tests/test_international_mining_db.py]
owner: 待补充
```

- 功能说明
  - 负责把国际矿企供给事实库转化为可分析、可查询、可复用的标准化数据库。
- 输入输出
  - 输入：原始矿企记录
  - 输出：标准化公司表、产量表、库存清单、SQLite 库、Markdown 报告
- 核心算法
  - `parse_production_text()` 识别金/铜/锂不同单位并统一到可比口径。
  - `standardize_mining_records()` 对记录去重、标准化、状态归类、规模分层。
  - `_competition_rows()` 计算竞争格局指标，如市场份额、CR3、HHI。
  - `write_sqlite_database()` 将标准化结果落到 SQLite。
- 异常处理
  - 无法识别单位时保留原文并标记为不可比。
  - 缺少关键字段的记录在清洗过程中会被过滤或降级。

## 4. 配置与脚本模块记录

### 4.1 `config/portfolio.json`

- 角色
  - 系统总配置文件，定义持仓、观察列表、外部缓存路径、宏观逻辑监控、商品事件、翻译配置。
- AI 检索关键词
  - `portfolio`, `watchlist`, `external_sources`, `focus_monitor`, `logic_monitor`
- 注意事项
  - 当前核心矿种口径以金、铜、锂为准。
  - 调整任何数据源路径或业务口径时，应先改此文件，再改代码。

### 4.2 脚本组

| 文件 | 功能说明 | 调用对象 | 输出 |
| --- | --- | --- | --- |
| `scripts/run_daily_report.sh` | 加载 `.env` 后执行日报主程序 | `src/zijin_daily_report.py` | HTML 日报 |
| `scripts/run_report_server.sh` | 启动本地报告服务 | `src/report_server.py` | `127.0.0.1:8765` |
| `scripts/run_test_suite.sh` | 运行全量 `unittest` | `tests/` | 测试结果 |
| `scripts/run_stability_test.sh` | 循环运行 scheduled 模式并记录日志 | 日报脚本 | `reports/testing/stability_*.log` |
| `scripts/run_international_mining_pipeline.sh` | 执行国际矿企标准化管道 | `src/international_mining_db.py` | DB/CSV/Markdown |

## 5. 测试映射

| 测试文件 | 覆盖对象 | 关注点 |
| --- | --- | --- |
| `tests/test_zijin_daily_report.py` | `zijin_daily_report.py` | 主流程、渲染、美元代理、相关性 |
| `tests/test_report_extra.py` | `report_extra.py` | SSL 回退、美债跨年抓取 |
| `tests/test_pipeline_ops.py` | `pipeline_ops.py` | 调度窗口、归档校验 |
| `tests/test_pipeline_integration.py` | 主流程与调度 | 集成链路 |
| `tests/test_report_server.py` | `report_server.py` | 服务接口与刷新行为 |
| `tests/test_translation_service.py` | `translation_service.py` | 翻译、缓存、术语 |
| `tests/test_research_tracker.py` | `research_tracker.py` | 主题分类、增量告警 |
| `tests/test_commodity_insights.py` | `commodity_insights.py` | 商品分析结构 |
| `tests/test_central_bank_insights.py` | `central_bank_insights.py` | 央行购金解析与汇总 |
| `tests/test_international_mining_db.py` | `international_mining_db.py` | 单位标准化、数据库输出 |

## 6. 跨模块关联索引

| 主题 | 核心模块 | 辅助模块 | 关键数据 |
| --- | --- | --- | --- |
| 日报生成 | `zijin_daily_report.py` | `pipeline_ops.py`, `report_server.py` | `reports/YYYY/MM/*.html` |
| 宏观外部源 | `report_extra.py` | `zijin_daily_report.py` | `data/cache/*.json`, `dollar_index_proxy.csv` |
| 翻译与研究 | `translation_service.py` | `research_tracker.py`, `zijin_daily_report.py` | `data/cache/translations/*`, `research_updates_latest.json` |
| 商品分析 | `commodity_insights.py` | `zijin_daily_report.py` | 行情、主营构成、供给事实库 |
| 央行购金 | `central_bank_insights.py` | `report_extra.py`, `zijin_daily_report.py` | `central_bank_gold.json` |
| 国际矿企 | `international_mining_db.py` | `commodity_insights.py`, `zijin_daily_report.py` | `commodity_supply_plans.json`, SQLite |

## 7. 维护建议

- 修改主流程前，先确认变更落在哪个模块，不要继续把所有逻辑堆回 `src/zijin_daily_report.py`。
- 涉及外部接口问题时，优先排查 `report_extra.py` 和缓存文件，再看渲染层。
- 涉及研究条目字段结构变化时，优先检查 `translation_service.py` 与 `research_tracker.py`。
- 涉及国际矿企事实口径变化时，先修 `commodity_supply_plans.json`，再重跑专题管道。
