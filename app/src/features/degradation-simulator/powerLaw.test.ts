// @vitest-environment node
/**
 * WI-17: the power-law tyre term against the Degradation Simulator's P3 gates (accuracy.ts).
 *
 *   Criterion 1 (form adequacy): a power law y = c + α·k^β fitted to each P3 basket cell's observed
 *     deg-from-fresh p50 passes P3.1 (MAE ≤ 0.5 s) -- can the two-number curve represent the cell.
 *   Criterion 4b: the PREDICTED power-law term, from the GroupKFold-by-race fold model that never
 *     saw the race (__fixtures__/powerlaw_basket.json, written by `python -m ml.src.powerlaw`),
 *     passes P3.1-P3.3 on the basket's dry cells.
 *   Criterion 4a: the exported ONNX files, scored here with onnxruntime-web, reproduce the Python
 *     prediction to 1e-5 for every cell of every race (__fixtures__/powerlaw_parity.json). Runs
 *     when ml/models/powerlaw_*_v1.onnx exist (they are gitignored build outputs).
 *
 * Out of scope: the basket's Istanbul INTERMEDIATE cell. Intermediates are not on the hardness
 * scale, so no power-law prediction exists for it (criterion 1 still fits it).
 */
import { describe, it, expect } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import * as ort from 'onnxruntime-web'
import {
  alphaFromLevel, clipBeta, evalPowerLawFit, fitPowerLaw, powerLawVector, predictPowerLaw, tyreCurve,
  BETA_MAX, BETA_MIN, FRESH_ANCHOR_AGE, LEVEL_AGE,
} from './powerLaw'
import type { PowerLawFeatures, PowerLawManifest } from './powerLaw'
import { projectedDegMAE, monotoneViolations } from './accuracy'
import type { BasketSample, TyrePoint } from './accuracy'
import fittedBasket from './__fixtures__/fitted_basket.json'
import accuracyBasket from './__fixtures__/accuracy_basket.json'
import plBasket from './__fixtures__/powerlaw_basket.json'
import plParity from './__fixtures__/powerlaw_parity.json'

const P31_MAE = 0.5
const MAX_LAP = 50

interface Params { deg20: number; beta: number; alpha: number }
interface BasketRace {
  race_id: string
  n_laps: number
  target: Params
  variants: Record<'own' | 'dirty_0' | 'dirty_0_8' | 'dirty_1' | 'temp_25' | 'temp_30', Params>
}
interface BasketCell { circuit_id: string; era: string; compound: string; races: BasketRace[]; excluded?: string }

const groundTruth = accuracyBasket.basket
const plCells = (plBasket as unknown as { cells: BasketCell[] }).cells
const fittedCells = (fittedBasket as unknown as {
  cells: { circuit_id: string; era: string; compound: string; rows: { lap_in_stint: number; n_observations: number; obs_deg_from_fresh_p50_s: number }[] }[]
}).cells

const key = (c: { circuit_id: string; era: string; compound: string }) => `${c.circuit_id}/${c.compound}/${c.era}`
const samplesFor = (c: { circuit_id: string; era: string; compound: string }): BasketSample[] => {
  const gt = groundTruth.find(g => key(g) === key(c))
  if (!gt) throw new Error(`no accuracy-basket cell for ${key(c)}`)
  return gt.samples.map(s => ({ lap_in_stint: s.lap_in_stint, obs_deg_from_fresh_p50_s: s.obs_deg_from_fresh_p50_s }))
}
const toPoints = (tyre: number[]): TyrePoint[] => tyre.map((t, i) => ({ x: i + 1, tyre: t }))

/** The cell's power-law term: the n_laps-weighted mean of its races' curves (each monotone). */
function pooledCurve(cell: BasketCell, pick: (r: BasketRace) => Params): number[] {
  const out = new Array<number>(MAX_LAP).fill(0)
  let w = 0
  for (const r of cell.races) {
    const p = pick(r)
    tyreCurve(p.alpha, p.beta, MAX_LAP).forEach((v, i) => { out[i] += r.n_laps * v })
    w += r.n_laps
  }
  return out.map(v => v / w)
}

