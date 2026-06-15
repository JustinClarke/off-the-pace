import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface DirtyAirCostRow {
  driver_id: string
  total_dirty_air_cost_s: number
  avg_tax_s: number
  taxed_laps: number
  total_laps: number
}

interface Params {
  season: number
  raceId: string
}

export const queryDirtyAirCost = registerQuery<Params, DirtyAirCostRow[]>(
  'dirty-air-cost.race',
  async ({ season, raceId }) => {
    const manifest = await loadManifest()
    const [taxPath, featPath] = await Promise.all([
      getTablePath(manifest, 'int_dirty_air_tax_component', season),
      getTablePath(manifest, 'fct_cliff_prediction_features', season),
    ])
    await Promise.all([
      registerParquet(`int_dirty_air_tax_component_${season}`, taxPath),
      registerParquet(`fct_cliff_prediction_features_${season}`, featPath),
    ])

    return rawQuery<DirtyAirCostRow>(`
      SELECT
        f.driver_id,
        MAX(d.cumulative_dirty_air_tax_race_s)                      AS total_dirty_air_cost_s,
        AVG(d.dirty_air_tax_s)                                      AS avg_tax_s,
        SUM(CASE WHEN d.dirty_air_tax_s > 0 THEN 1 ELSE 0 END)     AS taxed_laps,
        COUNT(*)                                                     AS total_laps
      FROM int_dirty_air_tax_component_${season} d
      JOIN fct_cliff_prediction_features_${season} f USING (lap_id)
      WHERE f.race_year = ?
        AND f.race_id = ?
      GROUP BY f.driver_id
      ORDER BY total_dirty_air_cost_s DESC
    `, [season, raceId])
  }
)
