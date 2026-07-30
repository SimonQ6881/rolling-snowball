import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import StockDetailPage from '@/pages/StockDetailPage'

vi.mock('@/api/console', () => ({
  getLatestRun: vi.fn(),
  getStockDetail: vi.fn(),
  getStockPeers: vi.fn(),
}))

const { getLatestRun, getStockDetail, getStockPeers } = await import('@/api/console')

describe('StockDetailPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders research-oriented stock detail view', async () => {
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
    vi.mocked(getStockDetail).mockResolvedValue({
      run_id: 'run-demo-001',
      ts_code: '000333.SZ',
      stock_name: '美的集团',
      sw_level1_industry: '家用电器',
      current_pool: '重点观察池',
      total_score: 91.2,
      industry_rank: 1,
      industry_total: 32,
      global_rank: 2,
      warning_tags: ['warn_cash_to_short_debt_lt'],
      is_filtered: false,
      latest_report_period: '2026Q1',
      audit_opinion: '标准无保留意见',
      biz_quality_score: 93,
      growth_delivery_score: 88,
      financial_quality_score: 90,
      valuation_fit_score: 85,
      filter_reasons: [],
      data_version: '20260730',
      rule_version: 'v1.0',
      pe_ttm: 12.3,
      pb_latest: 2.1,
      dividend_yield_avg_3y: 0.045,
      gross_margin_avg_3y: 0.24,
      roe_avg_3y: 0.22,
      net_margin_avg_3y: 0.09,
      revenue_cagr_3y: 0.11,
      nonrec_np_cagr_3y: 0.13,
      shareholder_return_ratio_3y: 0.08,
      cash_conversion_ratio_3y: 0.95,
      asset_liability_ratio_latest: 0.61,
      market: 'SZ',
    })
    vi.mocked(getStockPeers).mockResolvedValue({
      target: {
        run_id: 'run-demo-001',
        ts_code: '000333.SZ',
        stock_name: '美的集团',
        sw_level1_industry: '家用电器',
        current_pool: '重点观察池',
        total_score: 91.2,
        industry_rank: 1,
        industry_total: 32,
        global_rank: 2,
        warning_tags: [],
        is_filtered: false,
      },
      peers: [
        {
          ts_code: '000651.SZ',
          stock_name: '格力电器',
          sw_level1_industry: '家用电器',
          total_score: 86.4,
          current_pool: '观察池',
          global_rank: 12,
          industry_rank: 2,
          biz_quality_score: 89,
          growth_delivery_score: 80,
          financial_quality_score: 87,
          valuation_fit_score: 82,
        },
      ],
    })

    render(
      <MemoryRouter initialEntries={['/stocks/000333.SZ?run=run-demo-001']}>
        <Routes>
          <Route path="/stocks/:tsCode" element={<StockDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('总分')).toBeInTheDocument()
      expect(screen.getAllByText(/当前池子|已过滤/).length).toBeGreaterThan(0)
      expect(screen.getByRole('heading', { name: '为什么在这里' })).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: '硬过滤、预警与研究提示' })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: '返回股票列表' })).toHaveAttribute('href', '/stocks?run=run-demo-001&industry=%E5%AE%B6%E7%94%A8%E7%94%B5%E5%99%A8')
      expect(screen.getByText('格力电器')).toBeInTheDocument()
    })
  })
})
