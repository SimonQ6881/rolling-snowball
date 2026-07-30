import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { createRun, getActiveRule, validateRule } from '@/api/console'
import { AppShell } from '@/components/layout/AppShell'
import { Panel } from '@/components/ui/Panel'
import { StatusPill } from '@/components/ui/StatusPill'
import { cloneRuleSnapshot, getRuleChangeSummary, isRuleValueEqual } from '@/lib/ruleDiff'
import {
  getRuleFieldLabel,
  getSubmitAreaMessage,
  getValidationSummaryHeadline,
  getValidationSummarySecondary,
} from '@/lib/ruleMessages'
import { displayNumericInput, getRuleValidationSummary, parseNumericInput } from '@/lib/ruleValidation'
import type { RuleSnapshot } from '@/types/console'

type WeightGroupProps = {
  title: string
  weights: Record<string, number>
  defaultWeights: Record<string, number>
  sum: number
  changedCount: number
  errorCount: number
  pathPrefix: string
  onChange: (key: string, value: number) => void
  onReset: () => void
  validationErrors: Record<string, string>
  validationWarnings: Record<string, string>
}

function getInputClass({
  changed,
  hasError,
  hasWarning,
}: {
  changed: boolean
  hasError: boolean
  hasWarning: boolean
}) {
  if (hasError) {
    return 'rounded-2xl border border-rose-400/45 bg-rose-400/[0.08] px-4 py-3 text-white outline-none transition focus:border-rose-300/70'
  }
  if (changed) {
    return 'rounded-2xl border border-cyan-300/35 bg-cyan-300/[0.08] px-4 py-3 text-white outline-none transition focus:border-cyan-200/60'
  }
  if (hasWarning) {
    return 'rounded-2xl border border-amber-300/35 bg-amber-300/[0.06] px-4 py-3 text-white outline-none transition focus:border-amber-200/60'
  }
  return 'rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-white outline-none transition focus:border-cyan-300/40'
}

function GroupHeader({
  title,
  changedCount,
  errorCount,
  onReset,
}: {
  title: string
  changedCount: number
  errorCount: number
  onReset: () => void
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-xs uppercase tracking-[0.24em] text-slate-500">
          {errorCount > 0
            ? `${title} · ${errorCount} 项错误`
            : changedCount > 0
              ? `${title} · 已改动 ${changedCount} 项`
              : title}
        </p>
        {errorCount > 0 ? <StatusPill tone="rose">{errorCount} 项错误</StatusPill> : null}
        <StatusPill tone={changedCount > 0 ? 'cyan' : 'slate'}>{changedCount > 0 ? `已改动 ${changedCount} 项` : '未改动'}</StatusPill>
      </div>
      <button
        type="button"
        disabled={changedCount === 0}
        onClick={onReset}
        className="rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-xs font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-40"
      >
        恢复本组默认
      </button>
    </div>
  )
}

function WeightGroup({
  title,
  weights,
  defaultWeights,
  sum,
  changedCount,
  errorCount,
  pathPrefix,
  onChange,
  onReset,
  validationErrors,
  validationWarnings,
}: WeightGroupProps) {
  return (
    <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <GroupHeader title={title} changedCount={changedCount} errorCount={errorCount} onReset={onReset} />
        <StatusPill tone={Math.abs(sum - 1) < 0.0001 ? 'emerald' : 'rose'}>合计 {sum.toFixed(2)}</StatusPill>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {Object.entries(weights).map(([key, value]) => {
          const defaultValue = defaultWeights[key]
          const changed = !isRuleValueEqual(value, defaultValue)
          const path = `${pathPrefix}.${key}`
          const labelText = getRuleFieldLabel(path)
          const fieldError = validationErrors[path]
          const fieldWarning = validationWarnings[path]
          return (
            <label key={key} className="flex flex-col gap-2 rounded-[20px] border border-white/8 bg-white/[0.02] p-3">
              <span className="flex flex-wrap items-center gap-2 text-sm text-slate-300">
                {labelText}
                {fieldError ? <StatusPill tone="rose">错误</StatusPill> : null}
                {!fieldError && changed ? <StatusPill tone="cyan">已修改</StatusPill> : null}
              </span>
              <input
                type="number"
                step="0.01"
                value={displayNumericInput(value)}
                onChange={(event) => onChange(key, parseNumericInput(event.target.value))}
                data-path={path}
                className={getInputClass({ changed, hasError: Boolean(fieldError), hasWarning: Boolean(fieldWarning) })}
              />
              {fieldError ? <span className="text-xs text-rose-200">{fieldError}</span> : null}
              {!fieldError && changed ? <span className="text-xs text-cyan-100/80">默认值：{String(defaultValue)}</span> : null}
              {!fieldError && fieldWarning ? <span className="text-xs text-amber-200">{fieldWarning}</span> : null}
            </label>
          )
        })}
      </div>
    </div>
  )
}

