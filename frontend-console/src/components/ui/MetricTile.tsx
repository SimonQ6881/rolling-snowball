type MetricTileProps = {
  label: string
  value: string
  hint?: string
}

export function MetricTile({ label, value, hint }: MetricTileProps) {
  return (
    <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-4">
      <p className="text-xs uppercase tracking-[0.22em] text-slate-400">{label}</p>
      <p className="mt-3 font-serif text-3xl text-white">{value}</p>
      {hint ? <p className="mt-2 text-sm text-slate-400">{hint}</p> : null}
    </div>
  )
}
