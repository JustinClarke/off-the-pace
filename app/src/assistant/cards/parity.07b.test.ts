// AX-07b acceptance: the three live minimum-set kinds match an independent SQL oracle over the same
// parquet on 3 parameter sets (seasons 2018, 2022, 2025), at display precision; every card validates,
// is class T, and carries n; the two held kinds are held with their reason.
// Configure with AX04_DATA_DIR=<scratch export dir with _manifest.json>. Skips when unset.
// @vitest-environment node
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
// @ts-expect-error plain .mjs script without a declaration file
import { createHeadless } from '../../../scripts/build-cards.mjs'

const DATA = process.env.AX04_DATA_DIR ?? ''
const enabled = DATA !== '' && existsSync(join(DATA, '_manifest.json'))
if (!enabled) console.warn('[AX-07b parity] skipped: set AX04_DATA_DIR to a scratch export')

const SEASONS = [2018, 2022, 2025]
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any

describe.skipIf(!enabled)('AX-07b parity on 3 seasons', () => {
  let h: Any
  let report: Any
  let oracle: Any
  const card = (id: string) => report.cards.find((c: Any) => c.id === id)

  beforeAll(async () => {
    h = await createHeadless({ dataDir: DATA })
    const manifest = JSON.parse(readFileSync(join(DATA, '_manifest.json'), 'utf8'))
    const local = (name: string, season?: number) => {
      const t = manifest.tables.find((x: Any) => x.name === name)
      const p = season !== undefined ? t.files?.find?.((f: Any) => f.season === season)?.path ?? t.partitions?.[season] : t.path
      return join(DATA, String(p).replace(/^\/data\//, ''))
    }
    oracle = await h.adapter.createWasmEngine()
    for (const s of SEASONS) oracle.registerFile(`corner${s}.parquet`, join(DATA, 'marts/mart_corner_skill_driver', `${s}.parquet`))
    oracle.registerFile('season.parquet', local('mart_driver_season_summary'))
    oracle.registerFile('rct.parquet', local('race_caution_timeline'))
    const kinds = ['season.teammate_gap', 'corner_phase.season', 'race_control.pooled_rate']
    report = await h.build.buildCards({
      kinds,
      params: { 'season.teammate_gap': SEASONS.map((season) => ({ season })), 'corner_phase.season': SEASONS.map((season) => ({ season })), 'race_control.pooled_rate': [{}] },
    })
  }, 180_000)

  afterAll(async () => {
    oracle?.close()
    await h?.close()
  })

  it('every card validates, is class T, has n, and the interval kind is the registry one', async () => {
    const { validateCard } = await h.load('/src/assistant/cards/validate.ts')
    const { registry } = await h.load('/src/assistant/cards/registry.ts')
    const kindOf = Object.fromEntries(registry.map((s: Any) => [s.kind, s]))
    expect(report.cards.length).toBeGreaterThan(0)
    for (const c of report.cards) {
      expect(validateCard(c, { expectedIntervalKind: kindOf[c.kind].intervalKind }).errors).toEqual([])
      expect(kindOf[c.kind].class).toBe('T')
      expect(typeof c.n.count).toBe('number')
    }
  })

  it.each(SEASONS)('season.teammate_gap %i = mart_driver_season_summary (3 dp), CI and n_races', (season) => {
    const rows = oracle.run(`SELECT * FROM read_parquet('season.parquet') WHERE race_year = ?`, [season])
    expect(rows.length).toBeGreaterThan(5)
    for (const o of rows) {
      const c = card(`season.teammate_gap:${season}:${o.driver_id}`)
      expect(c, o.driver_id).toBeTruthy()
      expect(c.value.toFixed(3)).toBe((o.teammate_gap_s as number).toFixed(3))
      expect(c.interval.low.toFixed(3)).toBe((o.ci_low as number).toFixed(3))
      expect(c.interval.high.toFixed(3)).toBe((o.ci_high as number).toFixed(3))
      expect(c.interval.kind).toBe('ci_normal_95')
      expect(c.n).toEqual({ count: Number(o.n_races), unit: 'races' })
      expect(c.policy_fields.rank_separated_from_next).toBe(o.rank_separated_from_next ?? null)
      expect(c.caveats).toContain('AIR_STATE_FILTER')
    }
  })

  it.each(SEASONS)('corner_phase.season %i = mart (skill, SE, cells)', (season) => {
    const rows = oracle.run(`SELECT * FROM read_parquet('corner${season}.parquet')`)
    expect(rows.length).toBeGreaterThan(5)
    for (const o of rows) {
      for (const [phase, v, se, n] of [['braking', 'braking_skill_s', 'braking_skill_se_s', 'braking_cells_n'], ['mid_corner', 'mid_corner_skill_s', 'mid_corner_skill_se_s', 'mid_cells_n'], ['exit', 'exit_skill_s', 'exit_skill_se_s', 'exit_cells_n']] as const) {
        const c = card(`corner_phase.season:${season}:${o.driver_id}:${phase}`)
        expect(c, `${o.driver_id} ${phase}`).toBeTruthy()
        if (o[v] === null || o[se] === null) {
          expect(c.value).toBeNull()
          expect(c.unavailable_reason).toBeTruthy()
          continue
        }
        expect(c.value).toBeCloseTo(o[v] as number, 9)
        expect(c.interval.kind).toBe('se_1')
        expect((c.interval.high - c.interval.low) / 2).toBeCloseTo(o[se] as number, 9)
        expect(c.n.count).toBe(Number(o[n]))
      }
    }
  })

  it('race_control.pooled_rate interval = the page wilson_95 interval (AX-07c), via the page query and transform', async () => {
    const uq = await h.load('/src/data/hooks/useQuery.ts')
    const { summarisePooled } = await h.load('/src/features/race-control/transform.ts')
    const rows = await uq.getRegisteredQuery('race-control.pooled-rates')()
    const page = summarisePooled(rows)
    for (const [variant, p] of [['any_caution', page.anyCaution], ['safety_car', page.safetyCar], ['vsc', page.vsc], ['red_flag', page.redFlag]] as const) {
      const c = card(`race_control.pooled_rate:all:${variant}`)
      expect(c.interval).toMatchObject({ kind: 'wilson_95', level: 0.95 })
      expect(c.interval.low).toBe(p.lo)
      expect(c.interval.high).toBe(p.hi)
      expect(c.value).toBe(p.rate)
    }
  })

  it('race_control.pooled_rate = pooled counts per season and in total; no per-circuit card', () => {
    const rows = oracle.run(`
      WITH pr AS (SELECT race_year, race_id, MAX(CASE WHEN caution_status <> 'green' THEN 1 ELSE 0 END) AS a,
                         MAX(CASE WHEN caution_status = 'safety_car' THEN 1 ELSE 0 END) AS sc
                    FROM read_parquet('rct.parquet') GROUP BY race_year, race_id)
      SELECT race_year, COUNT(*) AS races, SUM(a) AS any_c, SUM(sc) AS sc FROM pr GROUP BY race_year`)
    expect(rows.length).toBeGreaterThanOrEqual(8)
    for (const o of rows) {
      const any = card(`race_control.pooled_rate:${o.race_year}:any_caution`)
      expect(any.n).toEqual({ count: Number(o.races), unit: 'races' })
      expect(any.value).toBeCloseTo(Number(o.any_c) / Number(o.races), 9)
      expect(any.scope.season).toBe(Number(o.race_year))
    }
    const total = card('race_control.pooled_rate:all:any_caution')
    expect(total.n.count).toBe(rows.reduce((a: number, o: Any) => a + Number(o.races), 0))
    for (const c of report.cards.filter((x: Any) => x.kind === 'race_control.pooled_rate')) {
      expect(c.scope.circuit_id).toBeNull()
      expect(c.interval.kind).toBe('wilson_95')
      expect(c.interval.low).toBeLessThanOrEqual(c.value)
      expect(c.interval.high).toBeGreaterThanOrEqual(c.value)
    }
  })
})