const hardFilterFields = [
  ['liquidity', 'exclude_market_cap_lt_cny', '市值门槛（元）'],
  ['liquidity', 'exclude_avg_turnover_20d_lt_cny', '20日成交额门槛（元）'],
  ['leverage', 'exclude_asset_liability_ratio_gt', '资产负债率上限'],
  ['cashflow', 'exclude_cash_conversion_ratio_3y_lt', '现金转化率下限'],
] as const

export default function LabPage() {
  const navigate = useNavigate()
  const [rule, setRule] = useState<RuleSnapshot | null>(null)
  const [defaultRule, setDefaultRule] = useState<RuleSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function load() {
      try {
        setLoading(true)
        setError(null)
        const snapshot = await getActiveRule()
        if (!active) return
        setDefaultRule(cloneRuleSnapshot(snapshot))
        setRule(cloneRuleSnapshot(snapshot))
      } catch (loadError) {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : '规则读取失败')
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [])

  const weightSum = useMemo(() => {
    if (!rule) return 0
    return Object.values(rule.top_level_weights).reduce((sum, item) => sum + item, 0)
  }, [rule])

  const dimensionSums = useMemo(() => {
    if (!rule) return {}
    return Object.fromEntries(
      Object.entries(rule.score_dimensions).map(([group, weights]) => [
        group,
        Object.values(weights).reduce((sum, item) => sum + item, 0),
      ]),
    )
  }, [rule])

  const isRuleBalanced = useMemo(() => {
    if (!rule) return false
    if (Math.abs(weightSum - 1) >= 0.0001) {
      return false
    }
    return Object.values(dimensionSums).every((sum) => Math.abs(sum - 1) < 0.0001)
  }, [dimensionSums, rule, weightSum])

  const changeSummary = useMemo(() => {
    if (!rule || !defaultRule) {
      return {
        totalChanges: 0,
        changedAreas: [],
        changedFieldPaths: new Set<string>(),
        groupCounts: {
          hardFilters: 0,
          topLevelWeights: 0,
          poolThresholds: 0,
          scoreDimensions: {},
        },
      }
    }
    return getRuleChangeSummary(defaultRule, rule)
  }, [defaultRule, rule])

  const validationSummary = useMemo(() => {
    if (!rule) {
      return {
        fieldErrors: {},
        fieldWarnings: {},
        groupErrorCounts: {
          hardFilters: 0,
          topLevelWeights: 0,
          poolThresholds: 0,
          scoreDimensions: {},
        },
        errorCount: 0,
        warningCount: 0,
        hasErrors: false,
      }
    }
    return getRuleValidationSummary(rule)
  }, [rule])

  const hasChanges = changeSummary.totalChanges > 0
  const canSubmit = !validationSummary.hasErrors && isRuleBalanced && !saving
  const summaryHeadline = getValidationSummaryHeadline(validationSummary.errorCount, validationSummary.warningCount)
  const summarySecondary = getValidationSummarySecondary({
    errorCount: validationSummary.errorCount,
    warningCount: validationSummary.warningCount,
    isRuleBalanced,
  })
  const submitAreaMessage = getSubmitAreaMessage({
    errorCount: validationSummary.errorCount,
    isRuleBalanced,
    hasChanges,
    totalChanges: changeSummary.totalChanges,
  })

  function applyRuleChange(nextRule: RuleSnapshot) {
    setRule(nextRule)
    setNotice(null)
    setError(null)
  }

  function updateHardFilter(section: keyof RuleSnapshot['hard_filters'], field: string, value: number) {
    if (!rule) return
    applyRuleChange({
      ...rule,
      hard_filters: {
        ...rule.hard_filters,
        [section]: {
          ...rule.hard_filters[section],
          [field]: value,
        },
      },
    })
  }

  function updateTopLevelWeight(field: string, value: number) {
    if (!rule) return
    applyRuleChange({
      ...rule,
      top_level_weights: {
        ...rule.top_level_weights,
        [field]: value,
      },
    })
  }

  function updateDimensionWeight(group: string, field: string, value: number) {
    if (!rule) return
    applyRuleChange({
      ...rule,
      score_dimensions: {
        ...rule.score_dimensions,
        [group]: {
          ...rule.score_dimensions[group],
          [field]: value,
        },
      },
    })
  }

  function restoreHardFilters() {
    if (!rule || !defaultRule) return
    applyRuleChange({
      ...rule,
      hard_filters: cloneRuleSnapshot(defaultRule).hard_filters,
    })
  }

  function restoreTopLevelWeights() {
    if (!rule || !defaultRule) return
    applyRuleChange({
      ...rule,
      top_level_weights: { ...defaultRule.top_level_weights },
    })
  }

  function restoreDimensionGroup(group: string) {
    if (!rule || !defaultRule) return
    applyRuleChange({
      ...rule,
      score_dimensions: {
        ...rule.score_dimensions,
        [group]: { ...defaultRule.score_dimensions[group] },
      },
    })
  }

  function restorePoolThresholds() {
    if (!rule || !defaultRule) return
    applyRuleChange({
      ...rule,
      pool_thresholds: { ...defaultRule.pool_thresholds },
    })
  }

  function restoreAllDefaults() {
    if (!defaultRule) return
    applyRuleChange(cloneRuleSnapshot(defaultRule))
  }

  async function handleSubmit(applyMode: 'run_once' | 'save_as_default') {
    if (!rule || !canSubmit) return

    try {
      setSaving(true)
      setError(null)
      setNotice(
        applyMode === 'save_as_default'
          ? '正在保存当前规则为默认版本…'
          : hasChanges
            ? `正在按本次改动后的规则创建任务，共 ${changeSummary.totalChanges} 项改动…`
            : '当前规则与默认规则一致，正在创建任务…',
      )
      const validated = await validateRule(rule)
      const task = await createRun({
        data_version: new Date().toISOString().slice(0, 10).replace(/-/g, ''),
        apply_mode: applyMode,
        rule_snapshot: validated,
      })
      navigate(`/tasks/${task.task_id}`)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : '任务创建失败')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <AppShell title="规则实验台" subtitle="先调硬过滤阈值和评分权重，再决定是只用于本次运行，还是保存成新的默认规则。">
        <Panel eyebrow="读取规则" title="正在加载默认规则…">
          <div className="h-72 animate-pulse rounded-[24px] bg-white/[0.05]" />
        </Panel>
      </AppShell>
    )
  }

  if (!rule || !defaultRule) {
    return (
      <AppShell title="规则实验台" subtitle="先调硬过滤阈值和评分权重，再决定是只用于本次运行，还是保存成新的默认规则。">
        <Panel eyebrow="读取规则" title="暂时无法加载规则">
          <p className="text-sm leading-7 text-rose-200">{error || '默认规则读取失败，当前无法判断改动项。'}</p>
        </Panel>
      </AppShell>
    )
  }

  return (
    <AppShell title="规则实验台" subtitle="先调硬过滤阈值和评分权重，再决定是只用于本次运行，还是保存成新的默认规则。">
      <div className="space-y-6">
        <Panel eyebrow="改动感知" title="本次改动摘要">
          <div className="flex flex-wrap items-center gap-3">
            <StatusPill tone={hasChanges ? 'cyan' : 'emerald'}>
              {hasChanges ? `本次共改动 ${changeSummary.totalChanges} 项` : '当前与默认规则一致'}
            </StatusPill>
            <StatusPill tone={validationSummary.hasErrors ? 'rose' : 'emerald'}>
              {summaryHeadline}
            </StatusPill>
            <StatusPill tone={isRuleBalanced ? 'emerald' : 'rose'}>{isRuleBalanced ? '权重已平衡' : '结构未平衡'}</StatusPill>
            <StatusPill tone="slate">涉及区域 {changeSummary.changedAreas.length}</StatusPill>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {changeSummary.changedAreas.length > 0 ? (
              changeSummary.changedAreas.map((area) => (
                <StatusPill key={area} tone="slate">
                  {area}
                </StatusPill>
              ))
            ) : (
              <p className="text-sm text-slate-400">当前还没有偏离默认规则，直接运行会沿用默认配置。</p>
            )}
          </div>
          <div className="mt-4 space-y-2 text-sm leading-7">
            <p className={validationSummary.hasErrors ? 'text-rose-200' : validationSummary.warningCount > 0 ? 'text-amber-200' : 'text-slate-300'}>{summaryHeadline}</p>
            {summarySecondary ? (
              <p className={!isRuleBalanced ? 'text-amber-200' : validationSummary.warningCount > 0 ? 'text-amber-200' : 'text-slate-400'}>{summarySecondary}</p>
            ) : null}
            {!summarySecondary && !validationSummary.hasErrors && validationSummary.warningCount === 0 ? (
              <p className="text-slate-400">{hasChanges ? `本次涉及 ${changeSummary.changedAreas.length} 个区域，提交前可以先用高亮区快速复核。` : '如果你只是想快速重跑一次，也可以在不修改任何规则的情况下直接运行。'}</p>
            ) : null}
          </div>
          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              disabled={!hasChanges}
              onClick={restoreAllDefaults}
              className="rounded-full border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-40"
            >
              全部恢复默认
            </button>
          </div>
        </Panel>

        <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="space-y-6">
            <Panel
              eyebrow="硬过滤阈值"
              title={
                validationSummary.groupErrorCounts.hardFilters > 0
                  ? `先筛掉不想看的样本 · ${validationSummary.groupErrorCounts.hardFilters} 项错误`
                  : changeSummary.groupCounts.hardFilters > 0
                    ? `先筛掉不想看的样本 · 已改动 ${changeSummary.groupCounts.hardFilters} 项`
                    : '先筛掉不想看的样本'
              }
            >
              <GroupHeader
                title="硬过滤阈值"
                changedCount={changeSummary.groupCounts.hardFilters}
                errorCount={validationSummary.groupErrorCounts.hardFilters}
                onReset={restoreHardFilters}
              />
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                {hardFilterFields.map(([section, field, label]) => {
                  const path = `hard_filters.${section}.${field}`
                  const changed = changeSummary.changedFieldPaths.has(path)
                  const defaultValue = Number(defaultRule.hard_filters[section]?.[field] || 0)
                  const currentValue = Number(rule.hard_filters[section]?.[field])
                  const fieldError = validationSummary.fieldErrors[path]
                  const fieldWarning = validationSummary.fieldWarnings[path]

                  return (
                    <label key={field} className="flex flex-col gap-2 rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
                      <span className="flex flex-wrap items-center gap-2 text-sm text-slate-300">
                        {label}
                        {fieldError ? <StatusPill tone="rose">错误</StatusPill> : null}
                        {!fieldError && changed ? <StatusPill tone="cyan">已修改</StatusPill> : null}
                      </span>
                      <input
                        type="number"
                        step="0.01"
                        value={displayNumericInput(currentValue)}
                        onChange={(event) => updateHardFilter(section, field, parseNumericInput(event.target.value))}
                        data-path={path}
                        className={getInputClass({ changed, hasError: Boolean(fieldError), hasWarning: Boolean(fieldWarning) })}
                      />
                      {fieldError ? <span className="text-xs text-rose-200">{fieldError}</span> : null}
                      {!fieldError && changed ? <span className="text-xs text-cyan-100/80">默认值：{String(defaultValue)}</span> : null}
                      {!fieldError && fieldWarning ? <span className="text-xs text-amber-200">{fieldWarning}</span> : null}
                    </label>
                  )
                })}
              </div>
            </Panel>

            <Panel
              eyebrow="运行方式"
              title={
                validationSummary.groupErrorCounts.poolThresholds > 0
                  ? `这次规则怎么生效 · ${validationSummary.groupErrorCounts.poolThresholds} 项错误`
                  : changeSummary.groupCounts.poolThresholds > 0
                    ? `这次规则怎么生效 · 已改动 ${changeSummary.groupCounts.poolThresholds} 项`
                    : '这次规则怎么生效'
              }
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-3">
                  <StatusPill tone={Math.abs(weightSum - 1) < 0.0001 ? 'emerald' : 'rose'}>一级权重合计 {weightSum.toFixed(2)}</StatusPill>
                  <StatusPill tone="cyan">重点观察池前 {displayNumericInput(Number(rule.pool_thresholds.key_watch_top_n)) || '--'} 名</StatusPill>
                  <StatusPill tone={isRuleBalanced ? 'emerald' : 'rose'}>{isRuleBalanced ? '权重已平衡' : '结构未平衡'}</StatusPill>
                </div>
                <button
                  type="button"
                  disabled={changeSummary.groupCounts.poolThresholds === 0}
                  onClick={restorePoolThresholds}
                  className="rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-xs font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  恢复本组默认
                </button>
              </div>
              <label className="mt-5 flex flex-col gap-2 rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
                <span className="flex flex-wrap items-center gap-2 text-sm text-slate-300">
                  重点观察池名额
                  {validationSummary.fieldErrors['pool_thresholds.key_watch_top_n'] ? <StatusPill tone="rose">错误</StatusPill> : null}
                  {!validationSummary.fieldErrors['pool_thresholds.key_watch_top_n'] && changeSummary.changedFieldPaths.has('pool_thresholds.key_watch_top_n') ? (
                    <StatusPill tone="cyan">已修改</StatusPill>
                  ) : null}
                </span>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={displayNumericInput(Number(rule.pool_thresholds.key_watch_top_n))}
                  onChange={(event) =>
                    applyRuleChange({
                      ...rule,
                      pool_thresholds: {
                        ...rule.pool_thresholds,
                        key_watch_top_n: parseNumericInput(event.target.value),
                      },
                    })
                  }
                  data-path="pool_thresholds.key_watch_top_n"
                  className={getInputClass({
                    changed: changeSummary.changedFieldPaths.has('pool_thresholds.key_watch_top_n'),
                    hasError: Boolean(validationSummary.fieldErrors['pool_thresholds.key_watch_top_n']),
                    hasWarning: Boolean(validationSummary.fieldWarnings['pool_thresholds.key_watch_top_n']),
                  })}
                />
                {validationSummary.fieldErrors['pool_thresholds.key_watch_top_n'] ? (
                  <span className="text-xs text-rose-200">{validationSummary.fieldErrors['pool_thresholds.key_watch_top_n']}</span>
                ) : null}
                {!validationSummary.fieldErrors['pool_thresholds.key_watch_top_n'] &&
                changeSummary.changedFieldPaths.has('pool_thresholds.key_watch_top_n') ? (
                  <span className="text-xs text-cyan-100/80">默认值：{String(defaultRule.pool_thresholds.key_watch_top_n)}</span>
                ) : null}
              </label>
              <div className="mt-4 space-y-2 text-sm">
                <p className={validationSummary.hasErrors ? 'text-rose-200' : !isRuleBalanced ? 'text-amber-200' : 'text-slate-400'}>{submitAreaMessage}</p>
                <p className="text-slate-500">选择“保存为默认规则并运行”时，会把当前规则写回默认规则。</p>
                {!isRuleBalanced ? <p className="text-amber-200">当前结构未平衡：至少有一组权重合计不等于 1。</p> : null}
                {notice ? <p className="text-cyan-200">{notice}</p> : null}
                {error ? <p className="text-rose-200">{error}</p> : null}
              </div>
              <div className="mt-6 flex flex-wrap gap-3">
                <button
                  type="button"
                  disabled={!canSubmit}
                  onClick={() => handleSubmit('run_once')}
                  className="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-5 py-3 text-sm font-semibold text-cyan-100 transition hover:border-cyan-300/45 hover:bg-cyan-300/15 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saving ? '正在创建任务…' : '仅本次生效并运行'}
                </button>
                <button
                  type="button"
                  disabled={!canSubmit}
                  onClick={() => handleSubmit('save_as_default')}
                  className="rounded-full border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  保存为默认规则并运行
                </button>
              </div>
            </Panel>
          </div>

          <div className="space-y-6">
            <Panel
              eyebrow="一级维度权重"
              title={validationSummary.groupErrorCounts.topLevelWeights > 0 ? `总分如何分配 · ${validationSummary.groupErrorCounts.topLevelWeights} 项错误` : '总分如何分配'}
            >
              <WeightGroup
                title="一级维度"
                weights={rule.top_level_weights}
                defaultWeights={defaultRule.top_level_weights}
                sum={weightSum}
                changedCount={changeSummary.groupCounts.topLevelWeights}
                errorCount={validationSummary.groupErrorCounts.topLevelWeights}
                pathPrefix="top_level_weights"
                onChange={updateTopLevelWeight}
                onReset={restoreTopLevelWeights}
                validationErrors={validationSummary.fieldErrors}
                validationWarnings={validationSummary.fieldWarnings}
              />
            </Panel>

            <Panel eyebrow="二级指标权重" title="维度内部结构">
              <div className="space-y-4">
                {Object.entries(rule.score_dimensions).map(([group, weights]) => (
                  <WeightGroup
                    key={group}
                    title={group}
                    weights={weights}
                    defaultWeights={defaultRule.score_dimensions[group] || {}}
                    sum={dimensionSums[group] || 0}
                    changedCount={changeSummary.groupCounts.scoreDimensions[group] || 0}
                    errorCount={validationSummary.groupErrorCounts.scoreDimensions[group] || 0}
                    pathPrefix={`score_dimensions.${group}`}
                    onChange={(field, value) => updateDimensionWeight(group, field, value)}
                    onReset={() => restoreDimensionGroup(group)}
                    validationErrors={validationSummary.fieldErrors}
                    validationWarnings={validationSummary.fieldWarnings}
                  />
                ))}
              </div>
            </Panel>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
