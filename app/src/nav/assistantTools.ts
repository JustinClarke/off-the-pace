// Read-only navigation and page-explainer tools for the assistant (AI-10).
//   navigate(route, filters?)  validated against the app's own route table, shipped routes only
//   explainPage(pageId)        pre-cut docs summary (<= 800 tokens), generated at build time
import { routes } from './routes'
import generated from './pageSummaries.generated.json'

/** The only URL filters the app reads (see state/FilterContext.tsx). All are integers. */
export const ALLOWED_FILTERS = ['season', 'race', 'driver', 'constructor'] as const
export type FilterKey = (typeof ALLOWED_FILTERS)[number]
export type NavFilters = Partial<Record<FilterKey, number>>

/** Shipped routes with a concrete path. Dynamic routes (":param") are excluded: nothing resolves them. */
/** Table-shipped routes that the built app renders as a "coming soon" stub: never navigable. */
const STUB_ROUTES: readonly string[] = ['/race-craft']
export const shippedRoutes = routes.filter(
  (r) => r.shipped !== false && !r.path.includes(':') && !STUB_ROUTES.includes(r.path),
)
export const shippedPaths: readonly string[] = shippedRoutes.map((r) => r.path)

/** Route path to the docs/app slug that explains it. Pillar roots map to their family page. */
export const routeToPageId: Record<string, string> = {
  '/': 'overview',
  '/ghost-car': 'families/ghost-car',
  '/ghost-car/standings': 'ghost-race-standings',
  '/ghost-car/championship': 'counterfactual-championship',
  '/ghost-car/hidden': 'hidden-performance',
  '/lap-decomposition': 'families/lap-decomposition',
  '/lap-decomposition/waterfall': 'lap-waterfall',
  '/lap-decomposition/race-lost': 'race-lost',
  '/lap-decomposition/sectors': 'sector-decomposition',
  '/tyre-strategy': 'families/tyre-strategy',
  '/tyre-strategy/survival': 'tyre-cliff-survival',
  '/tyre-strategy/degradation': 'stint-degradation-timeline',
  '/tyre-strategy/pit-gantt': 'pit-strategy',
  '/tyre-strategy/recovery': 'tyre-recovery-forecast',
  '/tyre-strategy/party-mode': 'party-mode',
  '/aero': 'families/aero-conditions',
  '/aero/dirty-air': 'dirty-air-cost',
  '/aero/lap-map': 'dirty-air-lap-map',
  '/aero/track-evolution': 'track-evolution',
  '/aero/field-pace': 'field-pace-curve',
  '/race-craft/race-control': 'race-control',
  '/drivers': 'families/drivers',
  '/drivers/ratings-timeline': 'era-ratings-timeline',
  '/drivers/consistency': 'driver-consistency',
  '/drivers/quali-vs-race': 'quali-vs-race-skill',
  '/drivers/circuit-affinity': 'driver-circuit-affinity',
  '/drivers/era-translator': 'era-translator',
  '/drivers/wet-race': 'wet-race-specialist',
  '/drivers/workload': 'driver-workload',
  '/drivers/synthetic-teammate': 'synthetic-teammate',
  '/drivers/corner-skill': 'corner-phase-skill',
  '/constructors': 'families/constructors',
  '/constructors/structural': 'constructor-structural-pace',
  '/constructors/circuits': 'constructor-circuit-interaction',
  '/ml': 'families/the-machine',
  '/ml/blind-test': 'blind-test-scoreboard',
  '/ml/simulator': 'degradation-simulator',
  '/ml/metrics': 'model-metrics',
  '/query': 'query-lab',
  '/data-quality': 'data-quality-audit',
}

export type NavResult = { ok: true; url: string } | { ok: false; error: string }

export function navigate(route: string, filters: Record<string, unknown> = {}): NavResult {
  if (!shippedPaths.includes(route)) {
    return { ok: false, error: `Unknown or unshipped route "${route}". Shipped routes: ${shippedPaths.join(', ')}` }
  }
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(filters)) {
    if (!(ALLOWED_FILTERS as readonly string[]).includes(k)) {
      return { ok: false, error: `Filter "${k}" is not allowed. Allowed: ${ALLOWED_FILTERS.join(', ')}` }
    }
    if (typeof v !== 'number' || !Number.isInteger(v)) {
      return { ok: false, error: `Filter "${k}" must be an integer` }
    }
    params.set(k, String(v))
  }
  const qs = params.toString()
  return { ok: true, url: qs ? `${route}?${qs}` : route }
}

export type ExplainResult =
  | { ok: true; pageId: string; title: string; summary: string; tokens: number }
  | { ok: false; error: string }

const pages = generated.pages as Record<string, { title: string; summary: string; tokens: number }>

/** pageId is a docs slug, or a shipped route path (resolved through routeToPageId). */
export function explainPage(pageId: string): ExplainResult {
  const id = routeToPageId[pageId] ?? pageId
  const p = pages[id]
  if (!p) return { ok: false, error: `No summary for "${pageId}". Known pages: ${Object.keys(pages).join(', ')}` }
  return { ok: true, pageId: id, title: p.title, summary: p.summary, tokens: p.tokens }
}

export const explainablePageIds: readonly string[] = Object.keys(pages)
