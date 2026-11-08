import { describe, it, expect, beforeEach } from 'vitest'
import { makeChart, MAX_POINTS, MAX_SERIES } from './makeChart'
import { clearCharts, getChart } from './chartStore'
import { clearResults, rememberResult } from '../queryBuilder/store'
import { fakeResult } from './testHelpers'

const rows = (n: number) => Array.from({ length: n }, (_, i) => ({ lap_number: i + 1, value: 90 + i / 10, n: 1 }))
const spec = (over: Record<string, unknown> = {}, ids: string[] = ['r1']) => ({
  type: 'line', title: 'T', x: { col: 'lap_number', label: 'Lap' }, y: { col: 'value', label: 'Time' },
  series: ids.map((id, i) => ({ result_id: id, label: `S${i}`, x_col: 'lap_number', y_col: 'value' })),
  ...over,
})

describe('make_chart', () => {
  beforeEach(() => { clearCharts(); clearResults(); rememberResult(fakeResult('r1', rows(10) as never)) })
  it('accepts a valid spec and returns only chart_id, n, series_count', () => {
    const r = makeChart(spec())
    expect(r).toMatchObject({ status: 'ok', n: 10, series_count: 1 })
    expect(Object.keys(r).sort()).toEqual(['chart_id', 'n', 'series_count', 'status'])
    expect(getChart((r as { chart_id: string }).chart_id)?.series[0].points).toHaveLength(10)
  })
  it('6 series ok, 7 rejected naming the limit', () => {
    expect(makeChart(spec({}, Array(MAX_SERIES).fill('r1'))).status).toBe('ok')
    const r = makeChart(spec({}, Array(MAX_SERIES + 1).fill('r1')))
    expect(r).toMatchObject({ status: 'error' })
    expect((r as { reason: string }).reason).toMatch(/at most 6 series/)
  })
  it('500 points ok, 501 rejected naming the limit', () => {
    rememberResult(fakeResult('r500', rows(MAX_POINTS) as never))
    rememberResult(fakeResult('r501', rows(MAX_POINTS + 1) as never))
    expect(makeChart(spec({}, ['r500'])).status).toBe('ok')
    const r = makeChart(spec({}, ['r501']))
    expect((r as { reason: string }).reason).toMatch(/at most 500/)
  })
  it('rejects a made-up or foreign result_id', () => {
    expect(makeChart(spec({}, ['zzz'])).status).toBe('error')
  })
  it('rejects a column the result does not have', () => {
    const s = spec(); (s.series[0] as { y_col: string }).y_col = 'nope'
    expect((makeChart(s) as { reason: string }).reason).toMatch(/y_col/)
  })
  it('rejects bad types, long or control-char text, non-objects', () => {
    expect(makeChart(spec({ type: 'pie' })).status).toBe('error')
    expect(makeChart(spec({ title: 'x'.repeat(81) })).status).toBe('error')
    expect(makeChart(spec({ title: 'a\u0000b' })).status).toBe('error')
    expect(makeChart(null).status).toBe('error')
    expect(makeChart(spec({ x: { col: 'lap_number; DROP', label: 'Lap' } })).status).toBe('error')
  })
  it('keeps an HTML title as inert text', () => {
    const r = makeChart(spec({ title: '<img src=x onerror=alert(1)>' })) as { chart_id: string }
    expect(getChart(r.chart_id)?.spec.title).toBe('<img src=x onerror=alert(1)>')
  })
})
