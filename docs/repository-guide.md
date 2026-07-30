# 仓库说明文档

这份文档用于帮助新接手的开发者快速理解 Rolling Snowball 仓库的主线范围、目录职责、运行依赖和协作边界。

如果你第一次打开这个仓库，建议先看：

1. 根目录 `README.md`
2. 本文档
3. `docs/current-console-status.md`

## 仓库全景

Rolling Snowball 当前主线是一个本地单用户的选股与研究控制台。它的核心闭环是：

`规则实验 -> 发起评分任务 -> 回看历史 run -> 查询股票与行业结果 -> 复盘 run 质量`

仓库中当前主要包含几类内容：

- 当前主线代码：前端控制台、后端控制台服务、评分管线和相关脚本
- 运行依赖与配置：数据库脚本、环境变量模板、规则配置
- 数据与样例结果：缓存、归档数据、数据库文件、报告文件
- 历史沉淀：报告、专项数据和少量非主线脚本
- 设计与状态文档：当前状态、规格、计划和历史说明

理解这个仓库时，最重要的是先区分“当前主线”和“历史沉淀”，不要把所有目录都当成正在演进的代码。

## 当前主线与历史模块边界

### 当前主线

以下目录和脚本属于当前持续开发的主线：

- `frontend-console/`
- `src/rolling_snowball/`
- `scripts/start_console_stack.sh`
- `scripts/stop_console_stack.sh`
- `scripts/run_console_server.py`
- `scripts/init_rolling_snowball_db.py`
- `scripts/run_scoring_bootstrap.py`
- `sql/postgres/001_init_schema.sql`

这部分对应的业务能力包括：

- 规则实验台
- 任务中心
- 历史运行
- 股票列表、行业看板和个股详情
- Run 质量复盘

### 已移除的历史模块

此前仓库中保留过两条旧链路，但已经在当前版本中移除：

- 紫金日报链路
- 旧版股票评估原型

因此，如果你在旧文档、旧提交记录或历史讨论里看到 `zijin`、`report_server`、`stock_evaluation` 等命名，应将其理解为已下线的历史实现，而不是当前主线入口。

### 仍保留的历史或专项内容

以下内容不属于当前控制台主线，但仍保留在仓库里：

- `scripts/run_international_mining_pipeline.sh`
- `data/international_mining/`
- `reports/` 下的历史报告产物

除非你的任务明确涉及这些资产，否则不要把新功能继续堆到这些入口中。

## 系统组成

### 前端控制台

- 路径：`frontend-console/`
- 技术栈：React、TypeScript、Vite、Zustand、Tailwind CSS
- 作用：承载首页、股票列表、行业看板、任务中心、历史运行、规则实验台和 Run 质量总览等页面

高频入口：

- `frontend-console/src/App.tsx`
- `frontend-console/src/pages/`
- `frontend-console/src/components/`
- `frontend-console/src/api/console.ts`
- `frontend-console/src/store/consoleStore.ts`

### 后端控制台服务

- 路径：`src/rolling_snowball/`
- 技术栈：Python、PostgreSQL
- 作用：提供控制台 API、评分管线、规则管理、股票结果查询和任务查询能力

高频入口：

- `src/rolling_snowball/console_server.py`
- `src/rolling_snowball/console_service.py`
- `src/rolling_snowball/scoring_pipeline.py`
- `src/rolling_snowball/rules.py`
- `src/rolling_snowball/settings.py`

### 脚本层

- 路径：`scripts/`
- 作用：负责启动、停止、初始化、测试和若干专项任务

主线脚本：

- `start_console_stack.sh`
- `stop_console_stack.sh`
- `run_console_server.py`
- `init_rolling_snowball_db.py`
- `run_scoring_bootstrap.py`
- `run_test_suite.sh`

历史脚本说明见 `scripts/README.md`。

### 数据与配置层

- `sql/postgres/`：数据库初始化 SQL
- `config/`：组合配置和规则版本
- `data/`：缓存、归档数据、数据库文件、样例 run 结果和部分报告产物

