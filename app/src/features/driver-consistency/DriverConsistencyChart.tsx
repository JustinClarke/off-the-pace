import { Scatter } from '../../ui/charts'
import type { ScatterPoint } from '../../ui/charts'
import type { TransformResult, ConsistencyPoint } from './transform'

const QUADRANT_COLORS: Record<string, string> = {
  'fast-consistent': '#34d399',
  'fast-erratic':    '#fbbf24',
  'slow-consistent': '#60a5fa',
  'slow-erratic':    '#f87171',
}

const LEGEND = Object.entries(QUADRANT_COLORS).map(([label, color]) => ({ label, color }))

function toPoint(p: ConsistencyPoint): ScatterPoint {
  return {
    x: p.mean_s,
    y: p.stddev_s,
    label: p.driver_id,
    color: QUADRANT_COLORS[p.quadrant],
    // extra fields available in renderTooltip
    driver_id: p.driver_id,
    mean_s: p.mean_s,
    stddev_s: p.stddev_s,
    clean_lap_count: p.clean_lap_count,
    quadrant: p.quadrant,
  }
}

interface Props {
  result: TransformResult
}

export default function DriverConsistencyChart({ result }: Props) {
  const { points, medianMean, medianStddev } = result
  const data = points.map(toPoint)

  const footnote = (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-1 mt-4">
      {points.map((p, i) => (
        <div key={`${p.driver_id}-${i}`} className="flex items-center gap-1.5 text-xs text-muted">
          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: QUADRANT_COLORS[p.quadrant] }} />
          <span className="font-mono font-medium text-[rgb(var(--color-text))]">{p.driver_id}</span>
          <span className="text-muted/60">{p.mean_s.toFixed(2)}s</span>
        </div>
      ))}
    </div>
  )

  return (
    <Scatter
      data={data}
      xLabel="mean residual (s)"
      yLabel="std dev (s)"
      xFormatter={v => `${(v as number) > 0 ? '+' : ''}${(v as number).toFixed(2)}s`}
      yFormatter={v => `${v.toFixed(2)}s`}
      xRef={medianMean}
      yRef={medianStddev}
      legend={LEGEND}
      footnote={footnote}
      renderTooltip={p => (
        <div className="bg-[#13151a] border border-white/15 rounded px-3 py-2 text-xs shadow-xl">
          <p className="font-semibold mb-1">{p.driver_id as string}</p>
          <p className="text-muted">mean residual: <span className="font-mono text-[rgb(var(--color-text))]">{(p.mean_s as number).toFixed(3)}s</span></p>
          <p className="text-muted">std dev: <span className="font-mono text-[rgb(var(--color-text))]">{(p.stddev_s as number).toFixed(3)}s</span></p>
          <p className="text-muted">clean laps: <span className="font-mono text-[rgb(var(--color-text))]">{String(p.clean_lap_count)}</span></p>
          <p className="mt-1 font-medium capitalize" style={{ color: QUADRANT_COLORS[p.quadrant as string] }}>
            {(p.quadrant as string).replace(/-/g, ' ')}
          </p>
        </div>
      )}
    />
  )
}
