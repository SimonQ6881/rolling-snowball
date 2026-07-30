import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Home from '@/pages/Home'

vi.mock('@/api/console', () => ({
  getLatestRun: vi.fn(),
  getRunList: vi.fn(),
  getRunSummary: vi.fn(),
  getRunStocks: vi.fn(),
}))

const { getLatestRun, getRunList, getRunStocks } = await import('@/api/console')

describe('Home', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders latest run summary and key watch stocks', async () => {
    vi.mocked(getRunList).mockResolvedValue({
      items: [],
    })
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
    vi.mocked(getRunStocks).mockResolvedValue({
      items: [
        {
          run_id: 'run-demo-001',
          ts_code: '000333.SZ',
          stock_name: '美的集团',
          sw_level1_industry: '家用电器',
          current_pool: '重点观察池',
          total_score: 81.83,
          industry_rank: 1,
          industry_total: 20,
          global_rank: 1,
          warning_tags: [],
          is_filtered: false,
        },
      ],
    })

    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: '重点观察池' })).toBeInTheDocument()
      expect(screen.getByText('本次最值得优先看的 run 结果与研究入口。')).toBeInTheDocument()
      expect(screen.getByText('美的集团')).toBeInTheDocument()
      expect(screen.getByRole('link', { name: '查看全股票列表' })).toHaveAttribute('href', '/stocks?run=run-demo-001')
      expect(screen.getByText('先看这次最值得研究的 20 只')).toBeInTheDocument()
    })
  })
})
