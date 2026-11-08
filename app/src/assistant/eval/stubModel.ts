// AX-13 STUB model. Deterministic, no network. It measures the HARNESS (dispatcher, loop, budget meter,
// checker, grounding, grader), not a model: its tool calls are fixed per question, and its answer is
// composed from the tool results it was given, using the wording system.md tells a model to use
// (the teammate_race sentences are read out of system.md itself, so a change there changes the stub).
// It never reads policy.json, the checker or the question's expectations. A repair turn gets the same
// draft back (a stub cannot fix its answer), so a repair in the stub run is a harness or prompt gap.
import systemMd from '../prompt/system.md?raw'
import type { ScriptContext, ScriptEntry, ScriptStep } from '../core/modelClient'
import type { ModelRequest } from '../core/types'
import type { Question } from './questions'

type Proj = { id: string; m: string; v: number | string | boolean | null; u: string | null; lbl: string; n: string; iv: [number, number, string] | null; cav: string[]; pg?: string | null; why?: string }
type Call = { name: string; arguments: Record<string, unknown> }

/** The two teammate_race sentences quoted in system.md's Refusals paragraph. */
export function systemSentences(md: string = systemMd): { pit: string; heldMeasures: string } {
  const pit = /then say: "([^"]+)"/.exec(md)?.[1]
  const heldMeasures = /only that sentence and this one: "([^"]+)"/.exec(md)?.[1]
  if (!pit || !heldMeasures) throw new Error('system.md no longer quotes the teammate_race sentences')
  return { pit, heldMeasures }
}

/** Plain-language reasons for questions no card answers (the chain lines of system.md). */
export const REASON_SENTENCES: Record<string, string> = {
  no_2026: 'There is no 2026 data: the data covers 2018-2025, so I cannot say how that race went.',
  different_eras:
    'I cannot answer that: laps from different eras are not comparable across eras (the cars and rules differ), so raw lap times cannot settle which driver is quicker.',
  in_sample:
    'I cannot claim that: the Blind Test and Model Metrics are scored in-sample or on a validation fold, so they are not out-of-sample evidence about races the model has never seen.',
  grey_cell: 'Not necessarily: a grey cell on the lap map can be clean air or missing telemetry, so it does not show he was in free air.',
  shared_inputs:
    'They are not two independent confirmations: circuit affinity and the era rating share the same laps, so they are not independent.',
  different_measures:
    'I cannot rank them across different skill measures: the era-adjusted rating and corner-phase skill are different measures, not one scale. I quote the era rating only.',
  pooled_only: 'I cannot give a figure for one circuit alone.',
  link_only: 'I do not compute what-if strategies and I do not quote a chance line; the Degradation Simulator lets you try it yourself.',
}

/** What the stub does for one question: tool-call rounds (one array per model round), then the answer. */
export interface StubPlan {
  rounds: Call[][]
  /** Who the question is about (for the sentences), e.g. "Verstappen". */
  who?: string
  /** System.md chain lines the stub adds (questions whose reason is not on a card). */
  reasons?: string[]
}

const gfc = (a: Record<string, unknown>): Call => ({ name: 'get_fact_cards', arguments: a })
const bundle = (b: string, scope: Record<string, unknown>): Call => gfc({ bundle: b, scopes: [scope] })
const kinds = (k: string[], ...scopes: Record<string, unknown>[]): Call => gfc({ kinds: k, scopes })
const qd = (a: Record<string, unknown>): Call => ({ name: 'query_data', arguments: a })
const lv = (domain: string, query?: string, extra: Record<string, unknown> = {}): Call => ({ name: 'list_values', arguments: { domain, ...(query ? { query } : {}), ...extra } })
const nav = (route: string, params: Record<string, unknown> = {}): Call => ({ name: 'navigate', arguments: { route, params } })
const explain = (page: string): Call => ({ name: 'explain_page', arguments: { page } })
const cmp = (race_id: string, a: string, b: string): Call => ({ name: 'compare_lap_times', arguments: { race_id, driver_a: a, driver_b: b } })
const chart = (kind?: string): Call => ({ name: 'make_chart', arguments: { result_id: '$LAST_RESULT', ...(kind ? { kind } : {}) } })
const eq = (col: string, val: unknown) => ({ col, op: 'eq', val })

