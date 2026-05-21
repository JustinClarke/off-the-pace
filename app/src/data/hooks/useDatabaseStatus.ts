// Subscribes to the DuckDB lifecycle atom; components use this to show loading/error states before querying.
import { useState, useEffect } from 'react'
import { getDbState, subscribeDbState } from '../duckdb/status'
import type { DbState } from '../duckdb/types'

export function useDatabaseStatus(): DbState {
  const [state, setState] = useState<DbState>(getDbState)

  useEffect(() => {
    const unsubscribe = subscribeDbState(setState)
    return unsubscribe
  }, [])

  return state
}
