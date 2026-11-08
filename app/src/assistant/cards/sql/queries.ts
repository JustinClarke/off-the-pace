// AX-07 sqlKind queries: SQL over PUBLISHED files for card kinds that have no page (design 2.4).
// Registered in the same useQuery registry as the feature queries, under a 'cards.' prefix, so the
// headless runner and the parity oracle run them through the same seams as every page query.
//
// Every column read here is T or T with the AIR_STATE_FILTER caveat in the AX-07 lineage table
// (_roadmap/_ai-integration/_evidence/ax-07-lineage/lineage.json). No dirty-air column, no
// mean_*_component_s, no residual, no laps_completed (it counts valid timed laps, lineage 3.1).
import { registerQuery, rawQuery } from '../../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../../data/manifest'
import { registerParquet } from '../../../data/duckdb/register'

async function reg(...names: string[]): Promise<void> {
  const manifest = await loadManifest()
  await Promise.all(names.map((n) => registerParquet(n, getTablePath(manifest, n))))
}

/** stg_results: the classified result (Jolpica), one row per driver who started the entry list. */
export interface ResultRow {
  race_id: string
  race_year: number
  driver_id: string
  constructor_id: string | null
  finish_position: number | null
  classified_position: string | null
  grid_position: number | null
  points: number | null
  status: string | null
  is_classified: boolean | null
  is_dnf: boolean | null
  dnf_cause: string | null
}

export const queryRaceResults = registerQuery<{ race_id: string }, ResultRow[]>('cards.race-results', async ({ race_id }) => {
  await reg('stg_results')
  return rawQuery<ResultRow>(
    `SELECT race_id, CAST(race_year AS INTEGER) AS race_year, driver_id, constructor_id,
            CAST(finish_position AS INTEGER) AS finish_position, classified_position,
            CAST(grid_position AS INTEGER) AS grid_position, points, status,
            is_classified, is_dnf, dnf_cause
       FROM stg_results WHERE race_id = ? ORDER BY finish_position NULLS LAST, driver_id`,
    [race_id],
  )
})

/**
 * AX-07 ruling 5: driver x season result counts from stg_results (the same source as race.result).
 * Wins and podiums count classified finishers only (is_classified, finish_position 1 / <= 3), so a
 * disqualified driver never counts. DNFs repeat stg_results' is_dnf rule on status + is_classified (no new
 * lineage column). Not qv_driver_race.actual_finish_position (it undercounts).
 */
export interface SeasonResultsRow {
  driver_id: string
  constructor_ids: string | null
  starts: number
  wins: number
  podiums: number
  classified: number
  dnfs: number
}

export const querySeasonResults = registerQuery<{ season: number }, SeasonResultsRow[]>('cards.season-results', async ({ season }) => {
  await reg('stg_results')
  return rawQuery<SeasonResultsRow>(
    `SELECT driver_id,
            STRING_AGG(DISTINCT constructor_id, ', ') AS constructor_ids,
            CAST(COUNT(*) AS INTEGER) AS starts,
            CAST(COUNT(*) FILTER (WHERE is_classified AND finish_position = 1) AS INTEGER) AS wins,
            CAST(COUNT(*) FILTER (WHERE is_classified AND finish_position <= 3) AS INTEGER) AS podiums,
            CAST(COUNT(*) FILTER (WHERE is_classified) AS INTEGER) AS classified,
            CAST(COUNT(*) FILTER (WHERE NOT is_classified AND status NOT LIKE '%Lap%' AND status <> 'Finished') AS INTEGER) AS dnfs
       FROM stg_results WHERE race_year = ? GROUP BY driver_id ORDER BY driver_id`,
    [season],
  )
})

/**
 * Every (season, race_id) in mart_race_coverage (one row per scheduled race, 173): the enumeration
 * grain of the race kinds. Not fct_lap_residuals: a race with no valid lap (2021_12) still has a
 * result, cautions and a coverage reason.
 */
export const queryCoverageRaces = registerQuery<Record<string, never>, { race_year: number; race_id: string }[]>(
  'cards.coverage-races',
  async () => {
    await reg('mart_race_coverage')
    return rawQuery(
      `SELECT CAST(race_year AS INTEGER) AS race_year, race_id FROM mart_race_coverage
        ORDER BY race_year, CAST(split_part(race_id, '_', 2) AS INTEGER)`,
    )
  },
)

/** TX-01 race-rating columns of mart_race_driver_summary (T + AIR_STATE_FILTER; lineage 3.1). */
export interface RatingRow {
  race_id: string
  driver_id: string
  constructor_id: string | null
  teammate_id: string | null
  teammate_gap_s: number | null
  rating_s: number | null
  ci_low: number | null
  ci_high: number | null
  paired_lap_count: number | null
  rating_trust_label: string | null
  ci_unavailable_reason: string | null
}

