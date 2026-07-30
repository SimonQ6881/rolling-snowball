import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { getRunSummary, getTask, getTaskList, getTaskLogs } from '@/api/console'
import { AppShell } from '@/components/layout/AppShell'
import { RuleSnapshotSummary } from '@/components/rules/RuleSnapshotSummary'
import { MetricTile } from '@/components/ui/MetricTile'
import { Panel } from '@/components/ui/Panel'
import { StatusPill } from '@/components/ui/StatusPill'
import { formatDateTime } from '@/lib/format'
import type { RunSummary, TaskStatus } from '@/types/console'

const terminalStates = new Set(['success', 'failed'])
const stageLabelMap: Record<string, string> = {
  bootstrap: '初始化环境',
  sync_master: '同步主档',
  evaluate: '执行评分',
  persist: '写入结果',
  finished: '已完成',
  failed: '已失败',
}

function getTaskTone(status: TaskStatus['task_status']) {
  if (status === 'success') return 'emerald'
  if (status === 'failed') return 'rose'
  return 'amber'
}

const primaryLinkClass =
  'inline-flex rounded-full border border-sky-200 bg-sky-50 px-5 py-3 text-sm font-semibold text-sky-700 transition hover:border-sky-300 hover:bg-sky-100'

const secondaryLinkClass =
  'inline-flex rounded-full border border-slate-200 bg-slate-50 px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-white'

const taskListItemBaseClass = 'block rounded-[24px] border px-4 py-4 transition'

