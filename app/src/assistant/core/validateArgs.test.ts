import { describe, it, expect } from 'vitest'
import { validateArgs } from './validateArgs'
import { tools } from './testKit'

const def = (n: string) => tools.find((t) => t.function.name === n)!

describe('validateArgs against the generated tool schemas', () => {
  it('accepts a good query_data request', () => {
    expect(validateArgs(def('query_data'), { view: 'qv_stints', aggregate: { fn: 'count', col: 'stint' }, limit: 5 })).toBeNull()
  })
  it('rejects an unknown view and lists the allowed ones', () => {
    const e = validateArgs(def('query_data'), { view: 'runLabQuery' })
    expect(e?.reason).toMatch(/view/)
    expect(e?.allowed).toContain('qv_laps')
  })
  it('rejects a limit above 25, too many scopes, a missing required key and a wrong type', () => {
    expect(validateArgs(def('query_data'), { view: 'qv_laps', limit: 26 })?.reason).toMatch(/at most 25/)
    expect(validateArgs(def('get_fact_cards'), { scopes: [{}, {}, {}, {}], bundle: 'teammate_race' })?.reason).toMatch(/more than 3/)
    expect(validateArgs(def('navigate'), {})?.reason).toMatch(/route is required/)
    expect(validateArgs(def('list_values'), { domain: 'driver', limit: 'ten' })?.reason).toMatch(/integer/)
  })
  it('refuses any top-level key no schema names', () => {
    const e = validateArgs(def('query_data'), { view: 'qv_laps', sql: 'select 1' })
    expect(e?.reason).toMatch(/not an argument/)
    expect(validateArgs(def('make_chart'), { result_id: 'x', code: '<script>' })?.reason).toMatch(/not an argument/)
  })
  it('rejects non-object and unparsable arguments', () => {
    expect(validateArgs(def('navigate'), 'route')?.reason).toMatch(/object/)
    expect(validateArgs(def('navigate'), { __unparsable: true })?.reason).toMatch(/JSON/)
  })
})
