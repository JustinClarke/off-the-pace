// AX-06: parameters, identifier source, multi-season.
import { describe, it, expect } from 'vitest'
import { catalogue } from './__fixtures__/fixtures'
import { compile } from './compile'
import { validate, type ValidatedRequest } from './validate'

function v(req: unknown): ValidatedRequest {
  const r = validate(req, catalogue)
  if ('status' in r) throw new Error(`${r.code}: ${r.message}`)
  return r
}

const PLANT = "'; DROP TABLE x; --"

describe('compile', () => {
  it('binds every value and takes identifiers from the catalogue', () => {
    const c = compile(
      v({
        view: 'qv_laps',
        filters: [
          { col: 'season', op: 'eq', val: 2024 },
          { col: 'driver_id', op: 'in', val: ['LEC', PLANT] },
          { col: 'lap_number', op: 'between', val: [10, 20] },
        ],
        group_by: ['driver_id'],
        aggregate: { fn: 'median', col: 'lap_time_s' },
        order: 'value_asc',
        limit: 5,
      }),
    )
    expect(c.sql).toBe(
      'SELECT "driver_id", MEDIAN("lap_time_s") AS "value", COUNT("lap_time_s") AS "n", COUNT(*) OVER () AS "total_groups" ' +
        'FROM "qv_laps_2024" WHERE "season" = ? AND "driver_id" IN (?, ?) AND "lap_number" BETWEEN ? AND ? AND "is_major_outlier_lap" = ? ' +
        'GROUP BY "driver_id" ORDER BY "value" ASC NULLS LAST, "driver_id" ASC NULLS LAST LIMIT 5',
    )
    expect(c.params).toEqual([2024, 'LEC', PLANT, 10, 20, false])
    expect(c.sql).not.toContain('DROP')
    expect(c.aliases).toEqual([{ alias: 'qv_laps_2024', season: 2024, race_id: null }])
  })

  it('unions at most two season aliases', () => {
    const c = compile(v({ view: 'qv_laps', filters: [{ col: 'season', op: 'in', val: [2024, 2023] }], aggregate: { fn: 'count', col: 'laps' } }))
    expect(c.seasons).toEqual([2023, 2024])
    expect(c.sql).toContain('FROM (SELECT * FROM "qv_laps_2023" UNION ALL SELECT * FROM "qv_laps_2024") AS src')
    expect(c.sql).toContain('COUNT(*) AS "value", COUNT(*) AS "n"')
  })

  it('single-file views use the view name; race views hash the race id into the alias', () => {
    expect(compile(v({ view: 'qv_stints', filters: [{ col: 'season', op: 'eq', val: 2024 }], aggregate: { fn: 'count', col: 'stints' } })).aliases[0].alias).toBe('qv_stints')
    const c = compile(
      v({
        view: 'qv_teammate_corners',
        filters: [{ col: 'season', op: 'eq', val: 2024 }, { col: 'race_id', op: 'eq', val: '2024_8' }],
        group_by: ['corner_name'],
        aggregate: { fn: 'avg', col: 'v_min_delta_kph' },
      }),
    )
    expect(c.aliases[0].alias).toMatch(/^qv_teammate_corners_2024_r[0-9a-f]{12}$/)
    expect(c.sql).not.toContain('2024_8')
    expect(c.params).toContain('2024_8')
  })

  it('group_asc orders by the group columns first', () => {
    const c = compile(v({ view: 'qv_stints', filters: [{ col: 'season', op: 'eq', val: 2024 }], group_by: ['compound'], aggregate: { fn: 'avg', col: 'stint_length_laps' }, order: 'group_asc' }))
    expect(c.sql).toContain('ORDER BY "compound" ASC NULLS LAST, "value" DESC NULLS LAST')
  })

  it('refuses an object that did not come from validate()', () => {
    const fake = { ...v({ view: 'qv_stints', filters: [{ col: 'season', op: 'eq', val: 2024 }], aggregate: { fn: 'count', col: 'stints' } }) }
    expect(() => compile(fake as ValidatedRequest)).toThrow(/validate/)
  })
})
