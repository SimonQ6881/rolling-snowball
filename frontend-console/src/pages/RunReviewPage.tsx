import { useEffect, useMemo, useState } from 'react'
import { Link, createSearchParams, useSearchParams } from 'react-router-dom'

import { getLatestRun, getRunQualityOverview } from '@/api/console'
import { AppShell } from '@/components/layout/AppShell'
import { RunSwitcher } from '@/components/layout/RunSwitcher'
import { MetricTile } from '@/components/ui/MetricTile'
import { Panel } from '@/components/ui/Panel'
import { StatusPill } from '@/components/ui/StatusPill'
import { formatDateTime, formatPercent, formatScore } from '@/lib/format'
import type { RunIndustryReviewItem, RunQualityOverview } from '@/types/console'

function getReviewHighlights(overview: RunQualityOverview) {
  const { metrics, industries } = overview
  const highlights: string[] = []

  if (metrics.pass_rate < 0.08) {
    highlights.push('通过率偏低，这次规则整体偏紧，建议回看硬过滤阈值。')
  } else if (metrics.pass_rate > 0.35) {
    highlights.push('通过率偏高，这次规则整体偏松，可能放入了较多边缘样本。')
  } else {
    highlights.push('通过率处在相对可控区间，可以继续看 warning 和行业分布。')
  }

  if (metrics.warning_stock_rate > 0.35) {
    highlights.push('warning 覆盖面偏高，说明入样本里需要人工复核的股票较多。')
  }

  const topIndustry = industries[0]
  if (topIndustry && metrics.key_watch_count > 0 && topIndustry.key_watch_count / metrics.key_watch_count >= 0.35) {
    highlights.push(`重点观察池对 ${topIndustry.sw_level1_industry} 集中度较高，建议留意行业暴露是否过重。`)
  }

  if (metrics.data_missing_count > 0) {
    highlights.push('存在数据缺口样本，复盘时建议优先看 data_missing 类 warning。')
  }

  return highlights
}

function getIndustryWarningRate(industry: RunIndustryReviewItem) {
  if (industry.stock_count <= 0) return 0
  return industry.warning_stock_count / industry.stock_count
}

const warningLabelMap: Record<string, string> = {
  manual_review: '人工复核',
  data_missing: '数据缺口',
  cash_conversion_ratio_below_0_6: '现金转化率偏弱',
  asset_liability_ratio_above_0_7: '资产负债率偏高',
}

function presentWarningLabel(value: string) {
  return warningLabelMap[value] || value
}

function getWarningOutlierMessage(warningCount: number, currentPool: string | null) {
  const poolLabel = currentPool || '观察池'
  return `已入${poolLabel}，但有 ${warningCount} 个 warning，建议先复核再下判断。`
}

function getRunVerdict(overview: RunQualityOverview) {
  const { metrics } = overview

  if (metrics.pass_rate < 0.08) {
    return {
      tone: 'rose' as const,
      title: '这次 run 偏紧',
      description: '通过率明显偏低，优先回看硬过滤阈值和异常 warning 是否放大了筛除范围。',
    }
  }

  if (metrics.pass_rate > 0.35 || metrics.warning_stock_rate > 0.35) {
    return {
      tone: 'amber' as const,
      title: '这次 run 需要复核',
      description: '通过率或 warning 覆盖偏高，建议先确认是否放入了过多边缘样本。',
    }
  }

  return {
    tone: 'emerald' as const,
    title: '这次 run 基本可控',
    description: '可以先沿着高分样本和行业分布继续下钻，再决定是否需要重跑规则。',
  }
}

