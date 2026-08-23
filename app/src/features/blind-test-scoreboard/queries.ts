import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface ScoreboardRow {
  lap_id: string
  driver_id: string
  circuit_key: string
  race_year: number
  compound: string
  lap_in_stint: number
  // Degradation jump: predicted vs actual
  predicted_degradation_jump_s: number
  predicted_degradation_jump_p10_s: number
  predicted_degradation_jump_p90_s: number
  actual_degradation_jump_s: number | null
  is_in_envelope: boolean
  // Cliff class: predicted vs actual
  predicted_cliff_class: string
  actual_cliff_class: string | null
  // Stint life. The model is an AFT survival fit, so the prediction is a median
  // with a band, and `is_censored_stint` says whether the observed life is a real
  // retirement or only a lower bound (the driver's last stint of the race ended at
  // the flag). Reporting the two together would let the censored tail flatter the
  // fit -- see ml_headroom_ii.md #3.
  predicted_remaining_stint_life_laps: number
  predicted_remaining_stint_life_p10_laps: number
  predicted_remaining_stint_life_p90_laps: number
  actual_remaining_stint_life_laps: number | null
  is_censored_stint: boolean
  // Probabilities for confusion matrix
  prob_0_to_2: number
  prob_3_to_5: number
  prob_6_plus: number
  prob_none_in_stint: number
}

const PREDS_TABLE = 'mart_degradation_predictions'
const FEATURES_TABLE = 'fct_cliff_prediction_features'
// Stint-grain: carries stint_length_laps (for the actual remaining life) and the
// censoring flag. Not season-partitioned, so it registers once.
const STINTS_TABLE = 'fct_stint_features'

async function registerSeason(season: number): Promise<{ predsView: string; featuresView: string }> {
  const manifest = await loadManifest()
  const predsPath = getTablePath(manifest, PREDS_TABLE, season)
  const featuresPath = getTablePath(manifest, FEATURES_TABLE, season)
  const stintsPath = getTablePath(manifest, STINTS_TABLE)
  const predsView = `${PREDS_TABLE}_${season}`
  const featuresView = `${FEATURES_TABLE}_${season}`
  await Promise.all([
    registerParquet(predsView, predsPath),
    registerParquet(featuresView, featuresPath),
    registerParquet(STINTS_TABLE, stintsPath),
  ])
  return { predsView, featuresView }
}

export const queryScoreboardRows = registerQuery<{ season: number }, ScoreboardRow[]>(
  'blind-test-scoreboard.rows',
  async ({ season }) => {
    const { predsView, featuresView } = await registerSeason(season)
    return rawQuery<ScoreboardRow>(`
      SELECT
        p.lap_id,
        f.driver_id,
        p.circuit_key,
        p.race_year,
        f.compound,
        f.lap_in_stint,
        p.predicted_degradation_jump_s,
        p.predicted_degradation_jump_p10_s,
        p.predicted_degradation_jump_p90_s,
        f.next_lap_degradation_jump_s   AS actual_degradation_jump_s,
        p.is_in_envelope,
        p.predicted_cliff_class,
        f.laps_until_cliff_class        AS actual_cliff_class,
        p.predicted_remaining_stint_life_laps,
        p.predicted_remaining_stint_life_p10_laps,
        p.predicted_remaining_stint_life_p90_laps,
        GREATEST(s.stint_length_laps - f.lap_in_stint, 0) AS actual_remaining_stint_life_laps,
        s.is_censored_stint,
        p.prob_0_to_2,
        p.prob_3_to_5,
        p.prob_6_plus,
        p.prob_none_in_stint
      FROM ${predsView} p
      JOIN ${featuresView} f ON p.lap_id = f.lap_id
      JOIN ${STINTS_TABLE} s ON p.stint_id = s.stint_id
      WHERE f.next_lap_degradation_jump_s IS NOT NULL
        AND f.laps_until_cliff_class IS NOT NULL
      ORDER BY p.circuit_key, f.driver_id, f.lap_in_stint
    `, [])
  }
)
