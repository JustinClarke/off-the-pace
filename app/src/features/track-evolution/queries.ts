import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface TrackEvolutionRow {
  lap_number: number
  rubber_component_s: number
  ambient_component_s: number
  track_state_index_s: number
  rainfall_flag: boolean
}

interface Params {
  season: number
  raceId: string
}

export const queryTrackEvolution = registerQuery<Params, TrackEvolutionRow[]>(
  'track-evolution.race',
  async ({ season, raceId }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'int_track_evolution')
    await registerParquet('int_track_evolution', path)

    return rawQuery<TrackEvolutionRow>(`
      SELECT
        lap_number,
        rubber_component_s,
        ambient_component_s,
        track_state_index_s,
        rainfall_flag
      FROM int_track_evolution
      WHERE race_year = ?
        AND race_id = ?
      ORDER BY lap_number ASC
    `, [season, raceId])
  }
)
