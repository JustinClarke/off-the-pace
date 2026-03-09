// Loads and types ml/models/manifest.json the browser-inference contract (AD-3, Appendix C).
// Everything about feature order, encoders, and per-model output interpretation is read from
// here at runtime; nothing is hard-coded in the inference layer.

export interface ModelEncoding {
  categorical_columns: string[]
  boolean_columns: string[]
  missing_ordinal: number
  boolean_true_false: [number, number]
  continuous_missing: string
  encoders: Record<string, Record<string, number>>
}

export interface ManifestInput {
  tensor_name: string
  dtype: 'float32'
  shape: [string, number]
  feature_order: string[]
  n_features: number
  encoding: ModelEncoding
}

/** Regression / quantile output: a single scalar at `index`, optionally bounded/clipped. */
export interface ScalarOutput {
  index: number
  meaning: string
  bounds?: [number, number]
  postprocess?: string
}

/** Classifier output: probabilities tensor at `probabilities_index`, mapped to `class_order`. */
export interface ClassifierOutput {
  probabilities_index: number
  zipmap: boolean
  class_order: string[]
  meaning: string
}

export type ModelKind = 'quantile' | 'classification' | 'regression'

export interface ModelSpec {
  name: string
  family: string
  kind: ModelKind
  objective: string
  onnx: string
  onnx_sha256: string
  booster_sha256: string
  cv_headline: number
  headline_metric: string
  quantile_alpha?: number
  output: ScalarOutput | ClassifierOutput
}

export interface ModelManifest {
  manifest_schema_version: number
  name: string
  model_version: string
  generated_at: string
  input: ManifestInput
  models: ModelSpec[]
  cliff_class_labels: string[]
  predictions_schema: string[]
  provenance: {
    source_mart: string
    training_seasons: number[]
    holdout_season: number
    dataset_fingerprint: string
    random_state: number
    library_versions: Record<string, string>
    onnx_parity: {
      atol: number
      rtol: number
      max_abs_diff: Record<string, number>
      all_pass: boolean
    }
  }
  related: { model_card: string; encoders: string }
}

export function isClassifierOutput(o: ScalarOutput | ClassifierOutput): o is ClassifierOutput {
  return 'probabilities_index' in o
}

import { DATA_CDN_BASE } from '../data/manifest'

/** Base URL the ONNX models + manifest are served from (GitHub Pages CDN). */
export const MODELS_BASE = `${DATA_CDN_BASE}/models`

let cached: ModelManifest | null = null

export async function loadModelManifest(): Promise<ModelManifest> {
  if (cached) return cached
  const res = await fetch(`${MODELS_BASE}/manifest.json`)
  if (!res.ok) throw new Error(`Failed to load model manifest: ${res.status}`)
  cached = (await res.json()) as ModelManifest
  return cached
}

export function getModelSpec(manifest: ModelManifest, name: string): ModelSpec {
  const spec = manifest.models.find(m => m.name === name)
  if (!spec) throw new Error(`Model not found in manifest: ${name}`)
  return spec
}

/** Test-only: inject a manifest so unit tests don't fetch. */
export function __setCachedManifest(m: ModelManifest | null): void {
  cached = m
}