需要注意的是，`data/` 目录并不等同于“全部都是临时文件”。这个仓库当前保留了一部分业务数据和样例结果用于体验、验证和追溯。

## 数据与依赖

### Python 依赖

根目录 `requirements.txt` 当前包含：

- `tushare`
- `pandas`
- `psycopg[binary]`
- `pytest`

### 前端依赖

前端依赖位于 `frontend-console/package.json`，核心包括：

- `react`
- `react-router-dom`
- `zustand`
- `vite`
- `typescript`
- `vitest`
- `eslint`

### 环境变量

环境变量模板位于 `.env.example`。高频变量包括：

- `TUSHARE_TOKEN`
- `PGHOST`
- `PGPORT`
- `PGDATABASE`
- `PGUSER`
- `PGPASSWORD`

可选翻译相关变量包括：

- `TRANSLATION_ENABLED`
- `TRANSLATION_API_BASE_URL`
- `TRANSLATION_API_KEY`
- `TRANSLATION_MODEL`

### 数据角色说明

- PostgreSQL：承载运行摘要、逐股结果、规则快照等主线查询数据
- Tushare：提供部分金融数据来源
- `data/cache/`：本地缓存和中间结果
- `data/archive/`：归档快照
- `data/international_mining/`：历史或专项数据资产

## 常用开发路径

如果你要继续沿当前主线开发，建议按这个顺序建立上下文：

1. 看根目录 `README.md`
2. 看 `docs/current-console-status.md`
3. 看 `docs/legacy-modules.md`
4. 浏览 `frontend-console/src/App.tsx` 和 `frontend-console/src/pages/`
5. 浏览 `src/rolling_snowball/console_server.py` 和 `src/rolling_snowball/console_service.py`
6. 根据任务再进入规则、评分或数据相关模块

如果你的任务和交互或页面有关，优先进入：

- `frontend-console/src/pages/`
- `frontend-console/src/components/`
- `frontend-console/src/lib/`

如果你的任务和 run 查询、任务、评分结果聚合有关，优先进入：

- `src/rolling_snowball/console_service.py`
- `src/rolling_snowball/scoring_pipeline.py`
- `src/rolling_snowball/db.py`

## 常用命令与脚本职责

### 初始化与启动

```bash
cd /Users/user/Documents/personal/rolling-snowball
python3 -m pip install -r requirements.txt
cd frontend-console && npm install
cd ..
cp .env.example .env
python3 scripts/init_rolling_snowball_db.py
bash scripts/start_console_stack.sh --open
```

### 停止服务

```bash
cd /Users/user/Documents/personal/rolling-snowball
bash scripts/stop_console_stack.sh
```

### 后端相关

```bash
cd /Users/user/Documents/personal/rolling-snowball
python3 scripts/run_console_server.py
python3 scripts/run_scoring_bootstrap.py
bash scripts/run_test_suite.sh
pytest tests -q
```

### 前端相关

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

如果前端默认端口 `4178` 被占用，Vite 会自动切到其他端口，最终以前端日志输出为准。

## 文档索引

- `README.md`：仓库首页入口
- `docs/repository-guide.md`：仓库结构、依赖和协作说明
- `docs/current-console-status.md`：当前主线已完成能力、数据状态和后续优先级
- `docs/legacy-modules.md`：历史模块边界说明
- `scripts/README.md`：主线脚本与历史脚本说明
- `docs/superpowers/specs/`：交互与页面设计规格
- `docs/superpowers/plans/`：实施计划文档

如果你只想尽快开始开发，优先看前 5 个文档即可。

## 协作约定

- 默认只在当前主线目录中新增或修改功能
- 看到 `zijin`、`report_server`、`stock_evaluation` 等命名，先按“已移除的历史模块”理解
- `.env`、日志、PID、缓存目录不应提交到仓库
- `data/dev-console/`、`data/scoring_tasks/` 等运行态目录按忽略规则处理
- 修改文档时，尽量保持与 `docs/current-console-status.md` 和 `docs/legacy-modules.md` 的口径一致
- 如果新增主线功能，优先同步更新 `README.md` 或本文档中的导航信息
