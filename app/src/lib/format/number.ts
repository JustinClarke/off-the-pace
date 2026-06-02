// Number formatters: percentage, fixed-decimal, compact (1.2k), and signed delta (+0.000).
export function formatPct(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`
}

export function formatSigFig(value: number, sig = 3): string {
  return Number(value.toPrecision(sig)).toString()
}

export function formatRounded(value: number, decimals = 2): string {
  return value.toFixed(decimals)
}
