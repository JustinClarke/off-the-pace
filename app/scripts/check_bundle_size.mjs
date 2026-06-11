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
// Run `pnpm build` first. The budget carries ~8% headroom so ordinary churn doesn't flake the gate;
// regenerate it deliberately (make app-bundle-budget-update) when a real size change is intended.

import { readdirSync, statSync, readFileSync, writeFileSync, existsSync } from 'node:fs'
import { join, dirname, extname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { gzipSync } from 'node:zlib'

const appRoot = join(dirname(fileURLToPath(import.meta.url)), '..')
const DIST = join(appRoot, 'dist')
const BUDGET_FILE = join(appRoot, 'perf-budget.json')
const HEADROOM = 1.08 // budgets written by --update get 8% slack above the current build
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

let totalJsBytes = 0
let gzipJsBytes = 0
let largest = { path: '', size: 0 }
for (const f of files) {
  totalJsBytes += f.size
  gzipJsBytes += gzipSync(readFileSync(f.path)).length
  if (f.size > largest.size) largest = f
}
const measured = { totalJsBytes, gzipJsBytes, largestJsBytes: largest.size }

if (update) {
  const budget = {
    _comment:
      'Bundle-size budget for app/scripts/check_bundle_size.mjs (Phase 5 / F9). JS bytes in dist/ ' +
      '(.wasm excluded). Regenerate with `make app-bundle-budget-update` after an intentional size change.',
    maxTotalJsBytes: Math.ceil((totalJsBytes * HEADROOM) / 1024) * 1024,
    maxGzipJsBytes: Math.ceil((gzipJsBytes * HEADROOM) / 1024) * 1024,
    maxLargestJsBytes: Math.ceil((largest.size * HEADROOM) / 1024) * 1024,
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

console.log(`── Bundle-size budget (${files.length} JS assets in dist/) ──`)
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
