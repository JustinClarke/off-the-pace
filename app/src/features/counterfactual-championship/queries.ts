import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface ChampionshipRow {
  ego_driver_id: string
  ghost_points: number
  actual_points: number
  races_counted: number
  avg_confidence: number
}

async function registerTables(manifest: Awaited<ReturnType<typeof loadManifest>>) {
  const path = getTablePath(manifest, 'fct_ghost_race_finish')
  await registerParquet('fct_ghost_race_finish', path)
}

export const queryChampionship = registerQuery<
  { season: number; hostConstructorId: string },
  ChampionshipRow[]
>(
  'counterfactual-championship.data',
  async ({ season, hostConstructorId }) => {
    const manifest = await loadManifest()
    await registerTables(manifest)

    // Counterfactual = transplant ONE driver at a time into the host car and rank
    // them against the REST of the grid in their REAL cars. The host car's pace
    // level no longer cancels (as it does when all drivers share it and are ranked
    // only against each other), so a slow host produces few points and a fast host
    // sweeps the board the reading the feature's hook actually promises.
    return rawQuery<ChampionshipRow>(`
      WITH pts AS (
        SELECT pos, pts FROM (VALUES
          (1, 25), (2, 18), (3, 15), (4, 12), (5, 10),
          (6, 8),  (7, 6),  (8, 4),  (9, 2),  (10, 1)
        ) t(pos, pts)
      ),
      -- Real grid: each driver's actual race pace (host-invariant), one row per
      -- (race, driver). AVG collapses the rare per-host coverage differences.
      field AS (
        SELECT
          race_id,
          ego_driver_id            AS field_driver_id,
          AVG(actual_mean_lap_s)   AS field_pace_s
        FROM fct_ghost_race_finish
        WHERE race_year = ?
          AND is_short_run = FALSE
          AND actual_mean_lap_s IS NOT NULL
        GROUP BY race_id, ego_driver_id
      ),
      -- Each driver recombined into the host car.
      ghost AS (
        SELECT
          race_id,
          ego_driver_id,
          predicted_mean_lap_s,
          actual_finish_position,
          avg_recombination_confidence
        FROM fct_ghost_race_finish
        WHERE race_year = ?
          AND host_constructor_id = ?
          AND is_short_run = FALSE
          AND avg_recombination_confidence >= 0.3
          AND predicted_mean_lap_s IS NOT NULL
      ),
      -- Insert the transplanted driver into the real field: finishing position is
      -- 1 + (real cars whose actual pace beats the ghost's host-car pace).
      ranked AS (
        SELECT
          g.race_id,
          g.ego_driver_id,
          g.actual_finish_position,
          g.avg_recombination_confidence,
          1 + SUM(CASE
                    WHEN f.field_driver_id <> g.ego_driver_id
                     AND f.field_pace_s < g.predicted_mean_lap_s
                    THEN 1 ELSE 0
                  END) AS ghost_position
        FROM ghost g
        JOIN field f USING (race_id)
        GROUP BY g.race_id, g.ego_driver_id, g.actual_finish_position, g.avg_recombination_confidence
      )
      SELECT
        r.ego_driver_id,
        COUNT(*) AS races_counted,
        SUM(COALESCE(gp.pts, 0)) AS ghost_points,
        SUM(COALESCE(ap.pts, 0)) AS actual_points,
        AVG(r.avg_recombination_confidence) AS avg_confidence
      FROM ranked r
      LEFT JOIN pts gp ON r.ghost_position = gp.pos
      LEFT JOIN pts ap ON r.actual_finish_position = ap.pos
      GROUP BY r.ego_driver_id
      ORDER BY ghost_points DESC
    `, [season, season, hostConstructorId])
  }
)

export const queryChampionshipConstructors = registerQuery<
  { season: number },
  { host_constructor_id: string }[]
>(
  'counterfactual-championship.constructors',
  async ({ season }) => {
    const manifest = await loadManifest()
    await registerTables(manifest)

    return rawQuery<{ host_constructor_id: string }>(`
      SELECT DISTINCT host_constructor_id
      FROM fct_ghost_race_finish
      WHERE race_year = ?
      ORDER BY host_constructor_id
    `, [season])
  }
)