export default function RunReviewPage() {
  const [searchParams] = useSearchParams()
  const runIdFromQuery = searchParams.get('run')
  const [overview, setOverview] = useState<RunQualityOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function load() {
      try {
        setLoading(true)
        setError(null)
        const resolvedRunId = runIdFromQuery || (await getLatestRun()).run_id
        if (!active) return
        const nextOverview = await getRunQualityOverview(resolvedRunId)
        if (!active) return
        setOverview(nextOverview)
      } catch (loadError) {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : 'Run 质量总览加载失败')
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
  }, [runIdFromQuery])

  const highlights = useMemo(() => (overview ? getReviewHighlights(overview) : []), [overview])
  const verdict = useMemo(() => (overview ? getRunVerdict(overview) : null), [overview])
  const activeRunId = overview?.run_summary.run_id || runIdFromQuery

  return (
    <AppShell
      title="Run 质量总览"
      subtitle="先快速判断这次全市场跑批有没有跑偏，再决定是回头调规则，还是继续深入看股票与行业结果。"
      actions={
        <>
          <RunSwitcher currentRunId={activeRunId || null} />
          <Link
            to="/runs"
            className="inline-flex rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
          >
            返回历史运行
          </Link>
          {activeRunId ? (
            <Link
              to={`/stocks?${createSearchParams({ run: activeRunId }).toString()}`}
              className="inline-flex rounded-full border border-slate-900 bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700"
            >
              查看股票列表
            </Link>
          ) : null}
        </>
      }
    >
      {loading ? (
        <div className="grid gap-6">
          <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="h-28 animate-pulse rounded-[24px] bg-slate-100" />
            ))}
          </div>
          <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
            <div className="h-[320px] animate-pulse rounded-[28px] bg-slate-100" />
            <div className="h-[320px] animate-pulse rounded-[28px] bg-slate-100" />
          </div>
        </div>
      ) : error ? (
        <Panel eyebrow="质量总览" title="暂时无法读取这次 run 的复盘结果">
          <div className="rounded-[22px] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">{error}</div>
        </Panel>
      ) : overview ? (
        <div className="grid gap-6">
          <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
            <MetricTile label="run_id" value={overview.run_summary.run_id.slice(0, 8)} hint={formatDateTime(overview.run_summary.finished_at)} />
            <MetricTile label="总样本" value={String(overview.metrics.total_stocks)} hint={`平均总分 ${formatScore(overview.metrics.avg_total_score)}`} />
            <MetricTile label="通过率" value={formatPercent(overview.metrics.pass_rate)} hint={`通过 ${overview.metrics.passed_filter_count} / 过滤 ${overview.metrics.filtered_count}`} />
            <MetricTile label="重点池占比" value={formatPercent(overview.metrics.key_watch_rate)} hint={`重点池 ${overview.metrics.key_watch_count} 只`} />
            <MetricTile label="warning 覆盖" value={formatPercent(overview.metrics.warning_stock_rate)} hint={`涉及 ${overview.metrics.warning_stock_count} 只`} />
            <MetricTile
              label="平均 warning 数"
              value={formatScore(overview.metrics.avg_warning_tags_per_stock)}
              hint={`人工复核 ${overview.metrics.manual_review_count} · 数据缺口 ${overview.metrics.data_missing_count}`}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
            <Panel eyebrow="Review Summary" title="先判断这次 run 有没有跑偏">
              <div className="rounded-[24px] border border-slate-200/70 bg-slate-50/85 p-5">
                <div className="flex flex-wrap gap-2">
                  <StatusPill tone={verdict?.tone || 'slate'}>{verdict?.title || '等待结论'}</StatusPill>
                  <StatusPill tone={overview.run_summary.run_status === 'success' ? 'emerald' : overview.run_summary.run_status === 'failed' ? 'rose' : 'amber'}>
                    {overview.run_summary.run_status}
                  </StatusPill>
                  <StatusPill tone="slate">规则 {overview.run_summary.rule_version}</StatusPill>
                  <StatusPill tone="cyan">数据 {overview.run_summary.data_version}</StatusPill>
                </div>
                <p className="mt-4 text-sm leading-7 text-slate-600">{verdict?.description}</p>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <div className="rounded-[20px] border border-white/80 bg-white/90 px-4 py-3 text-sm text-slate-600">
                    run_id：{overview.run_summary.run_id}
                  </div>
                  <div className="rounded-[20px] border border-white/80 bg-white/90 px-4 py-3 text-sm text-slate-600">
                    完成时间：{formatDateTime(overview.run_summary.finished_at)}
                  </div>
                </div>
              </div>

              <div className="mt-5 space-y-3">
                {highlights.map((item) => (
                  <div key={item} className="rounded-[20px] border border-slate-200/70 bg-slate-50/80 p-4 text-sm leading-7 text-slate-600">
                    {item}
                  </div>
                ))}
              </div>
            </Panel>

            <Panel eyebrow="Warning Distribution" title="最常见的人工复核信号">
              {overview.top_warning_tags.length > 0 ? (
                <div className="space-y-3">
                  {overview.top_warning_tags.map((item) => (
                    <div
                      key={item.warning_tag}
                      className="flex items-center justify-between rounded-[20px] border border-slate-200/70 bg-slate-50/80 px-4 py-4"
                    >
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{presentWarningLabel(item.warning_tag)}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          覆盖率 {formatPercent(item.stock_count / Math.max(overview.metrics.total_stocks, 1))}
                        </p>
                      </div>
                      <StatusPill tone="amber">{item.stock_count}</StatusPill>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-[22px] border border-dashed border-slate-200 bg-slate-50/70 p-6 text-sm leading-7 text-slate-500">
                  这次 run 没有 warning 标签，说明当前样本在预警维度上比较干净。
                </div>
              )}
            </Panel>
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.02fr_0.98fr]">
            <Panel eyebrow="Outliers" title="高分但 warning 多">
              {overview.warning_outliers.length > 0 ? (
                <div className="space-y-4">
                  {overview.warning_outliers.map((item) => (
                    <div key={item.ts_code} className="rounded-[24px] border border-slate-200/70 bg-slate-50/80 p-5">
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-base font-semibold text-slate-900">{item.stock_name}</p>
                            <StatusPill tone="slate">{item.ts_code}</StatusPill>
                            <StatusPill tone="cyan">{item.sw_level1_industry}</StatusPill>
                          </div>
                          <p className="mt-3 text-sm leading-7 text-slate-600">{getWarningOutlierMessage(item.warning_count, item.current_pool)}</p>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <StatusPill tone="amber">{item.current_pool || '观察池'}</StatusPill>
                            <StatusPill tone="slate">总分 {formatScore(item.total_score)}</StatusPill>
                            <StatusPill tone="rose">{item.warning_count} 个 warning</StatusPill>
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {item.warning_tags.map((tag) => (
                              <StatusPill key={tag} tone="slate">
                                {presentWarningLabel(tag)}
                              </StatusPill>
                            ))}
                          </div>
                        </div>

                        <Link
                          to={{
                            pathname: `/stocks/${item.ts_code}`,
                            search: createSearchParams({ run: overview.run_summary.run_id }).toString(),
                          }}
                          className="inline-flex rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
                        >
                          查看个股详情
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-[22px] border border-dashed border-slate-200 bg-slate-50/70 p-6 text-sm leading-7 text-slate-500">
                  当前没有“高分但 warning 多”的样本，这次 run 的高分股票相对更干净。
                </div>
              )}
            </Panel>

            <Panel eyebrow="Industry View" title="行业分布先看哪里值得继续追">
              {overview.industries.length > 0 ? (
                <div className="space-y-3">
                  {overview.industries.map((industry) => (
                    <div key={industry.sw_level1_industry} className="rounded-[22px] border border-slate-200/70 bg-slate-50/80 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-slate-900">{industry.sw_level1_industry}</p>
                          <p className="mt-2 text-sm text-slate-600">
                            通过 {industry.passed_count}/{industry.stock_count}，重点池 {industry.key_watch_count}，warning 覆盖{' '}
                            {formatPercent(getIndustryWarningRate(industry))}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">平均总分</p>
                          <p className="mt-2 font-serif text-2xl text-slate-950">{formatScore(industry.avg_total_score)}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-[22px] border border-dashed border-slate-200 bg-slate-50/70 p-6 text-sm leading-7 text-slate-500">
                  当前没有行业分布数据，通常说明这次 run 还没有完整股票结果落库。
                </div>
              )}
            </Panel>
          </div>
        </div>
      ) : null}
    </AppShell>
  )
}
