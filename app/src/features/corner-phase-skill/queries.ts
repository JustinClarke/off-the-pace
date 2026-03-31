import { registerQuery, rawQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'

export interface CornerPhaseRow {
  driver_id: string
  braking_skill_s: number
  mid_corner_skill_s: number
  exit_skill_s: number
  braking_skill_z: number
  mid_corner_skill_z: number
  exit_skill_z: number
  corner_skill_index: number
  mapped_corners: number
}

export const queryCornerPhaseSkill = registerQuery<{ season: number }, CornerPhaseRow[]>(
  'corner-phase-skill.season',
  async ({ season }) => {
    const manifest = await loadManifest()
    const path = getTablePath(manifest, 'mart_corner_skill_driver', season)
    const alias = `mart_corner_skill_driver_${season}`
    await registerParquet(alias, path)

    return rawQuery<CornerPhaseRow>(`
      SELECT
        driver_id,
        braking_skill_s,
        mid_corner_skill_s,
        exit_skill_s,
        braking_skill_z,
        mid_corner_skill_z,
        exit_skill_z,
        corner_skill_index,
        mapped_corners
      FROM ${alias}
      ORDER BY corner_skill_index ASC
    `)
  }
)
