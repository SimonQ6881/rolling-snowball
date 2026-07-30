# Scripts Guide

当前仓库里的脚本分为两类：

## 当前主线

这些脚本服务于 rolling-snowball 控制台，是目前持续开发和日常使用的主入口。

- `start_console_stack.sh`：一键启动前端控制台和后端 API
- `stop_console_stack.sh`：停止前端控制台和后端 API
- `run_console_server.py`：单独启动控制台后端
- `init_rolling_snowball_db.py`：初始化 PostgreSQL 表结构
- `run_scoring_bootstrap.py`：执行评分链路相关初始化
- `run_test_suite.sh`：运行测试

## 历史模块

早期日报链路和旧版股票评估原型相关脚本已经从仓库中移除。当前仍保留的非主线脚本主要是专项数据处理脚本，不属于现在的控制台主线。

- `run_international_mining_pipeline.sh`

如果你当前的目标是使用或开发选股控制台，优先使用“当前主线”脚本，不要从非主线入口启动。
