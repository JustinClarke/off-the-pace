import type { TrackEvolutionRow } from './queries'
import type { CIPoint } from '../../ui/charts'

export interface TransformResult {
  rubberPoints: CIPoint[]
  ambientPoints: CIPoint[]
  hasRain: boolean
  peakRubber: number
}

export function transform(rows: TrackEvolutionRow[]): TransformResult {
  if (!rows.length) return { rubberPoints: [], ambientPoints: [], hasRain: false, peakRubber: 0 }

  const rubberPoints: CIPoint[] = rows.map(r => ({
    x: r.lap_number,
    y: r.rubber_component_s,
    lo: r.rubber_component_s,
    hi: r.rubber_component_s,
    y2: r.ambient_component_s,
  }))

  const ambientPoints: CIPoint[] = rows.map(r => ({
    x: r.lap_number,
    y: r.ambient_component_s,
    lo: r.ambient_component_s,
    hi: r.ambient_component_s,
  }))

  const hasRain = rows.some(r => r.rainfall_flag)
  const peakRubber = Math.max(...rows.map(r => Math.abs(r.rubber_component_s)))

  return { rubberPoints, ambientPoints, hasRain, peakRubber }
}

export function toCsvRows(rows: TrackEvolutionRow[]): Record<string, unknown>[] {
  return rows.map(r => ({
    lap_number: r.lap_number,
    rubber_component_s: r.rubber_component_s.toFixed(4),
    ambient_component_s: r.ambient_component_s.toFixed(4),
    track_state_index_s: r.track_state_index_s.toFixed(4),
    rainfall_flag: r.rainfall_flag,
  }))
}
