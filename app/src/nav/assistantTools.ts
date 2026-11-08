// Read-only navigation and page-explainer tools for the assistant (AI-10).
//   navigate(route, params?)   v2 (AX-03): shipped routes only; each key and value validated
//                              against routeParams.ts (the keys the page really reads)
//   explainPage(pageId)        pre-cut docs summary (<= 800 tokens), generated at build time
import { routes } from './routes'
import { buildRouteUrl, routeParams } from './routeParams'
import type { LinkResult } from './routeParams'
import generated from './pageSummaries.generated.json'

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
  '/constructors/team-averages': 'constructors',
  '/ml': 'families/the-machine',
  '/ml/blind-test': 'blind-test-scoreboard',
  '/ml/simulator': 'degradation-simulator',
  '/ml/metrics': 'model-metrics',
  '/query': 'query-lab',
  '/data-quality': 'data-quality-audit',
}

export type NavResult = LinkResult

/**
 * Read-only: returns a URL for a shipped route, never navigates. Values may be strings or
 * numbers; every key must be one the route's page reads (routeParams.ts), and every value must
 * match its pattern. Errors list the allowed keys.
 */
export function navigate(route: string, params: Record<string, unknown> = {}): NavResult {
  if (!shippedPaths.includes(route)) {
    return { ok: false, error: `Unknown or unshipped route "${route}". Shipped routes: ${shippedPaths.join(', ')}` }
  }
  if (!routeParams[route]) return { ok: false, error: `Route "${route}" has no parameter schema` }
  return buildRouteUrl(route, params)
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
