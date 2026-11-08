// AX-10 dispatcher: dispatch(call) -> ToolResult for the seven tools (AD2). Arguments are validated
// against the generated tool schemas first; an unknown tool, bad arguments or a refused call comes back
// as a ToolResult {status:'error', reason, allowed}. dispatch never throws to the model.
//
// Wiring (design 2.4/2.5, AX-10 spec step 1):
//   get_fact_cards   -> the card store; its `bundle` argument -> resolveBundle (AX-21), held stubs included
//   query_data       -> the AX-06 bounded builder only (injected as deps.queryData; never runLabQuery)
//   list_values      -> AX-02 (session cache here: a repeated query is not looked up twice)
//   compare_lap_times, make_chart -> AX-11 functions. make_chart takes {result_id, kind}: the dispatcher
//                      builds the chart spec from that result, so the model never writes one.
//   navigate, explain_page -> nav/assistantTools.ts
//
// No SQL, chart code or URL is built from model text here: SQL comes from the builder's catalogue
// compile, chart specs from stored results, URLs from routeParams.
import type { Card } from '../cards/card.types'
import { toModelProjection } from '../cards/project'
import { bundleTypes, resolveBundle, BUNDLE_MAX_CARDS } from '../prompt/bundles'
import { explainPage, explainablePageIds, navigate } from '../../nav/assistantTools'
import { makeChart as defaultMakeChart, type MakeChartResult } from '../charts/makeChart'
import type { CompareResult } from '../charts/compareLapTimes'
import type { ListValuesInput, ListValuesResult } from '../listValues'
import { getResult, rememberResult } from '../queryBuilder/store'
import type { QueryOutcome, QueryResult } from '../queryBuilder/types'
import type { CardStore, CardScopeQuery } from './cardStore'
import type { ToolCall, ToolResult } from './types'
import { validateArgs, type ToolDef } from './validateArgs'

export const TOOL_NAMES = ['get_fact_cards', 'query_data', 'list_values', 'compare_lap_times', 'make_chart', 'explain_page', 'navigate'] as const
export type ToolName = (typeof TOOL_NAMES)[number]

export interface KindInfo {
  kind: string
  /** Why every card of this kind is held, or null when the kind is live. */
  held_reason: string | null
}

export interface DispatcherDeps {
  /** The generated tool schemas (worker/src/generated/tools.ts TOOLS, the same ones the Worker sends). */
  tools: readonly ToolDef[]
  cards: CardStore
  listValues(input: ListValuesInput): Promise<ListValuesResult>
  queryData(req: unknown): Promise<QueryOutcome>
  /** AX-11. Absent: the tool answers not_available_yet. */
  compareLapTimes?(a: string, b: string, raceId: string): Promise<CompareResult>
  makeChart?(spec: unknown): MakeChartResult
  /** Registry kinds and their held reasons, for the "held card" refusal. Optional. */
  kinds?: readonly KindInfo[]
}

/** What the dispatcher saw this session; the loop feeds it to the checker and the grounding check. */
export interface SessionRecord {
  /** Full cards returned to the model, by id. */
  cards: Map<string, Card>
  queryResults: QueryResult[]
  chartIds: string[]
  links: string[]
  listValuesCacheHits: number
  listValuesLookups: number
}

export interface Dispatcher {
  dispatch(call: ToolCall): Promise<ToolResult>
  session: SessionRecord
}

const err = (reason: string, allowed?: unknown): ToolResult => ({ status: 'error', reason, ...(allowed !== undefined ? { allowed } : {}) })

function seasonOf(raceId: string | undefined): number | undefined {
  const m = raceId ? /^(\d{4})_\d{1,2}$/.exec(raceId) : null
  return m ? Number(m[1]) : undefined
}

