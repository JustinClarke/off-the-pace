// AX-07 acceptance: the driver-by-race kinds match an independent SQL oracle over the same parquet
// for 20 (driver, race) pairs across 8 seasons, at display precision (gap and CI 3 dp; positions,
// stops, laps integers). The race kinds (coverage, cautions) are checked on the same races.
//
// Pairs: the four demo races first (2024_1 VER ok, 2020_14 HAM 1 paired lap, 2018_1 HAM no
// telemetry, 2021_16 HAM unrated wet race), then 16 drawn from stg_results with Python
// random.Random(20261108).sample(rows, 16), rows ordered by (race_id, driver_id), plus one thin
// case (2019_1 NOR) for the thin-vs-clean interval check. Written here so the test is fixed.
//
// Configure with AX04_DATA_DIR=<scratch export dir with _manifest.json>. Skips when unset.
// @vitest-environment node
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
// @ts-expect-error plain .mjs script without a declaration file
import { createHeadless } from '../../../scripts/build-cards.mjs'

const DATA = process.env.AX04_DATA_DIR ?? ''
const enabled = DATA !== '' && existsSync(join(DATA, '_manifest.json'))
if (!enabled) console.warn('[AX-07 parity.20pairs] skipped: set AX04_DATA_DIR to a scratch export (dir with _manifest.json)')

export const PAIRS = [
  { season: 2024, race_id: '2024_1', driver_id: 'VER' },
  { season: 2020, race_id: '2020_14', driver_id: 'HAM' },
  { season: 2018, race_id: '2018_1', driver_id: 'HAM' },
  { season: 2021, race_id: '2021_16', driver_id: 'HAM' },
  { season: 2018, race_id: '2018_1', driver_id: 'ERI' },
  { season: 2018, race_id: '2018_12', driver_id: 'ALO' },
  { season: 2018, race_id: '2018_5', driver_id: 'RAI' },
  { season: 2019, race_id: '2019_10', driver_id: 'KUB' },
  { season: 2020, race_id: '2020_12', driver_id: 'RAI' },
  { season: 2021, race_id: '2021_11', driver_id: 'BOT' },
  { season: 2021, race_id: '2021_17', driver_id: 'ALO' },
  { season: 2021, race_id: '2021_7', driver_id: 'VET' },
  { season: 2022, race_id: '2022_14', driver_id: 'ZHO' },
  { season: 2022, race_id: '2022_15', driver_id: 'ALO' },
  { season: 2022, race_id: '2022_2', driver_id: 'HUL' },
  { season: 2023, race_id: '2023_18', driver_id: 'MAG' },
  { season: 2023, race_id: '2023_19', driver_id: 'PER' },
  { season: 2024, race_id: '2024_20', driver_id: 'GAS' },
  { season: 2024, race_id: '2024_4', driver_id: 'MAG' },
  { season: 2025, race_id: '2025_16', driver_id: 'BEA' },
]
const THIN = { season: 2019, race_id: '2019_1', driver_id: 'NOR' }

type Row = Record<string, unknown>
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any
const f3 = (v: unknown) => (v as number).toFixed(3)

