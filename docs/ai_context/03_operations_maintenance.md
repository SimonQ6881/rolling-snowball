---
doc_id: zijin-daily-operations-maintenance
title: 紫金矿业日报部署与维护手册（历史模块）
doc_type: operations
project: rolling-snowball
generated_on: 2026-07-07
last_verified_on: 2026-07-07
maintainer_owner: 待补充
status: legacy
keywords:
  - 技术栈
  - 部署
  - 调度
  - 运维
  - 故障排查
  - 版本演进
---

# 紫金矿业日报部署与维护手册

> 说明：本文档描述的是仓库中的历史“紫金日报”模块，不属于当前 rolling-snowball 控制台主线。

## 1. 技术栈

### 1.1 核心运行栈

| 类别 | 内容 |
| --- | --- |
| 语言 | Python 3 |
| 数据处理 | `pandas` |
| 行情与财务数据 | `tushare` |
| 网络抓取 | `urllib.request` |
| 本地服务 | `http.server` |
| 数据库存储 | `sqlite3` |
| 测试框架 | `unittest` |
| 调度方式 | macOS `launchd` |
| 运行系统 | macOS |

### 1.2 第三方依赖

`requirements.txt` 当前只声明两项：

```text
tushare
pandas
```

说明：

- 其余能力尽量使用 Python 标准库实现，降低部署复杂度。
- 翻译链路不依赖 SDK，而是使用 OpenAI 兼容 HTTP 接口直接调用。

## 2. 环境要求

### 2.1 必要环境变量

`.env.example` 当前包含如下字段：

```bash
TUSHARE_TOKEN=your_tushare_token_here
TRANSLATION_ENABLED=false
TRANSLATION_API_BASE_URL=https://your-compliant-openai-compatible-endpoint/v1
TRANSLATION_API_KEY=your_translation_api_key
TRANSLATION_MODEL=gpt-4.1-mini
```

### 2.2 环境变量说明

| 变量 | 是否必需 | 说明 |
| --- | --- | --- |
| `TUSHARE_TOKEN` | 是 | 主程序启动硬性依赖，缺失会直接退出 |
| `TRANSLATION_ENABLED` | 否 | 是否启用翻译链路 |
| `TRANSLATION_API_BASE_URL` | 否 | OpenAI 兼容接口地址 |
| `TRANSLATION_API_KEY` | 否 | 翻译服务密钥 |
| `TRANSLATION_MODEL` | 否 | 翻译模型名称 |

### 2.3 本地目录约定

| 目录 | 说明 |
| --- | --- |
| `reports/` | 日报与测试日志输出 |
| `data/cache/` | 缓存与事实库 |
| `data/archive/` | 收盘后归档快照 |
| `data/alerts/` | 研究或翻译异常提醒 |
| `data/international_mining/` | 国际矿企标准化数据产物 |

## 3. 安装与启动

### 3.1 安装依赖

```bash
cd /Users/user/Documents/personal/rolling-snowball
python3 -m pip install -r requirements.txt
```

### 3.2 生成日报

```bash
cd /Users/user/Documents/personal/rolling-snowball
bash scripts/run_daily_report.sh
```

### 3.3 调度模式执行

```bash
bash scripts/run_daily_report.sh --mode scheduled
```

### 3.4 启动本地服务

```bash
bash scripts/run_report_server.sh
```

默认监听地址：`http://127.0.0.1:8765`

### 3.5 测试与稳定性验证

```bash
bash scripts/run_test_suite.sh
bash scripts/run_stability_test.sh 72 3600
```

### 3.6 国际矿企专题管道

```bash
bash scripts/run_international_mining_pipeline.sh
```

## 4. 调度配置

`launchd/com.user.zijin-daily-report.plist.example` 当前配置要点如下：

| 项目 | 当前值 | 说明 |
| --- | --- | --- |
| 调度标签 | `com.user.zijin-daily-report` | macOS LaunchAgent 标识 |
| 触发周期 | `3600` 秒 | 每小时唤醒一次 |
| 实际执行 | `scripts/run_daily_report.sh --mode scheduled` | 是否真正运行由代码再判断 |
| 工作目录 | 项目根目录 | 保证相对路径稳定 |
| 标准输出日志 | `reports/launchd.stdout.log` | 正常执行日志 |
| 错误输出日志 | `reports/launchd.stderr.log` | 错误信息 |
| `RunAtLoad` | `true` | 登录后立即执行一次 |

### 4.1 调度窗口规则

| 条件 | 规则 |
| --- | --- |
| 非交易日 | 不更新，不归档 |
| 交易日 `09:00-15:59` | 允许小时级更新 |
| 交易日 `16:00` 后 | 允许归档 |

## 5. 日常维护流程

### 5.1 每日巡检

1. 检查 `reports/YYYY/MM/` 下是否生成最新 HTML。
2. 检查 `reports/launchd.stderr.log` 是否有异常。
3. 检查 `data/archive/YYYY/MM/DD/` 是否存在收盘归档。
4. 检查 `data/alerts/research_updates_latest.json` 是否有新增高优先级研报。
5. 若启用翻译，检查 `data/cache/translations/` 与告警文件是否正常更新。

### 5.2 每周巡检

1. 执行 `bash scripts/run_test_suite.sh`。
2. 抽查美元代理、外部政策、央行购金是否仍有数据。
3. 检查 `data/cache/commodity_supply_plans.json` 是否需要补充国际矿企事实。
4. 检查 `portfolio.json` 中关注列表和业务逻辑是否有新需求。

### 5.3 需求迭代流程

