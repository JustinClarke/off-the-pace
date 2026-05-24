/**
 * Shared hook: returns race options for a season with human-readable circuit names.
 *
 * Joins race_to_track (integer race key -> track_id) with dim_circuits (track_id -> circuit_name).
 * Both are small single-parquet exports loaded once and cached by TanStack Query.
 *
 * Usage:
 *   const { raceOptions, isLoading } = useRaceOptions(season)
 *   // raceOptions: { value: '2024_1', label: 'Bahrain International Circuit' }[]
 */
import { useMemo } from 'react'
import { registerQuery, rawQuery, useQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface RaceOption {
  race_id: string
  circuit_name: string
  round_number: number
}

const queryRaceOptionsBySeason = registerQuery<{ season: number }, RaceOption[]>(
  'shared.race-options',
  async ({ season }) => {
    const manifest = await loadManifest()
    const [rttPath, circPath] = await Promise.all([
      getTablePath(manifest, 'race_to_track'),
      getTablePath(manifest, 'dim_circuits'),
    ])
    await Promise.all([
      registerParquet('race_to_track', rttPath),
      registerParquet('dim_circuits', circPath),
    ])

    return rawQuery<RaceOption>(`
      SELECT
        substr(CAST(rt.race_id AS VARCHAR), 1, 4) || '_' || substr(CAST(rt.race_id AS VARCHAR), 5) AS race_id,
        COALESCE(dc.circuit_name, substr(CAST(rt.race_id AS VARCHAR), 1, 4) || '_' || substr(CAST(rt.race_id AS VARCHAR), 5)) AS circuit_name,
        CAST(substr(CAST(rt.race_id AS VARCHAR), 5) AS INTEGER) AS round_number
      FROM race_to_track rt
      LEFT JOIN dim_circuits dc ON rt.track_id = dc.circuit_key
      WHERE CAST(substr(CAST(rt.race_id AS VARCHAR), 1, 4) AS INTEGER) = ?
      ORDER BY rt.race_id
    `, [season])
  }
)

/** Returns select-ready options for races in a season, labelled by circuit name. */
export function useRaceOptions(season: number) {
  const { data, isLoading } = useQuery<RaceOption[]>(
    'shared.race-options',
    { season }
  )

  const raceOptions = useMemo(
    () => (data ?? []).map(r => ({ value: r.race_id, label: r.circuit_name })),
    [data]
  )

  return { raceOptions, raceData: data ?? [], isLoading }
}

// Needed to register the query when the module is imported
void queryRaceOptionsBySeason
