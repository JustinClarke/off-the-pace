// DuckDB lifecycle types shared between client.ts, status.ts, and useDatabaseStatus.
export type DbStatus = 'idle' | 'initializing' | 'ready' | 'error'

export interface DbState {
  status: DbStatus
  error: Error | null
}
