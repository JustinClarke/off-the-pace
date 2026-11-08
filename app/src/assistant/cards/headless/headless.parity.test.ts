// AX-04 acceptance: the three features run headless on a scratch export, and for 3 fixed
// parameter sets each the card value (or the transform output the card is built from) equals
//   (a) the page's own call chain (registered query -> transform), run here step by step, and
//   (b) an independent SQL oracle over the same parquet, on a separate engine connection,
// at the page's display precision:
//   era_rating.season      value, ci low/high: 3 decimals (tooltip, LineWithCIRibbon.tsx:70)
//   race_lost.component    component totals:   4 decimals (tooltip, ui/charts/Waterfall.tsx:48), over
//                          AP-06's closed lap set
//   pit_strategy           laps, stint counts: integers (Gantt)
// Configure with AX04_DATA_DIR=<dir with _manifest.json> (a scratch export from
// scripts/export_app_data.py --db <scratch>/dev.duckdb --out <dir>). Skips when unset.
// With AX04_EXPECT_OUT=<file> it also writes the headless values for e2e/card-render.e2e.ts,
// which reads the same numbers off the rendered pages (their CSV export) in a real browser.
// @vitest-environment node
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
// @ts-expect-error plain .mjs script without a declaration file
import { createHeadless } from '../../../../scripts/build-cards.mjs'

const DATA = process.env.AX04_DATA_DIR ?? ''
const enabled = DATA !== '' && existsSync(join(DATA, '_manifest.json'))
if (!enabled) console.warn('[AX-04 parity] skipped: set AX04_DATA_DIR to a scratch export (dir with _manifest.json)')

const ERA = [
  { driver_id: 'LEC', season: 2024 },
  { driver_id: 'HAM', season: 2019 },
  { driver_id: 'VER', season: 2021 },
]
const RACE_LOST = [
  { season: 2024, race_id: '2024_8', driver_id: 'LEC' },
  { season: 2019, race_id: '2019_1', driver_id: 'HAM' },
  { season: 2022, race_id: '2022_5', driver_id: 'VER' },
]
const PIT = [
  { season: 2024, race_id: '2024_8' },
  { season: 2019, race_id: '2019_1' },
  { season: 2022, race_id: '2022_5' },
]

type Row = Record<string, unknown>
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any

const fixed = (v: unknown, d: number) => (v as number).toFixed(d)

