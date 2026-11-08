// AX-03: the URL keys each shipped route actually reads, and the one place a link is built.
//
// The key names are the exact keys the page reads (searchParams.get('<key>') in its page.tsx,
// or season / race through useFilters). routeParams.test.ts checks every entry against the page
// source, so a page that stops reading a key fails the test. No model-written URL reaches the
// router: navigate() and cardLink() only emit keys listed here, with values that match the spec.
import { SEASONS, LATEST_SEASON } from '../data/constants'
import { peekManifest } from '../data/manifest'
import type { Card } from '../assistant/cards/card.types'

export type ParamKind = 'season' | 'race' | 'driver' | 'constructor' | 'circuit' | 'compound' | 'enum' | 'int'

export interface ParamSpec {
  kind: ParamKind
  /** Overrides the kind's default pattern (string kinds only). */
  pattern?: RegExp
  /** Allowed values for kind 'enum'. */
  values?: readonly string[]
  /** round_int: the page reads the integer round, so race=2024_8 is written as race=8 plus season=2024. */
  encode?: 'round_int'
  /** Bounds for kind 'int'. */
  min?: number
  max?: number
}

export const FIRST_SEASON: number = SEASONS[0]

/** Latest season a link may name: the manifest's seasons_list when it has loaded, else LATEST_SEASON. */
export function latestSeason(): number {
  const list = peekManifest()?.stats?.seasons_list
  return list && list.length ? Math.max(...list) : LATEST_SEASON
}

export const PATTERNS: Record<Exclude<ParamKind, 'season' | 'enum' | 'int'>, RegExp> = {
  race: /^\d{4}_\d{1,2}$/,
  driver: /^[A-Z]{3}$/,
  constructor: /^[a-z][a-z0-9_]*$/,
  circuit: /^[a-z][a-z0-9_]*$/,
  compound: /^[A-Z]{3,12}$/,
}

const season: ParamSpec = { kind: 'season' }
const race: ParamSpec = { kind: 'race' }
const driver: ParamSpec = { kind: 'driver' }
// Named const: an object key called "constructor" loses contextual typing in a literal.
const constructorId: ParamSpec = { kind: 'constructor' }

/** Route path -> URL key -> spec. Every shipped path has an entry; an empty one takes no parameters. */
export const routeParams: Record<string, Record<string, ParamSpec>> = {
  '/': {},
  '/roadmap': {},
  '/query': {},
  '/ghost-car': {},
  '/ghost-car/standings': {
    circuit: { kind: 'circuit' },
    era: { kind: 'enum', values: ['pre2022', 'post2022'] },
    min: { kind: 'int', min: 1, max: 30 },
  },
  '/ghost-car/championship': { season, constructor: constructorId },
  '/ghost-car/hidden': { season, constructor: constructorId },
  '/lap-decomposition': {},
  '/lap-decomposition/waterfall': { season, race: { kind: 'race', encode: 'round_int' }, driver },
  '/lap-decomposition/race-lost': { season, race, driver },
  '/lap-decomposition/sectors': { season, race },
  '/tyre-strategy': {},
  '/tyre-strategy/survival': { season, race_id: race, compound: { kind: 'compound' } },
  '/tyre-strategy/degradation': { season, race },
  '/tyre-strategy/pit-gantt': { season, race_id: race },
  '/tyre-strategy/recovery': {},
  '/tyre-strategy/party-mode': { season, race },
  '/aero': {},
  '/aero/dirty-air': { season, race },
  '/aero/lap-map': { season, race },
  '/aero/track-evolution': { season, race },
  '/aero/field-pace': { season, race },
  '/race-craft/race-control': { season, race_id: race },
  '/drivers': {},
  '/drivers/ratings-timeline': {},
  '/drivers/consistency': { season },
  '/drivers/quali-vs-race': { season },
  '/drivers/circuit-affinity': {},
  '/drivers/era-translator': { season },
  '/drivers/wet-race': {},
  '/drivers/workload': { season },
  '/drivers/synthetic-teammate': { season },
  '/drivers/corner-skill': { season },
  '/constructors': {},
  '/constructors/structural': { season, race, mode: { kind: 'enum', values: ['race', 'qualifying'] } },
  '/constructors/circuits': {},
  '/constructors/team-averages': { season },
  '/ml': {},
  '/ml/blind-test': { season },
  '/ml/simulator': { season },
  '/ml/metrics': {},
  '/data-quality': { season },
}

/** Keys that are never a URL parameter, whatever a route lists. */
export const DENIED_KEYS = ['sql', 'url', 'query', 'href', 'redirect'] as const

export type ParamValue = string | number
export type LinkResult =
  | { ok: true; url: string }
  | { ok: false; error: string; key?: string; allowed?: string[] }

