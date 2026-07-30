# Rolling Snowball 控制台当前状态

这份文档用于沉淀当前主线已经完成的功能、当前可直接体验的数据状态、已明确跳过的范围，以及后续继续开发时最值得优先推进的方向。

适用场景：

- 继续优化前先快速了解项目现状
- 多轮对话或长间隔后恢复开发上下文
- 体验工具时确认哪些是当前主线、哪些是历史遗留

## 1. 当前项目主线

当前持续开发的主线是一个本地单用户的选股与研究控制台，核心闭环是：

`规则实验 -> 发起评分任务 -> 回看历史 run -> 查询股票与行业结果 -> 复盘 run 质量`

主线代码入口：

- `src/rolling_snowball/`
- `frontend-console/`
- `scripts/run_console_server.py`
- `scripts/start_console_stack.sh`
- `scripts/stop_console_stack.sh`

历史模块说明见：

- `docs/legacy-modules.md`
- `scripts/README.md`

## 2. 已完成能力

### 2.0 前端界面基线

当前主线前端已经完成一轮浅色 Apple 风格产品化改造，整体特征是：

- 浅色主导的研究工作台背景与轻卡片系统
- 克制标题和更安静的数据排版
- 首页、列表、详情、复盘、历史运行、任务中心统一采用“摘要优先”的信息结构
- 规则实验台升级为左编辑、右反馈的实验驾驶舱

### 2.1 结果查询主站

已完成页面与能力：

- `/`
  - 首页默认展示重点观察池
  - 支持按 `run` 切换查看历史结果
  - 第一屏先给结论摘要，再提供股票列表、行业看板、规则实验台、历史运行等辅助入口
- `/stocks`
  - 展示指定 `run` 下的股票结果
  - 支持按池子、行业、是否被过滤、关键词筛选
  - 使用“摘要 + 过滤舱 + 安静表格”的双层结构
  - 对旧 run 缺少逐股明细时给出提示
- `/industries`
  - 展示行业分布与行业结果视角
  - 使用行业摘要 + 行业卡片的轻量看板结构
- `/stocks/:tsCode`
  - 个股详情页
  - 先展示结论区，再展示四个一级维度拆解、硬过滤 / warning / 同行业对比

### 2.2 任务与历史运行

已完成页面与能力：

- `/tasks/:taskId`
  - 任务中心
  - 展示最近任务列表、任务状态、阶段、日志、run 入口
  - 使用“状态与结果入口 -> run 摘要 -> 执行日志”的右侧主内容结构
  - 支持从任务跳转到首页、股票列表、行业看板、历史运行
  - 支持显示本次任务对应的规则快照摘要
- `/runs`
  - 历史运行页
  - 展示运行时间、样本规模、分池结果、来源任务
  - 使用导航型 run 卡片组织结果入口与规则快照
  - 支持跳转首页、股票列表、行业看板、`Run 质量总览`
  - 支持显示 run 对应的规则快照摘要

### 2.3 规则实验台

已完成页面与能力：

- `/lab`
  - 支持编辑硬过滤阈值、一级权重、二级指标权重、重点池名额
  - 支持 `run_once` / `save_as_default`
  - 支持左编辑右反馈的实验驾驶舱布局
  - 支持改动高亮
  - 支持顶部改动摘要
  - 支持字段级“已修改”标记与默认值参考
  - 支持全部恢复默认 / 分组恢复默认
  - 支持即时前端校验
  - 支持区分硬错误与软提醒
  - 支持更清楚的字段级、页面级、提交区文案

相关规格文档：

- `docs/superpowers/specs/2026-07-30-rule-lab-change-highlighting-design.md`
- `docs/superpowers/specs/2026-07-30-rule-lab-validation-design.md`
- `docs/superpowers/specs/2026-07-30-rule-lab-message-clarity-design.md`

### 2.4 Run 复盘能力

已完成页面与能力：

- `/run-review`
  - 展示 run 质量总览
  - 第一屏先判断 run 是否跑偏，再展开 warning 分布和异常样本
  - 包含整体健康度指标：
    - 总样本
    - 通过率
    - 重点池占比
    - warning 覆盖率
    - 平均 warning 数
  - 展示 warning 分布
  - 展示行业分布
  - 展示异常样本首版：`高分但 warning 多`
  - 支持跳转到个股详情页继续人工复核

后端支持接口：

- `GET /api/runs/{run_id}/review`

### 2.5 规则快照回看

已完成能力：

- `run_rule_snapshots` 已并入历史运行查询
- 任务页、历史运行页都可直接回看规则摘要
- 不需要再回到规则实验台，才能知道这次 run 用了什么参数

### 2.6 命名与工程收口

已完成内容：

- 新增主线与历史模块区分文档
- 已移除旧版日报链路与股票评估原型
- 补充一键启动脚本与停止脚本
- 前端包名与 README 已改到 rolling-snowball 口径

## 3. 当前数据与体验状态

## 3.1 当前可直接体验的数据

当前控制台可以直接体验两类数据：

1. 样本验证 run
   - 如 `d4644025-0bf1-4a4e-a5bc-1abf16845930`
   - 适合验证新规则逻辑和前端交互

2. 历史近全量 run
   - `run_id = f8deb06b-8f04-4589-937f-af62a80b659f`
   - `data_version = 20260729_full`
   - 当前已恢复到 `stock_run_scores` 的逐股明细数为 `5434`

## 3.2 关于“历史近全量 run”的口径说明

这条近全量 run 可以用于体验工具，但要注意两个事实：

