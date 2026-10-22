// Hermetic tests for the docs drift check: every case builds its own docs/ and assistant-docs/
// folders in a temp dir, so they do not depend on (or break with) the live pages.
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { analyse, numbers, updatedManifest, sha256 } from './docsDrift.mjs'

const PAGE = `---
title: "Demo"
---

Intro with 4.1 races and 22 points.

<Warning>
  **Never read the raw rate.** It spans 0.000 to 0.100.
</Warning>

<Note>
  Built from green laps only.
</Note>
`
const SUMMARY = 'Demo\n\nIntro with 4.1 races and 22 points.\n\nWARNING: Never read the raw rate. It spans 0.000 to 0.100.\n\nNOTE: Built from green laps only.'

let root, docsDir, assistantDir
beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), 'docs-drift-'))
  docsDir = join(root, 'docs', 'app')
  assistantDir = join(root, 'assistant-docs')
  mkdirSync(docsDir, { recursive: true })
  mkdirSync(assistantDir, { recursive: true })
  writeFileSync(join(docsDir, 'demo.mdx'), PAGE)
})
afterEach(() => rmSync(root, { recursive: true, force: true }))

const gen = (summary = SUMMARY) => ({ pages: { demo: { title: 'Demo', summary, tokens: 0 } } })
const run = (generated, manifest) => analyse({ docsDir, assistantDir, generated, manifest, rootDir: root })
const reasons = (r) => r.failures.flatMap((f) => f.reasons).join(' | ')

describe('docs drift check', () => {
  it('passes a reviewed page, and fails an unrecorded one', () => {
    const first = run(gen(), null)
    expect(reasons(first)).toContain('not in manifest')
    const manifest = updatedManifest(null, first)
    expect(run(gen(), manifest).failures).toEqual([])
  })

  it('fails when the docs page changed and the AI copy did not', () => {
    const manifest = updatedManifest(null, run(gen(), null))
    writeFileSync(join(docsDir, 'demo.mdx'), PAGE.replace('Intro', 'Opening'))
    expect(reasons(run(gen(), manifest))).toContain('docs page changed since the manifest but its AI copy did not')
  })

  it('fails when a Warning is missing from the AI copy', () => {
    const r = run(gen(SUMMARY.replace(/WARNING:.*\n\n/, '')), null)
    expect(reasons(r)).toMatch(/Warning missing from AI copy: "Never read the raw rate/)
  })

  it('fails when a Note is missing from the AI-facing source', () => {
    writeFileSync(join(assistantDir, 'demo.md'), PAGE.replace(/<Note>[\s\S]*<\/Note>/, ''))
    const src = PAGE.replace(/<Note>[\s\S]*<\/Note>/, '')
    const g = gen()
    Object.assign(g.pages.demo, { source: 'assistant-docs/demo.md', sourceSha256: sha256(src), docsSha256: sha256(PAGE) })
    expect(reasons(run(g, null))).toContain('Note missing from AI-facing source')
  })

  it('fails when the generated entry is stale against its AI-facing source', () => {
    writeFileSync(join(assistantDir, 'demo.md'), PAGE)
    const g = gen()
    Object.assign(g.pages.demo, { source: 'assistant-docs/demo.md', sourceSha256: 'old', docsSha256: sha256(PAGE) })
    expect(reasons(run(g, null))).toContain('generated summary is stale')
  })

  it('fails when the AI copy is over the 800-token budget', () => {
    const r = run(gen(SUMMARY + '\n\n' + 'x'.repeat(2800)), null)
    expect(reasons(r)).toMatch(/AI copy is \d+ tokens, over the 800 budget/)
  })

  it('fails when the AI copy states a number the docs page does not', () => {
    const r = run(gen(SUMMARY.replace('22 points', '23 points')), null)
    expect(reasons(r)).toContain('number(s) in AI copy not on docs page: 23')
  })

  it('--update does not record a page that fails a content check', () => {
    const r = run(gen(SUMMARY.replace('22 points', '23 points')), null)
    expect(updatedManifest(null, r).pages.demo).toBeUndefined()
  })

  it('prints one failure entry per page', () => {
    const r = run(gen('x'.repeat(3000) + ' 99'), null)
    expect(r.failures.map((f) => f.slug)).toEqual(['demo'])
  })
})

describe('numbers()', () => {
  it('reads figures, skips identifiers, and ignores thousands separators', () => {
    expect([...numbers('8.97% of 1,000 laps, 66.2-80.2, 110/149, fct_v2 and AI10')]).toEqual(['8.97', '1000', '66.2', '80.2', '110', '149'])
  })
})
