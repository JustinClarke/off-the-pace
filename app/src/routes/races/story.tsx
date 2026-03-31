import { useParams } from 'react-router-dom'

export default function Page() {
  const { raceId } = useParams<{ raceId: string }>()
  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold tracking-tight mb-3">Race Story</h1>
      {raceId && (
        <p className="text-xs font-mono text-muted mb-3">{raceId}</p>
      )}
      <p className="text-sm text-muted mb-3">
        The Race Story view is a single-race narrative dashboard lap chart, position changes,
        tyre strategy overlay, pace decomposition, and key moments that requires a dedicated
        race-level data model. That model has not been built yet.
      </p>
      <p className="text-sm text-muted">
        Individual race data (lap times, stints, pit stops) is already available through the
        existing feature pages: use the race selector in Dirty Air, Sector Decomposition, or
        the Lap Waterfall to drill into a specific event.
      </p>
    </div>
  )
}
