import { describe, it, expect } from 'vitest'
import { transform, CLIFF_CLASSES } from './transform'
import type { ScoreboardRow } from './queries'

function makeRow(overrides: Partial<ScoreboardRow> = {}): ScoreboardRow {
  return {
    lap_id: 'test_lap',
    driver_id: 'VER',
    circuit_key: 'monaco',
    race_year: 2024,
    compound: 'MEDIUM',
    lap_in_stint: 5,
    predicted_degradation_jump_s: 0.2,
    predicted_degradation_jump_p10_s: -0.1,
    predicted_degradation_jump_p90_s: 0.5,
    actual_degradation_jump_s: 0.25,
    is_in_envelope: true,
    predicted_cliff_class: 'none_in_stint',
    actual_cliff_class: 'none_in_stint',
    predicted_remaining_stint_life_laps: 8,
    predicted_remaining_stint_life_p10_laps: 5,
    predicted_remaining_stint_life_p90_laps: 13,
    actual_remaining_stint_life_laps: 9,
    is_censored_stint: false,
    prob_0_to_2: 0.1,
    prob_3_to_5: 0.15,
    prob_6_plus: 0.1,
    prob_none_in_stint: 0.65,
    ...overrides,
  }
}

describe('transform', () => {
  it('produces one scatter point per non-null actual row', () => {
    const rows = [makeRow(), makeRow({ actual_degradation_jump_s: null })]
    const result = transform(rows)
    expect(result.scatter).toHaveLength(1)
  })

  it('scatter x = actual, y = predicted p50', () => {
    const row = makeRow({ actual_degradation_jump_s: 0.3, predicted_degradation_jump_s: 0.2 })
    const result = transform([row])
    expect(result.scatter[0].x).toBe(0.3)
    expect(result.scatter[0].y).toBe(0.2)
  })

  it('coverage stat matches is_in_envelope fraction', () => {
    const rows = [
      makeRow({ is_in_envelope: true }),
      makeRow({ is_in_envelope: false }),
      makeRow({ is_in_envelope: true }),
    ]
    const result = transform(rows)
    expect(result.coverageStat.n).toBe(3)
    expect(result.coverageStat.empirical).toBeCloseTo(2 / 3)
    expect(result.coverageStat.nominal).toBe(0.80)
  })

  it('confusion matrix covers all 16 cells (4x4)', () => {
    const result = transform([makeRow()])
    expect(result.confusion).toHaveLength(CLIFF_CLASSES.length * CLIFF_CLASSES.length)
  })

  it('confusion matrix diagonal cell is 1 for perfect prediction', () => {
    const result = transform([makeRow({ predicted_cliff_class: 'none_in_stint', actual_cliff_class: 'none_in_stint' })])
    const diagCell = result.confusion.find(c => c.predicted === 'none_in_stint' && c.actual === 'none_in_stint')
    expect(diagCell?.count).toBe(1)
    expect(diagCell?.rowShare).toBe(1)
  })

  it('row-share sums to 1 for each predicted class with data', () => {
    const rows = [
      makeRow({ predicted_cliff_class: '0_to_2', actual_cliff_class: 'none_in_stint' }),
      makeRow({ predicted_cliff_class: '0_to_2', actual_cliff_class: '0_to_2' }),
    ]
    const result = transform(rows)
    const rowCells = result.confusion.filter(c => c.predicted === '0_to_2')
    const sumShare = rowCells.reduce((s, c) => s + c.rowShare, 0)
    expect(sumShare).toBeCloseTo(1.0)
  })

  it('compound filter restricts scatter and coverage', () => {
    const rows = [makeRow({ compound: 'SOFT' }), makeRow({ compound: 'HARD' })]
    const result = transform(rows, 'SOFT')
    expect(result.scatter.every(p => p.compound === 'SOFT')).toBe(true)
  })

  it('compoundFilter list is always over unfiltered rows', () => {
    const rows = [makeRow({ compound: 'SOFT' }), makeRow({ compound: 'HARD' })]
    const result = transform(rows, 'SOFT')
    expect(result.compoundFilter).toContain('HARD')
    expect(result.compoundFilter).toContain('SOFT')
  })

  it('empty rows produce zero coverage n', () => {
    const result = transform([])
    expect(result.coverageStat.n).toBe(0)
    expect(result.coverageStat.empirical).toBe(0)
  })
})

describe('stint life, split by censoring', () => {
  it('routes rows to the population their censoring flag names', () => {
    const r = transform([
      makeRow({ is_censored_stint: false }),
      makeRow({ is_censored_stint: true }),
      makeRow({ is_censored_stint: true }),
    ])
    expect(r.stintLife.uncensored.n).toBe(1)
    expect(r.stintLife.censored.n).toBe(2)
    expect(r.stintLife.censoredShare).toBeCloseTo(2 / 3)
  })

  it('reports no point error for censored laps', () => {
    // The observed life is a lower bound there, so a distance to it is not an error.
    const r = transform([makeRow({ is_censored_stint: true })])
    expect(r.stintLife.censored.medianAbsErrorLaps).toBeNull()
    expect(r.stintLife.uncensored.medianAbsErrorLaps).toBeNull() // empty population
  })

  it('measures uncensored error against the predicted median', () => {
    const r = transform([
      makeRow({ predicted_remaining_stint_life_laps: 8, actual_remaining_stint_life_laps: 11 }),
      makeRow({ predicted_remaining_stint_life_laps: 8, actual_remaining_stint_life_laps: 9 }),
    ])
    expect(r.stintLife.uncensored.medianAbsErrorLaps).toBeCloseTo(2) // median of |3|,|1|
  })

  it('counts an uncensored lap as consistent only inside the band', () => {
    const inside = transform([makeRow({ actual_remaining_stint_life_laps: 9 })])
    const outside = transform([makeRow({ actual_remaining_stint_life_laps: 40 })])
    expect(inside.stintLife.uncensored.bandConsistentShare).toBe(1)
    expect(outside.stintLife.uncensored.bandConsistentShare).toBe(0)
  })

  it('counts a censored lap as consistent when p90 reaches the observed bound', () => {
    // p90 = 13. A tyre seen to last 11 is consistent; one seen to last 20 is not,
    // because the band never reaches a life we actually observed.
    const reaches = transform([makeRow({ is_censored_stint: true, actual_remaining_stint_life_laps: 11 })])
    const falls = transform([makeRow({ is_censored_stint: true, actual_remaining_stint_life_laps: 20 })])
    expect(reaches.stintLife.censored.bandConsistentShare).toBe(1)
    expect(falls.stintLife.censored.bandConsistentShare).toBe(0)
  })

  it('does not let a censored lap fail for overshooting the bound', () => {
    // The asymmetry is the point: predicting far MORE life than we observed is fine
    // on a censored lap (the race ended, the tyre did not), and would be an error
    // on an uncensored one.
    const row = { actual_remaining_stint_life_laps: 1 }
    expect(transform([makeRow({ ...row, is_censored_stint: true })])
      .stintLife.censored.bandConsistentShare).toBe(1)
    expect(transform([makeRow({ ...row, is_censored_stint: false })])
      .stintLife.uncensored.bandConsistentShare).toBe(0)
  })

  it('ignores rows with no actual life', () => {
    const r = transform([makeRow({ actual_remaining_stint_life_laps: null })])
    expect(r.stintLife.uncensored.n).toBe(0)
    expect(r.stintLife.censored.n).toBe(0)
  })
})
