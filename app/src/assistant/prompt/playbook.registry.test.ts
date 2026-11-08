// AX-21: every recipe card exists or is held with a reason. Reads playbook.json against the AX-07
// registry (AX-15a's stubs are registry kinds). Fails on a kind that is neither live, held nor a
// declared pending kind; on a held link that is live in the registry or has no reason the model can
// give; and on a glossary status that disagrees with the registry class.
// @vitest-environment node
import { describe, it, expect, vi } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

vi.mock('../../data/manifest', async (orig) => ({
  ...(await orig<typeof import('../../data/manifest')>()),
  loadManifest: async () => ({ version: 'test-version', generatedAt: '', tables: [], stats: { seasons_list: [] } }),
}))

const { registry, heldReasonFor, classesLive } = await import('../cards/registry')
const { stubDefs } = await import('../cards/sql/heldStubs')
const { playbook } = await import('./bundles')
const { policy } = await import('../honesty/checker')

type Status = 'live' | 'held' | 'missing'
const byKind = new Map(registry.map((s) => [s.kind, s]))

function statusOf(kind: string): Status {
  const spec = byKind.get(kind)
  if (spec) return heldReasonFor(spec) === null ? 'live' : 'held'
  const p = playbook.pending_kinds[kind]
  return p ? p.expected : 'missing'
}

// HELD_CARD_WORDING's second group: what the figure waits on. A held reason the model repeats must
// satisfy it, or the model's own answer would fail the checker.
const waitsOn = policy.rules.find((r) => r.code === 'HELD_CARD_WORDING')!.required_wording.all_of[1].map((p) => new RegExp(p, 'iu'))

describe('AX-21 playbook vs registry', () => {
  it('classes_live matches the registry', () => {
    expect([...classesLive]).toEqual(playbook.classes_live)
  })

  it('the resolver tells live, held and unknown kinds apart (so the checks below can fail)', () => {
    expect(statusOf('race.teammate_gap')).toBe('live')
    expect(statusOf('pit_strategy.verdict')).toBe('held')
    expect(statusOf('race_lost.component')).toBe('held')
    expect(statusOf('no_such.kind')).toBe('missing')
  })

  it('a pending kind is not yet in the registry (once it lands, delete the pending entry)', () => {
    for (const k of Object.keys(playbook.pending_kinds)) expect(byKind.has(k), k).toBe(false)
  })

  for (const t of playbook.types) {
    it(`${t.type}: recipe kinds are live, held links are held with a reason`, () => {
      for (const s of t.recipe.filter((x) => x.kind)) {
        expect(statusOf(s.kind!), `${t.type} recipe ${s.kind} must be a live kind`).toBe('live')
      }
      for (const h of t.held_links) {
        expect(statusOf(h.kind), `${t.type} held link ${h.kind}`).toBe('held')
        expect(h.held_reason.trim(), `${t.type} ${h.kind}`).not.toBe('')
        expect(waitsOn.some((rx) => rx.test(h.held_reason)), `${t.type} ${h.kind}: reason names what it waits on`).toBe(true)
      }
    })
  }

  it('the glossary status equals the registry class of every kind it names', () => {
    for (const g of playbook.glossary) {
      for (const k of g.kinds) expect(statusOf(k), `${g.skill_measure}: ${k}`).toBe(g.status)
    }
  })

  it('every skill_measure a card kind sets is a glossary name', () => {
    const names = new Set(playbook.glossary.map((g) => g.skill_measure))
    for (const d of stubDefs) if (d.skillMeasure) expect(names.has(d.skillMeasure), d.kind).toBe(true)
    // Live kinds set it inside build(); read the literal from the sources.
    const src = join(import.meta.dirname, '..', '..')
    const files: string[] = []
    const walk = (dir: string) => {
      for (const e of readdirSync(dir)) {
        const p = join(dir, e)
        if (statSync(p).isDirectory()) walk(p)
        else if (/(cards|Kinds|Stubs)\.ts$/.test(e) && !e.endsWith('.test.ts')) files.push(p)
      }
    }
    walk(join(src, 'features'))
    walk(join(src, 'assistant', 'cards'))
    const found = new Set<string>()
    for (const f of files) for (const m of readFileSync(f, 'utf8').matchAll(/skill_measure: '([a-z_]+)'/g)) found.add(m[1])
    expect(found.size).toBeGreaterThan(0)
    for (const m of found) expect(names.has(m), m).toBe(true)
  })
})
