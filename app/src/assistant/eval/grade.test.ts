// AX-13 grader self-test: for EVERY playbook question type, a correct answer passes and a planted wrong answer
// FAILS on the check it plants. The eight wrong-answer kinds of the AX-13 acceptance each appear at least once:
// wrong card number, number with no source, missing required wording, a number given for a held class, answered
// when it should refuse, wrong reason given, wrong tool, over-budget run. Expected values are read from the
// fixture card table (prompt/__fixtures__/demo-cards.json, real cards), never typed here.
import { describe, it, expect } from 'vitest'
import { demoCards } from '../core/testKit'
import { createCardTable, grade, type CheckName, type RunObservation } from './grade'
import { QUESTIONS, type Question } from './questions'
import { systemSentences } from './stubModel'
import type { QueryResultLike } from '../honesty/queryCard'

const table = createCardTable(demoCards)
const S = systemSentences()
const card = (id: string) => {
  const c = table.byId(id)
  if (!c) throw new Error(`fixture has no ${id}`)
  return c
}
const v = (id: string) => card(id).value as number
const a3 = (x: number) => Math.abs(x).toFixed(3)
const s3 = (x: number) => `${x < 0 ? '-' : ''}${Math.abs(x).toFixed(3)}`
const Q = (id: string, over: Partial<Question> = {}): Question => ({ ...QUESTIONS.find((q) => q.id === id)!, ...over })
const prefixed = (p: string) => demoCards.filter((c) => c.id.startsWith(p)).map((c) => c.id)

function obs(q: Question, answer: string, o: Partial<RunObservation> = {}): RunObservation {
  return {
    question_id: q.id,
    repeat: 1,
    mode: 'test',
    status: 'answered',
    answer,
    tools: q.expected_tools.map((name) => ({ name, arguments: q.expected_bundle && name === 'get_fact_cards' ? { bundle: q.expected_bundle } : {}, status: 'ok' })),
    cards_received: [],
    results: [],
    query_results: [],
    budget: { total: 4800, peak_context: 2600, rounds: 2, neurons: 90, estimated: true },
    rounds: 2,
    repaired: false,
    repair_skipped: false,
    first_draft_failed: [],
    loop_notes: [],
    usage_rounds: [],
    ...o,
  }
}

function expectPass(q: Question, o: RunObservation) {
  const g = grade(q, o, table)
  expect(g.failures, `${q.id} correct answer should pass`).toEqual([])
  return g
}
function expectFail(q: Question, o: RunObservation, checks: CheckName[]) {
  const g = grade(q, o, table)
  for (const c of checks) expect(g.checks[c].pass, `${q.id} planted answer should fail ${c}: ${JSON.stringify(g.checks[c])}`).toBe(false)
  expect(g.all_pass).toBe(false)
  return g
}

// --- teammate_race ------------------------------------------------------------------------------------------
const trQ = Q('tr-2024_1-VER')
const trCards = ['race.coverage:2024_1', 'race.teammate_gap:2024_1:VER', 'race.teammate_gap:2024_1:PER', 'race.result:2024_1:VER', 'race.result:2024_1:PER', 'race.cautions:2024_1', 'driver_race.pit_stops:2024_1:VER', ...prefixed('race_driver.skill_components:2024_1:VER')]
const gap = card('race.teammate_gap:2024_1:VER')
const trAnswer = (x: number) =>
  `Verstappen was ${a3(x)} s per lap faster than Perez: the teammate-paired median gap over ${gap.n.count} paired laps, 95% CI ${s3(gap.interval!.low!)} to ${s3(gap.interval!.high!)} s [card ${gap.id}]. ` +
  `The laps were chosen with the air-state filter; it is not a dirty-air estimate. For context, ${v('race.cautions:2024_1')} laps were under caution [card race.cautions:2024_1]. ${S.pit} ${S.heldMeasures}`

