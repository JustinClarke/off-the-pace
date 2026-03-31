export default function Page() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold tracking-tight mb-3">Energy-Management Map</h1>
      <p className="text-sm text-muted mb-3">
        This feature requires ERS deployment telemetry harvest and discharge events mapped to
        circuit distance. That channel is not available in the current public dataset; ERS
        state is not broadcast in the official timing feed.
      </p>
      <p className="text-sm text-muted">
        When available, this view will show a circuit-layout overlay of energy harvesting zones
        (braking into heavy-braking corners) and deployment zones (straights and high-load
        sectors), with per-driver variation in ERS management strategy.
      </p>
    </div>
  )
}
