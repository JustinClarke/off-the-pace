// Lap-time and duration formatters: seconds → M:SS.mmm and delta formatting (±0.000s).
export function formatLapTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = (seconds % 60).toFixed(3).padStart(6, '0')
  return mins > 0 ? `${mins}:${secs}` : secs
}

export function formatDelta(seconds: number): string {
  const sign = seconds >= 0 ? '+' : ''
  return `${sign}${seconds.toFixed(3)}s`
}

export function formatMillis(ms: number): string {
  return formatLapTime(ms / 1000)
}
