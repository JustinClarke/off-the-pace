// AX-04 seam: stands in for data/duckdb/register.ts when the headless runner loads a feature.
import { headless } from './adapter'
import type { DataManifest } from '../../../data/manifest'
import { getTablePath } from './manifest'

export async function registerParquet(tableName: string, url: string): Promise<void> {
  return headless().registerParquet(tableName, url)
}

export async function registerPartitionedParquet(name: string, manifest: DataManifest): Promise<void> {
  return headless().registerPartitionedParquet(name, manifest, getTablePath)
}

export async function registerParquetMany(tables: Array<{ name: string; url: string }>): Promise<void> {
  for (const { name, url } of tables) await registerParquet(name, url)
}

export function isRegistered(tableName: string): boolean {
  return headless().isRegistered(tableName)
}

export function clearRegistrations(): void {
  headless().clearRegistrations()
}
