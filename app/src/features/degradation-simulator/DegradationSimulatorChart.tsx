// The simulator's output views. The primary chart is the absolute projected lap time, decomposed
// into the fresh-tyre anchor + fuel + tyre-degradation components (stacked areas), with the
// observed historical range (p10/p90 of the isotonic-fitted monotone degradation × M). Below it:
// the predicted degradation-jump fan, cliff-class probability bars, and remaining-stint-life gauge.
// All read the same SimulatorResult so they stay in sync as the sliders move.

import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
  ResponsiveContainer, TooltipProps,
} from 'recharts'
import QuantileFanChart from '../../ui/charts/QuantileFanChart'
import type { SimulatorResult } from './transform'

const GRID = 'rgba(255,255,255,0.05)'
const AXIS_STYLE = { fontSize: 11, fill: 'rgb(var(--color-text-muted))' }
const REF_COLOR = '#475569'
const FUEL_COLOR = '#38bdf8'
const TYRE_COLOR = '#f59e0b'
const NET_COLOR = '#e2e8f0'
const HIST_COLOR = '#a78bfa'

const CLIFF_COLORS: Record<string, string> = {
  '0_to_2': '#f87171',      // imminent cliff-red
  '3_to_5': '#fbbf24',      // soon amber
  '6_plus': '#60a5fa',      // distant blue
  none_in_stint: '#34d399', // safe green
}

interface LapTimeDatum {
  x: number
  floor: number
  refBase: number       // ref − floor (invisible stacking base)
  fuelBand: number      // fuel component (stacked)
  tyreBand: number      // tyre component (stacked) → top edge = net
  net: number
  netP10: number        // fitted observed p10 band × M (absolute axis)
  netP90: number        // fitted observed p90 band × M (absolute axis)
}

function LapTimeTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload as LapTimeDatum
  return (
    <div className="bg-[#13151a] border border-white/15 rounded px-3 py-2 text-xs shadow-xl space-y-0.5">
      <p className="font-semibold mb-1">Lap {d.x}</p>
      <p className="text-muted">Projected: <span className="font-mono text-[rgb(var(--color-text))]">{(d.net + d.floor).toFixed(3)}s</span></p>
      <p className="text-muted">Fresh-tyre anchor: <span className="font-mono text-[rgb(var(--color-text))]">{(d.refBase + d.floor).toFixed(3)}s</span></p>
      <p className="text-muted">+ Fuel: <span className="font-mono" style={{ color: FUEL_COLOR }}>{d.fuelBand.toFixed(3)}s</span></p>
      <p className="text-muted">+ Tyre (isotonic deg): <span className="font-mono" style={{ color: TYRE_COLOR }}>{d.tyreBand.toFixed(3)}s</span></p>
    </div>
  )
}

