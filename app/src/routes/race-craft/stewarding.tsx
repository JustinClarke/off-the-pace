export default function Page() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold tracking-tight mb-3">Penalty Impact</h1>
      <p className="text-sm text-muted mb-3">
        The FIA race-control message feed is ingested-12,814 messages across all 149 races,
        2018-2024-and the Race Control Timeline is built from that lineage. What it does not
        carry is structure. Incidents (track limits, collisions, unsafe releases) and the
        penalties that follow them (time additions, grid drops) exist only as free text inside
        the messages, with no driver, no sanction and no time cost as fields.
      </p>
      <p className="text-sm text-muted">
        When available, this view will quantify the championship-points impact of stewarding
        decisions which drivers were most penalised, how consistent decisions were across
        circuits, and how often penalties changed race outcomes.
      </p>
    </div>
  )
}
