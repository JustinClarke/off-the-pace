import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface CircuitAffinityRow {
  driver_id: string
  circuit_id: string
  circuit_name: string
  shrunk_affinity_s: number
  n_obs: number
  seasons_observed_n: number
  affinity_confidence: number
}

async function registerTables(manifest: Awaited<ReturnType<typeof loadManifest>>) {
  const affinityPath = getTablePath(manifest, 'int_driver_circuit_affinity')
  await registerParquet('int_driver_circuit_affinity', affinityPath)
}

export const queryCircuitAffinity = registerQuery<void, CircuitAffinityRow[]>(
  'driver-circuit-affinity.all',
  async () => {
    const manifest = await loadManifest()
    await registerTables(manifest)

    return rawQuery<CircuitAffinityRow>(`
      SELECT
        a.driver_id,
        a.circuit_id,
        a.circuit_name,
        a.shrunk_affinity_s,
        a.n_obs,
        a.seasons_observed_n,
        a.affinity_confidence
      FROM int_driver_circuit_affinity a
      WHERE a.n_obs >= 2
      ORDER BY a.driver_id, a.circuit_name
    `, [])
  }
)
