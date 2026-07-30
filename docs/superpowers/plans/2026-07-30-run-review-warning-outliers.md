# Run Review Warning Outliers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `Run 质量总览` 页面补出“高分但 warning 多”的异常股票清单，帮助用户快速定位需要人工复核的高分样本。

**Architecture:** 后端在 `console_service` 中新增一个按 `run_id` 聚合的异常清单查询，并把结果并入现有 `/api/runs/{run_id}/review` 返回体。前端继续复用 `RunReviewPage`，在质量概览下方新增一个异常股票区块，展示股票、池子、总分、warning 数量与标签，并提供跳转到股票详情页的入口。

**Tech Stack:** Python、PostgreSQL、React、TypeScript、Vitest

---

### Task 1: 扩展前端测试以描述新行为

**Files:**
- Modify: `frontend-console/src/pages/RunReviewPage.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
expect(screen.getByText('高分但 warning 多')).toBeInTheDocument()
expect(screen.getByText('美的集团')).toBeInTheDocument()
expect(screen.getByText('已入重点观察池，但有 3 个 warning，建议先复核再下判断。')).toBeInTheDocument()
expect(screen.getByRole('link', { name: '查看个股详情' })).toHaveAttribute('href', '/stocks/000333.SZ?run=run-demo-001')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"/opt/homebrew/bin/node" node_modules/vitest/vitest.mjs run frontend-console/src/pages/RunReviewPage.test.tsx`
Expected: FAIL，因为页面还没有“高分但 warning 多”区块。

### Task 2: 扩展 review 数据模型

**Files:**
- Modify: `frontend-console/src/types/console.ts`

- [ ] **Step 1: Write minimal implementation**

```ts
export type RunWarningOutlierItem = {
  ts_code: string
  stock_name: string
  sw_level1_industry: string
  current_pool: PoolType
  total_score: number | null
  global_rank: number | null
  warning_tags: string[]
  warning_count: number
}
```

- [ ] **Step 2: Extend the overview payload**

```ts
export type RunQualityOverview = {
  run_summary: RunSummary
  metrics: RunReviewMetrics
  top_warning_tags: RunWarningTagSummary[]
  industries: RunIndustryReviewItem[]
  warning_outliers: RunWarningOutlierItem[]
}
```

### Task 3: 扩展后端 review 查询

**Files:**
- Modify: `src/rolling_snowball/console_service.py`

- [ ] **Step 1: Write minimal query**

```python
outlier_sql = """
    SELECT
        ts_code,
        stock_name,
        sw_level1_industry,
        current_pool,
        total_score,
        global_rank,
        warning_tags,
        jsonb_array_length(warning_tags) AS warning_count
    FROM stock_run_scores
    WHERE run_id = %s
      AND is_filtered = false
      AND jsonb_array_length(warning_tags) > 0
    ORDER BY warning_count DESC, total_score DESC NULLS LAST, global_rank ASC NULLS LAST, ts_code ASC
    LIMIT 20
"""
```

- [ ] **Step 2: Return it from the overview payload**

```python
"warning_outliers": warning_outliers,
```

- [ ] **Step 3: Run backend syntax verification**

Run: `python3 -m py_compile src/rolling_snowball/console_service.py src/rolling_snowball/console_server.py`
Expected: PASS

### Task 4: 在 RunReviewPage 展示异常清单

**Files:**
- Modify: `frontend-console/src/pages/RunReviewPage.tsx`

- [ ] **Step 1: Add helper for anomaly copy**

```tsx
function getWarningOutlierMessage(warningCount: number, currentPool: string | null) {
  const poolLabel = currentPool || '观察池'
  return `已入${poolLabel}，但有 ${warningCount} 个 warning，建议先复核再下判断。`
}
```

- [ ] **Step 2: Render the section**

```tsx
<Panel eyebrow="异常样本" title="高分但 warning 多">
  ...
</Panel>
```

- [ ] **Step 3: Link to stock detail**

```tsx
to={{ pathname: `/stocks/${item.ts_code}`, search: createSearchParams({ run: overview.run_summary.run_id }).toString() }}
```

### Task 5: Run verification

**Files:**
- Modify: `frontend-console/src/pages/RunsPage.test.tsx` (only if needed)
- Test: `frontend-console/src/pages/RunReviewPage.test.tsx`
- Test: `src/rolling_snowball/console_service.py`

- [ ] **Step 1: Run frontend typecheck**

Run: `"/opt/homebrew/bin/node" node_modules/typescript/bin/tsc -b --noEmit`
Expected: PASS

- [ ] **Step 2: Run frontend tests**

Run: `"/opt/homebrew/bin/node" node_modules/vitest/vitest.mjs run`
Expected: PASS

- [ ] **Step 3: Run frontend lint**

Run: `"/opt/homebrew/bin/node" node_modules/eslint/bin/eslint.js .`
Expected: PASS