describe('powerLaw arithmetic', () => {
  it('is zero through the fresh-tyre anchor and rises after it', () => {
    const c = tyreCurve(0.05, 1.2, 30)
    expect(c[0]).toBe(0)
    expect(c[FRESH_ANCHOR_AGE - 1]).toBe(0)
    expect(c[FRESH_ANCHOR_AGE]).toBeGreaterThan(0)
    expect(monotoneViolations(c)).toBe(0)
  })

  it('alphaFromLevel pins the curve at the level age', () => {
    for (const beta of [0.2, 0.7, 1, 1.9, 3]) {
      const a = alphaFromLevel(0.8, beta)
      expect(tyreCurve(a, beta, LEVEL_AGE)[LEVEL_AGE - 1]).toBeCloseTo(0.8, 12)
    }
    expect(alphaFromLevel(-0.4, 1.1)).toBe(0) // a falling level is a flat curve, never a negative one
  })

  it('clamps beta to the grid range and alpha at zero', () => {
    expect(clipBeta(-1)).toBe(BETA_MIN)
    expect(clipBeta(9)).toBe(BETA_MAX)
    expect(tyreCurve(-1, 1, 10).every(v => v === 0)).toBe(true)
  })

  it('is non-decreasing in alpha and in beta at every lap (what makes the P3.3 gates structural)', () => {
    const base = tyreCurve(0.03, 1.1, MAX_LAP)
    const moreA = tyreCurve(0.04, 1.1, MAX_LAP)
    const moreB = tyreCurve(0.03, 1.3, MAX_LAP)
    base.forEach((v, i) => {
      expect(moreA[i]).toBeGreaterThanOrEqual(v)
      expect(moreB[i]).toBeGreaterThanOrEqual(v)
    })
  })

  it('fitPowerLaw recovers a known curve', () => {
    const pts = Array.from({ length: 30 }, (_, i) => ({ x: i + 1, y: 0.3 + 0.02 * Math.pow(i + 1, 1.5) }))
    const f = fitPowerLaw(pts)
    expect(f.beta).toBeCloseTo(1.5, 10)
    expect(f.alpha).toBeCloseTo(0.02, 10)
    expect(f.intercept).toBeCloseTo(0.3, 10)
  })

  it('powerLawVector is positional and encodes missing as NaN', () => {
    const v = powerLawVector({ era_code: 2, track_temp_c: null }, ['track_temp_c', 'era_code', 'dirty_air_share'])
    expect(Number.isNaN(v[0])).toBe(true)
    expect(v[1]).toBe(2)
    expect(Number.isNaN(v[2])).toBe(true)
  })

  it('reproduces the Python tyre curve from the Python (alpha, beta) on every cell', () => {
    const fx = plParity as unknown as { laps: number[]; rows: { alpha: number; beta: number; tyre_s: number[] }[] }
    let maxAbs = 0
    for (const r of fx.rows) {
      const c = tyreCurve(r.alpha, r.beta, MAX_LAP)
      fx.laps.forEach((lap, j) => { maxAbs = Math.max(maxAbs, Math.abs(c[lap - 1] - r.tyre_s[j])) })
    }
    expect(maxAbs).toBeLessThanOrEqual(1e-8)
  })
})

describe('WI-17 criterion 1: form adequacy -- a power law fitted to each P3 basket cell passes P3.1', () => {
  for (const cell of fittedCells) {
    it(`${key(cell)}: fitted c + α·k^β has MAE ≤ ${P31_MAE}s`, () => {
      // same inputs as the isotonic fit: laps with n_observations >= 10, n-weighted
      const pts = cell.rows
        .filter(r => r.n_observations >= 10)
        .map(r => ({ x: r.lap_in_stint, y: r.obs_deg_from_fresh_p50_s, w: r.n_observations }))
      const fit = fitPowerLaw(pts)
      const curve = toPoints(evalPowerLawFit(fit, cell.rows.length))
      expect(projectedDegMAE(curve, samplesFor(cell))).toBeLessThanOrEqual(P31_MAE)
    })
  }
})

