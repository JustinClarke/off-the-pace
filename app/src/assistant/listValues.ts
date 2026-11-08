// AX-02 list_values: resolve names, nicknames and ids to the codes the data uses.
// Pure matcher (listValuesFromRows) plus a loader over the published assistant_entities table.
// Never guesses: an ambiguous query returns every candidate, an empty one returns { status: 'no_data' }.
import { loadManifest, getTablePath } from '../data/manifest'
import { registerParquet } from '../data/duckdb/register'
import { rawQuery } from '../data/hooks/useQuery'

export type ListDomain =
  | 'driver' | 'constructor' | 'race' | 'circuit' | 'season' | 'compound'
  | 'caution_status' | 'stint_end_cause' | 'card_kind' | 'page' | 'columns'

export interface EntityRow {
  domain: string
  code: string
  display: string
  aliases: string[]
  seasons: number[]
  parent_code: string | null
  extra: Record<string, unknown>
}

export interface ListValuesInput {
  domain: ListDomain
  query?: string
  season?: number
  limit?: number
}

export interface ListValuesRow {
  code: string
  display: string
  aliases_matched: string[]
  /** Compact season ranges, e.g. "2018-2024" or "2018-2020,2022". */
  seasons: string
}

export type ListValuesResult =
  | { status: 'ok'; rows: ListValuesRow[]; note?: string }
  | { status: 'no_data'; rows: []; note?: string }

export const MAX_ROWS = 20
export const MAX_TOKENS = 400

/** Same formula as estimateTokens in nav/pageSummaries.mjs (that module imports node:fs, so it is not bundled). */
const tokensOf = (text: string): number => Math.ceil(text.length / 3.5)

/** Lowercase, strip accents and punctuation, collapse spaces. */
export function normalise(s: string): string {
  return s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
}

export function compactSeasons(seasons: number[]): string {
  const s = [...new Set(seasons)].sort((a, b) => a - b)
  const out: string[] = []
  for (let i = 0; i < s.length; ) {
    let j = i
    while (j + 1 < s.length && s[j + 1] === s[j] + 1) j++
    out.push(j > i ? `${s[i]}-${s[j]}` : `${s[i]}`)
    i = j + 1
  }
  return out.join(',')
}

/** Providers for domains whose values are registered elsewhere (AX-05 columns, AX-04 card kinds). */
export type Provider = () => Array<{ code: string; display: string; aliases?: string[] }>
const providers: Partial<Record<ListDomain, Provider>> = {}
export function registerListProvider(domain: 'columns' | 'card_kind', fn: Provider): void {
  providers[domain] = fn
  cache.clear()
}

const YEAR = /\b(19|20)\d{2}\b/

interface Scored { row: EntityRow; tier: number; score: number; matched: string[] }

function score(row: EntityRow, q: string, qFull: string): Scored | null {
  const names = [row.display, ...row.aliases].filter(Boolean)
  const norm = names.map(normalise)
  const code = normalise(row.code)
  if (code === q || code === qFull) return { row, tier: 0, score: 1, matched: [row.code] }
  const exact = names.filter((_, i) => norm[i] === q)
  if (exact.length) return { row, tier: 1, score: 1, matched: exact.slice(0, 3) }
  if (q.length >= 2) {
    const pre = names.filter((_, i) => norm[i].startsWith(q))
    if (pre.length) return { row, tier: 2, score: 1, matched: pre.slice(0, 3) }
  }
  const qt = q.split(' ').filter(Boolean)
  const rowTokens = new Set(norm.flatMap(n => n.split(' ')).concat(code.split(' ')))
  const hit = qt.filter(t => rowTokens.has(t) || (t.length >= 3 && [...rowTokens].some(r => r.startsWith(t))))
  const sc = qt.length ? hit.length / qt.length : 0
  if (sc >= 0.5) {
    const matched = names.filter((_, i) => norm[i].split(' ').some(t => hit.some(h => t === h || t.startsWith(h))))
    return { row, tier: 3, score: sc, matched: matched.slice(0, 3) }
  }
  return null
}

function toRow(s: Scored): ListValuesRow {
  return { code: s.row.code, display: s.row.display, aliases_matched: s.matched, seasons: compactSeasons(s.row.seasons) }
}