1. 它不是完整 `5534` 条
   - `scoring_runs` 摘要里记录的是 `5534`
   - 当前可恢复到前端查询链路中的逐股明细是 `5434`

2. 它不是最新分池逻辑
   - 这条 run 属于较早阶段的历史结果
   - 不代表后来确认的“通过硬过滤后按总分前 20 名进入重点观察池”的最终逻辑

因此：

- 它适合用来体验页面、筛选、详情、历史运行、run 复盘
- 不适合用来代表当前最终规则的正式全量结果

## 3.3 数据表现状

当前几个关键结果表的角色如下：

- `scoring_runs`
  - 保存每次 run 的摘要
- `stock_run_scores`
  - 保存按 `run_id` 可回看的逐股历史明细
- `stock_latest_scores`
  - 保存最新一版逐股结果快照
- `run_rule_snapshots`
  - 保存每次 run 对应的规则快照

开发时要注意：

- 前端查询历史 run 主要依赖 `stock_run_scores`
- 某些较早 run 可能只剩摘要，没有完整逐股明细
- `stock_latest_scores` 不能简单等同于“所有历史 run 的完整归档”

## 4. 已明确跳过或暂不做

以下内容已经由用户明确确认，当前不作为主线：

- 结果导出
- 跨 run 对比
- 历史文件入口下沉

后续如果要重开这些项，需要视为新需求重新讨论，而不是默认继续推进。

## 5. 还未完成、但值得继续做的内容

按当前价值和连续性，后续最值得继续推进的是下面几项。

### 5.1 Run 复盘继续补强

当前已经有 `Run 质量总览` 和首版异常样本，但还没完全形成复盘闭环。

可继续做：

- `入池但数据缺口`
- `行业前排但被过滤`
- warning 按类型拆分展示
- 从复盘页直接跳到带筛选条件的股票列表

### 5.2 后端单测补强

当前前端测试已覆盖主线页面，但后端聚合逻辑仍偏轻。

建议补强：

- `get_run_quality_overview`
- 历史 run 与规则快照的查询组合
- 历史 run 缺逐股明细时的边界行为

### 5.3 启动体验收口

当前启动脚本已可用，但还有一个已确认的问题：

- 如果 `4178` 被占用，Vite 会自动切到别的端口，例如 `4179`
- 启动脚本仍可能按默认端口提示，容易误导体验

这个问题建议后续修掉，让脚本能输出前端真实启动端口。

### 5.4 命名残留继续清理

高频误导项已经继续收口一轮，但仍有少量历史报告、专项数据和命名残留可以在后续继续整理。

## 6. 当前主线的重要文件

### 后端

- `src/rolling_snowball/console_service.py`
  - 控制台查询服务主入口
  - 包含：
    - `latest_run`
    - `list_runs`
    - `get_run_summary`
    - `get_run_quality_overview`
    - `list_stocks`
    - `list_industries`
    - `get_stock_detail`
    - `get_stock_peers`
    - 任务相关查询与创建

- `src/rolling_snowball/console_server.py`
  - HTTP API 路由层

- `src/rolling_snowball/scoring_pipeline.py`
  - run 生成、落库、规则快照持久化主入口

### 前端

- `frontend-console/src/App.tsx`
  - 当前页面路由定义
- `frontend-console/src/pages/Home.tsx`
- `frontend-console/src/pages/StocksPage.tsx`
- `frontend-console/src/pages/IndustriesPage.tsx`
- `frontend-console/src/pages/StockDetailPage.tsx`
- `frontend-console/src/pages/TaskPage.tsx`
- `frontend-console/src/pages/RunsPage.tsx`
- `frontend-console/src/pages/RunReviewPage.tsx`
- `frontend-console/src/pages/LabPage.tsx`

### 公共与规则相关

- `frontend-console/src/components/layout/RunSwitcher.tsx`
- `frontend-console/src/components/rules/RuleSnapshotSummary.tsx`
- `frontend-console/src/lib/ruleDiff.ts`
- `frontend-console/src/lib/ruleValidation.ts`
- `frontend-console/src/lib/ruleMessages.ts`

### 文档

- `docs/superpowers/specs/2026-07-30-frontend-console-design.md`
- `docs/superpowers/specs/2026-07-30-key-watch-top20-design.md`
- `docs/superpowers/specs/2026-07-30-rule-lab-change-highlighting-design.md`
- `docs/superpowers/specs/2026-07-30-rule-lab-validation-design.md`
- `docs/superpowers/specs/2026-07-30-rule-lab-message-clarity-design.md`
- `docs/superpowers/plans/2026-07-30-run-review-warning-outliers.md`

## 7. 推荐的后续开发顺序

如果要继续沿当前主线推进，建议按这个顺序：

1. `Run 质量总览` 第二批异常样本
2. 复盘页到股票列表的跳转闭环
3. 后端单测补强
4. 启动脚本输出真实前端端口
5. 命名残留继续清理

## 8. 本地体验建议

启动控制台：

```bash
bash scripts/start_console_stack.sh --open
```

如果前端默认端口 `4178` 被占用，Vite 可能自动改到其他端口。遇到“网页无法连接”时，优先查看：

- `data/dev-console/frontend.log`

历史近全量体验链接示例：

```text
http://127.0.0.1:4179/?run=f8deb06b-8f04-4589-937f-af62a80b659f
http://127.0.0.1:4179/stocks?run=f8deb06b-8f04-4589-937f-af62a80b659f
http://127.0.0.1:4179/run-review?run=f8deb06b-8f04-4589-937f-af62a80b659f
```

端口号以实际日志为准，不要只看脚本里的默认值。
