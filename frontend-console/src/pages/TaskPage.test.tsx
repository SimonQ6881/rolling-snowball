import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import TaskPage from '@/pages/TaskPage'
import type { RuleSnapshot } from '@/types/console'

vi.mock('@/api/console', () => ({
  getRunSummary: vi.fn(),
  getTask: vi.fn(),
  getTaskList: vi.fn(),
  getTaskLogs: vi.fn(),
}))

const { getRunSummary, getTask, getTaskList, getTaskLogs } = await import('@/api/console')

const ruleSnapshot: RuleSnapshot = {
  rule_version: 'v1.0',
  hard_filters: {
    liquidity: {
      exclude_market_cap_lt_cny: 3000000000,
      exclude_avg_turnover_20d_lt_cny: 50000000,
    },
    leverage: {
      exclude_asset_liability_ratio_gt: 0.65,
    },
    cashflow: {
      exclude_cash_conversion_ratio_3y_lt: 0.8,
    },
  },
  score_dimensions: {
    biz_quality: {
      gross_margin: 0.3,
      roe_avg_3y: 0.3,
      net_margin_avg_3y: 0.2,
      industry_position: 0.2,
    },
    growth_delivery: {
      revenue_cagr_3y: 0.35,
      nonrec_np_cagr_3y: 0.35,
      shareholder_return_ratio_3y: 0.3,
    },
    financial_quality: {
      cash_conversion_ratio_3y: 0.4,
      asset_liability_ratio_latest: 0.3,
      capital_return_stability: 0.3,
    },
    valuation_fit: {
      pe_ttm: 0.4,
      pb_latest: 0.3,
      dividend_yield_avg_3y: 0.3,
    },
  },
  top_level_weights: {
    biz_quality: 0.3,
    growth_delivery: 0.25,
    financial_quality: 0.25,
    valuation_fit: 0.2,
  },
  pool_thresholds: {
    key_watch_top_n: 20,
    key_watch_min_score: 0,
  },
}

describe('TaskPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders recent task list and selected task detail', async () => {
    vi.mocked(getTaskList).mockResolvedValue({
      items: [
        {
          task_id: 'task-demo-001',
          run_id: 'run-demo-001',
          task_status: 'success',
          apply_mode: 'run_once',
          total_count: 100,
          done_count: 100,
          failed_count: 0,
          progress_stage: 'finished',
          latest_message: '运行完成',
          log_path: '/tmp/task-demo-001.log',
          error_message: null,
          created_at: '2026-07-30T08:00:00+08:00',
          started_at: '2026-07-30T08:00:05+08:00',
          finished_at: '2026-07-30T08:06:00+08:00',
        },
      ],
    })
    vi.mocked(getTask).mockResolvedValue({
      task_id: 'task-demo-001',
      run_id: 'run-demo-001',
      task_status: 'success',
      apply_mode: 'run_once',
      total_count: 100,
      done_count: 100,
      failed_count: 0,
      progress_stage: 'finished',
      latest_message: '运行完成',
      log_path: '/tmp/task-demo-001.log',
      error_message: null,
      requested_rule_snapshot: ruleSnapshot,
      created_at: '2026-07-30T08:00:00+08:00',
      started_at: '2026-07-30T08:00:05+08:00',
      finished_at: '2026-07-30T08:06:00+08:00',
    })
    vi.mocked(getRunSummary).mockResolvedValue({
      run_id: 'run-demo-001',
      rule_version: 'v1.0',
      data_version: '20260730',
      run_status: 'success',
      total_stocks: 100,
      passed_filter_count: 23,
      key_watch_count: 20,
      watch_count: 3,
      started_at: '2026-07-30T08:00:00+08:00',
      finished_at: '2026-07-30T08:05:00+08:00',
      apply_mode: 'run_once',
      rule_snapshot: ruleSnapshot,
    })
    vi.mocked(getTaskLogs).mockResolvedValue({
      items: ['[2026-07-30 08:06:00] 运行完成'],
    })

    render(
      <MemoryRouter initialEntries={['/tasks/latest']}>
        <Routes>
          <Route path="/tasks/:taskId" element={<TaskPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: '任务运行' })).toBeInTheDocument()
      expect(screen.getByText('最近 1 条')).toBeInTheDocument()
      expect(screen.getByText('状态与结果入口')).toBeInTheDocument()
      expect(screen.getByText('task-demo-001')).toBeInTheDocument()
      expect(screen.getByText('最近任务 · task-demo-001')).toBeInTheDocument()
      expect(screen.getByRole('link', { name: '打开首页摘要' })).toHaveAttribute('href', '/?run=run-demo-001')
      expect(screen.getByRole('link', { name: '打开股票列表' })).toHaveAttribute('href', '/stocks?run=run-demo-001')
      expect(screen.getByRole('heading', { name: '本次 run 摘要' })).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: '执行日志' })).toBeInTheDocument()
      expect(screen.getByText('通过硬过滤')).toBeInTheDocument()
      expect(screen.getByText('以下参数就是这次 run 实际使用的规则快照。')).toBeInTheDocument()
      expect(screen.getByText('重点观察池名额')).toBeInTheDocument()
      expect(screen.getByText('临时运行')).toBeInTheDocument()
      expect(screen.getByText('[2026-07-30 08:06:00] 运行完成')).toBeInTheDocument()
    })
  })
})
