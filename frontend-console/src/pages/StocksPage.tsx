import { useEffect, useMemo, useState } from 'react'
import { Link, createSearchParams, useSearchParams } from 'react-router-dom'

import { getLatestRun, getRunStocks, getRunSummary } from '@/api/console'
import { AppShell } from '@/components/layout/AppShell'
import { RunSwitcher } from '@/components/layout/RunSwitcher'
import { Panel } from '@/components/ui/Panel'
import { StatusPill } from '@/components/ui/StatusPill'
import { formatScore } from '@/lib/format'
import { useConsoleStore } from '@/store/consoleStore'
import type { RunSummary, StockListItem } from '@/types/console'

export default function StocksPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [stocks, setStocks] = useState<StockListItem[]>([])
  const [runSummary, setRunSummary] = useState<RunSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const selectedRunId = useConsoleStore((state) => state.selectedRunId)
  const setSelectedRunId = useConsoleStore((state) => state.setSelectedRunId)
  const runIdFromQuery = searchParams.get('run')
  const industryFilter = searchParams.get('industry') || ''
  const poolFilter = searchParams.get('pool') || ''
  const filteredFlag = searchParams.get('filtered') || ''
  const keyword = searchParams.get('keyword') || ''

  useEffect(() => {
    let active = true

    async function load() {
      try {
        setLoading(true)
        setError(null)
        const runId = runIdFromQuery || selectedRunId || (await getLatestRun()).run_id
        if (!active) return
        setSelectedRunId(runId)
        const summary = await getRunSummary(runId)
        if (!active) return
        setRunSummary(summary)
        const requestParams = createSearchParams({ limit: '100' })
        if (industryFilter) requestParams.set('industry', industryFilter)
        if (poolFilter) requestParams.set('pool', poolFilter)
        if (filteredFlag === 'true') requestParams.set('is_filtered', 'true')
        if (filteredFlag === 'false') requestParams.set('is_filtered', 'false')

        const response = await getRunStocks(runId, requestParams.toString())
        if (!active) return
        setStocks(response.items)
      } catch (loadError) {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : '股票列表加载失败')
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [filteredFlag, industryFilter, poolFilter, runIdFromQuery, selectedRunId, setSelectedRunId])

  const grouped = useMemo(() => {
    return stocks.reduce<Record<string, number>>((accumulator, item) => {
      accumulator[item.sw_level1_industry] = (accumulator[item.sw_level1_industry] || 0) + 1
      return accumulator
    }, {})
  }, [stocks])

  const visibleStocks = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase()
    if (!normalizedKeyword) {
      return stocks
    }
    return stocks.filter((stock) => {
      const haystack = `${stock.stock_name} ${stock.ts_code} ${stock.sw_level1_industry}`.toLowerCase()
      return haystack.includes(normalizedKeyword)
    })
  }, [keyword, stocks])

  const hasActiveFilters = Boolean(industryFilter || poolFilter || filteredFlag || keyword)
  const missingHistoricalDetails = !loading && !error && visibleStocks.length === 0 && !hasActiveFilters && (runSummary?.total_stocks || 0) > 0

  function updateFilters(next: Partial<Record<'industry' | 'pool' | 'filtered' | 'keyword', string>>) {
    const params = new URLSearchParams(searchParams)
    const runId = runIdFromQuery || selectedRunId
    if (runId) {
      params.set('run', runId)
    }

    for (const [key, value] of Object.entries(next)) {
      if (value) {
        params.set(key, value)
      } else {
        params.delete(key)
      }
    }
    setSearchParams(params)
  }

  return (
    <AppShell
      title="全股票列表"
      subtitle="这里展示当前选中 run 下的全部股票结果，方便你快速扫一遍全量结果。"
      actions={
        <>
          <RunSwitcher currentRunId={runIdFromQuery || selectedRunId} />
          <Link
            to={{
              pathname: '/industries',
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
            看行业分布
          </Link>
        </>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
        <Panel eyebrow="筛选概览" title="当前结果快照">
          <div className="grid gap-3">
            <div className="rounded-[22px] border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300">
              当前 run：<span className="font-semibold text-white">{runIdFromQuery || selectedRunId || '--'}</span>
            </div>
            {runSummary ? (
              <div className="rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">run 摘要</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <StatusPill tone={runSummary.run_status === 'success' ? 'emerald' : runSummary.run_status === 'failed' ? 'rose' : 'amber'}>
                    {runSummary.run_status}
                  </StatusPill>
                  <StatusPill tone="slate">重点池 {runSummary.key_watch_count ?? '--'}</StatusPill>
                  <StatusPill tone="slate">观察池 {runSummary.watch_count ?? '--'}</StatusPill>
                </div>
                <p className="mt-4 text-sm leading-6 text-slate-400">
                  通过硬过滤 {runSummary.passed_filter_count ?? '--'} / 总样本 {runSummary.total_stocks ?? '--'}，规则版本 {runSummary.rule_version}
                </p>
              </div>
            ) : null}
            <div className="rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs uppercase tracking-[0.24em] text-slate-500">快速筛选</p>
              <div className="mt-4 space-y-3">
                <input
                  value={keyword}
                  onChange={(event) => updateFilters({ keyword: event.target.value })}
                  placeholder="搜索股票名称 / 代码 / 行业"
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                />
                <div className="grid gap-3 md:grid-cols-2">
                  <select
                    value={poolFilter}
                    onChange={(event) => updateFilters({ pool: event.target.value })}
                    className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                  >
                    <option value="">全部池子</option>
                    <option value="重点观察池">重点观察池</option>
                    <option value="观察池">观察池</option>
                  </select>
                  <select
                    value={filteredFlag}
                    onChange={(event) => updateFilters({ filtered: event.target.value })}
                    className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                  >
                    <option value="">全部状态</option>
                    <option value="false">仅通过硬过滤</option>
                    <option value="true">仅已过滤</option>
                  </select>
                </div>
                <select
                  value={industryFilter}
                  onChange={(event) => updateFilters({ industry: event.target.value })}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40"
                >
                  <option value="">全部行业</option>
                  {Object.keys(grouped)
                    .sort((left, right) => left.localeCompare(right, 'zh-Hans-CN'))
                    .map((industry) => (
                      <option key={industry} value={industry}>
                        {industry}
                      </option>
                    ))}
                </select>
              </div>
            </div>
            <div className="rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
              <p className="text-xs uppercase tracking-[0.24em] text-slate-500">行业覆盖</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {Object.entries(grouped)
                  .slice(0, 8)
                  .map(([industry, count]) => (
                    <StatusPill key={industry} tone="slate">
                      {industry} · {count}
                    </StatusPill>
                  ))}
              </div>
            </div>
          </div>
        </Panel>

        <Panel eyebrow="结果明细" title="股票列表">
          {!loading && !error ? (
            <div className="mb-5 flex flex-wrap items-center gap-2">
              <StatusPill tone="cyan">结果 {visibleStocks.length} 条</StatusPill>
              {industryFilter ? <StatusPill tone="slate">行业 {industryFilter}</StatusPill> : null}
              {poolFilter ? <StatusPill tone="slate">池子 {poolFilter}</StatusPill> : null}
              {filteredFlag ? <StatusPill tone="slate">{filteredFlag === 'true' ? '已过滤' : '通过硬过滤'}</StatusPill> : null}
              {keyword ? <StatusPill tone="slate">关键词 {keyword}</StatusPill> : null}
            </div>
          ) : null}
          {missingHistoricalDetails ? (
            <div className="mb-5 rounded-[22px] border border-amber-400/20 bg-amber-400/10 p-5 text-sm leading-7 text-amber-100">
              这次 `run` 有汇总结果，但没有逐股历史明细，所以当前列表无法展开。更常见于较早生成的历史 run。你可以切到较新的 run，或先去历史运行页确认这次运行的来源与时间。
            </div>
          ) : null}
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="h-16 animate-pulse rounded-[20px] bg-white/[0.05]" />
              ))}
            </div>
          ) : error ? (
            <div className="rounded-[22px] border border-rose-400/20 bg-rose-400/10 p-5 text-sm text-rose-100">{error}</div>
          ) : (
            <div className="space-y-3">
              {visibleStocks.map((stock) => (
                <Link
                  key={stock.ts_code}
                  to={{ pathname: `/stocks/${stock.ts_code}`, search: createSearchParams({ run: stock.run_id }).toString() }}
                  className="flex items-center justify-between rounded-[22px] border border-white/10 bg-white/[0.03] px-5 py-4 transition hover:border-cyan-300/25 hover:bg-cyan-300/[0.05]"
                >
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold text-white">{stock.stock_name}</p>
                      <StatusPill tone={stock.is_filtered ? 'rose' : stock.current_pool === '重点观察池' ? 'emerald' : 'slate'}>
                        {stock.is_filtered ? '已过滤' : stock.current_pool || '观察池'}
                      </StatusPill>
                    </div>
                    <p className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-500">
                      {stock.ts_code} · {stock.sw_level1_industry}
                    </p>
                    {stock.warning_tags.length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {stock.warning_tags.slice(0, 3).map((tag) => (
                          <StatusPill key={tag} tone="slate">
                            {tag}
                          </StatusPill>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  <div className="text-right">
                    <p className="font-serif text-2xl text-white">{formatScore(stock.total_score)}</p>
                    <p className="mt-1 text-xs text-slate-400">
                      行业排名 {stock.industry_rank && stock.industry_total ? `${stock.industry_rank}/${stock.industry_total}` : '--'}
                    </p>
                  </div>
                </Link>
              ))}
              {visibleStocks.length === 0 ? (
                <div className="rounded-[22px] border border-dashed border-white/10 bg-white/[0.02] px-5 py-8 text-center text-sm text-slate-400">
                  {missingHistoricalDetails ? '当前 run 缺少逐股历史明细，建议切换到较新的 run 查看。' : '当前筛选条件下没有结果，换一个行业、池子或关键词再试试。'}
                </div>
              ) : null}
            </div>
          )}
        </Panel>
      </div>
    </AppShell>
  )
}
