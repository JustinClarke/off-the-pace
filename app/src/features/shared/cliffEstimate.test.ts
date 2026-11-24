import { describe, it, expect } from 'vitest'
import {
  BORROWED_ESTIMATE_LABEL, CLIFF_ESTIMATE_LABEL, UNKNOWN_SOURCE_LABEL,
  cliffOnsetDisplay, formatOnsetRange, isClassDefault, ONSET_IQR_CTE, paramNoteLabel, paramSourceNote,
} from './cliffEstimate'

describe('cliffOnsetDisplay', () => {
  it('keeps a measured onset as one lap', () => {
    expect(cliffOnsetDisplay(18, 'fitted', 15, 23)).toEqual({ kind: 'measured', lap: 18 })
  })

  it('flags cross-season, pooled and carried-forward onsets as borrowed, not measured', () => {
    for (const src of ['cross_season_fallback', 'pooled_compound_fallback', 'carried_forward']) {
      expect(cliffOnsetDisplay(18, src, null, null)).toEqual({ kind: 'measured', lap: 18, borrowed: true })
    }
  })

  it('keeps a null onset source distinct: unknown, not fitted', () => {
    expect(cliffOnsetDisplay(18, null, null, null)).toEqual({ kind: 'measured', lap: 18, unknown: true })
    expect(cliffOnsetDisplay(18, undefined, null, null)).toEqual({ kind: 'measured', lap: 18, unknown: true })
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

  it('pools only own-history (fitted) onsets and needs at least 5 cells', () => {
    expect(ONSET_IQR_CTE).toContain("onset_source IN ('fitted')")
    expect(ONSET_IQR_CTE).not.toContain('cross_season_fallback')
    expect(ONSET_IQR_CTE).toContain('HAVING count(*) >= 5')
  })
})

// Onset, gradient and severity each read their OWN source column; the same mapping applies to all three.
describe('paramSourceNote per parameter', () => {
  const sources: Array<[string | null | undefined, ReturnType<typeof paramSourceNote>, string | null]> = [
    ['fitted', null, null],
    ['cross_season_fallback', 'borrowed', BORROWED_ESTIMATE_LABEL],
    ['pooled_compound_fallback', 'borrowed', BORROWED_ESTIMATE_LABEL],
    ['carried_forward', 'borrowed', BORROWED_ESTIMATE_LABEL],
    ['class_default', 'estimate', CLIFF_ESTIMATE_LABEL],
    [null, 'unknown', UNKNOWN_SOURCE_LABEL],
    [undefined, 'unknown', UNKNOWN_SOURCE_LABEL],
  ]
  for (const param of ['onset', 'gradient', 'severity']) {
    for (const [src, note, label] of sources) {
      it(`${param}: ${String(src)} -> ${String(note)}`, () => {
        expect(paramSourceNote(src)).toBe(note)
        expect(paramNoteLabel(paramSourceNote(src))).toBe(label)
      })
    }
  }

  it('onset display agrees with the shared mapping for every source', () => {
    expect(cliffOnsetDisplay(18, 'fitted', null, null)).toEqual({ kind: 'measured', lap: 18 })
    for (const src of ['cross_season_fallback', 'pooled_compound_fallback', 'carried_forward']) {
      expect(cliffOnsetDisplay(18, src, null, null)).toMatchObject({ kind: 'measured', borrowed: true })
    }
    expect(cliffOnsetDisplay(18, 'class_default', null, null)).toEqual({ kind: 'estimate', range: null })
  })
})