describe('AX-13 grader: teammate_race', () => {
  it('passes the compliant answer (the two system.md sentences beside the gap)', () => {
    expectPass(trQ, obs(trQ, trAnswer(gap.value as number), { cards_received: trCards }))
  })
  it('FAILS a wrong card number (grounded and expected_value)', () => {
    expectFail(trQ, obs(trQ, trAnswer((gap.value as number) - 0.09), { cards_received: trCards }), ['grounded', 'expected_value'])
  })
  it('FAILS when the "different measures" idea is left out (AX-10 finding 7: ONE_SKILL_MEASURE)', () => {
    const a = trAnswer(gap.value as number).replace(S.heldMeasures, 'The time-loss breakdown is held until wake calibration reports.')
    const g = expectFail(trQ, obs(trQ, a, { cards_received: trCards }), ['honesty'])
    expect(g.checker.failed).toContain('ONE_SKILL_MEASURE')
  })
  it('FAILS when the pit sentence is left out (PIT_CALL_REPRODUCTION_RATE)', () => {
    const g = expectFail(trQ, obs(trQ, trAnswer(gap.value as number).replace(S.pit, ''), { cards_received: trCards }), ['honesty'])
    expect(g.checker.failed).toContain('PIT_CALL_REPRODUCTION_RATE')
  })
})

// --- season_standing ----------------------------------------------------------------------------------------
const ssQ = Q('ss-2024-NOR')
const ss = card('season.teammate_gap:2024:NOR')
const ssAnswer = (rankWording: string) =>
  `Norris's 2024 era rating, the season gap to his teammate, was ${a3(ss.value as number)} s per lap faster [card ${ss.id}]; ${rankWording} The laps were chosen with the air-state filter; it is not a dirty-air estimate.`
describe('AX-13 grader: season_standing', () => {
  it('passes with the overlap wording', () => {
    expectPass(ssQ, obs(ssQ, ssAnswer('he is in a group whose intervals overlap.'), { cards_received: [ss.id] }))
  })
  it('FAILS a missing required wording (RANK_WITHIN_CI) and a claimed rank', () => {
    const g = expectFail(ssQ, obs(ssQ, ssAnswer('he ranks first among teammates.'), { cards_received: [ss.id] }), ['honesty'])
    expect(g.checker.failed).toContain('RANK_WITHIN_CI')
  })
})

// --- why_slow (2024_1 variant: the fixture's race) -----------------------------------------------------------
const wsQ = Q('ws-2024_8-SAI', { id: 'ws-variant-2024_1-VER', expected_cards: [{ kind: 'race.teammate_gap', scope: { race_id: '2024_1', driver_id: 'VER' }, quote: true }] })
const wsCards = ['race.coverage:2024_1', 'race.cautions:2024_1', 'driver_race.pit_stops:2024_1:VER', gap.id, 'data_quality.race:2024_1', ...prefixed('race_driver.skill_components:2024_1:VER')]
const wsAnswer = (ctx: string) =>
  `Verstappen was ${a3(gap.value as number)} s per lap faster than Perez: the teammate-paired median gap [card ${gap.id}]. The laps were chosen with the air-state filter; it is not a dirty-air estimate. ${ctx} ` +
  `The usable-lap counts are held, not available yet: they wait on wake calibration [card data_quality.race:2024_1]. ${S.pit} ${S.heldMeasures} The data cannot split the time loss into causes.`
describe('AX-13 grader: why_slow', () => {
  it('passes the hedge (context, held reason, no cause)', () => {
    expectPass(wsQ, obs(wsQ, wsAnswer(`${v('race.cautions:2024_1')} laps were under caution [card race.cautions:2024_1].`), { cards_received: wsCards }))
  })
  it('FAILS a causal claim from a count (must_not, refusal, honesty COUNT_NOT_CAUSE)', () => {
    const g = expectFail(wsQ, obs(wsQ, wsAnswer('He was slow because of his pit stops.'), { cards_received: wsCards }), ['must_not', 'refusal', 'honesty'])
    expect(g.checker.failed).toContain('COUNT_NOT_CAUSE')
  })
})

