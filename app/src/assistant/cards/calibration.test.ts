// AX-07c: policy_fields.calibration_flag on race-scoped cards, so CALIBRATION_FLAGGED_CIRCUIT can fire.
// Fixture cases always run; the data case runs when AX04_DATA_DIR points at an export from after TX-13
// (dim_circuits.calibration_flag present), e.g. scratchpad/laneR/out. Skips otherwise.
// @vitest-environment node
import { describe, it, expect, vi, beforeAll, afterAll } from 'vitest'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
// @ts-expect-error plain .mjs script without a declaration file
import { createHeadless } from '../../../scripts/build-cards.mjs'

vi.mock('../../data/manifest', async (orig) => ({
  ...(await orig<typeof import('../../data/manifest')>()),
  loadManifest: async () => ({ version: 'fx', generatedAt: '', tables: [], stats: { seasons_list: [] } }),
}))

const { buildCards } = await import('./build')
const { validateCard } = await import('./validate')
const { toCheckerCard } = await import('./project')
const { checkRule, policy } = await import('../honesty/checker')
const { raceResult } = await import('./sql/raceKinds')
import type { QueryRunner } from './kinds'
import type { Card } from './card.types'

const rule = policy.rules.find((r) => r.code === 'CALIBRATION_FLAGGED_CIRCUIT')!

const result = (race_id: string) => ({
  race_id, race_year: 2099, driver_id: 'AAA', constructor_id: 'team', finish_position: 1, classified_position: '1',
  grid_position: 1, points: 25, status: 'Finished', is_classified: true, is_dnf: false, dnf_cause: null,
})
const runner = (flags: unknown): QueryRunner => ({
  run: async <T,>(name: string, p?: unknown) => {
    if (name === 'cards.race-circuit-flags') {
      if (flags === 'throw') throw new Error('no dim_circuits.calibration_flag in this export')
      return flags as T
    }
    return [result((p as { race_id: string }).race_id)] as T
  },
})
const params = [{ season: 2099, race_id: '2099_1' }, { season: 2099, race_id: '2099_2' }, { season: 2099, race_id: '2099_3' }]
const flags = [
  { race_id: '2099_1', circuit_id: 'barcelona', calibration_flag: 'REVIEW_REQUIRED' },
  { race_id: '2099_2', circuit_id: 'monza', calibration_flag: 'SKIPPED' },
  { race_id: '2099_4', circuit_id: 'x', calibration_flag: 'INSUFFICIENT_DATA' },
]
const build = (f: unknown) =>
  buildCards({ specs: [raceResult], params: { 'race.result': params }, q: runner(f), index: { dataVersion: 'fx', seasons: [], races: [] } })
const fires = (c: Card) => checkRule(rule, { answer: 'x', cards: [toCheckerCard(c)] }).verdict !== 'not_fired'

describe('AX-07c calibration_flag on cards (fixtures)', () => {
  it('a REVIEW_REQUIRED circuit makes CALIBRATION_FLAGGED_CIRCUIT fire; a SKIPPED one does not', async () => {
    const r = await build(flags)
    const by = Object.fromEntries(r.cards.map((c) => [c.scope.race_id, c]))
    expect(by['2099_1'].policy_fields.calibration_flag).toBe('REVIEW_REQUIRED')
    expect(by['2099_2'].policy_fields.calibration_flag).toBe('SKIPPED')
    expect(fires(by['2099_1'])).toBe(true)
    expect(fires(by['2099_2'])).toBe(false)
    for (const c of r.cards) expect(validateCard(c, { expectedIntervalKind: 'none' }).errors).toEqual([])
  })
  it('a race with no circuit row carries no flag, and so does not fire', async () => {
    const r = await build(flags)
    const c = r.cards.find((x) => x.scope.race_id === '2099_3')!
    expect(c.policy_fields).not.toHaveProperty('calibration_flag')
    expect(fires(c)).toBe(false)
  })
  it('INSUFFICIENT_DATA fires too', async () => {
    const r = await buildCards({ specs: [raceResult], params: { 'race.result': [{ season: 2099, race_id: '2099_4' }] }, q: runner(flags), index: { dataVersion: 'fx', seasons: [], races: [] } })
    expect(fires(r.cards[0])).toBe(true)
  })
  it('an export without the column builds cards with no flag (no failure)', async () => {
    const r = await build('throw')
    expect(r.cards).toHaveLength(3)
    for (const c of r.cards) expect(c.policy_fields).not.toHaveProperty('calibration_flag')
  })
})

const DATA = process.env.AX04_DATA_DIR ?? ''
const enabled = DATA !== '' && existsSync(join(DATA, '_manifest.json')) && existsSync(join(DATA, 'dimensions/dim_circuits.parquet'))

describe.skipIf(!enabled)('AX-07c calibration_flag on the scratch export', () => {
  let h: any // eslint-disable-line @typescript-eslint/no-explicit-any
  let rows: { race_id: string; circuit_id: string; calibration_flag: string }[] = []
  let report: any // eslint-disable-line @typescript-eslint/no-explicit-any
  beforeAll(async () => {
    h = await createHeadless({ dataDir: DATA })
    const uq = await h.load('/src/data/hooks/useQuery.ts')
    try {
      rows = await uq.getRegisteredQuery('cards.race-circuit-flags')({})
    } catch {
      rows = [] // export from before TX-13: no calibration_flag column
    }
    const barcelona = rows.filter((r) => r.calibration_flag === 'REVIEW_REQUIRED')
    const skipped = rows.filter((r) => r.calibration_flag === 'SKIPPED')
    if (barcelona.length && skipped.length) {
      const pick = (r: { race_id: string }) => ({ season: Number(r.race_id.split('_')[0]), race_id: r.race_id })
      report = await h.build.buildCards({ kinds: ['race.result'], params: { 'race.result': [pick(barcelona[0]), pick(skipped[0])] } })
    }
  }, 120_000)
  afterAll(async () => { await h?.close() })

  it('every race maps to a circuit; the REVIEW_REQUIRED circuit fires the rule, a SKIPPED one does not', function () {
    if (!rows.some((r) => r.calibration_flag)) return void console.warn('[AX-07c] export has no calibration_flag (pre TX-13): skipped')
    expect(rows).toHaveLength(173)
    const review = rows.filter((r) => r.calibration_flag === 'REVIEW_REQUIRED')
    expect(new Set(review.map((r) => r.circuit_id))).toEqual(new Set(['circuit_de_barcelona_catalunya']))
    const flagOf = (id: string) => rows.find((r) => r.race_id === id)!.calibration_flag
    const cards: Card[] = report.cards
    expect(cards.length).toBeGreaterThan(0)
    for (const c of cards) {
      expect(c.policy_fields.calibration_flag).toBe(flagOf(c.scope.race_id as string))
      expect(fires(c)).toBe(c.policy_fields.calibration_flag === 'REVIEW_REQUIRED')
    }
    expect(cards.some((c) => c.policy_fields.calibration_flag === 'REVIEW_REQUIRED')).toBe(true)
    expect(cards.some((c) => c.policy_fields.calibration_flag === 'SKIPPED')).toBe(true)
  })
})
