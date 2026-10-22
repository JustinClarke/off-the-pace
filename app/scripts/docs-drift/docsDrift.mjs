// Docs drift check: human docs pages (docs/app/**/*.mdx) vs the AI-facing copies the assistant reads.
//
// AI copies covered:
//   - the per-page summary in app/src/nav/pageSummaries.generated.json (what explain_page returns);
//   - the hand-written AI-facing source app/src/nav/assistant-docs/<slug>.md, when a page has one.
// This script never builds summaries itself: it reads the generator's output and only imports the
// generator's constants (paths, budget, token estimate) so both use one definition.
//
// A page fails when:
//   - a recorded hash (docs page, AI-facing source, or AI copy) differs from the committed manifest,
//     or the page is not in the manifest yet (a human must review and run --update);
//   - the generated entry is stale against its own source files (regenerate the summaries);
//   - a <Warning>/<Note>/<Tip> text on the docs page is missing from the AI copy;
//   - the AI copy is over the token budget (ceil(chars / 3.5) > 800);
//   - a number in the AI copy does not appear on the docs page.
//
// It also checks stated facts against the code (docsClaims.mjs, claims in docs-claims.json, any page
// under docs/): value claims are decided here; prose claims are decided by the docs-claims-reviewer
// agent and recorded with --record-verdicts. A changed hash on a page covered by claims is NEEDS
// REVIEW, not FAIL.
//
//   node scripts/docs-drift/docsDrift.mjs            check; one line per page: content OK / FAIL /
//                                                    NEEDS REVIEW; exit 1 on any FAIL
//   node scripts/docs-drift/docsDrift.mjs --update   record current hashes in the manifest (the only
//                                                    way the manifest is written). A page is recorded
//                                                    only if its content checks pass AND every claim on
//                                                    it is PASS at its current sha256; exit 1 if any
//                                                    page is refused.
//   --values-only           value claims only (deterministic; what CI runs)
//   --list-needs-review     JSON: pages with prose claims lacking a verdict at the current sha256
//   --record-verdicts F     merge reviewer output (JSON file F) into docs-claims.verdicts.json
import { readFileSync, writeFileSync, readdirSync, existsSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  ASSISTANT_DOCS_DIR,
  DOCS_APP_DIR,
  OUT_FILE,
  SUMMARY_BUDGET_TOKENS,
  TOKEN_ESTIMATE,
  estimateTokens,
} from '../../src/nav/pageSummaries.mjs'
import {
  CLAIMS_FILE,
  VERDICTS_FILE,
  evaluateClaims,
  gateReasons,
  loadJson,
  mergeVerdicts,
  needsReview,
  writeJson,
} from './docsClaims.mjs'

const here = dirname(fileURLToPath(import.meta.url))
export const REPO_ROOT = join(here, '..', '..', '..')
export const MANIFEST_FILE = join(here, 'docs-drift.manifest.json')

export const sha256 = (text) => createHash('sha256').update(text).digest('hex')

/** Markup-insensitive text: tags, link targets, bold and whitespace runs do not count as drift. */
export const norm = (t) =>
  t
    .replace(/<\/?[A-Za-z][^>\n]*>/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\*\*/g, '')
    .replace(/\s+/g, ' ')
    .trim()

export const stripComments = (src) => src.replace(/<!--[\s\S]*?-->\n?/g, '')

/** Every <Note>/<Warning>/<Tip> on a page, normalised. */
export function callouts(src) {
  return [...src.matchAll(/<(Note|Warning|Tip)[^>]*>([\s\S]*?)<\/\1>/g)]
    .map((m) => ({ tag: m[1], text: norm(m[2]) }))
    .filter((c) => c.text)
}

/**
 * Numeric tokens in a text. A number glued to letters or underscores (v2, fct_x_2) is an identifier,
 * not a figure, and is skipped. Thousands separators are dropped so 1,000 and 1000 match.
 */
export function numbers(text) {
  const out = new Set()
  for (const m of text.matchAll(/(?<![\w.])\d+(?:[.,]\d+)*(?![A-Za-z_])/g)) {
    out.add(m[0].replace(/,(?=\d{3}(?!\d))/g, ''))
  }
  return out
}

function listMdx(dir) {
  const out = []
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name)
    if (e.isDirectory()) out.push(...listMdx(p))
    else if (e.name.endsWith('.mdx')) out.push(p)
  }
  return out.sort()
}

const clip = (s, n = 60) => (s.length > n ? `${s.slice(0, n)}...` : s)

