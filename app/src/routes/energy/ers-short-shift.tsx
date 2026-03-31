export default function Page() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold tracking-tight mb-3">ERS &amp; Short-Shift</h1>
      <p className="text-sm text-muted mb-3">
        This feature requires gear-change and ERS deployment telemetry at a per-lap resolution.
        Neither the gear channel nor ERS state are available in the current public dataset.
      </p>
      <p className="text-sm text-muted">
        When available, this view will identify corners and straights where drivers short-shift
        to optimise ERS deployment a technique that can yield tenths per lap in the right
        conditions and rank drivers by how aggressively they use it.
      </p>
    </div>
  )
}
