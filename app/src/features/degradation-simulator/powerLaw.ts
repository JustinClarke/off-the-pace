// WI-17: the power-law tyre term, Δt(k) = α · (k^β − 2^β) seconds over the fresh-tyre pace.
//
// Mirrors ml/src/powerlaw.py (the curve arithmetic) and ml/models/powerlaw_manifest_v1.json (the
// two ONNX models' feature contracts). Not wired into the page: WI-17 only makes it the headline
// tyre term if it beats the current isotonic term on the P3 basket, and it does not (the basket
// IS the isotonic term's own data; see powerLaw.test.ts and the WI's As built). It ships as code
// plus tests, and nothing user-visible changes.
//
// Why "over the pace at tyre age 2": the recomposition's fresh-tyre anchor (ref_green_pace_s) is
// the median clean lap at tyre age <= 2, and those laps are almost all age 2 because the age-1 lap
// is the out-lap. So the tyre term is zero through lap 2 of a new set and rises after it.
//
// Where α and β come from (the WI-17 Step-0 fallback): α itself is not identified by 8-30 noisy
// laps (reliability ceiling ~0.07), the curve over the fresh pace is (0.58-0.76). So one model
// predicts the curve's LEVEL, the degradation at age 20 (deg20), and a second predicts its SHAPE,
// β; α follows in closed form. Hardness rank, dirty air and track temperature feed the level
// only, monotone non-decreasing, and never the shape, so raising any of them scales the whole
// curve up at every lap (the P3.3 sanity gates hold by construction).

import * as ort from 'onnxruntime-web'

export const FRESH_ANCHOR_AGE = 2
export const LEVEL_AGE = 20
export const BETA_MIN = 0.2
export const BETA_MAX = 3.0
/** The β grid the dbt fits and fitPowerLaw profile over: 0.20..3.00 step 0.05 (k / 20, k = 4..60). */
export const BETA_GRID: readonly number[] = Array.from({ length: 57 }, (_, i) => (i + 4) / 20)

/** era_code as fct_power_law_training encodes it (compound_hardness_scale's era column). */
export const ERA_CODE = { '2018': 0, '2019-21': 1, '2022+': 2 } as const

/** Every feature either model reads. The simulator must supply all of them (W26). */
export interface PowerLawFeatures {
  compound_hardness_rank?: number | null
  era_code?: number | null
  track_energy_index?: number | null
  circuit_abrasiveness_index?: number | null
  track_temp_c?: number | null
  stint_start_fuel_kg?: number | null
  dirty_air_share?: number | null
  constructor_pace_s?: number | null
}

export interface PowerLawModelSpec {
  name: string
  onnx: string
  feature_order: string[]
  n_features: number
}

export interface PowerLawManifest {
  model_version: string
  models: PowerLawModelSpec[]
  curve: { fresh_anchor_age: number; level_age: number }
}

export interface PowerLawParams {
  /** Tyre degradation at age 20 over the age-2 fresh pace (s): the level model's raw output. */
  deg20: number
  /** Power-law exponent, clipped to [BETA_MIN, BETA_MAX]. */
  beta: number
  /** max(deg20, 0) / (20^β − 2^β). */
  alpha: number
}

export function clipBeta(beta: number): number {
  return Math.min(BETA_MAX, Math.max(BETA_MIN, beta))
}

/** α from the level: the curve passes through deg20 at age 20 (0 when deg20 <= 0). */
export function alphaFromLevel(deg20: number, beta: number): number {
  const b = clipBeta(beta)
  return Math.max(deg20, 0) / (Math.pow(LEVEL_AGE, b) - Math.pow(FRESH_ANCHOR_AGE, b))
}

/**
 * The tyre term for laps 1..laps of a new set: max(0, α · (k^β − 2^β)). Index i is lap i + 1.
 * Monotone non-decreasing in k for any α, β (α is clamped at 0, β to the grid range), zero
 * through the fresh-tyre anchor, and non-decreasing in α and in β at every lap.
 */
export function tyreCurve(alpha: number, beta: number, laps: number): number[] {
  const a = Math.max(alpha, 0)
  const b = clipBeta(beta)
  const anchor = Math.pow(FRESH_ANCHOR_AGE, b)
  const out: number[] = []
  for (let k = 1; k <= Math.max(0, Math.round(laps)); k++) {
    out.push(Math.max(0, a * (Math.pow(k, b) - anchor)))
  }
  return out
}

/** Positional float32 vector for one model; a missing feature is NaN (XGBoost native-missing). */
export function powerLawVector(features: PowerLawFeatures, order: readonly string[]): Float32Array {
  const row = features as Record<string, number | null | undefined>
  const v = new Float32Array(order.length)
  order.forEach((name, i) => {
    const x = row[name]
    v[i] = x === null || x === undefined || !Number.isFinite(Number(x)) ? NaN : Number(x)
  })
  return v
}