describe.skipIf(!enabled)('AX-07 parity, 20 driver-race pairs', () => {
  let h: Any
  let report: Any
  let oracle: { registerFile(n: string, p: string): void; run(sql: string, params?: unknown[]): Row[]; close(): void }
  const card = (id: string) => report.cards.find((c: Any) => c.id === id)

  beforeAll(async () => {
    h = await createHeadless({ dataDir: DATA })
    const manifest = JSON.parse(readFileSync(join(DATA, '_manifest.json'), 'utf8'))
    const local = (name: string) => join(DATA, manifest.tables.find((t: Any) => t.name === name).path.replace(/^\/data\//, ''))
    oracle = await h.adapter.createWasmEngine()
    oracle.registerFile('res.parquet', local('stg_results'))
    oracle.registerFile('rds.parquet', local('mart_race_driver_summary'))
    oracle.registerFile('cov.parquet', local('mart_race_coverage'))
    oracle.registerFile('pv.parquet', local('int_pit_strategy_value'))
    oracle.registerFile('rct.parquet', local('race_caution_timeline'))
    const races = [...new Map([...PAIRS, THIN].map((p) => [p.race_id, { season: p.season, race_id: p.race_id }])).values()]
    const kinds = ['race.result', 'race.teammate_gap', 'race.coverage', 'race.cautions', 'driver_race.pit_stops']
    // The registry's own classesLive (['T']): these are the cards that would be published.
    report = await h.build.buildCards({ kinds, params: Object.fromEntries(kinds.map((k) => [k, races])) })
  }, 180_000)

  afterAll(async () => {
    oracle?.close()
    await h?.close()
  })

  it('pairs span at least 3 seasons and every emitted card validates', async () => {
    expect(new Set(PAIRS.map((p) => p.season)).size).toBeGreaterThanOrEqual(3)
    expect(PAIRS).toHaveLength(20)
    const { validateCard } = await h.load('/src/assistant/cards/validate.ts')
    const { registry } = await h.load('/src/assistant/cards/registry.ts')
    const kindOf = Object.fromEntries(registry.map((s: Any) => [s.kind, s]))
    for (const c of report.cards) {
      expect(validateCard(c, { expectedIntervalKind: kindOf[c.kind].intervalKind }).errors).toEqual([])
      expect(kindOf[c.kind].class).toBe('T')
      expect(c.status).toBe('active')
    }
  })

  it.each(PAIRS)('race.result $race_id $driver_id = stg_results', ({ race_id, driver_id }) => {
    const [o] = oracle.run(`SELECT * FROM read_parquet('res.parquet') WHERE race_id = ? AND driver_id = ?`, [race_id, driver_id])
    const c = card(`race.result:${race_id}:${driver_id}`)
    expect(c).toBeTruthy()
    expect(c.value).toBe(o.is_classified && o.finish_position !== null ? Number(o.finish_position) : o.status)
    expect(c.n).toEqual({ count: 1, unit: 'races' })
  })

  it.each(PAIRS)('race.teammate_gap $race_id $driver_id = mart (3 dp); suppressed never a value', ({ race_id, driver_id }) => {
    const [o] = oracle.run(
      `SELECT teammate_id, teammate_gap_s, ci_low, ci_high, rating_s, CAST(paired_lap_count AS INTEGER) AS k, rating_trust_label AS lbl
       FROM read_parquet('rds.parquet') WHERE race_id = ? AND driver_id = ?`,
      [race_id, driver_id],
    )
    const c = card(`race.teammate_gap:${race_id}:${driver_id}`)
    expect(c).toBeTruthy()
    if (!o) {
      const [cov] = oracle.run(`SELECT coverage_reason FROM read_parquet('cov.parquet') WHERE race_id = ?`, [race_id])
      expect(c.label).toBe('unavailable')
      expect(c.value).toBeNull()
      expect(c.unavailable_reason).toMatch(cov.coverage_reason === 'OK' ? /no paired clean laps/ : new RegExp(String(cov.coverage_reason)))
      return
    }
    const k = Number(o.k)
    if (k < 6 || o.lbl === 'suppressed') {
      expect(c.label).toBe('unavailable')
      expect(c.value).toBeNull()
      expect(c.interval).toBeNull()
      expect(c.n.count).toBe(0)
      expect(c.unavailable_reason).toMatch(new RegExp(`^rated on ${k} paired laps?`))
      expect(JSON.stringify(c)).not.toContain(f3(Math.abs(o.rating_s as number)))
      return
    }
    expect(f3(c.value)).toBe(f3(o.teammate_gap_s))
    expect(f3(c.interval.low)).toBe(f3(o.ci_low))
    expect(f3(c.interval.high)).toBe(f3(o.ci_high))
    expect(c.interval.kind).toBe('ci_order_stat_median')
    expect(c.n).toEqual({ count: k, unit: 'laps' })
    expect(c.policy_fields.rating_trust_label).toBe(o.lbl)
    expect(c.caveats).toContain('AIR_STATE_FILTER')
  })

  it.each(PAIRS)('driver_race.pit_stops $race_id $driver_id = int_pit_strategy_value', ({ race_id, driver_id }) => {
    const [o] = oracle.run(
      `SELECT CAST(COUNT(actual_pit_lap) AS INTEGER) AS stops, CAST(SUM(stint_length_laps) AS INTEGER) AS laps
       FROM read_parquet('pv.parquet') WHERE race_id = ? AND driver_id = ?`,
      [race_id, driver_id],
    )
    const c = card(`driver_race.pit_stops:${race_id}:${driver_id}`)
    if (o.laps === null) {
      expect(c).toBeUndefined()
      return
    }
    expect(c.value).toBe(Number(o.stops))
    expect(c.n).toEqual({ count: Number(o.laps), unit: 'laps' })
  })

  it.each([...new Set(PAIRS.map((p) => p.race_id))])('race.coverage and race.cautions %s = oracle', (race_id) => {
    const [cov] = oracle.run(`SELECT coverage_reason, CAST(n_lap_rows AS INTEGER) AS n FROM read_parquet('cov.parquet') WHERE race_id = ?`, [race_id])
    expect(card(`race.coverage:${race_id}`).value).toBe(cov.coverage_reason)
    expect(card(`race.coverage:${race_id}`).n.count).toBe(Number(cov.n))
    const [ct] = oracle.run(
      `SELECT CAST(COUNT(*) FILTER (WHERE caution_status <> 'green') AS INTEGER) AS caution, CAST(COUNT(*) AS INTEGER) AS laps
       FROM read_parquet('rct.parquet') WHERE race_id = ?`,
      [race_id],
    )
    expect(card(`race.cautions:${race_id}`).value).toBe(Number(ct.caution))
    expect(card(`race.cautions:${race_id}`).n.count).toBe(Number(ct.laps))
  })

  it('a thin and a clean case differ visibly in n and interval width', () => {
    const ok = card('race.teammate_gap:2024_1:VER')
    const thin = card(`race.teammate_gap:${THIN.race_id}:${THIN.driver_id}`)
    expect(ok.policy_fields.rating_trust_label).toBe('ok')
    expect(thin.policy_fields.rating_trust_label).toBe('thin')
    expect(thin.n.count).toBeLessThan(ok.n.count)
    expect(thin.interval.high - thin.interval.low).toBeGreaterThan(ok.interval.high - ok.interval.low)
    expect(thin.display).toMatch(/thin/)
  })

  it('demo races say what the AX-07 brief expects', () => {
    expect(card('race.teammate_gap:2024_1:VER').display).toMatch(/^-0\.622 s\/lap vs PER/)
    expect(card('race.teammate_gap:2020_14:HAM').unavailable_reason).toMatch(/^rated on 1 paired lap \(/)
    expect(card('race.coverage:2018_1').value).toBe('NO_TELEMETRY')
    expect(card('race.coverage:2021_16').value).toBe('ALL_WET_NO_DRY_PAIRS')
    expect(card('race.teammate_gap:2021_16:HAM').unavailable_reason).toMatch(/ALL_WET_NO_DRY_PAIRS/)
    expect(card('race.result:2021_16:HAM').value).toBe(5)
  })
})
