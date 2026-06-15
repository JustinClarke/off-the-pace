export default function Page() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold tracking-tight mb-3">Pass-Location Heatmap</h1>
      <p className="text-sm text-muted mb-3">
        This feature requires GPS track-position data at metre-level resolution to detect where
        position changes occur on the circuit layout. That data source is not yet ingested.
      </p>
      <p className="text-sm text-muted">
        When available, this view will overlay a 2D circuit map with a heatmap of overtaking
        frequency highlighting which corners and straights generate the most race action,
        and how that shifts across seasons as regulations change.
      </p>
    </div>
  )
}
