import type { DegradationProfileRow } from './queries'
import type { CIPoint } from '../../ui/charts'

export interface CompoundProfile {
  compound: string
  points: CIPoint[]
  cliffOnset: number | null
}

const COMPOUND_ORDER = ['SOFT', 'MEDIUM', 'HARD']

export function transform(rows: DegradationProfileRow[]): CompoundProfile[] {
  if (!rows.length) return []

  const byCompound = new Map<string, DegradationProfileRow[]>()
  for (const row of rows) {
    const list = byCompound.get(row.compound) ?? []
    list.push(row)
    byCompound.set(row.compound, list)
  }

  const ordered = [...byCompound.keys()].sort((a, b) => {
    const ai = COMPOUND_ORDER.indexOf(a)
    const bi = COMPOUND_ORDER.indexOf(b)
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
  })

  return ordered.map(compound => {
    const laps = byCompound.get(compound)!.sort((a, b) => a.lap_in_stint - b.lap_in_stint)
    const points: CIPoint[] = laps.map(r => ({
      x: r.lap_in_stint,
      y: r.avg_pace_loss_s,
      lo: Math.max(0, r.avg_pace_loss_s - r.std_pace_loss_s),
      hi: r.avg_pace_loss_s + r.std_pace_loss_s,
    }))
    const cliffOnset = (laps[0]?.cliff_onset_laps ?? 0) > 0 ? laps[0].cliff_onset_laps : null
    return { compound, points, cliffOnset }
  })
}

export function toCsvRows(rows: DegradationProfileRow[]): Record<string, unknown>[] {
  return rows.map(r => ({
    compound: r.compound,
    lap_in_stint: r.lap_in_stint,
    avg_pace_loss_s: r.avg_pace_loss_s.toFixed(4),
    std_pace_loss_s: r.std_pace_loss_s.toFixed(4),
    cliff_onset_laps: r.cliff_onset_laps,
    lap_count: r.lap_count,
  }))
}
