import clsx from 'clsx'

type StatusPillProps = {
  tone?: 'emerald' | 'amber' | 'slate' | 'rose' | 'cyan'
  children: React.ReactNode
}

const toneClassMap = {
  emerald: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  amber: 'border-amber-200 bg-amber-50 text-amber-700',
  slate: 'border-slate-200 bg-slate-100 text-slate-700',
  rose: 'border-rose-200 bg-rose-50 text-rose-700',
  cyan: 'border-sky-200 bg-sky-50 text-sky-700',
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
