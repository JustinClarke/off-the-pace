// Loads and caches the data manifest; resolves Parquet table paths (including partitions) at runtime.
// Data and model artefacts are served from GitHub Pages to keep the Vercel deployment under 100 MB.
export const DATA_CDN_BASE = 'https://storage.googleapis.com/off-the-pace-cdn'
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

export function getTablePath(manifest: DataManifest, name: string, partition?: string | number): string {
  const table = manifest.tables.find(t => t.name === name)
  if (!table) throw new Error(`Table not found in manifest: ${name}`)
  if (table.partitioned && partition !== undefined) {
    const p = table.partitions?.find(p => p.value === partition)
    if (!p) throw new Error(`Partition ${partition} not found for table ${name}`)
    return `${DATA_CDN_BASE}${p.path}`
  }
  return `${DATA_CDN_BASE}${table.path}`
}

/**
 * For double-partitioned tables (year/race_id) returns the path to a specific race file.
 * The partition entry path is the year directory; appending `/{raceId}.parquet` gives the file.
 */
// getTablePath already prepends DATA_CDN_BASE, so just append the race file.
export function getRaceFilePath(manifest: DataManifest, name: string, season: number, raceId: string): string {
  const dir = getTablePath(manifest, name, season)
  return `${dir}/${raceId}.parquet`
}
