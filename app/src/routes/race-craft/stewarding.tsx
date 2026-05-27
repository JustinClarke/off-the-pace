export default function Page() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold tracking-tight mb-3">Penalty Impact</h1>
      <p className="text-sm text-muted mb-3">
        This feature requires the FIA incident and penalty log, which is not yet ingested into
        the pipeline. Race incidents (track limits, collisions, unsafe releases) and their
        resulting penalties (time additions, grid drops) are not in the current dataset.
      </p>
      <p className="text-sm text-muted">
        When available, this view will quantify the championship-points impact of stewarding
        decisions which drivers were most penalised, how consistent decisions were across
        circuits, and how often penalties changed race outcomes.
      </p>
    </div>
  )
}