export const queryRaceRatings = registerQuery<{ race_id: string }, RatingRow[]>('cards.race-ratings', async ({ race_id }) => {
  await reg('mart_race_driver_summary')
  return rawQuery<RatingRow>(
    `SELECT race_id, driver_id, constructor_id, teammate_id, teammate_gap_s, rating_s, ci_low, ci_high,
            CAST(paired_lap_count AS INTEGER) AS paired_lap_count, rating_trust_label, ci_unavailable_reason
       FROM mart_race_driver_summary WHERE race_id = ? ORDER BY driver_id`,
    [race_id],
  )
})

/** TX-02 mart_race_coverage: one row per race; coverage_reason says why a race is or is not rated. */
export interface CoverageRow {
  race_id: string
  race_year: number
  n_lap_rows: number
  n_rated_drivers: number
  has_rating: boolean
  has_telemetry: boolean
  rain_lap_share: number | null
  tyre_qa_status: string | null
  coverage_reason: string
}

export const queryRaceCoverage = registerQuery<{ race_id: string }, CoverageRow[]>('cards.race-coverage', async ({ race_id }) => {
  await reg('mart_race_coverage')
  return rawQuery<CoverageRow>(
    `SELECT race_id, CAST(race_year AS INTEGER) AS race_year, CAST(n_lap_rows AS INTEGER) AS n_lap_rows,
            CAST(n_rated_drivers AS INTEGER) AS n_rated_drivers, has_rating, has_telemetry, rain_lap_share,
            tyre_qa_status, coverage_reason
       FROM mart_race_coverage WHERE race_id = ?`,
    [race_id],
  )
})

/**
 * Observed pit stops per driver from int_pit_strategy_value (the pit-strategy page's source):
 * actual_pit_lap comes from stg_pits (lineage 1, T). The modelled columns of that table
 * (optimal lap, overrun, opportunity cost, verdict) are NOT read here; those kinds are held.
 */
export interface PitStopRow {
  driver_id: string
  stints: number
  stint_laps: number
  stops: number
  stop_laps: string | null
  compounds: string | null
}

export const queryPitStops = registerQuery<{ race_id: string }, PitStopRow[]>('cards.pit-stops', async ({ race_id }) => {
  await reg('int_pit_strategy_value')
  return rawQuery<PitStopRow>(
    `SELECT driver_id,
            CAST(COUNT(*) AS INTEGER) AS stints,
            CAST(SUM(stint_length_laps) AS INTEGER) AS stint_laps,
            CAST(COUNT(actual_pit_lap) AS INTEGER) AS stops,
            STRING_AGG(CAST(actual_pit_lap AS VARCHAR), ',' ORDER BY end_lap_number) FILTER (WHERE actual_pit_lap IS NOT NULL) AS stop_laps,
            STRING_AGG(compound, ',' ORDER BY end_lap_number) AS compounds
       FROM int_pit_strategy_value WHERE race_id = ?
      GROUP BY driver_id ORDER BY driver_id`,
    [race_id],
  )
})

/**
 * AX-15a scope enumeration for HELD stubs: scope keys only, from stg_results. A stub's builder reads
 * these columns and nothing else, so a held kind can never carry a value column (stub.no-value test).
 */
export interface StubScopeRow {
  race_year: number
  race_id: string | null
  driver_id: string | null
  constructor_id: string | null
  compound?: string | null
}

export type StubGrain = 'race_compound' | 'race' | 'race_driver' | 'season_driver' | 'season_constructor'

