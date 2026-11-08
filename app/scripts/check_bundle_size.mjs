#!/usr/bin/env node
// Bundle-size budget gate (Phase 5 / F9 of SYSTEM_DESIGN_AUDIT.md). The app ships a large JS payload
// (lazy route chunks + the self-hosted DuckDB-wasm and onnxruntime-web JS workers); without a budget,
// a stray heavyweight import silently bloats every visitor's download. This sums the *JavaScript*
// bytes in dist/ (raw + gzip, .wasm binaries excluded - "pre-wasm" per the audit) and fails if any
// metric exceeds app/perf-budget.json. Deterministic + offline: it reads the built artefact only.
//
//   node scripts/check_bundle_size.mjs            # check dist/ against the committed budget (CI gate)
//   node scripts/check_bundle_size.mjs --update   # rewrite the budget from the current build (+ headroom)
//
// Split budget (AX-14 ruling 1): a build with VITE_ASSISTANT_ENABLED=true also ships the lazy assistant chunks
// (everything reachable ONLY through the lazy AssistantLauncher import). Those are measured separately from the
// Vite manifest (build with `vite build --manifest`) and checked against maxAssistant* limits; every other JS file
// is checked against the unchanged global limits, so a flag-on build cannot hide a regression in the main app.
// A flag-off build has no launcher chunk and is checked exactly as before. `--dist <dir>` checks a scratch build.
//
// Run `pnpm build` first. The budget carries ~8% headroom so ordinary churn doesn't flake the gate;
// regenerate it deliberately (make app-bundle-budget-update) when a real size change is intended.

import { readdirSync, statSync, readFileSync, writeFileSync, existsSync } from 'node:fs'
import { join, dirname, extname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { gzipSync } from 'node:zlib'

const appRoot = join(dirname(fileURLToPath(import.meta.url)), '..')
const distArg = process.argv.indexOf('--dist')
const DIST = distArg > -1 && process.argv[distArg + 1] ? resolve(process.argv[distArg + 1]) : join(appRoot, 'dist')
const BUDGET_FILE = join(appRoot, 'perf-budget.json')
const HEADROOM = 1.08 // budgets written by --update get 8% slack above the current build
const ASSISTANT_HEADROOM = 1.1 // assistant limits: measured + 10%, rounded up to the next 10 KB
const LAUNCHER_SRC = 'assistant/drawer/AssistantLauncher.tsx'
const JS_EXT = new Set(['.js', '.mjs', '.cjs'])

const update = process.argv.includes('--update')
const kb = (b) => (b / 1024).toFixed(1)
const mb = (b) => (b / (1024 * 1024)).toFixed(2)

function walk(dir) {
  const out = []
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    const st = statSync(p)
    if (st.isDirectory()) out.push(...walk(p))
    else if (JS_EXT.has(extname(name))) out.push({ path: p, size: st.size })
  }
  return out
}

if (!existsSync(DIST)) {
  console.error('❌  dist/ not found; run `pnpm build` before checking the bundle size.')
  process.exit(1)
}

const files = walk(DIST)
if (files.length === 0) {
  console.error('❌  no JS assets found under dist/; did the build succeed?')
  process.exit(1)
}

// Files reachable only through the lazy launcher import (needs the Vite manifest).
function assistantOnlyFiles() {
  const manifestPath = join(DIST, '.vite', 'manifest.json')
  const hasLauncherChunk = files.some((f) => /AssistantLauncher-[^/]*\.js$/.test(f.path))
  if (!existsSync(manifestPath)) {
    if (hasLauncherChunk) {
      console.error('❌  this build contains the assistant launcher chunk but no .vite/manifest.json; rebuild with `vite build --manifest`.')
      process.exit(1)
    }
    return new Set()
  }
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'))
  const launcherKey = Object.keys(manifest).find((k) => k.endsWith(LAUNCHER_SRC))
  if (!launcherKey) return new Set() // flag-off build: nothing assistant-only
  const reach = (roots, skip) => {
    const seen = new Set()
    const stack = [...roots]
    while (stack.length) {
      const k = stack.pop()
      if (seen.has(k) || k === skip || !manifest[k]) continue
      seen.add(k)
      stack.push(...(manifest[k].imports ?? []), ...(manifest[k].dynamicImports ?? []))
    }
    return seen
  }
  const rest = reach(Object.keys(manifest).filter((k) => manifest[k].isEntry), launcherKey)
  const launcher = reach([launcherKey], null)
  const out = new Set()
  for (const k of launcher) if (!rest.has(k)) out.add(join(DIST, manifest[k].file))
  return out
}