describe.skipIf(!enabled)('AX-04 headless parity', () => {
  let h: Any
  let oracle: { registerFile(n: string, p: string): void; run(sql: string, params?: unknown[]): Row[]; close(): void }
  let manifest: { tables: { name: string; path: string; partitions?: { value: number; path: string }[] }[] }
  const local = (name: string, part?: number) => {
    const t = manifest.tables.find((x) => x.name === name)!
    const p = part === undefined ? t.path : t.partitions!.find((x) => x.value === part)!.path
    return join(DATA, p.replace(/^\/data\//, ''))
  }
  let report: Any
  let getQ: (name: string) => (p?: unknown) => Promise<Any>

  beforeAll(async () => {
    h = await createHeadless({ dataDir: DATA })
    manifest = JSON.parse(readFileSync(join(DATA, '_manifest.json'), 'utf8'))
    oracle = await h.adapter.createWasmEngine()
    oracle.registerFile('era.parquet', local('int_era_normalized_driver_rating'))
    oracle.registerFile('pv.parquet', local('int_pit_strategy_value'))
    oracle.registerFile('sf.parquet', local('fct_stint_features'))
    for (const s of [2019, 2022, 2024]) oracle.registerFile(`laps_${s}.parquet`, local('fct_lap_residuals', s))
    // buildCards with every class live (test only), so the era card carries its value.
    report = await h.build.buildCards({
      params: { 'era_rating.season': ERA, 'race_lost.component': RACE_LOST, 'pit_strategy.optimal_lap': PIT },
      classesLive: ['T', 'T-F', 'DA', 'TRAFFIC', 'ML'],
    })
    const uq = await h.load('/src/data/hooks/useQuery.ts')
    getQ = (name) => {
      const fn = uq.getRegisteredQuery(name)
      if (!fn) throw new Error(`not registered: ${name}`)
      return fn
    }
  }, 120_000)

  it('writes the rendered-page expectations when AX04_EXPECT_OUT is set', async () => {
    const out = process.env.AX04_EXPECT_OUT
    if (!out) return
    const era = report.cards
      .filter((c: Any) => c.kind === 'era_rating.season')
      .map((c: Any) => ({ driver_id: c.scope.driver_id, season: c.scope.season, value: c.value, low: c.interval.low, high: c.interval.high }))
    const allEra = await getQ('era-ratings-timeline.all')()
    const { raceLostComponent } = await h.load('/src/features/race-lost/cards.ts')
    const { toCsvRows } = await h.load('/src/features/race-lost/transform.ts')
    const pitT = await h.load('/src/features/pit-strategy/transform.ts')
    const q = h.build.registryQueryRunner()
    const rl = RACE_LOST[0]
    const rlComputed = await raceLostComponent.compute(rl, q)
    const pit = PIT[0]
    const rows = await getQ('pit-strategy.gantt')({ race_id: pit.race_id, season: pit.season })
    const [summary] = await getQ('pit-strategy.race-summary')({ race_id: pit.race_id, season: pit.season })
    writeFileSync(out, JSON.stringify({
      era,
      eraAll: allEra.map((r: Any) => ({ driver_id: r.driver_id, season: r.season, value: r.era_adjusted_rating, low: r.era_adjusted_rating_ci_low_s, high: r.era_adjusted_rating_ci_high_s })),
      raceLost: { ...rl, csv: toCsvRows(rl.driver_id, rlComputed.row) },
      pit: { ...pit, csv: pitT.toCsvRows(pitT.transform(rows, summary.total_laps)) },
    }, null, 1))
  })

  afterAll(async () => {
    oracle?.close()
    await h?.close()
  })

  it('every emitted card validates and every refused row has a reason', async () => {
    const { validateCard } = await h.load('/src/assistant/cards/validate.ts')
    const { registry } = await h.load('/src/assistant/cards/registry.ts')
    const kindOf = Object.fromEntries(registry.map((s: Any) => [s.kind, s]))
    for (const c of report.cards) expect(validateCard(c, { expectedIntervalKind: kindOf[c.kind].intervalKind }).errors).toEqual([])
    for (const u of report.ungrounded) expect(u.reason.length).toBeGreaterThan(10)
    expect(report.counts['era_rating.season']).toEqual({ params: 3, active: 3, held: 0, refused: 0 })
    expect(report.counts['race_lost.component']).toMatchObject({ params: 3, active: 0, refused: 18 })
    expect(report.counts['pit_strategy.optimal_lap'].active).toBe(0)
  })

  it.each(ERA)('era rating $driver_id $season: card = page chain = SQL oracle (3 dp)', async ({ driver_id, season }) => {
    const card = report.cards.find((c: Any) => c.id === `era_rating.season:${season}:${driver_id}`)
    expect(card).toBeTruthy()
    const { transform } = await h.load('/src/features/era-ratings-timeline/transform.ts')
    const rows = await getQ('era-ratings-timeline.all')()
    const pt = transform(rows).series.find((s: Any) => s.driver_id === driver_id).points.find((p: Any) => p.x === season)
    const [o] = oracle.run(
      `SELECT era_adjusted_rating AS y, era_adjusted_rating_ci_low_s AS lo, era_adjusted_rating_ci_high_s AS hi, CAST(n_races AS INTEGER) AS n
       FROM read_parquet('era.parquet') WHERE driver_id = ? AND season = ?`,
      [driver_id, season],
    )
    for (const [cardV, pageV, sqlV] of [
      [card.value, pt.y, o.y],
      [card.interval.low, pt.lo, o.lo],
      [card.interval.high, pt.hi, o.hi],
    ]) {
      expect(fixed(cardV, 3)).toBe(fixed(pageV, 3))
      expect(fixed(cardV, 3)).toBe(fixed(sqlV, 3))
    }
    expect(card.n).toEqual({ count: Number(o.n), unit: 'races' })
    expect(card.interval.kind).toBe('ci_normal_95')
    expect(card.display).toBe(`${(o.y as number) > 0 ? '+' : ''}${fixed(o.y, 3)} s`)
  })

  it.each(RACE_LOST)('race-lost $race_id $driver_id: transform output = page chain = SQL oracle (4 dp); all refused', async ({ season, race_id, driver_id }) => {
    const { raceLostComponent } = await h.load('/src/features/race-lost/cards.ts')
    const { transform } = await h.load('/src/features/race-lost/transform.ts')
    const q = h.build.registryQueryRunner()
    const computed = await raceLostComponent.compute({ season, race_id, driver_id }, q)
    const [row] = await getQ('race-lost.driver')({ season, raceId: race_id, driverId: driver_id })
    const page = transform(row)
    // Oracle: raw lap rows, filtered and summed in JS (not the page's SQL). AP-06 (2026-11-08): the
    // five closure terms and the pace delta are summed over ONE closed lap set (pace delta, compound,
    // constructor, dirty air and skill all non-NULL); a term falls back to its own coverage only when
    // that set is empty. Track Noise is informational, over its own coverage, outside the closure.
    const laps = oracle.run(
      `SELECT fuel_component_s, compound_component_s, constructor_component_s, dirty_air_tax_s,
              driver_skill_residual_s, track_unexplained_s, pace_delta_s, is_major_outlier_lap
       FROM read_parquet('laps_${season}.parquet') WHERE race_year = ? AND race_id = ? AND driver_id = ?`,
      [season, race_id, driver_id],
    ).filter((l) => !l.is_major_outlier_lap && l.fuel_component_s !== null)
    const TERMS = ['fuel_component_s', 'compound_component_s', 'constructor_component_s', 'dirty_air_tax_s', 'driver_skill_residual_s']
    const closed = laps.filter((l) => l.pace_delta_s !== null && TERMS.every((k) => l[k] !== null))
    const sumOver = (set: Row[], k: string): number | null => {
      const vs = set.map((l) => l[k] as number | null).filter((v): v is number => v !== null)
      return vs.length ? vs.reduce((a, v) => a + v, 0) : null
    }
    const own = (k: string) => sumOver(k === 'dirty_air_tax_s' ? laps.filter((l) => l.pace_delta_s !== null) : laps, k)
    const want = [...TERMS.map((k) => (closed.length ? sumOver(closed, k) : own(k))), sumOver(laps, 'track_unexplained_s')]
    const fx = (v: unknown) => (v === null || v === undefined ? null : fixed(v, 4))
    expect(computed.result.bars.map((b: Any) => fx(b.value))).toEqual(page.bars.map((b: Any) => fx(b.value)))
    expect(computed.result.bars.map((b: Any) => fx(b.value))).toEqual(want.map(fx))
    expect(computed.result.nLaps).toBe(laps.length)
    expect(computed.result.nClosedLaps).toBe(closed.length)
    expect(fx(computed.result.totalPaceDelta)).toBe(closed.length ? fx(sumOver(closed, 'pace_delta_s')) : null)
    const refused = report.ungrounded.filter((u: Any) => u.kind === 'race_lost.component' && u.params.race_id === race_id && u.params.driver_id === driver_id)
    expect(refused).toHaveLength(6)
    expect(report.cards.some((c: Any) => c.id.startsWith(`race_lost.component:${race_id}:${driver_id}:`))).toBe(false)
  })

  it.each(PIT)('pit-strategy $race_id: stints = page chain = SQL oracle (integers); every card held', async ({ season, race_id }) => {
    const { transform } = await h.load('/src/features/pit-strategy/transform.ts')
    const rows = await getQ('pit-strategy.gantt')({ race_id, season })
    const [summary] = await getQ('pit-strategy.race-summary')({ race_id, season })
    const page = transform(rows, summary.total_laps)
    // AP-08 (2026-11-08): the page draws every fct_stint_features stint in stint-number order (suffix of
    // stint_id), not just the int_pit_strategy_value rows. Oracle: same rule written independently, with the
    // running sum of stint_length_laps as the end of a stint that has no stop, and LEAD(compound) for the next one.
    const sql = oracle.run(
      `WITH b AS (
         SELECT f.stint_id, f.driver_id, f.compound, f.stint_length_laps,
                CAST(regexp_extract(f.stint_id, '([0-9]+)$', 1) AS INTEGER) AS sn
         FROM read_parquet('sf.parquet') f WHERE f.race_id = ? AND regexp_matches(f.stint_id, '[0-9]+$')
       ), c AS (
         SELECT b.*, p.actual_pit_lap, p.optimal_pit_lap_in_stint,
                SUM(b.stint_length_laps) OVER (PARTITION BY b.driver_id ORDER BY b.sn) AS cum
         FROM b LEFT JOIN read_parquet('pv.parquet') p ON p.stint_id = b.stint_id
       )
       SELECT driver_id, sn, CAST(COALESCE(actual_pit_lap, cum) AS INTEGER) AS end_lap,
              CAST(optimal_pit_lap_in_stint AS INTEGER) AS opt,
              LEAD(compound) OVER (PARTITION BY driver_id ORDER BY sn) AS next_c
       FROM c ORDER BY driver_id, sn`,
      [race_id],
    )
    expect(page.stints.map((s: Any) => [s.driverId, s.stintNumber, s.endLap, s.optimalPitLapInStint])).toEqual(
      sql.map((r) => [r.driver_id, Number(r.sn), r.end_lap, r.opt]),
    )
    expect(sql.map((r) => [`${r.driver_id}:${r.sn}`, r.next_c ?? null])).toEqual(Object.entries(page.nextCompound))
    const cards = report.cards.filter((c: Any) => c.kind === 'pit_strategy.optimal_lap' && c.scope.race_id === race_id)
    expect(cards).toHaveLength(sql.length)
    expect(cards.map((c: Any) => c.id).sort()).toEqual(page.stints.map((s: Any) => `pit_strategy.optimal_lap:${race_id}:${s.driverId}:${s.stintNumber}`).sort())
    for (const c of cards) {
      expect(c.status).toBe('held')
      expect(c.value).toBeNull()
      expect(c.held_reason).toMatch(/^PIT_CALL_REPRODUCTION_RATE/)
      expect(c.caveats).toContain('PIT_CALL_REPRODUCTION_RATE')
    }
  })
})
