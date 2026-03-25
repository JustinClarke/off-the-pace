// Loads and caches the data manifest; resolves Parquet table paths (including partitions) at runtime.
// Data and model artefacts are served from the GCS CDN by default.
// Set VITE_DATA_BASE (e.g. "" for Vite dev server at localhost) to run fully offline:
//   make app-data && VITE_DATA_BASE="" make app-dev
export const DATA_CDN_BASE: string =
  import.meta.env.VITE_DATA_BASE !== undefined
    ? (import.meta.env.VITE_DATA_BASE as string)
    : 'https://storage.googleapis.com/off-the-pace-cdn'
export interface TableManifest {
  name: string
  path: string
  partitioned: boolean
  partitionKey?: string
  partitions?: Array<{ value: string | number; path: string }>
}

export interface ManifestStats {
  total_laps: number
  dbt_models: number
  ml_models: number
  seasons: string
}

export interface DataManifest {
  version: string
  generatedAt: string
  stats?: ManifestStats
  tables: TableManifest[]
}

let cached: DataManifest | null = null

export async function loadManifest(): Promise<DataManifest> {
  if (cached) return cached
  const res = await fetch(`${DATA_CDN_BASE}/data/_manifest.json`)
  if (!res.ok) throw new Error(`Failed to load data manifest: ${res.status}`)
  cached = await res.json() as DataManifest
  return cached
}

// Append the manifest version as a cache-busting query param. CDN parquet paths
// are NOT content-hashed, so a schema/data change reuses the same URL and the
// browser can serve a stale cached copy indefinitely (the is_self_scenario
// failure of 2026-06-11). Keying the URL on the manifest version which the
// app always re-fetches no-cache gives every data revision a unique URL the
// browser cannot satisfy from a prior cache entry. Only applied to single .parquet
// files; directory globs append the file segment downstream.
function withVersion(url: string, version: string): string {
  if (!url.endsWith('.parquet')) return url
  return `${url}?v=${encodeURIComponent(version)}`
}

export function getTablePath(manifest: DataManifest, name: string, partition?: string | number): string {
  const table = manifest.tables.find(t => t.name === name)
  if (!table) throw new Error(`Table not found in manifest: ${name}`)
  if (table.partitioned && partition !== undefined) {
    const p = table.partitions?.find(p => p.value === partition)
    if (!p) throw new Error(`Partition ${partition} not found for table ${name}`)
    return withVersion(`${DATA_CDN_BASE}${p.path}`, manifest.version)
  }
  return withVersion(`${DATA_CDN_BASE}${table.path}`, manifest.version)
}

/**
 * For double-partitioned tables (year/race_id) returns the path to a specific race file.
 * The partition entry path is the year directory; appending `/{raceId}.parquet` gives the file.
 */
// getTablePath already prepends DATA_CDN_BASE. The year-dir path is not a
// .parquet file so it carries no version param; append the race file then
// version-stamp the resulting URL for the same cache-busting guarantee.
export function getRaceFilePath(manifest: DataManifest, name: string, season: number, raceId: string): string {
  const dir = getTablePath(manifest, name, season)
  return withVersion(`${dir}/${raceId}.parquet`, manifest.version)
}
