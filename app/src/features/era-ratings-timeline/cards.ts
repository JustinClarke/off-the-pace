// AX-04 card kind for the era ratings timeline: one card per driver-season era-adjusted rating.
// Built from the page's own query ('era-ratings-timeline.all') and transform(), so the card value
// is the chart's point. Interval: era_adjusted_rating_ci_low_s / _high_s, which the warehouse
// computes as rating +/- 1.96 x SE (int_era_normalized_driver_rating.sql:179-181), hence
// ci_normal_95 (AX-04 finding 7), never ci_bayes. Class T with the AIR_STATE_FILTER caveat (AX-07,
// HD13: AX-07a lineage.md section 1, the rating is the paired teammate gap; air state enters only
// via the rain filter, which chooses laps).
import { defineKind } from '../../assistant/cards/kinds'
import { transform } from './transform'
import type { EraRatingRow } from './queries'
import type { CIPoint } from '../../ui/charts/LineWithCIRibbon'
import './queries'

export interface EraCardParams {
  driver_id: string
  season: number
}

export interface EraComputed {
  /** The chart point transform() produced for this driver-season, or null. */
  point: CIPoint | null
  /** The query row the point came from (n_races lives here, not in the transform output). */
  row: EraRatingRow | null
}

const QUERY = 'era-ratings-timeline.all'

/** The page's finest readout: the chart tooltip shows 3 decimals (LineWithCIRibbon.tsx:70). */
export const ERA_DISPLAY_DECIMALS = 3
export const formatEraRating = (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(ERA_DISPLAY_DECIMALS)} s`

export const eraRatingSeason = defineKind<EraCardParams, EraComputed>({
  kind: 'era_rating.season',
  class: 'T',
  metric: 'era_adjusted_rating',
  label: 'modelled',
  unit: 's',
  intervalKind: 'ci_normal_95',
  intervalLevel: 0.95,
  nUnit: 'races',
  source: {
    mart: 'int_era_normalized_driver_rating',
    columns: ['era_adjusted_rating', 'era_adjusted_rating_ci_low_s', 'era_adjusted_rating_ci_high_s', 'n_races'],
    feature: 'era-ratings-timeline',
    query: QUERY,
    transform: 'era-ratings-timeline/transform.ts#transform',
  },
  route: '/drivers/ratings-timeline',
  docsSlug: 'era-ratings-timeline',
  rev: 2,
  async enumerate(_index, q) {
    const rows = await q.run<EraRatingRow[]>(QUERY)
    return rows.map((r) => ({ driver_id: r.driver_id, season: r.season }))
  },
  async compute({ driver_id, season }, q) {
    const rows = await q.run<EraRatingRow[]>(QUERY)
    const series = transform(rows).series.find((s) => s.driver_id === driver_id)
    const point = series?.points.find((p) => p.x === season) ?? null
    const row = rows.find((r) => r.driver_id === driver_id && r.season === season) ?? null
    return { point, row }
  },
  refusal({ point, row }) {
    if (!point || !row) return 'no era rating for this driver-season in the published table'
    if (row.n_races === null || row.n_races === undefined) return 'no n: n_races is null'
    if (point.lo === null || point.lo === undefined || point.hi === null || point.hi === undefined) {
      return 'no interval: era_adjusted_rating_ci_low_s/high_s is null'
    }
    return null
  },
  ids: ({ driver_id, season }) => [`era_rating.season:${season}:${driver_id}`],
  build({ driver_id, season }, { point, row }) {
    if (!point || !row) return []
    return [
      {
        key: [season, driver_id],
        scope: { season, driver_id },
        value: point.y as number,
        display: formatEraRating(point.y as number),
        n: row.n_races,
        interval: {
          low: point.lo as number,
          high: point.hi as number,
          level: 0.95,
          source_columns: ['era_adjusted_rating_ci_low_s', 'era_adjusted_rating_ci_high_s'],
        },
        pageParams: {},
        policy_fields: { skill_measure: 'era_rating', shared_input_group: 'race_rating' },
      },
    ]
  },
  pageParams: () => ({}),
  caveatRules: [{ code: 'AIR_STATE_FILTER', when: () => true }],
  onScreen: ({ driver_id, season }) => [`era_rating.season:${season}:${driver_id}`],
})

export const cardKinds = [eraRatingSeason]
