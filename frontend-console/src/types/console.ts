export type RunStatus = 'running' | 'success' | 'failed'

export type PoolType = '重点观察池' | '观察池' | null

export type ApiResponse<T> = {
  code: number
  message: string
  data: T
}

export type RunSummary = {
  run_id: string
  rule_version: string
  data_version: string
  run_status: RunStatus
  total_stocks: number | null
  passed_filter_count: number | null
  key_watch_count: number | null
  watch_count: number | null
  started_at: string
  finished_at: string | null
  created_at?: string
  updated_at?: string
  apply_mode?: string
  rule_snapshot?: RuleSnapshot
}

export type StockListItem = {
  run_id: string
  ts_code: string
  stock_name: string
  sw_level1_industry: string
  current_pool: PoolType
  total_score: number | null
  industry_rank: number | null
  industry_total: number | null
  global_rank: number | null
  warning_tags: string[]
  is_filtered: boolean
}

export type StockDetail = StockListItem & {
  market?: string
  latest_report_period?: string | null
  audit_opinion?: string | null
  biz_quality_score?: number | null
  growth_delivery_score?: number | null
  financial_quality_score?: number | null
  valuation_fit_score?: number | null
  filter_reasons?: string[]
  data_version?: string
  rule_version?: string
  pe_ttm?: number | null
  pb_latest?: number | null
  dividend_yield_avg_3y?: number | null
  gross_margin_avg_3y?: number | null
  roe_avg_3y?: number | null
  net_margin_avg_3y?: number | null
  revenue_cagr_3y?: number | null
  nonrec_np_cagr_3y?: number | null
  shareholder_return_ratio_3y?: number | null
  cash_conversion_ratio_3y?: number | null
  asset_liability_ratio_latest?: number | null
}

export type IndustrySummary = {
  sw_level1_industry: string
  stock_count: number
  avg_total_score: number | null
  max_total_score: number | null
  key_watch_count: number
  watch_count: number
}

export type RunReviewMetrics = {
  total_stocks: number
  passed_filter_count: number
  filtered_count: number
  key_watch_count: number
  watch_count: number
  warning_stock_count: number
  manual_review_count: number
  data_missing_count: number
  avg_warning_tags_per_stock: number | null
  avg_total_score: number | null
  pass_rate: number
  filtered_rate: number
  key_watch_rate: number
  watch_rate: number
  warning_stock_rate: number
  manual_review_rate: number
  data_missing_rate: number
}

export type RunWarningTagSummary = {
  warning_tag: string
  stock_count: number
}

export type RunIndustryReviewItem = {
  sw_level1_industry: string
  stock_count: number
  passed_count: number
  key_watch_count: number
  watch_count: number
  warning_stock_count: number
  avg_total_score: number | null
}

export type RunWarningOutlierItem = {
  ts_code: string
  stock_name: string
  sw_level1_industry: string
  current_pool: PoolType
  total_score: number | null
  global_rank: number | null
  warning_tags: string[]
  warning_count: number
}

export type RunQualityOverview = {
  run_summary: RunSummary
  metrics: RunReviewMetrics
  top_warning_tags: RunWarningTagSummary[]
  industries: RunIndustryReviewItem[]
  warning_outliers: RunWarningOutlierItem[]
}

export type RuleSnapshot = {
  rule_version: string
  hard_filters: Record<string, Record<string, number | boolean | string[] | null>>
  score_dimensions: Record<string, Record<string, number>>
  top_level_weights: Record<string, number>
  pool_thresholds: {
    key_watch_top_n: number
    key_watch_min_score: number
  }
}

export type TaskStatus = {
  task_id: string
  run_id: string | null
  task_status: 'queued' | 'running' | 'success' | 'failed'
  apply_mode: 'run_once' | 'save_as_default'
  requested_rule_snapshot?: RuleSnapshot
  total_count: number | null
  done_count: number
  failed_count: number
  progress_stage: string | null
  latest_message: string | null
  log_path: string | null
  error_message: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export type PeerPayload = {
  target: StockDetail
  peers: Array<
    Pick<
      StockDetail,
      | 'ts_code'
      | 'stock_name'
      | 'sw_level1_industry'
      | 'total_score'
      | 'current_pool'
      | 'global_rank'
      | 'industry_rank'
      | 'biz_quality_score'
      | 'growth_delivery_score'
      | 'financial_quality_score'
      | 'valuation_fit_score'
    >
  >
}
