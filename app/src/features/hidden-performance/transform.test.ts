import { describe, it, expect } from 'vitest'
import { transform, seasonTransform, toCsvRows, toSeasonCsvRows } from './transform'
import type { HiddenPerformanceRow, SeasonRow } from './queries'

const base: HiddenPerformanceRow = {
  ego_driver_id: 'VER',
  race_id: '2023_1',
  circuit_name: 'Bahrain International Circuit',
  race_year: 2023,
  host_constructor_id: 'Williams',
  ego_constructor_id: 'Red Bull',
  predicted_finish_position: 7,
  actual_finish_position: 15,
  delta_vs_actual_position: -8,
  finish_pos_se: 1.4,
  avg_recombination_confidence: 0.72,
  laps_counted: 57,
  adjusted_delta: -2.5,
  adjusted_delta_z: -1.79,
  affinity_shrunk_s: -0.31,
  affinity_confidence: 0.82,
  driver_season_rating: -0.12,
}

describe('transform', () => {
  it('maps row fields correctly', () => {
    const result = transform([base])
    expect(result).toHaveLength(1)
    expect(result[0].driver).toBe('VER')
    expect(result[0].team).toBe('Red Bull')
    expect(result[0].race).toBe('Bahrain International Circuit')
    expect(result[0].delta).toBe(-8)
    expect(result[0].adjustedDelta).toBe(-2.5)
    expect(result[0].adjustedDeltaZ).toBeCloseTo(-1.79)
    expect(result[0].finishPosSe).toBe(1.4)
    expect(result[0].affinityS).toBe(-0.31)
    expect(result[0].driverRating).toBe(-0.12)
  })

  it('excludes rows with null delta', () => {
    const nullDelta = { ...base, delta_vs_actual_position: null }
    expect(transform([nullDelta])).toHaveLength(0)
  })

  it('excludes rows with null actual', () => {
    const nullActual = { ...base, actual_finish_position: null }
    expect(transform([nullActual])).toHaveLength(0)
  })

  it('handles null optional fields', () => {
    const sparse = { ...base, circuit_name: null, ego_constructor_id: null, adjusted_delta: null, adjusted_delta_z: null, affinity_shrunk_s: null, affinity_confidence: null, driver_season_rating: null }
    const result = transform([sparse])
    expect(result[0].race).toBe('2023_1')  // falls back to race_id when circuit_name is null
    expect(result[0].team).toBeNull()
    expect(result[0].adjustedDelta).toBeNull()
    expect(result[0].affinityS).toBeNull()
    expect(result[0].driverRating).toBeNull()
  })
})

describe('seasonTransform', () => {
  const baseRow: SeasonRow = {
    ego_driver_id: 'ALO',
    ego_constructor_id: 'Aston Martin',
    mean_raw_delta: -12,
    mean_adjusted_delta: -5,
    sd_adjusted_delta: 2.1,
    n_races: 10,
    total_laps: 570,
    mean_confidence: 0.68,
    driver_season_rating: -0.08,
  }

  it('maps season fields', () => {
    const result = seasonTransform([baseRow])
    expect(result).toHaveLength(1)
    expect(result[0].driver).toBe('ALO')
    expect(result[0].team).toBe('Aston Martin')
    expect(result[0].meanAdjustedDelta).toBe(-5)
    expect(result[0].nRaces).toBe(10)
  })
})

describe('toCsvRows', () => {
  it('produces expected keys', () => {
    const rows = toCsvRows(transform([base]))
    expect(rows[0]).toHaveProperty('delta_positions')
    expect(rows[0]).toHaveProperty('adjusted_delta')
    expect(rows[0]).toHaveProperty('finish_pos_se')
    expect(rows[0]).toHaveProperty('team')
  })
})

describe('toSeasonCsvRows', () => {
  it('produces expected keys', () => {
    const rows = toSeasonCsvRows(seasonTransform([{
      ego_driver_id: 'ALO', ego_constructor_id: 'Aston Martin',
      mean_raw_delta: -12, mean_adjusted_delta: -5, sd_adjusted_delta: 2.1,
      n_races: 10, total_laps: 570, mean_confidence: 0.68, driver_season_rating: -0.08,
    }]))
    expect(rows[0]).toHaveProperty('mean_adjusted_delta')
    expect(rows[0]).toHaveProperty('driver_season_rating')
  })
})
