// AX-10 page-card pre-load (design 2.4): on a new question, read the current route and params, ask
// the registry for the card ids the page shows (onScreen, at most 6) and put their projections in the
// page-context slot. A question about the number on screen then needs 0 tool calls.
//
// Two sources, in order: each registry spec whose route is the current route (spec.onScreen), then the
// cards whose own page link names this route and agrees with the params (store.onPage). Ids not in the
// store are dropped, so a stub registry or a partial store never yields a phantom card.
import type { Card } from '../cards/card.types'
import { toModelProjection } from '../cards/project'
import { tokensOf, SLOTS } from './budget'
import type { CardStore } from './cardStore'

export const MAX_ON_SCREEN = 6

export interface PageContext {
  route: string
  params: Record<string, string | number>
}

/** The part of a registry spec the pre-load uses. */
export interface OnScreenSpec {
  route: string | null
  onScreen(params: never): string[]
}

export interface Preload {
  cards: Card[]
  /** The page-context block for the model, '' when no page is open. */
  text: string
  ids: string[]
}

/** Route params (season, race, race_id, driver, constructor ...) as the card scope keys. */
export function scopeFromRoute(params: Record<string, string | number>): Record<string, string | number> {
  const out: Record<string, string | number> = { ...params }
  const season = params.season !== undefined ? Number(params.season) : undefined
  if (season !== undefined && Number.isFinite(season)) out.season = season
  const race = params.race_id ?? params.race
  if (race !== undefined) {
    const r = String(race)
    out.race_id = /^\d{4}_\d{1,2}$/.test(r) ? r : season !== undefined && /^\d{1,2}$/.test(r) ? `${season}_${Number(r)}` : r
  }
  if (params.driver !== undefined && out.driver_id === undefined) out.driver_id = String(params.driver)
  if (params.constructor !== undefined && out.constructor_id === undefined) out.constructor_id = String(params.constructor)
  return out
}

export function preloadPageCards(store: CardStore, page: PageContext | null | undefined, specs: readonly OnScreenSpec[] = []): Preload {
  if (!page) return { cards: [], text: '', ids: [] }
  const scope = scopeFromRoute(page.params)
  const ids: string[] = []
  const add = (id: string) => {
    if (!ids.includes(id) && store.has(id)) ids.push(id)
  }
  for (const spec of specs) {
    if (spec.route !== page.route) continue
    try {
      for (const id of (spec.onScreen as (p: unknown) => string[])(scope)) add(id)
    } catch {
      /* the spec needs a param this page did not give: nothing on screen from it */
    }
  }
  for (const c of store.onPage(page.route, scope)) add(c.id)
  const capped = ids.slice(0, MAX_ON_SCREEN)
  const cards = capped.map((id) => store.byId(id) as Card)
  // Fit the page-context slot: drop trailing cards until the block is within 600 tokens.
  const build = (cs: Card[]) =>
    `Current page: ${page.route} ${JSON.stringify(page.params)}\n` +
    (cs.length ? `On-screen cards (the numbers the user can see; cite by id):\n${cs.map((c) => JSON.stringify(toModelProjection(c))).join('\n')}` : 'No fact card is tied to what is on screen.')
  let use = cards
  let text = build(use)
  while (use.length > 0 && tokensOf(text) > SLOTS.page_context) {
    use = use.slice(0, -1)
    text = build(use)
  }
  return { cards: use, text, ids: use.map((c) => c.id) }
}
