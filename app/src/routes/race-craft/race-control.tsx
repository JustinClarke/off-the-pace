export default function Page() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold tracking-tight mb-3">Race Control Timeline</h1>
      <p className="text-sm text-muted mb-3">
        This feature requires the FIA race control message feed safety car deployments, VSC
        periods, red flags, and the lap on which each occurred. That event log is not yet
        ingested into the pipeline.
      </p>
      <p className="text-sm text-muted">
        When available, this view will provide a lap-by-lap timeline of safety car and VSC
        windows per race, overlaid with the pit-strategy decisions drivers made in response  
        showing who gained and lost positions under each neutralisation period.
      </p>
    </div>
  )
}
