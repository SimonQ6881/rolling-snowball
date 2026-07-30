# Rolling Snowball

这是当前在持续开发的选股与研究控制台项目。核心目标是把“规则实验 -> 发起评分任务 -> 回看历史 run -> 查询股票与行业结果”收成一个本地可用的研究工作台。

当前主线能力包括：

- 首页默认查看重点观察池，并支持切换历史 run
- 股票列表、行业看板、个股详情的查询闭环
- 任务中心查看任务状态、日志和结果入口
- 历史运行页回看 run 摘要与来源任务
- 规则实验台支持改动高亮、实时校验、错误文案、规则快照回看
- `Run 质量总览` 支持看整体健康度、warning 分布、行业分布与异常样本首版

如果要继续开发或回看当前项目状态，优先看：

- `docs/current-console-status.md`
- `docs/superpowers/specs/2026-07-30-frontend-console-design.md`

## 快速启动

### 1. 安装依赖

```bash
cd /Users/user/Documents/personal/rolling-snowball
python3 -m pip install -r requirements.txt
```

前端依赖位于 `frontend-console/node_modules`。如果后续需要重装，可在 `frontend-console` 目录重新安装。

### 2. 配置环境

复制环境变量模板：

```bash
cd /Users/user/Documents/personal/rolling-snowball
cp .env.example .env
```

至少确认这些参数可用：

- `TUSHARE_TOKEN`
- `PGHOST`
- `PGPORT`
- `PGDATABASE`
- `PGUSER`
- `PGPASSWORD`（如本地数据库需要）

### 3. 一键启动前后端

```bash
cd /Users/user/Documents/personal/rolling-snowball
bash scripts/start_console_stack.sh --open
```

默认会启动：

- 前端：`http://127.0.0.1:4178`
- 后端：`http://127.0.0.1:8780`

注意：

- 如果 `4178` 已被占用，Vite 可能自动切到其他端口，例如 `4179`
- 这时请以 `data/dev-console/frontend.log` 里的实际地址为准

日志与 PID 文件会写到：

- `data/dev-console/backend.log`
- `data/dev-console/frontend.log`
- `data/dev-console/backend.pid`
- `data/dev-console/frontend.pid`

如果只想先检查命令而不真正启动：

```bash
bash scripts/start_console_stack.sh --dry-run
```

停止前后端：

```bash
bash scripts/stop_console_stack.sh
```

## 常用脚本

- `python3 scripts/run_console_server.py`：单独启动控制台后端
- `python3 scripts/init_rolling_snowball_db.py`：初始化数据库
- `python3 scripts/run_scoring_bootstrap.py`：手动执行评分数据准备
- `bash scripts/run_test_suite.sh`：运行 Python 测试

## 目录结构

```text
frontend-console/                     React 前端控制台
src/rolling_snowball/                 选股核心逻辑、评分管线、控制台服务
scripts/run_console_server.py         控制台后端启动脚本
scripts/start_console_stack.sh        前后端一键启动脚本
scripts/stop_console_stack.sh         前后端停止脚本
sql/postgres/001_init_schema.sql      PostgreSQL 初始化表结构
data/scoring_tasks/                   任务日志
data/dev-console/                     本地开发态日志与 PID
docs/superpowers/specs/               已确认的设计规格
```

## 当前主线页面

- `/`：首页，默认查看最新 run 的重点观察池
- `/stocks`：股票结果列表，支持 run、行业、池子筛选
- `/industries`：行业看板
- `/tasks/latest`：任务中心
- `/runs`：历史运行
- `/lab`：规则实验台

## 说明

仓库里仍保留了一些较早的日报/报告模块与脚本，它们不是当前控制台主线的一部分。后续若继续收口，会逐步把这些历史命名和文档再清理掉。

如果需要区分当前主线和历史入口，可以先看：

- `scripts/README.md`
- `docs/legacy-modules.md`
