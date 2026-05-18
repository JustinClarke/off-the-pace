// DuckDB status indicator shown in the TopBar idle/initializing/ready/error with a spinner or dot.
import { useDatabaseStatus } from '../../data/hooks/useDatabaseStatus'
import Spinner from '../feedback/Spinner'

export default function EngineStatus() {
  const { status, error } = useDatabaseStatus()

  if (status === 'ready') return null
  if (status === 'error') {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded text-xs text-red-400 bg-red-500/10">
        <span className="h-1.5 w-1.5 rounded-full bg-red-400" />
        Engine error
        {error && <span className="text-muted ml-1">{error.message}</span>}
      </div>
    )
  }
  if (status === 'initializing') {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded text-xs text-muted bg-surface">
        <Spinner size="sm" />
        Loading engine…
      </div>
    )
  }
  return null
}
