// AX-06: 500 seeded random requests (mixing valid and broken parts) through validate + compile +
// runQuery on a spy engine: every outcome is a structured error, no_data or a valid result shape,
// nothing throws, and no request-supplied string reaches the SQL text.
import { describe, it, expect } from 'vitest'
import { catalogue, makeManifest, rng, spyEngine } from './__fixtures__/fixtures'
import { compile } from './compile'
import { runQuery } from './run'
import { validate } from './validate'

const PLANTS = ["'; DROP TABLE x; --", 'x" OR 1=1 --', "read_parquet('https://evil/x.parquet')", '__proto__', 'constructor', ''] as const

function gen(r: () => number): { req: unknown; strings: string[] } {
  const pick = <T,>(xs: readonly T[]): T => xs[Math.floor(r() * xs.length)]
  const strings: string[] = []
  const str = () => {
    const s = r() < 0.5 ? pick(PLANTS) : `${pick(['LEC', 'HAM', 'VER', '2024_8', 'SOFT', 'Turn_1'])}${r() < 0.3 ? pick(PLANTS) : ''}`
    strings.push(s)
    return s
  }
  if (r() < 0.3) {
    // A valid request built from the catalogue, with planted strings in bound values.
    const vw = pick(catalogue.views.filter((x) => !x.sub_partition_key))
    const filters: unknown[] = vw.required_filters.includes('season') ? [{ col: 'season', op: 'eq', val: pick(catalogue.seasons) }] : []
    const strDim = vw.columns.find((c) => c.role === 'dimension' && c.type === 'string' && c.ops.includes('in'))
    if (strDim) filters.push({ col: strDim.name, op: 'in', val: [str(), str()] })
    const measure = vw.columns.find((c) => c.role === 'measure')
    const groupable = vw.columns.filter((c) => c.group_by && !vw.group_by_requires[c.name])
    return {
      req: {
        view: vw.name,
        filters,
        group_by: groupable.length && r() < 0.6 ? [pick(groupable).name] : [],
        aggregate: measure && r() < 0.6 ? { fn: measure.aggregates[0], col: measure.name } : { fn: 'count', col: vw.count_name },
        order: pick(['value_asc', 'value_desc', 'group_asc']),
        limit: 1 + Math.floor(r() * 25),
      },
      strings,
    }
  }
  const view = r() < 0.85 ? pick(catalogue.views) : null
  const viewName = view ? view.name : r() < 0.5 ? str() : pick([42, null, {}, ['qv_laps']])
  const cols = view ? view.columns.map((c) => c.name) : ['season']
  const anyVal = (): unknown =>
    pick([
      () => pick(catalogue.seasons),
      () => str(),
      () => Math.floor(r() * 80),
      () => r() < 0.5,
      () => pick([NaN, Infinity, -0, -Infinity, 2.5]),
      () => Array.from({ length: Math.floor(r() * 25) }, () => (r() < 0.5 ? str() : Math.floor(r() * 30))),
      () => [pick(catalogue.seasons), pick(catalogue.seasons)],
      () => ({ $gt: 1 }),
      () => null,
    ])()
  const nFilters = Math.floor(r() * 8)
  const filters: unknown[] = [{ col: 'season', op: pick(['eq', 'in', 'between', 'gt']), val: anyVal() }]
  for (let i = 0; i < nFilters; i++) {
    filters.push(
      r() < 0.1
        ? JSON.parse('{"__proto__":{"polluted":true},"col":"season","op":"eq","val":2024}')
        : { col: r() < 0.8 ? pick(cols) : str(), op: pick(['eq', 'ne', 'lt', 'lte', 'gt', 'gte', 'in', 'between', 'like', 'or']), val: anyVal() },
    )
  }
  const req: Record<string, unknown> = {
    view: viewName,
    filters: r() < 0.9 ? filters : str(),
    group_by: r() < 0.7 ? Array.from({ length: Math.floor(r() * 4) }, () => (r() < 0.8 ? pick(cols) : str())) : str(),
    aggregate:
      r() < 0.9
        ? { fn: pick(['count', 'avg', 'median', 'min', 'max', 'sum', 'stddev', str()]), col: view && r() < 0.5 ? (r() < 0.3 ? view.count_name : pick(cols)) : str() }
        : str(),
    order: r() < 0.8 ? pick(['value_asc', 'value_desc', 'group_asc']) : str(),
    limit: pick([1, 5, 10, 25, 26, 0, -3, 2.5, '10', Number.MAX_SAFE_INTEGER]),
  }
  if (r() < 0.05) req['__proto__'] = { admin: true }
  if (r() < 0.05) req.sql = 'SELECT 1'
  if (r() < 0.05) return { req: JSON.parse(JSON.stringify(req).replace('"view"', '"__proto__":{"x":1},"view"')), strings }
  return { req, strings }
}

describe('fuzz (500 seeded cases)', () => {
  it('never throws; every outcome is structured; no request string reaches the SQL', async () => {
    const r = rng(20261108)
    const manifest = makeManifest()
    const counts = { error: 0, ok: 0, no_data: 0 }
    for (let i = 0; i < 500; i++) {
      const { req, strings } = gen(r)
      const v = validate(req, catalogue)
      if (!('status' in v)) {
        const c = compile(v)
        for (const s of strings) {
          if (s.length < 3 || ['LEC', 'HAM', 'VER', 'SOFT'].includes(s)) continue
          // Request strings may appear only in params, never in the SQL text.
          if (c.sql.includes(s)) {
            const isIdentifier = catalogue.views.some((vw) => vw.name === s || vw.count_name === s || vw.columns.some((col) => col.name === s))
            expect(isIdentifier, `case ${i}: request string ${JSON.stringify(s)} in SQL ${c.sql}`).toBe(true)
          }
        }
        expect(c.sql).not.toMatch(/DROP|read_parquet|https?:|OR 1=1/i)
      }
      const engine = spyEngine([{ value: 81.23456, n: 12, total_groups: 1 }])
      const out = await runQuery(req, { catalogue, manifest, engine })
      expect(['error', 'ok', 'no_data']).toContain(out.status)
      counts[out.status]++
      if (out.status === 'error') {
        expect(typeof out.code).toBe('string')
        expect(typeof out.message).toBe('string')
      }
      if (out.status === 'ok') {
        expect(out.label).toBe('computed_not_card')
        expect(out.rows_shown).toBeLessThanOrEqual(25)
        for (const row of out.rows) expect(typeof row.n).toBe('number')
      }
    }
    expect(({} as Record<string, unknown>).polluted).toBeUndefined()
    expect(({} as Record<string, unknown>).admin).toBeUndefined()
    // The generator must exercise both sides.
    expect(counts.ok).toBeGreaterThan(5)
    expect(counts.error).toBeGreaterThan(300)
  })
})