function asInt(v: ParamValue): number | null {
  if (typeof v === 'number') return Number.isInteger(v) ? v : null
  return /^-?\d+$/.test(v) ? Number(v) : null
}

/** Validate one value; returns the string to put in the URL, or an error message. */
function checkValue(key: string, spec: ParamSpec, v: ParamValue): { ok: true; value: string } | { ok: false; error: string } {
  switch (spec.kind) {
    case 'season': {
      const n = asInt(v)
      const hi = latestSeason()
      if (n === null || n < FIRST_SEASON || n > hi) return { ok: false, error: `"${key}" must be a season ${FIRST_SEASON}-${hi}` }
      return { ok: true, value: String(n) }
    }
    case 'int': {
      const n = asInt(v)
      if (n === null || (spec.min !== undefined && n < spec.min) || (spec.max !== undefined && n > spec.max)) {
        return { ok: false, error: `"${key}" must be an integer ${spec.min ?? '-inf'}-${spec.max ?? 'inf'}` }
      }
      return { ok: true, value: String(n) }
    }
    case 'enum': {
      if (typeof v !== 'string' || !(spec.values ?? []).includes(v)) {
        return { ok: false, error: `"${key}" must be one of ${(spec.values ?? []).join(', ')}` }
      }
      return { ok: true, value: v }
    }
    default: {
      const pattern = spec.pattern ?? PATTERNS[spec.kind]
      if (typeof v !== 'string' || !pattern.test(v)) return { ok: false, error: `"${key}" must match ${pattern}` }
      return { ok: true, value: v }
    }
  }
}

/**
 * Build a URL for a shipped route from validated parameters. Unknown keys, denied keys and bad
 * values are refused with the allowed keys listed. A race key (2024_8) also sets season when the
 * route reads one, so the page's season-scoped race list contains it; a contradicting season is
 * refused.
 */
export function buildRouteUrl(route: string, params: Record<string, unknown> = {}): LinkResult {
  const specs = routeParams[route]
  if (!specs) return { ok: false, error: `No parameter schema for route "${route}"` }
  const allowed = Object.keys(specs)
  const out = new Map<string, string>()
  let raceYear: string | null = null
  for (const [key, raw] of Object.entries(params)) {
    if (raw === undefined || raw === null) continue
    if ((DENIED_KEYS as readonly string[]).includes(key)) {
      return { ok: false, error: `"${key}" is never a URL parameter`, key, allowed }
    }
    const spec = specs[key]
    if (!spec) {
      return {
        ok: false,
        error: `"${key}" is not a parameter of ${route}. Allowed: ${allowed.length ? allowed.join(', ') : '(none)'}`,
        key,
        allowed,
      }
    }
    if (typeof raw !== 'string' && typeof raw !== 'number') {
      return { ok: false, error: `"${key}" must be a string or a number`, key, allowed }
    }
    const r = checkValue(key, spec, raw)
    if (!r.ok) return { ...r, key, allowed }
    if (spec.kind === 'race') {
      const [year, round] = r.value.split('_')
      raceYear = year
      out.set(key, spec.encode === 'round_int' ? String(Number(round)) : r.value)
    } else {
      out.set(key, r.value)
    }
  }
  if (raceYear !== null && specs.season) {
    const given = out.get('season')
    if (given !== undefined && given !== raceYear) {
      return { ok: false, error: `season ${given} contradicts race of ${raceYear}`, key: 'season', allowed }
    }
    if (given === undefined) {
      const s = checkValue('season', specs.season, raceYear)
      if (!s.ok) return { ...s, key: 'season', allowed }
      out.set('season', s.value)
    }
  }
  // Stable order: the route's own key order.
  const qs = new URLSearchParams()
  for (const k of allowed) if (out.has(k)) qs.set(k, out.get(k) as string)
  const s = qs.toString()
  return { ok: true, url: s ? `${route}?${s}` : route }
}

/** The page link for a card, or null when the card has none or it does not validate. */
export function cardLink(card: Pick<Card, 'page' | 'scope'>): string | null {
  const page = card.page
  if (!page) return null
  const specs = routeParams[page.route]
  if (!specs) return null
  // The link must select what the card describes: when the route reads a race or driver key
  // and the card is scoped to one, the params must name that same race or driver.
  for (const [key, spec] of Object.entries(specs)) {
    if (spec.kind === 'race' && card.scope.race_id !== null && page.params[key] !== card.scope.race_id) return null
    if (spec.kind === 'driver' && card.scope.driver_id !== null && page.params[key] !== card.scope.driver_id) return null
  }
  const r = buildRouteUrl(page.route, page.params)
  return r.ok ? r.url : null
}
