# 历史模块说明

这个仓库最早承载过几条不同方向的本地工具链，后续才逐步收口到当前的 rolling-snowball 选股控制台。因此仓库里仍保留了一些历史模块，它们可以继续参考，但不属于当前主线。

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

## 历史模块

### 1. 紫金日报链路

相关入口：

- `src/zijin_daily_report.py`
- `src/report_server.py`
- `scripts/run_daily_report.sh`
- `scripts/run_report_server.sh`
- `launchd/com.user.zijin-daily-report.plist.example`

这条链路是早期的日报生成和本地预览服务，保留它主要是为了参考已有的数据抓取、报告生成和调度经验。

### 2. 旧版股票评估原型

相关入口：

- `src/stock_evaluation_core.py`
- `src/stock_evaluation_server.py`
- `scripts/run_stock_evaluation_server.sh`
- `stock_evaluation/`

这条链路是更早期的原型，不再作为当前控制台的演进基线。

## 使用约定

- 如果当前要开发选股控制台，只进入 `src/rolling_snowball/` 和 `frontend-console/`
- 如果看到 `zijin`、`report_server`、`stock_evaluation` 命名，默认按“历史模块”理解
- 除非是专门回看旧实现，否则不要把新功能继续堆到这些历史入口里

## 后续清理方向

- 继续把历史文档从主线文档中剥离
- 为历史脚本统一增加 legacy 提示
- 在不影响追溯的前提下，逐步减少主目录里与当前主线无关的入口数量
