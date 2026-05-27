import { Scatter } from '../../ui/charts'
import type { ScatterPoint } from '../../ui/charts'
import type { TransformResult, QualiRacePoint } from './transform'

const COLORS: Record<string, string> = {
  quali:    '#60a5fa',
  race:     '#f97316',
  balanced: '#94a3b8',
}

const LEGEND = [
  { label: 'Qualifying specialist', color: COLORS.quali },
  { label: 'Balanced',              color: COLORS.balanced },
  { label: 'Race specialist',       color: COLORS.race },
]

function toPoint(p: QualiRacePoint): ScatterPoint {
  return {
    x: p.quali_skill_s,
    y: p.race_skill_s,
    label: p.driver_id,
    color: COLORS[p.specialist],
    driver_id: p.driver_id,
    quali_skill_s: p.quali_skill_s,
    race_skill_s: p.race_skill_s,
    delta_s: p.delta_s,
    n_races: p.n_races,
    specialist: p.specialist,
  }
}

interface Props {
  result: TransformResult
}

export default function QualiVsRaceChart({ result }: Props) {
  const { points } = result
  const data = points.map(toPoint)

  const footnote = (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-1 mt-4">
      {points.map((p, i) => (
        <div key={`${p.driver_id}-${i}`} className="flex items-center gap-1.5 text-xs text-muted">
          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: COLORS[p.specialist] }} />
          <span className="font-mono font-medium text-[rgb(var(--color-text))]">{p.driver_id}</span>
          <span className="text-muted/60">{(p.delta_s >= 0 ? '+' : '')}{p.delta_s.toFixed(2)}s</span>
        </div>
      ))}
    </div>
  )

  return (
    <Scatter
      data={data}
      xLabel="qualifying skill residual (s)"
      yLabel="race skill residual (s)"
      xFormatter={v => `${(v as number) >= 0 ? '+' : ''}${(v as number).toFixed(2)}s`}
      yFormatter={v => `${v >= 0 ? '+' : ''}${v.toFixed(2)}s`}
      legend={LEGEND}
      footnote={footnote}
      renderTooltip={p => (
        <div className="bg-[#13151a] border border-white/15 rounded px-3 py-2 text-xs shadow-xl">
          <p className="font-semibold mb-1">{p.driver_id as string}</p>
          <p className="text-muted">
            quali: <span className="font-mono text-[rgb(var(--color-text))]">
              {(p.quali_skill_s as number) >= 0 ? '+' : ''}{(p.quali_skill_s as number).toFixed(3)}s
            </span>
          </p>
          <p className="text-muted">
            race: <span className="font-mono text-[rgb(var(--color-text))]">
              {(p.race_skill_s as number) >= 0 ? '+' : ''}{(p.race_skill_s as number).toFixed(3)}s
            </span>
          </p>
          <p className="text-muted">
            Q−R delta: <span className="font-mono text-[rgb(var(--color-text))]">
              {(p.delta_s as number) >= 0 ? '+' : ''}{(p.delta_s as number).toFixed(3)}s
            </span>
          </p>
          <p className="text-muted">races: <span className="font-mono">{String(p.n_races)}</span></p>
          <p className="mt-1 capitalize font-medium" style={{ color: COLORS[p.specialist as string] }}>
            {(p.specialist as string).replace('-', ' ')}
          </p>
        </div>
      )}
    />
  )
}
