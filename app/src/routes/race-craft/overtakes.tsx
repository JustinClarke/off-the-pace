export default function Page() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold tracking-tight mb-3">Overtake Graph</h1>
      <p className="text-sm text-muted mb-3">
        This feature requires per-lap track-position data to reconstruct which driver passed which,
        and at what lap. That telemetry source is not yet included in the public dataset.
      </p>
      <p className="text-sm text-muted">
        When available, this view will show a directed overtake graph per race every on-track
        position change with the lap, corner, and whether a DRS zone was involved.
      </p>
    </div>
  )
}
