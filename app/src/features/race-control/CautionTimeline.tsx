// The lap axis of one race, green with the neutralisations burnt onto it.
// No interval is drawn here on purpose: this pane is observation, and the page
// keeps it visually separate from the estimated hazard pane below it.
import { KIND_COLOR, KIND_LABEL, type CautionKind, type TimelineResult } from './transform'

const KINDS: CautionKind[] = ['safety_car', 'vsc', 'red_flag']

export default function CautionTimeline({
  result,
  raceLabel,
}: {
  result: TimelineResult
  raceLabel: string
}) {
  const { raceLaps, segments, cautionLaps } = result
  if (!raceLaps) return null

  const pct = (lap: number) => ((lap - 1) / raceLaps) * 100
  const tickEvery = raceLaps > 60 ? 10 : 5
  const ticks: number[] = []
  for (let l = tickEvery; l <= raceLaps; l += tickEvery) ticks.push(l)

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold tracking-tight">{raceLabel} — lap by lap</h2>
        <span className="font-mono text-xs text-muted">
          {cautionLaps} of {raceLaps} laps under caution
        </span>
      </div>

      {/* Lap strip */}
      <div className="relative h-12 w-full overflow-hidden rounded border border-border bg-emerald-500/10">
        {segments.map(s => (
          <div
            key={`${s.kind}-${s.startLap}`}
            className="absolute inset-y-0"
            style={{
              left: `${pct(s.startLap)}%`,
              width: `${(s.laps / raceLaps) * 100}%`,
              backgroundColor: KIND_COLOR[s.kind],
              opacity: 0.85,
            }}
            title={`${KIND_LABEL[s.kind]}: lap ${s.startLap}${
              s.laps > 1 ? `–${s.endLap}` : ''
            } (${s.laps} lap${s.laps === 1 ? '' : 's'})`}
          />
        ))}
        {ticks.map(t => (
          <div
            key={t}
            className="absolute inset-y-0 w-px bg-[rgb(var(--color-border))] opacity-50"
            style={{ left: `${pct(t)}%` }}
          />
        ))}
      </div>

      {/* Lap ruler */}
      <div className="relative mt-1 h-4">
        <span className="absolute left-0 font-mono text-[10px] text-muted">1</span>
        {ticks.map(t => (
          <span
            key={t}
            className="absolute -translate-x-1/2 font-mono text-[10px] text-muted"
            style={{ left: `${pct(t)}%` }}
          >
            {t}
          </span>
        ))}
        <span className="absolute right-0 font-mono text-[10px] text-muted">{raceLaps}</span>
      </div>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2">
        <span className="flex items-center gap-1.5 text-xs text-muted">
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-emerald-500/40" />
          Green
        </span>
        {KINDS.map(k => (
          <span key={k} className="flex items-center gap-1.5 text-xs text-muted">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: KIND_COLOR[k] }}
            />
            {KIND_LABEL[k]}
          </span>
        ))}
      </div>

      {/* Event list */}
      {segments.length === 0 ? (
        <p className="mt-5 text-sm text-muted">
          This race ran green from lights to flag — no safety car, VSC or red flag on any lap.
        </p>
      ) : (
        <table className="mt-5 w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted">
              <th className="pb-2 font-medium">Event</th>
              <th className="pb-2 font-medium">Laps</th>
              <th className="pb-2 text-right font-medium">Duration</th>
              <th className="pb-2 text-right font-medium">Share of race</th>
            </tr>
          </thead>
          <tbody>
            {segments.map(s => (
              <tr key={`${s.kind}-${s.startLap}`} className="border-b border-border/50">
                <td className="py-2">
                  <span className="flex items-center gap-2">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-sm"
                      style={{ backgroundColor: KIND_COLOR[s.kind] }}
                    />
                    {KIND_LABEL[s.kind]}
                  </span>
                </td>
                <td className="py-2 font-mono text-xs">
                  {s.startLap}
                  {s.laps > 1 ? `–${s.endLap}` : ''}
                </td>
                <td className="py-2 text-right font-mono text-xs">
                  {s.laps} lap{s.laps === 1 ? '' : 's'}
                </td>
                <td className="py-2 text-right font-mono text-xs text-muted">
                  {((s.laps / raceLaps) * 100).toFixed(1)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
