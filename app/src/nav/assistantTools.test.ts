// AI-10 acceptance checks: every shipped route resolves, none unshipped is listed, every summary
// is within budget and carries its page's caveats. Runs in CI via `vitest run`.
import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { routes } from './routes'
import {
  navigate,
  explainPage,
  shippedPaths,
  routeToPageId,
  explainablePageIds,
} from './assistantTools'
import {
  buildAll,
  estimateTokens,
  serialise,
  SUMMARY_BUDGET_TOKENS,
  DOCS_APP_DIR,
  OUT_FILE,
} from './pageSummaries.mjs'

const appSrc = readFileSync(join(import.meta.dirname, '..', 'App.tsx'), 'utf8')
const routerPaths = new Set([...appSrc.matchAll(/path:\s*'([^']+)'/g)].map((m) => m[1]))
// Routes the built app renders as a "coming soon" stub rather than a page.
const stubPaths = new Set([...appSrc.matchAll(/path:\s*'([^']+)',\s*element:\s*<Stub/g)].map((m) => m[1]))

const norm = (t: string) =>
  t.replace(/<\/?[A-Za-z][^>\n]*>/g, '').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/\*\*/g, '').replace(/\s+/g, ' ').trim()

describe('navigate: route list', () => {
  it('lists only routes the router actually defines', () => {
    for (const p of shippedPaths) expect(routerPaths.has(p), p).toBe(true)
  })
  it('lists no route marked unshipped', () => {
    for (const r of routes.filter((r) => r.shipped === false)) expect(shippedPaths).not.toContain(r.path)
  })
  it('lists no dynamic route', () => {
    for (const p of shippedPaths) expect(p).not.toContain(':')
  })
  it('lists no route that renders only a coming-soon stub', () => {
    expect([...stubPaths].filter((p) => shippedPaths.includes(p))).toEqual([])
  })
  it('rejects /race-craft, a coming-soon stub', () => {
    expect(navigate('/race-craft').ok).toBe(false)
    expect(shippedPaths).not.toContain('/race-craft')
  })
  it('the shipped-route count is derived from the route table, not hard-coded', () => {
    const expected = routes.filter((r) => r.shipped !== false && !r.path.includes(':') && !stubPaths.has(r.path))
    expect(shippedPaths).toHaveLength(expected.length)
  })
  it('resolves every shipped route and rejects others', () => {
    for (const p of shippedPaths) expect(navigate(p)).toEqual({ ok: true, url: p })
    expect(navigate('/races').ok).toBe(false)
    expect(navigate('/nope').ok).toBe(false)
  })
  it('allows only the four URL filters, as integers', () => {
    expect(navigate('/tyre-strategy/pit-gantt', { season: 2024, race: 7 })).toEqual({
      ok: true,
      url: '/tyre-strategy/pit-gantt?season=2024&race=7',
    })
    expect(navigate('/', { sql: 1 }).ok).toBe(false)
    expect(navigate('/', { season: '2024' }).ok).toBe(false)
  })
})

describe('explain_page: summaries', () => {
  it('the race-control summary keeps its "Reading the signal correctly" caveats and no empty heading', () => {
    const r = explainPage('race-control')
    expect(r.ok).toBe(true)
    if (!r.ok) return
    expect(r.summary).toContain('Why 2018 is blank')
    expect(r.summary).toContain('How a "window" is counted')
    expect(r.summary).toContain('wearing a circuit')
    // An empty heading is one followed only by whitespace and then another heading or the end.
    // (The old pattern's `$` under /m matched before any blank line, so it flagged every heading.)
    expect(r.summary).not.toMatch(/^#{2,6} [^\n]*(?:\n\s*#{2,6} |\s*(?![\s\S]))/m)
  })
  const built = buildAll()
  it('the committed generated file is current with docs/app', () => {
    expect(existsSync(OUT_FILE)).toBe(true)
    expect(readFileSync(OUT_FILE, 'utf8')).toBe(serialise(built))
  })
  it('covers every docs/app page', () => {
    const slugs = (dir: string, pre = ''): string[] =>
      readdirSync(join(dir), { withFileTypes: true }).flatMap((e) =>
        e.isDirectory() ? slugs(join(dir, e.name), `${pre}${e.name}/`) : e.name.endsWith('.mdx') ? [pre + e.name.slice(0, -4)] : [],
      )
    expect([...explainablePageIds].sort()).toEqual(slugs(DOCS_APP_DIR).sort())
  })
  it('every summary is within budget', () => {
    for (const [id, p] of Object.entries(built.pages)) {
      expect(estimateTokens(p.summary), id).toBeLessThanOrEqual(SUMMARY_BUDGET_TOKENS)
    }
  })
  it('every summary carries every Note/Warning/Tip from its docs page', () => {
    for (const id of explainablePageIds) {
      const src = readFileSync(join(DOCS_APP_DIR, `${id}.mdx`), 'utf8')
      const callouts = [...src.matchAll(/<(Note|Warning|Tip)[^>]*>([\s\S]*?)<\/\1>/g)]
      const summary = explainPage(id)
      expect(summary.ok).toBe(true)
      if (!summary.ok) continue
      for (const c of callouts) {
        expect(norm(summary.summary), `${id}: ${norm(c[2]).slice(0, 40)}`).toContain(norm(c[2]).slice(0, 60))
      }
    }
  })
  it('every shipped route with a feature page maps to a real summary', () => {
    for (const p of shippedPaths) {
      if (p === '/roadmap') continue
      expect(routeToPageId[p], p).toBeDefined()
      expect(explainPage(p).ok, p).toBe(true)
    }
  })
  it('rejects unknown pages', () => {
    expect(explainPage('nope').ok).toBe(false)
  })
})
