import { ArrowRight, ChevronRight, RefreshCcw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, createSearchParams, useSearchParams } from 'react-router-dom'

import { getLatestRun, getRunStocks, getRunSummary } from '@/api/console'
import { AppShell } from '@/components/layout/AppShell'
import { RunSwitcher } from '@/components/layout/RunSwitcher'
import { KeyWatchTable } from '@/components/stocks/KeyWatchTable'
import { MetricTile } from '@/components/ui/MetricTile'
import { Panel } from '@/components/ui/Panel'
import { StatusPill } from '@/components/ui/StatusPill'
import { formatDateTime } from '@/lib/format'
import { useConsoleStore } from '@/store/consoleStore'
import type { RunSummary, StockListItem } from '@/types/console'

export default function Home() {
  const [searchParams] = useSearchParams()
  const [latestRun, setLatestRun] = useState<RunSummary | null>(null)
  const [stocks, setStocks] = useState<StockListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const setSelectedRunId = useConsoleStore((state) => state.setSelectedRunId)
  const runIdFromQuery = searchParams.get('run')

  useEffect(() => {
    let active = true

    async function load() {
      try {
        setLoading(true)
        setError(null)
        const run = runIdFromQuery ? await getRunSummary(runIdFromQuery) : await getLatestRun()
        if (!active) return

        setLatestRun(run)
        setSelectedRunId(run.run_id)

        const response = await getRunStocks(
          run.run_id,
          createSearchParams({
            pool: '重点观察池',
            limit: '20',
          }).toString(),
        )

        if (!active) return
        setStocks(response.items)
      } catch (loadError) {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : '首页加载失败')
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [runIdFromQuery, setSelectedRunId])

  const activeRunId = latestRun?.run_id || runIdFromQuery

  return (
    <AppShell
      title="重点观察池"
      subtitle="默认先看最近一次成功运行的重点观察池，再决定是否切到全股票列表、行业看板或单股详情。"
      actions={
        <>
          <RunSwitcher currentRunId={activeRunId} />
          <Link
            to={{
              pathname: '/stocks',
              search: activeRunId ? createSearchParams({ run: activeRunId }).toString() : '',
            }}
            className="inline-flex items-center gap-2 rounded-full border border-cyan-400/25 bg-cyan-400/10 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:border-cyan-300/40 hover:bg-cyan-300/15"
          >
            查看全股票列表
            <ChevronRight className="h-4 w-4" />
          </Link>
          <Link
            to="/lab"
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08]"
          >
            <RefreshCcw className="h-4 w-4" />
            发起新运行
          </Link>
        </>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[1.45fr_0.85fr]">
        <Panel eyebrow="最新成功运行" title={latestRun ? latestRun.run_id : '正在读取运行摘要…'}>
          {loading ? (
            <div className="grid gap-4 md:grid-cols-2">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="h-28 animate-pulse rounded-[24px] bg-white/[0.05]" />
              ))}
            </div>
          ) : error ? (
            <div className="rounded-[24px] border border-rose-400/20 bg-rose-400/10 p-5 text-sm text-rose-100">{error}</div>
          ) : latestRun ? (
            <div className="grid gap-4 md:grid-cols-2">
              <MetricTile label="运行时间" value={formatDateTime(latestRun.finished_at)} hint={`规则版本 ${latestRun.rule_version}`} />
              <MetricTile
                label="通过硬过滤"
                value={String(latestRun.passed_filter_count ?? '--')}
                hint={`总样本 ${latestRun.total_stocks ?? '--'} 只`}
              />
              <MetricTile label="重点观察池" value={String(latestRun.key_watch_count ?? '--')} hint="按当前规则直接列入重点池" />
              <MetricTile label="观察池" value={String(latestRun.watch_count ?? '--')} hint={`数据版本 ${latestRun.data_version}`} />
            </div>
          ) : null}
        </Panel>

        <Panel eyebrow="快捷入口" title="今天先从哪里看">
          <div className="flex flex-col gap-3">
            {[
              { to: '/runs', title: '历史运行', desc: '回看每次 run 的结果摘要、来源任务与跳转入口。' },
              { to: '/stocks', title: '全股票列表', desc: '查看完整结果、按行业和 warning 标签筛选。' },
              { to: '/industries', title: '行业看板', desc: '从行业视角看分布、均分与重点池数量。' },
              { to: '/lab', title: '规则实验台', desc: '调整硬过滤阈值和评分权重，发起新任务。' },
            ].map((item) => (
              <Link
                key={item.to}
                to={{
                  pathname: item.to,
                  search: item.to === '/lab' || item.to === '/runs' || !activeRunId ? '' : createSearchParams({ run: activeRunId }).toString(),
                }}
                className="group rounded-[24px] border border-white/10 bg-white/[0.03] p-4 transition hover:border-cyan-300/25 hover:bg-cyan-300/[0.06]"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-serif text-xl text-white">{item.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-slate-400">{item.desc}</p>
                  </div>
                  <ArrowRight className="h-5 w-5 text-slate-500 transition group-hover:text-cyan-200" />
                </div>
              </Link>
            ))}
          </div>
          <div className="mt-5 rounded-[24px] border border-cyan-300/15 bg-cyan-300/[0.05] p-4">
            <p className="text-xs uppercase tracking-[0.24em] text-cyan-100/70">高频筛选</p>
            <div className="mt-4 flex flex-wrap gap-3">
              <Link
                to={{
                  pathname: '/stocks',
                  search: activeRunId ? createSearchParams({ run: activeRunId, pool: '重点观察池' }).toString() : '',
                }}
                className="inline-flex rounded-full border border-cyan-300/20 bg-cyan-300/[0.08] px-4 py-2 text-sm font-semibold text-cyan-50 transition hover:border-cyan-200/35 hover:bg-cyan-300/[0.12]"
              >
                重点观察池
              </Link>
              <Link
                to={{
                  pathname: '/stocks',
                  search: activeRunId ? createSearchParams({ run: activeRunId, filtered: 'true' }).toString() : '',
                }}
                className="inline-flex rounded-full border border-white/10 bg-white/[0.05] px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-white/20 hover:bg-white/[0.08]"
              >
                仅已过滤
              </Link>
              <Link
                to={{
                  pathname: '/industries',
                  search: activeRunId ? createSearchParams({ run: activeRunId }).toString() : '',
                }}
                className="inline-flex rounded-full border border-white/10 bg-white/[0.05] px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-white/20 hover:bg-white/[0.08]"
              >
                按行业查看
              </Link>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-400">把最常用的三类入口单独拎出来，少走一步就能开始筛查。</p>
          </div>
        </Panel>
      </div>

      <div className="mt-6">
        <Panel
          eyebrow="默认结果视图"
          title={`重点观察池列表${latestRun ? ` · ${latestRun.run_id.slice(0, 8)}` : ''}`}
          className="overflow-hidden"
        >
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="h-20 animate-pulse rounded-[22px] bg-white/[0.05]" />
              ))}
            </div>
          ) : stocks.length > 0 && latestRun ? (
            <KeyWatchTable stocks={stocks} runId={latestRun.run_id} />
          ) : (
            <div className="rounded-[24px] border border-dashed border-white/10 bg-white/[0.02] p-8 text-center">
              <StatusPill tone="amber">暂无重点观察池结果</StatusPill>
              <p className="mx-auto mt-4 max-w-2xl text-sm leading-7 text-slate-400">
                当前最新运行还没有重点观察池样本。你可以进入规则实验台调整阈值或评分权重，然后重新发起一次运行。
              </p>
            </div>
          )}
        </Panel>
      </div>
    </AppShell>
  )
}
