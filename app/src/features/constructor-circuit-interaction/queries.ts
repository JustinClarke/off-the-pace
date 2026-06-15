import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface CircuitInteractionRow {
  constructor_id: string
  circuit_key: string
  circuit_name: string
  avg_interaction_s: number
  n_races: number
}

async function registerTables(manifest: Awaited<ReturnType<typeof loadManifest>>) {
  const interactionPath = getTablePath(manifest, 'int_circuit_x_constructor_interaction')
  const circuitsPath = getTablePath(manifest, 'dim_circuits')
  await Promise.all([
    registerParquet('int_circuit_x_constructor_interaction', interactionPath),
    registerParquet('dim_circuits', circuitsPath),
  ])
}

export const queryCircuitInteraction = registerQuery<void, CircuitInteractionRow[]>(
  'constructor-circuit-interaction.all',
  async () => {
    const manifest = await loadManifest()
    await registerTables(manifest)

    return rawQuery<CircuitInteractionRow>(`
      SELECT
        x.constructor_id,
        x.circuit_key,
        COALESCE(dc.circuit_name, x.circuit_key) AS circuit_name,
        AVG(x.circuit_constructor_interaction_s)  AS avg_interaction_s,
        COUNT(DISTINCT x.race_id)                 AS n_races
      FROM int_circuit_x_constructor_interaction x
      LEFT JOIN dim_circuits dc ON x.circuit_key = dc.circuit_key
      WHERE x.circuit_constructor_interaction_s IS NOT NULL
      GROUP BY x.constructor_id, x.circuit_key, dc.circuit_name
      HAVING COUNT(DISTINCT x.race_id) >= 2
      ORDER BY x.constructor_id, circuit_name
    `, [])
  }
)
