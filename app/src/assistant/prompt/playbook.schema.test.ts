// AX-21: playbook.json shape. Types are unique, every recipe step names a kind (with an id template)
// or a tool, every held link has a reason, and forbidden_codes are real policy codes.
import { describe, it, expect } from 'vitest'
import { playbook, bundleTypes } from './bundles'
import { policy } from '../honesty/checker'

const TOOLS = ['get_fact_cards', 'query_data', 'list_values', 'compare_lap_times', 'make_chart', 'explain_page', 'navigate']
const TYPES = [
  'teammate_race', 'season_standing', 'why_slow', 'stint_describe', 'safety_car_rate', 'tyre_life',
  'corner_phase', 'observed_count', 'lookup_navigate', 'what_if', 'held_class',
]
const ID_TEMPLATE = /^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*:[^\s]+$/

describe('AX-21 playbook schema', () => {
  it('has a version, classes_live T and the eleven taxonomy types, unique', () => {
    expect(playbook.version).toBeGreaterThanOrEqual(1)
    expect(playbook.classes_live).toEqual(['T'])
    const types = playbook.types.map((t) => t.type)
    expect(new Set(types).size).toBe(types.length)
    expect([...types].sort()).toEqual([...TYPES].sort())
  })

  for (const t of playbook.types) {
    it(`${t.type}: steps, conclusion, held links and codes are well formed`, () => {
      expect(t.examples.length, t.type).toBeGreaterThan(0)
      expect(t.allowed_conclusion.length).toBeGreaterThan(10)
      for (const s of t.recipe) {
        expect(!!s.kind !== !!s.tool, `${t.type}: a step names a kind or a tool, not both`).toBe(true)
        if (s.tool) expect(TOOLS).toContain(s.tool)
        if (s.kind) {
          expect(s.id, `${t.type} ${s.kind}`).toMatch(ID_TEMPLATE)
          expect(s.id!.startsWith(`${s.kind}:`), s.id).toBe(true)
          for (const key of s.id!.match(/\{([a-z_]+)\}/g) ?? []) expect(s.scope_from).toContain(key.slice(1, -1))
        }
        expect(typeof s.required).toBe('boolean')
      }
      for (const h of t.held_links) {
        expect(h.held_reason.trim().length, `${t.type} ${h.kind}`).toBeGreaterThan(0)
        expect(h.id.startsWith(`${h.kind}:`), h.id).toBe(true)
      }
      const codes = new Set(policy.rules.map((r) => r.code))
      for (const c of t.forbidden_codes) expect(codes.has(c), `${t.type}: ${c}`).toBe(true)
      if (t.bundle) expect(t.recipe.some((s) => s.kind) || t.held_links.length > 0, t.type).toBe(true)
      else expect(t.recipe.every((s) => s.tool), `${t.type}: a non-bundle type has tool steps only`).toBe(true)
    })
  }

  it('the bundle enum is the types with a card recipe', () => {
    expect(bundleTypes()).toEqual(['corner_phase', 'safety_car_rate', 'season_standing', 'stint_describe', 'teammate_race', 'tyre_life', 'why_slow'])
  })

  it('the glossary has the six skill measures, each with a model-facing line', () => {
    expect(playbook.glossary.map((g) => g.skill_measure)).toEqual([
      'lap_residual', 'consistency_residual', 'wet_proxy', 'teammate_paired_median', 'era_rating', 'proxy_family',
    ])
    for (const g of playbook.glossary) expect(g.line.length).toBeGreaterThan(5)
  })
})
