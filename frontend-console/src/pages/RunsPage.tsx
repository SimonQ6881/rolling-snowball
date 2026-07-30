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

const primaryLinkClass =
  'inline-flex rounded-full border border-sky-200 bg-sky-50 px-5 py-3 text-sm font-semibold text-sky-700 transition hover:border-sky-300 hover:bg-sky-100'

const secondaryLinkClass =
  'inline-flex rounded-full border border-slate-200 bg-slate-50 px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-white'

const infoCardClass = 'rounded-[24px] border border-slate-200/80 bg-slate-50/90 p-5 shadow-[0_16px_36px_rgba(15,23,42,0.05)]'

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
        className="inline-flex rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
          >
            查看任务中心
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
        <div className="grid gap-4 xl:grid-cols-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="h-64 animate-pulse rounded-[28px] bg-white/70 shadow-[0_16px_36px_rgba(15,23,42,0.05)]" />
          ))}
        </div>
      ) : error ? (
        <Panel eyebrow="运行历史" title="暂时无法读取历史运行">
          <div className="rounded-[22px] border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">{error}</div>
        </Panel>
      ) : runs.length === 0 ? (
        <Panel eyebrow="运行历史" title="还没有历史运行">
          <div className="rounded-[22px] border border-dashed border-slate-200 bg-slate-50/80 p-6 text-sm leading-7 text-slate-600">
            当前还没有可回看的 run。先去规则实验台发起一次运行，这里会自动沉淀历史记录。
          </div>
        </Panel>
      ) : (
        <div className="space-y-6">
          <Panel eyebrow="Run Navigation" title="先从运行快照进入结果视图">
            <div className="grid gap-4 md:grid-cols-3">
              <div className={infoCardClass}>
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">最近 run</p>
                <p className="mt-3 font-serif text-3xl text-slate-950">{runs.length}</p>
                <p className="mt-2 text-sm leading-6 text-slate-600">这里保留最近 30 次运行，方便快速切回当次首页、列表与复盘视图。</p>
              </div>
              <div className={infoCardClass}>
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">成功完成</p>
                <p className="mt-3 font-serif text-3xl text-slate-950">
                  {runs.filter((run) => run.run_status === 'success').length}
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-600">成功 run 与来源任务状态会并排展示，方便判断是否需要继续追查。</p>
              </div>
              <div className={infoCardClass}>
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">最近任务</p>
                <p className="mt-3 font-serif text-3xl text-slate-950">{tasks.length}</p>
                <p className="mt-2 text-sm leading-6 text-slate-600">每张卡片都保留来源任务与规则快照入口，避免在历史记录中来回跳转。</p>
              </div>
            </div>
          </Panel>

          <div className="grid gap-5 xl:grid-cols-2">
            {runs.map((run) => {
              const task = taskMap.get(run.run_id)
              return (
                <Panel key={run.run_id} eyebrow="运行快照" title={run.run_id}>
                  <div className="flex flex-wrap gap-2">
                    <StatusPill tone={getRunTone(run.run_status)}>{run.run_status}</StatusPill>
                    <StatusPill tone="slate">规则 {run.rule_version}</StatusPill>
                    <StatusPill tone="cyan">数据 {run.data_version}</StatusPill>
                  </div>

                  <div className="mt-5 grid gap-4 md:grid-cols-2">
                    <div className={infoCardClass}>
                      <p className="text-xs uppercase tracking-[0.22em] text-slate-500">运行时间</p>
                      <p className="mt-3 text-lg font-semibold text-slate-950">{formatDateTime(run.finished_at || run.started_at)}</p>
                      <p className="mt-2 text-sm text-slate-600">started_at {formatDateTime(run.started_at)}</p>
                    </div>
                    <div className={infoCardClass}>
                      <p className="text-xs uppercase tracking-[0.22em] text-slate-500">分池结果</p>
                      <p className="mt-3 text-lg font-semibold text-slate-950">
                        重点池 {run.key_watch_count ?? '--'} · 观察池 {run.watch_count ?? '--'}
                      </p>
                      <p className="mt-2 text-sm text-slate-600">通过硬过滤 {run.passed_filter_count ?? '--'} / 总样本 {run.total_stocks ?? '--'}</p>
                    </div>
                  </div>

                  <div className="mt-5 rounded-[24px] border border-slate-200/80 bg-white/70 p-5 shadow-[0_16px_36px_rgba(15,23,42,0.05)]">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-500">来源任务</p>
                    {task ? (
                      <>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <StatusPill tone={getTaskTone(task.task_status)}>{task.task_status}</StatusPill>
                          <StatusPill tone="cyan">{task.apply_mode}</StatusPill>
                        </div>
                        <p className="mt-3 text-sm font-semibold text-slate-950">{task.task_id}</p>
                        <p className="mt-2 text-sm text-slate-600">{task.latest_message || task.task_status}</p>
                        <p className="mt-2 text-sm text-slate-500">
                          创建于 {formatDateTime(task.created_at)} · 结束于 {formatDateTime(task.finished_at)}
                        </p>
                      </>
                    ) : (
                      <>
                        <p className="mt-3 text-sm font-semibold text-slate-950">暂未找到来源任务</p>
                        <p className="mt-2 text-sm text-slate-600">这通常意味着是较早生成的历史 run，或任务记录已不在最近列表内。</p>
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

                  <div className="mt-6 rounded-[24px] border border-slate-200/80 bg-slate-50/85 p-5">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-500">结果入口</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">从这里直接回到该次运行对应的首页摘要、质量复盘、股票列表和行业看板。</p>
                    <div className="mt-4 flex flex-wrap gap-3">
                      <Link to={`/?run=${run.run_id}`} className={primaryLinkClass}>
                        打开首页摘要
                      </Link>
                      <Link to={`/run-review?run=${run.run_id}`} className={primaryLinkClass}>
                        Run 质量总览
                      </Link>
                      <Link to={`/stocks?run=${run.run_id}`} className={secondaryLinkClass}>
                        打开股票列表
                      </Link>
                      <Link to={`/industries?run=${run.run_id}`} className={secondaryLinkClass}>
                        打开行业看板
                      </Link>
                      {task ? (
                        <Link to={`/tasks/${task.task_id}`} className={secondaryLinkClass}>
                          打开来源任务
                        </Link>
                      ) : null}
                    </div>
                  </div>
                </Panel>
              )
            })}
          </div>
        </div>
      )}
    </AppShell>
  )
}
