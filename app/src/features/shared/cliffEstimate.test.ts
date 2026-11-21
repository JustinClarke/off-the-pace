import { describe, it, expect } from 'vitest'
import { cliffOnsetDisplay, formatOnsetRange, isClassDefault, ONSET_IQR_CTE } from './cliffEstimate'

describe('cliffOnsetDisplay', () => {
  it('keeps a measured onset as one lap', () => {
    expect(cliffOnsetDisplay(18, 'fitted', 15, 23)).toEqual({ kind: 'measured', lap: 18 })
    expect(cliffOnsetDisplay(18, 'cross_season_fallback', null, null)).toEqual({ kind: 'measured', lap: 18 })
  })

  it('replaces a class_default onset with the rounded IQR range', () => {
    expect(cliffOnsetDisplay(50, 'class_default', 15, 26.5)).toEqual({ kind: 'estimate', range: [15, 27] })
  })

  it('gives the label only when the compound has no range', () => {
    expect(cliffOnsetDisplay(50, 'class_default', null, null)).toEqual({ kind: 'estimate', range: null })
  })

  it('is null when there is no onset and it is not a default', () => {
    expect(cliffOnsetDisplay(null, 'fitted', 15, 23)).toBeNull()
  })
})

describe('helpers', () => {
  it('flags only class_default', () => {
    expect(isClassDefault('class_default')).toBe(true)
    expect(isClassDefault('fitted')).toBe(false)
    expect(isClassDefault(null)).toBe(false)
  })

  it('formats a range', () => {
    expect(formatOnsetRange([15, 23])).toBe('laps 15–23')
  })

  it('pools only measured onsets and needs at least 5 cells', () => {
    expect(ONSET_IQR_CTE).toContain("onset_source IN ('fitted', 'cross_season_fallback')")
    expect(ONSET_IQR_CTE).toContain('HAVING count(*) >= 5')
  })
})
