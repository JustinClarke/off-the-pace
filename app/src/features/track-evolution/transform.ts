import type { TrackEvolutionRow } from './queries'
import type { MaybeCIPoint } from '../../ui/charts'

export interface TransformResult {
  rubberPoints: MaybeCIPoint[]
  ambientPoints: MaybeCIPoint[]
  hasRain: boolean
  /** Largest |rubber component| over measured laps; null when no lap has one. */
  peakRubber: number | null
}

const isNum = (v: number | null | undefined): v is number =>
  typeof v === 'number' && Number.isFinite(v)

/** Fixed-point string for a measured value, empty string for NULL. */
const fmtOrBlank = (v: number | null | undefined, digits = 4): string =>
  isNum(v) ? v.toFixed(digits) : ''

export function transform(rows: TrackEvolutionRow[]): TransformResult {
  if (!rows.length) return { rubberPoints: [], ambientPoints: [], hasRain: false, peakRubber: null }

  const rubberPoints: MaybeCIPoint[] = rows.map(r => ({
    x: r.lap_number,
    y: r.rubber_component_s,
    lo: r.rubber_component_s,
    hi: r.rubber_component_s,
    y2: r.ambient_component_s,
  }))

  const ambientPoints: MaybeCIPoint[] = rows.map(r => ({
    x: r.lap_number,
    y: r.ambient_component_s,
    lo: r.ambient_component_s,
    hi: r.ambient_component_s,
  }))

  // Only a recorded TRUE counts as rain; NULL (no weather reading) is neither rain nor dry.
  const hasRain = rows.some(r => r.rainfall_flag === true)
  const measured = rows.map(r => r.rubber_component_s).filter(isNum)
  const peakRubber = measured.length ? Math.max(...measured.map(Math.abs)) : null

  return { rubberPoints, ambientPoints, hasRain, peakRubber }
}

export function toCsvRows(rows: TrackEvolutionRow[]): Record<string, unknown>[] {
  return rows.map(r => ({
    lap_number: r.lap_number,
    rubber_component_s: fmtOrBlank(r.rubber_component_s),
    ambient_component_s: fmtOrBlank(r.ambient_component_s),
    track_state_index_s: fmtOrBlank(r.track_state_index_s),
    rainfall_flag: r.rainfall_flag === null ? '' : r.rainfall_flag,
  }))
}