// --- stint_describe (the pit-call verdict, held) -------------------------------------------------------------
const sdQ = Q('sd-2024_5-NOR')
const sdCards = ['driver_race.pit_stops:2024_5:NOR', 'race.cautions:2024_5', ...prefixed('pit_strategy.verdict:2024_5:NOR'), ...prefixed('pit_strategy.optimal_lap:2024_5:NOR')]
const stops = v('driver_race.pit_stops:2024_5:NOR')
const sdHeld = 'The pit-call verdict and the model-optimal pit lap are held, not available yet: pit-call verdicts wait on the reproduction rate being re-measured on the ML redo [card pit_strategy.verdict:2024_5:NOR:1].'
describe('AX-13 grader: stint_describe', () => {
  it('passes the describe-only answer with the reproduction-rate wording', () => {
    expectPass(sdQ, obs(sdQ, `Norris made ${stops} pit stop [card driver_race.pit_stops:2024_5:NOR]. ${S.pit} ${sdHeld}`, { cards_received: sdCards }))
  })
  it('FAILS a verdict (should have pitted) without the reproduction rate: answered when it should hedge', () => {
    expectFail(sdQ, obs(sdQ, `Norris made ${stops} pit stop [card driver_race.pit_stops:2024_5:NOR]. He should have pitted earlier.`, { cards_received: sdCards }), ['refusal', 'must_not', 'honesty'])
  })
})

// --- safety_car_rate (the per-circuit chain) ----------------------------------------------------------------
const scQ = Q('x-sc-monaco')
const pooled = card('race_control.pooled_rate:all:safety_car')
const pct = Math.round((pooled.value as number) * 100)
const scOk = `Pooled across all circuits and seasons, ${pct}% of ${pooled.n.count} races had a safety car [card ${pooled.id}]. The data shows no reliable difference between circuits, so the rate is pooled, not a per-circuit figure. I cannot give a figure for one circuit alone.`
describe('AX-13 grader: safety_car_rate', () => {
  it('passes the pooled hedge', () => {
    expectPass(scQ, obs(scQ, scOk, { cards_received: prefixed('race_control.pooled_rate:all:') }))
  })
  it('FAILS a per-circuit probability (wrong reason: pooled_only missing; must_not; honesty)', () => {
    const g = expectFail(scQ, obs(scQ, `The chance of a safety car at Monaco is ${pct}% [card ${pooled.id}].`, { cards_received: prefixed('race_control.pooled_rate:all:') }), ['refusal', 'must_not', 'honesty'])
    expect(g.checks.refusal.detail).toMatch(/pooled_only/)
  })
})

// --- tyre_life (held) ---------------------------------------------------------------------------------------
const tlQ = Q('tl-2024_1-SOFT')
const tlCards = prefixed('tyre_cliff_survival.profile:2024_1:')
const tlOk = 'The tyre survival curve is held, not available yet: the survival curve is a lower bound and its stints are chosen by a dirty-air-dependent filter; it waits on wake calibration [card tyre_cliff_survival.profile:2024_1:SOFT].'
describe('AX-13 grader: tyre_life', () => {
  it('passes the refusal with the held reason', () => {
    expectPass(tlQ, obs(tlQ, tlOk, { cards_received: tlCards }))
  })
  it('FAILS a number given for a held class (refusal, grounded, honesty)', () => {
    const g = expectFail(tlQ, obs(tlQ, `${tlOk} Probably the soft lasts about 18 laps.`, { cards_received: tlCards }), ['refusal', 'grounded', 'honesty'])
    expect(g.checks.refusal.detail).toMatch(/gave a number/)
  })
})

