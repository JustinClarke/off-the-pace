export default function Page() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold tracking-tight mb-3">Racing Line Fidelity</h1>
      <p className="text-sm text-muted mb-3">
        This feature requires GPS coordinates at lap-level resolution to compare each driver's
        actual racing line against the reference optimal line for each circuit. That positional
        data source is not yet available in the dataset.
      </p>
      <p className="text-sm text-muted">
        When available, this view will score each driver's circuit-level adherence to the
        optimal racing line identifying drivers who consistently find cleaner arcs through
        high-speed corners versus those who sacrifice geometry for momentum.
      </p>
    </div>
  )
}
