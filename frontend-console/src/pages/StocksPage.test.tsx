import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import StocksPage from '@/pages/StocksPage'

vi.mock('@/api/console', () => ({
  getLatestRun: vi.fn(),
  getRunList: vi.fn(),
  getRunSummary: vi.fn(),
  getRunStocks: vi.fn(),
}))

const { getLatestRun, getRunList, getRunStocks, getRunSummary } = await import('@/api/console')

describe('StocksPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('passes industry filter from url and renders filtered list', async () => {
    vi.mocked(getRunList).mockResolvedValue({
      items: [],
    })
    vi.mocked(getLatestRun).mockResolvedValue({
      run_id: 'run-demo-002',
      rule_version: 'v1.0',
      data_version: '20260730',
      run_status: 'success',
      total_stocks: 100,
      passed_filter_count: 20,
      key_watch_count: 5,
      watch_count: 15,
      started_at: '2026-07-30T08:00:00+08:00',
      finished_at: '2026-07-30T08:05:00+08:00',
    })
    vi.mocked(getRunSummary).mockResolvedValue({
      run_id: 'run-demo-002',
      rule_version: 'v1.0',
      data_version: '20260730',
      run_status: 'success',
      total_stocks: 100,
      passed_filter_count: 20,
      key_watch_count: 5,
      watch_count: 15,
      started_at: '2026-07-30T08:00:00+08:00',
      finished_at: '2026-07-30T08:05:00+08:00',
    })
    vi.mocked(getRunStocks).mockResolvedValue({
      items: [
        {
          run_id: 'run-demo-002',
          ts_code: '000021.SZ',
          stock_name: '深科技',
          sw_level1_industry: '电子',
          current_pool: '重点观察池',
          total_score: 64.69,
          industry_rank: 1,
          industry_total: 2,
          global_rank: 1,
          warning_tags: [],
          is_filtered: false,
        },
      ],
    })

    render(
      <MemoryRouter initialEntries={['/stocks?run=run-demo-002&industry=电子']}>
        <Routes>
          <Route path="/stocks" element={<StocksPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(getRunStocks).toHaveBeenCalledWith('run-demo-002', expect.stringContaining('industry=%E7%94%B5%E5%AD%90'))
      expect(screen.getByText('深科技')).toBeInTheDocument()
      expect(screen.getByText('行业 电子')).toBeInTheDocument()
    })
  })

  it('shows missing historical detail hint for old runs without stock rows', async () => {
    vi.mocked(getRunList).mockResolvedValue({
      items: [],
    })
    vi.mocked(getLatestRun).mockResolvedValue({
      run_id: 'run-demo-003',
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
    vi.mocked(getRunSummary).mockResolvedValue({
      run_id: 'run-demo-003',
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
      items: [],
    })

    render(
      <MemoryRouter initialEntries={['/stocks?run=run-demo-003']}>
        <Routes>
          <Route path="/stocks" element={<StocksPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/这次 `run` 有汇总结果，但没有逐股历史明细/)).toBeInTheDocument()
    })
  })
})
