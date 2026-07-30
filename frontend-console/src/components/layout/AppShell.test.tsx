import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { AppShell } from '@/components/layout/AppShell'

describe('AppShell', () => {
  it('renders title, subtitle, navigation label, and action slot', () => {
    render(
      <MemoryRouter>
        <AppShell title="重点观察池" subtitle="先看本次 run 的结论" actions={<button>查看列表</button>}>
          <div>content</div>
        </AppShell>
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '重点观察池' })).toBeInTheDocument()
    expect(screen.getByText('先看本次 run 的结论')).toBeInTheDocument()
    expect(screen.getByText('Rolling Snowball')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: '主导航' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '查看列表' })).toBeInTheDocument()
    expect(screen.getByText('content')).toBeInTheDocument()
  })
})
