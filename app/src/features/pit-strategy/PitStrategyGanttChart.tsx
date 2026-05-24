import { Gantt } from '../../ui/charts'
import { compoundColor } from '../../lib/colors'
import type { GanttResult } from './transform'

interface Props {
  result: GanttResult
}

const VERDICT_COLORS: Record<string, string> = {
  optimal: 'rgb(52, 211, 153)',
  overran: 'rgb(248, 113, 113)',
  unknown: 'rgb(100, 116, 139)',
}

export default function PitStrategyGanttChart({ result }: Props) {
  const { stints, totalLaps, verdictCounts, totalOpportunityCostS, topCostStints } = result

  return (
    <div className="space-y-6">
      {/* Summary strip */}
      <div className="flex flex-wrap gap-6 text-xs">
        {Object.entries(verdictCounts).map(([v, n]) => (
          <div key={v} className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: VERDICT_COLORS[v] }} />
            <span className="font-mono font-medium text-[rgb(var(--color-text))]">{n}</span>
            <span className="text-muted capitalize">{v}</span>
          </div>
        ))}
        {totalOpportunityCostS > 0 && (
          <div className="text-muted ml-auto">
            Total opportunity cost:{' '}
            <span className="font-mono text-red-400">+{totalOpportunityCostS.toFixed(1)} s</span>
          </div>
        )}
      </div>

      <Gantt
        stints={stints}
        totalLaps={totalLaps}
        compoundColor={compoundColor}
      />

      {/* Top cost stints */}
      {topCostStints.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-medium text-[rgb(var(--color-text))] mb-2">Biggest overruns</p>
          <div className="divide-y divide-border">
            {topCostStints.map(s => (
              <div
                key={`${s.driverId}-${s.stintNumber}`}
                className="flex items-center gap-3 py-1.5 text-xs"
              >
                <span className="font-mono text-[rgb(var(--color-text))] w-10">{s.driverId}</span>
                <span
                  className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
                  style={{ background: compoundColor(s.compound) }}
                  title={s.compound}
                />
                <span className="text-muted flex-1">
                  Stint {s.stintNumber} &middot; laps {s.startLap}&ndash;{s.endLap}
                  {s.overrunLaps != null && s.overrunLaps > 0 && (
                    <> &middot; <span className="font-mono text-red-400">+{s.overrunLaps} lap{s.overrunLaps !== 1 ? 's' : ''} late</span></>
                  )}
                </span>
                <span className="font-mono text-red-400 tabular-nums">
                  +{s.opportunityCostS?.toFixed(1)} s
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
