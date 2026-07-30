import type { RuleSnapshot } from '@/types/console'

type GroupCounts = {
  hardFilters: number
  topLevelWeights: number
  poolThresholds: number
  scoreDimensions: Record<string, number>
}

export type RuleChangeSummary = {
  totalChanges: number
  changedAreas: string[]
  changedFieldPaths: Set<string>
  groupCounts: GroupCounts
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function cloneRuleSnapshot(snapshot: RuleSnapshot): RuleSnapshot {
  return JSON.parse(JSON.stringify(snapshot)) as RuleSnapshot
}

export function isRuleValueEqual(left: unknown, right: unknown): boolean {
  if (Array.isArray(left) || Array.isArray(right)) {
    return JSON.stringify(left) === JSON.stringify(right)
  }
  if (isPlainObject(left) || isPlainObject(right)) {
    return JSON.stringify(left) === JSON.stringify(right)
  }
  return left === right
}

function compareRecord(
  current: Record<string, unknown>,
  baseline: Record<string, unknown>,
  pathPrefix: string,
) {
  const changedFieldPaths = new Set<string>()

  for (const key of new Set([...Object.keys(current), ...Object.keys(baseline)])) {
    if (!isRuleValueEqual(current[key], baseline[key])) {
      changedFieldPaths.add(`${pathPrefix}.${key}`)
    }
  }

  return changedFieldPaths
}

export function getRuleChangeSummary(defaultRule: RuleSnapshot, currentRule: RuleSnapshot): RuleChangeSummary {
  const changedFieldPaths = new Set<string>()
  const scoreDimensions: Record<string, number> = {}

  let hardFilters = 0
  for (const section of new Set([...Object.keys(currentRule.hard_filters), ...Object.keys(defaultRule.hard_filters)])) {
    const currentSection = currentRule.hard_filters[section] || {}
    const baselineSection = defaultRule.hard_filters[section] || {}
    const changes = compareRecord(currentSection, baselineSection, `hard_filters.${section}`)
    hardFilters += changes.size
    changes.forEach((path) => changedFieldPaths.add(path))
  }

  const topLevelChanges = compareRecord(currentRule.top_level_weights, defaultRule.top_level_weights, 'top_level_weights')
  topLevelChanges.forEach((path) => changedFieldPaths.add(path))

  const scoreDimensionGroups = new Set([
    ...Object.keys(currentRule.score_dimensions),
    ...Object.keys(defaultRule.score_dimensions),
  ])

  for (const group of scoreDimensionGroups) {
    const currentGroup = currentRule.score_dimensions[group] || {}
    const baselineGroup = defaultRule.score_dimensions[group] || {}
    const changes = compareRecord(currentGroup, baselineGroup, `score_dimensions.${group}`)
    scoreDimensions[group] = changes.size
    changes.forEach((path) => changedFieldPaths.add(path))
  }

  let poolThresholds = 0
  if (!isRuleValueEqual(currentRule.pool_thresholds.key_watch_top_n, defaultRule.pool_thresholds.key_watch_top_n)) {
    poolThresholds = 1
    changedFieldPaths.add('pool_thresholds.key_watch_top_n')
  }

  const changedAreas = [
    hardFilters > 0 ? '硬过滤阈值' : null,
    topLevelChanges.size > 0 ? '一级维度权重' : null,
    ...Object.entries(scoreDimensions)
      .filter(([, count]) => count > 0)
      .map(([group]) => group),
    poolThresholds > 0 ? '重点观察池名额' : null,
  ].filter(Boolean) as string[]

  return {
    totalChanges: changedFieldPaths.size,
    changedAreas,
    changedFieldPaths,
    groupCounts: {
      hardFilters,
      topLevelWeights: topLevelChanges.size,
      poolThresholds,
      scoreDimensions,
    },
  }
}
