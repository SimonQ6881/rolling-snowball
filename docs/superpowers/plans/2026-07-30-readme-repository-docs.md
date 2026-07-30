# README And Repository Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重写仓库首页 README，并新增一份完整的仓库说明文档，让新开发者能快速理解项目定位、完成本地启动并找到主线代码与文档。

**Architecture:** 采用“双文档”方案：根目录 `README.md` 负责仓库首页导览与快速开始，`docs/repository-guide.md` 负责更完整的仓库结构、依赖、协作约定与阅读路径说明。两份文档均基于现有主线状态文档与历史模块文档，不改动任何功能代码。

**Tech Stack:** Markdown、Git、现有 Python + React/Vite + PostgreSQL 项目结构

---

### Task 1: 重写根 README

**Files:**
- Modify: `README.md`
- Reference: `docs/current-console-status.md`
- Reference: `docs/legacy-modules.md`
- Reference: `scripts/README.md`

- [ ] **Step 1: 梳理 README 结构**

写入以下章节骨架：

```md
# Rolling Snowball

## 项目概述
## 当前主线能力
## 技术栈与系统组成
## 快速开始
## 常用命令
## 目录结构
## 主线页面
## 文档导航
## 历史模块说明
```

- [ ] **Step 2: 写入启动与导航信息**

补全安装依赖、环境变量、数据库初始化、前后端启动、测试命令、主线路由、文档链接与历史模块边界说明。

- [ ] **Step 3: 自检 README**

检查是否满足：

```text
1. 首页首屏能说明项目是什么
2. 开发者能直接看到怎么启动
3. 能区分主线与历史模块
4. 能继续跳转到更详细文档
```

- [ ] **Step 4: 提交 README 变更**

```bash
git add README.md
git commit -m "docs: refresh project readme"
```

### Task 2: 新增仓库说明文档

**Files:**
- Create: `docs/repository-guide.md`
- Reference: `docs/current-console-status.md`
- Reference: `docs/legacy-modules.md`
- Reference: `scripts/README.md`

- [ ] **Step 1: 创建仓库说明文档**

写入以下章节骨架：

```md
# 仓库说明文档

## 仓库全景
## 当前主线与历史模块边界
## 系统组成
## 数据与依赖
## 常用开发路径
## 常用命令与脚本职责
## 文档索引
## 协作约定
```

- [ ] **Step 2: 写清关键边界**

明确 `frontend-console/`、`src/rolling_snowball/`、`scripts/`、`sql/`、`data/` 的职责，说明 PostgreSQL、Tushare、本地缓存和历史模块角色。

- [ ] **Step 3: 自检仓库说明文档**

检查是否满足：

```text
1. 新开发者知道优先看哪些目录
2. 主线和历史模块边界明确
3. 依赖和数据目录解释清楚
4. 协作约定不与 .gitignore 口径冲突
```

- [ ] **Step 4: 提交仓库说明变更**

```bash
git add docs/repository-guide.md
git commit -m "docs: add repository guide"
```

### Task 3: 统一文档导航并整体校验

**Files:**
- Modify: `README.md`
- Create: `docs/repository-guide.md`

- [ ] **Step 1: 统一交叉链接**

确保 README 能跳到仓库说明、当前状态、历史模块和脚本说明文档。

- [ ] **Step 2: 检查口径一致性**

人工核对以下事实：

```text
- 当前主线是本地单用户选股与研究控制台
- 当前主入口是 frontend-console/、src/rolling_snowball/ 与 console 启动脚本
- 历史模块包括日报链路与旧版股票评估原型
- .env、日志、PID、缓存不应进入仓库
```

- [ ] **Step 3: 查看最终变更**

运行：

```bash
git diff -- README.md docs/repository-guide.md
```

预期：只包含文档变更，无功能代码改动。