export const STUB_PLANS: Record<string, StubPlan> = {
  'tr-2024_1-VER': { rounds: [[bundle('teammate_race', { race_id: '2024_1', driver_id: 'VER' })]], who: 'Verstappen' },
  'tr-2020_14-HAM': { rounds: [[bundle('teammate_race', { race_id: '2020_14', driver_id: 'HAM' })]], who: 'Hamilton' },
  'tr-2018_1-RIC': { rounds: [[bundle('teammate_race', { race_id: '2018_1', driver_id: 'RIC' })]], who: 'Ricciardo' },
  'tr-2021_16-HAM': { rounds: [[bundle('teammate_race', { race_id: '2021_16', driver_id: 'HAM' })]], who: 'Hamilton' },
  'tr-2024_5-NOR': { rounds: [[bundle('teammate_race', { race_id: '2024_5', driver_id: 'NOR' })]], who: 'Norris' },
  'tr-2019_1-NOR': { rounds: [[bundle('teammate_race', { race_id: '2019_1', driver_id: 'NOR' })]], who: 'Norris' },
  'ss-2024-NOR': { rounds: [[bundle('season_standing', { season: 2024, driver_id: 'NOR' })]], who: 'Norris' },
  'ss-2023-ALO': { rounds: [[bundle('season_standing', { season: 2023, driver_id: 'ALO' })]], who: 'Alonso' },
  'er-2023-ALO': { rounds: [[kinds(['era_rating.season'], { season: 2023, driver_id: 'ALO' })]], who: 'Alonso' },
  'rr-2023_10-HAM': { rounds: [[kinds(['race.result'], { race_id: '2023_10', driver_id: 'HAM' })]], who: 'Hamilton' },
  'rc-2024_8': { rounds: [[kinds(['race.coverage'], { race_id: '2024_8' })]] },
  'ws-2024_8-SAI': { rounds: [[bundle('why_slow', { race_id: '2024_8', driver_id: 'SAI' })]], who: 'Sainz' },
  'ws-2023_10-HAM': { rounds: [[bundle('why_slow', { race_id: '2023_10', driver_id: 'HAM' })]], who: 'Hamilton' },
  'sd-2024_1-VER': { rounds: [[bundle('stint_describe', { race_id: '2024_1', driver_id: 'VER' })]], who: 'Verstappen' },
  'sd-2024_5-NOR': { rounds: [[bundle('stint_describe', { race_id: '2024_5', driver_id: 'NOR' })]], who: 'Norris' },
  'sc-all': { rounds: [[bundle('safety_car_rate', {})]] },
  'sc-2018': { rounds: [[bundle('safety_car_rate', { season: 2018 })]] },
  'x-sc-monaco': { rounds: [[bundle('safety_car_rate', {})]], reasons: ['pooled_only'] },
  'tl-2024_1-SOFT': { rounds: [[bundle('tyre_life', { race_id: '2024_1' })]] },
  'tl-2023_10-HARD': { rounds: [[bundle('tyre_life', { race_id: '2023_10' })]] },
  'cp-2024-NOR': { rounds: [[bundle('corner_phase', { season: 2024, driver_id: 'NOR' })]], who: 'Norris' },
  'cp-2024-VER': { rounds: [[bundle('corner_phase', { season: 2024, driver_id: 'VER' })]], who: 'Verstappen' },

  'oc-pits-VER-2024': { rounds: [[qd({ view: 'qv_pit_stops', filters: [eq('season', 2024), eq('driver_id', 'VER')], aggregate: { fn: 'count', col: 'stops' } })]] },
  'oc-pits-top3-2024': { rounds: [[qd({ view: 'qv_pit_stops', filters: [eq('season', 2024)], group_by: ['driver_id'], aggregate: { fn: 'count', col: 'stops' }, order: 'value_desc', limit: 3 })]] },
  'oc-wins-VER-2023': { rounds: [[qd({ view: 'qv_driver_race', filters: [eq('season', 2023), eq('driver_id', 'VER'), eq('actual_finish_position', 1)], aggregate: { fn: 'count', col: 'races' } })]] },
  'oc-sc-laps-2024': { rounds: [[qd({ view: 'qv_race_laps', filters: [eq('season', 2024), eq('caution_status', 'safety_car')], aggregate: { fn: 'count', col: 'laps' } })]] },
  'oc-soft-stint-2024': { rounds: [[qd({ view: 'qv_stints', filters: [eq('season', 2024), eq('compound', 'SOFT'), eq('is_censored_stint', false)], aggregate: { fn: 'avg', col: 'stint_length_laps' } })]] },
  'oc-dnf-LEC-2022': {
    rounds: [[lv('driver', 'Charles', { season: 2022 })], [qd({ view: 'qv_driver_race', filters: [eq('season', 2022), eq('driver_id', 'LEC'), eq('has_dnf', true)], aggregate: { fn: 'count', col: 'races' } })]],
  },
  'oc-gained-2021': { rounds: [[qd({ view: 'qv_driver_race', filters: [eq('season', 2021)], group_by: ['driver_id'], aggregate: { fn: 'avg', col: 'positions_gained' }, order: 'value_desc', limit: 3 })]] },
  'oc-quickest-2024_1': { rounds: [[qd({ view: 'qv_laps', filters: [eq('season', 2024), eq('race_id', '2024_1')], group_by: ['driver_id'], aggregate: { fn: 'min', col: 'lap_time_s' }, order: 'value_asc', limit: 3 })]] },
  'oc-corners': { rounds: [[qd({ view: 'qv_circuits', group_by: ['circuit_name'], aggregate: { fn: 'max', col: 'corner_count' }, order: 'value_desc', limit: 3 })]] },
  'oc-monaco-sc-history': { rounds: [[qd({ view: 'qv_circuit_history', filters: [eq('circuit_slug', 'monaco_grand_prix'), eq('season', 2024)], aggregate: { fn: 'sum', col: 'prior_sc_onsets' } })]] },
  'oc-stints-HAM-2024_1': { rounds: [[qd({ view: 'qv_stints', filters: [eq('season', 2024), eq('race_id', '2024_1'), eq('driver_id', 'HAM')], group_by: ['compound'], aggregate: { fn: 'count', col: 'stints' } })]] },
  'oc-braking-2024_8': {
    rounds: [[qd({ view: 'qv_teammate_corners', filters: [eq('season', 2024), eq('race_id', '2024_8'), eq('driver_a', 'NOR'), eq('driver_b', 'PIA')], aggregate: { fn: 'median', col: 'braking_point_delta_m' } })]],
  },

  'ch-pits-per-race-2024': { rounds: [[qd({ view: 'qv_pit_stops', filters: [eq('season', 2024)], group_by: ['race_id'], aggregate: { fn: 'count', col: 'stops' }, order: 'group_asc', limit: 25 })], [chart('bar')]] },
  'ch-sc-laps-season': {
    rounds: [[qd({ view: 'qv_race_laps', filters: [{ col: 'season', op: 'in', val: [2024, 2025] }, eq('caution_status', 'safety_car')], group_by: ['season'], aggregate: { fn: 'count', col: 'laps' }, order: 'group_asc' })], [chart('bar')]],
  },
  'ch-stint-compound-2023': { rounds: [[qd({ view: 'qv_stints', filters: [eq('season', 2023)], group_by: ['compound'], aggregate: { fn: 'avg', col: 'stint_length_laps' }, order: 'value_desc' })], [chart('bar')]] },
  'ch-laps-VER-2024_1': {
    rounds: [[qd({ view: 'qv_laps', filters: [eq('season', 2024), eq('race_id', '2024_1'), eq('driver_id', 'VER')], group_by: ['lap_number'], aggregate: { fn: 'avg', col: 'lap_time_s' }, order: 'group_asc', limit: 25 })], [chart('line')]],
  },
  'ch-wins-2023': { rounds: [[qd({ view: 'qv_driver_race', filters: [eq('season', 2023), eq('actual_finish_position', 1)], group_by: ['driver_id'], aggregate: { fn: 'count', col: 'races' }, order: 'value_desc' })], [chart('bar')]] },

  'cmp-2024_1-VER-PER': { rounds: [[cmp('2024_1', 'VER', 'PER')]] },
  'cmp-2024_5-NOR-PIA': { rounds: [[cmp('2024_5', 'NOR', 'PIA')]] },
  'cmp-2023_10-HAM-RUS': { rounds: [[cmp('2023_10', 'HAM', 'RUS')]] },
  'cmp-2022_1-LEC-SAI': { rounds: [[cmp('2022_1', 'LEC', 'SAI')]] },
  'cmp-2019_1-NOR-SAI': { rounds: [[cmp('2019_1', 'NOR', 'SAI')]] },

  'ex-race-lost': { rounds: [[explain('/lap-decomposition/race-lost')]] },
  'ex-pit-gantt': { rounds: [[explain('/tyre-strategy/pit-gantt')]] },
  'ex-survival': { rounds: [[explain('/tyre-strategy/survival')]] },
  'ex-ratings': { rounds: [[explain('/drivers/ratings-timeline')]] },
  'x-lap-map-grey': { rounds: [[explain('/aero/lap-map')]], reasons: ['grey_cell'] },

  'nav-pit-gantt-2024_8': { rounds: [[nav('/tyre-strategy/pit-gantt', { season: 2024, race_id: '2024_8' })]] },
  'nav-race-control-2024_5': { rounds: [[nav('/race-craft/race-control', { season: 2024, race_id: '2024_5' })]] },
  'nav-ratings': { rounds: [[nav('/drivers/ratings-timeline')]] },
  'nav-corner-2024': { rounds: [[nav('/drivers/corner-skill', { season: 2024 })]] },
  'os-cautions-2024_1': { rounds: [] },

  'lv-checo': { rounds: [[lv('driver', 'Checo')]] },
  'lv-kmag': { rounds: [[lv('driver', 'K-Mag')]] },
  'lv-teams-2024': { rounds: [[lv('constructor', undefined, { season: 2024 })]] },
  'lv-spa': { rounds: [[lv('circuit', 'Spa')]] },

  'wi-pit-lap20': { rounds: [[nav('/ml/simulator', { season: 2024 })]], reasons: ['link_only'] },
  'x-chance-line': { rounds: [[nav('/ml/simulator', { season: 2024 })]], reasons: ['link_only'] },
  'wi-no-stop-2021': { rounds: [[nav('/ml/simulator', { season: 2021 })]], reasons: ['link_only'] },

  'x-skill-mix-2024': {
    rounds: [[kinds(['season.teammate_gap', 'corner_phase.season'], { season: 2024, driver_id: 'VER' }, { season: 2024, driver_id: 'NOR' })]],
    reasons: ['different_measures'],
  },
  'x-affinity-era': { rounds: [[kinds(['era_rating.season'], { season: 2023, driver_id: 'HAM' })]], who: 'Hamilton', reasons: ['shared_inputs'] },
  'x-would-have-won-2022': { rounds: [[kinds(['counterfactual_championship.season'], { season: 2022 })]] },
  'x-blind-test': { rounds: [[explain('/ml/blind-test')]], reasons: ['in_sample'] },
  'x-sector-2023_10-VER': { rounds: [[kinds(['sector_decomposition.component'], { race_id: '2023_10', driver_id: 'VER' })]] },
  'x-2026': { rounds: [], reasons: ['no_2026'] },
  'x-cross-era': { rounds: [], reasons: ['different_eras'] },
  'x-constructor-pace-2023': { rounds: [[kinds(['constructor_structural_pace.season'], { season: 2023, constructor_id: 'Red Bull Racing' })]] },

  'h-traffic-2023_10-HAM': { rounds: [[kinds(['dirty_air.price'], { race_id: '2023_10', driver_id: 'HAM' })]] },
  'h-dirty-air-2024_1-NOR': { rounds: [[kinds(['dirty_air.price'], { race_id: '2024_1', driver_id: 'NOR' })]] },
  'h-ml-band-2024_1-VER': { rounds: [[kinds(['ml.prediction_band'], { race_id: '2024_1', driver_id: 'VER' })]], reasons: ['ml_band'] },
  'h-ml-cliff-2024_1': { rounds: [[bundle('tyre_life', { race_id: '2024_1' })]] },
  'h-race-lost-2024_1-PER': { rounds: [[kinds(['race_driver.skill_components'], { race_id: '2024_1', driver_id: 'PER' })]] },
  'h-ghost-2024_1': { rounds: [[kinds(['ghost_race.standings'], { race_id: '2024_1' })]] },
  'h-ghost-champ-2021': { rounds: [[kinds(['counterfactual_championship.season'], { season: 2021 })]] },
  'h-consistency-2023': { rounds: [[kinds(['driver_consistency.season'], { season: 2023 })]] },
  'h-wet-2021': { rounds: [[kinds(['wet_race.specialist'], { season: 2021 })]] },
  'h-party-2020': { rounds: [[kinds(['party_mode.season'], { season: 2020, constructor_id: 'Mercedes' })]] },
}