/** Content checks that do not depend on the manifest. Returns a list of reasons. */
export function contentReasons({ human, aiSource, entry, budget = SUMMARY_BUDGET_TOKENS }) {
  const reasons = []
  const summary = entry.summary ?? ''
  const copies = [['AI copy', norm(summary)]]
  if (aiSource != null) copies.push(['AI-facing source', norm(stripComments(aiSource))])

  for (const c of callouts(human)) {
    for (const [label, text] of copies) {
      if (!text.includes(c.text)) reasons.push(`${c.tag} missing from ${label}: "${clip(c.text)}"`)
    }
  }

  const tokens = estimateTokens(summary)
  if (tokens > budget) reasons.push(`AI copy is ${tokens} tokens, over the ${budget} budget`)

  const onPage = numbers(human)
  for (const [label, text] of copies) {
    const missing = [...numbers(text)].filter((n) => !onPage.has(n))
    if (missing.length) reasons.push(`number(s) in ${label} not on docs page: ${missing.join(', ')}`)
  }
  return reasons
}

/**
 * Check every page. Returns { failures: [{ slug, reasons, content }], entries: { slug: manifestEntry } }.
 * `content` is true when the page failed a check other than the manifest comparison.
 */
export function analyse({
  docsDir = DOCS_APP_DIR,
  assistantDir = ASSISTANT_DOCS_DIR,
  generated,
  manifest,
  rootDir = REPO_ROOT,
  budget = SUMMARY_BUDGET_TOKENS,
}) {
  const rel = (p) => relative(rootDir, p)
  const genPages = generated?.pages ?? {}
  const manPages = manifest?.pages ?? {}
  const docsSlugs = existsSync(docsDir)
    ? listMdx(docsDir).map((f) => relative(docsDir, f).replace(/\.mdx$/, '').split('\\').join('/'))
    : []
  const slugs = [...new Set([...docsSlugs, ...Object.keys(genPages), ...Object.keys(manPages)])].sort()

  const failures = []
  const entries = {}
  for (const slug of slugs) {
    const content = []
    const drift = []
    const humanPath = join(docsDir, `${slug}.mdx`)
    const aiPath = join(assistantDir, `${slug}.md`)
    const entry = genPages[slug]
    const recorded = manPages[slug]

    if (!existsSync(humanPath)) {
      content.push('docs page is gone but an AI copy or manifest entry remains')
      failures.push({ slug, reasons: content, content: true })
      continue
    }
    const human = readFileSync(humanPath, 'utf8')
    const aiSource = existsSync(aiPath) ? readFileSync(aiPath, 'utf8') : null

    if (!entry) {
      content.push('no AI copy in pageSummaries.generated.json (run `node src/nav/pageSummaries.mjs`)')
      failures.push({ slug, reasons: content, content: true })
      continue
    }

    // The generated entry must reflect the files it was built from.
    if (aiSource != null) {
      if (entry.sourceSha256 !== sha256(aiSource) || entry.docsSha256 !== sha256(human)) {
        content.push('generated summary is stale against its AI-facing source or docs page (run `node src/nav/pageSummaries.mjs`)')
      }
    } else if (entry.source) {
      content.push(`generated summary names AI-facing source ${entry.source}, which no longer exists`)
    }

    content.push(...contentReasons({ human, aiSource, entry, budget }))

    const current = {
      docs: { path: rel(humanPath), sha256: sha256(human) },
      ...(aiSource != null ? { assistantSource: { path: rel(aiPath), sha256: sha256(aiSource) } } : {}),
      aiCopy: { path: `${rel(OUT_FILE)}#pages/${slug}`, sha256: sha256(entry.summary ?? '') },
    }
    entries[slug] = current

    if (!recorded) {
      drift.push('not in manifest: review the page and its AI copy, then run --update')
    } else {
      const docsChanged = recorded.docs?.sha256 !== current.docs.sha256
      const aiChanged =
        recorded.aiCopy?.sha256 !== current.aiCopy.sha256 ||
        (recorded.assistantSource?.sha256 ?? null) !== (current.assistantSource?.sha256 ?? null)
      if (docsChanged && !aiChanged) drift.push('docs page changed since the manifest but its AI copy did not')
      else if (docsChanged && aiChanged) drift.push('docs page and AI copy both changed since the manifest: review, then run --update')
      else if (aiChanged) drift.push('AI copy changed since the manifest but the docs page did not: review, then run --update')
    }

    if (content.length || drift.length) failures.push({ slug, reasons: [...content, ...drift], content: content.length > 0 })
  }
  return { failures, entries }
}

