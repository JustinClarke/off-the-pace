// AX-04 seam: stands in for data/duckdb/client.ts when the headless runner loads a feature.
import { headless } from './adapter'

export type DuckDBConnection = unknown

export async function query<T = Record<string, unknown>>(sql: string, params?: unknown[]): Promise<T[]> {
  return headless().query<T>(sql, params)
}

/** The browser returns an AsyncDuckDBConnection; headless callers only need query(). */
export async function getConnection(): Promise<{ query: typeof query }> {
  return { query }
}

export function getDb(): null {
  return null
}
