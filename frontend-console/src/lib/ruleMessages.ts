type ValidationErrorCode =
  | 'required'
  | 'invalid_number'
  | 'invalid_integer'
  | 'range_0_1'
  | 'non_negative'
  | 'positive_integer'

type ValidationWarningCode = 'weak_market_cap_threshold' | 'weak_turnover_threshold'

const fieldLabelMap: Record<string, string> = {
  'hard_filters.liquidity.exclude_market_cap_lt_cny': '市值门槛',
  'hard_filters.liquidity.exclude_avg_turnover_20d_lt_cny': '20日成交额门槛',
  'hard_filters.leverage.exclude_asset_liability_ratio_gt': '资产负债率上限',
  'hard_filters.cashflow.exclude_cash_conversion_ratio_3y_lt': '现金转化率下限',
  'pool_thresholds.key_watch_top_n': '重点观察池名额',
  'top_level_weights.biz_quality': '业务质量权重',
  'top_level_weights.growth_delivery': '成长兑现度权重',
  'top_level_weights.financial_quality': '财务质量权重',
  'top_level_weights.valuation_fit': '估值匹配度权重',
  'score_dimensions.biz_quality.gross_margin': '毛利率权重',
  'score_dimensions.biz_quality.roe_avg_3y': 'ROE 权重',
  'score_dimensions.biz_quality.net_margin_avg_3y': '净利率权重',
  'score_dimensions.biz_quality.industry_position': '行业地位权重',
  'score_dimensions.growth_delivery.revenue_cagr_3y': '营收增长权重',
  'score_dimensions.growth_delivery.nonrec_np_cagr_3y': '扣非净利增长权重',
  'score_dimensions.growth_delivery.shareholder_return_ratio_3y': '股东回报权重',
  'score_dimensions.financial_quality.cash_conversion_ratio_3y': '现金转化率权重',
  'score_dimensions.financial_quality.asset_liability_ratio_latest': '资产负债率权重',
  'score_dimensions.financial_quality.capital_return_stability': '资本回报稳定性权重',
  'score_dimensions.valuation_fit.pe_ttm': 'PE 权重',
  'score_dimensions.valuation_fit.pb_latest': 'PB 权重',
  'score_dimensions.valuation_fit.dividend_yield_avg_3y': '股息率权重',
}

export function getRuleFieldLabel(path: string): string {
  return fieldLabelMap[path] || path.split('.').at(-1) || path
}

export function getRuleFieldErrorMessage(path: string, code: ValidationErrorCode): string {
  const label = getRuleFieldLabel(path)
  switch (code) {
    case 'required':
      return `${label}不能为空，请先输入数值`
    case 'invalid_number':
      return `${label}请输入有效数字`
    case 'invalid_integer':
      return `${label}请输入有效整数`
    case 'range_0_1':
      return `${label}必须在 0 到 1 之间`
    case 'non_negative':
      return `${label}必须大于等于 0`
    case 'positive_integer':
      return `${label}必须是大于等于 1 的整数`
    default:
      return `${label}输入不合法`
  }
}

export function getRuleFieldWarningMessage(path: string, code: ValidationWarningCode): string {
  const label = getRuleFieldLabel(path)
  switch (code) {
    case 'weak_market_cap_threshold':
      return `当前${label}较低，筛选约束可能偏弱`
    case 'weak_turnover_threshold':
      return `当前${label}较低，可能会放入更多流动性较弱样本`
    default:
      return `${label}当前值可能需要再复核`
  }
}

export function getValidationSummaryHeadline(errorCount: number, warningCount: number): string {
  if (errorCount > 0) {
    return `当前有 ${errorCount} 个字段超出合法范围，修正后才能运行`
  }
  if (warningCount > 0) {
    return '当前字段都合法，可以运行'
  }
  return '当前字段均合法'
}

export function getValidationSummarySecondary({
  errorCount,
  warningCount,
  isRuleBalanced,
}: {
  errorCount: number
  warningCount: number
  isRuleBalanced: boolean
}): string | null {
  if (errorCount > 0 && !isRuleBalanced) {
    return '另外，当前权重结构还未平衡，至少有一组权重合计不等于 1'
  }
  if (errorCount > 0) {
    return null
  }
  if (!isRuleBalanced) {
    return '当前权重结构还未平衡，至少有一组权重合计不等于 1'
  }
  if (warningCount > 0) {
    return `有 ${warningCount} 项参数可能削弱筛选约束，建议提交前再看一眼`
  }
  return null
}

export function getSubmitAreaMessage({
  errorCount,
  isRuleBalanced,
  hasChanges,
  totalChanges,
}: {
  errorCount: number
  isRuleBalanced: boolean
  hasChanges: boolean
  totalChanges: number
}): string {
  if (errorCount > 0) {
    return '当前存在字段越界或输入格式错误，暂时不能发起运行'
  }
  if (!isRuleBalanced) {
    return '当前权重结构还未平衡，暂时不能发起运行'
  }
  if (hasChanges) {
    return `本次共改动 ${totalChanges} 项，提交时会按当前改动后的规则创建任务`
  }
  return '当前规则与默认规则一致，直接运行会沿用默认配置'
}