/** The slice of an onnxruntime InferenceSession this module uses (a real session satisfies it). */
export interface SessionLike {
  readonly inputNames: readonly string[]
  readonly outputNames: readonly string[]
  run(feeds: Record<string, ort.Tensor>): Promise<Record<string, { data: unknown }>>
}

export interface PowerLawSessions {
  deg20: SessionLike
  beta: SessionLike
}

function specFor(manifest: PowerLawManifest, name: string): PowerLawModelSpec {
  const spec = manifest.models.find(m => m.name === name)
  if (!spec) throw new Error(`power-law manifest has no model '${name}'`)
  return spec
}

async function runOne(session: SessionLike, spec: PowerLawModelSpec, rows: PowerLawFeatures[]): Promise<Float32Array> {
  const n = rows.length
  const mat = new Float32Array(n * spec.n_features)
  rows.forEach((r, i) => mat.set(powerLawVector(r, spec.feature_order), i * spec.n_features))
  const out = await session.run({ [session.inputNames[0]]: new ort.Tensor('float32', mat, [n, spec.n_features]) })
  return out[session.outputNames[0]].data as Float32Array
}

/** Score rows through both ONNX models and recover (α, β). */
export async function predictPowerLaw(
  sessions: PowerLawSessions,
  manifest: PowerLawManifest,
  rows: PowerLawFeatures[],
): Promise<PowerLawParams[]> {
  if (!rows.length) return []
  const deg20 = await runOne(sessions.deg20, specFor(manifest, 'powerlaw_deg20'), rows)
  const betaRaw = await runOne(sessions.beta, specFor(manifest, 'powerlaw_beta'), rows)
  return rows.map((_, i) => {
    const beta = clipBeta(betaRaw[i])
    return { deg20: deg20[i], beta, alpha: alphaFromLevel(deg20[i], beta) }
  })
}

/** Create both sessions from a base URL (e.g. '/models'), per the manifest's file names. */
export async function loadPowerLawSessions(manifest: PowerLawManifest, baseUrl: string): Promise<PowerLawSessions> {
  const make = (name: string) =>
    ort.InferenceSession.create(`${baseUrl}/${specFor(manifest, name).onnx}`, { executionProviders: ['wasm'] })
  const [deg20, beta] = await Promise.all([make('powerlaw_deg20'), make('powerlaw_beta')])
  return { deg20, beta }
}

export interface PowerLawFit {
  intercept: number
  alpha: number
  beta: number
  r2: number
}

/**
 * Weighted least-squares fit of y = c + α · x^β, β profiled on BETA_GRID (smallest β on a tie),
 * (c, α) by weighted OLS at each β. The same profile the dbt stint fit runs, with weights. Used
 * for WI-17 criterion 1 (form adequacy): can a power law represent a basket cell's curve at all.
 */
export function fitPowerLaw(points: { x: number; y: number; w?: number }[]): PowerLawFit {
  const pts = points.filter(p => Number.isFinite(p.x) && Number.isFinite(p.y) && p.x > 0)
  const sw = pts.reduce((s, p) => s + (p.w ?? 1), 0)
  if (pts.length < 3 || sw <= 0) throw new Error('fitPowerLaw needs at least three points')
  const ym = pts.reduce((s, p) => s + (p.w ?? 1) * p.y, 0) / sw
  const syy = pts.reduce((s, p) => s + (p.w ?? 1) * (p.y - ym) ** 2, 0)
  let best: PowerLawFit | null = null
  for (const b of BETA_GRID) {
    const xs = pts.map(p => Math.pow(p.x, b))
    const xm = pts.reduce((s, p, i) => s + (p.w ?? 1) * xs[i], 0) / sw
    let sxx = 0
    let sxy = 0
    pts.forEach((p, i) => {
      const w = p.w ?? 1
      sxx += w * (xs[i] - xm) ** 2
      sxy += w * (xs[i] - xm) * (p.y - ym)
    })
    if (sxx <= 0) continue
    const alpha = sxy / sxx
    const r2 = syy > 0 ? (sxy * sxy) / (sxx * syy) : 1
    if (best === null || r2 > best.r2) best = { intercept: ym - alpha * xm, alpha, beta: b, r2 }
  }
  if (best === null) throw new Error('fitPowerLaw: no β on the grid gave a usable fit')
  return best
}

/** Evaluate a fitted y = c + α · x^β at laps 1..laps. */
export function evalPowerLawFit(fit: PowerLawFit, laps: number): number[] {
  return Array.from({ length: Math.max(0, Math.round(laps)) }, (_, i) => fit.intercept + fit.alpha * Math.pow(i + 1, fit.beta))
}
