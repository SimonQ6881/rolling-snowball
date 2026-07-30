import type { RuleSnapshot } from '@/types/console'
import { getRuleFieldErrorMessage, getRuleFieldWarningMessage } from '@/lib/ruleMessages'

type GroupErrorCounts = {
  hardFilters: number
  topLevelWeights: number
  poolThresholds: number
  scoreDimensions: Record<string, number>
}

export type RuleValidationSummary = {
  fieldErrors: Record<string, string>
  fieldWarnings: Record<string, string>
  groupErrorCounts: GroupErrorCounts
  errorCount: number
  warningCount: number
  hasErrors: boolean
}

function createEmptySummary(): RuleValidationSummary {
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

function validateRatio(value: number) {
  if (Number.isNaN(value)) {
    return 'required' as const
  }
  if (!Number.isFinite(value)) {
    return 'invalid_number' as const
  }
  if (value < 0 || value > 1) {
    return 'range_0_1' as const
  }
  return null
}

function validateNonNegative(value: number) {
  if (Number.isNaN(value)) {
    return 'required' as const
  }
  if (!Number.isFinite(value)) {
    return 'invalid_number' as const
  }
  if (value < 0) {
    return 'non_negative' as const
  }
  return null
}

function validatePositiveInteger(value: number) {
  if (Number.isNaN(value)) {
    return 'required' as const
  }
  if (!Number.isFinite(value)) {
    return 'invalid_number' as const
  }
  if (!Number.isInteger(value)) {
    return 'invalid_integer' as const
  }
  if (value < 1) {
    return 'positive_integer' as const
  }
  return null
}

function setError(summary: RuleValidationSummary, path: string, message: string) {
  summary.fieldErrors[path] = message
  summary.errorCount += 1
}

function setWarning(summary: RuleValidationSummary, path: string, message: string) {
  summary.fieldWarnings[path] = message
  summary.warningCount += 1
}

export function parseNumericInput(value: string): number {
  if (value.trim() === '') {
    return Number.NaN
  }
  return Number(value)
}

export function displayNumericInput(value: number): number | '' {
  return Number.isFinite(value) ? value : ''
}

export function getRuleValidationSummary(rule: RuleSnapshot): RuleValidationSummary {
  const summary = createEmptySummary()

  const hardFilterChecks = [
    ['hard_filters.liquidity.exclude_market_cap_lt_cny', rule.hard_filters.liquidity?.exclude_market_cap_lt_cny, 'amount'],
    ['hard_filters.liquidity.exclude_avg_turnover_20d_lt_cny', rule.hard_filters.liquidity?.exclude_avg_turnover_20d_lt_cny, 'amount'],
    ['hard_filters.leverage.exclude_asset_liability_ratio_gt', rule.hard_filters.leverage?.exclude_asset_liability_ratio_gt, 'ratio'],
    ['hard_filters.cashflow.exclude_cash_conversion_ratio_3y_lt', rule.hard_filters.cashflow?.exclude_cash_conversion_ratio_3y_lt, 'ratio'],
  ] as const

  for (const [path, rawValue, type] of hardFilterChecks) {
    const value = Number(rawValue)
    const code = type === 'ratio' ? validateRatio(value) : validateNonNegative(value)
    if (code) {
      setError(summary, path, getRuleFieldErrorMessage(path, code))
      summary.groupErrorCounts.hardFilters += 1
      continue
    }
    if (type === 'amount' && value >= 0 && value < 1) {
      const warningCode =
        path === 'hard_filters.liquidity.exclude_market_cap_lt_cny'
          ? 'weak_market_cap_threshold'
          : 'weak_turnover_threshold'
      setWarning(summary, path, getRuleFieldWarningMessage(path, warningCode))
    }
  }

  for (const [key, rawValue] of Object.entries(rule.top_level_weights)) {
    const path = `top_level_weights.${key}`
    const code = validateRatio(Number(rawValue))
    if (code) {
      setError(summary, path, getRuleFieldErrorMessage(path, code))
      summary.groupErrorCounts.topLevelWeights += 1
    }
  }

  for (const [group, weights] of Object.entries(rule.score_dimensions)) {
    let groupErrors = 0
    for (const [key, rawValue] of Object.entries(weights)) {
      const path = `score_dimensions.${group}.${key}`
      const code = validateRatio(Number(rawValue))
      if (code) {
        setError(summary, path, getRuleFieldErrorMessage(path, code))
        groupErrors += 1
      }
    }
    summary.groupErrorCounts.scoreDimensions[group] = groupErrors
  }

  const topNCode = validatePositiveInteger(Number(rule.pool_thresholds.key_watch_top_n))
  if (topNCode) {
    setError(summary, 'pool_thresholds.key_watch_top_n', getRuleFieldErrorMessage('pool_thresholds.key_watch_top_n', topNCode))
    summary.groupErrorCounts.poolThresholds += 1
  }

  summary.hasErrors = summary.errorCount > 0
  return summary
}
