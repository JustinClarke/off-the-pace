// season.results parity: every driver-season card (wins, podiums, classified, starts, DNFs) matches an independent
// SQL oracle over stg_results.parquet. The oracle deliberately uses different columns from the card query:
// classified_position for wins/podiums and the is_dnf flag for DNFs and classified finishes (classified = starts - DNFs; a
// numeric classified_position alone would wrongly count disqualified rows, which the card correctly excludes).
// Configure with AX04_DATA_DIR=<export dir with _manifest.json>. Skips when unset.
// @vitest-environment node
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
// @ts-expect-error plain .mjs script without a declaration file
import { createHeadless } from '../../../scripts/build-cards.mjs'

const DATA = process.env.AX04_DATA_DIR ?? ''
const enabled = DATA !== '' && existsSync(join(DATA, '_manifest.json'))
if (!enabled) console.warn('[season.results parity] skipped: set AX04_DATA_DIR to a scratch export')

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any

describe.skipIf(!enabled)('season.results parity vs independent stg_results SQL', () => {
  let h: Any
  let oracle: Any
  let report: Any

  beforeAll(async () => {
    h = await createHeadless({ dataDir: DATA })
    oracle = await h.adapter.createWasmEngine()
    oracle.registerFile('results.parquet', join(DATA, 'intermediates', 'stg_results.parquet'))
    report = await h.build.buildCards({ kinds: ['season.results'] })
  }, 180_000)

  afterAll(async () => {
    oracle?.close()
    await h?.close()
  })

  it('every driver-season matches wins, podiums, classified, starts and DNFs', () => {
    const rows = oracle.run(`
      SELECT race_year, driver_id,
             COUNT(*) AS starts,
             COUNT(*) FILTER (WHERE classified_position = '1') AS wins,
             COUNT(*) FILTER (WHERE classified_position IN ('1', '2', '3')) AS podiums,
             COUNT(*) FILTER (WHERE NOT is_dnf) AS classified,
             COUNT(*) FILTER (WHERE is_dnf) AS dnfs
        FROM read_parquet('results.parquet')
       GROUP BY race_year, driver_id`)
    expect(rows.length).toBeGreaterThan(100)
    const cards = report.cards.filter((c: Any) => c.kind === 'season.results')
    expect(cards.length).toBe(rows.length)
    const mismatches: string[] = []
    for (const o of rows) {
      const c = cards.find((x: Any) => x.id === `season.results:${o.race_year}:${o.driver_id}`)
      if (!c) { mismatches.push(`${o.race_year} ${o.driver_id}: no card`); continue }
      const pl = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`
      const want = `${pl(Number(o.wins), 'win')}, ${pl(Number(o.podiums), 'podium')}, ${Number(o.classified)} classified finishes, ${pl(Number(o.dnfs), 'DNF')} in ${pl(Number(o.starts), 'start')} (${o.race_year})`
      if (c.value !== Number(o.wins) || c.n.count !== Number(o.starts) || c.display !== want) {
        mismatches.push(`${o.race_year} ${o.driver_id}: card ${c.display} (wins ${c.value}, n ${c.n.count}) vs oracle ${want}`)
      }
    }
    expect(mismatches).toEqual([])
  })
})
