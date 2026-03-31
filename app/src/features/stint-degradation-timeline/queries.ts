import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface DegradationProfileRow {
  compound: string
  lap_in_stint: number
  avg_pace_loss_s: number
  std_pace_loss_s: number
  cliff_onset_laps: number
  lap_count: number
}

interface Params {
  season: number
  raceId: string
}

export const queryDegradationTimeline = registerQuery<Params, DegradationProfileRow[]>(
  'degradation-timeline.profile',
  async ({ season, raceId }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'fct_cliff_prediction_features', season)
    await registerParquet(`fct_cliff_prediction_features_${season}`, path)

    return rawQuery<DegradationProfileRow>(`
      SELECT
        compound,
        lap_in_stint,
        AVG(expected_compound_pace_s)               AS avg_pace_loss_s,
        COALESCE(STDDEV(expected_compound_pace_s), 0) AS std_pace_loss_s,
        MAX(compound_cliff_onset_laps)              AS cliff_onset_laps,
        COUNT(*)                                    AS lap_count
      FROM fct_cliff_prediction_features_${season}
      WHERE race_year = ?
        AND race_id = ?
        AND compound NOT IN ('INTERMEDIATE', 'WET')
        AND anomaly_class IN ('normal', 'clean_cliff')
        AND is_rain_lap = false
      GROUP BY compound, lap_in_stint
      ORDER BY compound, lap_in_stint
    `, [season, raceId])
  }
)
