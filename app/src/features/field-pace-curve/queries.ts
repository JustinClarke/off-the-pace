import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface FieldPaceRow {
  lap_number: number
  field_pace_smoothed_s: number
  field_pace_trimmed_mean_s: number
  eligible_lap_count: number
  low_sample_flag: boolean
}

interface Params {
  season: number
  raceId: string
}

export const queryFieldPaceCurve = registerQuery<Params, FieldPaceRow[]>(
  'field-pace.race',
  async ({ season, raceId }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'int_field_pace_curve')
    await registerParquet('int_field_pace_curve', path)

    return rawQuery<FieldPaceRow>(`
      SELECT
        lap_number,
        field_pace_smoothed_s,
        field_pace_trimmed_mean_s,
        eligible_lap_count,
        low_sample_flag
      FROM int_field_pace_curve
      WHERE race_year = ?
        AND race_id = ?
      ORDER BY lap_number ASC
    `, [season, raceId])
  }
)
