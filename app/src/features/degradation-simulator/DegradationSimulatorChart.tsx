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
import { TechTooltip } from '../../ui/TechTooltip'

const GRID = 'rgba(255,255,255,0.05)'
const AXIS_STYLE = { fontSize: 11, fill: 'rgb(var(--color-text-muted))' }
const REF_COLOR = '#475569'
const FUEL_COLOR = '#38bdf8'
const NET_COLOR = '#e2e8f0'
const HIST_COLOR = '#a78bfa'
const CLIFF_LINE_COLOR = '#fb7185'

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
      <p className="text-muted">+ Tyre (isotonic deg): <span className="font-mono" style={{ color: payload[0]?.payload?.tyreColor ?? '#f59e0b' }}>{d.tyreBand.toFixed(3)}s</span></p>
    </div>
  )
}

function LapTimeChart({ result, tyreColor }: { result: SimulatorResult; tyreColor: string }) {
  const curve = result.laptimeCurve
  const onset = result.cliffOnsetLap

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
    tyreColor,
  }))

  return (
    <div className="w-full">
      <div className="flex flex-wrap gap-4 mb-3">
        <Legend color={REF_COLOR} swatch tooltip="Baseline pace on fresh tyres, adjusted for circuit layout and car capabilities.">Fresh-tyre anchor</Legend>
        <Legend color={FUEL_COLOR} swatch tooltip="Additional lap time due to fuel weight. Decreases as fuel burns off (typically ~0.06s per lap).">Fuel</Legend>
        <Legend color={tyreColor} swatch tooltip="Additional lap time due to tyre wear. Modelled using isotonic regression on historical stints.">Tyre degradation</Legend>
        <Legend color={NET_COLOR} tooltip="The sum of fresh-tyre anchor + fuel weight + tyre degradation.">Projected lap time</Legend>
        {result.laptimeCurve.some(p => p.p10 !== p.net) && <Legend color={HIST_COLOR} dashed tooltip="The 10th to 90th percentile of historical degradation observed for this compound at this circuit.">Observed range</Legend>}
        {onset > 0 && onset <= curve.length && <Legend color={CLIFF_LINE_COLOR} dashed tooltip="The lap when degradation begins accelerating rapidly (Kaplan-Meier survival baseline).">Cliff onset</Legend>}
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
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any -- recharts <Tooltip content> render-prop is typed `any` upstream */}
          <Tooltip content={(props: any) => <LapTimeTooltip {...props} />} />

          {/* Stacked decomposition: invisible base (floor→ref), fuel, then tyre (top edge = net). */}
          <Area type="monotone" dataKey="refBase" stackId="lt" stroke="none" fill={REF_COLOR} fillOpacity={0.18} isAnimationActive={false} />
          <Area type="monotone" dataKey="fuelBand" stackId="lt" stroke="none" fill={FUEL_COLOR} fillOpacity={0.35} isAnimationActive={false} />
          <Area type="monotone" dataKey="tyreBand" stackId="lt" stroke="none" fill={tyreColor} fillOpacity={0.4} isAnimationActive={false} />

          {/* Observed range band (isotonic-fitted p10/p90 × M). */}
          <Line type="monotone" dataKey="netP10" stroke={HIST_COLOR} strokeWidth={1} strokeDasharray="2 3" dot={false} opacity={0.6} isAnimationActive={false} />
          <Line type="monotone" dataKey="netP90" stroke={HIST_COLOR} strokeWidth={1} strokeDasharray="2 3" dot={false} opacity={0.6} isAnimationActive={false} />

          {/* Net projected lap time. */}
          <Line type="monotone" dataKey="net" stroke={NET_COLOR} strokeWidth={2.5} dot={false} isAnimationActive={false} />

          {/* Cliff-onset reference: where the convex tyre extrapolation begins to bite. */}
          {onset > 0 && onset <= curve.length && (
            <ReferenceLine x={Math.round(onset)} stroke={CLIFF_LINE_COLOR} strokeDasharray="5 3"
              label={{ value: 'cliff onset', position: 'top', fontSize: 10, fill: CLIFF_LINE_COLOR }} />
          )}
          <ReferenceLine x={result.currentLap} stroke="rgba(255,255,255,0.25)" strokeDasharray="4 4"
            label={{ value: 'current', position: 'top', fontSize: 10, fill: 'rgba(255,255,255,0.4)' }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

function Legend({ color, children, swatch, dashed, tooltip }: { color: string; children: React.ReactNode; swatch?: boolean; dashed?: boolean; tooltip?: string }) {
  const inner = (
    <div className={`flex items-center gap-1.5 text-xs text-muted ${tooltip ? 'cursor-help' : ''}`}>
      {swatch
        ? <span className="w-8 h-3 inline-block rounded-sm" style={{ background: color, opacity: 0.4 }} />
        : <span className="w-8 h-0.5 inline-block" style={{ background: color, borderTop: dashed ? '2px dashed' : undefined }} />}
      {children}
    </div>
  )
  
  if (tooltip) {
    return <TechTooltip content={tooltip}>{inner}</TechTooltip>
  }
  return inner
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

const LIFE_HORIZON_LAPS = 40

/**
 * Urgency colour is taken from p10, not the median: "how soon could this tyre be
 * done" is the decision the colour is used for, and the pessimistic end of the
 * fitted distribution is the honest answer to it. Colouring the median would let a
 * wide, uncertain fit read as calmly green.
 */
function lifeColorFrom(p10: number): string {
  return p10 <= 3 ? '#f87171' : p10 <= 8 ? '#fbbf24' : '#34d399'
}

/**
 * Remaining stint life as a median against its 10th-90th percentile band.
 *
 * The model is an AFT survival fit, so what it yields is a log-normal median, not a
 * conditional mean. It used to be rendered to one decimal place against a
 * three-colour band, which overclaimed twice over: 46% of the rows it was fitted on
 * are right-censored (the race ended before the tyre did), and a tenth of a lap is
 * far finer than a censored fit can resolve. The median is now shown to the lap,
 * and the band is shown next to it rather than left implicit.
 */
function LifeGauge({ median, p10, p90 }: { median: number; p10: number; p90: number }) {
  const color = lifeColorFrom(p10)
  const pos = (v: number) => Math.max(0, Math.min(100, (v / LIFE_HORIZON_LAPS) * 100))
  const left = pos(p10)
  const width = Math.max(1.5, pos(p90) - left)   // keep a hairline visible when p10≈p90
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold">Remaining stint life</h3>
      <div className="flex items-end gap-2">
        <span className="text-4xl font-bold tabular-nums" style={{ color }}>{Math.round(median)}</span>
        <span className="text-sm text-muted mb-1">laps (median)</span>
      </div>
      <div className="relative h-2.5 rounded-full bg-white/5 overflow-hidden">
        <div
          className="absolute inset-y-0 rounded-full transition-all"
          style={{ left: `${left}%`, width: `${width}%`, background: color, opacity: 0.45 }}
        />
        <div
          className="absolute inset-y-0 w-[2px] transition-all"
          style={{ left: `${pos(median)}%`, background: color }}
        />
      </div>
      <div className="flex justify-between text-[11px] tabular-nums text-muted/70">
        <span>p10 {Math.round(p10)}</span>
        <span>p90 {Math.round(p90)}</span>
      </div>
      <p className="text-xs text-muted/70">
        Log-normal AFT median, with the 10th-90th percentile of the same fitted
        distribution. Right-censored stints (the race ended before the tyre did) are
        fitted as "at least this long", not as observed retirements.
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

// The answer-first readout: projected lap time (always present the curve no longer depends on
// ONNX), the live tyre cost, the physical laps-to-cliff, plus the ONNX cliff status and remaining
// life. All read the current-lap slice of the same SimulatorResult that drives the charts below.
function ResultHero({ result, onnxReady, tyreColor }: { result: SimulatorResult; onnxReady: boolean; tyreColor: string }) {
  const k = result.currentLap
  const point = result.laptimeCurve[k - 1]
  const cliffRaw = result.cliffBars[0]?.rawLabel ?? ''
  const cliff = CLIFF_META[cliffRaw] ?? { label: result.cliffLabel || ' ', color: '#94a3b8' }
  const cliffProb = result.cliffBars[0]?.prob ?? 0
  const life = result.remainingLifeLaps
  const lifeP10 = result.remainingLifeP10
  const lifeP90 = result.remainingLifeP90
  const lifeColor = lifeColorFrom(lifeP10)

  // Physical laps-to-cliff from the headline model (responsive to every slider; independent of ONNX).
  const onset = result.cliffOnsetLap
  const toCliff = onset > 0 ? Math.round(onset - k) : null
  const cliffColor = toCliff === null ? '#94a3b8' : toCliff <= 2 ? '#f87171' : toCliff <= 6 ? '#fbbf24' : '#34d399'

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
      <MetricCell label="Projected lap time" emphasized
        sub={point ? `@ lap ${k} of ${result.stintLength} · fresh ${point.ref.toFixed(2)}s` : 'select a circuit'}>
        <span className="font-mono text-[26px] font-bold tabular-nums text-[rgb(var(--color-text))]">
          {point ? point.net.toFixed(3) : ' '}
        </span>
        {point && <span className="ml-1 text-sm text-muted">s</span>}
      </MetricCell>
      <MetricCell label="Tyre degradation" sub={point ? `fuel adds +${point.fuel.toFixed(2)}s on top` : 'cumulative from fresh'}>
        <span className="font-mono text-[26px] font-bold tabular-nums" style={{ color: tyreColor }}>
          {point ? `+${point.tyre.toFixed(2)}` : ' '}
        </span>
        {point && <span className="ml-1 text-sm text-muted">s</span>}
      </MetricCell>
      <MetricCell label="Laps to cliff" sub={onset > 0 ? `onset ~lap ${Math.round(onset)} of stint` : 'no fitted cliff'}>
        <span className="font-mono text-[26px] font-bold tabular-nums" style={{ color: cliffColor }}>
          {toCliff === null ? ' ' : toCliff <= 0 ? 'past' : toCliff}
        </span>
        {toCliff !== null && toCliff > 0 && <span className="ml-1 text-sm text-muted">laps</span>}
      </MetricCell>
      <MetricCell label="Cliff risk" sub={onnxReady ? `${Math.round(cliffProb * 100)}% most likely` : 'model offline'}>
        <span className="inline-flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: onnxReady ? cliff.color : '#475569' }} aria-hidden />
          <span className="text-[17px] font-semibold leading-none" style={{ color: onnxReady ? cliff.color : '#64748b' }}>
            {onnxReady ? cliff.label : ' '}
          </span>
        </span>
      </MetricCell>
      <MetricCell
        label="Remaining tyre life"
        sub={onnxReady ? `median · p10-p90 ${Math.round(lifeP10)}-${Math.round(lifeP90)}` : 'model offline'}
      >
        <span className="font-mono text-[26px] font-bold tabular-nums" style={{ color: onnxReady ? lifeColor : '#64748b' }}>
          {onnxReady ? Math.round(life) : ' '}
        </span>
        {onnxReady && <span className="ml-1 text-sm text-muted">laps</span>}
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

// A small placeholder shown in an ONNX-driven panel when the trained models are loading or offline,
// so a slow/failed/404 inference degrades the panel gracefully instead of blanking it. The headline
// (which never depends on ONNX) stays live regardless.
function OnnxNote({ error, loading }: { error?: Error | null; loading?: boolean }) {
  const isLoading = !error && loading
  return (
    <div className="flex h-[120px] flex-col items-center justify-center gap-1 text-center">
      <span className="text-sm font-medium text-muted">
        {isLoading ? 'Loading trained model…' : 'Trained model offline'}
      </span>
      <span className="text-xs text-muted/60">
        {isLoading ? 'onnxruntime-web is scoring in your browser.' : 'The projected lap time above is unaffected.'}
      </span>
    </div>
  )
}

// The current-lap playhead. current_lap is NOT a model feature (see inputs.ts) it only positions
// the "current" marker the hero/cliff bars read so it lives here on the chart as a scrubber rather
// than as a slider in the input rail. Left padding roughly tracks the chart's y-axis gutter so the
// thumb reads against the plotted laps.
function LapScrubber({ current, stintLength, onChange }: {
  current: number; stintLength: number; onChange: (lap: number) => void
}) {
  return (
    <div className="mt-1 flex items-center gap-3 pl-[60px] pr-[30px]">
      <span className="shrink-0 text-[11px] text-muted">Current lap</span>
      <input
        type="range"
        min={1}
        max={Math.max(1, stintLength)}
        step={1}
        value={Math.min(current, stintLength)}
        onChange={e => onChange(Number(e.target.value))}
        aria-label="Current lap in stint"
        className="w-full cursor-pointer accent-[rgb(var(--color-accent))]"
      />
      <span className="shrink-0 rounded bg-white/[0.05] px-1.5 py-0.5 font-mono text-[11px] tabular-nums text-[rgb(var(--color-text))]">
        L{Math.min(current, stintLength)} / {stintLength}
      </span>
    </div>
  )
}

interface Props {
  result: SimulatorResult
  /** ONNX inference is still running and has produced no predictions yet. */
  onnxLoading?: boolean
  /** ONNX inference failed (slow / 404 / runtime error). */
  onnxError?: Error | null
  /** Move the current-lap playhead (drives the hero readout + cliff/jump markers). */
  onCurrentLapChange?: (lap: number) => void
  tyreColor?: string
}

export default function DegradationSimulatorChart({ result, onnxLoading, onnxError, onCurrentLapChange, tyreColor = '#f59e0b' }: Props) {
  const hasLapTime = result.laptimeCurve.length > 0
  const onnxReady = result.fan.length > 0 && !onnxError

  return (
    <div className="flex flex-col gap-4">
      <ResultHero result={result} onnxReady={onnxReady} tyreColor={tyreColor} />

      {hasLapTime && (
        <ChartCard
          title="Projected lap time across the stint"
          metric={<>at lap {result.currentLap}: <span className="font-mono text-[rgb(var(--color-text))]">{result.currentLapTime.toFixed(3)}s</span></>}
        >
          <LapTimeChart result={result} tyreColor={tyreColor} />
          {onCurrentLapChange && result.stintLength > 1 && (
            <LapScrubber current={result.currentLap} stintLength={result.stintLength} onChange={onCurrentLapChange} />
          )}
        </ChartCard>
      )}

      <ChartCard
        title="Predicted degradation jump across the stint"
        metric={onnxReady ? (
          <>
            next-lap jump at lap {result.currentLap}:{' '}
            <span className="font-mono text-[rgb(var(--color-text))]">
              {result.currentJumpP50 >= 0 ? '+' : ''}{result.currentJumpP50.toFixed(3)}s
            </span>
          </>
        ) : undefined}
      >
        {onnxReady ? (
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
        ) : (
          <OnnxNote error={onnxError} loading={onnxLoading} />
        )}
      </ChartCard>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-border bg-white/[0.02] p-4">
          {onnxReady ? <CliffBars result={result} /> : <OnnxNote error={onnxError} loading={onnxLoading} />}
        </div>
        <div className="rounded-xl border border-border bg-white/[0.02] p-4">
          {onnxReady
            ? <LifeGauge median={result.remainingLifeLaps} p10={result.remainingLifeP10} p90={result.remainingLifeP90} />
            : <OnnxNote error={onnxError} loading={onnxLoading} />}
        </div>
      </div>
    </div>
  )
}
