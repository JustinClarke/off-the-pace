// In-browser parity check the recruiter-grade integrity badge (AD-3 / R-3).
//
// Scores a handful of real laps in the browser and asserts the result matches the
// precomputed mart_degradation_predictions within tolerance. This is the browser
// analogue of the Python ONNX-parity test (manifest.provenance.onnx_parity).
//
// The 38-feature vector is reconstructed from the warehouse the same way training did:
// fct_cliff_prediction_features carries 30 of the columns; the remaining 8 live in
// int_lap_powertrain_signature (6) and int_air_density (2), joined on lap_id.
//
// ⚠️ KNOWN DATA CAVEAT (not an inference bug): the shipped mart_degradation_predictions was
// generated against an earlier warehouse state whose cliff-features mart still joined those 8
// columns; the current mart SQL no longer does, so the stored predictions are STALE. Until the
// mart is regenerated consistently, this badge will report a mismatch. The inference layer
// itself is proven correct against booster ground truth see app/src/ml/parity.node.test.ts
// (1.05e-5 maxAbs). When the mart is refreshed, this check goes green with no code change.

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
    { name: 'int_lap_powertrain_signature', table: 'int_lap_powertrain_signature' },
    { name: 'int_air_density', table: 'int_air_density' },
    { name: 'mart_degradation_predictions', table: 'mart_degradation_predictions' },
  ]
  await registerParquetMany(
    tables.map(t => ({ name: t.name, url: getTablePath(manifest, t.table, season) }))
  )
}

/**
 * For each column, pick the first source view (in priority order) whose schema contains it.
 * `aliases` are the SQL aliases used in the join; `viewByAlias` maps alias → registered view name.
 */
async function resolveColumnOwners(
  cols: string[],
  aliases: string[],
  viewByAlias: Record<string, string>,
): Promise<Record<string, string>> {
  const viewNames = aliases.map(a => viewByAlias[a])
  const inList = viewNames.map(v => `'${v}'`).join(', ')
  const rows = await query<{ table_name: string; column_name: string }>(
    `SELECT table_name, column_name FROM information_schema.columns WHERE table_name IN (${inList})`,
  )
  const colsByView = new Map<string, Set<string>>()
  for (const r of rows) {
    if (!colsByView.has(r.table_name)) colsByView.set(r.table_name, new Set())
    colsByView.get(r.table_name)!.add(r.column_name)
  }
  const owner: Record<string, string> = {}
  for (const c of cols) {
    const alias = aliases.find(a => colsByView.get(viewByAlias[a])?.has(c))
    if (!alias) throw new Error(`Parity: feature column "${c}" not found in any source view`)
    owner[c] = alias
  }
  return owner
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

  // Route each feature column to the single source view that actually carries it. DuckDB
  // errors on `t."col"` for an absent column, so we can't blanket-COALESCE across sources;
  // instead we resolve ownership from information_schema (priority: cliff mart → powertrain
  // → air-density). 30 cols come from f, 6 from p, 2 from a today, but this adapts if they move.
  const owner = await resolveColumnOwners(featureCols, ['f', 'p', 'a'], {
    f: 'fct_cliff_prediction_features',
    p: 'int_lap_powertrain_signature',
    a: 'int_air_density',
  })
  const featureSelect = featureCols
    .map(c => `${owner[c]}."${c}" AS "${c}"`)
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
    LEFT JOIN int_lap_powertrain_signature p USING (lap_id)
    LEFT JOIN int_air_density a USING (lap_id)
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
