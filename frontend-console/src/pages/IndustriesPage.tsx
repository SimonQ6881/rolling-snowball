import { useEffect, useMemo, useState } from 'react'
import { Link, createSearchParams, useSearchParams } from 'react-router-dom'

import { getIndustryBoard, getLatestRun } from '@/api/console'
import { AppShell } from '@/components/layout/AppShell'
import { RunSwitcher } from '@/components/layout/RunSwitcher'
import { MetricTile } from '@/components/ui/MetricTile'
import { Panel } from '@/components/ui/Panel'
import { StatusPill } from '@/components/ui/StatusPill'
import { formatScore } from '@/lib/format'
import { useConsoleStore } from '@/store/consoleStore'
import type { IndustrySummary } from '@/types/console'

export default function IndustriesPage() {
  const [searchParams] = useSearchParams()
  const [industries, setIndustries] = useState<IndustrySummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const selectedRunId = useConsoleStore((state) => state.selectedRunId)
  const setSelectedRunId = useConsoleStore((state) => state.setSelectedRunId)
  const runIdFromQuery = searchParams.get('run')

  useEffect(() => {
    let active = true

    async function load() {
      try {
        setLoading(true)
        setError(null)
        const runId = runIdFromQuery || selectedRunId || (await getLatestRun()).run_id
        if (!active) return
        setSelectedRunId(runId)
        const response = await getIndustryBoard(runId)
        if (!active) return
        setIndustries(response.items)
      } catch (loadError) {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : '行业看板加载失败')
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [runIdFromQuery, selectedRunId, setSelectedRunId])

  const activeRunId = runIdFromQuery || selectedRunId
  const totals = useMemo(() => {
    const totalStocks = industries.reduce((sum, industry) => sum + industry.stock_count, 0)
    const totalKeyWatch = industries.reduce((sum, industry) => sum + industry.key_watch_count, 0)
    const topIndustry = [...industries].sort((left, right) => (right.avg_total_score ?? -1) - (left.avg_total_score ?? -1))[0] || null

    return {
      totalStocks,
      totalKeyWatch,
      topIndustry,
    }
  }, [industries])

  return (
    <AppShell
      title="行业看板"
      subtitle="先看行业分布摘要，再决定回到全量列表还是继续下钻。"
      actions={
        <>
          <RunSwitcher currentRunId={activeRunId} />
          <Link
            to={{
              pathname: '/stocks',
              search: createSearchParams(
                Object.fromEntries(
                  Object.entries({
                    run: activeRunId || '',
                  }).filter(([, value]) => value),
                ),
              ).toString(),
            }}
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
          >
            查看股票列表
          </Link>
        </>
      }
    >
      <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <Panel eyebrow="Run Context" title="这次 run 的行业摘要">
          <div className="grid gap-4 sm:grid-cols-2">
            <MetricTile label="行业数" value={loading ? '--' : String(industries.length)} hint="当前 run 覆盖的申万一级行业" />
            <MetricTile label="覆盖股票" value={loading ? '--' : String(totals.totalStocks)} hint="行业看板对应的总股票数" />
            <MetricTile label="重点池样本" value={loading ? '--' : String(totals.totalKeyWatch)} hint="行业层面的重点池总量" />
            <MetricTile
              label="最高均分行业"
              value={loading ? '--' : totals.topIndustry?.sw_level1_industry || '--'}
              hint={totals.topIndustry ? `均分 ${formatScore(totals.topIndustry.avg_total_score)}` : '等待行业数据'}
            />
          </div>
          <div className="mt-5 rounded-[24px] border border-slate-200/70 bg-slate-50/85 p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">阅读建议</p>
            <p className="mt-3 text-sm leading-7 text-slate-600">
              先看高均分行业与重点池是否集中，再决定回到股票列表逐只展开，能更快判断这次 run 是结构性机会还是个别样本突出。
            </p>
          </div>
        </Panel>

        <Panel eyebrow="Industry Board" title="从行业视角回看这次 run">
          {loading ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="h-40 animate-pulse rounded-[24px] bg-slate-100" />
              ))}
            </div>
          ) : error ? (
            <div className="rounded-[24px] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">{error}</div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {industries.map((industry) => (
                <Link
                  key={industry.sw_level1_industry}
                  to={{
                    pathname: '/stocks',
                    search: createSearchParams({
                      industry: industry.sw_level1_industry,
                      run: activeRunId || '',
                    }).toString(),
                  }}
                  className="rounded-[26px] border border-slate-200/70 bg-slate-50/80 p-5 transition hover:border-slate-300 hover:bg-white"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">申万一级行业</p>
                      <h3 className="mt-3 font-serif text-2xl text-slate-950">{industry.sw_level1_industry}</h3>
                    </div>
                    <StatusPill tone="cyan">查看股票</StatusPill>
                  </div>
                  <div className="mt-6 grid grid-cols-2 gap-3 text-sm">
                    <div className="rounded-[20px] border border-white/80 bg-white/90 p-3">
                      <p className="text-slate-500">股票数</p>
                      <p className="mt-2 text-xl text-slate-950">{industry.stock_count}</p>
                    </div>
                    <div className="rounded-[20px] border border-white/80 bg-white/90 p-3">
                      <p className="text-slate-500">均分</p>
                      <p className="mt-2 text-xl text-slate-950">{formatScore(industry.avg_total_score)}</p>
                    </div>
                    <div className="rounded-[20px] border border-white/80 bg-white/90 p-3">
                      <p className="text-slate-500">最高分</p>
                      <p className="mt-2 text-xl text-slate-950">{formatScore(industry.max_total_score)}</p>
                    </div>
                    <div className="rounded-[20px] border border-white/80 bg-white/90 p-3">
                      <p className="text-slate-500">重点池</p>
                      <p className="mt-2 text-xl text-slate-950">{industry.key_watch_count}</p>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {industry.watch_count > 0 ? <StatusPill tone="slate">观察池 {industry.watch_count}</StatusPill> : null}
                    {industry.key_watch_count > 0 ? <StatusPill tone="emerald">重点池 {industry.key_watch_count}</StatusPill> : null}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </Panel>
      </section>
    </AppShell>
  )
}