// The ML prediction band has no card kind yet (pending AX-17): the playbook's held reason, in plain words.
REASON_SENTENCES.ml_band = 'Model prediction bands are held: they are not published yet and wait on the ML redo, so I have no predicted lap time to give.'

// ---------------------------------------------------------------------------------------------------
// Answer composition from the tool results.

const HELD_NAMES: Record<string, string> = {
  'race_driver.skill_components': 'the time-loss breakdown (the lap residual)',
  'lap_waterfall.component': 'the lap waterfall',
  'sector_decomposition.component': 'sector attribution',
  'data_quality.race': 'the usable-lap counts',
  'ghost_race.standings': 'the ghost-race standings',
  'counterfactual_championship.season': 'the championship what-if',
  'hidden_performance.season': 'hidden performance',
  'constructor_structural_pace.season': 'the structural car-pace figure',
  'constructor_team_averages.season': "Team Averages' car term",
  'constructor_circuit_interaction.season': 'the constructor-circuit figure',
  'party_mode.season': 'the party-mode figure',
  'driver_consistency.season': 'the consistency residual',
  'wet_race.specialist': 'the wet-race proxy',
  'season_driver.skill_benchmark': 'the skill benchmark',
  'driver_isolation.race': 'the isolation figure',
  'driver_isolation.stint': 'the stint isolation figure',
  'dirty_air.price': 'traffic cost',
  'tyre_cliff_survival.profile': 'the tyre survival curve',
  'pit_strategy.verdict': 'the pit-call verdict',
  'pit_strategy.optimal_lap': 'the model-optimal pit lap',
  'pit_strategy.opportunity_cost': 'the pit opportunity cost',
  'ml.cliff_probability': 'the ML cliff probability',
  'ml.prediction_band': 'the ML prediction band',
}

