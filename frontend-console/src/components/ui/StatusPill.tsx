import clsx from 'clsx'

type StatusPillProps = {
  tone?: 'emerald' | 'amber' | 'slate' | 'rose' | 'cyan'
  children: React.ReactNode
}

const toneClassMap = {
  emerald: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200',
  amber: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
  slate: 'border-white/10 bg-white/5 text-slate-200',
  rose: 'border-rose-400/30 bg-rose-400/10 text-rose-200',
  cyan: 'border-cyan-400/30 bg-cyan-400/10 text-cyan-200',
}

export function StatusPill({ tone = 'slate', children }: StatusPillProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em]',
        toneClassMap[tone],
      )}
    >
      {children}
    </span>
  )
}
