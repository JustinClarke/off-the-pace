// Hermetic tests for the docs content claims: each case builds its own repo root (pages, sources,
// docs/app and assistant-docs) in a temp dir, so the real pages are never read or touched.
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createHash } from 'node:crypto'
import { evaluateClaims, mergeVerdicts, needsReview, resolveSource } from './docsClaims.mjs'
import { analyse, updatedManifest, pageStatuses, reviewedShas } from './docsDrift.mjs'

const sha = (t) => createHash('sha256').update(t).digest('hex')

const PAGE = `---
title: "Demo"
---

The warehouse has 94 dbt models and 1183 tests.

## Reading the signal correctly

The gap is measured, not modelled.
`
const SUMMARY = 'Demo\n\nThe warehouse has 94 dbt models and 1183 tests.'

let root, docsDir, assistantDir
const PAGE_PATH = 'docs/app/demo.mdx'
beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), 'docs-claims-'))
  docsDir = join(root, 'docs', 'app')
  assistantDir = join(root, 'assistant-docs')
  mkdirSync(docsDir, { recursive: true })
  mkdirSync(assistantDir, { recursive: true })
  mkdirSync(join(root, 'src'), { recursive: true })
  writeFileSync(join(docsDir, 'demo.mdx'), PAGE)
  writeFileSync(join(root, 'src', 'project.yml'), 'models: 94\nisolation_offset: {}\n')
})
afterEach(() => rmSync(root, { recursive: true, force: true }))

const valueClaim = (over = {}) => ({
  id: 'models',
  page: PAGE_PATH,
  kind: 'value',
  expect: { pattern: '(\\d+) dbt models' },
  source: { type: 'file-regex', file: 'src/project.yml', regex: '^models: (\\d+)' },
  ...over,
})
const proseClaim = { id: 'signal', page: PAGE_PATH, kind: 'prose', expect: 'The caveat is true.', source: { files: ['src/project.yml'] } }

const evaluate = (claims, verdicts = null, reviewed = {}) => evaluateClaims({ claims, verdicts, rootDir: root, reviewed })
const gen = () => ({ pages: { demo: { title: 'Demo', summary: SUMMARY, tokens: 0 } } })
const drift = (manifest) => analyse({ docsDir, assistantDir, generated: gen(), manifest, rootDir: root })
const opts = () => ({ docsDir, rootDir: root })
const record = (claims, verdict = 'PASS', evidence = 'page:9 agrees with src/project.yml:1') =>
  mergeVerdicts(null, { page: PAGE_PATH, sha256: sha(readFileSync(join(docsDir, 'demo.mdx'), 'utf8')), claims: [{ id: 'signal', verdict, evidence }] }, { claims, rootDir: root, now: 'T' })

describe('value claims', () => {
  it('FAILs a wrong number with both values and file:line', () => {
    writeFileSync(join(root, 'src', 'project.yml'), 'models: 95\n')
    const r = evaluate([valueClaim()]).pages[PAGE_PATH]
    expect(r.status).toBe('FAIL')
    expect(r.claims[0].detail).toContain('docs/app/demo.mdx:5 states "94", source says "95"')
  })

  it('binds the number to its label on the same line, so a number elsewhere on the page does not pass', () => {
    writeFileSync(join(docsDir, 'demo.mdx'), PAGE.replace('94 dbt models', 'many dbt models').replace('measured', 'measured on 94 laps'))
    const r = evaluate([valueClaim({ expect: { pattern: '(\\d+) dbt models' } })]).pages[PAGE_PATH]
    expect(r.status).toBe('FAIL')
    expect(r.claims[0].detail).toContain('not found on the page')
  })

  it('FAILs a forbidden statement with its line', () => {
    const r = evaluate([valueClaim({ forbid: ['measured, not modelled'] })]).pages[PAGE_PATH]
    expect(r.claims[0].detail).toMatch(/demo\.mdx:9 matches forbidden/)
  })

  it('passes a correct page', () => {
    expect(evaluate([valueClaim()]).pages[PAGE_PATH].status).toBe('OK')
  })

  it('uses a fallback source when a command cannot run, and says so', () => {
    mkdirSync(join(root, 'models'))
    writeFileSync(join(root, 'models', 'a.sql'), '')
    const r = resolveSource({ type: 'command', cmd: 'definitely-not-a-binary-xyz', countLines: true, fallback: { type: 'count-files', dir: 'models', ext: '.sql' } }, root)
    expect(r.value).toBe('1')
    expect(r.via).toContain('fallback')
  })
})

