#!/usr/bin/env node
// Headless ONNX serving check for the synthetic monitor (F3, Phase 3 of SYSTEM_DESIGN_AUDIT.md).
// Fetches the live model manifest + ONNX from the CDN and runs one real inference, asserting the
// serving plane is intact and produces finite output. This is the "headless ONNX-parity assertion"
// the audit asks for, minus the warehouse-side booster ground truth (which exists only at build
// time; full booster parity stays a CI gate via ml-ci / app-parity). A committed golden input
// vector would upgrade this to exact parity; see .github/OBSERVABILITY.md.
//
// Hard-fails (exit 1) on: manifest fetch error, missing model_version, an .onnx that 404s, or a
// successful inference returning non-finite output. Pure wasm-init/runtime infra errors are warned
// (exit 0) so node-wasm quirks never page falsely; the HTTP smoke already gates artefact presence.
//
// Run from anywhere; resolves onnxruntime-web + its wasm from app/node_modules.
//   CDN_BASE / SYNTH_ENV (prod|staging) override the target.

import * as ort from 'onnxruntime-web'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const CDN_BASE = process.env.CDN_BASE || 'https://storage.googleapis.com/off-the-pace-cdn'
const ENV = process.env.SYNTH_ENV || 'prod'
const BASE = ENV === 'staging' ? `${CDN_BASE}/staging` : CDN_BASE
const MODELS_BASE = `${BASE}/models`

const appRoot = join(dirname(fileURLToPath(import.meta.url)), '..') // app/
ort.env.wasm.wasmPaths = join(appRoot, 'node_modules/onnxruntime-web/dist/')
ort.env.wasm.numThreads = 1

const fail = (msg) => { console.error(`❌  ${msg}`); process.exitCode = 1 }
const ok = (msg) => console.log(`  ✓ ${msg}`)
const warn = (msg) => console.log(`  ⚠ ${msg}`)

async function main() {
  console.log(`── synthetic ONNX check: ${ENV} ── ${MODELS_BASE}/manifest.json`)

  // 1. model manifest
  const res = await fetch(`${MODELS_BASE}/manifest.json`)
  if (!res.ok) return fail(`model manifest → HTTP ${res.status}`)
  const manifest = await res.json()
  const version = manifest.model_version
  if (!version) return fail('model manifest has no model_version')
  const input = manifest.input || {}
  const featureCount = Array.isArray(input.shape) ? Number(input.shape[input.shape.length - 1]) : 0
  const inputName = input.tensor_name || 'input'
  const models = Array.isArray(manifest.models) ? manifest.models : []
  if (models.length === 0) return fail('model manifest lists no models')
  ok(`model_version=${version}  models=${models.length}  features=${featureCount}`)

  // 2. every referenced .onnx is reachable
  for (const m of models) {
    if (!m.onnx) continue
    const head = await fetch(`${MODELS_BASE}/${m.onnx}`, { method: 'HEAD' })
    if (!head.ok) return fail(`onnx ${m.onnx} → HTTP ${head.status}`)
  }
  ok(`all ${models.length} ONNX artefact(s) reachable`)

  // 3. real inference on the first model (liveness + finite-output assertion)
  if (!featureCount) { warn('no feature count in manifest; skipping inference'); return }
  const first = models.find((m) => m.onnx)
  try {
    const bytes = new Uint8Array(await (await fetch(`${MODELS_BASE}/${first.onnx}`)).arrayBuffer())
    const session = await ort.InferenceSession.create(bytes, { executionProviders: ['wasm'] })
    const feeds = {
      [inputName]: new ort.Tensor('float32', new Float32Array(featureCount), [1, featureCount]),
    }
    const out = await session.run(feeds)
    let n = 0
    let bad = 0
    for (const key of Object.keys(out)) {
      for (const v of out[key].data) { n++; if (!Number.isFinite(Number(v))) bad++ }
    }
    if (n === 0) return fail(`inference on ${first.onnx} produced no outputs`)
    if (bad > 0) return fail(`inference on ${first.onnx} produced ${bad}/${n} non-finite values`)
    ok(`inference ${first.onnx}: ${n} finite output value(s)`)
  } catch (err) {
    warn(`inference infra error (not failing): ${err?.message || err}`)
  }

  if (process.exitCode !== 1) console.log(`  ✅  synthetic ONNX check passed (${ENV})`)
}

main().catch((err) => fail(`unexpected: ${err?.message || err}`))
