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
      expect(screen.getByText('美的集团')).toBeInTheDocument()
      expect(screen.getByText('run-demo-001')).toBeInTheDocument()
      const keyWatchLinks = screen.getAllByRole('link', { name: '重点观察池' })
      expect(keyWatchLinks.some((link) => link.getAttribute('href') === '/stocks?run=run-demo-001&pool=%E9%87%8D%E7%82%B9%E8%A7%82%E5%AF%9F%E6%B1%A0')).toBe(true)
      expect(screen.getByRole('link', { name: '仅已过滤' })).toHaveAttribute('href', '/stocks?run=run-demo-001&filtered=true')
    })
  })
})