/** Repo-relative docs path of a docs/app slug, as claims name pages. */
const appPage = (slug, docsDir, rootDir) => relative(rootDir, join(docsDir, `${slug}.mdx`)).split('\\').join('/')

/**
 * Why --update must not record a page: content-check failures, plus (for a page with claims) every
 * claim that is not PASS at the page's current sha256. Returns Map(page -> reasons).
 */
export function blockedPages(result, evaluation, { docsDir = DOCS_APP_DIR, rootDir = REPO_ROOT } = {}) {
  const blocked = new Map()
  const add = (page, reasons) => blocked.set(page, [...(blocked.get(page) ?? []), ...reasons])
  for (const f of result.failures) if (f.content) add(appPage(f.slug, docsDir, rootDir), f.reasons.filter((r) => !r.startsWith('not in manifest') && !/changed since the manifest/.test(r)))
  for (const [page, res] of Object.entries(evaluation?.pages ?? {})) {
    const reasons = gateReasons(res)
    if (reasons.length) add(page, reasons)
  }
  return blocked
}

/**
 * Manifest after --update. A docs/app page gets its current hashes only when its content checks pass
 * AND every claim on it PASSes at its current sha256; claim pages anywhere under docs/ are recorded in
 * `claimPages` under the same rule. A blocked page keeps its previous record.
 */
export function updatedManifest(previous, result, evaluation = null, opts = {}) {
  const { docsDir = DOCS_APP_DIR, rootDir = REPO_ROOT } = opts
  const { entries } = result
  const blocked = blockedPages(result, evaluation, { docsDir, rootDir })
  const pages = {}
  for (const slug of Object.keys(entries).sort()) {
    if (blocked.has(appPage(slug, docsDir, rootDir))) {
      if (previous?.pages?.[slug]) pages[slug] = previous.pages[slug]
    } else pages[slug] = entries[slug]
  }
  const claimPages = {}
  for (const [page, res] of Object.entries(evaluation?.pages ?? {}).sort(([a], [b]) => a.localeCompare(b))) {
    if (blocked.has(page) || !res.exists) {
      if (previous?.claimPages?.[page]) claimPages[page] = previous.claimPages[page]
    } else claimPages[page] = { sha256: res.sha256 }
  }
  return {
    note: 'Written only by `node scripts/docs-drift/docsDrift.mjs --update`. Do not edit by hand.',
    budgetTokens: SUMMARY_BUDGET_TOKENS,
    tokenEstimate: TOKEN_ESTIMATE,
    pages,
    ...(evaluation ? { claimPages } : {}),
  }
}

/** page -> sha256 last recorded as reviewed (claimPages, else the docs/app manifest entry). */
export function reviewedShas(manifest, { docsDir = DOCS_APP_DIR, rootDir = REPO_ROOT } = {}) {
  const out = {}
  for (const [slug, e] of Object.entries(manifest?.pages ?? {})) if (e.docs?.sha256) out[appPage(slug, docsDir, rootDir)] = e.docs.sha256
  for (const [page, e] of Object.entries(manifest?.claimPages ?? {})) out[page] = e.sha256
  return out
}

/**
 * One status per page: FAIL, NEEDS REVIEW or OK. Hash drift on a page covered by claims is NEEDS
 * REVIEW, not FAIL (the claims and verdicts carry correctness there); on an uncovered docs/app page it
 * stays FAIL as before.
 */
export function pageStatuses(result, evaluation, { docsDir = DOCS_APP_DIR, rootDir = REPO_ROOT } = {}) {
  const rows = new Map()
  const row = (page) => rows.get(page) ?? rows.set(page, { page, fail: [], review: [] }).get(page)
  const covered = new Set(Object.keys(evaluation?.pages ?? {}))
  for (const slug of Object.keys(result.entries)) row(appPage(slug, docsDir, rootDir))
  for (const f of result.failures) {
    const page = appPage(f.slug, docsDir, rootDir)
    for (const r of f.reasons) {
      const drift = r.startsWith('not in manifest') || /changed since the manifest/.test(r)
      if (drift && covered.has(page)) row(page).review.push(r)
      else row(page).fail.push(r)
    }
  }
  for (const [page, res] of Object.entries(evaluation?.pages ?? {})) {
    const r = row(page)
    for (const c of res.claims) {
      if (c.status === 'FAIL' || c.status === 'UNSETTLED') r.fail.push(`claim ${c.id} ${c.status}: ${c.detail}`)
      else if (c.status !== 'PASS') r.review.push(`claim ${c.id} ${c.status}: ${c.detail}`)
    }
    if (res.changedSinceReview && !page.startsWith(relative(rootDir, docsDir))) r.review.push('page changed since its last reviewed record')
  }
  return [...rows.values()]
    .map((r) => ({ ...r, status: r.fail.length ? 'FAIL' : r.review.length ? 'NEEDS REVIEW' : 'OK' }))
    .sort((a, b) => a.page.localeCompare(b.page))
}

