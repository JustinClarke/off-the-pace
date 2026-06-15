// In-browser parity check the recruiter-grade integrity badge (AD-3 / R-3).
//
// Scores a handful of real laps in the browser and asserts the result matches the
// precomputed mart_degradation_predictions within tolerance. This is the browser
// analogue of the Python ONNX-parity test (manifest.provenance.onnx_parity).
//
// The 41-feature vector is read straight from fct_cliff_prediction_features, which carries the
// full v3 feature set (the 8 telemetry/air columns that once lived in int_lap_powertrain_signature
// and int_air_density were folded into this mart in ml-v0.2 §2). predict.py scores the same single
// frame, so the browser vector and the stored mart line up column-for-column.
//
// The inference layer itself is independently proven against booster ground truth in
// app/src/ml/parity.node.test.ts (1.05e-5 maxAbs); this badge additionally proves the *shipped*
// predictions match in-browser scoring. Both sides must be regenerated from the same warehouse
// state (make ml-predict → make app-data) or the badge will flag a mismatch.

import { query } from '@/data/duckdb/client'
import { registerParquetMany } from '@/data/duckdb/register'
import { loadManifest, getTablePath, DataManifest } from '@/data/manifest'
import { predictLaps } from './infer'
import { FeatureRow } from './featureVector'
import { loadModelManifest } from './manifest'

export interface ParityRow {
  lap_id: string
  field: 'degradation_jump_s' | 'degradation_jump_p10_s' | 'degradation_jump_p90_s' | 'remaining_stint_life_laps' | 'cliff_class'
  browser: number | string
  mart: number | string
  absDiff: number // 0/1 for the categorical cliff_class
}

export interface ParityResult {
  pass: boolean
  tolerance: number
  nRows: number
  maxAbsDiff: number
  cliffClassMismatches: number
  worst: ParityRow[] // the few largest numeric diffs, for display
}

// Match the Python parity atol (manifest.provenance.onnx_parity.atol = 1e-5) but allow a
// little headroom for f32↔f64 + ORT/XGBoost kernel differences across platforms.
const DEFAULT_TOLERANCE = 1e-3

interface JoinedRow extends FeatureRow {
  lap_id: string
  m_p50: number
  m_p10: number
  m_p90: number
  m_life: number
  m_cliff: string
}

async function registerParityViews(manifest: DataManifest, season: number): Promise<void> {
  const tables = [
    { name: 'fct_cliff_prediction_features', table: 'fct_cliff_prediction_features' },
    { name: 'mart_degradation_predictions', table: 'mart_degradation_predictions' },
  ]
  await registerParquetMany(
    tables.map(t => ({ name: t.name, url: getTablePath(manifest, t.table, season) }))
  )
}

/**
 * Assert every feature column exists in fct_cliff_prediction_features (the single source view).
 * Fails loud listing the missing columns if the mart and the model's feature_order drift,
 * rather than letting DuckDB error on `f."col"` for an absent column mid-query.
 */
async function assertFeatureColumns(cols: string[]): Promise<void> {
  const rows = await query<{ column_name: string }>(
    `SELECT column_name FROM information_schema.columns
     WHERE table_name = 'fct_cliff_prediction_features'`,
  )
  const present = new Set(rows.map(r => r.column_name))
  const missing = cols.filter(c => !present.has(c))
  if (missing.length > 0) {
    throw new Error(
      `Parity: feature columns missing from fct_cliff_prediction_features: ${missing.join(', ')}`,
    )
  }
}

/**
 * Run the parity check on `limit` laps from `season` (default 2024, the holdout fold).
 * Pure data + inference; safe to call from a dev panel or a vitest browser test.
 */
export async function verifyParity(season = 2024, limit = 64, tolerance = DEFAULT_TOLERANCE): Promise<ParityResult> {
  const dataManifest = await loadManifest()
  await registerParityViews(dataManifest, season)

  const modelManifest = await loadModelManifest()
  const featureCols = modelManifest.input.feature_order

  // All 41 features live in fct_cliff_prediction_features (v3); guard that the mart and the
  // model's feature_order haven't drifted before building the query, so a mismatch fails loud
  // instead of as a DuckDB "column not found" mid-scoring.
  await assertFeatureColumns(featureCols)
  const featureSelect = featureCols
    .map(c => `f."${c}" AS "${c}"`)
    .join(',\n    ')

  const sql = `
    SELECT
      f.lap_id AS lap_id,
      ${featureSelect},
      m.predicted_degradation_jump_s        AS m_p50,
      m.predicted_degradation_jump_p10_s    AS m_p10,
      m.predicted_degradation_jump_p90_s    AS m_p90,
      m.predicted_remaining_stint_life_laps AS m_life,
      m.predicted_cliff_class               AS m_cliff
    FROM fct_cliff_prediction_features f
    JOIN mart_degradation_predictions m USING (lap_id)
    ORDER BY f.lap_id
    LIMIT ${limit}
  `

  const joined = await query<JoinedRow>(sql)
  if (joined.length === 0) {
    throw new Error(`Parity: no rows for season ${season} (is the data exported?)`)
  }

  const featureRows: FeatureRow[] = joined.map(row => {
    const r: FeatureRow = {}
    for (const c of featureCols) r[c] = row[c] as FeatureRow[string]
    return r
  })

  const preds = await predictLaps(featureRows)

  let maxAbsDiff = 0
  let cliffClassMismatches = 0
  const diffs: ParityRow[] = []

  const pushNum = (lap_id: string, field: ParityRow['field'], browser: number, mart: number) => {
    const absDiff = Math.abs(browser-mart)
    if (absDiff > maxAbsDiff) maxAbsDiff = absDiff
    diffs.push({ lap_id, field, browser, mart, absDiff })
  }

  for (let i = 0; i < joined.length; i++) {
    const j = joined[i]
    const b = preds[i]
    pushNum(j.lap_id, 'degradation_jump_s', b.degradation_jump_s, Number(j.m_p50))
    pushNum(j.lap_id, 'degradation_jump_p10_s', b.degradation_jump_p10_s, Number(j.m_p10))
    pushNum(j.lap_id, 'degradation_jump_p90_s', b.degradation_jump_p90_s, Number(j.m_p90))
    pushNum(j.lap_id, 'remaining_stint_life_laps', b.remaining_stint_life_laps, Number(j.m_life))
    if (b.cliff.label !== j.m_cliff) {
      cliffClassMismatches++
      diffs.push({ lap_id: j.lap_id, field: 'cliff_class', browser: b.cliff.label, mart: j.m_cliff, absDiff: 1 })
    }
  }

  const worst = diffs
    .filter(d => d.field !== 'cliff_class')
    .sort((a, b) => b.absDiff-a.absDiff)
    .slice(0, 5)
    .concat(diffs.filter(d => d.field === 'cliff_class').slice(0, 3))

  return {
    pass: maxAbsDiff <= tolerance && cliffClassMismatches === 0,
    tolerance,
    nRows: joined.length,
    maxAbsDiff,
    cliffClassMismatches,
    worst,
  }
}
