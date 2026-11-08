// AX-06: one test per error code, plus the accepted shapes.
import { describe, it, expect } from 'vitest'
import { catalogue } from './__fixtures__/fixtures'
import { validate, isValidated } from './validate'
import type { QueryError } from './types'

const base = {
  view: 'qv_laps',
  filters: [
    { col: 'season', op: 'eq', val: 2024 },
    { col: 'race_id', op: 'eq', val: '2024_8' },
  ],
  group_by: ['driver_id'],
  aggregate: { fn: 'median', col: 'lap_time_s' },
  order: 'value_asc',
  limit: 10,
}

function code(req: unknown): string {
  const r = validate(req, catalogue)
  return 'status' in r ? (r as QueryError).code : 'ok'
}

describe('validate', () => {
  it('accepts a valid request, applies the default outlier filter and brands it', () => {
    const v = validate(base, catalogue)
    expect('status' in v).toBe(false)
    expect(isValidated(v)).toBe(true)
    if ('status' in v) return
    expect(v.seasons).toEqual([2024])
    expect(v.canonical.filters).toContainEqual({ col: 'is_major_outlier_lap', op: 'eq', val: false })
  })

  it('does not apply the default filter when the request filters that column', () => {
    const v = validate({ ...base, filters: [...base.filters, { col: 'is_major_outlier_lap', op: 'eq', val: true }] }, catalogue)
    if ('status' in v) throw new Error(v.message)
    expect(v.canonical.filters.filter((f) => f.col === 'is_major_outlier_lap')).toEqual([{ col: 'is_major_outlier_lap', op: 'eq', val: true }])
  })

  it('unknown_view lists the views', () => {
    const r = validate({ ...base, view: 'fct_lap_residuals' }, catalogue) as QueryError
    expect(r.code).toBe('unknown_view')
    expect(r.allowed?.views).toContain('qv_laps')
  })
  it('unknown_column lists the allowed columns and ops', () => {
    const r = validate({ ...base, filters: [...base.filters, { col: 'driver_skill_residual_s', op: 'eq', val: 1 }] }, catalogue) as QueryError
    expect(r.code).toBe('unknown_column')
    expect(Object.keys(r.allowed?.filter_columns as object)).toContain('driver_id')
  })
  it('bad_op', () => expect(code({ ...base, filters: [...base.filters, { col: 'driver_id', op: 'gt', val: 'A' }] })).toBe('bad_op'))
  it('bad_op on season ranges', () => expect(code({ ...base, filters: [{ col: 'season', op: 'gte', val: 2024 }] })).toBe('bad_op'))
  it('bad_value: type, length, non-finite, unknown season, prototype keys', () => {
    expect(code({ ...base, filters: [{ col: 'season', op: 'eq', val: '2024' }] })).toBe('bad_value')
    expect(code({ ...base, filters: [...base.filters, { col: 'driver_id', op: 'eq', val: 'x'.repeat(65) }] })).toBe('bad_value')
    expect(code({ ...base, filters: [...base.filters, { col: 'lap_number', op: 'gt', val: Infinity }] })).toBe('bad_value')
    expect(code({ ...base, filters: [{ col: 'season', op: 'eq', val: 2031 }] })).toBe('bad_value')
    expect(code(JSON.parse('{"view":"qv_laps","__proto__":{"x":1},"aggregate":{"fn":"count","col":"laps"}}'))).toBe('bad_value')
    expect(code({ ...base, extra: 1 })).toBe('bad_value')
    expect(code({ ...base, filters: [...base.filters, { col: 'driver_id', op: 'in', val: Array.from({ length: 21 }, (_, i) => `D${i}`) }] })).toBe('bad_value')
    expect(code(null)).toBe('bad_value')
    expect(code([base])).toBe('bad_value')
  })
  it('missing_required_filter: season, and race_id for grouping by lap_number', () => {
    expect(code({ ...base, filters: [] })).toBe('missing_required_filter')
    expect(code({ ...base, filters: [base.filters[0]], group_by: ['lap_number'] })).toBe('missing_required_filter')
    expect(code({ ...base, group_by: ['lap_number'] })).toBe('ok')
  })
  it('missing_required_filter: teammate corners need one race', () => {
    expect(code({ view: 'qv_teammate_corners', filters: [{ col: 'season', op: 'eq', val: 2024 }], aggregate: { fn: 'count', col: 'corners' } })).toBe('missing_required_filter')
  })
  it('too_many_filters', () => {
    const f = [...base.filters, ...['driver_id', 'constructor_id', 'compound', 'stint_id', 'lap_number'].map((col) => ({ col, op: 'eq', val: col === 'lap_number' ? 1 : 'A' }))]
    expect(code({ ...base, filters: f })).toBe('too_many_filters')
  })
  it('too_many_seasons', () => {
    expect(code({ ...base, filters: [{ col: 'season', op: 'in', val: [2022, 2023, 2024] }], group_by: [] })).toBe('too_many_seasons')
    expect(code({ ...base, filters: [{ col: 'season', op: 'between', val: [2018, 2025] }], group_by: [] })).toBe('too_many_seasons')
    expect(code({ ...base, filters: [{ col: 'season', op: 'in', val: [2023, 2024] }], group_by: [] })).toBe('ok')
  })
  it('bad_group_by', () => {
    expect(code({ ...base, group_by: ['lap_time_s'] })).toBe('bad_group_by')
    expect(code({ ...base, group_by: ['driver_id', 'compound', 'constructor_id'] })).toBe('bad_group_by')
    expect(code({ ...base, group_by: ['driver_id', 'driver_id'] })).toBe('bad_group_by')
  })
  it('bad_aggregate: unknown fn, sum on a lap time, count on a column, measure from another view', () => {
    expect(code({ ...base, aggregate: { fn: 'stddev', col: 'lap_time_s' } })).toBe('bad_aggregate')
    expect(code({ ...base, aggregate: { fn: 'sum', col: 'lap_time_s' } })).toBe('bad_aggregate')
    expect(code({ ...base, aggregate: { fn: 'count', col: 'lap_time_s' } })).toBe('bad_aggregate')
    expect(code({ ...base, aggregate: { fn: 'avg', col: 'stint_length_laps' } })).toBe('bad_aggregate')
    expect(code({ ...base, aggregate: { fn: 'count', col: 'laps' } })).toBe('ok')
  })
  it('bad_limit', () => {
    for (const limit of [0, 26, 2.5, '10', -1]) expect(code({ ...base, limit })).toBe('bad_limit')
  })
  it('bad_order', () => expect(code({ ...base, order: 'random' })).toBe('bad_order'))
})
