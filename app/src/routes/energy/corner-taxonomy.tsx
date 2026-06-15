export default function Page() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold tracking-tight mb-3">Corner Taxonomy</h1>
      <p className="text-sm text-muted mb-3">
        This feature classifies each circuit's corners into archetypes (high-speed sweepers,
        medium-speed technical, slow hairpins) and requires both telemetry-derived corner
        metrics and a validated circuit-geometry catalogue. The corner geometry catalogue is
        not yet fully populated for all circuits in the dataset.
      </p>
      <p className="text-sm text-muted">
        When available, this view will let you explore which corner types favour which
        constructor or driver profiles answering whether a car that excels in slow corners
        compensates in high-speed sections, or whether an all-rounder advantage is real.
      </p>
    </div>
  )
}
