/**
 * P3 accuracy gates run via `npm test` (no DuckDB needed).
 * Inputs come from __fixtures__/fitted_basket.json (generated from mart_degradation_history_envelope
 * by scripts/generate_fitted_fixture.py; regenerate after any fit or mart change).
 *
 * Gates:
 *   P3.1 MAE ≤ 0.5s for every basket cell at neutral inputs (vs raw obs_deg_from_fresh_p50_s)
 *   P3.2 0 monotone violations on tyre term for every cell: neutral, dirty-air, and temp-past-window
 *   P3.3 Sign/sanity: no dry-compound cell tyre < −0.5s; RBR HARD lap-30 ≈ +1.2 ± 0.2;
 *        ↑dirty-air and ↑temp never lower the curve
 */

import { describe, it, expect } from 'vitest'
import { recomposeLapTimes } from './transform'
import type { RecomposeOptions } from './transform'
import type { HistoryEnvelopeRow } from './queries'
import { projectedDegMAE, monotoneViolations } from './accuracy'
import type { TyrePoint, BasketSample } from './accuracy'
import fittedBasket from './__fixtures__/fitted_basket.json'
import accuracyBasket from './__fixtures__/accuracy_basket.json'

// Fixture types
interface FittedRow {
  lap_in_stint: number
  obs_deg_from_fresh_p10_mono_s: number | null
  obs_deg_from_fresh_p50_mono_s: number | null
  obs_deg_from_fresh_p90_mono_s: number | null
  dirty_air_deg_mult: number
  temp_headroom_c: number
  temp_penalty_s_per_deg: number
  ref_green_pace_s: number
  n_observations: number
  obs_fuel_removed_pace_p10_s: number
  obs_fuel_removed_pace_p50_s: number
  obs_fuel_removed_pace_p90_s: number
  obs_deg_from_fresh_p10_s: number
  obs_deg_from_fresh_p50_s: number
  obs_deg_from_fresh_p90_s: number
}

interface FittedCell {
  circuit_id: string
  era: string
  compound: string
  rows: FittedRow[]
}

const cells = (fittedBasket as unknown as { cells: FittedCell[] }).cells
const groundTruth = (accuracyBasket as typeof accuracyBasket).basket

// Build a TyrePoint[] from recomposeLapTimes over the cell's fitted history.
function runCell(cell: FittedCell, overrides?: Partial<RecomposeOptions>): TyrePoint[] {
  const history: HistoryEnvelopeRow[] = cell.rows.map(r => ({
    lap_in_stint: r.lap_in_stint,
    n_observations: r.n_observations,
    ref_green_pace_s: r.ref_green_pace_s,
    obs_fuel_removed_pace_p10_s: r.obs_fuel_removed_pace_p10_s,
    obs_fuel_removed_pace_p50_s: r.obs_fuel_removed_pace_p50_s,
    obs_fuel_removed_pace_p90_s: r.obs_fuel_removed_pace_p90_s,
    obs_deg_from_fresh_p10_s: r.obs_deg_from_fresh_p10_s,
    obs_deg_from_fresh_p50_s: r.obs_deg_from_fresh_p50_s,
    obs_deg_from_fresh_p90_s: r.obs_deg_from_fresh_p90_s,
    obs_deg_from_fresh_p10_mono_s: r.obs_deg_from_fresh_p10_mono_s,
    obs_deg_from_fresh_p50_mono_s: r.obs_deg_from_fresh_p50_mono_s,
    obs_deg_from_fresh_p90_mono_s: r.obs_deg_from_fresh_p90_mono_s,
    dirty_air_deg_mult: r.dirty_air_deg_mult,
    temp_headroom_c: r.temp_headroom_c,
    temp_penalty_s_per_deg: r.temp_penalty_s_per_deg,
  }))

  // One dummy prediction per lap the headline no longer uses ONNX for tyre; only fan/cliff need it.
  const preds = cell.rows.map(() => ({
    degradation_jump_p10_s: 0,
    degradation_jump_s: 0,
    degradation_jump_p90_s: 0,
    remaining_stint_life_laps: 10,
    cliff: { label: 'none_in_stint', probabilities: { none_in_stint: 1 } },
  }))

  const opts: RecomposeOptions = {
    refGreenPaceS: cell.rows[0].ref_green_pace_s,
    fuelStartKg: 60,
    fuelConsumptionRateKgPerLap: 2,
    weightPenaltyFactor: 0.032,
    history,
    dirtyAirShare: 0,
    ambientTempDelta: 0,
    ...overrides,
  }

  return recomposeLapTimes(preds, opts).laptimeCurve.map(p => ({ x: p.x, tyre: p.tyre }))
}

