import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { getRunList } from '@/api/console'
import type { RunSummary } from '@/types/console'

type RunSwitcherProps = {
  currentRunId: string | null
}

function formatRunLabel(run: RunSummary) {
  const timestamp = run.finished_at || run.started_at
  const shortId = run.run_id.slice(0, 8)
  const dateLabel = timestamp ? timestamp.slice(0, 10) : '未完成'
  return `${shortId} · ${dateLabel}`
}

export function RunSwitcher({ currentRunId }: RunSwitcherProps) {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [loading, setLoading] = useState(true)
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    let active = true

    async function load() {
      try {
        const response = await getRunList(20)
        if (!active) return
        setRuns(response.items)
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
  }, [])

  const options = useMemo(() => {
    if (!currentRunId) {
      return runs
    }
    const exists = runs.some((run) => run.run_id === currentRunId)
    if (exists) {
      return runs
    }
    const currentRunOption: RunSummary = {
      run_id: currentRunId,
      rule_version: '',
      data_version: '',
      run_status: 'success',
      total_stocks: null,
      passed_filter_count: null,
      key_watch_count: null,
      watch_count: null,
      started_at: '',
      finished_at: null,
    }
    return [
      currentRunOption,
      ...runs,
    ]
  }, [currentRunId, runs])

  function handleChange(runId: string) {
    const params = new URLSearchParams(location.search)
    if (runId) {
      params.set('run', runId)
    } else {
      params.delete('run')
    }

    navigate({
      pathname: location.pathname,
      search: params.toString() ? `?${params.toString()}` : '',
    })
  }

  return (
    <label className="flex items-center gap-3 rounded-full border border-slate-200 bg-white/85 px-4 py-2 text-sm text-slate-700 shadow-[0_12px_30px_rgba(15,23,42,0.06)]">
      <span className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Run</span>
      <select
        value={currentRunId || ''}
        onChange={(event) => handleChange(event.target.value)}
        disabled={loading || options.length === 0}
        className="min-w-[220px] bg-transparent text-sm font-medium text-slate-900 outline-none disabled:text-slate-400"
      >
        <option value="" className="bg-white text-slate-900">
          {loading ? '读取 run 列表中…' : '选择 run'}
        </option>
        {options.map((run) => (
          <option key={run.run_id} value={run.run_id} className="bg-white text-slate-900">
            {formatRunLabel(run)}
          </option>
        ))}
      </select>
    </label>
  )
}
