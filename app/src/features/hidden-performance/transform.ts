import type { HiddenPerformanceRow, SeasonRow } from './queries'

export interface HiddenPerformanceEntry {
  driver: string
  team: string | null
  race: string
  predicted: number
  actual: number
  delta: number
  adjustedDelta: number | null
  adjustedDeltaZ: number | null
  finishPosSe: number
  confidence: number
  laps: number
  affinityS: number | null
  affinityConf: number | null
  driverRating: number | null
}

export interface SeasonEntry {
  driver: string
  team: string | null
  meanRawDelta: number
  meanAdjustedDelta: number
  sdAdjustedDelta: number | null
  nRaces: number
  totalLaps: number
  meanConfidence: number
  driverRating: number | null
}

export function transform(rows: HiddenPerformanceRow[]): HiddenPerformanceEntry[] {
  return rows
    .filter(r => r.delta_vs_actual_position !== null && r.actual_finish_position !== null)
    .map(r => ({
      driver: r.ego_driver_id,
      team: r.ego_constructor_id,
      race: r.circuit_name ?? r.race_id,
      predicted: r.predicted_finish_position,
      actual: r.actual_finish_position!,
      delta: r.delta_vs_actual_position!,
      adjustedDelta: r.adjusted_delta,
      adjustedDeltaZ: r.adjusted_delta_z,
      finishPosSe: r.finish_pos_se,
      confidence: r.avg_recombination_confidence,
      laps: r.laps_counted,
      affinityS: r.affinity_shrunk_s,
      affinityConf: r.affinity_confidence,
      driverRating: r.driver_season_rating,
    }))
}

export function seasonTransform(rows: SeasonRow[]): SeasonEntry[] {
  return rows.map(r => ({
    driver: r.ego_driver_id,
    team: r.ego_constructor_id,
    meanRawDelta: r.mean_raw_delta,
    meanAdjustedDelta: r.mean_adjusted_delta,
    sdAdjustedDelta: r.sd_adjusted_delta,
    nRaces: r.n_races,
    totalLaps: r.total_laps,
    meanConfidence: r.mean_confidence,
    driverRating: r.driver_season_rating,
  }))
}

export function toCsvRows(entries: HiddenPerformanceEntry[]): Record<string, unknown>[] {
  return entries.map(e => ({
    driver: e.driver,
    team: e.team ?? '',
    circuit: e.race,
    predicted_position: e.predicted,
    actual_position: e.actual,
    delta_positions: e.delta,
    adjusted_delta: e.adjustedDelta?.toFixed(2) ?? '',
    adjusted_delta_z: e.adjustedDeltaZ?.toFixed(2) ?? '',
    finish_pos_se: e.finishPosSe.toFixed(2),
    recombination_confidence: e.confidence.toFixed(3),
    laps_counted: e.laps,
    circuit_affinity_s: e.affinityS?.toFixed(3) ?? '',
    driver_season_rating: e.driverRating?.toFixed(3) ?? '',
  }))
}

export function toSeasonCsvRows(entries: SeasonEntry[]): Record<string, unknown>[] {
  return entries.map(e => ({
    driver: e.driver,
    team: e.team ?? '',
    mean_raw_delta: e.meanRawDelta.toFixed(2),
    mean_adjusted_delta: e.meanAdjustedDelta.toFixed(2),
    sd_adjusted_delta: e.sdAdjustedDelta?.toFixed(2) ?? '',
    n_races: e.nRaces,
    total_laps: e.totalLaps,
    mean_confidence: e.meanConfidence.toFixed(3),
    driver_season_rating: e.driverRating?.toFixed(3) ?? '',
  }))
}
