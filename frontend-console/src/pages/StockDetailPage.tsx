import { useEffect, useMemo, useState } from 'react'
import { Link, createSearchParams, useParams, useSearchParams } from 'react-router-dom'

import { getLatestRun, getStockDetail, getStockPeers } from '@/api/console'
import { AppShell } from '@/components/layout/AppShell'
import { MetricTile } from '@/components/ui/MetricTile'
import { Panel } from '@/components/ui/Panel'
import { StatusPill } from '@/components/ui/StatusPill'
import { formatPercent, formatScore } from '@/lib/format'
import { useConsoleStore } from '@/store/consoleStore'
import type { PeerPayload, StockDetail } from '@/types/console'

const dimensionDefinitions = [
  ['业务质量', 'biz_quality_score', '看盈利能力、行业位置和利润率稳定性。'],
  ['成长兑现度', 'growth_delivery_score', '看营收、利润增长与股东回报是否匹配。'],
  ['财务质量', 'financial_quality_score', '看现金流、杠杆和资本回报稳定性。'],
  ['估值匹配度', 'valuation_fit_score', '看估值与分红是否与基本面相称。'],
] as const

const metricGroups = [
  {
    title: '业务质量',
    items: [
      ['近3年平均毛利率', 'gross_margin_avg_3y', 'percent'],
      ['近3年平均 ROE', 'roe_avg_3y', 'percent'],
      ['近3年平均净利率', 'net_margin_avg_3y', 'percent'],
    ],
  },
  {
    title: '成长兑现',
    items: [
      ['营收 CAGR', 'revenue_cagr_3y', 'percent'],
      ['扣非净利 CAGR', 'nonrec_np_cagr_3y', 'percent'],
      ['股东回报率', 'shareholder_return_ratio_3y', 'percent'],
    ],
  },
  {
    title: '财务质量',
    items: [
      ['现金转化率', 'cash_conversion_ratio_3y', 'number'],
      ['资产负债率', 'asset_liability_ratio_latest', 'percent'],
    ],
  },
  {
    title: '估值匹配',
    items: [
      ['PE TTM', 'pe_ttm', 'number'],
      ['PB', 'pb_latest', 'number'],
      ['近3年平均股息率', 'dividend_yield_avg_3y', 'percent'],
    ],
  },
] as const

const labelMap: Record<string, string> = {
  st_flag: 'ST 标签',
  audit_opinion_negative: '审计意见为负面类型',
  cash_conversion_ratio_below_0_6: '现金转化率低于阈值',
  asset_liability_ratio_above_0_7: '资产负债率高于阈值',
  market_cap_below_threshold: '市值低于门槛',
  avg_turnover_below_threshold: '成交额低于门槛',
  nonrec_np_negative_years_exceed: '扣非净利润连续为负超出阈值',
  nonrec_np_decline_years_exceed: '扣非净利润连续下滑超出阈值',
}

function presentRuleLabel(value: string) {
  return labelMap[value] || value
}

function formatMetricValue(mode: 'percent' | 'number', value: number | null | undefined) {
  return mode === 'percent' ? formatPercent(value) : formatScore(value, 2)
}

function getDetailSummary(detail: StockDetail) {
  if (detail.is_filtered) {
    return '这只股票本次没有通过硬过滤，更适合先看过滤原因和 warning，再判断是规则过严还是个股本身风险偏高。'
  }

  const poolLabel = detail.current_pool || '观察池'
  return `这只股票当前位于${poolLabel}，可以先用总分、行业位置和 warning 判断结论是否站得住，再继续下钻维度与财报口径。`
}

