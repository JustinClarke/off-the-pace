import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface EraTranslatorRow {
  driver_id: string
  season: number
  era_adjusted_rating: number
  era_adjusted_rating_ci_low_s: number
  era_adjusted_rating_ci_high_s: number
  rating_confidence: number
  n_races: number
  bridge_driver_anchor_flag: boolean
}

interface Params {
  season: number
}

export const queryEraTranslator = registerQuery<Params, EraTranslatorRow[]>(
  'era-translator.season',
  async ({ season }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'int_era_normalized_driver_rating')
    await registerParquet('int_era_normalized_driver_rating', path)

    return rawQuery<EraTranslatorRow>(`
      SELECT
        driver_id,
        season,
        era_adjusted_rating,
        era_adjusted_rating_ci_low_s,
        era_adjusted_rating_ci_high_s,
        rating_confidence,
        n_races,
        bridge_driver_anchor_flag
      FROM int_era_normalized_driver_rating
      WHERE season = ?
        AND era_adjusted_rating IS NOT NULL
        AND n_races >= 5
      ORDER BY era_adjusted_rating ASC
    `, [season])
  }
)
