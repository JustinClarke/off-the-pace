// AI-facing page sources (app/src/nav/assistant-docs/<slug>.md): the summary of such a page is
// built from that file instead of docs/app/<slug>.mdx. These checks keep the AI source honest
// against the published page: same callouts verbatim, same frontmatter, no figure the page does
// not state, within budget with nothing trimmed, and recorded hashes that match both files.
import { describe, it, expect } from 'vitest'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { join } from 'node:path'
import { explainPage } from './assistantTools'
import generated from './pageSummaries.generated.json'
import {
  ASSISTANT_DOCS_DIR,
  DOCS_APP_DIR,
  SUMMARY_BUDGET_TOKENS,
  assistantSourceFor,
  estimateTokens,
  summarise,
} from './pageSummaries.mjs'

const norm = (t: string) =>
  t.replace(/<\/?[A-Za-z][^>\n]*>/g, '').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/\*\*/g, '').replace(/\s+/g, ' ').trim()
const callouts = (src: string) => [...src.matchAll(/<(Note|Warning|Tip)[^>]*>([\s\S]*?)<\/\1>/g)].map((m) => ({ tag: m[1], text: norm(m[2]) }))
const frontmatter = (src: string) => src.match(/^---\n([\s\S]*?)\n---\n/)?.[1] ?? ''
const stripComments = (src: string) => src.replace(/<!--[\s\S]*?-->\n?/g, '')
const sha256 = (t: string) => createHash('sha256').update(t).digest('hex')

const aiSlugs = readdirSync(ASSISTANT_DOCS_DIR)
  .filter((f) => f.endsWith('.md'))
  .map((f) => f.slice(0, -3))
const pages = generated.pages as Record<string, { summary: string; source?: string; sourceSha256?: string; docsSha256?: string }>

// Caveat phrases the race-control summary must carry, in substance, from "Reading the signal
// correctly" and the page's callouts. Each is a figure or claim stated in docs/app/race-control.mdx.
const RACE_CONTROL_REQUIRED = [
  'There is no per-circuit safety-car probability on this page',
  'that is the finding, not an omission',
  '4.8 races per circuit',
  'between-circuit share at 0.000',
  '20 points',
  '93 points',
  '100 points',
  'seven coin flips as a forecast',
  'Only pooled rates',
  '95% CI',
  '128/173',
  '98/173',
  '74/173',
  '19/173',
  '9.03%',
  '90.5%',
  '58.3%',
  'The per-circuit strip, and what it actually is',
  'never read',
  'L / (L + 600)',
  '0.202',
  '0.452',
  'wearing a circuit',
  'Why 2018 is blank',
  'season-lagged',
  'not measurable',
  'never a measured zero',
  'How a "window" is counted',
  '129 safety-car windows from 137 logged onsets',
  '88 of the 98',
  'slight undercount of how many times race control acted',
  'fct_lap_residuals',
  'performing a no-op',
  'roughly half of normal',
  'changed for free',
]

describe('assistant-docs: AI-facing page sources', () => {
  it('race-control uses its AI-facing source', () => {
    expect(assistantSourceFor('race-control')).toBe(join(ASSISTANT_DOCS_DIR, 'race-control.md'))
    expect(pages['race-control'].source).toBe('app/src/nav/assistant-docs/race-control.md')
  })

  it('race-control summary carries every required caveat phrase', () => {
    const r = explainPage('race-control')
    expect(r.ok).toBe(true)
    if (!r.ok) return
    const s = norm(r.summary)
    for (const phrase of RACE_CONTROL_REQUIRED) expect(s, phrase).toContain(norm(phrase))
  })

  for (const slug of aiSlugs) {
    const aiRaw = readFileSync(join(ASSISTANT_DOCS_DIR, `${slug}.md`), 'utf8')
    const ai = stripComments(aiRaw)
    const humanPath = join(DOCS_APP_DIR, `${slug}.mdx`)

    it(`${slug}: has a docs/app page to shadow`, () => {
      expect(existsSync(humanPath)).toBe(true)
    })
    const human = existsSync(humanPath) ? readFileSync(humanPath, 'utf8') : ''

    it(`${slug}: fits the budget whole, with nothing trimmed`, () => {
      const built = summarise(slug, ai)
      expect(estimateTokens(built.summary)).toBeLessThanOrEqual(SUMMARY_BUDGET_TOKENS)
      expect(built.summary).not.toContain('[...]')
      // Every body paragraph of the AI source made it into the summary.
      const body = ai.slice(ai.indexOf('\n---\n', 4) + 5)
      const paras = body
        .replace(/<(Note|Warning|Tip)[^>]*>[\s\S]*?<\/\1>/g, '')
        .split(/\n\n/)
        .map((p) => p.trim())
        .filter((p) => p && !/^#{2,6}\s/.test(p))
      for (const p of paras) expect(norm(built.summary), p.slice(0, 40)).toContain(norm(p))
    })

    it(`${slug}: frontmatter matches the docs page`, () => {
      expect(frontmatter(ai)).toBe(frontmatter(human))
    })

    it(`${slug}: every Note/Warning/Tip on the docs page appears verbatim, and no others`, () => {
      const h = callouts(human)
      const a = callouts(ai)
      expect(h.length).toBeGreaterThan(0)
      for (const c of h) expect(a.map((x) => `${x.tag}: ${x.text}`), c.text.slice(0, 50)).toContain(`${c.tag}: ${c.text}`)
      for (const c of a) expect(h.map((x) => `${x.tag}: ${x.text}`), c.text.slice(0, 50)).toContain(`${c.tag}: ${c.text}`)
    })

    it(`${slug}: every figure in the AI source appears on the docs page`, () => {
      const body = ai.slice(ai.indexOf('\n---\n', 4) + 5)
      const figures = new Set(body.match(/\d+(?:\.\d+)?%?/g) ?? [])
      const humanFlat = human.replace(/\s+/g, ' ')
      for (const f of figures) expect(humanFlat, f).toContain(f)
    })

    it(`${slug}: generated entry is pinned to both current files`, () => {
      expect(pages[slug].sourceSha256).toBe(sha256(aiRaw))
      expect(pages[slug].docsSha256).toBe(sha256(human))
    })
  }

  it('pages without an AI source carry no AI-source fields', () => {
    for (const [id, p] of Object.entries(pages)) {
      if (aiSlugs.includes(id)) continue
      expect(p.source, id).toBeUndefined()
      expect(p.docsSha256, id).toBeUndefined()
    }
  })
})