describe('prose claims and verdicts', () => {
  it('is NEEDS REVIEW without a verdict, and listed for the reviewer with its sha256', () => {
    const ev = evaluate([proseClaim])
    expect(ev.pages[PAGE_PATH].status).toBe('NEEDS REVIEW')
    const list = needsReview({ claims: [proseClaim], evaluation: ev })
    expect(list).toEqual([{ page: PAGE_PATH, sha256: sha(PAGE), claims: [{ id: 'signal', expect: 'The caveat is true.', sourceFiles: ['src/project.yml'] }] }])
  })

  it('a changed page with an old PASS verdict is NEEDS REVIEW', () => {
    const { verdicts } = record([proseClaim])
    expect(evaluate([proseClaim], verdicts).pages[PAGE_PATH].status).toBe('OK')
    writeFileSync(join(docsDir, 'demo.mdx'), PAGE.replace('measured', 'estimated'))
    const r = evaluate([proseClaim], verdicts).pages[PAGE_PATH]
    expect(r.status).toBe('NEEDS REVIEW')
    expect(r.claims[0].status).toBe('NO VERDICT')
  })

  it('refuses verdicts for a sha256 that is not the current page', () => {
    const { errors } = mergeVerdicts(null, { page: PAGE_PATH, sha256: 'stale', claims: [{ id: 'signal', verdict: 'PASS' }] }, { claims: [proseClaim], rootDir: root })
    expect(errors[0]).toContain('is not the current')
  })

  it('a FAIL or UNSETTLED verdict fails the page', () => {
    expect(evaluate([proseClaim], record([proseClaim], 'FAIL').verdicts).pages[PAGE_PATH].status).toBe('FAIL')
    expect(evaluate([proseClaim], record([proseClaim], 'UNSETTLED').verdicts).pages[PAGE_PATH].status).toBe('FAIL')
  })
})

describe('--update gate', () => {
  it('refuses a page with a FAIL value claim', () => {
    writeFileSync(join(root, 'src', 'project.yml'), 'models: 95\n')
    const m = updatedManifest(null, drift(null), evaluate([valueClaim()]), opts())
    expect(m.pages.demo).toBeUndefined()
    expect(m.claimPages[PAGE_PATH]).toBeUndefined()
  })

  it('refuses a page with a missing verdict, and one with a FAIL verdict', () => {
    expect(updatedManifest(null, drift(null), evaluate([proseClaim]), opts()).pages.demo).toBeUndefined()
    const failed = evaluate([proseClaim], record([proseClaim], 'FAIL').verdicts)
    expect(updatedManifest(null, drift(null), failed, opts()).pages.demo).toBeUndefined()
  })

  it('records a page whose content checks pass and every claim is PASS at the current sha256', () => {
    const ev = evaluate([valueClaim(), proseClaim], record([valueClaim(), proseClaim]).verdicts)
    const m = updatedManifest(null, drift(null), ev, opts())
    expect(m.pages.demo.docs.sha256).toBe(sha(PAGE))
    expect(m.claimPages[PAGE_PATH]).toEqual({ sha256: sha(PAGE) })
  })

  it('a refused page keeps its previous record', () => {
    const claims = [valueClaim(), proseClaim]
    const first = updatedManifest(null, drift(null), evaluate(claims, record(claims).verdicts), opts())
    writeFileSync(join(docsDir, 'demo.mdx'), PAGE.replace('measured', 'estimated'))
    const second = updatedManifest(first, drift(first), evaluate(claims, null), opts())
    expect(second.pages.demo).toEqual(first.pages.demo)
    expect(second.claimPages[PAGE_PATH]).toEqual(first.claimPages[PAGE_PATH])
  })
})

describe('plain check statuses', () => {
  it('a covered page whose hash changed is NEEDS REVIEW, not FAIL; an uncovered one stays FAIL', () => {
    const claims = [valueClaim(), proseClaim]
    const manifest = updatedManifest(null, drift(null), evaluate(claims, record(claims).verdicts), opts())
    writeFileSync(join(docsDir, 'demo.mdx'), PAGE.replace('measured', 'estimated'))
    const result = drift(manifest)
    const covered = pageStatuses(result, evaluate(claims, null, reviewedShas(manifest, opts())), opts())
    expect(covered.map((r) => r.status)).toEqual(['NEEDS REVIEW'])
    const uncovered = pageStatuses(result, evaluate([], null), opts())
    expect(uncovered.map((r) => r.status)).toEqual(['FAIL'])
  })

  it('a correct, reviewed page is content OK', () => {
    const claims = [valueClaim(), proseClaim]
    const verdicts = record(claims).verdicts
    const manifest = updatedManifest(null, drift(null), evaluate(claims, verdicts), opts())
    const rows = pageStatuses(drift(manifest), evaluate(claims, verdicts, reviewedShas(manifest, opts())), opts())
    expect(rows).toEqual([{ page: PAGE_PATH, fail: [], review: [], status: 'OK' }])
  })
})
