import { getRuleFieldLabel } from '@/lib/ruleMessages'
import { formatPercent } from '@/lib/format'
import { StatusPill } from '@/components/ui/StatusPill'
import type { RuleSnapshot } from '@/types/console'

type RuleSnapshotSummaryProps = {
  snapshot?: RuleSnapshot | null
  applyMode?: 'run_once' | 'save_as_default' | string | null
  variant?: 'compact' | 'full'
  emptyText?: string
}

const applyModeLabelMap = {
  run_once: '临时运行',
  save_as_default: '保存为默认',
}

const thresholdFields = [
  'pool_thresholds.key_watch_top_n',
  'hard_filters.liquidity.exclude_market_cap_lt_cny',
  'hard_filters.liquidity.exclude_avg_turnover_20d_lt_cny',
  'hard_filters.leverage.exclude_asset_liability_ratio_gt',
  'hard_filters.cashflow.exclude_cash_conversion_ratio_3y_lt',
] as const

const topLevelWeightFields = [
  'top_level_weights.biz_quality',
  'top_level_weights.growth_delivery',
  'top_level_weights.financial_quality',
  'top_level_weights.valuation_fit',
] as const

const dimensionFieldGroups = {
  biz_quality: [
    'score_dimensions.biz_quality.gross_margin',
    'score_dimensions.biz_quality.roe_avg_3y',
    'score_dimensions.biz_quality.net_margin_avg_3y',
    'score_dimensions.biz_quality.industry_position',
  ],
  growth_delivery: [
    'score_dimensions.growth_delivery.revenue_cagr_3y',
    'score_dimensions.growth_delivery.nonrec_np_cagr_3y',
    'score_dimensions.growth_delivery.shareholder_return_ratio_3y',
  ],
  financial_quality: [
    'score_dimensions.financial_quality.cash_conversion_ratio_3y',
    'score_dimensions.financial_quality.asset_liability_ratio_latest',
    'score_dimensions.financial_quality.capital_return_stability',
  ],
  valuation_fit: [
    'score_dimensions.valuation_fit.pe_ttm',
    'score_dimensions.valuation_fit.pb_latest',
    'score_dimensions.valuation_fit.dividend_yield_avg_3y',
  ],
} as const

function getValueByPath(snapshot: RuleSnapshot, path: string): number {
  const parts = path.split('.')
  let value: unknown = snapshot
  for (const part of parts) {
    value = (value as Record<string, unknown>)[part]
  }
  return Number(value)
}

function formatThresholdValue(path: string, value: number) {
  if (path === 'pool_thresholds.key_watch_top_n') {
    return `${value}`
  }
  if (path.includes('market_cap') || path.includes('turnover')) {
    if (value >= 100000000) return `${(value / 100000000).toFixed(1)} 亿`
    if (value >= 10000) return `${(value / 10000).toFixed(0)} 万`
    return `${value}`
  }
  return formatPercent(value)
}

function formatWeightValue(value: number) {
  return formatPercent(value, 0)
}

export function RuleSnapshotSummary({
  snapshot,
  applyMode,
  variant = 'compact',
  emptyText = '当前没有可展示的规则快照。',
}: RuleSnapshotSummaryProps) {
  if (!snapshot) {
    return (
      <div className="rounded-[22px] border border-dashed border-white/10 bg-white/[0.02] p-5 text-sm leading-7 text-slate-400">
        {emptyText}
      </div>
    )
  }

  const applyModeLabel =
    applyMode && applyMode in applyModeLabelMap
      ? applyModeLabelMap[applyMode as keyof typeof applyModeLabelMap]
      : applyMode || '规则快照'

  return (
    <div className="rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-slate-500">规则实验记录</p>
          <p className="mt-2 text-sm text-slate-300">以下参数就是这次 run 实际使用的规则快照。</p>
        </div>
        <StatusPill tone="cyan">{applyModeLabel}</StatusPill>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {thresholdFields.map((path) => {
          const value = getValueByPath(snapshot, path)
          return (
            <div key={path} className="rounded-[20px] border border-white/8 bg-slate-950/40 p-3">
              <p className="text-xs text-slate-500">{getRuleFieldLabel(path)}</p>
              <p className="mt-2 text-sm font-semibold text-white">{formatThresholdValue(path, value)}</p>
            </div>
          )
        })}
      </div>

      <div className="mt-4 rounded-[20px] border border-white/8 bg-slate-950/30 p-4">
        <p className="text-xs uppercase tracking-[0.22em] text-slate-500">一级维度权重</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {topLevelWeightFields.map((path) => (
            <StatusPill key={path} tone="slate">
              {getRuleFieldLabel(path)} {formatWeightValue(getValueByPath(snapshot, path))}
            </StatusPill>
          ))}
        </div>
      </div>

      {variant === 'full' ? (
        <div className="mt-4 grid gap-3 xl:grid-cols-2">
          {Object.entries(dimensionFieldGroups).map(([group, fields]) => (
            <div key={group} className="rounded-[20px] border border-white/8 bg-slate-950/30 p-4">
              <p className="text-xs uppercase tracking-[0.22em] text-slate-500">{getRuleFieldLabel(`top_level_weights.${group}`)}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {fields.map((path) => (
                  <StatusPill key={path} tone="slate">
                    {getRuleFieldLabel(path)} {formatWeightValue(getValueByPath(snapshot, path))}
                  </StatusPill>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}
