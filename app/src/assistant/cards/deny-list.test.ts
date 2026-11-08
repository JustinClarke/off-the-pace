// AX-15a deny-list: no card, of any status, may name dirty_air_tax_s, cumulative_dirty_air_tax_s or a
// *dirty_air* price column in source.columns or interval.source_columns.
// race_lost.component declares dirty_air_tax_s on its SPEC (class DA) but its build() returns [] and its
// refusal always fires, so no card of that kind exists; the test proves that instead of exempting it.
// @vitest-environment node
import { describe, it, expect, vi } from 'vitest'

vi.mock('../../data/manifest', async (orig) => ({
  ...(await orig<typeof import('../../data/manifest')>()),
  loadManifest: async () => ({ version: 'test-version', generatedAt: '', tables: [], stats: { seasons_list: [] } }),
}))

const { registry } = await import('./registry')
const { buildCards } = await import('./build')
const { stubKinds } = await import('./sql/heldStubs')
import type { QueryRunner } from './kinds'

const DENY = /dirty_air_tax_s|cumulative_dirty_air_tax_s|dirty_air/
const q: QueryRunner = { run: async () => [{ race_year: 2024, race_id: '2024_1', driver_id: 'VER', constructor_id: 'Red Bull' }] as never }

describe('AX-15a deny-list', () => {
  it('stub cards name no dirty-air column', async () => {
    const r = await buildCards({ specs: stubKinds, q, index: { dataVersion: 'v', seasons: [], races: [] } })
    expect(r.cards.length).toBeGreaterThanOrEqual(stubKinds.length)
    for (const c of r.cards) {
      for (const col of [...c.source.columns, ...(c.interval?.source_columns ?? [])]) expect(col, c.id).not.toMatch(DENY)
    }
  })

  it('every registered kind that declares a dirty-air column can emit no card', async () => {
    const offenders = registry.filter((s) => s.source.columns.some((c) => DENY.test(c)))
    expect(offenders.map((s) => s.kind)).toEqual(['race_lost.component'])
    for (const s of offenders) {
      expect(s.refusal({}, {}), s.kind).toBeTruthy()
      expect(s.build({}, {}), s.kind).toEqual([])
    }
  })
})
