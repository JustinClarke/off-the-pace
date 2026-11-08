// AX-05: catalogue.json (real scratch-export output, checked in as a fixture) parses as a Catalogue.
import { describe, it, expect } from 'vitest'
import fixture from './__fixtures__/catalogue.json'
import { parseCatalogue, getView } from './catalogue'

describe('catalogue.json', () => {
  it('parses against the Catalogue type', () => {
    const cat = parseCatalogue(fixture)
    expect(cat.views.map((v) => v.name)).toEqual([
      'qv_laps', 'qv_stints', 'qv_pit_stops', 'qv_driver_race', 'qv_race_laps',
      'qv_circuit_history', 'qv_teammate_corners', 'qv_circuits', 'qv_compounds',
    ])
    expect(cat.limits.max_limit).toBe(25)
    expect(getView(cat, 'qv_laps')?.required_filters).toContain('season')
  })

  it('rejects a broken catalogue', () => {
    const bad = structuredClone(fixture) as unknown as { views: { columns: { ops: string[] }[] }[] }
    bad.views[0].columns[0].ops = ['drop']
    expect(() => parseCatalogue(bad)).toThrow(/ops/)
    expect(() => parseCatalogue({ ...fixture, catalogue_version: 'x' })).toThrow(/catalogue_version/)
  })
})