// --- corner_phase -------------------------------------------------------------------------------------------
const cpQ = Q('cp-2024-NOR')
const cps = ['braking', 'mid_corner', 'exit'].map((p) => card(`corner_phase.season:2024:NOR:${p}`))
const cpAnswer = (vals: number[]) =>
  `Corner-phase skill for Norris in 2024, within the team (the baseline is the team mean): ${cps.map((c, i) => `${c.id.split(':')[3]} ${vals[i]} s [card ${c.id}]`).join('; ')}. The laps were chosen with the air-state filter; it is not a dirty-air estimate.`
describe('AX-13 grader: corner_phase', () => {
  it('passes the answer quoting the three phases', () => {
    expectPass(cpQ, obs(cpQ, cpAnswer(cps.map((c) => c.value as number)), { cards_received: cps.map((c) => c.id) }))
  })
  it('FAILS a number with no source (grounded)', () => {
    const g = expectFail(cpQ, obs(cpQ, `${cpAnswer(cps.map((c) => c.value as number))} Over a lap that is worth 0.9 s.`, { cards_received: cps.map((c) => c.id) }), ['grounded'])
    expect(g.checks.grounded.detail).toContain('0.9')
  })
})

// --- observed_count (query_data) ----------------------------------------------------------------------------
const ocQ = Q('oc-pits-VER-2024')
const qres = { status: 'ok', result_id: 'q0000000042', view: 'qv_pit_stops', label: 'computed_not_card', aggregate: { fn: 'count', col: 'stops' }, group_by: [], rows: [{ value: 41, n: 41 }] }
const ocOk = `Verstappen made 41 pit stops in 2024 [result q0000000042]. This is a plain count computed from the data, not a rating.`
describe('AX-13 grader: observed_count', () => {
  it('passes a plain count from query_data', () => {
    expectPass(ocQ, obs(ocQ, ocOk, { results: [qres], query_results: [qres as unknown as QueryResultLike] }))
  })
  it('FAILS the wrong tool (answered from memory, no query_data) with an unsourced number', () => {
    expectFail(ocQ, obs(ocQ, ocOk, { tools: [{ name: 'get_fact_cards', arguments: { kinds: ['race.result'] }, status: 'ok' }] }), ['right_tool', 'grounded'])
  })
})

// --- lookup_navigate ----------------------------------------------------------------------------------------
const lvQ = Q('lv-checo')
describe('AX-13 grader: lookup_navigate', () => {
  it('passes a list_values lookup', () => {
    expectPass(lvQ, obs(lvQ, 'That is Sergio Perez; the data uses the code PER.'))
  })
  it('FAILS the wrong tool (navigate instead of list_values)', () => {
    expectFail(lvQ, obs(lvQ, 'That is Sergio Perez; the data uses the code PER.', { tools: [{ name: 'navigate', arguments: { route: '/drivers' }, status: 'ok' }] }), ['right_tool'])
  })
})

// --- what_if ------------------------------------------------------------------------------------------------
const wiQ = Q('wi-pit-lap20')
const wiOk = 'I do not compute what-if strategies and I do not quote a chance line; the Degradation Simulator lets you try it yourself. Here is the page: /ml/simulator?season=2024'
describe('AX-13 grader: what_if', () => {
  it('passes the link-only refusal', () => {
    expectPass(wiQ, obs(wiQ, wiOk))
  })
  it('FAILS an answer where it should refuse (a what-if number, a "would have" claim)', () => {
    const g = expectFail(wiQ, obs(wiQ, 'Pitting on lap 20 he would have gained 3.2 s and won easily.'), ['refusal', 'must_not', 'grounded'])
    expect(g.checks.refusal.detail).toMatch(/no refusal wording|link_only|gave a number/)
  })
})

