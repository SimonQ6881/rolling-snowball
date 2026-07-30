# 历史模块说明

这个仓库最早承载过几条不同方向的本地工具链，后续才逐步收口到当前的 rolling-snowball 选股控制台。此前遗留在仓库中的两条旧链路已经移除，这份文档用于说明它们的历史定位，以及当前仍保留的非主线资产应该如何理解。

## 当前主线

当前持续开发的主线是：

- `src/rolling_snowball/`
- `frontend-console/`
- `scripts/start_console_stack.sh`
- `scripts/stop_console_stack.sh`
- `scripts/run_console_server.py`

这部分对应的是：

- 规则实验台
- 任务中心
- 历史运行
- 股票结果与行业看板

## 已移除的历史模块

### 1. 紫金日报链路

这条链路是早期的日报生成和本地预览服务，曾经承载过数据抓取、报告生成和调度能力。当前已从仓库中移除，不再作为追溯或开发入口。

### 2. 旧版股票评估原型

这条链路是更早期的股票评估原型。当前已从仓库中移除，不再作为当前控制台的演进基线。

## 当前仍保留的非主线资产

以下内容不属于当前主线，但仍保留在仓库中：

- `scripts/run_international_mining_pipeline.sh`
- `data/international_mining/`
- `reports/` 下的历史报告产物

## 使用约定

- 如果当前要开发选股控制台，只进入 `src/rolling_snowball/` 和 `frontend-console/`
- 如果看到 `zijin`、`report_server`、`stock_evaluation` 命名，默认按“已移除历史模块”理解
- 如果当前要开发选股控制台，只进入 `src/rolling_snowball/` 和 `frontend-console/`
- 除非任务明确涉及专项数据或历史报告，否则不要把新功能继续堆到非主线入口里
