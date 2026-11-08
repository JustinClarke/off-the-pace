// AX-06: session store of query_data results by result_id, for AX-14's render-time grounding check
// (every number in an answer must match a card or a result returned in this session).
import type { QueryResult } from './types'

const MAX_RESULTS = 200
const results = new Map<string, QueryResult>()

export function rememberResult(r: QueryResult): void {
  results.delete(r.result_id)
  results.set(r.result_id, r)
  while (results.size > MAX_RESULTS) results.delete(results.keys().next().value as string)
}

export function getResult(id: string): QueryResult | undefined {
  return results.get(id)
}

export function sessionResults(): QueryResult[] {
  return [...results.values()]
}

export function clearResults(): void {
  results.clear()
}
