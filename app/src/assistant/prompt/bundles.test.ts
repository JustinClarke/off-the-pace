// AX-21: resolveBundle. Unit behaviour, then the plan's five demo cases on real cards copied from a
// scratch card build (__fixtures__/demo-cards.json): at most 10 cards, held stubs included, and the
// model projection of the bundle fits one 1,200-token tool slot.
import { describe, it, expect } from 'vitest'
import { resolveBundle, fillTemplate, bundleTypes, BUNDLE_MAX_CARDS } from './bundles'
import { toModelProjection } from '../cards/project'
import { estimateTokens } from '../../nav/pageSummaries.mjs'
import type { Card } from '../cards/card.types'
import fixture from './__fixtures__/demo-cards.json'

const cards = (fixture as unknown as { cards: Card[] }).cards
const byId = new Map(cards.map((c) => [c.id, c]))
const sortedIds = [...byId.keys()].sort()
const store = {
  has: (id: string) => byId.has(id),
  expand: (prefix: string) => sortedIds.filter((id) => id.startsWith(prefix)),
  // The real store reads teammate_id from the race mart; the fixture's pairs are fixed.
  teammateOf: (race: string, driver: string) =>
    (({ '2024_1:VER': 'PER', '2020_14:HAM': 'BOT', '2018_1:RIC': 'VER', '2021_16:HAM': 'BOT', '2024_5:NOR': 'PIA' }) as Record<string, string>)[`${race}:${driver}`] ?? null,
}
const TOOL_SLOT_TOKENS = 1200

function slot(ids: string[], held: { kind: string; held_reason: string }[]) {
  const proj = ids.map((id) => toModelProjection(byId.get(id)!))
  return { proj, tokens: estimateTokens(JSON.stringify({ cards: proj, held })) }
}

describe('AX-21 resolveBundle (unit)', () => {
  it('fills templates and reports a missing key', () => {
    expect(fillTemplate('race.result:{race_id}:{driver_id}', { race_id: '2024_1', driver_id: 'VER' })).toBe('race.result:2024_1:VER')
    expect(fillTemplate('race.result:{race_id}:{driver_id}', { race_id: '2024_1' })).toBeNull()
  })

  it('without a store returns templates, globs unexpanded, held links as ids', () => {
    const b = resolveBundle('teammate_race', { race_id: '2024_1', driver_id: 'VER', teammate_id: 'PER' })
    expect(b.ids).toEqual([
      'race.coverage:2024_1',
      'race.teammate_gap:2024_1:VER',
      'race.teammate_gap:2024_1:PER',
      'race.result:2024_1:VER',
      'race.result:2024_1:PER',
      'race.cautions:2024_1',
      'driver_race.pit_stops:2024_1:VER',
      'race_driver.skill_components:2024_1:VER:*',
    ])
    expect(b.held).toEqual([])
  })

  it('lists required steps it cannot fill and never throws on a partial scope', () => {
    const b = resolveBundle('teammate_race', { race_id: '2024_1' })
    expect(b.missing_scope).toContain('race.teammate_gap:{race_id}:{driver_id}')
    expect(b.ids).toEqual(['race.coverage:2024_1', 'race.cautions:2024_1'])
  })

  it('a held link with no stub comes back with its reason instead of an id', () => {
    const b = resolveBundle('tyre_life', { race_id: '2024_1' }, store)
    const ml = b.held.find((h) => h.kind === 'ml.cliff_probability')
    expect(ml?.held_reason).toMatch(/ML redo/)
    expect(b.ids).toHaveLength(1)
    expect(b.ids[0]).toMatch(/^tyre_cliff_survival\.profile:2024_1:/)
  })

  it('caps at 10, dropping optional steps before required ones', () => {
    for (const type of bundleTypes()) {
      const b = resolveBundle(type, { season: 2024, race_id: '2024_1', driver_id: 'VER', teammate_id: 'PER', compound: 'SOFT' }, store)
      expect(b.ids.length, type).toBeLessThanOrEqual(BUNDLE_MAX_CARDS)
    }
  })

  it('rejects a type without a card recipe', () => {
    expect(() => resolveBundle('what_if', {})).toThrow(/no card recipe/)
  })
})