const kindOf = (id: string) => id.split(':')[0]

/** The held reason in plain words, with no number (a refusal never states one). */
export function plainReason(kind: string, why: string): string {
  if (/re-measured|dirty-air calibration/i.test(why) && kind === 'dirty_air.price') return 'traffic cost is being re-measured with wake calibration, so no number is available yet'
  if (/AX-18|reproduction rate/i.test(why)) return 'pit-call verdicts wait on the reproduction rate being re-measured on the ML redo'
  if (/ML redo/i.test(why)) return 'it waits on the ML redo'
  if (/survival curve/i.test(why)) return 'the survival curve is a lower bound and its stints are chosen by a dirty-air-dependent filter; it waits on wake calibration'
  if (/ghost-car pace/i.test(why))
    return 'it is built on ghost-car pace, which includes the unvalidated dirty-air term, and waits on wake calibration; when published it is a statistical, expected-value reconstruction, not a simulation'
  return 'it includes the unvalidated dirty-air term and waits on wake calibration'
}

const abs3 = (x: number) => Math.abs(x).toFixed(3)
const signed3 = (x: number) => `${x < 0 ? '-' : ''}${Math.abs(x).toFixed(3)}`
const nCount = (p: Proj) => Number(/^\d+/.exec(p.n)?.[0] ?? 0)
const ivText = (p: Proj) => (p.iv && p.iv[2] !== 'se_1' ? `, 95% CI ${signed3(p.iv[0])} to ${signed3(p.iv[1])} s` : '')
const cite = (id: string) => `[card ${id}]`
const fmtValue = (v: unknown): string => (typeof v === 'number' ? (Number.isInteger(v) ? String(v) : String(Number(v.toFixed(3)))) : String(v))
const FN_WORD: Record<string, string> = { count: 'count', avg: 'average', median: 'median', min: 'minimum', max: 'maximum', sum: 'total' }

