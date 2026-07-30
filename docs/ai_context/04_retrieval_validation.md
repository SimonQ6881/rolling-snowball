---
doc_id: zijin-daily-retrieval-validation
title: 紫金矿业日报检索索引与有效性验证（历史模块）
doc_type: retrieval_validation
project: rolling-snowball
generated_on: 2026-07-07
last_verified_on: 2026-07-07
maintainer_owner: 待补充
status: legacy
keywords:
  - 关键词索引
  - 检索验证
  - 跨模块索引
  - AI召回
  - 文档有效性
---

# 紫金矿业日报检索索引与有效性验证

> 说明：本文档描述的是仓库中的历史“紫金日报”模块，不属于当前 rolling-snowball 控制台主线。

## 1. 检索目标

本文件用于验证以下目标是否满足：

1. AI 能通过模块名、业务名、函数名、数据文件名快速命中文档位置。
2. AI 能从单个关键词回溯到对应代码入口、上游输入和下游产物。
3. AI 能区分“主程序逻辑”“子模块逻辑”“运维调度”“数据事实库”。
4. 文档对核心业务逻辑的描述不存在明显歧义。

## 2. 全文检索关键词索引

### 2.1 按业务主题

| 主题 | 推荐关键词 | 主要命中文档 | 关联代码 |
| --- | --- | --- | --- |
| 日报主流程 | `日报生成` `collect_report_data` `render_html_report` `build_report` | `01_system_overview.md` `02_module_registry.md` | `src/zijin_daily_report.py` |
| 调度归档 | `交易日` `归档` `manifest` `should_run_hourly_update` | `01_system_overview.md` `03_operations_maintenance.md` | `src/pipeline_ops.py` |
| 美元与美债 | `美元代理` `FRED` `USDCNH` `Treasury` `build_dollar_bond_analysis` | `02_module_registry.md` | `src/zijin_daily_report.py` `src/report_extra.py` |
| 研报追踪 | `研报分类` `可信度` `track_research_updates` | `02_module_registry.md` | `src/research_tracker.py` |
| 翻译链路 | `翻译` `OpenAI兼容` `glossary` `translate_entries` | `02_module_registry.md` `03_operations_maintenance.md` | `src/translation_service.py` |
| 商品分析 | `黄金` `铜` `锂` `营收结构` `供给规划` `收入预测` | `02_module_registry.md` | `src/commodity_insights.py` |
| 央行购金 | `WGC` `央行购金` `OFFICIAL_MONTH_OVERRIDES` | `02_module_registry.md` | `src/central_bank_insights.py` |
| 国际矿企 | `国际矿企` `SQLite` `parse_production_text` `HHI` `CR3` | `01_system_overview.md` `02_module_registry.md` | `src/international_mining_db.py` |
| 本地服务 | `refresh-report` `healthz` `8765` `ReportHandler` | `03_operations_maintenance.md` | `src/report_server.py` |

### 2.2 按文件与产物

| 文件或目录 | 推荐关键词 |
| --- | --- |
| `config/portfolio.json` | `watchlist` `external_sources` `focus_monitor` `logic_monitor` |
| `data/cache/commodity_supply_plans.json` | `国际矿企事实库` `供给计划` `commodity_supply_plans` |
| `data/archive/YYYY/MM/DD/` | `trading_snapshot` `archive` `manifest` |
| `reports/YYYY/MM/` | `zijin_daily_YYYYMMDD` `HTML日报` |
| `data/cache/dollar_index_proxy.csv` | `美元代理缓存` `dollar_index_proxy` |
| `data/alerts/research_updates_latest.json` | `研报告警` `research_updates_latest` |

### 2.3 按函数名

| 函数 | 功能 | 所在文件 |
| --- | --- | --- |
| `collect_report_data` | 采集编排中心 | `src/zijin_daily_report.py` |
| `render_html_report` | HTML 总渲染 | `src/zijin_daily_report.py` |
| `resolve_dollar_proxy_frame` | 美元代理兜底 | `src/zijin_daily_report.py` |
| `archive_trading_snapshot` | 归档写盘 | `src/pipeline_ops.py` |
| `fetch_treasury_curve` | 美债曲线抓取 | `src/report_extra.py` |
| `translate_entries` | 批量翻译 | `src/translation_service.py` |
| `track_research_updates` | 研报增量提醒 | `src/research_tracker.py` |
| `build_price_analysis` | 金铜锂价格分析 | `src/commodity_insights.py` |
| `build_central_bank_gold_analysis` | 央行购金分析 | `src/central_bank_insights.py` |
| `standardize_mining_records` | 国际矿企标准化 | `src/international_mining_db.py` |

