import type { GanttStint, StrategyVerdict } from '../../ui/charts/Gantt'
import type { PitGanttRow } from './queries'

export interface GanttResult {
  stints: GanttStint[]
  totalLaps: number
  /** Stints with a non-zero opportunity cost, sorted descending */
  topCostStints: GanttStint[]
  verdictCounts: Record<string, number>
  totalOpportunityCostS: number
}

function coerceVerdict(v: string | null): StrategyVerdict {
  if (v === 'optimal' || v === 'overran' || v === 'unknown') return v
  return null
}

export function transform(rows: PitGanttRow[], totalLaps: number): GanttResult {
  const stints: GanttStint[] = rows.map(r => ({
    driverId: r.driver_id,
    stintNumber: r.stint_number,
    startLap: r.start_lap,
    endLap: r.end_lap,
    compound: r.compound,
    verdict: coerceVerdict(r.verdict),
    overrunLaps: r.overrun_laps,
    opportunityCostS: r.opportunity_cost_s,
    optimalPitLapInStint: r.optimal_pit_lap_in_stint,
    cliffLapInStint: r.cliff_lap_in_stint,
    pitDurationS: r.pit_lane_loss_s,
    tyreManagementScore: r.tyre_management_score,
  }))

  const verdictCounts: Record<string, number> = { optimal: 0, overran: 0, unknown: 0 }
  let totalOpportunityCostS = 0

  for (const s of stints) {
    const v = s.verdict ?? 'unknown'
    verdictCounts[v] = (verdictCounts[v] ?? 0) + 1
    if (s.opportunityCostS != null && s.opportunityCostS > 0) {
      totalOpportunityCostS += s.opportunityCostS
    }
  }

  const topCostStints = stints
    .filter(s => (s.opportunityCostS ?? 0) > 0.1)
    .sort((a, b) => (b.opportunityCostS ?? 0)-(a.opportunityCostS ?? 0))
    .slice(0, 5)

  return { stints, totalLaps, topCostStints, verdictCounts, totalOpportunityCostS }
}

export function toCsvRows(result: GanttResult): Record<string, string | number | null>[] {
  return result.stints.map(s => ({
    driver_id: s.driverId,
    stint_number: s.stintNumber,
    compound: s.compound,
    start_lap: s.startLap,
    end_lap: s.endLap,
    stint_length_laps: s.endLap-s.startLap + 1,
    cliff_lap_in_stint: s.cliffLapInStint,
    verdict: s.verdict,
    overrun_laps: s.overrunLaps,
    opportunity_cost_s: s.opportunityCostS != null ? +s.opportunityCostS.toFixed(3) : null,
    optimal_pit_lap_in_stint: s.optimalPitLapInStint,
    tyre_management_score: s.tyreManagementScore != null ? +s.tyreManagementScore.toFixed(4) : null,
    pit_lane_loss_s: s.pitDurationS != null ? +s.pitDurationS.toFixed(3) : null,
  }))
}