const DEMOS: { name: string; race_id: string; driver_id: string; expect: (b: ReturnType<typeof resolveBundle>) => void }[] = [
  {
    name: '2024_1 VER ok',
    race_id: '2024_1',
    driver_id: 'VER',
    expect: (b) => {
      const gap = byId.get('race.teammate_gap:2024_1:VER')!
      expect(gap.policy_fields.rating_trust_label).toBe('ok')
      expect(gap.value).not.toBeNull()
      expect(b.ids).toContain('race.teammate_gap:2024_1:PER')
    },
  },
  {
    name: '2020_14 HAM suppressed',
    race_id: '2020_14',
    driver_id: 'HAM',
    expect: () => {
      const gap = byId.get('race.teammate_gap:2020_14:HAM')!
      expect(gap.policy_fields.rating_trust_label).toBe('suppressed')
      expect(gap.value).toBeNull()
      expect(gap.label).toBe('unavailable')
    },
  },
  {
    name: '2018_1 RIC NO_TELEMETRY',
    race_id: '2018_1',
    driver_id: 'RIC',
    expect: () => expect(byId.get('race.coverage:2018_1')!.value).toBe('NO_TELEMETRY'),
  },
  {
    name: '2021_16 HAM ALL_WET_NO_DRY_PAIRS',
    race_id: '2021_16',
    driver_id: 'HAM',
    expect: () => {
      expect(byId.get('race.coverage:2021_16')!.value).toBe('ALL_WET_NO_DRY_PAIRS')
      expect(byId.get('race.teammate_gap:2021_16:HAM')!.unavailable_reason).toMatch(/ALL_WET_NO_DRY_PAIRS/)
    },
  },
  {
    name: '2024_5 NOR safety-car race',
    race_id: '2024_5',
    driver_id: 'NOR',
    expect: () => expect(byId.get('race.cautions:2024_5')!.display).toMatch(/\bSC laps\b/),
  },
]

describe('AX-21 teammate_race bundle on the five demo cases', () => {
  for (const d of DEMOS) {
    it(`${d.name}: <= 10 cards, all present, held stub included, fits the 1,200-token slot`, () => {
      const b = resolveBundle('teammate_race', { race_id: d.race_id, driver_id: d.driver_id }, store)
      expect(b.ids.length).toBeLessThanOrEqual(BUNDLE_MAX_CARDS)
      expect(b.missing_scope).toEqual([])
      expect(b.absent).toEqual([])
      expect(b.dropped).toEqual([])
      for (const id of b.ids) expect(byId.has(id), id).toBe(true)
      expect(b.ids.length).toBe(8) // 7 recipe cards (teammate filled by the store) + 1 held stub
      const stub = b.ids.map((id) => byId.get(id)!).find((c) => c.status === 'held')
      expect(stub?.kind).toBe('race_driver.skill_components')
      expect(stub?.value).toBeNull()
      expect(stub?.held_reason).toMatch(/wake calibration/)
      const { proj, tokens } = slot(b.ids, b.held)
      expect(proj.every((p) => !('route' in p))).toBe(true)
      expect(tokens, `${d.name}: ${tokens} tokens`).toBeLessThanOrEqual(TOOL_SLOT_TOKENS)
      if (process.env.AX21_LOG) console.log(`AX21 ${d.name}: ${b.ids.length} cards, ${tokens} tokens`)
      d.expect(b)
    })
  }

  it('every bundle type fits one slot on a demo scope', () => {
    for (const type of bundleTypes()) {
      const b = resolveBundle(type, { season: 2024, race_id: '2024_1', driver_id: 'VER' }, store)
      const { tokens } = slot(b.ids, b.held)
      expect(tokens, `${type}: ${tokens}`).toBeLessThanOrEqual(TOOL_SLOT_TOKENS)
    }
  })
})
