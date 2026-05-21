// Builds the positional Float32Array[38] the ONNX models expect (AD-3, Appendix C),
// mirroring ml/src/features.py:_encode_frame exactly so browser inference matches training.
//
//   categoricals  → encoder lookup; NULL / unseen → missing_ordinal (-1)
//   booleans      → true→1, false→0; NULL → NaN
//   continuous    → numeric; NULL / non-numeric → NaN (XGBoost native-missing; never impute)
//
// The feature object is a raw row (DuckDB result or simulator state): keys are the warehouse
// column names in manifest.input.feature_order; values may be string | number | boolean | null.

import { ManifestInput } from './manifest'

export type FeatureValue = string | number | boolean | bigint | null | undefined

/** A raw feature row keyed by warehouse column name (a superset of feature_order is fine). */
export type FeatureRow = Record<string, FeatureValue>

function toNumberOrNaN(v: FeatureValue): number {
  if (v === null || v === undefined) return NaN
  if (typeof v === 'boolean') return v ? 1 : 0
  if (typeof v === 'bigint') return Number(v)
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isNaN(n) ? NaN : n
}

/**
 * Encode a single feature value per its column's role in the manifest encoding.
 * Exported for unit testing the per-column rules in isolation.
 */
export function encodeValue(col: string, value: FeatureValue, encoding: ManifestInput['encoding']): number {
  const { categorical_columns, boolean_columns, missing_ordinal, encoders } = encoding

  if (categorical_columns.includes(col)) {
    if (value === null || value === undefined) return missing_ordinal
    const map = encoders[col] ?? {}
    const code = map[String(value)]
    return code === undefined ? missing_ordinal : code // unseen level → missing sentinel
  }

  if (boolean_columns.includes(col)) {
    if (value === null || value === undefined) return NaN // NULL boolean preserved as native-missing
    if (typeof value === 'boolean') return value ? 1 : 0
    // tolerate string/number truthiness from a DB ("true"/"false"/1/0)
    if (value === 'true' || value === 1 || value === '1') return 1
    if (value === 'false' || value === 0 || value === '0') return 0
    return NaN
  }

  return toNumberOrNaN(value) // continuous
}

/**
 * Build the positional Float32Array in exact feature_order. Missing keys on the row are
 * treated as NULL (continuous → NaN, categorical → missing_ordinal, boolean → NaN).
 */
export function buildFeatureVector(row: FeatureRow, input: ManifestInput): Float32Array {
  const vec = new Float32Array(input.n_features)
  for (let i = 0; i < input.feature_order.length; i++) {
    const col = input.feature_order[i]
    vec[i] = encodeValue(col, row[col], input.encoding)
  }
  return vec
}

/** Stack N rows into a single [N * n_features] Float32Array for a batched inference run. */
export function buildFeatureMatrix(rows: FeatureRow[], input: ManifestInput): Float32Array {
  const mat = new Float32Array(rows.length * input.n_features)
  for (let r = 0; r < rows.length; r++) {
    const vec = buildFeatureVector(rows[r], input)
    mat.set(vec, r * input.n_features)
  }
  return mat
}
