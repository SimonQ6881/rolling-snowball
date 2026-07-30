import type {
  ApiResponse,
  IndustrySummary,
  PeerPayload,
  RuleSnapshot,
  RunQualityOverview,
  RunSummary,
  StockDetail,
  StockListItem,
  TaskStatus,
} from '@/types/console'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
    ...init,
  })

  const payload = (await response.json()) as ApiResponse<T>
  if (!response.ok || payload.code !== 0) {
    throw new Error(payload.message || '请求失败')
  }
  return payload.data
}

export function getLatestRun() {
  return request<RunSummary>('/api/runs/latest')
}

export function getRunList(limit = 20) {
  return request<{ items: RunSummary[] }>(`/api/runs?limit=${limit}`)
}

export function getRunSummary(runId: string) {
  return request<RunSummary>(`/api/runs/${runId}/summary`)
}

export function getRunQualityOverview(runId: string) {
  return request<RunQualityOverview>(`/api/runs/${runId}/review`)
}

export function getRunStocks(runId: string, search = '') {
  return request<{ items: StockListItem[] }>(`/api/runs/${runId}/stocks${search ? `?${search}` : ''}`)
}

export function getIndustryBoard(runId: string) {
  return request<{ items: IndustrySummary[] }>(`/api/runs/${runId}/industries`)
}

export function getStockDetail(runId: string, tsCode: string) {
  return request<StockDetail>(`/api/runs/${runId}/stocks/${tsCode}`)
}

export function getStockPeers(runId: string, tsCode: string) {
  return request<PeerPayload>(`/api/runs/${runId}/stocks/${tsCode}/peers`)
}

export function getActiveRule() {
  return request<RuleSnapshot>('/api/rules/active')
}

export function validateRule(snapshot: RuleSnapshot) {
  return request<RuleSnapshot>('/api/rules/validate', {
    method: 'POST',
    body: JSON.stringify(snapshot),
  })
}

export function createRun(payload: {
  data_version: string
  limit?: number
  apply_mode: 'run_once' | 'save_as_default'
  rule_snapshot?: RuleSnapshot
}) {
  return request<TaskStatus>('/api/runs', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getTask(taskId: string) {
  return request<TaskStatus>(`/api/tasks/${taskId}`)
}

export function getTaskList(limit = 20) {
  return request<{ items: TaskStatus[] }>(`/api/tasks?limit=${limit}`)
}

export function getTaskLogs(taskId: string) {
  return request<{ items: string[] }>(`/api/tasks/${taskId}/logs`)
}
