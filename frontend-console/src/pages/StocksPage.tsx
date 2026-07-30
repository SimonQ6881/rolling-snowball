import { useEffect, useMemo, useState } from 'react'
import { Link, createSearchParams, useSearchParams } from 'react-router-dom'

import { getLatestRun, getRunStocks, getRunSummary } from '@/api/console'
import { AppShell } from '@/components/layout/AppShell'
import { RunSwitcher } from '@/components/layout/RunSwitcher'
import { MetricTile } from '@/components/ui/MetricTile'
import { Panel } from '@/components/ui/Panel'
import { StatusPill } from '@/components/ui/StatusPill'
import { formatDateTime, formatScore } from '@/lib/format'
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

  const activeRunId = runIdFromQuery || selectedRunId
  const hasActiveFilters = Boolean(industryFilter || poolFilter || filteredFlag || keyword)
  const missingHistoricalDetails = !loading && !error && visibleStocks.length === 0 && !hasActiveFilters && (runSummary?.total_stocks || 0) > 0
  const topIndustries = Object.entries(grouped)
    .sort(([, leftCount], [, rightCount]) => rightCount - leftCount)
    .slice(0, 6)
  const activeFilterSummary = [
    industryFilter ? `行业 ${industryFilter}` : null,
    poolFilter ? `池子 ${poolFilter}` : null,
    filteredFlag ? (filteredFlag === 'true' ? '仅已过滤' : '仅通过硬过滤') : null,
    keyword ? `关键词 ${keyword}` : null,
  ].filter(Boolean) as string[]
  const runStatusTone = runSummary?.run_status === 'success' ? 'emerald' : runSummary?.run_status === 'failed' ? 'rose' : 'amber'

  function updateFilters(next: Partial<Record<'industry' | 'pool' | 'filtered' | 'keyword', string>>) {
    const params = new URLSearchParams(searchParams)
    const runId = activeRunId
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
      subtitle="先看当前 run 的筛选摘要，再进入更安静的结果列表。"
      actions={
        <>
          <RunSwitcher currentRunId={activeRunId} />
          <Link
            to={{
              pathname: '/industries',
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
            看行业分布
          </Link>
        </>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[0.88fr_1.12fr]">
        <Panel eyebrow="Snapshot" title="当前 run 与筛选摘要">
          <div className="space-y-4">
            <div className="rounded-[24px] border border-slate-200/70 bg-slate-50/85 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">当前 run</p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <StatusPill tone={runStatusTone}>{runSummary?.run_status || 'loading'}</StatusPill>
                <StatusPill tone="slate">{activeRunId || '--'}</StatusPill>
              </div>
              {runSummary ? (
                <p className="mt-4 text-sm leading-7 text-slate-600">
                  完成于 {formatDateTime(runSummary.finished_at)}，规则版本 {runSummary.rule_version}，数据版本 {runSummary.data_version}。
                </p>
              ) : (
                <p className="mt-4 text-sm leading-7 text-slate-500">正在读取这次 run 的摘要与结果分布。</p>
              )}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <MetricTile
                label="结果量"
                value={loading ? '--' : String(visibleStocks.length)}
                hint={hasActiveFilters ? '按当前筛选条件计算' : '当前列表可见结果'}
              />
              <MetricTile
                label="行业覆盖"
                value={loading ? '--' : String(Object.keys(grouped).length)}
                hint="当前结果命中的申万一级行业数"
              />
            </div>

            {runSummary ? (
              <div className="rounded-[24px] border border-slate-200/70 bg-white/85 p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">run 摘要</p>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <div>
                    <p className="text-sm text-slate-500">通过硬过滤</p>
                    <p className="mt-1 font-serif text-3xl text-slate-950">{runSummary.passed_filter_count ?? '--'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">重点观察池</p>
                    <p className="mt-1 font-serif text-3xl text-slate-950">{runSummary.key_watch_count ?? '--'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">观察池</p>
                    <p className="mt-1 font-serif text-3xl text-slate-950">{runSummary.watch_count ?? '--'}</p>
                  </div>
                </div>
                <p className="mt-4 text-sm leading-7 text-slate-600">
                  共覆盖 {runSummary.total_stocks ?? '--'} 只股票。这个摘要用来先判断这次 run 的宽度，再决定是否继续缩小筛选范围。
                </p>
              </div>
            ) : null}

            <div className="rounded-[24px] border border-slate-200/70 bg-white/85 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">当前筛选</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {activeFilterSummary.length > 0 ? (
                  activeFilterSummary.map((label) => (
                    <StatusPill key={label} tone="slate">
                      {label}
                    </StatusPill>
                  ))
                ) : (
                  <StatusPill tone="cyan">未额外缩小范围</StatusPill>
                )}
              </div>
              <p className="mt-4 text-sm leading-7 text-slate-600">先读当前筛选语境，再扫结果列表，能避免把局部结果误读成全量结论。</p>
            </div>

            <div className="rounded-[24px] border border-slate-200/70 bg-white/85 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">行业覆盖</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {topIndustries.length > 0 ? (
                  topIndustries.map(([industry, count]) => (
                    <StatusPill key={industry} tone="slate">
                      {industry} {count}
                    </StatusPill>
                  ))
                ) : (
                  <span className="text-sm text-slate-500">当前还没有可展示的行业分布。</span>
                )}
              </div>
            </div>
          </div>
        </Panel>

        <Panel eyebrow="Filters" title="过滤舱">
          <div className="grid gap-4">
            <div className="rounded-[24px] border border-slate-200/70 bg-slate-50/85 p-5">
              <p className="text-sm leading-7 text-slate-600">
                过滤器保持在右侧独立区域，先提供上下文，再让你逐步缩小范围，不和结果摘要抢第一屏的注意力。
              </p>
            </div>

            <div className="grid gap-3">
              <label className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500" htmlFor="stocks-keyword">
                关键词
              </label>
              <input
                id="stocks-keyword"
                value={keyword}
                onChange={(event) => updateFilters({ keyword: event.target.value })}
                placeholder="搜索股票名称 / 代码 / 行业"
                className="w-full rounded-[22px] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400"
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-3">
                <label className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500" htmlFor="stocks-pool">
                  池子
                </label>
                <select
                  id="stocks-pool"
                  value={poolFilter}
                  onChange={(event) => updateFilters({ pool: event.target.value })}
                  className="rounded-[22px] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400"
                >
                  <option value="">全部池子</option>
                  <option value="重点观察池">重点观察池</option>
                  <option value="观察池">观察池</option>
                </select>
              </div>
              <div className="grid gap-3">
                <label className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500" htmlFor="stocks-filtered">
                  过滤状态
                </label>
                <select
                  id="stocks-filtered"
                  value={filteredFlag}
                  onChange={(event) => updateFilters({ filtered: event.target.value })}
                  className="rounded-[22px] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400"
                >
                  <option value="">全部状态</option>
                  <option value="false">仅通过硬过滤</option>
                  <option value="true">仅已过滤</option>
                </select>
              </div>
            </div>

            <div className="grid gap-3">
              <label className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500" htmlFor="stocks-industry">
                行业
              </label>
              <select
                id="stocks-industry"
                value={industryFilter}
                onChange={(event) => updateFilters({ industry: event.target.value })}
                className="w-full rounded-[22px] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400"
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

            <div className="rounded-[24px] border border-slate-200/70 bg-slate-50/85 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">过滤建议</p>
              <p className="mt-3 text-sm leading-7 text-slate-600">
                先按池子或过滤状态缩小结果，再用行业和关键词精修，能更快找到该次 run 里最值得继续研究的样本。
              </p>
            </div>
          </div>
        </Panel>
      </div>

      <div className="mt-6">
        <Panel eyebrow="Result List" title="股票列表">
          {!loading && !error ? (
            <div className="mb-5 flex flex-wrap items-center gap-2">
              <StatusPill tone="cyan">结果 {visibleStocks.length} 条</StatusPill>
              {activeFilterSummary.map((label) => (
                <StatusPill key={label} tone="slate">
                  {label}
                </StatusPill>
              ))}
            </div>
          ) : null}
          {missingHistoricalDetails ? (
            <div className="mb-5 rounded-[24px] border border-amber-200 bg-amber-50 p-5 text-sm leading-7 text-amber-700">
              这次 `run` 有汇总结果，但没有逐股历史明细，所以当前列表无法展开。更常见于较早生成的历史 run。你可以切到较新的 run，或先去历史运行页确认这次运行的来源与时间。
            </div>
          ) : null}
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="h-16 animate-pulse rounded-[20px] bg-slate-100" />
              ))}
            </div>
          ) : error ? (
            <div className="rounded-[24px] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">{error}</div>
          ) : (
            <div className="overflow-hidden rounded-[24px] border border-slate-200/70 bg-white/90">
              <div className="hidden grid-cols-[minmax(0,1.4fr)_0.9fr_120px] gap-4 border-b border-slate-200/70 bg-slate-50/85 px-5 py-3 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500 md:grid">
                <p>股票</p>
                <p>状态与预警</p>
                <p className="text-right">总分</p>
              </div>
              <div className="divide-y divide-slate-200/70">
                {visibleStocks.map((stock) => (
                  <Link
                    key={stock.ts_code}
                    to={{ pathname: `/stocks/${stock.ts_code}`, search: createSearchParams({ run: stock.run_id }).toString() }}
                    className="grid gap-4 px-5 py-4 transition hover:bg-slate-50 md:grid-cols-[minmax(0,1.4fr)_0.9fr_120px] md:items-center"
                  >
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold text-slate-950">{stock.stock_name}</p>
                        <StatusPill tone={stock.is_filtered ? 'rose' : stock.current_pool === '重点观察池' ? 'emerald' : 'slate'}>
                          {stock.is_filtered ? '已过滤' : stock.current_pool || '观察池'}
                        </StatusPill>
                      </div>
                      <p className="mt-2 text-xs uppercase tracking-[0.2em] text-slate-500">
                        {stock.ts_code} · {stock.sw_level1_industry}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {stock.warning_tags.length > 0 ? (
                        stock.warning_tags.slice(0, 3).map((tag) => (
                          <StatusPill key={tag} tone="slate">
                            {tag}
                          </StatusPill>
                        ))
                      ) : (
                        <StatusPill tone="cyan">无额外预警</StatusPill>
                      )}
                    </div>
                    <div className="text-left md:text-right">
                      <p className="font-serif text-2xl text-slate-950">{formatScore(stock.total_score)}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        行业排名 {stock.industry_rank && stock.industry_total ? `${stock.industry_rank}/${stock.industry_total}` : '--'}
                      </p>
                    </div>
                  </Link>
                ))}
                {visibleStocks.length === 0 ? (
                  <div className="px-5 py-8 text-center text-sm text-slate-500">
                    {missingHistoricalDetails ? '当前 run 缺少逐股历史明细，建议切换到较新的 run 查看。' : '当前筛选条件下没有结果，换一个行业、池子或关键词再试试。'}
                  </div>
                ) : null}
              </div>
            </div>
          )}
        </Panel>
      </div>
    </AppShell>
  )
}
