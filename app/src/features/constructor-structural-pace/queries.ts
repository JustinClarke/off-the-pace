import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export type PaceMode = 'race' | 'qualifying'

export interface ConstructorPaceRow {
  constructor_id: string
  constructor_structural_pace_s: number
  constructor_structural_pace_se_s: number
  constructor_structural_pace_ci_low_s: number
  constructor_structural_pace_ci_high_s: number
  panel_observations_n: number
  races_n?: number
}

async function registerTables(manifest: Awaited<ReturnType<typeof loadManifest>>) {
  const [racePath, qualiPath] = await Promise.all([
    getTablePath(manifest, 'int_constructor_structural_pace'),
    getTablePath(manifest, 'int_constructor_structural_pace_qualifying'),
  ])
  await Promise.all([
    registerParquet('int_constructor_structural_pace', racePath),
    registerParquet('int_constructor_structural_pace_qualifying', qualiPath),
  ])
}

export const queryConstructorPace = registerQuery<
  { season: number; raceId: string | null; mode: PaceMode },
  ConstructorPaceRow[]
>(
  'constructor-structural-pace.data',
  async ({ season, raceId, mode }) => {
    const manifest = await loadManifest()
    await registerTables(manifest)

    const table = mode === 'qualifying'
      ? 'int_constructor_structural_pace_qualifying'
      : 'int_constructor_structural_pace'

    if (raceId) {
      return rawQuery<ConstructorPaceRow>(`
        SELECT
          constructor_id,
          constructor_structural_pace_s,
          constructor_structural_pace_se_s,
          constructor_structural_pace_ci_low_s,
          constructor_structural_pace_ci_high_s,
          panel_observations_n,
          1 AS races_n
        FROM ${table}
        WHERE race_year = ?
          AND race_id = ?
        ORDER BY constructor_structural_pace_s
      `, [season, raceId])
    }

    // Season aggregate: average pace across all races
    return rawQuery<ConstructorPaceRow>(`
      SELECT
        constructor_id,
        AVG(constructor_structural_pace_s)     AS constructor_structural_pace_s,
        AVG(constructor_structural_pace_se_s)  AS constructor_structural_pace_se_s,
        AVG(constructor_structural_pace_ci_low_s)  AS constructor_structural_pace_ci_low_s,
        AVG(constructor_structural_pace_ci_high_s) AS constructor_structural_pace_ci_high_s,
        SUM(panel_observations_n)              AS panel_observations_n,
        COUNT(*)                               AS races_n
      FROM ${table}
      WHERE race_year = ?
      GROUP BY constructor_id
      ORDER BY AVG(constructor_structural_pace_s)
    `, [season])
  }
)