export default function StockDetailPage() {
  const { tsCode = '' } = useParams()
  const [searchParams] = useSearchParams()
  const runIdFromQuery = searchParams.get('run')
  const selectedRunId = useConsoleStore((state) => state.selectedRunId)
  const setSelectedRunId = useConsoleStore((state) => state.setSelectedRunId)
  const [detail, setDetail] = useState<StockDetail | null>(null)
  const [peers, setPeers] = useState<PeerPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function load() {
      try {
        setLoading(true)
        setError(null)
        const runId = runIdFromQuery || selectedRunId || (await getLatestRun()).run_id
        if (!active) return
        setSelectedRunId(runId)
        const [detailResult, peersResult] = await Promise.all([getStockDetail(runId, tsCode), getStockPeers(runId, tsCode)])
        if (!active) return
        setDetail(detailResult)
        setPeers(peersResult)
      } catch (loadError) {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : '股票详情加载失败')
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [runIdFromQuery, selectedRunId, setSelectedRunId, tsCode])

  const dimensionTiles = useMemo(
    () =>
      detail
        ? dimensionDefinitions.map(([label, key, description]) => [
            label,
            formatScore(detail[key as keyof StockDetail] as number | null | undefined),
            description,
          ])
        : [],
    [detail],
  )

  const activeRunId = detail?.run_id || runIdFromQuery || selectedRunId
  const stockListBackSearch = createSearchParams(
    Object.fromEntries(
      Object.entries({
        run: activeRunId || '',
        industry: detail?.sw_level1_industry || '',
      }).filter(([, value]) => value),
    ),
  ).toString()

  const industryBoardSearch = createSearchParams(
    Object.fromEntries(
      Object.entries({
        run: activeRunId || '',
      }).filter(([, value]) => value),
    ),
  ).toString()

  return (
    <AppShell
      title={detail?.stock_name || '股票详情'}
      subtitle="查看单只股票的完整评分拆解，理解它为什么进池、为什么被预警，并默认带出同行业对比。"
      actions={
        <>
          <Link
            to={{ pathname: '/stocks', search: stockListBackSearch }}
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
          >
            返回股票列表
          </Link>
          <Link
            to={{ pathname: '/industries', search: industryBoardSearch }}
            className="inline-flex items-center gap-2 rounded-full border border-slate-900 bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700"
          >
            返回行业看板
          </Link>
        </>
      }
    >
      {loading ? (
        <div className="grid gap-6">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-[280px] animate-pulse rounded-[28px] bg-slate-100" />
          ))}
        </div>
      ) : error || !detail ? (
        <Panel eyebrow="加载失败" title="暂时无法读取股票详情">
          <div className="rounded-[22px] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">{error || '结果不存在'}</div>
        </Panel>
      ) : (
        <div className="space-y-6">
          <Panel eyebrow={detail.ts_code} title={detail.stock_name}>
            <div className="grid gap-6 xl:grid-cols-[1.08fr_0.92fr]">
              <div>
                <div className="flex flex-wrap gap-2">
                  <StatusPill tone={detail.is_filtered ? 'rose' : 'emerald'}>{detail.is_filtered ? '已过滤' : detail.current_pool || '观察池'}</StatusPill>
                  <StatusPill tone="slate">{detail.sw_level1_industry}</StatusPill>
                  {(detail.warning_tags || []).slice(0, 3).map((tag) => (
                    <StatusPill key={tag} tone="slate">
                      {presentRuleLabel(tag)}
                    </StatusPill>
                  ))}
                </div>
                <p className="mt-5 max-w-3xl text-base leading-8 text-slate-600">{getDetailSummary(detail)}</p>
                <div className="mt-6 rounded-[24px] border border-slate-200/70 bg-slate-50/85 p-5">
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">先看结论</p>
                  <div className="mt-4 space-y-3 text-sm leading-7 text-slate-600">
                    <p>先确认总分与行业位置，判断它是否属于这次 run 里值得优先研究的高分样本。</p>
                    <p>再看当前池子和 warning，分辨它是“高分合理”还是“需要人工复核”的结果。</p>
                    <p>最后再回到硬过滤原因、一级维度和原始指标，判断要不要继续追踪或回头调规则。</p>
                  </div>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <MetricTile label="总分" value={formatScore(detail.total_score)} hint={`全市场排名 ${detail.global_rank || '--'}`} />
                <MetricTile
                  label="当前池子"
                  value={detail.is_filtered ? '已过滤' : detail.current_pool || '观察池'}
                  hint={detail.is_filtered ? '本次未通过硬过滤' : '当前研究优先级'}
                />
                <MetricTile
                  label="行业排名"
                  value={detail.industry_rank && detail.industry_total ? `${detail.industry_rank}/${detail.industry_total}` : '--'}
                  hint={detail.sw_level1_industry}
                />
                <MetricTile
                  label="warning 数量"
                  value={String((detail.warning_tags || []).length)}
                  hint={(detail.warning_tags || []).length > 0 ? '建议先复核再下判断' : '当前没有 warning 标签'}
                />
              </div>
            </div>
          </Panel>

          <div className="grid gap-6 xl:grid-cols-[1.02fr_0.98fr]">
            <Panel eyebrow="Dimensions" title="为什么在这里">
              <div className="grid gap-4 md:grid-cols-2">
                {dimensionTiles.map(([label, value, description]) => (
                  <MetricTile key={label} label={label} value={value} hint={description} />
                ))}
              </div>
            </Panel>

            <Panel eyebrow="Peer Context" title="同行参考">
              <div className="rounded-[24px] border border-sky-200 bg-sky-50/70 p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">当前股票</p>
                <div className="mt-3 flex items-start justify-between gap-4">
                  <div>
                    <p className="text-base font-semibold text-slate-950">{detail.stock_name}</p>
                    <p className="mt-1 text-xs uppercase tracking-[0.22em] text-slate-500">
                      {detail.ts_code} · 行业排名 {detail.industry_rank && detail.industry_total ? `${detail.industry_rank}/${detail.industry_total}` : '--'}
                    </p>
                  </div>
                  <p className="font-serif text-3xl text-slate-950">{formatScore(detail.total_score)}</p>
                </div>
              </div>
              <div className="mt-4 space-y-3">
                {(peers?.peers || []).length > 0 ? (
                  peers?.peers.map((peer) => (
                    <div key={peer.ts_code} className="rounded-[22px] border border-slate-200/70 bg-slate-50/80 p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-semibold text-slate-900">{peer.stock_name}</p>
                            <StatusPill tone={peer.current_pool === '重点观察池' ? 'emerald' : 'slate'}>{peer.current_pool || '观察池'}</StatusPill>
                          </div>
                          <p className="mt-1 text-xs uppercase tracking-[0.22em] text-slate-500">
                            {peer.ts_code} · 行业排名 {peer.industry_rank || '--'}
                          </p>
                          <div className="mt-3 grid gap-2 text-xs text-slate-600 md:grid-cols-2">
                            <span>业务质量 {formatScore(peer.biz_quality_score)}</span>
                            <span>成长兑现 {formatScore(peer.growth_delivery_score)}</span>
                            <span>财务质量 {formatScore(peer.financial_quality_score)}</span>
                            <span>估值匹配 {formatScore(peer.valuation_fit_score)}</span>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="font-serif text-2xl text-slate-950">{formatScore(peer.total_score)}</p>
                          <Link
                            to={{ pathname: `/stocks/${peer.ts_code}`, search: createSearchParams({ run: detail.run_id }).toString() }}
                            className="mt-2 inline-flex text-xs font-semibold text-slate-700 transition hover:text-slate-950"
                          >
                            查看详情
                          </Link>
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="rounded-[22px] border border-dashed border-slate-200 bg-slate-50/70 p-6 text-sm leading-7 text-slate-500">
                    当前没有可比较的同行业样本，可以先以一级维度和规则判断为主。
                  </div>
                )}
              </div>
            </Panel>
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.02fr_0.98fr]">
            <Panel eyebrow="Rules" title="硬过滤、预警与研究提示">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-[22px] border border-slate-200/70 bg-slate-50/80 p-5">
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">硬过滤结果</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <StatusPill tone={detail.is_filtered ? 'rose' : 'emerald'}>{detail.is_filtered ? '未通过' : '已通过'}</StatusPill>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {(detail.filter_reasons || []).length > 0 ? (
                      detail.filter_reasons?.map((reason) => (
                        <StatusPill key={reason} tone="rose">
                          {presentRuleLabel(reason)}
                        </StatusPill>
                      ))
                    ) : (
                      <p className="text-sm text-slate-600">没有触发硬过滤原因。</p>
                    )}
                  </div>
                </div>

                <div className="rounded-[22px] border border-slate-200/70 bg-slate-50/80 p-5">
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">预警与辅助信息</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {(detail.warning_tags || []).length > 0 ? (
                      detail.warning_tags?.map((tag) => (
                        <StatusPill key={tag} tone="slate">
                          {presentRuleLabel(tag)}
                        </StatusPill>
                      ))
                    ) : (
                      <p className="text-sm text-slate-600">当前没有 warning 标签。</p>
                    )}
                  </div>
                  <div className="mt-4 space-y-2 text-sm text-slate-600">
                    <p>最新报告期：{detail.latest_report_period || '--'}</p>
                    <p>审计意见：{detail.audit_opinion || '--'}</p>
                    <p>所属市场：{detail.market || '--'}</p>
                  </div>
                </div>
              </div>
            </Panel>

            <Panel eyebrow="Metrics" title="二级指标与财报口径">
              <div className="space-y-5">
                {metricGroups.map((group) => (
                  <div key={group.title}>
                    <div className="mb-3 flex items-center gap-2">
                      <StatusPill tone="cyan">{group.title}</StatusPill>
                    </div>
                    <div className="space-y-3">
                      {group.items.map(([label, key, mode]) => (
                        <div key={key} className="flex items-center justify-between rounded-[20px] border border-slate-200/70 bg-slate-50/80 px-4 py-3">
                          <span className="text-sm text-slate-700">{label}</span>
                          <span className="font-semibold text-slate-950">
                            {formatMetricValue(mode, detail[key as keyof StockDetail] as number | null | undefined)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          </div>

          <Panel eyebrow="Run Context" title="本次结果来源">
            <div className="grid gap-3 text-sm text-slate-600 md:grid-cols-2 xl:grid-cols-5">
              <div className="rounded-[20px] border border-slate-200/70 bg-slate-50/80 px-4 py-3">run_id：{detail.run_id}</div>
              <div className="rounded-[20px] border border-slate-200/70 bg-slate-50/80 px-4 py-3">rule_version：{detail.rule_version || '--'}</div>
              <div className="rounded-[20px] border border-slate-200/70 bg-slate-50/80 px-4 py-3">data_version：{detail.data_version || '--'}</div>
              <div className="rounded-[20px] border border-slate-200/70 bg-slate-50/80 px-4 py-3">latest_report_period：{detail.latest_report_period || '--'}</div>
              <div className="rounded-[20px] border border-slate-200/70 bg-slate-50/80 px-4 py-3">audit_opinion：{detail.audit_opinion || '--'}</div>
            </div>
          </Panel>
        </div>
      )}
    </AppShell>
  )
}
