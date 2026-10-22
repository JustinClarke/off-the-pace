// Build-time page summaries for the assistant's explain_page tool (AI-10).
//
// Reads docs/app/**/*.mdx and writes pageSummaries.generated.json. Every summary is cut to
// SUMMARY_BUDGET_TOKENS or less. Caveats (<Note>, <Warning>, <Tip> blocks and the "Reading the
// signal correctly" section) are never dropped: if a page's caveats cannot fit, the build fails
// instead of silently losing one.
//
// Per-page rule: if app/src/nav/assistant-docs/<slug>.md exists, the summary is built from that
// AI-facing source instead of docs/app/<slug>.mdx (same parser, same budget). Every other page
// is built from its docs page exactly as before. An AI-sourced entry also records the sha256 of
// both files, so --check fails when either changes without regenerating.
//
//   node src/nav/pageSummaries.mjs           write the generated file
//   node src/nav/pageSummaries.mjs --check   exit 1 if the file is stale or any page is over budget
import { readFileSync, writeFileSync, readdirSync, existsSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

export const SUMMARY_BUDGET_TOKENS = 800
export const TOKEN_ESTIMATE = 'ceil(characters / 3.5)'

const here = dirname(fileURLToPath(import.meta.url))
export const DOCS_APP_DIR = join(here, '..', '..', '..', 'docs', 'app')
export const OUT_FILE = join(here, 'pageSummaries.generated.json')
/** AI-facing page sources, outside docs/ so the published Mintlify pages stay untouched. */
export const ASSISTANT_DOCS_DIR = join(here, 'assistant-docs')

const sha256 = (text) => createHash('sha256').update(text).digest('hex')

/** Path of the AI-facing source for a docs slug, or null when the page uses its docs page. */
export function assistantSourceFor(slug, dir = ASSISTANT_DOCS_DIR) {
  const p = join(dir, `${slug}.md`)
  return existsSync(p) ? p : null
}

/** Conservative token estimate. English prose with identifiers runs about 4 chars/token; 3.5 over-counts. */
export function estimateTokens(text) {
  return Math.ceil(text.length / 3.5)
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

function parseFrontmatter(src) {
  const m = src.match(/^---\n([\s\S]*?)\n---\n?/)
  const fm = {}
  if (!m) return { fm, body: src }
  for (const line of m[1].split('\n')) {
    const kv = line.match(/^(\w+):\s*"?(.*?)"?\s*$/)
    if (kv) fm[kv[1]] = kv[2]
  }
  return { fm, body: src.slice(m[0].length) }
}

/** Strip JSX/markup to plain text the model can read. Keeps bullets, bold and inline code. */
function clean(text) {
  return text
    .replace(/<span[^>]*>([\s\S]*?)<\/span>/g, '$1')
    .replace(/<\/?(Note|Warning|Tip|Info|Frame)[^>]*>/g, '')
    .replace(/<CardGroup[\s\S]*?<\/CardGroup>/g, '')
    .replace(/<Card[\s\S]*?(<\/Card>|\/>)/g, '')
    .replace(/<\/?[A-Za-z][^>\n]*>/g, '')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/[ \t]{2,}/g, ' ')
    .trim()
}

/** Split an MDX body into ordered blocks with a keep-priority (lower number is kept first). */
function toBlocks(body) {
  const blocks = []
  // Pull callouts out first so they stay whole.
  const callouts = []
  const stripped = body.replace(/<(Note|Warning|Tip)[^>]*>([\s\S]*?)<\/\1>/g, (_, tag, inner) => {
    callouts.push({ tag, text: clean(inner) })
    return `\n@@CALLOUT${callouts.length - 1}@@\n`
  })
  const parts = stripped.split(/^(?=##\s)/m)
  let first = true
  for (const part of parts) {
    const heading = part.match(/^##\s+(.*)\n/)
    const name = heading ? heading[1].trim() : ''
    const lower = name.toLowerCase()
    // Priority: 0 caveat (must keep), 1 intro and "what it shows", 2 method/how-to, 3 data source/other.
    let priority = 2
    if (first && !heading) priority = 0.5
    else if (/reading the signal|does not claim|caveat|limit/.test(lower)) priority = 0
    else if (/what (it|the .*) shows|what this pillar does|architecture/.test(lower)) priority = 1
    else if (/data source|data lineage|data shape|every feature|explore by pillar|available visualizations/.test(lower)) priority = 3
    first = false
    // Re-split into callouts and prose so callouts are individually protected.
    const pieces = part.split(/(@@CALLOUT\d+@@)/)
    for (const piece of pieces) {
      const c = piece.match(/^@@CALLOUT(\d+)@@$/)
      if (c) {
        const { tag, text } = callouts[Number(c[1])]
        if (text) blocks.push({ priority: 0, caveat: true, text: `${tag.toUpperCase()}: ${text}` })
      } else {
        const t = clean(piece)
        if (!t) continue
        // One block per paragraph, so a long section can be cut at a paragraph boundary.
        // A heading is glued to the paragraph after it, so a dropped section leaves no empty heading.
        let pending = ''
        for (const para of t.split(/\n\n/)) {
          const p = para.trim()
          if (!p) continue
          if (/^#{2,6}\s[^\n]*$/.test(p)) {
            pending = p + '\n\n'
            continue
          }
          // Every paragraph of a "Reading the signal correctly" section is protected like a callout.
          blocks.push({ priority: priority === 0 ? 0.2 : priority, caveat: priority === 0, text: pending + p })
          pending = ''
        }
        // A trailing heading with no body would be an empty heading: keep it out.
      }
    }
  }
  return blocks
}

/** Build one summary of at most budget tokens. Throws if the caveats alone cannot fit. */
export function summarise(slug, src, budget = SUMMARY_BUDGET_TOKENS) {
  const { fm, body } = parseFrontmatter(src)
  const head = `${fm.title ?? slug}${fm.description ? `\n${fm.description}` : ''}`
  const blocks = toBlocks(body).map((b, i) => ({ ...b, i }))
  const kept = new Set()
  let used = estimateTokens(head)
  const sep = 2 // blank line between blocks, in chars; folded in below
  const cost = (b) => estimateTokens(b.text) + Math.ceil(sep / 3.5)
  const order = [...blocks].sort((a, b) => a.priority - b.priority || a.i - b.i)
  for (const b of order) {
    if (used + cost(b) <= budget) {
      kept.add(b.i)
      used += cost(b)
    } else if (b.caveat) {
      throw new Error(`${slug}: caveat block does not fit in ${budget} tokens (needs ${cost(b)}, ${budget - used} left)`)
    } else {
      // Trim a prose block to whole sentences/lines that fit; never trim caveats.
      const room = (budget - used) * 3.5 - 8
      if (room > 150) {
        const lines = b.text.split(/(?<=[.!?])\s+|\n/)
        let acc = ''
        for (const l of lines) {
          if ((acc + l + ' ').length > room) break
          acc += l + ' '
        }
        if (acc.trim()) {
          b.text = acc.trim() + ' [...]'
          kept.add(b.i)
          used += cost(b)
        }
      }
    }
  }
  const summary = [head, ...blocks.filter((b) => kept.has(b.i)).map((b) => b.text)].join('\n\n')
  const tokens = estimateTokens(summary)
  if (tokens > budget) throw new Error(`${slug}: summary is ${tokens} tokens, over the ${budget} budget`)
  return { title: fm.sidebarTitle ? fm.title : (fm.title ?? slug), summary, tokens }
}

export function buildAll(docsDir = DOCS_APP_DIR, assistantDir = ASSISTANT_DOCS_DIR) {
  const pages = {}
  for (const file of listMdx(docsDir)) {
    const slug = relative(docsDir, file).replace(/\.mdx$/, '')
    const human = readFileSync(file, 'utf8')
    const aiPath = assistantSourceFor(slug, assistantDir)
    if (!aiPath) {
      pages[slug] = summarise(slug, human)
      continue
    }
    const ai = readFileSync(aiPath, 'utf8')
    pages[slug] = {
      ...summarise(slug, ai.replace(/<!--[\s\S]*?-->\n?/g, '')),
      source: relative(join(here, '..', '..', '..'), aiPath),
      sourceSha256: sha256(ai),
      docsSha256: sha256(human),
    }
  }
  return { tokenEstimate: TOKEN_ESTIMATE, budgetTokens: SUMMARY_BUDGET_TOKENS, pages }
}

export function serialise(data) {
  return JSON.stringify(data, null, 2) + '\n'
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const out = serialise(buildAll())
  if (process.argv.includes('--check')) {
    const cur = existsSync(OUT_FILE) ? readFileSync(OUT_FILE, 'utf8') : ''
    if (cur !== out) {
      console.error('pageSummaries.generated.json is stale: run `node src/nav/pageSummaries.mjs`')
      process.exit(1)
    }
    console.log('page summaries up to date')
  } else {
    writeFileSync(OUT_FILE, out)
    console.log(`wrote ${OUT_FILE}`)
  }
}
