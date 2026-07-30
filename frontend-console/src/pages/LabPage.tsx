import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { createRun, getActiveRule, validateRule } from '@/api/console'
import { AppShell } from '@/components/layout/AppShell'
import { MetricTile } from '@/components/ui/MetricTile'
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
    return 'rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-rose-300 focus:bg-white'
  }
  if (changed) {
    return 'rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-sky-300 focus:bg-white'
  }
  if (hasWarning) {
    return 'rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-amber-300 focus:bg-white'
  }
  return 'rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-slate-300 focus:bg-white'
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
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
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
        className="rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
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
    <div className="rounded-[24px] border border-slate-200/80 bg-slate-50/85 p-4 shadow-[0_16px_32px_rgba(15,23,42,0.05)]">
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
            <label key={key} className="flex flex-col gap-2 rounded-[20px] border border-white/70 bg-white p-3 shadow-[0_12px_28px_rgba(15,23,42,0.04)]">
              <span className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-700">
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
              {fieldError ? <span className="text-xs text-rose-700">{fieldError}</span> : null}
              {!fieldError && changed ? <span className="text-xs text-sky-700">默认值：{String(defaultValue)}</span> : null}
              {!fieldError && fieldWarning ? <span className="text-xs text-amber-700">{fieldWarning}</span> : null}
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
  const balanceLabel = isRuleBalanced ? '权重已平衡' : '结构待调整'
  const editorPanelTitle =
    changeSummary.totalChanges > 0
      ? `当前共改动 ${changeSummary.totalChanges} 项，左侧继续调参，右侧随时查看反馈。`
      : '先调整左侧参数，再从右侧确认改动摘要、校验状态和运行方式。'

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
          <div className="h-72 animate-pulse rounded-[24px] bg-slate-100" />
        </Panel>
      </AppShell>
    )
  }

  if (!rule || !defaultRule) {
    return (
      <AppShell title="规则实验台" subtitle="先调硬过滤阈值和评分权重，再决定是只用于本次运行，还是保存成新的默认规则。">
        <Panel eyebrow="读取规则" title="暂时无法加载规则">
          <p className="text-sm leading-7 text-rose-700">{error || '默认规则读取失败，当前无法判断改动项。'}</p>
        </Panel>
      </AppShell>
    )
  }

  return (
    <AppShell title="规则实验台" subtitle="先调硬过滤阈值和评分权重，再决定是只用于本次运行，还是保存成新的默认规则。">
      <div className="grid gap-6 xl:grid-cols-[1.18fr_0.82fr]">
        <div className="space-y-6">
          <Panel eyebrow="Cockpit Overview" title="当前规则版本与实验结构">
            <div className="rounded-[24px] border border-slate-200/80 bg-slate-50/85 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">当前规则版本</p>
              <p className="mt-3 font-serif text-3xl text-slate-950">{`默认规则 ${defaultRule.rule_version}`}</p>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">{editorPanelTitle}</p>
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <MetricTile label="改动字段" value={String(changeSummary.totalChanges)} hint={hasChanges ? '当前快照已偏离默认规则' : '当前仍沿用默认规则'} />
              <MetricTile label="涉及区域" value={String(changeSummary.changedAreas.length)} hint={changeSummary.changedAreas.length > 0 ? changeSummary.changedAreas.join(' / ') : '尚未产生改动'} />
              <MetricTile label="字段错误" value={String(validationSummary.errorCount)} hint={validationSummary.errorCount > 0 ? '修正后才能提交运行' : '当前没有阻断性错误'} />
              <MetricTile label="权重结构" value={balanceLabel} hint={`一级权重合计 ${weightSum.toFixed(2)}`} />
            </div>
          </Panel>

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
                  <label key={field} className="flex flex-col gap-2 rounded-[22px] border border-white/70 bg-white p-4 shadow-[0_12px_28px_rgba(15,23,42,0.04)]">
                    <span className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-700">
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
                    {fieldError ? <span className="text-xs text-rose-700">{fieldError}</span> : null}
                    {!fieldError && changed ? <span className="text-xs text-sky-700">默认值：{String(defaultValue)}</span> : null}
                    {!fieldError && fieldWarning ? <span className="text-xs text-amber-700">{fieldWarning}</span> : null}
                  </label>
                )
              })}
            </div>
          </Panel>

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

          <Panel
            eyebrow="重点观察池"
            title={
              validationSummary.groupErrorCounts.poolThresholds > 0
                ? `重点观察池名额 · ${validationSummary.groupErrorCounts.poolThresholds} 项错误`
                : changeSummary.groupCounts.poolThresholds > 0
                  ? `重点观察池名额 · 已改动 ${changeSummary.groupCounts.poolThresholds} 项`
                  : '重点观察池名额'
            }
          >
            <GroupHeader
              title="重点观察池"
              changedCount={changeSummary.groupCounts.poolThresholds}
              errorCount={validationSummary.groupErrorCounts.poolThresholds}
              onReset={restorePoolThresholds}
            />
            <label className="mt-5 flex flex-col gap-2 rounded-[22px] border border-white/70 bg-white p-4 shadow-[0_12px_28px_rgba(15,23,42,0.04)]">
              <span className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-700">
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
                <span className="text-xs text-rose-700">{validationSummary.fieldErrors['pool_thresholds.key_watch_top_n']}</span>
              ) : null}
              {!validationSummary.fieldErrors['pool_thresholds.key_watch_top_n'] && changeSummary.changedFieldPaths.has('pool_thresholds.key_watch_top_n') ? (
                <span className="text-xs text-sky-700">默认值：{String(defaultRule.pool_thresholds.key_watch_top_n)}</span>
              ) : null}
              {!validationSummary.fieldErrors['pool_thresholds.key_watch_top_n'] && validationSummary.fieldWarnings['pool_thresholds.key_watch_top_n'] ? (
                <span className="text-xs text-amber-700">{validationSummary.fieldWarnings['pool_thresholds.key_watch_top_n']}</span>
              ) : null}
            </label>
          </Panel>
        </div>

        <div className="space-y-6 xl:sticky xl:top-6 self-start">
          <Panel eyebrow="Change Summary" title="本次改动摘要">
            <div className="rounded-[24px] border border-slate-200/80 bg-slate-50/90 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">当前规则版本</p>
              <p className="mt-3 text-lg font-semibold text-slate-950">{`默认规则 ${defaultRule.rule_version}`}</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {hasChanges ? `本次共改动 ${changeSummary.totalChanges} 项，提交时将把当前快照附加到新任务。` : '当前还没有偏离默认规则，直接运行会沿用默认配置。'}
              </p>
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-3">
              <StatusPill tone={hasChanges ? 'cyan' : 'emerald'}>{hasChanges ? `本次共改动 ${changeSummary.totalChanges} 项` : '当前与默认规则一致'}</StatusPill>
              <StatusPill tone={isRuleBalanced ? 'emerald' : 'rose'}>{balanceLabel}</StatusPill>
              <StatusPill tone="slate">涉及区域 {changeSummary.changedAreas.length}</StatusPill>
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              {changeSummary.changedAreas.length > 0 ? (
                changeSummary.changedAreas.map((area) => (
                  <StatusPill key={area} tone="slate">
                    {area}
                  </StatusPill>
                ))
              ) : (
                <p className="text-sm leading-6 text-slate-600">还没有触发任何改动区域。左侧编辑区的字段一旦变化，这里会立即显示偏移范围。</p>
              )}
            </div>

            <div className="mt-5 rounded-[22px] border border-dashed border-slate-200 bg-white/80 p-4 text-sm leading-7 text-slate-600">
              {hasChanges ? `本次涉及 ${changeSummary.changedAreas.length} 个区域，提交前可以先用这里的区域标签和左侧高亮快速复核。` : '如果你只是想快速重跑一次，也可以不修改任何规则，直接沿用默认配置创建任务。'}
            </div>

            <div className="mt-5 flex flex-wrap gap-3">
              <button
                type="button"
                disabled={!hasChanges}
                onClick={restoreAllDefaults}
                className="rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                全部恢复默认
              </button>
            </div>
          </Panel>

          <Panel eyebrow="Validation" title="当前校验状态">
            <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3">
              <MetricTile label="字段错误" value={String(validationSummary.errorCount)} hint={validationSummary.errorCount > 0 ? '仍有字段超出合法范围' : '当前没有错误字段'} />
              <MetricTile label="提示项" value={String(validationSummary.warningCount)} hint={validationSummary.warningCount > 0 ? '建议提交前再复核一次' : '当前没有提醒项'} />
              <MetricTile label="一级权重" value={weightSum.toFixed(2)} hint={balanceLabel} />
            </div>
            <div className="mt-5 space-y-2 text-sm leading-7">
              <p className={validationSummary.hasErrors ? 'text-rose-700' : validationSummary.warningCount > 0 ? 'text-amber-700' : 'text-slate-700'}>{summaryHeadline}</p>
              {summarySecondary ? (
                <p className={!isRuleBalanced || validationSummary.warningCount > 0 ? 'text-amber-700' : 'text-slate-600'}>{summarySecondary}</p>
              ) : (
                <p className="text-slate-600">所有阻断性校验都通过后，右下角提交按钮会立即恢复可用。</p>
              )}
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              <StatusPill tone={validationSummary.hasErrors ? 'rose' : 'emerald'}>{summaryHeadline}</StatusPill>
              <StatusPill tone={isRuleBalanced ? 'emerald' : 'rose'}>{balanceLabel}</StatusPill>
              {validationSummary.warningCount > 0 ? <StatusPill tone="amber">{`提醒 ${validationSummary.warningCount} 项`}</StatusPill> : null}
            </div>
          </Panel>

          <Panel eyebrow="Submit" title="运行与保存">
            <div className="rounded-[24px] border border-slate-200/80 bg-slate-50/90 p-5">
              <p className={validationSummary.hasErrors ? 'text-sm leading-7 text-rose-700' : !isRuleBalanced ? 'text-sm leading-7 text-amber-700' : 'text-sm leading-7 text-slate-700'}>{submitAreaMessage}</p>
              <p className="mt-3 text-sm leading-6 text-slate-600">选择“保存为默认规则并运行”时，会把当前规则写回默认规则，后续运行会直接沿用这份配置。</p>
              {!isRuleBalanced ? <p className="mt-3 text-sm leading-6 text-amber-700">当前结构未平衡：至少有一组权重合计不等于 1。</p> : null}
              {notice ? <p className="mt-3 text-sm leading-6 text-sky-700">{notice}</p> : null}
              {error ? <p className="mt-3 text-sm leading-6 text-rose-700">{error}</p> : null}
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-1">
              <div className="rounded-[22px] border border-sky-200 bg-sky-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-700">Run Once</p>
                <p className="mt-2 text-sm font-semibold text-slate-950">仅本次生效并运行</p>
                <p className="mt-2 text-sm leading-6 text-slate-600">适合临时实验。默认规则不会被覆盖，但任务会记录当前快照。</p>
              </div>
              <div className="rounded-[22px] border border-slate-200 bg-white p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Save As Default</p>
                <p className="mt-2 text-sm font-semibold text-slate-950">保存为默认规则并运行</p>
                <p className="mt-2 text-sm leading-6 text-slate-600">适合已经确认的新默认配置，会同步更新后续运行基线。</p>
              </div>
            </div>

            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                disabled={!canSubmit}
                onClick={() => handleSubmit('run_once')}
                className="rounded-full border border-sky-200 bg-sky-50 px-5 py-3 text-sm font-semibold text-sky-700 transition hover:border-sky-300 hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {saving ? '正在创建任务…' : '仅本次生效并运行'}
              </button>
              <button
                type="button"
                disabled={!canSubmit}
                onClick={() => handleSubmit('save_as_default')}
                className="rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                保存为默认规则并运行
              </button>
            </div>
          </Panel>
        </div>
      </div>
    </AppShell>
  )
}
