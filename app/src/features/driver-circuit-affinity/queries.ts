import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface CircuitAffinityRow {
  driver_id: string
  circuit_id: string
  circuit_name: string
  /**
   * The affinity the heatmap draws: shrunk circuit gap to the teammate minus the
   * driver's own all-circuit mean gap (int_driver_circuit_affinity, F44).
   * Negative = the driver does better against his teammate here than he does on average.
   */
  affinity_vs_driver_mean_s: number
  /** The driver's mean gap to his teammate over every race (negative = faster). */
  global_driver_mean_s: number
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

    // F44: draw the deviation from the driver's own mean, never the level
    // (shrunk_affinity_s), which is a gap to the teammate and was negative in
    // every cell.
    return rawQuery<CircuitAffinityRow>(`
      SELECT
        a.driver_id,
        a.circuit_id,
        a.circuit_name,
        a.affinity_vs_driver_mean_s,
        a.global_driver_mean_s,
        a.n_obs,
        a.seasons_observed_n,
        a.affinity_confidence
      FROM int_driver_circuit_affinity a
      WHERE a.n_obs >= 2
      ORDER BY a.driver_id, a.circuit_name
    `, [])
  }
)
