// Pure statistical utilities (mean, median, percentile, z-score) used by chart and table components.
export function mean(values: number[]): number {
  if (!values.length) return 0
  return values.reduce((a, b) => a + b, 0) / values.length
}

export function quantile(sorted: number[], q: number): number {
  const idx = q * (sorted.length - 1)
  const lo = Math.floor(idx)
  const hi = Math.ceil(idx)
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo)
}

export function ci95(values: number[]): [number, number] {
  const m = mean(values)
  const variance = values.reduce((acc, v) => acc + (v - m) ** 2, 0) / (values.length - 1)
  const se = Math.sqrt(variance / values.length)
  return [m - 1.96 * se, m + 1.96 * se]
}
