# Rolling Snowball

Rolling Snowball 是一个本地单用户的选股与研究控制台，目标是把“规则实验 -> 发起评分任务 -> 回看历史 run -> 查询股票与行业结果 -> 复盘 run 质量”收成一个可持续迭代的研究工作台。

当前仓库已经包含产品文档、后端服务、前端控制台、数据库脚本、样例数据和历史报告。对于新接手的开发者，最重要的判断是：`frontend-console/`、`src/rolling_snowball/` 和控制台相关脚本是当前主线，其余部分可能是历史模块或沉淀资产。

## 项目概述

当前主线聚焦在一个本地研究闭环：

- 在规则实验台调整硬过滤阈值、权重和重点池名额
- 发起评分任务并生成新的 run
- 回看历史 run、规则快照和任务日志
- 查询股票列表、行业分布和个股详情
- 复盘 run 质量、warning 分布和异常样本

这个仓库不是通用 SaaS 平台，也不是多人协同系统。当前定位是面向个人研究场景的本地工具链。

## 当前主线能力

- 首页：默认查看最新 run 的重点观察池，并可切换历史 run
- 股票结果：支持按 run、行业、池子、关键词和过滤状态查看股票结果
- 行业看板：支持从行业维度查看结果分布和表现
- 个股详情：支持查看一级维度拆解、warning、硬过滤和同行对比
- 任务中心：支持查看任务状态、阶段、日志和结果入口
- 历史运行：支持回看 run 摘要、来源任务和规则快照摘要
- 规则实验台：支持改动高亮、即时校验、错误文案和恢复默认
- Run 复盘：支持查看整体健康度、warning 分布、行业分布和异常样本首版

如果你要继续开发或先快速建立上下文，优先阅读：

- [当前状态文档](docs/current-console-status.md)
- [仓库说明文档](docs/repository-guide.md)
- [历史模块说明](docs/legacy-modules.md)

## 技术栈与系统组成

- 后端：Python + PostgreSQL
- 前端：React 18 + Vite + TypeScript + Zustand + Tailwind CSS
- 数据来源：Tushare、本地缓存文件、本地 PostgreSQL
- 主线目录：
  - `src/rolling_snowball/`：控制台查询服务、评分管线、规则与配置
  - `frontend-console/`：前端控制台
  - `scripts/`：控制台启动、初始化、测试和任务相关脚本
  - `sql/postgres/`：数据库初始化脚本

## 快速开始

### 1. 安装依赖

```bash
cd /Users/user/Documents/personal/rolling-snowball
python3 -m pip install -r requirements.txt
cd frontend-console
npm install
```

### 2. 配置环境变量

```bash
cd /Users/user/Documents/personal/rolling-snowball
cp .env.example .env
```

至少需要确认这些参数：

- `TUSHARE_TOKEN`
- `PGHOST`
- `PGPORT`
- `PGDATABASE`
- `PGUSER`
- `PGPASSWORD`

可选参数：

- `TRANSLATION_ENABLED`
- `TRANSLATION_API_BASE_URL`
- `TRANSLATION_API_KEY`
- `TRANSLATION_MODEL`

### 3. 初始化数据库

```bash
cd /Users/user/Documents/personal/rolling-snowball
python3 scripts/init_rolling_snowball_db.py
```

### 4. 启动前后端

```bash
cd /Users/user/Documents/personal/rolling-snowball
bash scripts/start_console_stack.sh --open
```

默认地址：

- 前端：`http://127.0.0.1:4178`
- 后端：`http://127.0.0.1:8780`

如果前端默认端口被占用，Vite 可能自动切到其他端口，例如 `4179`。此时请以 `data/dev-console/frontend.log` 中的实际地址为准。

### 5. 停止服务

```bash
cd /Users/user/Documents/personal/rolling-snowball
bash scripts/stop_console_stack.sh
```

## 常用命令

### 后端

```bash
cd /Users/user/Documents/personal/rolling-snowball
python3 scripts/run_console_server.py
python3 scripts/run_scoring_bootstrap.py
bash scripts/run_test_suite.sh
pytest tests -q
```

### 前端

```bash
cd /Users/user/Documents/personal/rolling-snowball/frontend-console
npm run dev
npm run build
npm run test
npm run lint
```

### 启动排查

```bash
cd /Users/user/Documents/personal/rolling-snowball
bash scripts/start_console_stack.sh --dry-run
tail -n 50 data/dev-console/frontend.log
tail -n 50 data/dev-console/backend.log
```

## 目录结构

```text
frontend-console/                 React 前端控制台
src/rolling_snowball/             当前主线后端服务、评分管线与规则逻辑
scripts/                          启动、初始化、测试和任务相关脚本
sql/postgres/                     PostgreSQL 初始化脚本
config/                           组合与规则配置
data/                             本地数据、缓存、样例结果与数据库文件
docs/                             当前状态、历史模块和规格文档
tests/                            Python 测试
stock_evaluation/                 旧版股票评估原型静态资源
```

更完整的目录职责和阅读顺序见 [仓库说明文档](docs/repository-guide.md)。

## 主线页面

- `/`：首页，默认查看重点观察池
- `/stocks`：股票结果列表
- `/industries`：行业看板
- `/stocks/:tsCode`：个股详情页
- `/tasks/:taskId`：任务中心
- `/runs`：历史运行
- `/run-review`：Run 质量总览
- `/lab`：规则实验台

## 文档导航

- [仓库说明文档](docs/repository-guide.md)：适合新接手开发者快速建立整体认知
- [当前状态文档](docs/current-console-status.md)：适合继续迭代前确认当前能力、数据状态和后续优先级
- [历史模块说明](docs/legacy-modules.md)：适合判断哪些目录和脚本不属于当前主线
- [脚本说明](scripts/README.md)：适合快速识别主线脚本与历史脚本
- [主线前端设计规格](docs/superpowers/specs/2026-07-30-frontend-console-design.md)：适合回看主线页面和交互边界

## 历史模块说明

仓库中仍保留两类历史资产，它们可以参考，但不应继续作为当前主线的演进基线：

- 紫金日报链路：`src/zijin_daily_report.py`、`src/report_server.py`、`scripts/run_daily_report.sh`
- 旧版股票评估原型：`src/stock_evaluation_core.py`、`src/stock_evaluation_server.py`、`stock_evaluation/`

如果你当前目标是继续开发选股控制台，请优先进入：

- `frontend-console/`
- `src/rolling_snowball/`
- `scripts/start_console_stack.sh`
- `scripts/stop_console_stack.sh`
- `scripts/run_console_server.py`

## 仓库约定

- `.env`、日志、PID、缓存目录不应提交到仓库
- `data/` 中保留的是当前项目需要的业务数据与样例结果，不等同于全部都是临时文件
- 新功能默认落在当前主线目录，不继续堆到历史模块入口中
