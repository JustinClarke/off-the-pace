// AX-06 test fixtures: the real catalogue (AX-05 scratch export), a manifest shaped like the export's
// qv_* entries, and a spy engine.
import catalogueJson from '../../catalogue/__fixtures__/catalogue.json'
import { parseCatalogue, type Catalogue } from '../../catalogue/catalogue'
import type { DataManifest, TableManifest } from '../../../data/manifest'
import type { Engine } from '../run'
import type { Scalar } from '../types'

export const catalogue: Catalogue = parseCatalogue(catalogueJson)
export const RACES = ['2024_8', '2024_9', '2023_1']

export function makeManifest(version = 'v-test'): DataManifest {
  const tables: TableManifest[] = catalogue.views.map((v) => {
    const dir = `/data/assistant/qv/${v.name}`
    if (!v.partition_key) return { name: v.name, path: `${dir}.parquet`, partitioned: false }
    const partitions = catalogue.seasons.map((s) =>
      v.sub_partition_key
        ? {
            value: s,
            path: `${dir}/${s}`,
            subPartitions: RACES.filter((r) => r.startsWith(`${s}_`)).map((r) => ({ value: r, path: `${dir}/${s}/${r}.parquet` })),
          }
        : { value: s, path: `${dir}/${s}.parquet` },
    )
    return { name: v.name, path: dir, partitioned: true, partitionKey: 'season', partitions } as TableManifest
  })
  return { version, generatedAt: '2026-11-08T00:00:00Z', tables }
}

export interface SpyEngine extends Engine {
  registered: { alias: string; url: string }[]
  runs: { sql: string; params: Scalar[] }[]
  cancels: number
}

export function spyEngine(rows: Record<string, unknown>[] | (() => Promise<Record<string, unknown>[]>) = []): SpyEngine {
  const e: SpyEngine = {
    registered: [],
    runs: [],
    cancels: 0,
    async registerPartition(alias, url) {
      e.registered.push({ alias, url })
    },
    async prepareRun(sql, params) {
      e.runs.push({ sql, params })
      return typeof rows === 'function' ? rows() : rows
    },
    async cancel() {
      e.cancels++
    },
  }
  return e
}

/** A seeded PRNG (mulberry32) so the fuzz cases are reproducible. */
export function rng(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
