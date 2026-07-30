type MetricTileProps = {
  label: string
  value: string
  hint?: string
}

export function MetricTile({ label, value, hint }: MetricTileProps) {
  return (
    <div className="rounded-[24px] border border-slate-200/70 bg-slate-50/85 p-4 shadow-[0_16px_32px_rgba(15,23,42,0.05)]">
      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">{label}</p>
      <p className="mt-3 font-serif text-3xl text-slate-950">{value}</p>
      {hint ? <p className="mt-2 text-sm text-slate-600">{hint}</p> : null}
    </div>
  )
}