1. 先判断属于哪个业务域。
2. 优先修改对应子模块，而不是继续膨胀主文件。
3. 若新增外部源，优先落在 `report_extra.py`。
4. 若新增业务分析，优先落在专门分析模块。
5. 更新文档集中的模块登记册和检索关键词。
6. 至少运行对应测试，必要时跑完整测试集。

## 6. 常见故障排查

### 6.1 启动即退出

| 现象 | 可能原因 | 排查步骤 |
| --- | --- | --- |
| 程序提示缺少 Token | `TUSHARE_TOKEN` 未配置 | 检查 `.env` 是否存在且变量已导出 |
| `run_daily_report.sh` 找不到配置文件 | 工作目录不正确 | 确认脚本从项目根目录执行 |

### 6.2 某些板块无数据

| 现象 | 可能原因 | 排查步骤 |
| --- | --- | --- |
| Tushare 行情/财务为空 | 接口权限不足或 token 异常 | 查看状态面板与终端日志 |
| 美元/美债板块为空 | FRED/Treasury 抓取失败 | 检查 `report_extra.py` 路径、网络与 `data/cache/dollar_index_proxy.csv` |
| 研报/政策为空 | 缓存文件为空或外部源无命中 | 检查 `data/cache/research_entries.json`、`policy_events.json` |
| 央行购金为空 | WGC 抓取失败或解析缺口 | 检查 `central_bank_gold.json` 和 `OFFICIAL_MONTH_OVERRIDES` |

### 6.3 刷新接口异常

| 现象 | 可能原因 | 排查步骤 |
| --- | --- | --- |
| `/api/refresh-report` 返回 `409` | 已有刷新任务执行中 | 等待当前任务结束 |
| 返回 `504` | 数据抓取过慢或网络卡住 | 先手工执行日报脚本定位慢点 |
| 返回 `500` | 日报脚本内部报错 | 查看返回 detail 与 stderr 日志 |

### 6.4 翻译链路异常

| 现象 | 可能原因 | 排查步骤 |
| --- | --- | --- |
| 全部条目状态为 `skipped` | 未启用翻译 | 检查 `TRANSLATION_ENABLED` |
| 状态为 `failed` | 接口错误、超时、密钥失效 | 检查 API 地址、Key、告警文件 |
| 术语未统一 | glossary 配置缺失 | 检查 `portfolio.json` 的 `external_sources.translation.glossary` |

### 6.5 归档失败

| 现象 | 可能原因 | 排查步骤 |
| --- | --- | --- |
| 抛出“归档校验失败” | 结构化数据记录主键缺失或重复 | 查看 manifest 中 invalid_datasets |
| 归档目录不存在 | 调度窗口未命中或脚本未执行到归档逻辑 | 检查交易日历和执行时间 |

### 6.6 外部 HTTPS 证书问题

- 当前代码已在 `report_extra.py` 中加入 SSL 证书校验失败回退逻辑。
- 若仍失败，先确认是否为网络被拦截，而非单纯证书错误。

## 7. 配置维护点

### 7.1 高频维护文件

| 文件 | 维护时机 | 说明 |
| --- | --- | --- |
| `config/portfolio.json` | 观察列表、业务规则调整时 | 系统总配置 |
| `.env` | token 或翻译服务切换时 | 运行凭据 |
| `data/cache/commodity_supply_plans.json` | 国际矿企事实更新时 | 国际矿企事实库主文件 |
| `launchd/com.user.zijin-daily-report.plist.example` | 调整调度频率时 | 本地自动运行配置 |

### 7.2 缓存维护策略

| 缓存文件 | 策略 |
| --- | --- |
| `dollar_index_proxy.csv` | 主源失败时保留最近可用美元代理 |
| `research_entries.json` | 按主键合并去重 |
| `policy_events.json` | 保留最近政策事件 |
| `central_bank_gold.json` | 保留最近月度购金条目 |
| `translations/*.json` | 保留翻译映射，减少重复调用 |
| `research_tracking_state.json` | 保留已提醒记录 ID |

## 8. 版本演进纪要

说明：当前目录不是 Git 仓库，无法读取提交历史。以下内容基于现有代码、测试产物、报告产物与近期工程变更归纳。

### 8.1 2026-07-05

- 主日报脚本完成一次较大重构，采集与渲染逻辑解耦。
- 引入 `ReportData` 数据对象和 `collect_report_data()` 主编排函数。
- 增加翻译模块、研报追踪模块、测试脚本与稳定性测试脚本。
- 建立交易时段更新与归档机制。

### 8.2 2026-07-06

- 国际矿企事实库处理流程完善。
- 增加 `international_mining_db.py` 与一键运行管道脚本。
- 产出 SQLite、CSV、JSON 和专题报告文档。

### 8.3 2026-07-07

- 业务范围正式收敛为金、铜、锂，不再继续扩展铁矿石。
- 日报结构重构为“全局总览 - 核心维度拆解 - 关联影响分析 - 结论与展望”。
- 国际矿企对标从列表升级到雷达图/热力图呈现。
- 美元与美债模块补齐有效数据链路。
- 增强美元代理三层兜底：`FRED -> USDCNH -> 本地缓存`。
- 修复外部抓取 SSL 证书问题。
- 修复美债曲线跨年抓取问题。
- 修复相关性计算列名冲突问题。

## 9. 长期维护建议

- 优先保持“配置驱动 + 分析模块分层 + 渲染层收口”的结构，不要再把全部逻辑回灌到单一函数。
- 若未来要继续扩容业务域，建议新增：
  - `src/macro_insights.py`
  - `src/peer_company_insights.py`
  - `src/report_templates.py`
- 若未来要强化 AI 记忆场景，建议同步维护：
  - 模块 owner
  - 变更日期
  - 变更原因
  - 受影响测试
