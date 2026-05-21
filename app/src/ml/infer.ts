// Runs the five tyre-degradation models in the browser and post-processes each output
// per the manifest contract (AD-3, Appendix C):
//   degradation_regressor_p10/p50/p90 → scalar at output index 0, clamp [-10, 10]
//   cliff_classifier                  → probabilities tensor (output index 1), argmax → label
//   stint_life_regressor              → scalar at output index 0, clip(>=0)
//
// The quantile trio is row-sorted (p10 ≤ p50 ≤ p90) to match predict.py's crossing guard,
// so a browser score lines up byte-for-byte with mart_degradation_predictions.

import { loadModelManifest, getModelSpec, isClassifierOutput, ModelManifest, ScalarOutput } from './manifest'
import { buildFeatureMatrix, FeatureRow } from './featureVector'
import { getSession, runSerial, ort } from './session'

const QUANTILE_MODELS = ['degradation_regressor_p10', 'degradation_regressor_p50', 'degradation_regressor_p90'] as const
const CLASSIFIER_MODEL = 'cliff_classifier'
const STINT_LIFE_MODEL = 'stint_life_regressor'

export interface CliffPrediction {
  label: string
  probabilities: Record<string, number> // class_order → prob
}

export interface LapPrediction {
  /** Row-sorted, clamped degradation jump in seconds. */
  degradation_jump_p10_s: number
  degradation_jump_s: number // p50
  degradation_jump_p90_s: number
  cliff: CliffPrediction
  remaining_stint_life_laps: number
}

function clamp(x: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, x))
}

/**
 * Pure post-processing for the four scalar outputs of one lap (exported for unit tests):
 * row-sort the quantile trio, clamp each to bounds, clip stint-life at 0. Mirrors predict.py.
 */
export function postProcessScalars(
  p10: number, p50: number, p90: number, life: number,
  bounds: [number, number] = [-10, 10],
): Omit<LapPrediction, 'cliff'> {
  const sorted = [p10, p50, p90].sort((a, b) => a-b)
  return {
    degradation_jump_p10_s: clamp(sorted[0], bounds[0], bounds[1]),
    degradation_jump_s: clamp(sorted[1], bounds[0], bounds[1]),
    degradation_jump_p90_s: clamp(sorted[2], bounds[0], bounds[1]),
    remaining_stint_life_laps: Math.max(0, life),
  }
}

/** Pure argmax over a probabilities row → {label, probabilities} (exported for unit tests). */
export function classifyProbs(probsRow: ArrayLike<number>, classOrder: string[]): CliffPrediction {
  let argmax = 0
  const probabilities: Record<string, number> = {}
  for (let c = 0; c < classOrder.length; c++) {
    probabilities[classOrder[c]] = probsRow[c]
    if (probsRow[c] > probsRow[argmax]) argmax = c
  }
  return { label: classOrder[argmax], probabilities }
}

/** Run one single-output model over a feature matrix; returns the scalar per row at output index 0. */
async function runScalar(modelName: string, matrix: Float32Array, nRows: number, nFeatures: number): Promise<Float32Array> {
  const session = await getSession(modelName)
  const input = new ort.Tensor('float32', matrix, [nRows, nFeatures])
  const out = await runSerial(modelName, session, { [session.inputNames[0]]: input })
  const spec = getModelSpec(await loadModelManifest(), modelName)
  const idx = (spec.output as ScalarOutput).index
  const tensor = out[session.outputNames[idx]]
  return tensor.data as Float32Array
}

/**
 * Score N rows. Returns one LapPrediction per row, post-processed per the manifest.
 * All five models run; the quantile trio is sorted then clamped.
 */
export async function predictLaps(rows: FeatureRow[]): Promise<LapPrediction[]> {
  const manifest = await loadModelManifest()
  const { n_features } = manifest.input
  const nRows = rows.length
  if (nRows === 0) return []

  const matrix = buildFeatureMatrix(rows, manifest.input)

  // Quantile trio + stint-life run as plain scalar models; classifier handled separately.
  const [p10, p50, p90, life, cliff] = await Promise.all([
    runScalar(QUANTILE_MODELS[0], matrix, nRows, n_features),
    runScalar(QUANTILE_MODELS[1], matrix, nRows, n_features),
    runScalar(QUANTILE_MODELS[2], matrix, nRows, n_features),
    runScalar(STINT_LIFE_MODEL, matrix, nRows, n_features),
    runClassifier(manifest, matrix, nRows, n_features),
  ])

  const degBounds = (getModelSpec(manifest, QUANTILE_MODELS[1]).output as ScalarOutput).bounds ?? [-10, 10]

  const out: LapPrediction[] = new Array(nRows)
  for (let r = 0; r < nRows; r++) {
    out[r] = { ...postProcessScalars(p10[r], p50[r], p90[r], life[r], degBounds), cliff: cliff[r] }
  }
  return out
}

/** Convenience wrapper for a single row. */
export async function predictLap(row: FeatureRow): Promise<LapPrediction> {
  return (await predictLaps([row]))[0]
}

async function runClassifier(manifest: ModelManifest, matrix: Float32Array, nRows: number, nFeatures: number): Promise<CliffPrediction[]> {
  const spec = getModelSpec(manifest, CLASSIFIER_MODEL)
  if (!isClassifierOutput(spec.output)) throw new Error('cliff_classifier manifest output is not a classifier output')
  const { probabilities_index, class_order } = spec.output

  const session = await getSession(CLASSIFIER_MODEL)
  const input = new ort.Tensor('float32', matrix, [nRows, nFeatures])
  const out = await runSerial(CLASSIFIER_MODEL, session, { [session.inputNames[0]]: input })

  // The v1 export emits a plain [batch, nClasses] float tensor at the probabilities output
  // (no ZipMap F4 spike resolved: ort-web reads it directly). Honour the manifest index.
  const probs = out[session.outputNames[probabilities_index]].data as Float32Array
  const k = class_order.length

  const results: CliffPrediction[] = new Array(nRows)
  for (let r = 0; r < nRows; r++) {
    results[r] = classifyProbs(probs.subarray(r * k, r * k + k), class_order)
  }
  return results
}
