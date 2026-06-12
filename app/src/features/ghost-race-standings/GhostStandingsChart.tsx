import RankedTable from '../../ui/charts/RankedTable'
import type { TransformResult, RaceScenario } from './transform'
import { CONFIDENCE_FLOOR } from './transform'

interface Props {
  result: TransformResult
  /** If provided, only show this scenario (filtered by the page to one race + constructor). */
  activeScenario?: RaceScenario
}

function ScenarioTable({ scenario }: { scenario: RaceScenario }) {
  const deltaClass = (delta: number): string => {
    if (delta < -1) return 'text-emerald-400'
    if (delta > 1) return 'text-rose-400'
    return 'text-muted'
  }

  const confidenceBadge = (conf: number): string => {
    if (conf >= 0.7) return 'bg-emerald-500/10 text-emerald-400'
    if (conf >= CONFIDENCE_FLOOR) return 'bg-amber-500/10 text-amber-400'
    return 'bg-rose-500/10 text-rose-400'
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-mono text-muted uppercase tracking-wider">
          {scenario.hostConstructorId}
        </span>
        <span className="text-xs text-muted/50">race {scenario.raceId}</span>
        {scenario.minConfidence < 0.5 && (
          <span className="ml-auto text-xs text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded">
            low confidence
          </span>
        )}
      </div>
      <RankedTable<any>
        rows={scenario.entries}
        columns={[
          {
            key: 'predictedPosition',
            header: 'Pred.',
            align: 'right',
            render: v => <span className="font-semibold">{String(v)}</span>,
          },
          {
            key: 'driverId',
            header: 'Driver',
            align: 'left',
            render: v => <span className="font-medium tracking-wide">{String(v)}</span>,
          },
          {
            key: 'actualPosition',
            header: 'Actual',
            align: 'right',
            render: v => v != null ? String(v) : <span className="text-muted/40">-</span>,
          },
          {
            key: 'delta',
            header: 'Δ pos',
            align: 'right',
            render: (v, row) => {
              if (row.isSelfScenario) {
                return <span className="text-muted/40 text-xs" title="Own-car scenario identity holds">self</span>
              }
              const d = v as number | null
              if (d == null) {
                return <span className="text-muted/40 text-xs" title="DNF no actual finishing position">—</span>
              }
              const label = d === 0 ? '=' : d > 0 ? `+${d}` : String(d)
              return <span className={deltaClass(d)}>{label}</span>
            },
          },
          {
            key: 'confidence',
            header: 'Conf.',
            align: 'right',
            render: v => {
              const c = v as number
              return (
                <span className={`text-xs px-1.5 py-0.5 rounded font-mono ${confidenceBadge(c)}`}>
                  {c.toFixed(2)}
                </span>
              )
            },
          },
          {
            key: 'lapsScored',
            header: 'Laps',
            align: 'right',
            render: (v, row) => {
              const laps = v as number
              if (row.isShortRun) {
                return (
                  <span
                    className="text-amber-400/80"
                    title={`Partial race ${(row.lapCoverage * 100).toFixed(0)}% of distance (small-sample estimate)`}
                  >
                    {laps}
                    <span className="ml-1 text-[10px] uppercase tracking-wide">dnf</span>
                  </span>
                )
              }
              return <span>{laps}</span>
            },
          },
        ]}
        initialRows={25}
      />
    </div>
  )
}

export default function GhostStandingsChart({ result, activeScenario }: Props) {
  const scenarios = activeScenario ? [activeScenario] : result.scenarios

  if (!scenarios.length) return null

  if (scenarios.length === 1) {
    return <ScenarioTable scenario={scenarios[0]} />
  }

  return (
    <div className="space-y-8">
      {scenarios.map(s => (
        <ScenarioTable
          key={`${s.raceId}::${s.hostConstructorId}`}
          scenario={s}
        />
      ))}
    </div>
  )
}
