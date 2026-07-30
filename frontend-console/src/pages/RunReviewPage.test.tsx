import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import RunReviewPage from '@/pages/RunReviewPage'

vi.mock('@/api/console', () => ({
  getLatestRun: vi.fn(),
  getRunList: vi.fn(),
  getRunQualityOverview: vi.fn(),
}))

const { getLatestRun, getRunList, getRunQualityOverview } = await import('@/api/console')

describe('RunReviewPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders run quality overview', async () => {
    vi.mocked(getLatestRun).mockResolvedValue({
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
    })
    vi.mocked(getRunList).mockResolvedValue({
      items: [
        {
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
        },
      ],
    })
    vi.mocked(getRunQualityOverview).mockResolvedValue({
      run_summary: {
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
      },
      metrics: {
        total_stocks: 100,
        passed_filter_count: 23,
        filtered_count: 77,
        key_watch_count: 20,
        watch_count: 3,
        warning_stock_count: 18,
        manual_review_count: 6,
        data_missing_count: 2,
        avg_warning_tags_per_stock: 0.31,
        avg_total_score: 71.5,
        pass_rate: 0.23,
        filtered_rate: 0.77,
        key_watch_rate: 0.2,
        watch_rate: 0.03,
        warning_stock_rate: 0.18,
        manual_review_rate: 0.06,
        data_missing_rate: 0.02,
      },
      top_warning_tags: [
        { warning_tag: 'manual_review', stock_count: 6 },
        { warning_tag: 'data_missing', stock_count: 2 },
      ],
      warning_outliers: [
        {
          ts_code: '000333.SZ',
          stock_name: '美的集团',
          sw_level1_industry: '家用电器',
          current_pool: '重点观察池',
          total_score: 88.6,
          global_rank: 1,
          warning_tags: ['manual_review', 'data_missing', 'cash_conversion_ratio_below_0_6'],
          warning_count: 3,
        },
      ],
      industries: [
        {
          sw_level1_industry: '家用电器',
          stock_count: 8,
          passed_count: 4,
          key_watch_count: 3,
          watch_count: 1,
          warning_stock_count: 1,
          avg_total_score: 78.3,
        },
      ],
    })

    render(
      <MemoryRouter initialEntries={['/run-review?run=run-demo-001']}>
        <Routes>
          <Route path="/run-review" element={<RunReviewPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Run 质量总览')).toBeInTheDocument()
      expect(screen.getByText('最常见的人工复核信号')).toBeInTheDocument()
      expect(screen.getByText('manual_review')).toBeInTheDocument()
      expect(screen.getByText('高分但 warning 多')).toBeInTheDocument()
      expect(screen.getByText('美的集团')).toBeInTheDocument()
      expect(screen.getByText('已入重点观察池，但有 3 个 warning，建议先复核再下判断。')).toBeInTheDocument()
      expect(screen.getAllByText('家用电器').length).toBeGreaterThan(0)
      expect(screen.getByRole('link', { name: '查看股票列表' })).toHaveAttribute('href', '/stocks?run=run-demo-001')
      expect(screen.getByRole('link', { name: '查看个股详情' })).toHaveAttribute('href', '/stocks/000333.SZ?run=run-demo-001')
    })
  })
})
