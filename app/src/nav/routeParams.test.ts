// AX-03: every shipped route has a parameter schema whose keys its page really reads; values are
// validated; encodings round-trip; cardLink never guesses.
import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join, dirname, resolve } from 'node:path'
import { shippedPaths } from './assistantTools'
import { routeParams, buildRouteUrl, cardLink, latestSeason, FIRST_SEASON } from './routeParams'
import { intParam } from '../state/urlParams'
import { makeCard } from '../assistant/cards/card.fixture'

const SRC = join(import.meta.dirname, '..')
const appSrc = readFileSync(join(SRC, 'App.tsx'), 'utf8')
const lazyImports = new Map(
  [...appSrc.matchAll(/path:\s*'([^']+)',\s*element:\s*lazyRoute\(\(\) => import\('([^']+)'\)\)/g)].map((m) => [m[1], m[2]]),
)
// Routes rendered inline (not lazy) in App.tsx.
const INLINE: Record<string, string> = { '/': 'routes/home/index.tsx' }

function resolveModule(base: string): string | null {
  for (const c of [`${base}.tsx`, `${base}.ts`, join(base, 'index.tsx'), join(base, 'index.ts')]) if (existsSync(c)) return c
  return null
}

/** The route's module plus every file it re-exports its default from, ending at the page. */
function pageFiles(route: string): string[] {
  const first = lazyImports.has(route) ? resolveModule(resolve(SRC, lazyImports.get(route) as string)) : join(SRC, INLINE[route] ?? '')
  if (!first || !existsSync(first)) throw new Error(`cannot resolve the page for ${route}`)
  const files = [first]
  for (;;) {
    const m = readFileSync(files[files.length - 1], 'utf8').match(/export \{ default \} from '([^']+)'/)
    if (!m) return files
    const next = resolveModule(resolve(dirname(files[files.length - 1]), m[1]))
    if (!next) return files
    files.push(next)
  }
}

describe('AX-03 routeParams coverage', () => {
  it('has an entry for every shipped path and none for anything else', () => {
    expect(Object.keys(routeParams).sort()).toEqual([...shippedPaths].sort())
  })

  it.each([...shippedPaths])('%s: every key is read by the page', (route) => {
    const src = pageFiles(route)
      .map((f) => readFileSync(f, 'utf8'))
      .join('\n')
    for (const [key, spec] of Object.entries(routeParams[route])) {
      const viaFilters =
        (key === 'season' && /\{[^}]*\bseason\b[^}]*\}\s*=\s*useFilters\(\)/.test(src)) ||
        (key === 'race' && spec.encode === 'round_int' && /\{[^}]*\braceId\b[^}]*\}\s*=\s*useFilters\(\)/.test(src))
      const viaGet = src.includes(`searchParams.get('${key}')`)
      expect(viaFilters || viaGet, `${route} lists "${key}" but its page does not read it`).toBe(true)
    }
  })

  it('lists every searchParams key a routed page reads', () => {
    for (const route of shippedPaths) {
      const src = pageFiles(route)
        .map((f) => readFileSync(f, 'utf8'))
        .join('\n')
      for (const m of src.matchAll(/searchParams\.get\('([a-z_]+)'\)/g)) {
        expect(Object.keys(routeParams[route]), `${route} reads ${m[1]}`).toContain(m[1])
      }
    }
  })
})