interface Gathered {
  cards: Proj[]
  held: { kind: string; held_reason: string }[]
  queries: { result_id: string; rows: Record<string, unknown>[]; group_by: string[]; aggregate: { fn: string; col: string }; view: string }[]
  charts: { chart_id: string }[]
  compares: { chart_id: string; n_a: number; n_b: number; laps_missing: number; a: string; b: string }[]
  links: string[]
  lists: { code: string; display: string }[]
  explains: { title: string; page_id: string }[]
}

function gather(req: ModelRequest, ctx: ScriptContext, plan: StubPlan): Gathered {
  const g: Gathered = { cards: [], held: [], queries: [], charts: [], compares: [], links: [], lists: [], explains: [] }
  // The page-context block (pre-load) is the first user message's card lines.
  const first = req.messages.find((m) => m.role === 'user')?.content ?? ''
  for (const line of first.split('\n')) if (line.startsWith('{"id":')) g.cards.push(JSON.parse(line) as Proj)
  for (const r of ctx.results('get_fact_cards')) {
    for (const c of (r.cards as Proj[] | undefined) ?? []) if (!g.cards.some((x) => x.id === c.id)) g.cards.push(c)
    for (const h of (r.held as Gathered['held'] | undefined) ?? []) g.held.push(h)
  }
  for (const r of ctx.results('query_data')) if (r.status === 'ok') g.queries.push(r as unknown as Gathered['queries'][number])
  for (const r of ctx.results('make_chart')) if (r.status === 'ok') g.charts.push(r as unknown as { chart_id: string })
  const cmpCalls = plan.rounds.flat().filter((c) => c.name === 'compare_lap_times')
  ctx.results('compare_lap_times').forEach((r, i) => {
    if (r.status === 'ok') g.compares.push({ ...(r as unknown as Gathered['compares'][number]), a: String(cmpCalls[i]?.arguments.driver_a), b: String(cmpCalls[i]?.arguments.driver_b) })
  })
  for (const r of ctx.results('navigate')) if (r.status === 'ok') g.links.push(String(r.url))
  for (const r of ctx.results('list_values')) for (const row of ((r.rows as Gathered['lists'] | undefined) ?? []).slice(0, 12)) g.lists.push(row)
  for (const r of ctx.results('explain_page')) if (r.status === 'ok') g.explains.push({ title: String(r.title), page_id: String(r.page_id) })
  return g
}

