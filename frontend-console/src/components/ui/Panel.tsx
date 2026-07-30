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
        'rounded-[28px] border border-slate-200/70 bg-white/78 p-6 shadow-[0_20px_48px_rgba(15,23,42,0.07)] backdrop-blur-xl',
        className,
      )}
    >
      {(eyebrow || title) && (
        <div className="mb-5 flex flex-col gap-2">
          {eyebrow ? (
            <span className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-500">{eyebrow}</span>
          ) : null}
          {title ? <h2 className="font-serif text-2xl text-slate-950">{title}</h2> : null}
        </div>
      )}
      {children}
    </section>
  )
}