describe('AX-03 buildRouteUrl', () => {
  it('encodes the waterfall race as an integer round plus season, and round-trips', () => {
    const r = buildRouteUrl('/lap-decomposition/waterfall', { race: '2024_8', driver: 'LEC' })
    expect(r).toEqual({ ok: true, url: '/lap-decomposition/waterfall?season=2024&race=8&driver=LEC' })
    if (!r.ok) return
    const q = new URLSearchParams(r.url.split('?')[1])
    // What the page does with it: FilterContext reads season and race as integers.
    expect(`${intParam(q.get('season'))}_${intParam(q.get('race'))}`).toBe('2024_8')
  })

  it('keeps string race keys as written and adds the season they belong to', () => {
    expect(buildRouteUrl('/lap-decomposition/race-lost', { race: '2024_8', driver: 'LEC' })).toEqual({
      ok: true,
      url: '/lap-decomposition/race-lost?season=2024&race=2024_8&driver=LEC',
    })
    expect(buildRouteUrl('/tyre-strategy/survival', { race_id: '2023_12', compound: 'SOFT' })).toEqual({
      ok: true,
      url: '/tyre-strategy/survival?season=2023&race_id=2023_12&compound=SOFT',
    })
  })

  it('emits exactly the five links e2e/card-links.e2e.ts opens', () => {
    const url = (route: string, p: Record<string, string>) => {
      const r = buildRouteUrl(route, p)
      return r.ok ? r.url : r.error
    }
    expect(url('/lap-decomposition/race-lost', { race: '2024_8', driver: 'LEC' })).toBe('/lap-decomposition/race-lost?season=2024&race=2024_8&driver=LEC')
    expect(url('/lap-decomposition/waterfall', { race: '2024_8', driver: 'LEC' })).toBe('/lap-decomposition/waterfall?season=2024&race=8&driver=LEC')
    expect(url('/tyre-strategy/pit-gantt', { race_id: '2024_8' })).toBe('/tyre-strategy/pit-gantt?season=2024&race_id=2024_8')
    expect(url('/tyre-strategy/degradation', { race: '2024_8' })).toBe('/tyre-strategy/degradation?season=2024&race=2024_8')
    expect(url('/tyre-strategy/survival', { race_id: '2024_8', compound: 'MEDIUM' })).toBe('/tyre-strategy/survival?season=2024&race_id=2024_8&compound=MEDIUM')
  })

  it('refuses bad values', () => {
    const bad: [string, Record<string, unknown>][] = [
      ['/lap-decomposition/race-lost', { race: '2024-8' }],
      ['/lap-decomposition/race-lost', { race: 2024 }],
      ['/lap-decomposition/race-lost', { driver: 'lec' }],
      ['/lap-decomposition/race-lost', { driver: 'LECL' }],
      ['/lap-decomposition/race-lost', { season: 2017 }],
      ['/lap-decomposition/race-lost', { season: latestSeason() + 1 }],
      ['/lap-decomposition/race-lost', { season: 2024.5 }],
      ['/lap-decomposition/race-lost', { season: 2023, race: '2024_8' }],
      ['/constructors/structural', { mode: 'sprint' }],
      ['/ghost-car/standings', { min: 0 }],
      ['/ghost-car/standings', { circuit: 'Monaco<script>' }],
      ['/ghost-car/championship', { constructor: 'Red Bull' }],
      ['/drivers/ratings-timeline', { season: 2024 }],
      ['/tyre-strategy/pit-gantt', { race_id: { toString: () => '2024_8' } }],
      ['/not-a-route', {}],
    ]
    for (const [route, params] of bad) expect(buildRouteUrl(route, params).ok, `${route} ${JSON.stringify(params)}`).toBe(false)
  })

  it('accepts the season range ends', () => {
    expect(buildRouteUrl('/drivers/consistency', { season: FIRST_SEASON }).ok).toBe(true)
    expect(buildRouteUrl('/drivers/consistency', { season: latestSeason() }).ok).toBe(true)
  })
})

describe('AX-03 cardLink', () => {
  const raceLostCard = makeCard({
    scope: { ...makeCard().scope, race_id: '2024_8', driver_id: 'LEC' },
    page: { route: '/lap-decomposition/race-lost', params: { race: '2024_8', driver: 'LEC' }, docs_slug: 'race-lost' },
  })

  it('maps a card to its validated page URL', () => {
    expect(cardLink(raceLostCard)).toBe('/lap-decomposition/race-lost?season=2024&race=2024_8&driver=LEC')
  })

  it('returns null for a bad param, a missing page, an unknown route, or a link to another race or driver', () => {
    const with_ = (params: Record<string, string | number>, route = '/lap-decomposition/race-lost') =>
      cardLink({ ...raceLostCard, page: { route, params, docs_slug: null } })
    expect(with_({ race: '2024_8', driver: 'lec' })).toBeNull()
    expect(with_({ race: '2024_8', driver: 'LEC', sql: 'x' })).toBeNull()
    expect(with_({ race: '2024_9', driver: 'LEC' })).toBeNull()
    expect(with_({ race: '2024_8', driver: 'VER' })).toBeNull()
    expect(with_({ race: '2024_8' })).toBeNull()
    expect(with_({}, '/nope')).toBeNull()
    expect(cardLink({ ...raceLostCard, page: null })).toBeNull()
  })
})

describe('AX-03 FilterContext integer parsing', () => {
  it('reads string ids as null, never NaN', () => {
    expect(intParam('2024_8')).toBeNull()
    expect(intParam('LEC')).toBeNull()
    expect(intParam(null)).toBeNull()
    expect(intParam('8')).toBe(8)
  })
})
