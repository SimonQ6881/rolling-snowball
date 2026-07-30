import { ArrowRight, CircleAlert } from 'lucide-react'
import { Link, createSearchParams } from 'react-router-dom'

import { StatusPill } from '@/components/ui/StatusPill'
import type { StockListItem } from '@/types/console'

type KeyWatchTableProps = {
  stocks: StockListItem[]
  runId: string
}

function buildDetailHref(runId: string, tsCode: string) {
  return {
    pathname: `/stocks/${tsCode}`,
    search: createSearchParams({ run: runId }).toString(),
  }
}

export function KeyWatchTable({ stocks, runId }: KeyWatchTableProps) {
  return (
    <div className="overflow-hidden rounded-[26px] border border-white/10 bg-black/10">
      <div className="grid grid-cols-[1.1fr_1.4fr_1.1fr_0.8fr_0.9fr_1.2fr] gap-4 border-b border-white/10 px-5 py-4 text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-400">
        <span>股票</span>
        <span>行业</span>
        <span>总分</span>
        <span>排名</span>
        <span>状态</span>
        <span className="text-right">动作</span>
      </div>
      <div className="divide-y divide-white/5">
        {stocks.map((stock) => (
          <div
            key={stock.ts_code}
            className="grid grid-cols-[1.1fr_1.4fr_1.1fr_0.8fr_0.9fr_1.2fr] gap-4 px-5 py-5 text-sm text-slate-200 transition hover:bg-white/[0.03]"
          >
            <div>
              <p className="font-semibold text-white">{stock.stock_name}</p>
              <p className="mt-1 text-xs uppercase tracking-[0.22em] text-slate-500">{stock.ts_code}</p>
            </div>
            <div className="flex min-w-0 flex-col gap-2">
              <span className="truncate text-slate-200">{stock.sw_level1_industry}</span>
              <div className="flex flex-wrap gap-2">
                {stock.warning_tags.slice(0, 2).map((tag) => (
                  <StatusPill key={tag} tone="slate">
                    {tag}
                  </StatusPill>
                ))}
              </div>
            </div>
            <div className="font-serif text-3xl text-white">{stock.total_score?.toFixed(2) || '--'}</div>
            <div className="text-slate-300">
              {stock.industry_rank && stock.industry_total ? `${stock.industry_rank}/${stock.industry_total}` : '--'}
            </div>
            <div>
              {stock.is_filtered ? (
                <StatusPill tone="rose">
                  <CircleAlert className="h-3 w-3" />
                  已过滤
                </StatusPill>
              ) : (
                <StatusPill tone={stock.current_pool === '重点观察池' ? 'emerald' : 'amber'}>{stock.current_pool || '观察池'}</StatusPill>
              )}
            </div>
            <div className="flex justify-end">
              <Link
                to={buildDetailHref(runId, stock.ts_code)}
                className="inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.24em] text-cyan-100 transition hover:border-cyan-300/40 hover:bg-cyan-300/15"
              >
                查看详情
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
