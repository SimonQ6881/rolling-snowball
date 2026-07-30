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
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08]"
          >
            返回股票列表
          </Link>
          <Link
            to={{ pathname: '/industries', search: industryBoardSearch }}
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08]"
          >
            返回行业看板
          </Link>
        </>
      }
    >
      {loading ? (
        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          {Array.from({ length: 2 }).map((_, index) => (
            <div key={index} className="h-[420px] animate-pulse rounded-[30px] bg-white/[0.05]" />
          ))}
        </div>
      ) : error || !detail ? (
        <Panel eyebrow="加载失败" title="暂时无法读取股票详情">
          <div className="rounded-[22px] border border-rose-400/20 bg-rose-400/10 p-5 text-sm text-rose-100">{error || '结果不存在'}</div>
        </Panel>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <div className="space-y-6">
            <Panel eyebrow={detail.ts_code} title={detail.stock_name}>
              <div className="grid gap-4 lg:grid-cols-2">
                <MetricTile label="总分" value={formatScore(detail.total_score)} hint={`全市场排名 ${detail.global_rank || '--'}`} />
                <MetricTile
                  label="行业排名"
                  value={detail.industry_rank && detail.industry_total ? `${detail.industry_rank}/${detail.industry_total}` : '--'}
                  hint={detail.sw_level1_industry}
                />
              </div>
              <div className="mt-5 flex flex-wrap gap-2">
                <StatusPill tone={detail.is_filtered ? 'rose' : 'emerald'}>{detail.is_filtered ? '已过滤' : detail.current_pool || '观察池'}</StatusPill>
                <StatusPill tone="slate">{detail.sw_level1_industry}</StatusPill>
                {(detail.warning_tags || []).map((tag) => (
                  <StatusPill key={tag} tone="slate">
                    {presentRuleLabel(tag)}
                  </StatusPill>
                ))}
              </div>
              <div className="mt-5 rounded-[22px] border border-white/10 bg-white/[0.03] p-4 text-sm leading-7 text-slate-300">
                {detail.is_filtered
                  ? '这只股票本次没有通过硬过滤，当前详情更适合用来理解它被拦下的原因。'
                  : `这只股票当前位于${detail.current_pool || '观察池'}，可以结合四个一级维度和同行对比判断它是“高分合理”还是“结果待复核”。`}
              </div>
            </Panel>

            <Panel eyebrow="四个一级维度" title="为什么在这里">
              <div className="grid gap-4 md:grid-cols-2">
                {dimensionTiles.map(([label, value, description]) => (
                  <MetricTile key={label} label={label} value={value} hint={description} />
                ))}
              </div>
            </Panel>

            <Panel eyebrow="规则判断" title="硬过滤、预警与研究提示">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
                  <p className="text-xs uppercase tracking-[0.22em] text-slate-500">硬过滤结果</p>
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
                      <p className="text-sm text-slate-400">没有触发硬过滤原因。</p>
                    )}
                  </div>
                </div>
                <div className="rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
                  <p className="text-xs uppercase tracking-[0.22em] text-slate-500">预警与辅助信息</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {(detail.warning_tags || []).length > 0 ? (
                      detail.warning_tags?.map((tag) => (
                        <StatusPill key={tag} tone="slate">
                          {presentRuleLabel(tag)}
                        </StatusPill>
                      ))
                    ) : (
                      <p className="text-sm text-slate-400">当前没有 warning 标签。</p>
                    )}
                  </div>
                  <div className="mt-4 space-y-2 text-sm text-slate-400">
                    <p>最新报告期：{detail.latest_report_period || '--'}</p>
                    <p>审计意见：{detail.audit_opinion || '--'}</p>
                    <p>所属市场：{detail.market || '--'}</p>
                  </div>
                </div>
              </div>
            </Panel>

            <Panel eyebrow="原始指标" title="二级指标与财报口径">
              <div className="space-y-5">
                {metricGroups.map((group) => (
                  <div key={group.title}>
                    <div className="mb-3 flex items-center gap-2">
                      <StatusPill tone="cyan">{group.title}</StatusPill>
                    </div>
                    <div className="space-y-3">
                      {group.items.map(([label, key, mode]) => (
                        <div key={key} className="flex items-center justify-between rounded-[20px] border border-white/10 bg-white/[0.03] px-4 py-3">
                          <span className="text-sm text-slate-300">{label}</span>
                          <span className="font-semibold text-white">
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

          <div className="space-y-6">
            <Panel eyebrow="运行上下文" title="本次结果来源">
              <div className="space-y-3 text-sm text-slate-300">
                <div className="rounded-[20px] border border-white/10 bg-white/[0.03] px-4 py-3">run_id：{detail.run_id}</div>
                <div className="rounded-[20px] border border-white/10 bg-white/[0.03] px-4 py-3">rule_version：{detail.rule_version || '--'}</div>
                <div className="rounded-[20px] border border-white/10 bg-white/[0.03] px-4 py-3">data_version：{detail.data_version || '--'}</div>
                <div className="rounded-[20px] border border-white/10 bg-white/[0.03] px-4 py-3">latest_report_period：{detail.latest_report_period || '--'}</div>
                <div className="rounded-[20px] border border-white/10 bg-white/[0.03] px-4 py-3">audit_opinion：{detail.audit_opinion || '--'}</div>
              </div>
            </Panel>

            <Panel eyebrow="同行业对比" title={detail.sw_level1_industry}>
              <div className="mb-4 rounded-[22px] border border-cyan-300/20 bg-cyan-300/[0.06] p-4">
                <p className="text-xs uppercase tracking-[0.22em] text-cyan-100/70">当前股票</p>
                <div className="mt-3 flex items-start justify-between gap-4">
                  <div>
                    <p className="font-semibold text-white">{detail.stock_name}</p>
                    <p className="mt-1 text-xs uppercase tracking-[0.22em] text-slate-400">
                      {detail.ts_code} · 行业排名 {detail.industry_rank && detail.industry_total ? `${detail.industry_rank}/${detail.industry_total}` : '--'}
                    </p>
                  </div>
                  <p className="font-serif text-2xl text-white">{formatScore(detail.total_score)}</p>
                </div>
              </div>
              <div className="space-y-3">
                {(peers?.peers || []).map((peer) => (
                  <div key={peer.ts_code} className="rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-semibold text-white">{peer.stock_name}</p>
                          <StatusPill tone={peer.current_pool === '重点观察池' ? 'emerald' : 'slate'}>{peer.current_pool || '观察池'}</StatusPill>
                        </div>
                        <p className="mt-1 text-xs uppercase tracking-[0.22em] text-slate-500">
                          {peer.ts_code} · 行业排名 {peer.industry_rank || '--'}
                        </p>
                        <div className="mt-3 grid gap-2 text-xs text-slate-400 md:grid-cols-2">
                          <span>业务质量 {formatScore(peer.biz_quality_score)}</span>
                          <span>成长兑现 {formatScore(peer.growth_delivery_score)}</span>
                          <span>财务质量 {formatScore(peer.financial_quality_score)}</span>
                          <span>估值匹配 {formatScore(peer.valuation_fit_score)}</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-serif text-2xl text-white">{formatScore(peer.total_score)}</p>
                        <Link
                          to={{ pathname: `/stocks/${peer.ts_code}`, search: createSearchParams({ run: detail.run_id }).toString() }}
                          className="mt-2 inline-flex text-xs font-semibold text-cyan-200 transition hover:text-cyan-100"
                        >
                          查看详情
                        </Link>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        </div>
      )}
    </AppShell>
  )
}
