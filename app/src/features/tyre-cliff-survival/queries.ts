import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

/** Compound fit profile from dim_compounds_season for a given race x compound */
export interface CompoundProfileRow {
  circuit_key: string
  compound_code: string
  season: number
  compound_cliff_onset_laps: number | null
  compound_cliff_severity: number | null
  compound_wear_gradient: number | null
  compound_grip_peak: number | null
  compound_optimal_temp_low: number | null
  compound_optimal_temp_high: number | null
  fit_date: string | null
  data_window: string | null
  notes: string | null
}

/** Distinct compounds available for a race in the cliff prediction data */
export interface RaceCompoundRow {
  race_id: string
  race_year: number
  compound: string
  stint_count: number
}

/** Per-stint summary for KM + scatter overlay */
export interface StintSummaryRow {
  stint_id: string
  driver_id: string
  stint_length: number
  cliffed: boolean
  degradation_s: number
}

interface SeasonParams {
  season: number
}

interface StintParams {
  race_id: string
  compound: string
  season: number
}

/** Loads compound profiles for a full season (for the race/compound selector UI) */
export const queryCompoundProfiles = registerQuery<SeasonParams, CompoundProfileRow[]>(
  'tyre-cliff-survival.profiles',
  async ({ season }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'dim_compounds_season')
    await registerParquet('dim_compounds_season', path)

    return rawQuery<CompoundProfileRow>(`
      SELECT
        circuit_key,
        compound_code,
        season,
        compound_cliff_onset_laps,
        compound_cliff_severity,
        compound_wear_gradient,
        compound_grip_peak,
        compound_optimal_temp_low,
        compound_optimal_temp_high,
        CAST(fit_date AS VARCHAR) AS fit_date,
        data_window,
        notes
      FROM dim_compounds_season
      WHERE season = ?
        AND compound_code NOT IN ('INTERMEDIATE', 'WET')
      ORDER BY circuit_key, compound_code
    `, [season])
  }
)

/** Loads distinct race x compound combinations available for a season */
export const queryRaceCompounds = registerQuery<SeasonParams, RaceCompoundRow[]>(
  'tyre-cliff-survival.race-compounds',
  async ({ season }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'fct_cliff_prediction_features', season)
    await registerParquet(`fct_cliff_prediction_features_${season}`, path)

    return rawQuery<RaceCompoundRow>(`
      SELECT
        race_id,
        race_year,
        compound,
        COUNT(DISTINCT stint_id) AS stint_count
      FROM fct_cliff_prediction_features_${season}
      WHERE race_year = ?
        AND compound NOT IN ('INTERMEDIATE', 'WET')
        AND anomaly_class IN ('normal', 'clean_cliff')
        AND is_rain_lap = false
      GROUP BY race_id, race_year, compound
      ORDER BY race_id, compound
    `, [season])
  }
)

/**
 * Loads per-stint summary for KM curve construction and the degradation scatter overlay.
 * Each row is one stint: length, whether a cliff was detected, and cumulative degradation at end.
 */
export const queryStintSummaries = registerQuery<StintParams, StintSummaryRow[]>(
  'tyre-cliff-survival.stints',
  async ({ race_id, compound, season }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'fct_cliff_prediction_features', season)
    await registerParquet(`fct_cliff_prediction_features_${season}`, path)

    return rawQuery<StintSummaryRow>(`
      SELECT
        stint_id,
        MAX(driver_id)                              AS driver_id,
        MAX(lap_in_stint)                           AS stint_length,
        BOOL_OR(cliff_onset_passed)                 AS cliffed,
        COALESCE(SUM(expected_degradation_rate_s_per_lap), 0) AS degradation_s
      FROM fct_cliff_prediction_features_${season}
      WHERE race_id = ?
        AND compound = ?
        AND race_year = ?
        AND anomaly_class IN ('normal', 'clean_cliff')
        AND is_rain_lap = false
      GROUP BY stint_id
      ORDER BY stint_id
    `, [race_id, compound, season])
  }
)
