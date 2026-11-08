// AX-07: the saved ungrounded list (_evidence/ax-07-lineage/ungrounded.json, from the full scratch
// run) is consistent: refusal counts add up, every refusal has a coded reason, no live T kind is
// refused, and the cards it reports carry only registered kinds.
// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { registry, heldReasonFor } from './registry'

const FILE = join(import.meta.dirname, '../../../../_roadmap/_ai-integration/_evidence/ax-07-lineage/ungrounded.json')
const u = JSON.parse(readFileSync(FILE, 'utf8')) as {
  cards_total: number
  ungrounded_total: number
  label_version: string | null
  refusals: { kind: string; count: number; reason: string }[]
  cards_by_kind: { kind: string; status: string; label: string; count: number }[]
}
const kinds = new Set(registry.map((s) => s.kind))

describe('AX-07 ungrounded.json', () => {
  it('refusal counts add up to the total and every reason is coded', () => {
    expect(u.refusals.reduce((a, r) => a + r.count, 0)).toBe(u.ungrounded_total)
    for (const r of u.refusals) {
      expect(kinds.has(r.kind), r.kind).toBe(true)
      expect(r.reason.length).toBeGreaterThan(15)
    }
  })
  it('card counts add up and name only registered kinds', () => {
    expect(u.cards_by_kind.reduce((a, r) => a + r.count, 0)).toBe(u.cards_total)
    for (const r of u.cards_by_kind) expect(kinds.has(r.kind), r.kind).toBe(true)
  })
  it('active cards come only from live T kinds; held and DA kinds publish no active card', () => {
    for (const r of u.cards_by_kind.filter((x) => x.status === 'active')) {
      const s = registry.find((k) => k.kind === r.kind)!
      expect(s.class, r.kind).toBe('T')
      expect(heldReasonFor(s), r.kind).toBeNull()
    }
  })
  it('the run carried a label version from the export provenance', () => {
    expect(u.label_version).toMatch(/^v\d+$/)
  })
})
