// AX-07 step 3: the pit verdict, the opportunity cost and the optimal lap are always held: no value,
// n 0, a reason naming PIT_CALL_REPRODUCTION_RATE, even with every class live.
// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { assembleCard } from './build'
import { validateCard } from './validate'
import { registry, heldReasonFor } from './registry'

const versions = { data_version: 'v', label_version: 'v16', model_version: null, card_schema: '1' as const, registry: 'r' }
const outcome = { key: ['2024_1', 'VER', 1], scope: { season: 2024, race_id: '2024_1', driver_id: 'VER' }, value: 24, display: 'lap 24', n: 1, interval: null, pageParams: { race_id: '2024_1' } }

describe('AX-07 held pit kinds', () => {
  const pit = registry.filter((s) => s.kind.startsWith('pit_strategy.'))
  it('registers optimal lap, verdict and opportunity cost', () => {
    expect(pit.map((s) => s.kind).sort()).toEqual(['pit_strategy.opportunity_cost', 'pit_strategy.optimal_lap', 'pit_strategy.verdict'])
  })
  it.each(pit.map((s) => [s.kind, s] as const))('%s: held, no value, reason present, valid', (_k, s) => {
    expect(heldReasonFor(s, ['T', 'T-F', 'DA', 'TRAFFIC', 'ML'])).toMatch(/^PIT_CALL_REPRODUCTION_RATE, held until AX-18/)
    const r = assembleCard(s, {}, outcome, versions, ['T', 'T-F', 'DA', 'TRAFFIC', 'ML'])
    expect('card' in r).toBe(true)
    if (!('card' in r)) return
    expect(r.card).toMatchObject({ status: 'held', value: null, display: null, n: { count: 0 }, interval: null })
    expect(r.card.held_reason).toMatch(/PIT_CALL_REPRODUCTION_RATE/)
    expect(r.card.caveats).toContain('PIT_CALL_REPRODUCTION_RATE')
    expect(validateCard(r.card, { expectedIntervalKind: s.intervalKind }).ok).toBe(true)
  })
  it('the verdict kind is class TRAFFIC by lineage (min_gap_s used as a value)', () => {
    expect(registry.find((s) => s.kind === 'pit_strategy.verdict')!.class).toBe('TRAFFIC')
  })
})
