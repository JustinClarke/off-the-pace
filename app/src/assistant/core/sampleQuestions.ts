// AX-10 sample and demo questions for the headless CLI's stub mode. The "model" is scripted: its tool calls
// are fixed, and its answer text is built from the tool results it was given (so every number it states is
// one the dispatcher really returned). This exercises the dispatcher, loop, checker, grounding check and
// budget meter against real published files. It says nothing about how gpt-oss-20b would answer: that is AX-13.
import type { QuestionSpec } from './cli'
import type { ScriptContext, ScriptEntry } from './modelClient'

type Proj = { id: string; m: string; v: number | string | boolean | null; u: string | null; lbl: string; n: string; iv: [number, number, string] | null; cav: string[]; why?: string }

const cardsOf = (ctx: ScriptContext, call = 0): Proj[] => ((ctx.results('get_fact_cards')[call]?.cards as Proj[] | undefined) ?? [])
const find = (cs: Proj[], id: string) => cs.find((c) => c.id === id)
const f2 = (x: number) => Math.abs(x).toFixed(2)
const sf = (x: number) => `${x < 0 ? '-' : ''}${Math.abs(x).toFixed(2)}`
const nOf = (c: Proj) => Number(/^\d+/.exec(c.n)?.[0] ?? 0)

const PIT_SENTENCE = "I do not judge the stops: the pit-call method matches the team's real call only about a third of the time (a reproduction rate, not a verdict)."
const heldSentence = (c: Proj) => `A split of the lap time into causes is held: it is not available yet, waiting on wake calibration [card ${c.id}]. These are different measures: the lap residual in this held split is not the teammate-paired median gap above.`

/** teammate_race answer from the bundle: the driver's gap (or why there is none), the context card, the held split. */
function teammateAnswer(ctx: ScriptContext, raceId: string, driver: string, who: string, mate: string, raceName: string): string {
  const cs = cardsOf(ctx)
  const gap = find(cs, `race.teammate_gap:${raceId}:${driver}`)
  const cautions = find(cs, `race.cautions:${raceId}`)
  const held = cs.find((c) => c.id.startsWith('race_driver.skill_components:'))
  const stops = cs.find((c) => c.id === `driver_race.pit_stops:${raceId}:${driver}`)
  const parts: string[] = []
  if (!gap) {
    parts.push(`I have no gap card for ${who} in ${raceName}, so I have no data to compare ${who} with ${mate}.`)
  } else if (gap.v === null) {
    parts.push(`There is no reliable gap for ${who} against ${mate} in ${raceName}: no value for the teammate-paired median gap [card ${gap.id}]. ${gap.why ?? ''}`.trim())
  } else {
    const v = gap.v as number
    const n = nOf(gap)
    const thin = n < 12
    const iv = gap.iv ? `, 95% CI ${sf(gap.iv[0])} to ${sf(gap.iv[1])} s` : ''
    parts.push(
      `${who} was ${f2(v)} s per lap ${v < 0 ? 'faster' : 'slower'} than ${mate} in ${raceName}: a teammate-paired median gap over ${n} paired laps${iv} [card ${gap.id}].` +
        (thin ? ' It rests on few paired laps, so read it as directional.' : '') +
        ' The laps were chosen with the air-state filter; it is not a dirty-air estimate.',
    )
  }
  if (cautions && typeof cautions.v === 'number') {
    parts.push(`For context, ${cautions.v} caution laps in a race of ${nOf(cautions)} laps [card ${cautions.id}]; a count of laps does not explain the gap.`)
  }
  if (stops) parts.push(`${who} has a pit-stop card [card ${stops.id}]. ${PIT_SENTENCE}`)
  if (held) parts.push(heldSentence(held))
  return parts.join(' ')
}

const bundleCall = (race_id: string, driver_id: string): ScriptEntry => ({
  tool_calls: [{ name: 'get_fact_cards', arguments: { bundle: 'teammate_race', scopes: [{ race_id, driver_id }] } }],
})