function liveSentence(p: Proj, who: string | undefined, focus: string | undefined): string | null {
  const kind = kindOf(p.id)
  const subject = who ?? p.id.split(':')[2] ?? 'the driver'
  const isFocus = !focus || p.id.split(':')[2] === focus
  switch (kind) {
    case 'race.teammate_gap': {
      if (!isFocus) return null
      if (p.v === null) return `There is no reliable gap for ${subject} against his teammate here: no value ${cite(p.id)}. The card says: ${p.why ?? 'unavailable'}.`
      const v = p.v as number
      const n = nCount(p)
      return (
        `${subject} was ${abs3(v)} s per lap ${v < 0 ? 'faster' : 'slower'} than his teammate: the teammate-paired median gap over ${n} paired laps${ivText(p)} ${cite(p.id)}.` +
        (n < 12 ? ' It rests on few paired laps, so read it as directional.' : '')
      )
    }
    case 'race.result':
      if (!isFocus || typeof p.v !== 'number') return null
      return `${subject} finished in position ${p.v} ${cite(p.id)}.`
    case 'race.cautions':
      return typeof p.v === 'number' ? `For context, ${p.v} of ${nCount(p)} laps were under caution ${cite(p.id)}; a count of laps does not explain the gap.` : null
    case 'race.coverage':
      return `The race coverage card reads ${String(p.v)} over ${p.n} ${cite(p.id)}${p.v === 'OK' ? ': the race could be rated' : ': not every driver could be rated'}.`
    case 'driver_race.pit_stops':
      if (!isFocus || typeof p.v !== 'number') return null
      return `${subject} made ${p.v} pit stop${p.v === 1 ? '' : 's'} ${cite(p.id)}.`
    case 'season.teammate_gap':
    case 'era_rating.season': {
      if (typeof p.v !== 'number') return null
      const d = p.id.split(':')[2]
      const season = p.id.split(':')[1]
      return `${d}'s ${season} era rating, the season gap to his teammate, was ${abs3(p.v)} s per lap ${p.v < 0 ? 'faster' : 'slower'} over ${p.n}${ivText(p)} ${cite(p.id)}; his interval overlaps the drivers next to him, so he is in a group whose intervals overlap, not at a clear place.`
    }
    case 'corner_phase.season': {
      if (typeof p.v !== 'number') return null
      const phase = p.id.split(':')[3]?.replace('_', '-') ?? 'phase'
      return `${phase} ${fmtValue(p.v)} s over ${p.n} ${cite(p.id)}`
    }
    case 'race_control.pooled_rate':
      if (!p.id.endsWith(':safety_car') || typeof p.v !== 'number') return null
      return `Pooled across all circuits${p.id.includes(':all:') ? ' and seasons' : ` in ${p.id.split(':')[1]}`}, ${Math.round(p.v * 100)}% of ${p.n} had a safety car ${cite(p.id)}.`
    default:
      return null
  }
}

