// The simulator's three-view output: the predicted degradation fan across the stint, the
// cliff-class probability bars at the current lap, and the remaining-stint-life gauge. All three
// read the same SimulatorResult so they stay in sync as the sliders move.

import QuantileFanChart from '../../ui/charts/QuantileFanChart'
import type { SimulatorResult } from './transform'

const CLIFF_COLORS: Record<string, string> = {
  '0_to_2': '#f87171',      // imminent cliff-red
  '3_to_5': '#fbbf24',      // soon-amber
  '6_plus': '#60a5fa',      // distant-blue
  none_in_stint: '#34d399', // safe-green
}

function CliffBars({ result }: { result: SimulatorResult }) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold">Cliff probability <span className="text-muted font-normal">at lap {result.currentLap}</span></h3>
      {result.cliffBars.map(bar => (
        <div key={bar.rawLabel} className="flex items-center gap-2">
          <span className="text-xs text-muted w-32 flex-shrink-0">{bar.label}</span>
          <div className="flex-1 h-4 rounded bg-white/5 overflow-hidden">
            <div
              className="h-full rounded transition-all"
              style={{ width: `${Math.round(bar.prob * 100)}%`, background: CLIFF_COLORS[bar.rawLabel] ?? '#888' }}
            />
          </div>
          <span className="text-xs font-mono text-[rgb(var(--color-text))] w-10 text-right">
            {(bar.prob * 100).toFixed(0)}%
          </span>
        </div>
      ))}
      <p className="text-xs text-muted/70 mt-1">
        Most likely: <span className="font-medium text-[rgb(var(--color-text))]">{result.cliffLabel}</span>
      </p>
    </div>
  )
}

function LifeGauge({ laps }: { laps: number }) {
  // Gauge scaled against a generous 40-lap stint horizon.
  const pct = Math.min(100, (laps / 40) * 100)
  const color = laps <= 3 ? '#f87171' : laps <= 8 ? '#fbbf24' : '#34d399'
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold">Remaining stint life</h3>
      <div className="flex items-end gap-2">
        <span className="text-4xl font-bold tabular-nums" style={{ color }}>{laps.toFixed(1)}</span>
        <span className="text-sm text-muted mb-1">laps</span>
      </div>
      <div className="h-2.5 rounded-full bg-white/5 overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
      <p className="text-xs text-muted/70">
        Predicted laps before the tyre must be retired (stint_life_regressor, clipped at 0).
      </p>
    </div>
  )
}

interface Props {
  result: SimulatorResult
}

export default function DegradationSimulatorChart({ result }: Props) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="flex items-baseline justify-between mb-2">
          <h3 className="text-sm font-semibold">Predicted degradation jump across the stint</h3>
          <span className="text-xs text-muted">
            next-lap jump at lap {result.currentLap}:{' '}
            <span className="font-mono text-[rgb(var(--color-text))]">
              {result.currentJumpP50 >= 0 ? '+' : ''}{result.currentJumpP50.toFixed(3)}s
            </span>
          </span>
        </div>
        <QuantileFanChart
          data={result.fan}
          xLabel="lap in stint"
          yLabel="next-lap jump (s)"
          xFormatter={v => `L${v}`}
          yFormatter={v => `${v >= 0 ? '+' : ''}${v.toFixed(2)}s`}
          xRef={result.currentLap}
          xRefLabel="current"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
        <CliffBars result={result} />
        <LifeGauge laps={result.remainingLifeLaps} />
      </div>
    </div>
  )
}
