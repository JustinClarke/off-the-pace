import type { GhostStandingsRow } from './queries'

export const CONFIDENCE_FLOOR = 0.3

export interface StandingsEntry {
  driverId: string
  hostConstructorId: string
  raceId: string
  predictedPosition: number
  actualPosition: number | null
  /** negative = predicted better than actual; positive = predicted worse */
  delta: number
  confidence: number
  lapsScored: number
  /** true when ego_driver_id === host_constructor_id's car (identity/self scenario) */
  isSelfScenario: boolean
}

export interface RaceScenario {
  raceId: string
  raceYear: number
  hostConstructorId: string
  entries: StandingsEntry[]
  /** min confidence across all entries in this scenario */
  minConfidence: number
}

export interface TransformResult {
  scenarios: RaceScenario[]
  totalRows: number
}

export function transform(rows: GhostStandingsRow[]): TransformResult {
  if (!rows.length) return { scenarios: [], totalRows: 0 }

  // Group by (race_id, host_constructor_id)
  const map = new Map<string, GhostStandingsRow[]>()
  for (const row of rows) {
    const key = `${row.race_id}::${row.host_constructor_id}`
    const bucket = map.get(key) ?? []
    bucket.push(row)
    map.set(key, bucket)
  }

  const scenarios: RaceScenario[] = []
  for (const bucket of map.values()) {
    const first = bucket[0]
    const entries: StandingsEntry[] = bucket.map(r => ({
      driverId: r.ego_driver_id,
      hostConstructorId: r.host_constructor_id,
      raceId: r.race_id,
      predictedPosition: r.predicted_finish_position,
      actualPosition: r.actual_finish_position,
      delta: r.delta_vs_actual_position,
      confidence: r.avg_recombination_confidence,
      lapsScored: r.laps_counted,
      // degenerate identity check: when a driver is in their own constructor's car,
      // predicted == actual (no recombination); surface this so the UI can annotate it.
      isSelfScenario: isSelf(r),
    }))

    entries.sort((a, b) => a.predictedPosition-b.predictedPosition)

    scenarios.push({
      raceId: first.race_id,
      raceYear: first.race_year,
      hostConstructorId: first.host_constructor_id,
      entries,
      minConfidence: Math.min(...entries.map(e => e.confidence)),
    })
  }

  // Sort scenarios: by raceId then constructorId
  scenarios.sort((a, b) =>
    a.raceId < b.raceId ? -1 : a.raceId > b.raceId ? 1 :
    a.hostConstructorId < b.hostConstructorId ? -1 : 1
  )

  return { scenarios, totalRows: rows.length }
}

/** Self-scenario: the ego driver's actual constructor matches the host constructor. */
function isSelf(r: GhostStandingsRow): boolean {
  // The mart doesn't carry the driver's actual constructor, but the identity invariant
  // (predicted == actual in self-scenarios) is enforced in the SQL via RANK() on the same
  // time values. We detect it by checking delta == 0 AND confidence is high (>= 0.9).
  // This is a heuristic; the UI footnote acknowledges it.
  return r.delta_vs_actual_position === 0 && r.avg_recombination_confidence >= 0.9
}

export function toCsvRows(result: TransformResult): Record<string, unknown>[] {
  return result.scenarios.flatMap(s =>
    s.entries.map(e => ({
      race_id: e.raceId,
      host_constructor_id: e.hostConstructorId,
      driver_id: e.driverId,
      predicted_position: e.predictedPosition,
      actual_position: e.actualPosition ?? '',
      delta_positions: e.delta,
      avg_confidence: e.confidence.toFixed(3),
      laps_scored: e.lapsScored,
      is_self_scenario: e.isSelfScenario,
    }))
  )
}
