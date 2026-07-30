import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { getRunList, getTaskList } from '@/api/console'
import { AppShell } from '@/components/layout/AppShell'
import { RuleSnapshotSummary } from '@/components/rules/RuleSnapshotSummary'
import { Panel } from '@/components/ui/Panel'
import { StatusPill } from '@/components/ui/StatusPill'
import { formatDateTime } from '@/lib/format'
import type { RunSummary, TaskStatus } from '@/types/console'

function getRunTone(status: RunSummary['run_status']) {
  if (status === 'success') return 'emerald'
  if (status === 'failed') return 'rose'
  return 'amber'
}

function getTaskTone(status: TaskStatus['task_status']) {
  if (status === 'success') return 'emerald'
  if (status === 'failed') return 'rose'
  return 'amber'
}

export default function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [tasks, setTasks] = useState<TaskStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function load() {
      try {
        setLoading(true)
        setError(null)
        const [runsResult, tasksResult] = await Promise.all([getRunList(30), getTaskList(50)])
        if (!active) return
        setRuns(runsResult.items)
        setTasks(tasksResult.items)
      } catch (loadError) {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : '历史运行加载失败')
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

  const taskMap = useMemo(() => {
    const entries: Array<[string, TaskStatus]> = tasks
      .filter((task): task is TaskStatus & { run_id: string } => Boolean(task.run_id))
      .map((task) => [task.run_id, task])
    return new Map<string, TaskStatus>(entries)
  }, [tasks])

  return (
    <AppShell
      title="历史运行"
      subtitle="在这里回看每一次 run 的时间、样本规模、分池结果，以及它是从哪次任务产出的。"
      actions={
        <>
          <Link
            to="/tasks/latest"
            className="inline-flex rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08]"
          >
            查看任务中心
          </Link>
          <Link
            to="/lab"
            className="inline-flex rounded-full border border-cyan-400/25 bg-cyan-400/10 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:border-cyan-300/40 hover:bg-cyan-300/15"
          >
            发起新运行
          </Link>
        </>
      }
    >
      {loading ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="h-64 animate-pulse rounded-[28px] bg-white/[0.05]" />
          ))}
        </div>
      ) : error ? (
        <Panel eyebrow="运行历史" title="暂时无法读取历史运行">
          <div className="rounded-[22px] border border-rose-400/20 bg-rose-400/10 p-5 text-sm text-rose-100">{error}</div>
        </Panel>
      ) : runs.length === 0 ? (
        <Panel eyebrow="运行历史" title="还没有历史运行">
          <div className="rounded-[22px] border border-dashed border-white/10 bg-white/[0.02] p-6 text-sm leading-7 text-slate-400">
            当前还没有可回看的 run。先去规则实验台发起一次运行，这里会自动沉淀历史记录。
          </div>
        </Panel>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {runs.map((run) => {
            const task = taskMap.get(run.run_id)
            return (
              <Panel key={run.run_id} eyebrow="运行快照" title={run.run_id}>
                <div className="flex flex-wrap gap-2">
                  <StatusPill tone={getRunTone(run.run_status)}>{run.run_status}</StatusPill>
                  <StatusPill tone="slate">规则 {run.rule_version}</StatusPill>
                  <StatusPill tone="cyan">数据 {run.data_version}</StatusPill>
                </div>

                <div className="mt-5 grid gap-3 md:grid-cols-2">
                  <div className="rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-500">运行时间</p>
                    <p className="mt-3 text-lg font-semibold text-white">{formatDateTime(run.finished_at || run.started_at)}</p>
                    <p className="mt-2 text-sm text-slate-400">started_at {formatDateTime(run.started_at)}</p>
                  </div>
                  <div className="rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-500">分池结果</p>
                    <p className="mt-3 text-lg font-semibold text-white">
                      重点池 {run.key_watch_count ?? '--'} · 观察池 {run.watch_count ?? '--'}
                    </p>
                    <p className="mt-2 text-sm text-slate-400">通过硬过滤 {run.passed_filter_count ?? '--'} / 总样本 {run.total_stocks ?? '--'}</p>
                  </div>
                </div>

                <div className="mt-5 rounded-[22px] border border-white/10 bg-white/[0.03] p-4">
                  <p className="text-xs uppercase tracking-[0.22em] text-slate-500">来源任务</p>
                  {task ? (
                    <>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <StatusPill tone={getTaskTone(task.task_status)}>{task.task_status}</StatusPill>
                        <StatusPill tone="cyan">{task.apply_mode}</StatusPill>
                      </div>
                      <p className="mt-3 text-sm font-semibold text-white">{task.task_id}</p>
                      <p className="mt-2 text-sm text-slate-400">{task.latest_message || task.task_status}</p>
                      <p className="mt-2 text-sm text-slate-500">
                        创建于 {formatDateTime(task.created_at)} · 结束于 {formatDateTime(task.finished_at)}
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="mt-3 text-sm font-semibold text-white">暂未找到来源任务</p>
                      <p className="mt-2 text-sm text-slate-400">这通常意味着是较早生成的历史 run，或任务记录已不在最近列表内。</p>
                    </>
                  )}
                </div>

                <div className="mt-5">
                  <RuleSnapshotSummary
                    snapshot={run.rule_snapshot}
                    applyMode={run.apply_mode || task?.apply_mode}
                    emptyText="这次历史运行还没有保留下可展示的规则快照，通常是较早生成的旧 run。"
                  />
                </div>

                <div className="mt-6 flex flex-wrap gap-3">
                  <Link
                    to={`/?run=${run.run_id}`}
                    className="inline-flex rounded-full border border-cyan-400/25 bg-cyan-400/10 px-5 py-3 text-sm font-semibold text-cyan-100 transition hover:border-cyan-300/40 hover:bg-cyan-300/15"
                  >
                    查看首页视图
                  </Link>
                  <Link
                    to={`/run-review?run=${run.run_id}`}
                    className="inline-flex rounded-full border border-cyan-400/25 bg-cyan-400/10 px-5 py-3 text-sm font-semibold text-cyan-100 transition hover:border-cyan-300/40 hover:bg-cyan-300/15"
                  >
                    Run 质量总览
                  </Link>
                  <Link
                    to={`/stocks?run=${run.run_id}`}
                    className="inline-flex rounded-full border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08]"
                  >
                    查看股票列表
                  </Link>
                  <Link
                    to={`/industries?run=${run.run_id}`}
                    className="inline-flex rounded-full border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08]"
                  >
                    查看行业看板
                  </Link>
                  {task ? (
                    <Link
                      to={`/tasks/${task.task_id}`}
                      className="inline-flex rounded-full border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.08]"
                    >
                      查看来源任务
                    </Link>
                  ) : null}
                </div>
              </Panel>
            )
          })}
        </div>
      )}
    </AppShell>
  )
}