/** Compose the stub's answer for `q` from what the tools returned. */
export function composeAnswer(_q: Question, plan: StubPlan, req: ModelRequest, ctx: ScriptContext): string {
  const g = gather(req, ctx, plan)
  const S = systemSentences()
  const out: string[] = []
  const focus = (plan.rounds.flat().find((c) => c.name === 'get_fact_cards')?.arguments.scopes as { driver_id?: string }[] | undefined)?.[0]?.driver_id
  const live = g.cards.filter((c) => c.v !== null || kindOf(c.id) === 'race.teammate_gap')
  const heldCards = g.cards.filter((c) => c.v === null && kindOf(c.id) !== 'race.teammate_gap')

  // Live cards, one clause each (corner phases folded into one sentence).
  const corners = live.filter((c) => kindOf(c.id) === 'corner_phase.season')
  const quoteCorners = corners.length > 0 && !(plan.reasons ?? []).includes('different_measures')
  for (const c of live) {
    if (kindOf(c.id) === 'corner_phase.season') continue
    const s = liveSentence(c, plan.who, focus)
    if (s) out.push(s)
  }
  if (quoteCorners) {
    const byDriver = new Map<string, Proj[]>()
    for (const c of corners) byDriver.set(c.id.split(':')[2], [...(byDriver.get(c.id.split(':')[2]) ?? []), c])
    for (const [d, cs] of byDriver) {
      out.push(
        `Corner-phase skill for ${d} in ${cs[0].id.split(':')[1]}, within the team (the baseline is the team mean): ${cs.map((c) => liveSentence(c, undefined, undefined)).join('; ')}. Each phase is on its own scale; this is one skill measure, not an overall ranking.`,
      )
    }
  }
  if (live.some((c) => c.cav.includes('AIR_STATE_FILTER'))) out.push('The laps were chosen with the air-state filter (traffic laps left out); it is not a dirty-air estimate.')
  if (live.some((c) => kindOf(c.id) === 'race_control.pooled_rate')) out.push('The data shows no reliable difference between circuits, so the rate is pooled, not a per-circuit figure.')

  // Pit stops present -> the system.md pit sentence.
  const hasPit = g.cards.some((c) => kindOf(c.id) === 'driver_race.pit_stops' || kindOf(c.id).startsWith('pit_strategy.'))
  if (hasPit) out.push(S.pit)

  // Held cards and held entries, grouped by reason.
  const heldBy = new Map<string, { names: string[]; ids: string[] }>()
  const addHeld = (kind: string, why: string, id?: string) => {
    if (kind === 'race_driver.skill_components' && live.some((c) => kindOf(c.id) === 'race.teammate_gap')) return // the system.md sentence covers it
    const reason = plainReason(kind, why)
    const e = heldBy.get(reason) ?? { names: [], ids: [] }
    const name = HELD_NAMES[kind] ?? kind
    if (!e.names.includes(name)) e.names.push(name)
    if (id && e.ids.length < 1) e.ids.push(id)
    heldBy.set(reason, e)
  }
  for (const c of heldCards) addHeld(kindOf(c.id), c.why ?? '', c.id)
  for (const h of g.held) addHeld(h.kind, h.held_reason)
  for (const [reason, e] of heldBy) {
    const names = e.names.join(', ')
    out.push(`${names.charAt(0).toUpperCase()}${names.slice(1)} ${e.names.length > 1 ? 'are' : 'is'} held, not available yet: ${reason}${e.ids.length ? ` ${cite(e.ids[0])}` : ''}.`)
  }
  if (g.cards.some((c) => kindOf(c.id) === 'race_driver.skill_components') && live.some((c) => kindOf(c.id) === 'race.teammate_gap')) out.push(S.heldMeasures)
  if (heldCards.some((c) => kindOf(c.id) === 'race_driver.skill_components') && !live.length) out.push('The lap residual means time left unexplained, not driver error.')

  // Query results, charts, comparisons.
  for (const r of g.queries) {
    const fn = FN_WORD[r.aggregate.fn] ?? r.aggregate.fn
    if (!r.rows.length) {
      out.push(`The query matched no rows, so there is no data for that [result ${r.result_id}].`)
      continue
    }
    const rows = r.rows.slice(0, 5).map((row) => (r.group_by.length ? `${r.group_by.map((k) => String(row[k])).join(' ')}: ${fmtValue(row.value)}` : fmtValue(row.value)))
    out.push(`${r.group_by.length ? `By ${r.group_by.join(' and ').replace(/_/g, ' ')}, the ${fn} of ${r.aggregate.col.replace(/_/g, ' ')} is ${rows.join(', ')}` : `The ${fn} of ${r.aggregate.col.replace(/_/g, ' ')} is ${rows[0]}`}${r.rows.length > 5 ? ' (first five shown)' : ''} [result ${r.result_id}]. This is a plain ${fn} computed from the data, not a rating.`)
  }
  for (const c of g.charts) out.push(`Here is the chart [chart ${c.chart_id}].`)
  for (const c of g.compares)
    out.push(`Here is the lap-time chart for ${c.a} and ${c.b} [chart ${c.chart_id}]: ${c.n_a} laps against ${c.n_b} laps, observed green laps, not fuel- or tyre-corrected.`)

  // Lookups, explanations, links.
  if (g.lists.length) {
    const top = g.lists.slice(0, plan.rounds.flat().some((c) => c.name === 'list_values' && !c.arguments.query) ? 12 : 1)
    if (top.length === 1) out.push(`That is ${top[0].display}; the data uses the code ${top[0].code}.`)
    else out.push(`In the data: ${top.map((r) => r.display).join(', ')}.`)
  }
  for (const e of g.explains) out.push(`The ${e.title} page is explained in the app's notes (page ${e.page_id}).`)

  // System.md chain lines the question needs.
  for (const k of plan.reasons ?? []) if (REASON_SENTENCES[k]) out.push(REASON_SENTENCES[k])
  for (const url of g.links) out.push(`Here is the page: ${url}`)

  if (!out.length) out.push('I have no data for that, so I have no answer to give.')
  return out.join(' ')
}

/** The ScriptedModel script for one question: the planned tool rounds, then the composed answer (repeated on a repair turn). */
export function stubScript(q: Question, plan: StubPlan | undefined = STUB_PLANS[q.id]): ScriptEntry[] {
  if (!plan) throw new Error(`no stub plan for ${q.id}`)
  let draft: string | null = null
  const rounds: ScriptEntry[] = plan.rounds.map(
    (calls) =>
      (_req: ModelRequest, ctx: ScriptContext): ScriptStep => ({
        tool_calls: calls.map((c) => {
          if (c.arguments.result_id !== '$LAST_RESULT') return c
          const last = ctx.results('query_data').filter((r) => r.status === 'ok').pop()
          return { ...c, arguments: { ...c.arguments, result_id: String(last?.result_id ?? 'missing') } }
        }),
      }),
  )
  const answer = (req: ModelRequest, ctx: ScriptContext): ScriptStep => {
    draft ??= composeAnswer(q, plan, req, ctx)
    return { content: draft }
  }
  return [...rounds, answer, answer]
}
