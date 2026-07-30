import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import LabPage from '@/pages/LabPage'
import type { RuleSnapshot } from '@/types/console'

vi.mock('@/api/console', () => ({
  createRun: vi.fn(),
  getActiveRule: vi.fn(),
  validateRule: vi.fn(),
}))

const { createRun, getActiveRule, validateRule } = await import('@/api/console')

const baseRule: RuleSnapshot = {
  rule_version: 'v1.0',
  hard_filters: {
    liquidity: {
      exclude_market_cap_lt_cny: 5000000000,
      exclude_avg_turnover_20d_lt_cny: 30000000,
    },
    leverage: {
      exclude_asset_liability_ratio_gt: 0.7,
    },
    cashflow: {
      exclude_cash_conversion_ratio_3y_lt: 0.6,
    },
  },
  top_level_weights: {
    biz_quality: 0.3,
    growth_delivery: 0.25,
    financial_quality: 0.25,
    valuation_fit: 0.2,
  },
  score_dimensions: {
    biz_quality: {
      margin: 0.5,
      roe: 0.5,
    },
    growth_delivery: {
      revenue: 0.5,
      profit: 0.5,
    },
  },
  pool_thresholds: {
    key_watch_top_n: 20,
    key_watch_min_score: 80,
  },
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/lab']}>
      <Routes>
        <Route path="/lab" element={<LabPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('LabPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(getActiveRule).mockResolvedValue(baseRule)
    vi.mocked(validateRule).mockImplementation(async (snapshot) => snapshot)
    vi.mocked(createRun).mockResolvedValue({
      task_id: 'task-demo-001',
      run_id: 'run-demo-001',
      task_status: 'queued',
      apply_mode: 'run_once',
      total_count: null,
      done_count: 0,
      failed_count: 0,
      progress_stage: null,
      latest_message: null,
      log_path: null,
      error_message: null,
      created_at: '2026-07-30T08:00:00+08:00',
      started_at: null,
      finished_at: null,
    })
  })

  it('shows clean state first and highlights changed fields', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getAllByText('当前与默认规则一致').length).toBeGreaterThan(0)
      expect(screen.getAllByText('当前字段均合法').length).toBeGreaterThan(0)
    })

    fireEvent.change(screen.getByLabelText('现金转化率下限'), {
      target: { value: '0.75' },
    })

    await waitFor(() => {
      expect(screen.getByText('本次共改动 1 项')).toBeInTheDocument()
      expect(screen.getByText('默认值：0.6')).toBeInTheDocument()
    })
  })

  it('blocks submit and shows inline validation errors for invalid values', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '仅本次生效并运行' })).toBeEnabled()
    })

    fireEvent.change(screen.getByLabelText('现金转化率下限'), {
      target: { value: '1.2' },
    })

    await waitFor(() => {
      expect(screen.getByText('现金转化率下限必须在 0 到 1 之间')).toBeInTheDocument()
      expect(screen.getAllByText('当前有 1 个字段超出合法范围，修正后才能运行').length).toBeGreaterThan(0)
      expect(screen.getByText('当前存在字段越界或输入格式错误，暂时不能发起运行')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '仅本次生效并运行' })).toBeDisabled()
    })
  })

  it('restores valid submit state after correcting invalid value', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '仅本次生效并运行' })).toBeEnabled()
    })

    fireEvent.change(screen.getByLabelText('现金转化率下限'), {
      target: { value: '1.2' },
    })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '仅本次生效并运行' })).toBeDisabled()
    })

    fireEvent.change(screen.getByRole('spinbutton', { name: /现金转化率下限/ }), {
      target: { value: '0.75' },
    })

    await waitFor(() => {
      expect(screen.queryByText('现金转化率下限必须在 0 到 1 之间')).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: '仅本次生效并运行' })).toBeEnabled()
    })
  })

  it('shows soft warning without blocking submit', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '仅本次生效并运行' })).toBeEnabled()
    })

    fireEvent.change(screen.getByLabelText('市值门槛（元）'), {
      target: { value: '0' },
    })

    await waitFor(() => {
      expect(screen.getAllByText('当前市值门槛较低，筛选约束可能偏弱').length).toBeGreaterThan(0)
      expect(screen.getAllByText('当前字段都合法，可以运行').length).toBeGreaterThan(0)
      expect(screen.getByRole('button', { name: '仅本次生效并运行' })).toBeEnabled()
    })
  })

  it('shows structure-specific summary when weights are unbalanced', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '仅本次生效并运行' })).toBeEnabled()
    })

    fireEvent.change(screen.getByLabelText('业务质量权重'), {
      target: { value: '0.4' },
    })

    await waitFor(() => {
      expect(screen.getAllByText('当前权重结构还未平衡，至少有一组权重合计不等于 1').length).toBeGreaterThan(0)
      expect(screen.getAllByText('当前权重结构还未平衡，暂时不能发起运行').length).toBeGreaterThan(0)
      expect(screen.getByRole('button', { name: '仅本次生效并运行' })).toBeDisabled()
    })
  })

  it('restores a changed group back to default', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getAllByText('当前与默认规则一致').length).toBeGreaterThan(0)
    })

    fireEvent.change(screen.getByLabelText('现金转化率下限'), {
      target: { value: '0.75' },
    })

    await waitFor(() => {
      expect(screen.getByText('本次共改动 1 项')).toBeInTheDocument()
    })

    fireEvent.click(screen.getAllByRole('button', { name: '恢复本组默认' })[0])

    await waitFor(() => {
      expect(screen.getAllByText('当前与默认规则一致').length).toBeGreaterThan(0)
    })
  })

  it('shows explicit error when active rule cannot be loaded', async () => {
    vi.mocked(getActiveRule).mockRejectedValue(new Error('规则读取失败'))

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('规则读取失败')).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: '暂时无法加载规则' })).toBeInTheDocument()
    })
  })
})