/** Pure matcher over entity rows. Rank: exact code, exact alias, prefix, token overlap. */
export function listValuesFromRows(entities: EntityRow[], input: ListValuesInput): ListValuesResult {
  const limit = Math.max(1, Math.min(MAX_ROWS, Math.floor(input.limit ?? MAX_ROWS)))
  let pool = entities.filter(e => e.domain === input.domain)
  const qFull = normalise(input.query ?? '')
  let q = qFull
  let season = input.season
  if (input.domain !== 'season') {
    const m = YEAR.exec(input.query ?? '')
    if (m && season === undefined) {
      season = Number(m[0])
      q = normalise((input.query ?? '').replace(m[0], ' '))
    }
  }
  if (season !== undefined) {
    const s = season
    pool = pool.filter(e => e.seasons.length === 0 || e.seasons.includes(s))
  }
  let ranked: Scored[]
  if (!q) {
    ranked = [...pool].sort((a, b) => a.code.localeCompare(b.code, 'en', { numeric: true }))
      .map(row => ({ row, tier: 1, score: 1, matched: [] }))
  } else {
    ranked = pool.map(r => score(r, q, qFull)).filter((x): x is Scored => x !== null)
      .sort((a, b) => a.tier - b.tier || b.score - a.score || a.row.code.localeCompare(b.row.code, 'en', { numeric: true }))
  }
  if (!ranked.length) return { status: 'no_data', rows: [], note: `No ${input.domain} matches "${input.query ?? ''}".` }
  const all = ranked.slice(0, limit).map(toRow)
  const top = ranked[0].tier
  const tied = ranked.filter(r => r.tier === top).length
  // Drop trailing rows until the WHOLE serialised result (status, rows, note) fits the token cap.
  for (let n = all.length; n >= 1; n--) {
    const rows = all.slice(0, n)
    const notes: string[] = []
    if (q && tied > 1 && top <= 2) notes.push(`${tied} candidates match equally; ask which one, do not pick.`)
    if (n < ranked.length) notes.push(`Showing ${n} of ${ranked.length} matches.`)
    const result: ListValuesResult = { status: 'ok', rows, ...(notes.length ? { note: notes.join(' ') } : {}) }
    if (n === 1 || tokensOf(JSON.stringify(result)) <= MAX_TOKENS) return result
  }
  return { status: 'no_data', rows: [] }
}

// ── loader and session cache ────────────────────────────────────────────────

let entitiesPromise: Promise<EntityRow[]> | null = null
const cache = new Map<string, ListValuesResult>()

export function clearListValuesCache(): void {
  cache.clear()
  entitiesPromise = null
}

async function loadEntities(): Promise<EntityRow[]> {
  const manifest = await loadManifest()
  const path = await getTablePath(manifest, 'assistant_entities')
  await registerParquet('assistant_entities', path)
  const raw = await rawQuery<Record<string, string | null>>(
    'SELECT domain, code, display, aliases, seasons, parent_code, extra FROM assistant_entities',
  )
  return raw.map(r => ({
    domain: String(r.domain),
    code: String(r.code),
    display: String(r.display),
    aliases: JSON.parse(r.aliases ?? '[]'),
    seasons: JSON.parse(r.seasons ?? '[]'),
    parent_code: r.parent_code ?? null,
    extra: JSON.parse(r.extra ?? '{}'),
  }))
}

async function pageEntities(): Promise<EntityRow[]> {
  const { routeToPageId } = await import('../nav/assistantTools')
  return Object.entries(routeToPageId).map(([route, id]) => ({
    domain: 'page', code: route, display: id,
    aliases: [id, id.replace(/-/g, ' '), route.split('/').filter(Boolean).join(' ')],
    seasons: [], parent_code: null, extra: { page_id: id },
  }))
}

export async function listValues(input: ListValuesInput): Promise<ListValuesResult> {
  const key = JSON.stringify([input.domain, normalise(input.query ?? ''), input.season ?? null, input.limit ?? null])
  const hit = cache.get(key)
  if (hit) return hit
  let result: ListValuesResult
  if (input.domain === 'page') {
    result = listValuesFromRows(await pageEntities(), input)
  } else if (input.domain === 'columns' || input.domain === 'card_kind') {
    const p = providers[input.domain]
    if (!p) {
      const waits = input.domain === 'columns' ? 'AX-05 (catalogue)' : 'AX-04 (registry)'
      result = { status: 'no_data', rows: [], note: `No ${input.domain} provider registered yet; waits on ${waits}.` }
    } else {
      const rows: EntityRow[] = p().map(x => ({
        domain: input.domain, code: x.code, display: x.display, aliases: x.aliases ?? [],
        seasons: [], parent_code: null, extra: {},
      }))
      result = listValuesFromRows(rows, input)
    }
  } else {
    entitiesPromise ??= loadEntities().catch(e => { entitiesPromise = null; throw e })
    result = listValuesFromRows(await entitiesPromise, input)
  }
  cache.set(key, result)
  return result
}
