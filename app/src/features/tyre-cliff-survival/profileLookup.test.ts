// Runs the page's real lookup (RACE_TRACK_SQL + PROFILES_SQL + findProfile) against the
// published parquet files in app/public/data, with duckdb-wasm's node build.
// @vitest-environment node
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import path from 'node:path'
import { createDuckDB, NODE_RUNTIME, ConsoleLogger, DuckDBDataProtocol } from '@duckdb/duckdb-wasm/blocking'
import { PROFILES_SQL, RACE_TRACK_SQL } from './queries'
import type { CompoundProfileRow } from './queries'
import { findProfile } from './transform'

const DATA = path.resolve(__dirname, '../../../public/data')
const DIST = path.resolve(__dirname, '../../../node_modules/@duckdb/duckdb-wasm/dist')

let db: any
let conn: any

function all<T>(sql: string, params: unknown[]): T[] {
  const stmt = conn.prepare(sql)
  const rows = stmt.query(...params).toArray().map((r: any) => ({ ...r.toJSON() })) as T[]
  stmt.close()
  return rows
}

beforeAll(async () => {
  db = await createDuckDB(
    { mvp: { mainModule: path.join(DIST, 'duckdb-mvp.wasm'), mainWorker: path.join(DIST, 'duckdb-node-mvp.worker.cjs') },
      eh: { mainModule: path.join(DIST, 'duckdb-eh.wasm'), mainWorker: path.join(DIST, 'duckdb-node-eh.worker.cjs') } },
    new ConsoleLogger(),
    NODE_RUNTIME,
  )
  await db.instantiate()
  for (const [name, file] of [['race_to_track', 'dimensions/race_to_track.parquet'], ['dim_compounds_season', 'dimensions/dim_compounds_season.parquet']]) {
    db.registerFileURL(`${name}.parquet`, path.join(DATA, file), DuckDBDataProtocol.NODE_FS, false)
  }
  conn = db.connect()
  conn.query(`CREATE VIEW race_to_track AS SELECT * FROM read_parquet('race_to_track.parquet')`)
  conn.query(`CREATE VIEW dim_compounds_season AS SELECT * FROM read_parquet('dim_compounds_season.parquet')`)
})

afterAll(() => { conn?.close(); db?.terminate?.() })

/** What the page does: race id -> circuit -> profile for the compound. */
function profileFor(raceId: string, compound: string): CompoundProfileRow | null {
  const season = Number(raceId.split('_')[0])
  const profiles = all<CompoundProfileRow>(PROFILES_SQL, [season])
  const trackId = all<{ track_id: string }>(RACE_TRACK_SQL, [raceId])[0]?.track_id ?? null
  return findProfile(profiles, trackId, compound)
}

describe('tyre survival profile lookup on the published data', () => {
  // [race, compound]: 2023 R1 Australia, 2021 R5 Monaco, 2024 R10 (Spain) across three seasons
  it.each([
    ['2023_1', 'SOFT'],
    ['2021_5', 'MEDIUM'],
    ['2024_10', 'HARD'],
  ])('race %s %s resolves to a profile with model chips', (raceId, compound) => {
    const p = profileFor(raceId, compound)
    expect(p).not.toBeNull()
    expect(p!.compound_code).toBe(compound)
    expect(p!.compound_cliff_onset_laps).not.toBeNull()
    expect(p!.compound_cliff_severity).not.toBeNull()
    expect(p!.compound_wear_gradient).not.toBeNull()
  })
})
