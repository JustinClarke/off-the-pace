import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface GhostStandingsRow {
  ghost_race_id: string
  race_year: number
  race_id: string
  ego_driver_id: string
  host_constructor_id: string
  predicted_finish_position: number
  actual_finish_position: number | null
  delta_vs_actual_position: number
  predicted_total_race_time_s: number
  actual_total_race_time_s: number | null
  laps_counted: number
  avg_recombination_confidence: number
}

export interface RaceOption {
  race_id: string
  race_year: number
  circuit_name: string
}

export interface ConstructorOption {
  host_constructor_id: string
}

async function registerTables(manifest: Awaited<ReturnType<typeof loadManifest>>) {
  const ghostPath = getTablePath(manifest, 'fct_ghost_race_finish')
  const raceToTrackPath = getTablePath(manifest, 'race_to_track')
  const circuitsPath = getTablePath(manifest, 'dim_circuits')
  await Promise.all([
    registerParquet('fct_ghost_race_finish', ghostPath),
    registerParquet('race_to_track', raceToTrackPath),
    registerParquet('dim_circuits', circuitsPath),
  ])
}

// Options query: races for a given season (with circuit name) + distinct host constructors.
export const queryGhostOptions = registerQuery<
  { season: number },
  { races: RaceOption[]; constructors: ConstructorOption[] }
>(
  'ghost-race-standings.options',
  async ({ season }) => {
    const manifest = await loadManifest()
    await registerTables(manifest)

    const [races, constructors] = await Promise.all([
      rawQuery<RaceOption>(`
        SELECT DISTINCT
          g.race_id,
          g.race_year,
          COALESCE(dc.circuit_name, g.race_id) AS circuit_name
        FROM fct_ghost_race_finish g
        LEFT JOIN race_to_track rt
          ON CAST(REPLACE(g.race_id, '_', '') AS INTEGER) = rt.race_id
        LEFT JOIN dim_circuits dc
          ON rt.track_id = dc.circuit_key
        WHERE g.race_year = ?
        ORDER BY g.race_id
      `, [season]),
      rawQuery<ConstructorOption>(`
        SELECT DISTINCT host_constructor_id
        FROM fct_ghost_race_finish
        WHERE race_year = ?
        ORDER BY host_constructor_id
      `, [season]),
    ])

    return { races, constructors }
  }
)

// Main data query: one (race_id, constructor) scenario race_id already encodes the year
export const queryGhostStandings = registerQuery<
  { raceId: string; hostConstructorId: string },
  GhostStandingsRow[]
>(
  'ghost-race-standings.data',
  async ({ raceId, hostConstructorId }) => {
    const manifest = await loadManifest()
    await registerTables(manifest)

    return rawQuery<GhostStandingsRow>(`
      SELECT
        ghost_race_id,
        race_year,
        race_id,
        ego_driver_id,
        host_constructor_id,
        predicted_finish_position,
        actual_finish_position,
        delta_vs_actual_position,
        predicted_total_race_time_s,
        actual_total_race_time_s,
        laps_counted,
        avg_recombination_confidence
      FROM fct_ghost_race_finish
      WHERE race_id = ?
        AND host_constructor_id = ?
      ORDER BY predicted_finish_position
    `, [raceId, hostConstructorId])
  }
)