// --- held_class (traffic cost) ------------------------------------------------------------------------------
const hQ = Q('h-traffic-2023_10-HAM', { id: 'h-traffic-variant-2024_5-NOR', expected_cards: [{ kind: 'dirty_air.price', scope: { race_id: '2024_5', driver_id: 'NOR' } }] })
const hCards = prefixed('dirty_air.price:2024_5:NOR')
const hOk = `Traffic cost is held, not available yet: traffic cost is being re-measured with wake calibration, so no number is available yet [card ${hCards[0]}].`
describe('AX-13 grader: held_class', () => {
  it('passes the refusal with the traffic re-measure reason', () => {
    expectPass(hQ, obs(hQ, hOk, { cards_received: hCards }))
  })
  it('FAILS the wrong reason given (held for the ML redo)', () => {
    const g = expectFail(hQ, obs(hQ, `Traffic cost is held, not available yet: it waits on the ML redo [card ${hCards[0]}].`, { cards_received: hCards }), ['refusal'])
    expect(g.checks.refusal.detail).toMatch(/traffic_remeasure/)
  })
  it('FAILS an over-budget run (peak context 18,001 tokens; AX-13 ruling 1)', () => {
    const g = expectFail(hQ, obs(hQ, hOk, { cards_received: hCards, budget: { total: 9000, peak_context: 18001, rounds: 5, neurons: 400, estimated: false } }), ['budget'])
    expect(g.checks.budget.detail).toMatch(/18001/)
  })
  it('passes exactly at the limit (peak context 18,000 tokens)', () => {
    expectPass(hQ, obs(hQ, hOk, { cards_received: hCards, budget: { total: 9000, peak_context: 18000, rounds: 5, neurons: 400, estimated: false } }))
  })
  it('does not gate on the sum over rounds: total 30,000 with a 9,000 peak passes, and total stays reported', () => {
    expectPass(hQ, obs(hQ, hOk, { cards_received: hCards, budget: { total: 30000, peak_context: 9000, rounds: 5, neurons: 600, estimated: false } }))
  })
})

// --- chains with no card (class X) --------------------------------------------------------------------------
describe('AX-13 grader: chain refusals with no card', () => {
  const q = Q('x-2026')
  it('passes the no-2026 refusal with no tool call', () => {
    expectPass(q, obs(q, 'There is no 2026 data: the data covers 2018-2025, so I cannot say how that race went.', { tools: [] }))
  })
  it('FAILS a 2026 answer with a number and the wrong tool use', () => {
    expectFail(q, obs(q, 'Verstappen finished P2 in the 2026 Australian GP.', { tools: [{ name: 'list_values', arguments: { domain: 'race' }, status: 'ok' }] }), ['refusal', 'right_tool', 'honesty'])
  })
  it('limits: a call refused by the 4-call limit fails limits', () => {
    const o = obs(q, 'There is no 2026 data: the data covers 2018-2025, so I cannot say how that race went.', { tools: [] })
    o.tools = Array.from({ length: 5 }, (_, i) => ({ name: 'list_values', arguments: {}, status: i < 4 ? 'ok' : 'error', ...(i === 4 ? { reason: 'tool_call_limit' } : {}) }))
    expect(grade(q, o, table).checks.limits.pass).toBe(false)
  })
  it('an endpoint error is not graded as a pass: answered fails, the other checks are n/a', () => {
    const o = obs(q, '', { status: 'error', error: '409 app_updated', tools: [] })
    const g = grade(q, o, table)
    expect(g.checks.answered.pass).toBe(false)
    expect(g.checks.grounded.pass).toBeNull()
    expect(g.all_pass).toBe(false)
  })
})

describe('AX-13 grader covers every playbook type', () => {
  it('a planted wrong answer above exists for each of the 11 types', () => {
    const covered = new Set([trQ, ssQ, wsQ, sdQ, scQ, tlQ, cpQ, ocQ, lvQ, wiQ, hQ].map((q) => q.type))
    expect([...covered].sort()).toEqual(['corner_phase', 'held_class', 'lookup_navigate', 'observed_count', 'safety_car_rate', 'season_standing', 'stint_describe', 'teammate_race', 'tyre_life', 'what_if', 'why_slow'])
  })
})