## 3. 跨模块关联索引

### 3.1 入口到产出

| 查询意图 | 建议先看 | 再看 | 产物 |
| --- | --- | --- | --- |
| “日报怎么生成？” | `src/zijin_daily_report.py` | `01_system_overview.md` | `reports/YYYY/MM/*.html` |
| “归档为什么失败？” | `src/pipeline_ops.py` | `03_operations_maintenance.md` | `data/archive/**/*.manifest.json` |
| “美元与美债数据从哪来？” | `src/report_extra.py` | `src/zijin_daily_report.py` | `dollar_index_proxy.csv` |
| “研报为什么没提醒？” | `src/research_tracker.py` | `src/translation_service.py` | `research_updates_latest.json` |
| “国际矿企板块怎么更新？” | `src/international_mining_db.py` | `data/cache/commodity_supply_plans.json` | `data/international_mining/*` |

### 3.2 数据流转索引

| 上游 | 中间层 | 下游 |
| --- | --- | --- |
| Tushare / 外部 HTTP 源 | `collect_report_data()` / `ReportData` | HTML 日报、归档快照 |
| 原文资讯 | `translate_entries()` | 译文缓存、研报分类 |
| 翻译后研报 | `filter_target_research()` | 研报卡片、增量提醒 |
| 商品价格与财务 | `commodity_insights.py` | 价格板块、营收结构板块 |
| WGC 条目 | `build_central_bank_gold_analysis()` | 央行购金板块 |
| 国际矿企事实库 | `standardize_mining_records()` | SQLite、专题报告、日报对标 |

## 4. 检索验证样例

### 4.1 建议验证命令

在项目根目录执行：

```bash
grep -Rni "collect_report_data" docs/ai_context
grep -Rni "美元代理" docs/ai_context
grep -Rni "国际矿企" docs/ai_context
grep -Rni "归档" docs/ai_context
grep -Rni "translate_entries" docs/ai_context
grep -Rni "research_updates_latest" docs/ai_context
```

### 4.2 期望结果

| 关键词 | 期望命中 |
| --- | --- |
| `collect_report_data` | `01_system_overview.md` `02_module_registry.md` |
| `美元代理` | `01_system_overview.md` `02_module_registry.md` `03_operations_maintenance.md` |
| `国际矿企` | 四份文档均应命中 |
| `归档` | `01_system_overview.md` `03_operations_maintenance.md` |
| `translate_entries` | `02_module_registry.md` `04_retrieval_validation.md` |
| `research_updates_latest` | `01_system_overview.md` `02_module_registry.md` `04_retrieval_validation.md` |

## 5. 文档有效性验证清单

| 验证项 | 方法 | 结果判定 |
| --- | --- | --- |
| 能否定位主入口 | 搜索 `zijin_daily_report.py` 或 `build_report` | 命中即通过 |
| 能否定位数据采集链 | 搜索 `collect_report_data`、`report_extra` | 命中即通过 |
| 能否定位调度链 | 搜索 `pipeline_ops`、`archive`、`launchd` | 命中即通过 |
| 能否定位翻译链 | 搜索 `translation_service`、`glossary` | 命中即通过 |
| 能否定位国际矿企链 | 搜索 `standardize_mining_records`、`SQLite` | 命中即通过 |
| 能否定位运维命令 | 搜索 `run_daily_report.sh`、`run_test_suite.sh` | 命中即通过 |

## 6. 本次文档验证结论

### 6.1 已覆盖的核心对象

- 代码文件：已覆盖全部 `src/*.py`、核心 `scripts/*.sh`、`launchd` 调度模板和主要测试文件。
- 配置文件：已覆盖 `config/portfolio.json` 和 `.env.example`。
- 数据链路：已覆盖缓存、归档、国际矿企事实库和 HTML 报告产物。
- 业务模块：已覆盖金、铜、锂、美元与美债、央行购金、国际矿企、研究追踪、翻译、归档、服务刷新。

### 6.2 当前已知限制

- 仓库当前不是 Git 仓库，因此无法生成基于提交历史的精确变更时间线。
- “维护责任人”字段缺少仓内权威来源，统一标记为 `待补充`。
- 文档中的“版本演进纪要”属于工程现状归纳，不等价于正式发布记录。

## 7. 后续维护规则

- 每次新增模块时，必须同步更新：
  - `01_system_overview.md` 的目录树和依赖图谱
  - `02_module_registry.md` 的模块记录
  - `04_retrieval_validation.md` 的关键词索引
- 每次核心业务口径变更时，必须同步更新：
  - 关键词索引
  - 数据域描述
  - 故障排查与维护建议
