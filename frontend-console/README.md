# Rolling Snowball Frontend Console

这是 rolling-snowball 项目的 React 前端控制台，负责承接结果查询、任务中心、历史运行和规则实验台。

## 本地开发

在仓库根目录已经有一键启动脚本：

```bash
bash scripts/start_console_stack.sh --open
```

如果只想单独启动前端：

```bash
cd /Users/user/Documents/personal/rolling-snowball/frontend-console
/opt/homebrew/bin/node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4178
```

默认开发地址：

- `http://127.0.0.1:4178`

默认会把 `/api` 代理到：

- `http://127.0.0.1:8780`

## 常用命令

如果你的 `node` / `npm` 已在 PATH 里：

```bash
npm run dev
npm run check
npm run test
npm run lint
```

如果本机 `node` 不在 PATH，可以直接使用本地安装路径运行：

```bash
/opt/homebrew/bin/node node_modules/typescript/bin/tsc -b --noEmit
/opt/homebrew/bin/node node_modules/vitest/vitest.mjs run
/opt/homebrew/bin/node node_modules/eslint/bin/eslint.js .
```

## 页面结构

- `src/pages/Home.tsx`：首页
- `src/pages/StocksPage.tsx`：股票列表
- `src/pages/IndustriesPage.tsx`：行业看板
- `src/pages/StockDetailPage.tsx`：个股详情
- `src/pages/TaskPage.tsx`：任务中心
- `src/pages/RunsPage.tsx`：历史运行
- `src/pages/LabPage.tsx`：规则实验台