function LapTimeChart({ result }: { result: SimulatorResult }) {
  const curve = result.laptimeCurve

  // Stack components from a common floor (recharts stacks from 0; subtract a floor so the empty
  // base region doesn't dominate the y-range). Floor = a touch below the smallest plotted value.
  const lo = Math.min(...curve.map(p => Math.min(p.p10, p.net)))
  const floor = Math.floor(lo - 1)

  const data: LapTimeDatum[] = curve.map(p => ({
    x: p.x,
    floor,
    refBase: p.ref - floor,
    fuelBand: p.fuel,
    tyreBand: p.tyre,
    net: p.net - floor,
    netP10: p.p10 - floor,
    netP90: p.p90 - floor,
  }))

  return (
    <div className="w-full">
      <div className="flex flex-wrap gap-4 mb-3">
        <Legend color={REF_COLOR} swatch>Fresh-tyre anchor</Legend>
        <Legend color={FUEL_COLOR} swatch>Fuel</Legend>
        <Legend color={TYRE_COLOR} swatch>Tyre degradation</Legend>
        <Legend color={NET_COLOR}>Projected lap time</Legend>
        {result.laptimeCurve.some(p => p.p10 !== p.net) && <Legend color={HIST_COLOR} dashed>Observed range</Legend>}
      </div>
      <ResponsiveContainer width="100%" height={380}>
        <ComposedChart data={data} margin={{ top: 20, right: 30, bottom: 20, left: 24 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="x" tickFormatter={v => `L${v}`} tick={AXIS_STYLE}
            label={{ value: 'lap in stint', position: 'insideBottom', offset: -10, fontSize: 11, fill: 'rgb(var(--color-text-muted))' }} />
          <YAxis
            domain={['dataMin', 'dataMax']}
            tickFormatter={(v: number) => `${(v + floor).toFixed(1)}s`}
            tick={AXIS_STYLE}
            label={{ value: 'lap time (s)', angle: -90, position: 'insideLeft', offset: 8, fontSize: 11, fill: 'rgb(var(--color-text-muted))' }}
          />
          <Tooltip content={(props: any) => <LapTimeTooltip {...props} />} />

          {/* Stacked decomposition: invisible base (floor→ref), fuel, then tyre (top edge = net). */}
          <Area type="monotone" dataKey="refBase" stackId="lt" stroke="none" fill={REF_COLOR} fillOpacity={0.18} isAnimationActive={false} />
          <Area type="monotone" dataKey="fuelBand" stackId="lt" stroke="none" fill={FUEL_COLOR} fillOpacity={0.35} isAnimationActive={false} />
          <Area type="monotone" dataKey="tyreBand" stackId="lt" stroke="none" fill={TYRE_COLOR} fillOpacity={0.4} isAnimationActive={false} />

          {/* Observed range band (isotonic-fitted p10/p90 × M). */}
          <Line type="monotone" dataKey="netP10" stroke={HIST_COLOR} strokeWidth={1} strokeDasharray="2 3" dot={false} opacity={0.6} isAnimationActive={false} />
          <Line type="monotone" dataKey="netP90" stroke={HIST_COLOR} strokeWidth={1} strokeDasharray="2 3" dot={false} opacity={0.6} isAnimationActive={false} />

          {/* Net projected lap time. */}
          <Line type="monotone" dataKey="net" stroke={NET_COLOR} strokeWidth={2.5} dot={false} isAnimationActive={false} />

          <ReferenceLine x={result.currentLap} stroke="rgba(255,255,255,0.25)" strokeDasharray="4 4"
            label={{ value: 'current', position: 'top', fontSize: 10, fill: 'rgba(255,255,255,0.4)' }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

function Legend({ color, children, swatch, dashed }: { color: string; children: React.ReactNode; swatch?: boolean; dashed?: boolean }) {
  return (
    <div className="flex items-center gap-1.5 text-xs text-muted">
      {swatch
        ? <span className="w-8 h-3 inline-block rounded-sm" style={{ background: color, opacity: 0.4 }} />
        : <span className="w-8 h-0.5 inline-block" style={{ background: color, borderTop: dashed ? '2px dashed' : undefined }} />}
      {children}
    </div>
  )
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

const CLIFF_META: Record<string, { label: string; color: string }> = {
  '0_to_2': { label: 'Cliff imminent', color: '#f87171' },
  '3_to_5': { label: 'Cliff soon', color: '#fbbf24' },
  '6_plus': { label: 'Cliff distant', color: '#60a5fa' },
  none_in_stint: { label: 'No cliff in stint', color: '#34d399' },
}

// One instrument cell in the result readout: tiny uppercase label, a big value slot, optional sub.
function MetricCell({
  label, sub, emphasized, className, children,
}: { label: string; sub?: React.ReactNode; emphasized?: boolean; className?: string; children: React.ReactNode }) {
  return (
    <div
      className={[
        'flex flex-col rounded-xl border p-3.5',
        emphasized
          ? 'border-[rgb(var(--color-accent))]/30 bg-[rgb(var(--color-accent)/0.06)]'
          : 'border-border bg-white/[0.02]',
        className ?? '',
      ].join(' ')}
    >
      <span className="text-[10px] font-medium uppercase tracking-widest text-muted">{label}</span>
      <div className="mt-1.5 flex items-baseline leading-none">{children}</div>
      {sub && <span className="mt-1.5 text-[11px] leading-snug text-muted">{sub}</span>}
    </div>
  )
}

// The answer-first readout: projected lap time, live tyre cost, cliff status and remaining life,
// all reading the current-lap slice of the same SimulatorResult that drives the charts below.
function ResultHero({ result }: { result: SimulatorResult }) {
  const k = result.currentLap
  const point = result.laptimeCurve[k - 1]
  const cliffRaw = result.cliffBars[0]?.rawLabel ?? ''
  const cliff = CLIFF_META[cliffRaw] ?? { label: result.cliffLabel || ' ', color: '#94a3b8' }
  const cliffProb = result.cliffBars[0]?.prob ?? 0
  const life = result.remainingLifeLaps
  const lifeColor = life <= 3 ? '#f87171' : life <= 8 ? '#fbbf24' : '#34d399'

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {point ? (
        <>
          <MetricCell label="Projected lap time" emphasized
            sub={`@ lap ${k} of ${result.stintLength} · fresh ${point.ref.toFixed(2)}s`}>
            <span className="font-mono text-[26px] font-bold tabular-nums text-[rgb(var(--color-text))]">{point.net.toFixed(3)}</span>
            <span className="ml-1 text-sm text-muted">s</span>
          </MetricCell>
          <MetricCell label="Tyre degradation" sub={`fuel adds +${point.fuel.toFixed(2)}s on top`}>
            <span className="font-mono text-[26px] font-bold tabular-nums" style={{ color: TYRE_COLOR }}>+{point.tyre.toFixed(2)}</span>
            <span className="ml-1 text-sm text-muted">s</span>
          </MetricCell>
        </>
      ) : (
        <MetricCell label="Next-lap degradation" className="col-span-2" sub={`predicted jump at lap ${k}`}>
          <span className="font-mono text-[26px] font-bold tabular-nums" style={{ color: TYRE_COLOR }}>
            {result.currentJumpP50 >= 0 ? '+' : ''}{result.currentJumpP50.toFixed(3)}
          </span>
          <span className="ml-1 text-sm text-muted">s</span>
        </MetricCell>
      )}
      <MetricCell label="Cliff risk" sub={`${Math.round(cliffProb * 100)}% most likely`}>
        <span className="inline-flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: cliff.color }} aria-hidden />
          <span className="text-[17px] font-semibold leading-none" style={{ color: cliff.color }}>{cliff.label}</span>
        </span>
      </MetricCell>
      <MetricCell label="Remaining tyre life" sub="laps before retirement">
        <span className="font-mono text-[26px] font-bold tabular-nums" style={{ color: lifeColor }}>{life.toFixed(1)}</span>
        <span className="ml-1 text-sm text-muted">laps</span>
      </MetricCell>
    </div>
  )
}

// A titled chart panel: heading + an optional live metric on the right, then the chart body.
function ChartCard({ title, metric, children }: { title: string; metric?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-border bg-white/[0.02] p-4">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-semibold tracking-tight">{title}</h3>
        {metric && <span className="text-xs text-muted">{metric}</span>}
      </div>
      {children}
    </section>
  )
}

interface Props {
  result: SimulatorResult
}

export default function DegradationSimulatorChart({ result }: Props) {
  const hasLapTime = result.laptimeCurve.length > 0
  return (
    <div className="flex flex-col gap-4">
      <ResultHero result={result} />

      {hasLapTime && (
        <ChartCard
          title="Projected lap time across the stint"
          metric={<>at lap {result.currentLap}: <span className="font-mono text-[rgb(var(--color-text))]">{result.currentLapTime.toFixed(3)}s</span></>}
        >
          <LapTimeChart result={result} />
        </ChartCard>
      )}

      <ChartCard
        title="Predicted degradation jump across the stint"
        metric={(
          <>
            next-lap jump at lap {result.currentLap}:{' '}
            <span className="font-mono text-[rgb(var(--color-text))]">
              {result.currentJumpP50 >= 0 ? '+' : ''}{result.currentJumpP50.toFixed(3)}s
            </span>
          </>
        )}
      >
        <QuantileFanChart
          data={result.fan}
          xLabel="lap in stint"
          yLabel="deg %"
          xFormatter={v => `L${v}`}
          yFormatter={() => ''}
          xRef={result.currentLap}
          xRefLabel="current"
          reversed
        />
      </ChartCard>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-border bg-white/[0.02] p-4">
          <CliffBars result={result} />
        </div>
        <div className="rounded-xl border border-border bg-white/[0.02] p-4">
          <LifeGauge laps={result.remainingLifeLaps} />
        </div>
      </div>
    </div>
  )
}