// Basket cells where P3.1 fails for the predicted term, found by `python -m ml.src.powerlaw` and
// recorded in the WI-17 As built (W52). Monza HARD post2022: the gate's truth is mostly not tyre
// wear. Its fresh-tyre anchor (the median of every tyre-age <= 2 lap, pooled over 2022-24) comes
// from a faster set of cars than the later laps it is subtracted from:
//   - race mix: 2024, the fastest of the three races by 1.5-2.7 s, supplies 67 % of the anchor's
//     33 laps but under half of the later laps;
//   - car mix: in 2023 only Ferrari and Red Bull fitted new HARDs (4 anchor laps, 0.76 s quicker
//     than that race's median car). The rest of the field started on used sets (tyre age 5-7), so
//     those cars appear at every lap_in_stint but never in the anchor.
// That pace gap is ~0.9 s of the truth's "degradation" (the other three basket cells carry < 0.1 s).
// Against a per-stint anchor the same predictions score 0.26 s here, and within-stint wear at
// Monza is ~0.6 s by lap 20. The model trains on within-stint fits, so it cannot learn the gap, and
// even the race cells' OWN in-sample fits (the oracle below) miss it by more than 0.5 s. Fixing it
// means redefining the P3 truth, which the shipped isotonic term shares, so that is a ruling (W52),
// not a model change. `it.fails` keeps the failure visible: if a rebuild makes the cell pass, this
// flips to red and the entry has to be removed.
const KNOWN_P31_FAILS = new Set(['autodromo_nazionale_monza/HARD/post2022'])

describe('WI-17 criterion 4b: the predicted power-law term on held-out races passes P3.1-P3.3', () => {
  const dry = plCells.filter(c => !c.excluded)

  it('covers every dry basket cell and excludes only the non-slick one', () => {
    expect(dry.map(key).sort()).toEqual(
      groundTruth.filter(g => g.compound !== 'INTERMEDIATE').map(key).sort(),
    )
    expect(plCells.filter(c => c.excluded).map(c => c.compound)).toEqual(['INTERMEDIATE'])
    for (const c of dry) expect(c.races.length).toBeGreaterThan(0)
  })

  for (const cell of dry) {
    const label = key(cell)
    const own = () => pooledCurve(cell, r => r.variants.own)

    const p31 = () => {
      expect(projectedDegMAE(toPoints(own()), samplesFor(cell))).toBeLessThanOrEqual(P31_MAE)
    }
    if (KNOWN_P31_FAILS.has(label)) {
      it.fails(`${label}: P3.1 MAE ≤ ${P31_MAE}s -- KNOWN FAIL, see KNOWN_P31_FAILS`, p31)
      it(`${label}: the within-stint oracle fails P3.1 too (the gap is the truth's level, not the model)`, () => {
        const oracle = pooledCurve(cell, r => ({ ...r.target, alpha: alphaFromLevel(r.target.deg20, r.target.beta) }))
        expect(projectedDegMAE(toPoints(oracle), samplesFor(cell))).toBeGreaterThan(P31_MAE)
      })
    } else {
      it(`${label}: P3.1 MAE ≤ ${P31_MAE}s`, p31)
    }

    it(`${label}: P3.2 zero monotone violations (own conditions, dirty-air 0.8, temp +25°C)`, () => {
      for (const v of ['own', 'dirty_0_8', 'temp_25'] as const) {
        expect(monotoneViolations(pooledCurve(cell, r => r.variants[v]))).toBe(0)
      }
    })

    it(`${label}: P3.3 sign -- no lap below −0.5s`, () => {
      for (const t of own()) expect(t).toBeGreaterThanOrEqual(-0.5)
    })

    it(`${label}: P3.3 ↑dirty-air never lowers the curve (share 0 → 1)`, () => {
      const clean = pooledCurve(cell, r => r.variants.dirty_0)
      const dirty = pooledCurve(cell, r => r.variants.dirty_1)
      clean.forEach((v, i) => expect(dirty[i]).toBeGreaterThanOrEqual(v - 1e-9))
    })

    it(`${label}: P3.3 ↑temp never lowers the curve (+30°C)`, () => {
      const cool = own()
      const hot = pooledCurve(cell, r => r.variants.temp_30)
      cool.forEach((v, i) => expect(hot[i]).toBeGreaterThanOrEqual(v - 1e-9))
    })
  }

  it('P3.3 regression anchor: Red Bull Ring HARD post2022 lap 30 ≈ +1.264s (±0.5, as for the isotonic term)', () => {
    const rbr = dry.find(c => key(c) === 'red_bull_ring/HARD/post2022')
    if (!rbr) throw new Error('RBR HARD post2022 not in the power-law basket fixture')
    expect(pooledCurve(rbr, r => r.variants.own)[29]).toBeCloseTo(1.264, 0)
  })
})

