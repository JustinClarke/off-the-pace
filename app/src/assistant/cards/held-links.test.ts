// AX-15a: every held link resolves. Each stub's page route is a shipped route in the AX-03 table and
// the card's page params only use keys that route reads. AX-21 imports STUB_KINDS for its bundles.
// @vitest-environment node
import { describe, it, expect, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

vi.mock('../../data/manifest', async (orig) => ({
  ...(await orig<typeof import('../../data/manifest')>()),
  loadManifest: async () => ({ version: 'test-version', generatedAt: '', tables: [], stats: { seasons_list: [] } }),
}))

const { stubDefs } = await import('./sql/heldStubs')
const { routeParams } = await import('../../nav/routeParams')
const { routes } = await import('../../nav/routes').then((m) => ({ routes: (m as unknown as { routes?: { path: string; shipped?: boolean }[] }).routes ?? [] }))

describe('AX-15a held links', () => {
  it('every stub route is in routeParams', () => {
    for (const d of stubDefs) expect(routeParams[d.route], d.kind).toBeTruthy()
  })
  it('no stub route is an unshipped page', () => {
    const unshipped = new Set(routes.filter((r) => r.shipped === false).map((r) => r.path))
    for (const d of stubDefs) expect(unshipped.has(d.route), d.route).toBe(false)
  })
  it('classes.md lists every stub kind', () => {
    const md = readFileSync(join(import.meta.dirname, '../../../../_roadmap/_ai-integration/_evidence/ax-15a/classes.md'), 'utf8')
    for (const d of stubDefs) expect(md, d.kind).toContain(d.kind)
  })
})