/** The five demo teammate_race questions of AX-21 (demo cards: 2024_1, 2020_14, 2018_1, 2021_16, 2024_5). */
export const DEMO_QUESTIONS: QuestionSpec[] = [
  { race: '2024_1', d: 'VER', who: 'Verstappen', mate: 'Perez', name: 'Bahrain 2024' },
  { race: '2020_14', d: 'HAM', who: 'Hamilton', mate: 'Bottas', name: 'the 2020 Emilia Romagna GP' },
  { race: '2018_1', d: 'RIC', who: 'Ricciardo', mate: 'Verstappen', name: 'the 2018 Australian GP' },
  { race: '2021_16', d: 'HAM', who: 'Hamilton', mate: 'Bottas', name: 'the 2021 Turkish GP' },
  { race: '2024_5', d: 'NOR', who: 'Norris', mate: 'Piastri', name: 'the 2024 Chinese GP' },
].map((x, i) => ({
  id: `demo-${i + 1}`,
  kind: 'demo teammate_race',
  question: `How did ${x.who} do against ${x.mate} in ${x.name}?`,
  script: [bundleCall(x.race, x.d), (_req, ctx) => ({ content: teammateAnswer(ctx, x.race, x.d, x.who, x.mate, x.name) })],
}))

export const SAMPLE_QUESTIONS: QuestionSpec[] = [
  // 3 card-only
  { ...DEMO_QUESTIONS[0], id: 'sample-1', kind: 'card-only (teammate_race bundle)' },
  {
    id: 'sample-2',
    kind: 'card-only (season_standing bundle)',
    question: 'Where does Norris rank against his teammate in 2024?',
    script: [
      { tool_calls: [{ name: 'get_fact_cards', arguments: { bundle: 'season_standing', scopes: [{ season: 2024, driver_id: 'NOR' }] } }] },
      (_r, ctx) => {
        const c = find(cardsOf(ctx), 'season.teammate_gap:2024:NOR')
        if (!c || c.v === null) return { content: 'I have no season gap card for Norris in 2024, so I have no data to rank him.' }
        const iv = c.iv ? ` (95% CI ${sf(c.iv[0])} to ${sf(c.iv[1])} s)` : ''
        const cf = cardsOf(ctx).find((x) => x.id.startsWith('counterfactual_championship.season:'))
        return {
          content:
            `Norris's 2024 era rating, his season gap to his teammate, was ${f2(c.v as number)} s per lap ${(c.v as number) < 0 ? 'faster' : 'slower'}${iv} [card ${c.id}]. ` +
            `His interval overlaps the next driver's, so he is in a group whose intervals overlap, not at a clear place. The laps were chosen with the air-state filter; it is not a dirty-air estimate.` +
            (cf ? ` The championship what-if is held: it is not available yet, waiting on wake calibration; when published it is a statistical, expected-value reconstruction, not a simulation [card ${cf.id}].` : ''),
        }
      },
    ],
  },
  {
    id: 'sample-3',
    kind: 'card-only (safety_car_rate bundle)',
    question: 'How often do safety cars happen in 2024?',
    script: [
      { tool_calls: [{ name: 'get_fact_cards', arguments: { bundle: 'safety_car_rate', scopes: [{ season: 2024 }] } }] },
      (_r, ctx) => {
        const c = find(cardsOf(ctx), 'race_control.pooled_rate:2024:safety_car')
        if (!c || c.v === null) return { content: 'I have no pooled safety-car rate card for 2024, so I have no data to give.' }
        const iv = c.iv ? `, 95% Wilson interval ${(c.iv[0] * 100).toFixed(0)}% to ${(c.iv[1] * 100).toFixed(0)}%` : ''
        return {
          content:
            `Across all circuits in 2024 the safety car rate is pooled: ${((c.v as number) * 100).toFixed(0)}% of races${iv}, from ${c.n} [card ${c.id}]. ` +
            `The data shows no reliable difference between circuits, so I cannot give a figure for one circuit.`,
        }
      },
    ],
  },
  // 2 query_data
  {
    id: 'sample-4',
    kind: 'query_data (count)',
    question: 'How many pit stops did Verstappen make in 2024?',
    script: [
      { tool_calls: [{ name: 'query_data', arguments: { view: 'qv_pit_stops', filters: [{ col: 'season', op: 'eq', val: 2024 }, { col: 'driver_id', op: 'eq', val: 'VER' }], aggregate: { fn: 'count', col: 'stops' } } }] },
      (_r, ctx) => {
        const r = ctx.results('query_data')[0] as { status: string; rows?: { value: number }[]; result_id?: string }
        if (r?.status !== 'ok' || !r.rows?.length) return { content: 'There is no data for that: the query matched no rows, so I cannot give a count.' }
        return { content: `Verstappen made ${r.rows[0].value} pit stops in 2024 [result ${r.result_id}]. This is a plain count computed from the data, not a rating.` }
      },
    ],
  },
  {
    id: 'sample-5',
    kind: 'query_data (grouped, top 3)',
    question: 'Which three drivers made the most pit stops in 2024?',
    script: [
      { tool_calls: [{ name: 'query_data', arguments: { view: 'qv_pit_stops', filters: [{ col: 'season', op: 'eq', val: 2024 }], group_by: ['driver_id'], aggregate: { fn: 'count', col: 'stops' }, order: 'value_desc', limit: 3 } }] },
      (_r, ctx) => {
        const r = ctx.results('query_data')[0] as { status: string; rows?: { driver_id: string; value: number }[]; result_id?: string }
        if (r?.status !== 'ok' || !r.rows?.length) return { content: 'There is no data for that: the query matched no rows.' }
        const list = r.rows.map((x) => `${x.driver_id} with ${x.value}`).join(', ')
        return { content: `The three drivers with the most pit stops in 2024 were ${list} [result ${r.result_id}]. These are plain counts computed from the data, not a rating.` }
      },
    ],
  },
  // 1 list_values alias
  {
    id: 'sample-6',
    kind: 'list_values alias ("Checo")',
    question: 'Who is Checo?',
    script: [
      { tool_calls: [{ name: 'list_values', arguments: { domain: 'driver', query: 'Checo' } }] },
      (_r, ctx) => {
        const r = ctx.results('list_values')[0] as { rows?: { code: string; display: string; seasons: string }[] }
        const top = r?.rows?.[0]
        return { content: top ? `Checo is ${top.display}; his driver code in the data is ${top.code}, and he appears in seasons ${top.seasons}.` : 'I found no driver called Checo, so I have no data on him.' }
      },
    ],
  },
  // 1 on-screen, 0 tool calls
  {
    id: 'sample-7',
    kind: 'on-screen (0 tool calls)',
    question: 'How many laps were under caution in this race?',
    page: { route: '/race-craft/race-control', params: { season: 2024, race_id: '2024_1' } },
    script: [
      (req) => {
        const line = req.messages[req.messages.length - 1].content.split('\n').find((l) => l.startsWith('{"id":"race.cautions:'))
        const c = line ? (JSON.parse(line) as Proj) : null
        return { content: c && typeof c.v === 'number' ? `${c.v} laps in this race were under caution, out of ${c.n} [card ${c.id}].` : 'I have no on-screen card for that, so I have no data.' }
      },
    ],
  },
  // 1 held class refused with its reason
  {
    id: 'sample-8',
    kind: 'held class (refused with its reason)',
    question: 'How much did traffic cost Hamilton at Silverstone 2023?',
    script: [
      { tool_calls: [{ name: 'get_fact_cards', arguments: { kinds: ['dirty_air.price'], scopes: [{ race_id: '2023_10', driver_id: 'HAM' }] } }] },
      (_r, ctx) => {
        const r = ctx.results('get_fact_cards')[0] as { status: string; cards?: Proj[]; held?: { held_reason: string }[] }
        const stub = r?.cards?.[0]
        const reason = stub?.why ?? r?.held?.[0]?.held_reason ?? 'it is held'
        return {
          content: `That figure is held: it is not available yet, while traffic cost is re-measured with wake calibration${stub ? ` [card ${stub.id}]` : ''}. The card says: "${reason}" Dirty-air cost is modelled, not measured, and I will not estimate it.`,
        }
      },
    ],
  },
  // 1 what-if (link only)
  {
    id: 'sample-9',
    kind: 'what-if (link only)',
    question: 'What if Verstappen had pitted on lap 20 in Bahrain 2024?',
    script: [
      { tool_calls: [{ name: 'navigate', arguments: { route: '/ml/simulator', params: { season: 2024 } } }] },
      (_r, ctx) => {
        const r = ctx.results('navigate')[0] as { status: string; url?: string }
        return { content: r?.status === 'ok' ? `I do not compute what-if tyre strategies. The Degradation Simulator lets you try it yourself: ${r.url}` : 'I do not compute what-if tyre strategies, and I could not build the Simulator link.' }
      },
    ],
  },
  // 1 navigate
  {
    id: 'sample-10',
    kind: 'navigate',
    question: 'Take me to the pit strategy page for Monaco 2024.',
    script: [
      { tool_calls: [{ name: 'navigate', arguments: { route: '/tyre-strategy/pit-gantt', params: { season: 2024, race_id: '2024_8' } } }] },
      (_r, ctx) => {
        const r = ctx.results('navigate')[0] as { status: string; url?: string }
        return { content: r?.status === 'ok' ? `Here is the pit strategy page for Monaco 2024: ${r.url}` : 'I could not build that link.' }
      },
    ],
  },
]