// ── Criterion 4a: ONNX in the JS runtime == the Python prediction ──────────────────────────────
const repoRoot = join(__dirname, '../../../..')
const manifestPath = join(repoRoot, 'ml/models/powerlaw_manifest_v1.json')
const haveOnnx = existsSync(manifestPath) &&
  ['powerlaw_deg20_v1.onnx', 'powerlaw_beta_v1.onnx'].every(f => existsSync(join(repoRoot, 'ml/models', f)))

describe.runIf(haveOnnx)('WI-17 criterion 4a: onnxruntime-web reproduces the Python prediction', () => {
  it('matches deg20, beta and the tyre curve to 1e-5 on every cell of every race', async () => {
    ort.env.wasm.wasmPaths = join(repoRoot, 'app/node_modules/onnxruntime-web/dist/')
    ort.env.wasm.numThreads = 1
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8')) as PowerLawManifest
    const fx = plParity as unknown as {
      feature_order: { deg20: string[]; beta: string[] }
      laps: number[]
      rows: { x_deg20: (number | null)[]; x_beta: (number | null)[]; deg20: number; beta: number; tyre_s: number[] }[]
    }
    // the fixture and the manifest must agree on the contract before any number is compared
    expect(manifest.models.find(m => m.name === 'powerlaw_deg20')!.feature_order).toEqual(fx.feature_order.deg20)
    expect(manifest.models.find(m => m.name === 'powerlaw_beta')!.feature_order).toEqual(fx.feature_order.beta)

    const make = (name: string) =>
      ort.InferenceSession.create(join(repoRoot, 'ml/models', manifest.models.find(m => m.name === name)!.onnx))
    const [deg20, beta] = await Promise.all([make('powerlaw_deg20'), make('powerlaw_beta')])
    const rows: PowerLawFeatures[] = fx.rows.map(r => {
      const f: Record<string, number | null> = {}
      fx.feature_order.deg20.forEach((n, i) => { f[n] = r.x_deg20[i] })
      fx.feature_order.beta.forEach((n, i) => { f[n] = r.x_beta[i] })
      return f as PowerLawFeatures
    })
    const preds = await predictPowerLaw({ deg20, beta }, manifest, rows)

    let maxParam = 0
    let maxCurve = 0
    preds.forEach((p, i) => {
      const r = fx.rows[i]
      maxParam = Math.max(maxParam, Math.abs(p.deg20 - r.deg20), Math.abs(p.beta - r.beta))
      const c = tyreCurve(p.alpha, p.beta, MAX_LAP)
      fx.laps.forEach((lap, j) => { maxCurve = Math.max(maxCurve, Math.abs(c[lap - 1] - r.tyre_s[j])) })
    })
    console.log(`power-law ONNX parity: ${preds.length} cells, max |Δ| params ${maxParam.toExponential(2)}, curve ${maxCurve.toExponential(2)}`)
    expect(maxParam).toBeLessThanOrEqual(1e-5)
    expect(maxCurve).toBeLessThanOrEqual(1e-5)
  }, 60_000)
})
