import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'
import { ONSET_IQR_CTE } from '../shared/cliffEstimate'

export interface DegradationProfileRow {
  compound: string
  lap_in_stint: number
  avg_pace_loss_s: number
  std_pace_loss_s: number
  cliff_onset_laps: number
  /** dim_compounds_season.onset_source for this race's circuit; class_default = no data for this track */
  onset_source: string | null
  /** IQR of the compound's measured onsets (laps); null when fewer than 5 measured cells */
  onset_iqr_low: number | null
  onset_iqr_high: number | null
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
    await Promise.all([
      registerParquet(`fct_cliff_prediction_features_${season}`, path),
      registerParquet('dim_compounds_season', getTablePath(manifest, 'dim_compounds_season')),
    ])

    // Same (circuit_key, compound, season) join the fact used to pick up the onset, for its source tag.
    return rawQuery<DegradationProfileRow>(`
      WITH ${ONSET_IQR_CTE}
      SELECT
        f.compound,
        f.lap_in_stint,
        AVG(f.expected_compound_pace_s)               AS avg_pace_loss_s,
        COALESCE(STDDEV(f.expected_compound_pace_s), 0) AS std_pace_loss_s,
        MAX(f.compound_cliff_onset_laps)              AS cliff_onset_laps,
        MAX(cs.onset_source)                          AS onset_source,
        MAX(r.onset_iqr_low)                          AS onset_iqr_low,
        MAX(r.onset_iqr_high)                         AS onset_iqr_high,
        COUNT(*)                                      AS lap_count
      FROM fct_cliff_prediction_features_${season} f
      LEFT JOIN dim_compounds_season cs
        ON cs.circuit_key = f.circuit_key AND cs.compound_code = f.compound AND cs.season = f.race_year
      LEFT JOIN onset_iqr r ON r.compound_code = f.compound
      WHERE f.race_year = ?
        AND f.race_id = ?
        AND f.compound NOT IN ('INTERMEDIATE', 'WET')
        AND f.anomaly_class IN ('normal', 'clean_cliff')
        AND f.is_rain_lap = false
      GROUP BY f.compound, f.lap_in_stint
      ORDER BY f.compound, f.lap_in_stint
    `, [season, raceId])
  }
)
