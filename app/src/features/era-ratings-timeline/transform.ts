import type { EraRatingRow } from './queries'
import type { CIPoint } from '../../ui/charts/LineWithCIRibbon'

/** Why a driver does or does not bridge the 2022 regulation boundary. */
export type SpanCohort =
  | 'bridge'        // raced both sides of 2022, anchors the era calibration
  | 'full-span'     // present 2018-2024 but not a calibration anchor
  | 'joined'        // debuted after 2018
  | 'left'          // last season before 2024
  | 'cameo'         // single season

export interface DriverSeries {
  driver_id: string
  /** All driver-season points, sorted by season */
  points: CIPoint[]
  /** True if this driver was used to calibrate the 2022 era offset */
  isBridgeDriver: boolean
  /** Confidence of the most recent season's rating */
  latestConfidence: number
  /** First season the driver appears in the data */
  firstSeason: number
  /** Last season the driver appears in the data */
  lastSeason: number
  /** Distinct seasons the driver is present (sorted) */
  activeSeasons: number[]
  /** Career mean era-adjusted rating (negative = faster) */
  meanRating: number
  /** Career-span classification for the timeline DAG */
  cohort: SpanCohort
}

export interface TransformResult {
  /** One series per driver, sorted by best (most-negative) career mean rating */
  series: DriverSeries[]
  /** All seasons present in the data */
  seasons: number[]
  /** Earliest and latest season across the whole dataset */
  seasonRange: [number, number]
  /** True if the era offset was anchored on fewer than 3 bridge drivers */
  lowAnchorSample: boolean
  /** Number of bridge drivers used for calibration */
  nBridgeDrivers: number
}

const ERA_BOUNDARY = 2022

function classifyCohort(
  isBridge: boolean,
  firstSeason: number,
  lastSeason: number,
  globalFirst: number,
  globalLast: number,
): SpanCohort {
  if (firstSeason === lastSeason) return 'cameo'
  if (isBridge) return 'bridge'
  if (firstSeason === globalFirst && lastSeason === globalLast) return 'full-span'
  if (firstSeason > globalFirst) return 'joined'
  return 'left'
}

export function transform(rows: EraRatingRow[]): TransformResult {
  if (!rows.length) {
    return { series: [], seasons: [], seasonRange: [0, 0], lowAnchorSample: false, nBridgeDrivers: 0 }
  }

  const byDriver = new Map<string, EraRatingRow[]>()
  for (const row of rows) {
    const bucket = byDriver.get(row.driver_id) ?? []
    bucket.push(row)
    byDriver.set(row.driver_id, bucket)
  }

  const allSeasons = [...new Set(rows.map(r => r.season))].sort((a, b) => a - b)
  const globalFirst = allSeasons[0]
  const globalLast = allSeasons[allSeasons.length - 1]
  const lowAnchorSample = rows[0].low_anchor_sample_flag
  const nBridgeDrivers = rows[0].n_bridge_drivers ?? 0

  const series: DriverSeries[] = []
  for (const [driver_id, driverRows] of byDriver) {
    const sorted = [...driverRows].sort((a, b) => a.season - b.season)
    const points: CIPoint[] = sorted.map(r => ({
      x: r.season,
      y: r.era_adjusted_rating,
      lo: r.era_adjusted_rating_ci_low_s,
      hi: r.era_adjusted_rating_ci_high_s,
    }))
    const isBridgeDriver = driverRows.some(r => r.bridge_driver_anchor_flag)
    const latest = sorted[sorted.length - 1]
    const activeSeasons = sorted.map(r => r.season)
    const firstSeason = activeSeasons[0]
    const lastSeason = activeSeasons[activeSeasons.length - 1]
    const meanRating = points.reduce((s, p) => s + p.y, 0) / points.length
    const cohort = classifyCohort(isBridgeDriver, firstSeason, lastSeason, globalFirst, globalLast)
    series.push({
      driver_id,
      points,
      isBridgeDriver,
      latestConfidence: latest.rating_confidence,
      firstSeason,
      lastSeason,
      activeSeasons,
      meanRating,
      cohort,
    })
  }

  // Sort by mean era_adjusted_rating ascending (best/fastest first)
  series.sort((a, b) => a.meanRating - b.meanRating)

  return {
    series,
    seasons: allSeasons,
    seasonRange: [globalFirst, globalLast],
    lowAnchorSample,
    nBridgeDrivers,
  }
}

export { ERA_BOUNDARY }

/**
 * Returns the driver IDs with the highest rating confidence across their careers,
 * capped at `n`. Used as the default selection on first render.
 */
export function topDriversByConfidence(series: DriverSeries[], n: number): string[] {
  return [...series]
    .sort((a, b) => b.latestConfidence - a.latestConfidence)
    .slice(0, n)
    .map(s => s.driver_id)
}

export function toCsvRows(result: TransformResult, selected: string[]): Record<string, unknown>[] {
  const selectedSet = new Set(selected)
  return result.series
    .filter(s => selectedSet.has(s.driver_id))
    .flatMap(s =>
      s.points.map(p => ({
        driver_id: s.driver_id,
        season: p.x,
        era_adjusted_rating_s: (p.y as number).toFixed(4),
        ci_low_s: (p.lo as number).toFixed(4),
        ci_high_s: (p.hi as number).toFixed(4),
        is_bridge_driver: s.isBridgeDriver,
      }))
    )
}
