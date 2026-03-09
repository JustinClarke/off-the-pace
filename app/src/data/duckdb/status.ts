// Observable DB-status atom components subscribe via subscribeDbState() to react to init/ready/error transitions.
import { DbState, DbStatus } from './types'

type Listener = (state: DbState) => void

let state: DbState = { status: 'idle', error: null }
const listeners = new Set<Listener>()

export function getDbState(): DbState {
  return state
}

export function setDbStatus(status: DbStatus, error: Error | null = null): void {
  state = { status, error }
  listeners.forEach(fn => fn(state))
}

export function subscribeDbState(fn: Listener): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
