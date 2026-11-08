// AX-15a: the stub builder reads scope keys only. Even if a scope row carries value-looking columns,
// the card carries none of them; the spec declares no source column.
// @vitest-environment node
import { describe, it, expect, vi } from 'vitest'

vi.mock('../../data/manifest', async (orig) => ({
  ...(await orig<typeof import('../../data/manifest')>()),
  loadManifest: async () => ({ version: 'test-version', generatedAt: '', tables: [], stats: { seasons_list: [] } }),
}))

const { buildCards } = await import('./build')
const { stubKinds } = await import('./sql/heldStubs')
import type { QueryRunner } from './kinds'

const poisoned: QueryRunner = {
  run: async () =>
    [{ race_year: 2024, race_id: '2024_1', driver_id: 'VER', constructor_id: 'Red Bull', dirty_air_tax_s: 7.7712, rating_s: -3.4419, value: 4242 }] as never,
}

describe('AX-15a stub carries no value', () => {
  it.each(stubKinds.map((s) => [s.kind, s] as const))('%s', async (_k, spec) => {
    const r = await buildCards({ specs: [spec], q: poisoned, index: { dataVersion: 'v', seasons: [], races: [] } })
    expect(r.cards.length).toBeGreaterThan(0)
    for (const c of r.cards) {
      const json = JSON.stringify(c)
      expect(c.value).toBeNull()
      expect(c.display).toBeNull()
      expect(c.interval).toBeNull()
      expect(c.n.count).toBe(0)
      expect(json).not.toMatch(/7\.7712|3\.4419|4242/)
      expect(spec.source.columns).toEqual([])
    }
  })
})
