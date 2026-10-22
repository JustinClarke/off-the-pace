// Content claims for the docs drift check: facts a docs page states, checked against the code.
//
// docs-claims.json holds one entry per checkable claim: { id, page, kind, expect, source }.
//   kind "value": deterministic. `source` names a command or file-plus-selector that yields the true
//     value; `expect.pattern` is a regex with one capture group (or an alternation, each branch with
//     one group), matched line by line on the page, so a
//     number is bound to its label on the same line. Every match must equal the source value. Or
//     `expect.value` is a literal the source must equal (a page-independent fact, e.g. nav coverage).
//     `forbid` (optional) lists regexes no page line may match. A mismatch is FAIL with page:line.
//   kind "prose": needs reading. `expect` is the statement, `source.files` the files that settle it.
//     The script never decides these: the docs-claims-reviewer agent (.claude/agents/) does, and its
//     verdicts are recorded with --record-verdicts into docs-claims.verdicts.json, keyed by page and the
//     page's sha256. A verdict counts only while the page still has that sha256.
//
// This module calls no model. It runs value sources (files, and commands such as dbt ls) only.
import { readFileSync, writeFileSync, readdirSync, existsSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { execSync } from 'node:child_process'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
export const CLAIMS_FILE = join(here, 'docs-claims.json')
export const VERDICTS_FILE = join(here, 'docs-claims.verdicts.json')
const sha256 = (text) => createHash('sha256').update(text).digest('hex')

export const VERDICTS = ['PASS', 'FAIL', 'UNSETTLED']

/** Values compare after dropping thousands separators, unifying dashes and trimming. */
export const normValue = (v) =>
  String(v)
    .replace(/(?<=\d),(?=\d{3}(?!\d))/g, '')
    .replace(/[\u2013\u2014]/g, '-')
    .replace(/\s+/g, ' ')
    .trim()

function walk(dir, ext) {
  if (!existsSync(dir)) return []
  return readdirSync(dir, { withFileTypes: true })
    .flatMap((e) => (e.isDirectory() ? walk(join(dir, e.name), ext) : e.name.endsWith(ext) ? [join(dir, e.name)] : []))
    .sort()
}

function parseCsv(text) {
  const rows = []
  for (const line of text.split(/\r?\n/)) {
    if (!line) continue
    const cells = []
    let cur = ''
    let q = false
    for (let i = 0; i < line.length; i++) {
      const ch = line[i]
      if (q) {
        if (ch === '"' && line[i + 1] === '"') (cur += '"'), i++
        else if (ch === '"') q = false
        else cur += ch
      } else if (ch === '"') q = true
      else if (ch === ',') cells.push(cur), (cur = '')
      else cur += ch
    }
    cells.push(cur)
    rows.push(cells)
  }
  const [head, ...body] = rows
  return body.map((r) => Object.fromEntries(head.map((h, i) => [h, r[i]])))
}

/**
 * Resolve a value claim's source to { value, via } or { unavailable: reason }.
 * Source types: command, file-regex, count-matches, md-table-items, csv, count-files, docs-nav-unlisted.
 * Any source may carry `fallback` (another source) used when it cannot run here.
 */
export function resolveSource(source, rootDir) {
  const at = (p) => join(rootDir, p)
  try {
    switch (source.type) {
      case 'command': {
        const out = execSync(source.cmd, { cwd: at(source.cwd ?? '.'), stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf8', timeout: 180000 })
        const value = source.countLines ? String(out.split('\n').filter((l) => l.trim()).length) : out.trim()
        return { value, via: `${source.cmd.split(' ').slice(0, 4).join(' ')} ...${source.countLines ? ' (line count)' : ''}` }
      }
      case 'file-regex': {
        const m = readFileSync(at(source.file), 'utf8').match(new RegExp(source.regex, 'm'))
        if (!m) return { unavailable: `/${source.regex}/ not found in ${source.file}` }
        return { value: m[1].trim(), via: source.file }
      }
      case 'count-matches': {
        let text = readFileSync(at(source.file), 'utf8')
        if (source.start) {
          const i = text.search(new RegExp(source.start, 'm'))
          if (i < 0) return { unavailable: `start /${source.start}/ not found in ${source.file}` }
          text = text.slice(i)
        }
        if (source.end) {
          const j = text.slice(1).search(new RegExp(source.end, 'm'))
          if (j >= 0) text = text.slice(0, j + 1)
        }
        if (source.commentPrefix) text = text.split('\n').map((l) => l.split(source.commentPrefix)[0]).join('\n')
        return { value: String([...text.matchAll(new RegExp(source.regex, 'g'))].length), via: source.file }
      }
      case 'md-table-items': {
        const lines = readFileSync(at(source.file), 'utf8').split('\n')
        const h = lines.findIndex((l) => l.trim() === source.heading)
        if (h < 0) return { unavailable: `heading "${source.heading}" not found in ${source.file}` }
        const items = []
        let inTable = false
        for (const l of lines.slice(h + 1)) {
          if (/^#{1,6} /.test(l)) break
          if (!l.trim().startsWith('|')) {
            if (inTable) break
            continue
          }
          inTable = true
          const cells = l.split('|').slice(1, -1).map((c) => c.trim())
          if (cells.every((c) => /^:?-+:?$/.test(c))) continue
          items.push(cells)
        }
        const exclude = new Set(source.exclude ?? [])
        const body = items.slice(1) // first row is the header
        const n = body.flatMap((c) => c[source.column ?? 1].split(',').map((s) => s.trim()).filter(Boolean)).filter((s) => !exclude.has(s)).length
        return { value: String(n), via: `${source.file} "${source.heading}" table` }
      }
      case 'csv': {
        let rows = parseCsv(readFileSync(at(source.file), 'utf8')).map((r) => r[source.column])
        if (source.match) rows = rows.filter((v) => new RegExp(source.match).test(v))
        rows.sort()
        const value = source.reduce === 'min' ? rows[0] : source.reduce === 'count' ? String(rows.length) : rows[rows.length - 1]
        return { value, via: `${source.file}:${source.column}` }
      }
      case 'count-files':
        return { value: String(walk(at(source.dir), source.ext).length), via: `${source.ext} files under ${source.dir}` }
      case 'docs-nav-unlisted': {
        const docsDir = at(source.docsDir ?? 'docs')
        const nav = readFileSync(join(docsDir, 'docs.json'), 'utf8')
        const listed = new Set([...nav.matchAll(/"([^"]+)"/g)].map((m) => m[1]))
        const ex = source.exclude ?? []
        const missing = walk(docsDir, '.mdx')
          .map((f) => f.slice(docsDir.length + 1, -4).split('\\').join('/'))
          .filter((p) => !ex.some((e) => p.startsWith(e)) && !listed.has(p))
        return { value: missing.length ? missing.join(', ') : 'none', via: `${source.docsDir ?? 'docs'}/docs.json` }
      }
      default:
        return { unavailable: `unknown source type ${source.type}` }
    }
  } catch (e) {
    const first = String(e.stderr || e.message || e).split('\n').find(Boolean) ?? 'error'
    if (source.fallback) {
      const fb = resolveSource(source.fallback, rootDir)
      if (fb.value != null) return { ...fb, via: `${fb.via} (fallback: ${source.type} failed: ${first.slice(0, 80)})` }
      return fb
    }
    return { unavailable: `${source.type} failed: ${first.slice(0, 120)}` }
  }
}

/**
 * Check one value claim against its page text. Returns { status: PASS|FAIL|UNAVAILABLE, detail }.
 * `sources` caches resolved sources by JSON key so a command runs once per check.
 */
export function checkValueClaim(claim, pageText, { rootDir, sources = new Map() }) {
  const key = JSON.stringify(claim.source)
  if (!sources.has(key)) sources.set(key, resolveSource(claim.source, rootDir))
  const src = sources.get(key)
  const lines = pageText.split('\n')
  const fails = []

  for (const f of claim.forbid ?? []) {
    const re = new RegExp(f, 'i')
    lines.forEach((l, i) => {
      if (re.test(l)) fails.push(`${claim.page}:${i + 1} matches forbidden /${f}/: "${l.trim().slice(0, 100)}"`)
    })
  }

  if (src.unavailable) {
    if (fails.length) return { status: 'FAIL', detail: fails.join('; ') }
    return { status: 'UNAVAILABLE', detail: `source unavailable here (${src.unavailable})` }
  }
  const truth = normValue(src.value)
  const exp = claim.expect ?? {}

  if (exp.pattern) {
    const re = new RegExp(exp.pattern, exp.flags ?? '')
    let found = 0
    lines.forEach((l, i) => {
      for (const m of l.matchAll(new RegExp(re.source, re.flags.includes('g') ? re.flags : re.flags + 'g'))) {
        found++
        // An alternation may hold several groups: the first one that matched is the stated value.
        const stated = normValue(m.slice(1).find((x) => x !== undefined) ?? '')
        if (stated !== truth) fails.push(`${claim.page}:${i + 1} states "${stated}", source says "${truth}" (${src.via})`)
      }
    })
    if (!found) fails.push(`${claim.page}: pattern /${exp.pattern}/ not found on the page (the claim or the page changed); source says "${truth}" (${src.via})`)
  } else if ('value' in exp) {
    if (normValue(exp.value) !== truth) fails.push(`expected "${normValue(exp.value)}" for ${claim.page}, source says "${truth}" (${src.via})`)
  } else {
    fails.push('value claim has neither expect.pattern nor expect.value')
  }
  return fails.length ? { status: 'FAIL', detail: fails.join('; ') } : { status: 'PASS', detail: `"${truth}" (${src.via})` }
}

export const loadJson = (file, fallback) => (existsSync(file) ? JSON.parse(readFileSync(file, 'utf8')) : fallback)

/**
 * Evaluate every claim. Returns { pages: { [page]: { sha256, exists, status, claims: [...] } } } where
 * a page status is FAIL (any value FAIL, or any prose FAIL/UNSETTLED at the current sha),
 * NEEDS REVIEW (a prose claim has no verdict at the current sha, or a value source is unavailable),
 * or OK. `reviewed` (page -> sha256 last recorded by --update) adds `changedSinceReview`.
 */
export function evaluateClaims({ claims, verdicts, rootDir, reviewed = {}, valuesOnly = false }) {
  const byPage = new Map()
  for (const c of claims) {
    if (valuesOnly && c.kind !== 'value') continue
    if (!byPage.has(c.page)) byPage.set(c.page, [])
    byPage.get(c.page).push(c)
  }
  const sources = new Map()
  const pages = {}
  for (const [page, list] of [...byPage].sort(([a], [b]) => a.localeCompare(b))) {
    const file = join(rootDir, page)
    const exists = existsSync(file)
    const text = exists ? readFileSync(file, 'utf8') : ''
    const sha = exists ? sha256(text) : null
    const atSha = verdicts?.pages?.[page]?.[sha]?.claims ?? {}
    const results = list.map((c) => {
      if (!exists) return { id: c.id, kind: c.kind, status: 'FAIL', detail: `page ${page} does not exist` }
      if (c.kind === 'value') return { id: c.id, kind: c.kind, ...checkValueClaim(c, text, { rootDir, sources }) }
      if (c.kind === 'prose') {
        const v = atSha[c.id]
        if (!v) return { id: c.id, kind: c.kind, status: 'NO VERDICT', detail: 'no reviewer verdict at the current page sha256' }
        return { id: c.id, kind: c.kind, status: v.verdict, detail: v.evidence ?? '' }
      }
      return { id: c.id, kind: c.kind, status: 'FAIL', detail: `unknown claim kind ${c.kind}` }
    })
    const anyFail = results.some((r) => r.status === 'FAIL' || r.status === 'UNSETTLED')
    const anyPending = results.some((r) => r.status === 'NO VERDICT' || r.status === 'UNAVAILABLE')
    const recorded = reviewed[page]
    pages[page] = {
      sha256: sha,
      exists,
      status: anyFail ? 'FAIL' : anyPending ? 'NEEDS REVIEW' : 'OK',
      changedSinceReview: recorded != null && recorded !== sha,
      claims: results,
    }
  }
  return { pages }
}

/** A page may be recorded as reviewed only when every claim on it PASSes at its current sha256. */
export function gateReasons(pageResult) {
  if (!pageResult) return []
  return pageResult.claims.filter((r) => r.status !== 'PASS').map((r) => `${r.id}: ${r.status}${r.detail ? ` (${r.detail})` : ''}`)
}

/** Pages a reviewer must look at: any prose claim without a verdict at the current page sha256. */
export function needsReview({ claims, evaluation }) {
  const out = []
  for (const [page, res] of Object.entries(evaluation.pages)) {
    if (!res.exists) continue
    const pending = res.claims.filter((r) => r.kind === 'prose' && r.status === 'NO VERDICT').map((r) => r.id)
    if (!pending.length) continue
    out.push({
      page,
      sha256: res.sha256,
      claims: claims
        .filter((c) => c.page === page && pending.includes(c.id))
        .map((c) => ({ id: c.id, expect: c.expect, sourceFiles: c.source?.files ?? [], note: c.note ?? undefined })),
    })
  }
  return out
}

/**
 * Merge reviewer output into the verdicts file. Input: one { page, sha256, claims: [{ id, verdict, evidence }] }
 * or an array of them. Refuses a page whose sha256 is not its current one, an unknown claim id, a
 * value claim (those are not reviewer-decided), or a verdict outside PASS/FAIL/UNSETTLED.
 */
export function mergeVerdicts(previous, input, { claims, rootDir, reviewer = 'docs-claims-reviewer', now = new Date().toISOString() }) {
  const next = { note: 'Written only by `docsDrift.mjs --record-verdicts`. Keyed by page, then page sha256.', pages: { ...(previous?.pages ?? {}) } }
  const errors = []
  for (const rep of Array.isArray(input) ? input : [input]) {
    const file = join(rootDir, rep.page ?? '')
    if (!rep.page || !existsSync(file)) {
      errors.push(`${rep.page}: no such page`)
      continue
    }
    const current = sha256(readFileSync(file, 'utf8'))
    if (rep.sha256 !== current) {
      errors.push(`${rep.page}: reviewed sha256 ${String(rep.sha256).slice(0, 12)} is not the current ${current.slice(0, 12)}; review again`)
      continue
    }
    const prose = new Map(claims.filter((c) => c.page === rep.page && c.kind === 'prose').map((c) => [c.id, c]))
    const recorded = {}
    for (const v of rep.claims ?? []) {
      if (!prose.has(v.id)) errors.push(`${rep.page}: ${v.id} is not a prose claim on this page`)
      else if (!VERDICTS.includes(v.verdict)) errors.push(`${rep.page}: ${v.id} verdict "${v.verdict}" is not one of ${VERDICTS.join('/')}`)
      else if (v.verdict !== 'PASS' && !String(v.evidence ?? '').trim()) errors.push(`${rep.page}: ${v.id} ${v.verdict} needs evidence`)
      else recorded[v.id] = { verdict: v.verdict, evidence: String(v.evidence ?? ''), at: now }
    }
    if (!Object.keys(recorded).length) continue
    const keep = next.pages[rep.page]?.[current]?.claims ?? {}
    // Only verdicts at the current sha256 are kept: older ones no longer describe the page.
    next.pages[rep.page] = { [current]: { reviewer, recordedAt: now, claims: { ...keep, ...recorded } } }
  }
  return { verdicts: next, errors }
}

export function writeJson(file, data) {
  writeFileSync(file, JSON.stringify(data, null, 2) + '\n')
}