export function createDispatcher(deps: DispatcherDeps): Dispatcher {
  const defs = new Map(deps.tools.map((t) => [t.function.name, t]))
  const kindInfo = new Map((deps.kinds ?? []).map((k) => [k.kind, k]))
  const session: SessionRecord = { cards: new Map(), queryResults: [], chartIds: [], links: [], listValuesCacheHits: 0, listValuesLookups: 0 }
  const listCache = new Map<string, ListValuesResult>()
  const make = deps.makeChart ?? defaultMakeChart

  function projectCards(cards: Card[]): ToolResult {
    for (const c of cards) session.cards.set(c.id, c)
    return { status: 'ok', cards: cards.map(toModelProjection) }
  }

  function getFactCards(a: { scopes?: CardScopeQuery[]; kinds?: string[]; bundle?: string }): ToolResult {
    const picked: Card[] = []
    const seen = new Set<string>()
    const take = (c: Card | undefined) => {
      if (c && !seen.has(c.id)) {
        seen.add(c.id)
        picked.push(c)
      }
    }
    const held: { kind: string; held_reason: string }[] = []
    let missing: string[] = []
    let bundleNote: string | undefined

    if (a.bundle) {
      if (!bundleTypes().includes(a.bundle)) return err(`"${a.bundle}" has no card recipe`, bundleTypes())
      const s = a.scopes?.[0] ?? {}
      const scope = { ...s, season: s.season ?? seasonOf(s.race_id) }
      const r = resolveBundle(a.bundle, scope, {
        expand: (p) => deps.cards.expand(p),
        has: (id) => deps.cards.has(id),
        teammateOf: (race, driver) => deps.cards.teammateOf(race, driver),
      })
      for (const id of r.ids) take(deps.cards.byId(id))
      held.push(...r.held)
      missing = r.missing_scope
      if (r.dropped.length) bundleNote = `${r.dropped.length} optional card(s) left out by the ${BUNDLE_MAX_CARDS}-card cap`
      if (picked.length === 0 && missing.length) {
        return err('scope_incomplete', { needs: 'the scope keys the recipe uses (race_id, driver_id; season for season recipes)', missing })
      }
    }

    if (a.kinds?.length) {
      if (!a.scopes?.length) return err('scopes_required: give at least one scope (season, race_id, driver_id or constructor_id) with kinds')
      for (const sc of a.scopes) for (const c of deps.cards.find(sc, a.kinds)) take(c)
      for (const kind of a.kinds) {
        const info = kindInfo.get(kind)
        if (info?.held_reason && !picked.some((c) => c.kind === kind)) held.push({ kind, held_reason: info.held_reason })
      }
    }

    if (!a.bundle && !a.kinds?.length) return err('give kinds (with scopes) or a bundle')

    const total = picked.length
    const shown = picked.slice(0, BUNDLE_MAX_CARDS)
    if (shown.length === 0) {
      if (held.length) return { status: 'error', reason: 'held', held, allowed: 'No value is published for these yet. Give the held reason in plain words and the page link; no estimate.' }
      return { status: 'no_data', reason: 'no card matches that scope' }
    }
    const out = projectCards(shown)
    if (held.length) out.held = held
    if (total > shown.length) out.cards_dropped = total - shown.length
    if (missing.length) out.missing_scope = missing
    if (bundleNote) out.note = bundleNote
    return out
  }

  async function listValues(a: ListValuesInput): Promise<ToolResult> {
    const key = JSON.stringify([a.domain, (a.query ?? '').toLowerCase().trim(), a.season ?? null, a.limit ?? null])
    const hit = listCache.get(key)
    if (hit) {
      session.listValuesCacheHits++
      return { ...hit, cached: true }
    }
    session.listValuesLookups++
    const r = await deps.listValues(a)
    listCache.set(key, r)
    return { ...r }
  }

  async function queryData(a: unknown): Promise<ToolResult> {
    const out = await deps.queryData(a)
    if (out.status === 'ok') {
      rememberResult(out)
      session.queryResults.push(out)
      return { ...out }
    }
    if (out.status === 'no_data') return { status: 'no_data', reason: out.reason, view: out.view }
    return { status: 'error', reason: `${out.code}: ${out.message}`, field: out.field, ...(out.allowed ? { allowed: out.allowed } : {}) }
  }

  function chart(a: { result_id: string; kind?: 'line' | 'bar' | 'scatter' }): ToolResult {
    const r = getResult(a.result_id)
    if (!r) return err('result_id is not a query_data result from this session; call query_data first')
    const x = r.group_by[0]
    if (!x) return err('that result has no group_by column to put on the x axis; query with group_by first')
    const numericX = r.rows.every((row) => typeof row[x] === 'number')
    const type = a.kind ?? (numericX ? 'line' : 'bar')
    const label = `${r.aggregate.fn} of ${r.aggregate.col}`.slice(0, 80)
    const out = make({
      type,
      title: `${r.view}: ${label} by ${x}`.slice(0, 80),
      x: { col: x, label: x.replace(/_/g, ' ').slice(0, 80) },
      y: { col: 'value', label },
      series: [{ result_id: r.result_id, label: label.slice(0, 80), x_col: x, y_col: 'value' }],
    })
    if (out.status === 'ok') session.chartIds.push(out.chart_id)
    return { ...out }
  }

  async function run(name: string, args: Record<string, unknown>): Promise<ToolResult> {
    switch (name as ToolName) {
      case 'get_fact_cards':
        return getFactCards(args as Parameters<typeof getFactCards>[0])
      case 'query_data':
        return queryData(args)
      case 'list_values':
        return listValues(args as unknown as ListValuesInput)
      case 'compare_lap_times': {
        if (!deps.compareLapTimes) return err('not_available_yet')
        const r = await deps.compareLapTimes(String(args.driver_a), String(args.driver_b), String(args.race_id))
        if (r.status === 'ok') session.chartIds.push(r.chart_id)
        return { ...r }
      }
      case 'make_chart':
        return chart(args as { result_id: string; kind?: 'line' | 'bar' | 'scatter' })
      case 'explain_page': {
        const r = explainPage(String(args.page))
        return r.ok
          ? { status: 'ok', page_id: r.pageId, title: r.title, summary: r.summary }
          : err(`No summary for "${String(args.page)}"`, explainablePageIds)
      }
      case 'navigate': {
        const r = navigate(String(args.route), (args.params as Record<string, unknown> | undefined) ?? {})
        if (r.ok) {
          session.links.push(r.url)
          return { status: 'ok', url: r.url }
        }
        return err(r.error, r.allowed)
      }
      default:
        return err('unknown tool', [...TOOL_NAMES])
    }
  }

  return {
    session,
    async dispatch(call) {
      const def = defs.get(call.name)
      if (!def || !(TOOL_NAMES as readonly string[]).includes(call.name)) return err('unknown tool', [...TOOL_NAMES])
      const bad = validateArgs(def, call.arguments)
      if (bad) return err(bad.reason, bad.allowed)
      try {
        return await run(call.name, call.arguments as Record<string, unknown>)
      } catch (e) {
        return err(`tool_failed: ${e instanceof Error ? e.message.slice(0, 120) : 'error'}`)
      }
    },
  }
}
