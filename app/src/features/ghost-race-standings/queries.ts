import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

// Equal-car track record: one row per (driver, circuit, era) from
// int_driver_circuit_era_affinity. shrunk_affinity_s is the car-removed pace at this
// circuit (negative = faster than field), shrunk toward the driver's within-era mean.
export interface EraAffinityRow {
  driver_id: string
  circuit_id: string
  circuit_name: string
  era_key: string
  era_label: string
  n_obs: number
  seasons_observed_n: number
  raw_affinity_s: number
  shrunk_affinity_s: number
  shrunk_affinity_se_s: number
  shrunk_affinity_ci_low_s: number
  shrunk_affinity_ci_high_s: number
  affinity_confidence: number
}

export interface CircuitOption {
  circuit_id: string
  circuit_name: string
}

export interface EraOption {
  era_key: string
  era_label: string
}

async function registerTables(manifest: Awaited<ReturnType<typeof loadManifest>>) {
  const affinityPath = getTablePath(manifest, 'int_driver_circuit_era_affinity')
  await registerParquet('int_driver_circuit_era_affinity', affinityPath)
}

// Options query: every circuit that has affinity data (with display name) + the eras.
// Cross-season by design, so it ignores the global season filter.
export const queryGhostOptions = registerQuery<
  Record<string, never>,
  { circuits: CircuitOption[]; eras: EraOption[] }
>(
  'ghost-race-standings.options',
  async () => {
    const manifest = await loadManifest()
    await registerTables(manifest)

    const [circuits, eras] = await Promise.all([
      rawQuery<CircuitOption>(`
        SELECT DISTINCT circuit_id, circuit_name
        FROM int_driver_circuit_era_affinity
        ORDER BY circuit_name
      `),
      rawQuery<EraOption>(`
        SELECT DISTINCT era_key, era_label
        FROM int_driver_circuit_era_affinity
        -- ASC puts 'post2022' before 'pre2022' so the most recent era leads the dropdown
        ORDER BY era_key ASC
      `),
    ])

    return { circuits, eras }
  }
)

// Main data query: every driver's equal-car record at one (circuit, era), ranked by pace.
export const queryGhostStandings = registerQuery<
  { circuitId: string; eraKey: string },
  EraAffinityRow[]
>(
  'ghost-race-standings.data',
  async ({ circuitId, eraKey }) => {
    const manifest = await loadManifest()
    await registerTables(manifest)

    return rawQuery<EraAffinityRow>(`
      SELECT
        driver_id,
        circuit_id,
        circuit_name,
        era_key,
        era_label,
        n_obs,
        seasons_observed_n,
        raw_affinity_s,
        shrunk_affinity_s,
        shrunk_affinity_se_s,
        shrunk_affinity_ci_low_s,
        shrunk_affinity_ci_high_s,
        affinity_confidence
      FROM int_driver_circuit_era_affinity
      WHERE circuit_id = ?
        AND era_key = ?
      ORDER BY shrunk_affinity_s ASC
    `, [circuitId, eraKey])
  }
)