export const queryStubScopes = registerQuery<{ grain: StubGrain }, StubScopeRow[]>('cards.stub-scopes', async ({ grain }) => {
  await reg('stg_results', 'mart_race_coverage', 'race_to_track', 'dim_compounds_season')
  const order = `CAST(split_part(race_id, '_', 2) AS INTEGER)`
  switch (grain) {
    case 'race_compound':
      // Scope keys only: the circuit's dry compounds for the race's season (dim_compounds_season is a seed table).
      return rawQuery<StubScopeRow>(
        `SELECT CAST(split_part(r.race_id, '_', 1) AS INTEGER) AS race_year, r.race_id, NULL AS driver_id,
                NULL AS constructor_id, d.compound_code AS compound
           FROM race_to_track r JOIN dim_compounds_season d
             ON d.circuit_key = r.track_id AND d.season = CAST(split_part(r.race_id, '_', 1) AS INTEGER)
          WHERE d.compound_code NOT IN ('INTERMEDIATE', 'WET')
          ORDER BY race_year, CAST(split_part(r.race_id, '_', 2) AS INTEGER), d.compound_code`,
      )
    case 'race':
      return rawQuery<StubScopeRow>(
        `SELECT CAST(race_year AS INTEGER) AS race_year, race_id, NULL AS driver_id, NULL AS constructor_id
           FROM mart_race_coverage ORDER BY race_year, ${order}`,
      )
    case 'race_driver':
      return rawQuery<StubScopeRow>(
        `SELECT CAST(race_year AS INTEGER) AS race_year, race_id, driver_id, constructor_id
           FROM stg_results ORDER BY race_year, ${order}, driver_id`,
      )
    case 'season_driver':
      return rawQuery<StubScopeRow>(
        `SELECT CAST(race_year AS INTEGER) AS race_year, NULL AS race_id, driver_id, NULL AS constructor_id
           FROM stg_results GROUP BY race_year, driver_id ORDER BY race_year, driver_id`,
      )
    case 'season_constructor':
      return rawQuery<StubScopeRow>(
        `SELECT CAST(race_year AS INTEGER) AS race_year, NULL AS race_id, NULL AS driver_id, constructor_id
           FROM stg_results WHERE constructor_id IS NOT NULL GROUP BY race_year, constructor_id ORDER BY race_year, constructor_id`,
      )
  }
})

/** AX-07b: mart_corner_skill_driver for one season, with the *_se_s and cell counts the page does not select. */
export interface CornerSeasonRow {
  driver_id: string
  constructor_id: string | null
  braking_skill_s: number | null
  mid_corner_skill_s: number | null
  exit_skill_s: number | null
  braking_skill_se_s: number | null
  mid_corner_skill_se_s: number | null
  exit_skill_se_s: number | null
  braking_cells_n: number | null
  mid_cells_n: number | null
  exit_cells_n: number | null
}

export const queryCornerSeason = registerQuery<{ season: number }, CornerSeasonRow[]>('cards.corner-skill', async ({ season }) => {
  const manifest = await loadManifest()
  const alias = `cards_corner_skill_${season}`
  await registerParquet(alias, getTablePath(manifest, 'mart_corner_skill_driver', season))
  return rawQuery<CornerSeasonRow>(
    `SELECT driver_id, constructor_id, braking_skill_s, mid_corner_skill_s, exit_skill_s,
            braking_skill_se_s, mid_corner_skill_se_s, exit_skill_se_s,
            CAST(braking_cells_n AS INTEGER) AS braking_cells_n, CAST(mid_cells_n AS INTEGER) AS mid_cells_n,
            CAST(exit_cells_n AS INTEGER) AS exit_cells_n
       FROM ${alias} ORDER BY driver_id`,
  )
})

/** AX-07b: mart_driver_season_summary rating columns (T + AIR_STATE_FILTER) for one season. */
export interface SeasonRatingRow {
  driver_id: string
  teammate_id: string | null
  teammate_gap_s: number | null
  ci_low: number | null
  ci_high: number | null
  n_races: number | null
  rank_separated_from_next: boolean | null
}

export const querySeasonRatings = registerQuery<{ season: number }, SeasonRatingRow[]>('cards.season-ratings', async ({ season }) => {
  await reg('mart_driver_season_summary')
  return rawQuery<SeasonRatingRow>(
    `SELECT driver_id, teammate_id, teammate_gap_s, ci_low, ci_high, CAST(n_races AS INTEGER) AS n_races, rank_separated_from_next
       FROM mart_driver_season_summary WHERE race_year = ? ORDER BY driver_id`,
    [season],
  )
})

/**
 * AX-07c: the weight-penalty calibration flag of the circuit each race ran at (TX-13: dim_circuits.calibration_flag,
 * SKIPPED / INSUFFICIENT_DATA / REVIEW_REQUIRED), joined through race_to_track (race_id -> track_id = circuit_key).
 * Read by the card builder to set policy_fields.calibration_flag on every race-scoped card, so the policy rule
 * CALIBRATION_FLAGGED_CIRCUIT can fire on it.
 */
export interface RaceCircuitFlagRow {
  race_id: string
  circuit_id: string
  calibration_flag: string | null
}

export const queryRaceCircuitFlags = registerQuery<Record<string, never>, RaceCircuitFlagRow[]>('cards.race-circuit-flags', async () => {
  await reg('dim_circuits', 'race_to_track')
  return rawQuery<RaceCircuitFlagRow>(
    `SELECT r.race_id, d.circuit_id, d.calibration_flag
       FROM race_to_track r JOIN dim_circuits d ON d.circuit_key = r.track_id`,
  )
})
