import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface LapAirStateRow {
  driver_id: string
  lap_number: number
  air_state_dominant: string
  dirty_air_thermal_load_surface: number
  min_gap_s: number | null
}

interface Params {
  season: number
  raceId: string
}

export const queryLapAirState = registerQuery<Params, LapAirStateRow[]>(
  'dirty-air-lap-map.race',
  async ({ season, raceId }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'int_lap_air_state', season)
    await registerParquet(`int_lap_air_state_${season}`, path)

    return rawQuery<LapAirStateRow>(`
      SELECT
        driver_id,
        lap_number,
        air_state_dominant,
        dirty_air_thermal_load_surface,
        min_gap_s
      FROM int_lap_air_state_${season}
      WHERE race_year = ?
        AND CAST(race_id AS VARCHAR) = ?
      ORDER BY driver_id, lap_number
    `, [season, raceId])
  }
)
