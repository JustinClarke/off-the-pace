// Generic DuckDB query hook wraps React Query with a named-query registry; rawQuery() bypasses the registry.
import { useQuery as useTanstackQuery, QueryKey } from '@tanstack/react-query'
import { query } from '../duckdb/client'

type QueryFn<TParams, TResult> = (params: TParams) => Promise<TResult>

const queryRegistry = new Map<string, QueryFn<unknown, unknown>>()

export function registerQuery<TParams, TResult>(
  name: string,
  fn: QueryFn<TParams, TResult>
): QueryFn<TParams, TResult> {
  queryRegistry.set(name, fn as QueryFn<unknown, unknown>)
  return fn
}

/** The registered query function for a name, or undefined. Used by the headless card builder (AX-04). */
export function getRegisteredQuery<TParams = unknown, TResult = unknown>(
  name: string
): QueryFn<TParams, TResult> | undefined {
  return queryRegistry.get(name) as QueryFn<TParams, TResult> | undefined
}

/** Names of every registered query (AX-04 registry guard). */
export function registeredQueryNames(): string[] {
  return [...queryRegistry.keys()]
}

export function useQuery<TResult>(
  name: string,
  params: unknown = {},
  options?: { enabled?: boolean; staleTime?: number }
) {
  const queryKey: QueryKey = [name, params]

  return useTanstackQuery<TResult, Error>({
    queryKey,
    queryFn: async () => {
      const fn = queryRegistry.get(name)
      if (!fn) throw new Error(`No query registered for key: ${name}`)
      return fn(params) as Promise<TResult>
    },
    staleTime: options?.staleTime ?? 5 * 60 * 1000,
    enabled: options?.enabled ?? true,
  })
}

export async function rawQuery<T = Record<string, unknown>>(
  sql: string,
  params?: unknown[]
): Promise<T[]> {
  return query<T>(sql, params)
}
