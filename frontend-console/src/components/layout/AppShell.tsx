import { BarChart3, Database, FlaskConical, History, LayoutDashboard, ListOrdered } from 'lucide-react'
import { NavLink } from 'react-router-dom'

const links = [
  { to: '/', label: '重点观察池', icon: LayoutDashboard },
  { to: '/runs', label: '历史运行', icon: History },
  { to: '/stocks', label: '全股票列表', icon: ListOrdered },
  { to: '/industries', label: '行业看板', icon: BarChart3 },
  { to: '/lab', label: '规则实验台', icon: FlaskConical },
  { to: '/tasks/latest', label: '任务运行', icon: Database },
]

type AppShellProps = {
  title: string
  subtitle: string
  actions?: React.ReactNode
  children: React.ReactNode
}

export function AppShell({ title, subtitle, actions, children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(148,163,184,0.16),_transparent_24%),linear-gradient(180deg,_#f8fafc_0%,_#eef2f7_100%)] text-slate-900">
      <div className="mx-auto flex min-h-screen max-w-[1520px] gap-6 px-6 py-6">
        <aside className="hidden w-64 shrink-0 rounded-[32px] border border-slate-200/70 bg-white/80 p-6 shadow-[0_24px_60px_rgba(15,23,42,0.08)] backdrop-blur-xl lg:flex lg:flex-col">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.36em] text-slate-500">Rolling Snowball</p>
            <h1 className="mt-4 font-serif text-[28px] text-slate-950">滚雪球研究工作台</h1>
            <p className="mt-3 text-sm leading-6 text-slate-600">先看结果，再做实验。把每次筛选都沉淀为可回看的研究记录。</p>
          </div>

          <nav aria-label="主导航" className="mt-10 flex flex-col gap-2">
            {links.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  [
                    'flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm font-medium transition',
                    isActive
                      ? 'border-slate-200 bg-slate-950 text-white shadow-[0_18px_30px_rgba(15,23,42,0.14)]'
                      : 'border-transparent bg-slate-100/70 text-slate-600 hover:border-slate-200 hover:bg-white hover:text-slate-900',
                  ].join(' ')
                }
              >
                <Icon className="h-4 w-4" />
                {label}
              </NavLink>
            ))}
          </nav>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col gap-6">
          <header className="rounded-[32px] border border-white/70 bg-white/78 px-7 py-6 shadow-[0_24px_60px_rgba(15,23,42,0.08)] backdrop-blur-xl">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-slate-500">本地研究工作台</p>
                <h2 className="mt-3 font-serif text-4xl text-slate-950">{title}</h2>
                <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">{subtitle}</p>
              </div>
              {actions ? <div className="flex flex-wrap items-center gap-3">{actions}</div> : null}
            </div>
          </header>

          <main className="min-w-0 flex-1">{children}</main>
        </div>
      </div>
    </div>
  )
}
