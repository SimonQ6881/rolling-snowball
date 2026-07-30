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
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(76,213,161,0.12),_transparent_28%),linear-gradient(180deg,_#09131f_0%,_#07101a_100%)] text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-[1500px] gap-6 px-6 py-8">
        <aside className="hidden w-64 shrink-0 rounded-[32px] border border-white/10 bg-slate-950/70 p-6 backdrop-blur-xl lg:flex lg:flex-col">
          <div>
            <p className="text-[11px] uppercase tracking-[0.38em] text-cyan-200/80">Rolling Snowball</p>
            <h1 className="mt-4 font-serif text-3xl text-white">滚雪球控制台</h1>
            <p className="mt-3 text-sm leading-6 text-slate-400">先看结果，再做实验。把每次筛选都沉淀为可回看的研究记录。</p>
          </div>

          <nav className="mt-10 flex flex-col gap-2">
            {links.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  [
                    'flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm transition',
                    isActive
                      ? 'border-cyan-400/30 bg-cyan-300/10 text-white shadow-[0_10px_30px_rgba(34,211,238,0.12)]'
                      : 'border-transparent bg-white/[0.03] text-slate-300 hover:border-white/10 hover:bg-white/[0.05]',
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
          <header className="rounded-[30px] border border-white/10 bg-slate-950/60 px-6 py-5 backdrop-blur-xl">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
              <div>
                <p className="text-[11px] uppercase tracking-[0.36em] text-cyan-200/70">本地研究工作台</p>
                <h2 className="mt-3 font-serif text-4xl text-white">{title}</h2>
                <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">{subtitle}</p>
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
