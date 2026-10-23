import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface LapAirStateRow {
  driver_id: string
  lap_number: number
  air_state_dominant: string
  dirty_air_thermal_load_surface: number
  /**
   * Closest gap to the car ahead on this lap, in seconds, by crossing time:
   * the difference between the two cars' session-clock crossings of the same
   * point on track (int_lap_proximity, carried by fct_cliff_prediction_features).
   * This is the method DA-01 validated against the timing feed (DD7: seconds
   * only). It is NOT int_lap_air_state.min_gap_s, which is distance-to-driver-
   * ahead divided by point speed and is biased (-0.13 s at 1-2 s, -1.04 s
   * above 2 s). NULL when the lap is not in fct_cliff_prediction_features or
   * has no car ahead on track.
   */
  gap_ahead_min_s: number | null
}

interface Params {
  season: number
  raceId: string
}

export function buildLapAirStateSql(season: number): string {
  return `
      SELECT
        a.driver_id,
        a.lap_number,
        a.air_state_dominant,
        a.dirty_air_thermal_load_surface,
        f.gap_ahead_min_s
      FROM int_lap_air_state_${season} AS a
      LEFT JOIN fct_cliff_prediction_features_${season} AS f
        ON f.lap_id = a.lap_id
      WHERE a.race_year = ?
        AND CAST(a.race_id AS VARCHAR) = ?
      ORDER BY a.driver_id, a.lap_number
    `
}

export const queryLapAirState = registerQuery<Params, LapAirStateRow[]>(
  'dirty-air-lap-map.race',
  async ({ season, raceId }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'int_lap_air_state', season)
    await registerParquet(`int_lap_air_state_${season}`, path)
    const gapPath = getTablePath(manifest, 'fct_cliff_prediction_features', season)
    await registerParquet(`fct_cliff_prediction_features_${season}`, gapPath)

    return rawQuery<LapAirStateRow>(buildLapAirStateSql(season), [season, raceId])
  }
)
