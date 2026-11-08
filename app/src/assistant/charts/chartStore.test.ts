import { describe, it, expect, beforeEach } from 'vitest'
import { clearCharts, getChart, getResultRows, nextChartId, saveChart } from './chartStore'
import { clearResults, rememberResult } from '../queryBuilder/store'
import { fakeResult } from './testHelpers'

describe('chartStore', () => {
  beforeEach(() => { clearCharts(); clearResults() })
  it('saves and returns charts by id; ids are unique', () => {
    const id = nextChartId()
    expect(id).not.toBe(nextChartId())
    saveChart({ chart_id: id, spec: { type: 'line', title: 't', x: { col: 'a', label: 'a' }, y: { col: 'b', label: 'b' }, series: [] }, series: [], n: [], label: 'computed_not_card' })
    expect(getChart(id)?.chart_id).toBe(id)
    expect(getChart('nope')).toBeUndefined()
  })
  it('reads rows only for results of this session', () => {
    rememberResult(fakeResult('abc', [{ value: 1, n: 1 }]))
    expect(getResultRows('abc')).toHaveLength(1)
    expect(getResultRows('made_up')).toBeUndefined()
    clearResults()
    expect(getResultRows('abc')).toBeUndefined()
  })
})
