// Opt-in headless parity proof (F3 acceptance): real laps scored with onnxruntime-web
// through the actual featureVector + post-processing helpers, compared to booster-scored
// ground truth (the in-browser analogue of manifest.provenance.onnx_parity). Gated behind
// RUN_PARITY=1 because it needs the exported parquet + ONNX models and the python-dumped rows.
//
// Ground truth comes from scoring the .bst boosters on the SAME reconstructed feature vector
// (not the stored mart_degradation_predictions, which is stale vs the current warehouse see
// scripts/dump_parity_rows.py). This makes the check a true ONNX↔booster integrity proof.
//
//   make app-data app-models                                   # parquet + onnx present
//   PYTHONPATH=. ./.venv/bin/python scripts/dump_parity_rows.py # writes /tmp/parity_rows.json
//   cd app && RUN_PARITY=1 ./node_modules/.bin/vitest run src/ml/parity.node.test.ts --environment node
import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import * as ort from 'onnxruntime-web'
import { buildFeatureVector, type FeatureRow } from './featureVector'
import { postProcessScalars, classifyProbs } from './infer'
import type { ModelManifest, ScalarOutput, ClassifierOutput } from './manifest'

const ROWS_PATH = '/tmp/parity_rows.json'
const run = process.env.RUN_PARITY === '1' && existsSync(ROWS_PATH)

describe.runIf(run)('in-browser ONNX parity vs booster ground truth', () => {
  it('matches booster predictions within tolerance on real 2024 laps', async () => {
    const root = join(__dirname, '../..')
    const manifest = JSON.parse(readFileSync(join(root, 'public/models/manifest.json'), 'utf8')) as ModelManifest
    const rows = JSON.parse(readFileSync(ROWS_PATH, 'utf8')) as Array<Record<string, unknown>>

    ort.env.wasm.wasmPaths = join(root, 'node_modules/onnxruntime-web/dist/')
    ort.env.wasm.numThreads = 1

    const spec = Object.fromEntries(manifest.models.map(m => [m.name, m]))
    const load = (name: string) => ort.InferenceSession.create(join(root, 'public/models', spec[name].onnx))
    const [p10s, p50s, p90s, lifes, clf] = await Promise.all([
      load('degradation_regressor_p10'), load('degradation_regressor_p50'),
      load('degradation_regressor_p90'), load('stint_life_regressor'), load('cliff_classifier'),
    ])

    const nf = manifest.input.n_features
    const n = rows.length
    const mat = new Float32Array(n * nf)
    rows.forEach((r, i) => mat.set(buildFeatureVector(r as FeatureRow, manifest.input), i * nf))
    const runSess = async (s: ort.InferenceSession) =>
      (await s.run({ [s.inputNames[0]]: new ort.Tensor('float32', mat, [n, nf]) }))

    const o10 = (await runSess(p10s))[p10s.outputNames[0]].data as Float32Array
    const o50 = (await runSess(p50s))[p50s.outputNames[0]].data as Float32Array
    const o90 = (await runSess(p90s))[p90s.outputNames[0]].data as Float32Array
    const olife = (await runSess(lifes))[lifes.outputNames[0]].data as Float32Array
    const cOut = spec.cliff_classifier.output as ClassifierOutput
    const oprob = (await runSess(clf))[clf.outputNames[cOut.probabilities_index]].data as Float32Array
    const classOrder = cOut.class_order
    const k = classOrder.length
    const bounds = (spec.degradation_regressor_p50.output as ScalarOutput).bounds

    let maxAbs = 0
    let cliffMiss = 0
    for (let i = 0; i < n; i++) {
      const s = postProcessScalars(o10[i], o50[i], o90[i], olife[i], bounds)
      const cliff = classifyProbs(oprob.subarray(i * k, i * k + k), classOrder)
      const r = rows[i]
      for (const [b, m] of [
        [s.degradation_jump_s, Number(r.m_p50)],
        [s.degradation_jump_p10_s, Number(r.m_p10)],
        [s.degradation_jump_p90_s, Number(r.m_p90)],
        [s.remaining_stint_life_laps, Number(r.m_life)],
      ] as const) {
        maxAbs = Math.max(maxAbs, Math.abs(b-m))
      }
      if (cliff.label !== r.m_cliff) cliffMiss++
    }

    console.log(`parity: ${n} laps, maxAbs=${maxAbs.toExponential(3)}, cliffMismatches=${cliffMiss}`)
    expect(maxAbs).toBeLessThanOrEqual(1e-3)
    expect(cliffMiss).toBe(0)
  }, 60_000)
})
