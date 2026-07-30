export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return '--'
  }

  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

export function formatScore(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined) {
    return '--'
  }
  return value.toFixed(digits)
}

export function formatPercent(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined) {
    return '--'
  }
  return `${(value * 100).toFixed(digits)}%`
}
