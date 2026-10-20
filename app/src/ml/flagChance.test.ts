import { describe, expect, it } from 'vitest'
import fixture from './__fixtures__/flag_chance_parity.json'
import {
  applyFlagLookup, capToFlag, erfc, flagChance, lapsToFlagFromFuel, normalSf, rawFlagChance,
  type FlagChanceLookup,
} from './flagChance'

// The repo's ONNX parity tolerance (ml/src/export_onnx.py ATOL).
const ATOL = 1e-5
const lookup = fixture.lookup as unknown as FlagChanceLookup

describe('flag chance parity with ml/src/flag_chance.py (shared fixture)', () => {
  it('raw chance, calibrated chance, cap and laps-to-flag match Python within ATOL', () => {
    let worst = { raw: 0, cal: 0, cap: 0, fuel: 0 }
    for (const r of fixture.rows) {
      const raw = rawFlagChance(r.median, r.laps_to_flag, lookup.aft_scale, lookup.label_shift)
      worst = {
        raw: Math.max(worst.raw, Math.abs(raw - r.raw)),
        cal: Math.max(worst.cal, Math.abs(applyFlagLookup(raw, lookup) - r.calibrated)),
        cap: Math.max(worst.cap, Math.abs(capToFlag(r.median, r.laps_to_flag) - r.capped_median)),
        fuel: Math.max(worst.fuel, Math.abs(lapsToFlagFromFuel(r.fuel_kg, r.burn) - r.laps_to_flag_from_fuel)),
      }
    }
    expect(fixture.rows.length).toBeGreaterThan(100)
    expect(worst.raw).toBeLessThan(ATOL)
    expect(worst.cal).toBeLessThan(ATOL)
    expect(worst.cap).toBeLessThan(ATOL)
    expect(worst.fuel).toBeLessThan(ATOL)
  })
})

describe('flag chance pieces', () => {
  it('erfc / normalSf hit known values', () => {
    expect(erfc(0)).toBeCloseTo(1, 7)
    expect(normalSf(0)).toBeCloseTo(0.5, 7)
    expect(normalSf(1.2815515655446004)).toBeCloseTo(0.1, 6)
    expect(normalSf(-1.959963984540054)).toBeCloseTo(0.975, 6)
  })

  it('the chance is 0.5 when the median sits exactly on the flag', () => {
    expect(rawFlagChance(12, 12, 0.75)).toBeCloseTo(0.5, 7)
  })

  it('cap is a min, and an unknown race length leaves the value alone', () => {
    expect(capToFlag(21.3, 12)).toBe(12)
    expect(capToFlag(5, 12)).toBe(5)
    expect(capToFlag(8, null)).toBe(8)
  })

  it('lookup clamps outside its range and interpolates inside it', () => {
    const lk = { x: [0.2, 0.8], y: [0.1, 0.9] }
    expect(applyFlagLookup(0, lk)).toBe(0.1)
    expect(applyFlagLookup(1, lk)).toBe(0.9)
    expect(applyFlagLookup(0.5, lk)).toBeCloseTo(0.5, 12)
  })

  it('refuses a lookup fitted for another model version', () => {
    expect(flagChance(12, 12, lookup, 'some-other-version')).toBeNull()
    expect(flagChance(12, 12, null)).toBeNull()
    expect(flagChance(12, 12, lookup, lookup.model_version)).not.toBeNull()
  })
})

describe('shipped lookup (public/models/flag_chance_lookup.json)', () => {
  it('is paired with the served model manifest version and is a valid monotone table', async () => {
    const { readFileSync } = await import('node:fs')
    const dir = 'public/models/'  // vitest runs from app/
    const lk = JSON.parse(readFileSync(dir + 'flag_chance_lookup.json', 'utf8')) as FlagChanceLookup & { weighting: { rule: string } }
    const manifest = JSON.parse(readFileSync(dir + 'manifest.json', 'utf8')) as { model_version: string }
    expect(lk.model_version).toBe(manifest.model_version)
    expect(lk.weighting.rule).toBe('last3')
    expect(lk.x.length).toBe(lk.y.length)
    expect(lk.x.every((v, i) => i === 0 || v > lk.x[i - 1])).toBe(true)
    expect(flagChance(10, 10, lk, manifest.model_version)).not.toBeNull()
  })
})
