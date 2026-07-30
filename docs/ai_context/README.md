---
doc_id: zijin-daily-ai-context-readme
title: 紫金矿业日报 AI 上下文文档集（历史模块）
doc_type: index
project: rolling-snowball
system_scope: 紫金矿业自动日报
generated_on: 2026-07-07
last_verified_on: 2026-07-07
maintainer_owner: 待补充
status: legacy
keywords:
  - 紫金矿业日报
  - AI上下文
  - 技术文档
  - 模块索引
  - 检索验证
---

# 紫金矿业日报 AI 上下文文档集

> 说明：这组文档对应的是仓库中的历史“紫金日报”模块，不属于当前 rolling-snowball 控制台主线。

本目录用于承载“紫金矿业日报系统”的长期维护文档，目标不是面向终端读者，而是面向后续 AI 检索、上下文拼装、代码记忆与维护交接。

## 文档清单

1. [01_system_overview.md](file:///Users/user/Documents/personal/rolling-snowball/docs/ai_context/01_system_overview.md)
   - 全量代码资产盘点
   - 目录树
   - 模块依赖图谱
   - 全局数据流与业务链路

2. [02_module_registry.md](file:///Users/user/Documents/personal/rolling-snowball/docs/ai_context/02_module_registry.md)
   - 核心模块标准化说明
   - 输入输出参数
   - 关键函数
   - 异常处理规则
   - AI 友好元数据标签

3. [03_operations_maintenance.md](file:///Users/user/Documents/personal/rolling-snowball/docs/ai_context/03_operations_maintenance.md)
   - 技术栈
   - 环境变量
   - 部署与调度
   - 日常巡检
   - 常见故障排查
   - 版本演进纪要

4. [04_retrieval_validation.md](file:///Users/user/Documents/personal/rolling-snowball/docs/ai_context/04_retrieval_validation.md)
   - 检索关键词索引
   - 跨模块关联索引
   - 检索验证样例
   - 文档有效性检查结果

## 使用方式

- 面向 AI 检索时，优先先读 `01_system_overview.md` 获取全局结构，再按模块名跳转 `02_module_registry.md`。
- 面向运维与上线排查时，优先读 `03_operations_maintenance.md`。
- 面向知识召回质量验证时，优先读 `04_retrieval_validation.md`。

## 约定

- 所有路径均以当前仓库根目录 `/Users/user/Documents/personal/rolling-snowball` 为基准。
- 所有“维护责任人”字段当前统一标注为 `待补充`，因为仓内未发现明确的人事归属配置。
- “版本演进纪要”基于仓内脚本、测试报告、最近产物和代码现状归纳，不等同于 Git 提交历史。当前目录不是 Git 仓库，无法直接回溯提交记录。

## 推荐检索入口

- 入口程序：`src/zijin_daily_report.py`
- 调度归档：`src/pipeline_ops.py`
- 外部抓取：`src/report_extra.py`
- 服务刷新：`src/report_server.py`
- 翻译链路：`src/translation_service.py`
- 研报追踪：`src/research_tracker.py`
- 商品分析：`src/commodity_insights.py`
- 央行购金：`src/central_bank_insights.py`
- 国际矿企：`src/international_mining_db.py`
