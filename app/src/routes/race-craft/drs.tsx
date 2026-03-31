export default function Page() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold tracking-tight mb-3">DRS Dependency</h1>
      <p className="text-sm text-muted mb-3">
        This feature requires per-lap DRS activation events and the speed delta measured across
        DRS zones. That telemetry channel is not yet in the public export.
      </p>
      <p className="text-sm text-muted">
        When available, this view will show how much of each driver's race pace depended on
        DRS circuits where the top-speed delta made overtaking all but mandatory, versus
        circuits where drivers could sustain pace without DRS protection.
      </p>
    </div>
  )
}
