// AX-07 lineage, class and caveat guards. Reads the saved lineage table
// (_roadmap/_ai-integration/_evidence/ax-07-lineage/lineage.json) and the live registry:
//   - every column a kind declares has a lineage row for its source table;
//   - a kind that can publish a value (class live, not held) is class T and reads no DA, TRAFFIC or
//     ML column; every AIR_STATE_FILTER kind has a filter-only (T-F) row, and every kind with a
//     T-F row carries AIR_STATE_FILTER;
//   - no kind uses the class 'T-F' (HD13 publishes it as T with the caveat), classesLive is ['T'];
//   - every caveat code a kind can emit is a policy.json rule.
// @vitest-environment node
import { describe, it, expect, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

vi.mock('../../data/manifest', async (orig) => ({
  ...(await orig<typeof import('../../data/manifest')>()),
  loadManifest: async () => ({ version: 'test-version', generatedAt: '', tables: [], stats: { seasons_list: [] } }),
}))

const { registry, classesLive, heldReasonFor } = await import('./registry')
import policy from '../honesty/policy.json'

interface LineageRow {
  source: string
  column: string
  class: 'T' | 'T-F' | 'DA' | 'TRAFFIC' | 'ML'
  rule: string
  evidence: string
  kinds: string[]
}
const LINEAGE = join(import.meta.dirname, '../../../../_roadmap/_ai-integration/_evidence/ax-07-lineage/lineage.json')
const rows: LineageRow[] = JSON.parse(readFileSync(LINEAGE, 'utf8')).rows

const rowsFor = (mart: string | null, cols: string[]) => cols.map((c) => rows.find((r) => r.source === mart && r.column === c))

describe('AX-07 lineage table', () => {
  it('has a row for every column every kind declares, with class, rule and evidence', () => {
    for (const s of registry) {
      for (const [i, r] of rowsFor(s.source.mart, s.source.columns).entries()) {
        expect(r, `${s.kind}: no lineage row for ${s.source.mart}.${s.source.columns[i]}`).toBeTruthy()
        expect(r!.rule.length).toBeGreaterThan(10)
        expect(r!.evidence.length).toBeGreaterThan(5)
      }
    }
  })

  it('a kind that can publish a value is class T and reads no DA, TRAFFIC or ML column', () => {
    const live = registry.filter((s) => heldReasonFor(s) === null)
    expect(live.length).toBeGreaterThan(0)
    for (const s of live) {
      expect(s.class, s.kind).toBe('T')
      for (const r of rowsFor(s.source.mart, s.source.columns)) expect(['T', 'T-F'], `${s.kind} ${r!.column}`).toContain(r!.class)
    }
  })

  it('AIR_STATE_FILTER is carried exactly by the kinds with a filter-only row', () => {
    for (const s of registry.filter((k) => heldReasonFor(k) === null)) {
      const hasTF = rowsFor(s.source.mart, s.source.columns).some((r) => r!.class === 'T-F')
      const caveat = s.caveatRules.some((c) => c.code === 'AIR_STATE_FILTER')
      expect(caveat, s.kind).toBe(hasTF)
    }
  })

  it('held kinds keep a non-T lineage row or an explicit held reason', () => {
    for (const s of registry.filter((k) => heldReasonFor(k) !== null)) {
      const cls = rowsFor(s.source.mart, s.source.columns).map((r) => r!.class)
      expect(Boolean(s.held) || cls.some((c) => c !== 'T' && c !== 'T-F'), s.kind).toBe(true)
    }
  })
})

describe('AX-07 class guard', () => {
  it("classesLive is ['T'] and no kind is registered as T-F", () => {
    expect(classesLive).toEqual(['T'])
    for (const s of registry) expect(s.class, s.kind).not.toBe('T-F')
  })

  it('DA, TRAFFIC and ML kinds only ever publish held', () => {
    for (const s of registry.filter((k) => k.class !== 'T')) expect(heldReasonFor(s), s.kind).toBeTruthy()
  })

  it('every caveat code a kind can emit is a policy.json rule code', () => {
    const codes = new Set((policy as { rules: { code: string }[] }).rules.map((r) => r.code))
    for (const s of registry) for (const c of s.caveatRules) expect(codes.has(c.code), `${s.kind}: ${c.code}`).toBe(true)
  })

  it('no kind reads a dirty-air, residual or component column', () => {
    const bad = /dirty_air|residual|_component_s|total_explained|theta_air|share_lap|gap_ahead/
    for (const s of registry.filter((k) => heldReasonFor(k) === null)) {
      for (const c of s.source.columns) expect(c, s.kind).not.toMatch(bad)
    }
  })
})
