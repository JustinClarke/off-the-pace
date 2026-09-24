import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { buildFeatureVector, encodeValue } from './featureVector'
import { getModelInput } from './manifest'
import type { ManifestInput, ModelInputSpec, ModelManifest } from './manifest'

// Use the real shipped manifest so the encoding rules are tested against the true contract.
const manifest = JSON.parse(
  readFileSync(join(__dirname, '../../public/models/manifest.json'), 'utf8')
) as ModelManifest
const input: ManifestInput = manifest.input
const enc = input.encoding

// A representative model's input spec (32-wide) for the encodeValue/single-model tests below,
// which only care about feature ORDER and encoding, not which model owns it.
const p50Model: ModelInputSpec = getModelInput(manifest, 'degradation_regressor_p50')

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
    expect(encodeValue('air_state_dominant', 'plasma_air', enc)).toBe(enc.missing_ordinal)
  })

  it('coerces non-string keys via String()', () => {
    // air_state_dominant keys are strings; a lookalike should still resolve by string key.
    expect(encodeValue('air_state_dominant', 'free_air', enc)).toBe(enc.encoders.air_state_dominant.free_air)
  })
})

describe('encodeValue boolean', () => {
  it('maps true/false to 1/0', () => {
    expect(encodeValue('cliff_onset_passed', true, enc)).toBe(1)
    expect(encodeValue('cliff_onset_passed', false, enc)).toBe(0)
  })

  it('tolerates string/number truthiness from a DB', () => {
    expect(encodeValue('cliff_onset_passed', 'true', enc)).toBe(1)
    expect(encodeValue('cliff_onset_passed', 0, enc)).toBe(0)
    expect(encodeValue('cliff_onset_passed', '1', enc)).toBe(1)
  })

  it('preserves NULL boolean as NaN (native-missing)', () => {
    expect(encodeValue('cliff_onset_passed', null, enc)).toBeNaN()
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
  it('produces a Float32Array of exactly the model\'s n_features in its own feature_order', () => {
    const row = { lap_number: 5, compound: 'MEDIUM', cliff_onset_passed: false }
    const vec = buildFeatureVector(row, p50Model)
    expect(vec).toBeInstanceOf(Float32Array)
    expect(vec.length).toBe(p50Model.n_features)
    expect(vec.length).toBe(32) // degradation_regressor family, per the shipped manifest's models[i].n_features
  })

  it('places each encoded value at its feature_order index', () => {
    const row = { compound: 'SOFT', lap_number: 9 }
    const vec = buildFeatureVector(row, p50Model)
    const compoundIdx = p50Model.feature_order.indexOf('compound')
    const lapIdx = p50Model.feature_order.indexOf('lap_number')
    expect(vec[compoundIdx]).toBe(enc.encoders.compound.SOFT)
    expect(vec[lapIdx]).toBe(9)
  })

  it('treats missing keys as NULL per column role', () => {
    const vec = buildFeatureVector({}, p50Model)
    const compoundIdx = p50Model.feature_order.indexOf('compound') // categorical → missing ordinal
    const fuelIdx = p50Model.feature_order.indexOf('fuel_mass_kg') // continuous → NaN
    const cliffFlagIdx = p50Model.feature_order.indexOf('cliff_onset_passed') // boolean → NaN
    expect(vec[compoundIdx]).toBe(enc.missing_ordinal)
    expect(vec[fuelIdx]).toBeNaN()
    expect(vec[cliffFlagIdx]).toBeNaN()
  })
})

// T7 (WI-04/F3): a manifest-shape regression guard. Runs buildFeatureVector per model against
// the ACTUAL shipped manifest (not a fixture), so the next contract change -- a model dropped, a
// width changed, feature_order renamed -- fails this build immediately instead of shipping a
// Degradation Simulator that throws for every user. This is what F3 exploited: featureVector.ts
// kept reading a retired top-level input.n_features/feature_order and nothing caught it because
// no test ran buildFeatureVector against the real, current manifest.json.
describe('T7: per-model feature vector shape regression guard', () => {
  const EXPECTED_WIDTHS: Record<string, number> = {
    degradation_regressor_p10: 32,
    degradation_regressor_p50: 32,
    degradation_regressor_p90: 32,
    cliff_classifier: 39,
    stint_life_regressor: 32,
  }

  it('ships exactly the five expected models', () => {
    expect(manifest.models.map(m => m.name).sort()).toEqual(Object.keys(EXPECTED_WIDTHS).sort())
  })

  it.each(manifest.models.map(m => m.name))('%s: builds a vector of its declared width from the real manifest', (name) => {
    const model = getModelInput(manifest, name)
    expect(model.feature_order.length).toBe(model.n_features)
    expect(model.n_features).toBe(EXPECTED_WIDTHS[name])

    const vec = buildFeatureVector({}, model)
    expect(vec).toBeInstanceOf(Float32Array)
    expect(vec.length).toBe(EXPECTED_WIDTHS[name])
  })

  it('cliff_classifier\'s feature_union superset matches manifest.input.feature_union', () => {
    // feature_union is what verifyParity.ts fetches one raw row on; it must stay the union
    // of every model's own feature_order, or a caller will under-fetch a column some model needs.
    const union = new Set(manifest.models.flatMap(m => m.feature_order))
    expect([...union].sort()).toEqual([...input.feature_union].sort())
  })
})
