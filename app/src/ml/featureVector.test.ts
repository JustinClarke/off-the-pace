import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { buildFeatureVector, encodeValue } from './featureVector'
import type { ManifestInput, ModelManifest } from './manifest'

// Use the real shipped manifest so the encoding rules are tested against the true contract.
const manifest = JSON.parse(
  readFileSync(join(__dirname, '../../public/models/manifest.json'), 'utf8')
) as ModelManifest
const input: ManifestInput = manifest.input
const enc = input.encoding

describe('encodeValue categorical', () => {
  it('maps a known compound level to its ordinal', () => {
    expect(encodeValue('compound', 'SOFT', enc)).toBe(enc.encoders.compound.SOFT)
    expect(encodeValue('compound', 'HARD', enc)).toBe(0)
  })

  it('maps NULL/undefined categorical to the missing ordinal', () => {
    expect(encodeValue('compound', null, enc)).toBe(enc.missing_ordinal)
    expect(encodeValue('compound', undefined, enc)).toBe(enc.missing_ordinal)
  })

  it('maps an unseen categorical level to the missing ordinal', () => {
    expect(encodeValue('compound', 'PLASTIC', enc)).toBe(enc.missing_ordinal)
    expect(encodeValue('constructor_id', 'Brawn GP', enc)).toBe(enc.missing_ordinal)
  })

  it('coerces non-string keys via String()', () => {
    // constructor_id keys are strings; a numeric lookalike should still resolve by string key.
    expect(encodeValue('air_state_dominant', 'free_air', enc)).toBe(enc.encoders.air_state_dominant.free_air)
  })
})

describe('encodeValue boolean', () => {
  it('maps true/false to 1/0', () => {
    expect(encodeValue('is_rain_lap', true, enc)).toBe(1)
    expect(encodeValue('is_rain_lap', false, enc)).toBe(0)
    expect(encodeValue('cliff_onset_passed', true, enc)).toBe(1)
  })

  it('tolerates string/number truthiness from a DB', () => {
    expect(encodeValue('event_flag_any', 'true', enc)).toBe(1)
    expect(encodeValue('event_flag_any', 0, enc)).toBe(0)
    expect(encodeValue('event_flag_any', '1', enc)).toBe(1)
  })

  it('preserves NULL boolean as NaN (native-missing)', () => {
    expect(encodeValue('is_rain_lap', null, enc)).toBeNaN()
  })
})

describe('encodeValue continuous', () => {
  it('passes numbers through', () => {
    expect(encodeValue('lap_number', 12, enc)).toBe(12)
    expect(encodeValue('fuel_mass_kg', 45.5, enc)).toBeCloseTo(45.5)
  })

  it('coerces numeric strings', () => {
    expect(encodeValue('lap_number', '12', enc)).toBe(12)
  })

  it('preserves NULL / non-numeric as NaN (never imputes)', () => {
    expect(encodeValue('fuel_mass_kg', null, enc)).toBeNaN()
    expect(encodeValue('fuel_mass_kg', undefined, enc)).toBeNaN()
    expect(encodeValue('fuel_mass_kg', 'n/a', enc)).toBeNaN()
  })

  it('coerces bigint (DuckDB int columns arrive as bigint)', () => {
    expect(encodeValue('lap_number', 7n, enc)).toBe(7)
  })
})

describe('buildFeatureVector', () => {
  it('produces a Float32Array of exactly n_features in feature_order', () => {
    const row = { lap_number: 5, compound: 'MEDIUM', is_rain_lap: false }
    const vec = buildFeatureVector(row, input)
    expect(vec).toBeInstanceOf(Float32Array)
    expect(vec.length).toBe(input.n_features)
    expect(vec.length).toBe(38)
  })

  it('places each encoded value at its feature_order index', () => {
    const row = { compound: 'SOFT', lap_number: 9 }
    const vec = buildFeatureVector(row, input)
    const compoundIdx = input.feature_order.indexOf('compound')
    const lapIdx = input.feature_order.indexOf('lap_number')
    expect(vec[compoundIdx]).toBe(enc.encoders.compound.SOFT)
    expect(vec[lapIdx]).toBe(9)
  })

  it('treats missing keys as NULL per column role', () => {
    const vec = buildFeatureVector({}, input)
    const compoundIdx = input.feature_order.indexOf('compound') // categorical → missing ordinal
    const fuelIdx = input.feature_order.indexOf('fuel_mass_kg') // continuous → NaN
    const rainIdx = input.feature_order.indexOf('is_rain_lap') // boolean → NaN
    expect(vec[compoundIdx]).toBe(enc.missing_ordinal)
    expect(vec[fuelIdx]).toBeNaN()
    expect(vec[rainIdx]).toBeNaN()
  })
})