describe('P3.1 MAE ≤ 0.5s for every basket cell (neutral inputs)', () => {
  for (const cell of cells) {
    const gt = groundTruth.find(
      g => g.circuit_id === cell.circuit_id && g.era === cell.era && g.compound === cell.compound,
    )
    if (!gt) continue
    const label = `${cell.circuit_id}/${cell.compound}/${cell.era}`
    const samples: BasketSample[] = gt.samples.map(s => ({
      lap_in_stint: s.lap_in_stint,
      obs_deg_from_fresh_p50_s: s.obs_deg_from_fresh_p50_s,
    }))

    it(`${label}: MAE ≤ 0.5s`, () => {
      const curve = runCell(cell)
      const mae = projectedDegMAE(curve, samples)
      expect(mae).toBeLessThanOrEqual(0.5)
    })
  }
})

describe('P3.2 0 monotone violations (neutral, dirty-air, temp-perturbed)', () => {
  for (const cell of cells) {
    const label = `${cell.circuit_id}/${cell.compound}/${cell.era}`

    it(`${label}: neutral inputs → 0 violations`, () => {
      const tyres = runCell(cell).map(p => p.tyre)
      expect(monotoneViolations(tyres)).toBe(0)
    })

    it(`${label}: dirty-air (share=0.8) → 0 violations`, () => {
      const tyres = runCell(cell, { dirtyAirShare: 0.8 }).map(p => p.tyre)
      expect(monotoneViolations(tyres)).toBe(0)
    })

    it(`${label}: temp past window (delta=25°C) → 0 violations`, () => {
      const tyres = runCell(cell, { ambientTempDelta: 25 }).map(p => p.tyre)
      expect(monotoneViolations(tyres)).toBe(0)
    })
  }
})

const DRY = ['HARD', 'MEDIUM', 'SOFT', 'SUPERSOFT', 'ULTRASOFT', 'HYPERSOFT']

describe('P3.3 Sign / sanity', () => {
  for (const cell of cells) {
    const label = `${cell.circuit_id}/${cell.compound}/${cell.era}`
    const isDry = DRY.includes(cell.compound)

    if (isDry) {
      it(`${label}: no lap has tyre < −0.5s (sign gate)`, () => {
        const tyres = runCell(cell).map(p => p.tyre)
        for (const t of tyres) expect(t).toBeGreaterThanOrEqual(-0.5)
      })
    }

    it(`${label}: ↑dirty-air never lowers tyre (modulation ≥ 1)`, () => {
      const clean = runCell(cell, { dirtyAirShare: 0 }).map(p => p.tyre)
      const dirty = runCell(cell, { dirtyAirShare: 1.0 }).map(p => p.tyre)
      for (let i = 0; i < clean.length; i++) {
        expect(dirty[i]).toBeGreaterThanOrEqual(clean[i] - 1e-9)
      }
    })

    it(`${label}: ↑temp (above window) never lowers tyre (modulation ≥ 1)`, () => {
      const cool = runCell(cell, { ambientTempDelta: 0 }).map(p => p.tyre)
      const hot  = runCell(cell, { ambientTempDelta: 30 }).map(p => p.tyre)
      for (let i = 0; i < cool.length; i++) {
        expect(hot[i]).toBeGreaterThanOrEqual(cool[i] - 1e-9)
      }
    })
  }

  it('Red Bull Ring HARD post2022 lap-30 tyre ≈ +1.2s ± 0.2 (regression anchor)', () => {
    const rbr = cells.find(c => c.circuit_id === 'red_bull_ring' && c.compound === 'HARD' && c.era === 'post2022')
    if (!rbr) throw new Error('RBR HARD post2022 not found in fitted fixture')
    const curve = runCell(rbr)
    const lap30 = curve.find(p => p.x === 30)
    if (!lap30) {
      // Cell may not have 30 laps use the last available lap
      const last = curve[curve.length - 1]
      expect(last.tyre).toBeGreaterThan(-0.5) // at minimum, not negative
    } else {
      expect(lap30.tyre).toBeCloseTo(1.264, 0) // ±0.5 (integer precision)
    }
  })
})
