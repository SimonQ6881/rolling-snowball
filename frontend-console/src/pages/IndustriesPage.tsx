import { useEffect, useState } from 'react'
import { Link, createSearchParams, useSearchParams } from 'react-router-dom'

import { getIndustryBoard, getLatestRun } from '@/api/console'
import { AppShell } from '@/components/layout/AppShell'
import { RunSwitcher } from '@/components/layout/RunSwitcher'
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

  return (
    <AppShell
      title="行业看板"
      subtitle="从行业维度复核这次运行的分布结构，快速定位高分行业和重点池集中区域。"
      actions={
        <>
          <RunSwitcher currentRunId={runIdFromQuery || selectedRunId} />
          <Link
            to={{
              pathname: '/stocks',
              search: createSearchParams(
                Object.fromEntries(
                  Object.entries({
                    run: runIdFromQuery || selectedRunId || '',
                  }).filter(([, value]) => value),
                ),
              ).toString(),
            }}
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08]"
          >
            查看股票列表
          </Link>
        </>
      }
    >
      <Panel eyebrow="行业视图" title="行业摘要">
        {loading ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="h-40 animate-pulse rounded-[24px] bg-white/[0.05]" />
            ))}
          </div>
        ) : error ? (
          <div className="rounded-[22px] border border-rose-400/20 bg-rose-400/10 p-5 text-sm text-rose-100">{error}</div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {industries.map((industry) => (
              <Link
                key={industry.sw_level1_industry}
                to={{
                  pathname: '/stocks',
                  search: createSearchParams({
                    industry: industry.sw_level1_industry,
                    run: runIdFromQuery || selectedRunId || '',
                  }).toString(),
                }}
                className="rounded-[26px] border border-white/10 bg-white/[0.03] p-5 transition hover:border-cyan-300/30 hover:bg-cyan-300/[0.05]"
              >
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">申万一级行业</p>
                <h3 className="mt-3 font-serif text-2xl text-white">{industry.sw_level1_industry}</h3>
                <div className="mt-6 grid grid-cols-2 gap-3 text-sm">
                  <div className="rounded-2xl bg-white/[0.03] p-3">
                    <p className="text-slate-500">股票数</p>
                    <p className="mt-2 text-xl text-white">{industry.stock_count}</p>
                  </div>
                  <div className="rounded-2xl bg-white/[0.03] p-3">
                    <p className="text-slate-500">均分</p>
                    <p className="mt-2 text-xl text-white">{formatScore(industry.avg_total_score)}</p>
                  </div>
                  <div className="rounded-2xl bg-white/[0.03] p-3">
                    <p className="text-slate-500">最高分</p>
                    <p className="mt-2 text-xl text-white">{formatScore(industry.max_total_score)}</p>
                  </div>
                  <div className="rounded-2xl bg-white/[0.03] p-3">
                    <p className="text-slate-500">重点池</p>
                    <p className="mt-2 text-xl text-white">{industry.key_watch_count}</p>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <StatusPill tone="cyan">点此查看该行业股票</StatusPill>
                  {industry.watch_count > 0 ? <StatusPill tone="slate">观察池 {industry.watch_count}</StatusPill> : null}
                </div>
              </Link>
            ))}
          </div>
        )}
      </Panel>
    </AppShell>
  )
}
