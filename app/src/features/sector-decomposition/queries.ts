import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getRaceFilePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface SectorRow {
  driver_id: string
  sector: number
  avg_pace_delta_s: number
  avg_skill_residual_s: number
  avg_total_explained_s: number
  avg_consistency_index: number
  lap_count: number
}

interface Params {
  season: number
  raceId: string
}

export const querySectorDecomposition = registerQuery<Params, SectorRow[]>(
  'sector-decomposition.race',
  async ({ season, raceId }) => {
    if (!raceId) return []
    const manifest = await loadManifest()
    const path = getRaceFilePath(manifest, 'int_sector_residual_decomposed', season, raceId)
    const tableAlias = `int_sector_decomposed_${raceId.replace('-', '_')}`
    await registerParquet(tableAlias, path)

    return rawQuery<SectorRow>(`
      SELECT
        driver_id,
        sector,
        ROUND(AVG(sector_pace_delta_s), 4)           AS avg_pace_delta_s,
        ROUND(AVG(sector_driver_skill_residual_s), 4) AS avg_skill_residual_s,
        ROUND(AVG(sector_total_explained_s), 4)       AS avg_total_explained_s,
        ROUND(AVG(sector_consistency_index), 4)       AS avg_consistency_index,
        COUNT(*)                                      AS lap_count
      FROM ${tableAlias}
      WHERE race_year = ?
        AND race_id   = ?
        AND sector_pace_delta_s IS NOT NULL
      GROUP BY driver_id, sector
      HAVING COUNT(*) >= 3
      ORDER BY sector, avg_pace_delta_s ASC
    `, [season, raceId])
  }
)
