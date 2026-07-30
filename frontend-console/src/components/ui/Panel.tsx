import clsx from 'clsx'

type PanelProps = {
  title?: string
  eyebrow?: string
  className?: string
  children: React.ReactNode
}

export function Panel({ title, eyebrow, className, children }: PanelProps) {
  return (
    <section
      className={clsx(
        'rounded-[28px] border border-white/10 bg-slate-950/70 p-6 shadow-[0_24px_80px_rgba(0,0,0,0.28)] backdrop-blur-xl',
        className,
      )}
    >
      {(eyebrow || title) && (
        <div className="mb-5 flex flex-col gap-2">
          {eyebrow ? (
            <span className="text-[11px] font-semibold uppercase tracking-[0.3em] text-cyan-200/70">{eyebrow}</span>
          ) : null}
          {title ? <h2 className="font-serif text-2xl text-white">{title}</h2> : null}
        </div>
      )}
      {children}
    </section>
  )
}
