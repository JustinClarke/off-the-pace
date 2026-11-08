// AX-10 card store: the read side get_fact_cards, resolveBundle and the page pre-load use.
//
// The published cards are parquet (assistant/cards/<season>.parquet, AX-08). The browser will load
// them through DuckDB-wasm (AX-14); the headless CLI loads them through the AX-04 adapter or from a
// build-cards cards.json. Both feed createCardStore, so the dispatcher never knows where cards came from.
import type { Card } from '../cards/card.types'

export interface CardScopeQuery {
  season?: number
  race_id?: string
  driver_id?: string
  constructor_id?: string
}

export interface CardStore {
  size: number
  byId(id: string): Card | undefined
  has(id: string): boolean
  /** Cards of any of `kinds` whose scope matches every key given (absent keys match anything). Sorted: live before held, then id. */
  find(scope: CardScopeQuery, kinds: readonly string[]): Card[]
  /** Ids starting with `prefix`, sorted. */
  expand(prefix: string): string[]
  /** The driver sharing a constructor with `driver_id` in the race, or null (none, or ambiguous). */
  teammateOf(race_id: string, driver_id: string): string | null
  /** Cards whose page link is `route` and whose page params agree with every param given for keys both carry. */
  onPage(route: string, params: Record<string, string | number>): Card[]
}

const byLiveThenId = (a: Card, b: Card): number => {
  const ha = a.status === 'held' ? 1 : 0
  const hb = b.status === 'held' ? 1 : 0
  return ha - hb || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
}

export function createCardStore(cards: readonly Card[]): CardStore {
  const ids = new Map<string, Card>()
  for (const c of cards) ids.set(c.id, c)
  const sortedIds = [...ids.keys()].sort()
  const byKind = new Map<string, Card[]>()
  const byRoute = new Map<string, Card[]>()
  for (const c of ids.values()) {
    let k = byKind.get(c.kind)
    if (!k) byKind.set(c.kind, (k = []))
    k.push(c)
    const route = c.page?.route
    if (route) {
      let r = byRoute.get(route)
      if (!r) byRoute.set(route, (r = []))
      r.push(c)
    }
  }
  const teammateCache = new Map<string, string | null>()

  function lowerBound(prefix: string): number {
    let lo = 0
    let hi = sortedIds.length
    while (lo < hi) {
      const mid = (lo + hi) >> 1
      if (sortedIds[mid] < prefix) lo = mid + 1
      else hi = mid
    }
    return lo
  }

  return {
    size: ids.size,
    byId: (id) => ids.get(id),
    has: (id) => ids.has(id),
    find(scope, kinds) {
      const out: Card[] = []
      for (const kind of kinds) {
        for (const c of byKind.get(kind) ?? []) {
          const s = c.scope
          if (scope.season !== undefined && s.season !== scope.season) continue
          if (scope.race_id !== undefined && s.race_id !== scope.race_id) continue
          if (scope.driver_id !== undefined && s.driver_id !== scope.driver_id) continue
          if (scope.constructor_id !== undefined && s.constructor_id !== scope.constructor_id) continue
          out.push(c)
        }
      }
      return out.sort(byLiveThenId)
    },
    expand(prefix) {
      const out: string[] = []
      for (let i = lowerBound(prefix); i < sortedIds.length && sortedIds[i].startsWith(prefix); i++) out.push(sortedIds[i])
      return out
    },
    teammateOf(race_id, driver_id) {
      const key = `${race_id}:${driver_id}`
      if (teammateCache.has(key)) return teammateCache.get(key) ?? null
      let found: string | null = null
      // 1. The race.teammate_gap card names the teammate in its display ("... vs PER (median of 46 paired laps)").
      const gap = ids.get(`race.teammate_gap:${race_id}:${driver_id}`)
      // 0. AX-10b: the policy field set from the mart column wins.
      const field = gap?.policy_fields?.teammate_id
      if (typeof field === 'string' && field) found = field
      // 1. Fallback: older cards without the field name the teammate in the display ("... vs PER (median of 46 paired laps)").
      const m = !found && gap?.display ? /\bvs ([A-Z0-9]{2,4})\b/.exec(gap.display) : null
      if (m) found = m[1]
      // 2. Otherwise: the one other driver with the same constructor in this race's results.
      if (!found) {
        const mine = ids.get(`race.result:${race_id}:${driver_id}`)?.scope.constructor_id
        if (mine) {
          const mates = (byKind.get('race.result') ?? [])
            .filter((c) => c.scope.race_id === race_id && c.scope.constructor_id === mine && c.scope.driver_id && c.scope.driver_id !== driver_id)
            .map((c) => c.scope.driver_id as string)
          if (mates.length === 1) found = mates[0]
        }
      }
      teammateCache.set(key, found)
      return found
    },
    onPage(route, params) {
      const out: { c: Card; hits: number }[] = []
      for (const c of byRoute.get(route) ?? []) {
        const pp = (c.page?.params ?? {}) as Record<string, unknown>
        let ok = true
        let hits = 0
        for (const [k, v] of Object.entries(params)) {
          if (!(k in pp)) continue
          if (String(pp[k]) !== String(v)) {
            ok = false
            break
          }
          hits++
        }
        if (ok) out.push({ c, hits })
      }
      // Cards tied to these exact params; page-wide cards (pooled rates) only when none is. Live before held.
      const top = out.reduce((m, x) => Math.max(m, x.hits), 0)
      return out
        .filter((x) => x.hits === top)
        .sort((a, b) => byLiveThenId(a.c, b.c))
        .map((x) => x.c)
    },
  }
}

const json = <T>(v: unknown, fallback: T): T => {
  if (v === null || v === undefined) return fallback
  if (typeof v !== 'string') return v as T
  try {
    return JSON.parse(v) as T
  } catch {
    return fallback
  }
}

/** One row of the assistant_cards parquet (card.schema.json $comment) back to a Card. */
export function cardFromParquetRow(r: Record<string, unknown>): Card {
  const hasInterval = r.interval_kind !== null && r.interval_kind !== undefined
  const num = (v: unknown): number | null => (v === null || v === undefined ? null : Number(v))
  return {
    id: String(r.id),
    kind: String(r.kind),
    metric: String(r.metric),
    label: r.label,
    value: json<Card['value']>(r.value, null),
    unit: (r.unit as string | null) ?? null,
    display: (r.display as string | null) ?? null,
    unavailable_reason: (r.unavailable_reason as string | null) ?? null,
    n: { count: Number(r.n_count ?? 0), unit: r.n_unit },
    interval: hasInterval
      ? {
          low: num(r.interval_low),
          high: num(r.interval_high),
          level: num(r.interval_level),
          source_columns: json<string[]>(r.interval_source_columns, []),
          kind: r.interval_kind,
        }
      : null,
    sample: r.sample,
    grade: (r.grade as string | null) ?? null,
    status: r.status,
    held_reason: (r.held_reason as string | null) ?? null,
    scope: json(r.scope, {}),
    source: json(r.source, {}),
    versions: json(r.versions, {}),
    page: json(r.page, null),
    caveats: json<string[]>(r.caveats, []),
    policy_fields: json(r.policy_fields, {}),
  } as unknown as Card
}