const assistantSet = assistantOnlyFiles()
const sum = (list) => {
  let total = 0
  let gz = 0
  let big = { path: '', size: 0 }
  for (const f of list) {
    total += f.size
    gz += gzipSync(readFileSync(f.path)).length
    if (f.size > big.size) big = f
  }
  return { totalJsBytes: total, gzipJsBytes: gz, largestJsBytes: big.size, largest: big }
}
const mainFiles = files.filter((f) => !assistantSet.has(f.path))
const asstFiles = files.filter((f) => assistantSet.has(f.path))
const main = sum(mainFiles)
const asst = asstFiles.length ? sum(asstFiles) : null
const totalJsBytes = main.totalJsBytes
const gzipJsBytes = main.gzipJsBytes
const largest = main.largest
const measured = { totalJsBytes, gzipJsBytes, largestJsBytes: main.largestJsBytes }
const roundUp10k = (b) => Math.ceil((b * ASSISTANT_HEADROOM) / 10240) * 10240

if (update) {
  const budget = {
    _comment:
      'Bundle-size budget for app/scripts/check_bundle_size.mjs (Phase 5 / F9). JS bytes in dist/ ' +
      '(.wasm excluded). Regenerate with `make app-bundle-budget-update` after an intentional size change.',
    maxTotalJsBytes: Math.ceil((totalJsBytes * HEADROOM) / 1024) * 1024,
    maxGzipJsBytes: Math.ceil((gzipJsBytes * HEADROOM) / 1024) * 1024,
    maxLargestJsBytes: Math.ceil((largest.size * HEADROOM) / 1024) * 1024,
  }
  const prev = existsSync(BUDGET_FILE) ? JSON.parse(readFileSync(BUDGET_FILE, 'utf8')) : {}
  if (asst) {
    budget.maxAssistantTotalJsBytes = roundUp10k(asst.totalJsBytes)
    budget.maxAssistantGzipJsBytes = roundUp10k(asst.gzipJsBytes)
    budget.maxAssistantLargestJsBytes = roundUp10k(asst.largestJsBytes)
  } else {
    for (const k of ['maxAssistantTotalJsBytes', 'maxAssistantGzipJsBytes', 'maxAssistantLargestJsBytes']) if (prev[k] !== undefined) budget[k] = prev[k]
  }
  writeFileSync(BUDGET_FILE, JSON.stringify(budget, null, 2) + '\n')
  console.log(`✅  wrote ${BUDGET_FILE} (+${Math.round((HEADROOM - 1) * 100)}% headroom)`)
  console.log(`    total JS ${mb(totalJsBytes)} MB · gzip ${mb(gzipJsBytes)} MB · largest ${kb(largest.size)} KB`)
  process.exit(0)
}

if (!existsSync(BUDGET_FILE)) {
  console.error(`❌  ${BUDGET_FILE} missing; seed it with: node scripts/check_bundle_size.mjs --update`)
  process.exit(1)
}
const budget = JSON.parse(readFileSync(BUDGET_FILE, 'utf8'))

const checks = [
  ['total JS (raw)', measured.totalJsBytes, budget.maxTotalJsBytes, mb, 'MB'],
  ['total JS (gzip)', measured.gzipJsBytes, budget.maxGzipJsBytes, mb, 'MB'],
  ['largest chunk', measured.largestJsBytes, budget.maxLargestJsBytes, kb, 'KB'],
]

if (asst) {
  checks.push(
    ['assistant (raw)', asst.totalJsBytes, budget.maxAssistantTotalJsBytes, kb, 'KB'],
    ['assistant (gzip)', asst.gzipJsBytes, budget.maxAssistantGzipJsBytes, kb, 'KB'],
    ['assistant largest', asst.largestJsBytes, budget.maxAssistantLargestJsBytes, kb, 'KB'],
  )
  if (checks.slice(-3).some((c) => typeof c[2] !== 'number')) {
    console.error('❌  assistant chunks present but perf-budget.json has no maxAssistant* limits; seed with --update.')
    process.exit(1)
  }
}

console.log(`── Bundle-size budget (${mainFiles.length} JS assets${asst ? ` + ${asstFiles.length} assistant-only` : ''} in ${DIST.replace(appRoot + '/', '')}) ──`)
let failed = false
for (const [label, actual, max, fmt, unit] of checks) {
  const pct = ((actual / max) * 100).toFixed(0)
  const within = actual <= max
  if (!within) failed = true
  console.log(
    `  ${within ? '✓' : '✗'} ${label.padEnd(18)} ${fmt(actual).padStart(7)} / ${fmt(max).padStart(7)} ${unit}  (${pct}% of budget)`,
  )
}
if (largest.path) console.log(`    largest: ${largest.path.replace(appRoot + '/', '')}`)

if (failed) {
  console.error(
    '\n❌  bundle exceeds budget. Investigate the regression (lazy-load it, or `make app-bundle-budget-update` if intentional).',
  )
  process.exit(1)
}
console.log('\n✅  bundle within budget.')
