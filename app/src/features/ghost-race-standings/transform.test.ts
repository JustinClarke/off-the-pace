import { describe, it, expect } from 'vitest'
import { transform, toCsvRows, CONFIDENCE_FLOOR } from './transform'
import type { GhostStandingsRow } from './queries'

function makeRow(overrides: Partial<GhostStandingsRow> = {}): GhostStandingsRow {
  return {
    ghost_race_id: 'abc',
    race_year: 2024,
    race_id: '2024_1',
    ego_driver_id: 'HAM',
    host_constructor_id: 'mercedes',
    is_self_scenario: false,
    predicted_finish_position: 1,
    actual_finish_position: 1,
    delta_vs_actual_position: 0,
    predicted_mean_lap_s: 94.7,
    predicted_total_race_time_s: 5400,
    actual_total_race_time_s: 5400,
    laps_counted: 57,
    race_distance_laps: 57,
    lap_coverage: 1,
    is_short_run: false,
    avg_recombination_confidence: 0.85,
    ...overrides,
  }
}

describe('transform', () => {
  it('returns empty result for no rows', () => {
    const r = transform([])
    expect(r.scenarios).toHaveLength(0)
    expect(r.totalRows).toBe(0)
  })

  it('groups rows into scenarios by race + constructor', () => {
    const rows = [
      makeRow({ ego_driver_id: 'HAM', race_id: '2024_1', host_constructor_id: 'mercedes', predicted_finish_position: 1, actual_finish_position: 1, delta_vs_actual_position: 0 }),
      makeRow({ ego_driver_id: 'VER', race_id: '2024_1', host_constructor_id: 'mercedes', predicted_finish_position: 2, actual_finish_position: 1, delta_vs_actual_position: 1 }),
      makeRow({ ego_driver_id: 'HAM', race_id: '2024_2', host_constructor_id: 'mercedes', predicted_finish_position: 3, actual_finish_position: 1, delta_vs_actual_position: 2 }),
    ]
    const r = transform(rows)
    expect(r.scenarios).toHaveLength(2)
    expect(r.totalRows).toBe(3)
  })

  it('sorts entries within a scenario by predicted position asc', () => {
    const rows = [
      makeRow({ ego_driver_id: 'VER', predicted_finish_position: 3, delta_vs_actual_position: 2 }),
      makeRow({ ego_driver_id: 'HAM', predicted_finish_position: 1, delta_vs_actual_position: 0, avg_recombination_confidence: 0.95 }),
    ]
    const r = transform(rows)
    const entries = r.scenarios[0].entries
    expect(entries[0].driverId).toBe('HAM')
    expect(entries[1].driverId).toBe('VER')
  })

  it('computes minConfidence across entries', () => {
    const rows = [
      makeRow({ ego_driver_id: 'HAM', avg_recombination_confidence: 0.9, predicted_finish_position: 1, delta_vs_actual_position: 0 }),
      makeRow({ ego_driver_id: 'VER', avg_recombination_confidence: 0.4, predicted_finish_position: 2, delta_vs_actual_position: 1 }),
    ]
    const r = transform(rows)
    expect(r.scenarios[0].minConfidence).toBeCloseTo(0.4)
  })

  it('marks self-scenario from the mart column', () => {
    const rows = [
      makeRow({ is_self_scenario: true }),
    ]
    const r = transform(rows)
    expect(r.scenarios[0].entries[0].isSelfScenario).toBe(true)
  })

  it('does not mark self-scenario when the column is false', () => {
    const rows = [
      makeRow({ is_self_scenario: false, delta_vs_actual_position: 0 }),
    ]
    const r = transform(rows)
    expect(r.scenarios[0].entries[0].isSelfScenario).toBe(false)
  })

  it('passes through a null delta (DNF) without coercing it', () => {
    const rows = [
      makeRow({ delta_vs_actual_position: null, is_short_run: true, lap_coverage: 0.2 }),
    ]
    const r = transform(rows)
    expect(r.scenarios[0].entries[0].delta).toBeNull()
    expect(r.scenarios[0].entries[0].isShortRun).toBe(true)
  })

  it('CONFIDENCE_FLOOR matches the filter applied in the mart (0.3)', () => {
    expect(CONFIDENCE_FLOOR).toBe(0.3)
  })

  it('toCsvRows produces one row per entry', () => {
    const rows = [
      makeRow({ ego_driver_id: 'HAM', predicted_finish_position: 1, delta_vs_actual_position: 0, avg_recombination_confidence: 0.95 }),
      makeRow({ ego_driver_id: 'VER', predicted_finish_position: 2, delta_vs_actual_position: 1 }),
    ]
    const result = transform(rows)
    const csv = toCsvRows(result)
    expect(csv).toHaveLength(2)
    expect(csv[0].driver_id).toBe('HAM')
  })
})