function argValue(argv, flag) {
  const i = argv.indexOf(flag)
  return i >= 0 ? argv[i + 1] : undefined
}

function main(argv) {
  const generated = JSON.parse(readFileSync(OUT_FILE, 'utf8'))
  const manifest = existsSync(MANIFEST_FILE) ? JSON.parse(readFileSync(MANIFEST_FILE, 'utf8')) : null
  const claims = loadJson(CLAIMS_FILE, { claims: [] }).claims
  const verdicts = loadJson(VERDICTS_FILE, { pages: {} })
  const rel = (p) => relative(process.cwd(), p)

  if (argv.includes('--record-verdicts')) {
    const file = argValue(argv, '--record-verdicts')
    if (!file || !existsSync(file)) {
      console.log('docs-drift: --record-verdicts needs a JSON file of reviewer output')
      return 2
    }
    const { verdicts: next, errors } = mergeVerdicts(verdicts, JSON.parse(readFileSync(file, 'utf8')), { claims, rootDir: REPO_ROOT })
    for (const e of errors) console.log(`REFUSED ${e}`)
    writeJson(VERDICTS_FILE, next)
    console.log(`docs-drift: wrote ${rel(VERDICTS_FILE)} (${errors.length} refused)`)
    return errors.length ? 1 : 0
  }

  const valuesOnly = argv.includes('--values-only')
  const evaluation = evaluateClaims({ claims, verdicts, rootDir: REPO_ROOT, reviewed: reviewedShas(manifest), valuesOnly })

  if (argv.includes('--list-needs-review')) {
    console.log(JSON.stringify(needsReview({ claims, evaluation }), null, 2))
    return 0
  }

  if (valuesOnly) {
    // The deterministic part only (used in CI): value claims, no verdicts, no hashes.
    let fails = 0
    for (const [page, res] of Object.entries(evaluation.pages)) {
      for (const c of res.claims) {
        if (c.status === 'FAIL') fails++
        console.log(`${c.status === 'PASS' ? 'OK  ' : c.status === 'FAIL' ? 'FAIL' : 'SKIP'} ${page} ${c.id}: ${c.detail}`)
      }
    }
    const n = Object.values(evaluation.pages).reduce((s, p) => s + p.claims.length, 0)
    console.log(`docs-claims: ${n} value claims on ${Object.keys(evaluation.pages).length} pages, ${fails} failing`)
    return fails ? 1 : 0
  }

  const result = analyse({ generated, manifest })

  if (argv.includes('--update')) {
    const next = updatedManifest(manifest, result, evaluation)
    writeFileSync(MANIFEST_FILE, JSON.stringify(next, null, 2) + '\n')
    const blocked = blockedPages(result, evaluation)
    for (const [page, reasons] of blocked) console.log(`NOT RECORDED ${page}: ${reasons.join('; ')}`)
    console.log(`docs-drift: wrote ${rel(MANIFEST_FILE)} (${Object.keys(next.pages).length} app pages and ${Object.keys(next.claimPages ?? {}).length} claim pages recorded, ${blocked.size} refused)`)
    return blocked.size ? 1 : 0
  }

  if (!manifest) console.log(`docs-drift: no manifest at ${rel(MANIFEST_FILE)}; every page reads as unrecorded`)
  const rows = pageStatuses(result, evaluation)
  for (const r of rows) {
    const why = r.status === 'FAIL' ? r.fail : r.status === 'NEEDS REVIEW' ? r.review : []
    console.log(`${r.status === 'OK' ? 'content OK' : r.status} ${r.page}${why.length ? `: ${why.join('; ')}` : ''}`)
  }
  const count = (s) => rows.filter((r) => r.status === s).length
  console.log(`docs-drift: ${rows.length} pages checked (${Object.keys(evaluation.pages).length} with claims): ${count('OK')} OK, ${count('FAIL')} FAIL, ${count('NEEDS REVIEW')} NEEDS REVIEW`)
  return count('FAIL') ? 1 : 0
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  process.exit(main(process.argv.slice(2)))
}