export default function TaskPage() {
  const { taskId = 'latest' } = useParams()
  const [tasks, setTasks] = useState<TaskStatus[]>([])
  const [task, setTask] = useState<TaskStatus | null>(null)
  const [runSummary, setRunSummary] = useState<RunSummary | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const activeTaskId = taskId === 'latest' ? task?.task_id || null : taskId

  useEffect(() => {
    let active = true
    let timer: number | undefined

    async function load() {
      try {
        const recentTasksResult = await getTaskList()
        if (!active) return

        setTasks(recentTasksResult.items)

        const resolvedTaskId = taskId === 'latest' ? recentTasksResult.items[0]?.task_id : taskId
        if (!resolvedTaskId) {
          setTask(null)
          setLogs([])
          setError(null)
          return
        }

        const [taskResult, logsResult] = await Promise.all([getTask(resolvedTaskId), getTaskLogs(resolvedTaskId)])
        if (!active) return

        const runSummaryResult = taskResult.run_id ? await getRunSummary(taskResult.run_id).catch(() => null) : null
        if (!active) return

        setTask(taskResult)
        setRunSummary(runSummaryResult)
        setLogs(logsResult.items)
        setError(null)

        if (!terminalStates.has(taskResult.task_status)) {
          timer = window.setTimeout(load, 2000)
        }
      } catch (loadError) {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : '任务状态加载失败')
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    return () => {
      active = false
      if (timer) {
        window.clearTimeout(timer)
      }
    }
  }, [taskId])

  const summaryTitle = useMemo(() => {
    if (!task) return '还没有任务记录'
    return taskId === 'latest' ? `最近任务 · ${task.task_id}` : task.task_id
  }, [task, taskId])

  const ruleSnapshot = runSummary?.rule_snapshot || task?.requested_rule_snapshot || null

  return (
    <AppShell
      title="任务运行"
      subtitle="在这里查看最近任务、运行阶段、日志，以及每次任务最终落下来的 run_id。"
      actions={
        <>
          <Link
            to="/runs"
        className="inline-flex rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
          >
            历史运行
          </Link>
          <Link
            to="/tasks/latest"
        className="inline-flex rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
          >
            最近任务
          </Link>
          <Link
            to="/lab"
        className="inline-flex rounded-full border border-sky-200 bg-sky-50 px-4 py-2 text-sm font-semibold text-sky-700 transition hover:border-sky-300 hover:bg-sky-100"
          >
            发起新运行
          </Link>
        </>
      }
    >
      {loading ? (
        <div className="grid gap-6 xl:grid-cols-[0.7fr_1.3fr]">
          <div className="h-[520px] animate-pulse rounded-[30px] bg-white/70 shadow-[0_16px_36px_rgba(15,23,42,0.05)]" />
          <div className="h-[520px] animate-pulse rounded-[30px] bg-white/70 shadow-[0_16px_36px_rgba(15,23,42,0.05)]" />
        </div>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[0.72fr_1.28fr]">
          <Panel eyebrow="最近任务" title={`最近 ${tasks.length} 条`}>
            {tasks.length > 0 ? (
              <div className="space-y-3">
                {tasks.map((item) => (
                  <Link
                    key={item.task_id}
                    to={`/tasks/${item.task_id}`}
                    className={[
                      taskListItemBaseClass,
                      item.task_id === activeTaskId
                        ? 'border-sky-200 bg-sky-50 shadow-[0_16px_36px_rgba(14,165,233,0.10)]'
                        : 'border-slate-200 bg-slate-50/70 hover:border-slate-300 hover:bg-white',
                    ].join(' ')}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusPill tone={getTaskTone(item.task_status)}>{item.task_status}</StatusPill>
                      <StatusPill tone="slate">{stageLabelMap[item.progress_stage || ''] || item.progress_stage || 'waiting'}</StatusPill>
                    </div>
                    <p className="mt-3 text-sm font-semibold text-slate-950">{item.task_id}</p>
                    <p className="mt-2 text-xs text-slate-500">
                      {formatDateTime(item.created_at)} · {item.apply_mode} · {item.run_id || 'run 待生成'}
                    </p>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{item.latest_message || '等待任务写入最新状态。'}</p>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="rounded-[22px] border border-dashed border-slate-200 bg-slate-50/80 p-6 text-sm leading-7 text-slate-600">
                还没有任务记录。先去规则实验台发起一次运行，这里就会自动沉淀最近任务历史。
              </div>
            )}
          </Panel>

          {error ? (
            <Panel eyebrow="任务加载失败" title="暂时无法读取任务状态">
              <div className="rounded-[22px] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">{error}</div>
            </Panel>
          ) : !task ? (
            <Panel eyebrow="等待任务" title="还没有可查看的任务">
              <p className="text-sm leading-7 text-slate-600">当前没有任务详情可展示。发起一次新运行后，这里会显示进度、日志和结果入口。</p>
            </Panel>
          ) : (
            <div className="space-y-6">
              <Panel eyebrow="Task Summary" title="状态与结果入口">
                <div className="rounded-[24px] border border-slate-200/80 bg-slate-50/90 p-4">
                  <p className="text-xs uppercase tracking-[0.22em] text-slate-500">当前任务</p>
                  <p className="mt-2 text-sm font-semibold text-slate-950">{summaryTitle}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-600">先确认任务状态、阶段与结果入口，再决定是否继续查看 run 摘要或回到实验台。</p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <StatusPill tone={getTaskTone(task.task_status)}>{task.task_status}</StatusPill>
                  <StatusPill tone="slate">{stageLabelMap[task.progress_stage || ''] || task.progress_stage || 'waiting'}</StatusPill>
                  <StatusPill tone="cyan">{task.apply_mode}</StatusPill>
                </div>

                <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <MetricTile label="run_id" value={task.run_id || '--'} hint={task.latest_message || '等待最新进展'} />
                  <MetricTile label="已完成" value={`${task.done_count}/${task.total_count || '--'}`} hint={`失败 ${task.failed_count}`} />
                  <MetricTile label="开始时间" value={formatDateTime(task.started_at)} />
                  <MetricTile label="结束时间" value={formatDateTime(task.finished_at)} />
                </div>

                {task.error_message ? (
                  <div className="mt-5 rounded-[22px] border border-rose-200 bg-rose-50 p-5 text-sm leading-7 text-rose-700">
                    <p className="font-semibold">失败原因</p>
                    <p className="mt-2">{task.error_message}</p>
                  </div>
                ) : null}

                <div className="mt-6 flex flex-wrap gap-3">
                  {task.run_id ? (
                    <>
                      <Link to={`/?run=${task.run_id}`} className={primaryLinkClass}>
                        打开首页摘要
                      </Link>
                      <Link to={`/stocks?run=${task.run_id}`} className={secondaryLinkClass}>
                        打开股票列表
                      </Link>
                      <Link to={`/industries?run=${task.run_id}`} className={secondaryLinkClass}>
                        打开行业看板
                      </Link>
                      <Link to="/runs" className={secondaryLinkClass}>
                        打开历史运行
                      </Link>
                    </>
                  ) : null}
                  <Link to="/lab" className={secondaryLinkClass}>
                    返回规则实验台
                  </Link>
                </div>
              </Panel>

              {task.run_id ? (
                <Panel eyebrow="Run Output" title="本次 run 摘要">
                  {runSummary ? (
                    <>
                      <div className="flex flex-wrap gap-2">
                        <StatusPill tone={runSummary.run_status === 'success' ? 'emerald' : runSummary.run_status === 'failed' ? 'rose' : 'amber'}>
                          {runSummary.run_status}
                        </StatusPill>
                        <StatusPill tone="slate">规则 {runSummary.rule_version}</StatusPill>
                        <StatusPill tone="cyan">数据 {runSummary.data_version}</StatusPill>
                      </div>
                      <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                        <MetricTile label="通过硬过滤" value={String(runSummary.passed_filter_count ?? '--')} />
                        <MetricTile label="重点观察池" value={String(runSummary.key_watch_count ?? '--')} />
                        <MetricTile label="观察池" value={String(runSummary.watch_count ?? '--')} />
                        <MetricTile label="总样本" value={String(runSummary.total_stocks ?? '--')} hint={`完成时间 ${formatDateTime(runSummary.finished_at)}`} />
                      </div>

                      <div className="mt-5">
                        <RuleSnapshotSummary
                          snapshot={ruleSnapshot}
                          applyMode={runSummary.apply_mode || task.apply_mode}
                          variant="full"
                          emptyText="当前 run 已生成，但暂时还没有取到本次任务的规则快照。"
                        />
                      </div>
                    </>
                  ) : (
                    <div className="space-y-4">
                      <div className="rounded-[22px] border border-dashed border-slate-200 bg-slate-50/80 p-5 text-sm leading-7 text-slate-600">
                        当前任务已经拿到了 `run_id`，但暂时没有查到对应的运行摘要。通常说明这是较早的历史记录，或者这次 run 还没有完整摘要可读。
                      </div>
                      <RuleSnapshotSummary
                        snapshot={ruleSnapshot}
                        applyMode={task.apply_mode}
                        variant="full"
                        emptyText="当前任务也没有保留下可展示的规则快照。"
                      />
                    </div>
                  )}
                </Panel>
              ) : null}

              <Panel eyebrow="Logs" title="执行日志">
                <div className="max-h-[560px] overflow-auto rounded-[24px] border border-slate-200 bg-slate-950 p-4 font-mono text-xs leading-6 text-slate-200">
                  {logs.length > 0 ? (
                    logs.map((line) => <div key={line}>{line}</div>)
                  ) : (
                    <p className="text-slate-500">日志还没有写入。</p>
                  )}
                </div>
              </Panel>
            </div>
          )}
        </div>
      )}
    </AppShell>
  )
}
