// AX-04 card kind for the pit-strategy Gantt: the modelled optimal pit lap per stint.
// Published HELD (no value) until AX-18 re-measures the realised-call reproduction rate: the
// reason is the PIT_CALL_REPRODUCTION_RATE rule in policy.json (D9/W7; lineage: T [S], HELD).
// compute() runs the page's own queries ('pit-strategy.gantt', 'pit-strategy.race-summary') and
// transform(), so the held cards name exactly the stints the page draws.
import { defineKind } from '../../assistant/cards/kinds'
import policyData from '../../assistant/honesty/policy.json'
import { transform } from './transform'
import type { GanttResult } from './transform'
import type { PitGanttRow, RaceSummaryRow } from './queries'
import './queries'

export interface PitCardParams {
  season: number
  race_id: string
}

const pitRule = (policyData as { rules: { code: string; required_wording: { description: string } }[] }).rules.find(
  (r) => r.code === 'PIT_CALL_REPRODUCTION_RATE',
)
if (!pitRule) throw new Error('policy.json has no PIT_CALL_REPRODUCTION_RATE rule')

export const PIT_HELD_REASON = `PIT_CALL_REPRODUCTION_RATE, held until AX-18: ${pitRule.required_wording.description}`

export const pitOptimalLap = defineKind<PitCardParams, GanttResult>({
  kind: 'pit_strategy.optimal_lap',
  class: 'T',
  metric: 'optimal_pit_lap_in_stint',
  label: 'modelled',
  unit: 'lap',
  intervalKind: 'none',
  intervalLevel: null,
  nUnit: 'stints',
  source: {
    mart: 'int_pit_strategy_value',
    columns: ['optimal_pit_lap_in_stint', 'optimal_pit_lap_confidence'],
    feature: 'pit-strategy',
    query: 'pit-strategy.gantt',
    transform: 'pit-strategy/transform.ts#transform',
  },
  route: '/tyre-strategy/pit-gantt',
  docsSlug: 'pit-strategy',
  held: PIT_HELD_REASON,
  rev: 1,
  async enumerate(index, q) {
    const out: PitCardParams[] = []
    for (const season of index.seasons) {
      const races = await q.run<{ race_id: string }[]>('pit-strategy.race-options', { season })
      for (const r of races) out.push({ season, race_id: r.race_id })
    }
    return out
  },
  async compute({ season, race_id }, q) {
    const [rows, summary] = await Promise.all([
      q.run<PitGanttRow[]>('pit-strategy.gantt', { race_id, season }),
      q.run<RaceSummaryRow[]>('pit-strategy.race-summary', { race_id, season }),
    ])
    return transform(rows, summary[0]?.total_laps ?? 0)
  },
  refusal: (result) => (result.stints.length ? null : 'no stints for this race in int_pit_strategy_value'),
  ids: ({ race_id }) => [`pit_strategy.optimal_lap:${race_id}:*`],
  build({ season, race_id }, result) {
    return result.stints.map((s) => ({
      key: [race_id, s.driverId, s.stintNumber],
      scope: { season, race_id, driver_id: s.driverId, compound: s.compound },
      value: s.optimalPitLapInStint,
      display: s.optimalPitLapInStint === null ? null : `lap ${s.optimalPitLapInStint} of the stint`,
      n: 1,
      interval: null,
      pageParams: { race_id },
    }))
  },
  pageParams: ({ race_id }) => ({ race_id }),
  caveatRules: [{ code: 'PIT_CALL_REPRODUCTION_RATE', when: () => true }],
  onScreen: () => [],
})

/**
 * AX-07 step 3: the pit verdict and the opportunity cost are published HELD, with no value, for the
 * same D9 reason (watch AXW8). Lineage: strategy_verdict is TRAFFIC [A] (the undercut branch reads
 * int_lap_air_state.min_gap_s as a value); opportunity_cost_s is T [S] but modelled from the same
 * cost curve as the optimal lap. One held card per stint the page draws, like the optimal lap.
 */
export const pitVerdict = defineKind<PitCardParams, GanttResult>({
  ...pitOptimalLap,
  kind: 'pit_strategy.verdict',
  class: 'TRAFFIC',
  metric: 'strategy_verdict',
  label: 'modelled',
  unit: null,
  source: { ...pitOptimalLap.source, columns: ['strategy_verdict'] },
  ids: ({ race_id }) => [`pit_strategy.verdict:${race_id}:*`],
})

export const pitOpportunityCost = defineKind<PitCardParams, GanttResult>({
  ...pitOptimalLap,
  kind: 'pit_strategy.opportunity_cost',
  metric: 'opportunity_cost_s',
  unit: 's',
  source: { ...pitOptimalLap.source, columns: ['opportunity_cost_s', 'overrun_laps'] },
  ids: ({ race_id }) => [`pit_strategy.opportunity_cost:${race_id}:*`],
})

export const cardKinds = [pitOptimalLap, pitVerdict, pitOpportunityCost]
