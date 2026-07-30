import { ArrowRight } from 'lucide-react'
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
  const runStatusTone = latestRun?.run_status === 'success' ? 'emerald' : latestRun?.run_status === 'failed' ? 'rose' : 'amber'
  const summaryTiles = latestRun
    ? [
        {
          label: '运行时间',
          value: formatDateTime(latestRun.finished_at),
          hint: `规则版本 ${latestRun.rule_version}`,
        },
        {
          label: '通过硬过滤',
          value: String(latestRun.passed_filter_count ?? '--'),
          hint: `总样本 ${latestRun.total_stocks ?? '--'} 只`,
        },
        {
          label: '重点观察池',
          value: String(latestRun.key_watch_count ?? '--'),
          hint: '优先进入深度研究队列',
        },
        {
          label: '观察池',
          value: String(latestRun.watch_count ?? '--'),
          hint: `数据版本 ${latestRun.data_version}`,
        },
      ]
    : []
  const helperEntries = [
    {
      title: '历史运行',
      desc: '回看每次 run 的摘要、来源任务与结果入口。',
      to: { pathname: '/runs', search: '' },
    },
    {
      title: '行业看板',
      desc: '先看哪些行业在这次 run 里更集中、更值得展开。',
      to: {
        pathname: '/industries',
        search: activeRunId ? createSearchParams({ run: activeRunId }).toString() : '',
      },
    },
    {
      title: '规则实验台',
      desc: '调整阈值与权重，决定下一轮 run 怎么跑。',
      to: { pathname: '/lab', search: '' },
    },
  ]

  return (
    <AppShell
      title="重点观察池"
      subtitle="本次最值得优先看的 run 结果与研究入口。"
      actions={
        <>
          <RunSwitcher currentRunId={activeRunId} />
          <Link
            to={{
              pathname: '/stocks',
              search: activeRunId ? createSearchParams({ run: activeRunId }).toString() : '',
            }}
            className="inline-flex items-center gap-2 rounded-full border border-slate-900 bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700"
          >
            查看全股票列表
            <ArrowRight className="h-4 w-4" />
          </Link>
        </>
      }
    >
      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Panel eyebrow="Latest Run" title="先看这次最值得研究的 20 只">
          {loading ? (
            <div className="grid gap-4 md:grid-cols-2">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="h-28 animate-pulse rounded-[24px] bg-slate-100" />
              ))}
            </div>
          ) : error ? (
            <div className="rounded-[24px] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">{error}</div>
          ) : latestRun ? (
            <div className="grid gap-5 lg:grid-cols-[1.08fr_0.92fr]">
              <div>
                <div className="flex flex-wrap gap-2">
                  <StatusPill tone={runStatusTone}>{latestRun.run_status}</StatusPill>
                  <StatusPill tone="slate">{latestRun.run_id}</StatusPill>
                  <StatusPill tone="slate">规则 {latestRun.rule_version}</StatusPill>
                </div>
                <p className="mt-5 max-w-3xl text-base leading-8 text-slate-600">
                  这次 run 共筛过 {latestRun.total_stocks ?? '--'} 只股票，其中 {latestRun.key_watch_count ?? '--'} 只进入重点观察池，
                  更适合先判断优先级，再决定是否继续下钻到行业分布或全量列表。
                </p>
                <div className="mt-6 flex flex-wrap gap-3">
                  <Link
                    to={{
                      pathname: '/stocks',
                      search: activeRunId ? createSearchParams({ run: activeRunId, pool: '重点观察池' }).toString() : '',
                    }}
                    className="inline-flex items-center gap-2 rounded-full border border-slate-900 bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700"
                  >
                    直接看重点池
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                  <Link
                    to={{
                      pathname: '/industries',
                      search: activeRunId ? createSearchParams({ run: activeRunId }).toString() : '',
                    }}
                    className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
                  >
                    看行业分布
                  </Link>
                </div>
              </div>
              <div className="rounded-[24px] border border-slate-200/70 bg-slate-50/85 p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">研究顺序</p>
                <div className="mt-4 space-y-4">
                  <div className="rounded-[20px] border border-white/80 bg-white/90 p-4">
                    <p className="text-sm font-semibold text-slate-900">1. 先看重点池结论</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">优先确认总分、行业位置和 warning，决定哪些股票值得继续追踪。</p>
                  </div>
                  <div className="rounded-[20px] border border-white/80 bg-white/90 p-4">
                    <p className="text-sm font-semibold text-slate-900">2. 再看行业分布</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">判断高分样本是否集中在少数行业，避免只盯单只股票。</p>
                  </div>
                  <div className="rounded-[20px] border border-white/80 bg-white/90 p-4">
                    <p className="text-sm font-semibold text-slate-900">3. 最后决定是否重跑规则</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">如果分布结构和历史认知偏差较大，再进入实验台调整阈值。</p>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </Panel>

        <Panel eyebrow="Next Step" title="下一步从哪里展开">
          <p className="text-sm leading-7 text-slate-600">把高频入口降为辅助层，先决定研究路径，再进入对应明细页。</p>
          <div className="mt-5 space-y-3">
            {[
              {
                title: '看全量结果',
                desc: '进入全股票列表后，继续按行业、池子和 warning 做二次筛查。',
              },
              {
                title: '核对历史 run',
                desc: '如果这次分布异常，先回到历史运行页确认来源任务和规则版本。',
              },
              {
                title: '决定是否重跑',
                desc: '需要调规则时再去实验台，避免操作入口与结论同时争抢注意力。',
              },
            ].map((item, index) => (
              <div key={item.title} className="rounded-[22px] border border-slate-200/70 bg-slate-50/80 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">0{index + 1}</p>
                <p className="mt-2 text-sm font-semibold text-slate-900">{item.title}</p>
                <p className="mt-2 text-sm leading-6 text-slate-600">{item.desc}</p>
              </div>
            ))}
          </div>
        </Panel>
      </section>

      <section className="mt-6 grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
        {loading
          ? Array.from({ length: 4 }).map((_, index) => <div key={index} className="h-36 animate-pulse rounded-[24px] bg-slate-100" />)
          : summaryTiles.map((tile) => <MetricTile key={tile.label} label={tile.label} value={tile.value} hint={tile.hint} />)}
      </section>

      <section className="mt-6">
        <Panel eyebrow="Research Entry" title="辅助入口">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {helperEntries.map((item) => (
              <Link
                key={item.title}
                to={item.to}
                className="group rounded-[24px] border border-slate-200/70 bg-slate-50/80 p-5 transition hover:border-slate-300 hover:bg-white"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="font-serif text-2xl text-slate-950">{item.title}</h3>
                    <p className="mt-3 text-sm leading-7 text-slate-600">{item.desc}</p>
                  </div>
                  <ArrowRight className="mt-1 h-5 w-5 shrink-0 text-slate-400 transition group-hover:text-slate-700" />
                </div>
              </Link>
            ))}
          </div>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link
              to={{
                pathname: '/stocks',
                search: activeRunId ? createSearchParams({ run: activeRunId, pool: '重点观察池' }).toString() : '',
              }}
              className="inline-flex rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
            >
              重点观察池
            </Link>
            <Link
              to={{
                pathname: '/stocks',
                search: activeRunId ? createSearchParams({ run: activeRunId, filtered: 'true' }).toString() : '',
              }}
              className="inline-flex rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
            >
              仅已过滤
            </Link>
            <Link
              to={{
                pathname: '/industries',
                search: activeRunId ? createSearchParams({ run: activeRunId }).toString() : '',
              }}
              className="inline-flex rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
            >
              按行业查看
            </Link>
          </div>
        </Panel>
      </section>

      <section className="mt-6">
        <Panel eyebrow="Key Watch" title={`重点观察池列表${latestRun ? ` · ${latestRun.run_id.slice(0, 8)}` : ''}`} className="overflow-hidden">
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="h-20 animate-pulse rounded-[22px] bg-slate-100" />
              ))}
            </div>
          ) : stocks.length > 0 && latestRun ? (
            <KeyWatchTable stocks={stocks} runId={latestRun.run_id} />
          ) : (
            <div className="rounded-[24px] border border-dashed border-slate-200 bg-slate-50/80 p-8 text-center">
              <StatusPill tone="amber">暂无重点观察池结果</StatusPill>
              <p className="mx-auto mt-4 max-w-2xl text-sm leading-7 text-slate-600">
                当前最新运行还没有重点观察池样本。你可以进入规则实验台调整阈值或评分权重，然后重新发起一次运行。
              </p>
            </div>
          )}
        </Panel>
      </section>
    </AppShell>
  )
}
