// Stable per-driver line colour, shared by the rating chart and the career-span
// timeline so a driver keeps the same hue regardless of selection order.

const LINE_PALETTE = [
  '#60a5fa', '#34d399', '#fbbf24', '#f87171', '#a78bfa',
  '#fb923c', '#2dd4bf', '#e879f9', '#a3e635', '#facc15',
  '#38bdf8', '#4ade80', '#fda4af', '#c084fc', '#fcd34d',
]

/**
 * Deterministic colour for a driver among the current selection. Keyed by the
 * driver's index in the (already rating-sorted) selected list so lines stay
 * visually distinct, but each driver's slot is stable for a given selection set.
 */
export function lineColor(index: number): string {
  return LINE_PALETTE[index % LINE_PALETTE.length]
}
