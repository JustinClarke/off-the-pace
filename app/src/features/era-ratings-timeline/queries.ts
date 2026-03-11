import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface EraRatingRow {
  driver_id: string
  season: number
  era_adjusted_rating: number
  era_adjusted_rating_ci_low_s: number
  era_adjusted_rating_ci_high_s: number
  rating_confidence: number
  n_races: number
  bridge_driver_anchor_flag: boolean
  low_anchor_sample_flag: boolean
  n_bridge_drivers: number
}

export const queryEraRatings = registerQuery<void, EraRatingRow[]>(
  'era-ratings-timeline.all',
  async () => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'int_era_normalized_driver_rating')
    await registerParquet('int_era_normalized_driver_rating', path)

    return rawQuery<EraRatingRow>(`
      SELECT
        driver_id,
        season,
        era_adjusted_rating,
        era_adjusted_rating_ci_low_s,
        era_adjusted_rating_ci_high_s,
        rating_confidence,
        n_races,
        bridge_driver_anchor_flag,
        low_anchor_sample_flag,
        n_bridge_drivers
      FROM int_era_normalized_driver_rating
      WHERE era_adjusted_rating IS NOT NULL
      ORDER BY driver_id, season ASC
    `, [])
  }
)
