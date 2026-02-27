import {
  ComposedChart,
  Line,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  TooltipProps,
} from 'recharts'

/** One point on the Kaplan-Meier survival step function */
export interface KMPoint {
  /** Lap-in-stint */
  lap: number
  /** Estimated survival probability [0,1]: P(no cliff onset before this lap) */
  survival: number
}

/** One actual-stint observation for the degradation overlay scatter */
export interface StintObservation {
  /** Lap-in-stint at which the stint ended (censored or event) */
  endLap: number
  /** True if a cliff onset was detected before the stint ended */
  cliffed: boolean
  /** Cumulative degradation (seconds) at stint end, relative to fresh baseline */
  degradation_s: number
  /** Driver code for tooltip */
  driver_id?: string
}

export interface SurvivalCurveProps {
  /** KM step function (sorted ascending by lap) */
  kmCurve: KMPoint[]
  /** Per-stint observations for the overlay scatter */
  stintObservations?: StintObservation[]
  /** Model median cliff onset (from dim_compounds_season)-shown as a vertical marker */
  cliffOnsetLap?: number
  /** Cliff severity (s of degradation jump at cliff)-for annotation */
  cliffSeverity?: number
  /** Fit provenance: ISO date */
  fitDate?: string
  /** Fit provenance: data window description */
  dataWindow?: string
  /** Fit provenance: number of stints used in fit (from notes field) */
  nStints?: number
  height?: number
}

const GRID = 'rgba(255,255,255,0.05)'
const AXIS_STYLE = { fontSize: 11, fill: 'rgb(var(--color-text-muted))' }
const KM_COLOR = '#60a5fa'
const CLIFFED_COLOR = '#f87171'
const CENSORED_COLOR = '#94a3b8'

function KMTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload as KMPoint | undefined
  if (!d || d.survival == null) return null
  return (
    <div className="bg-[#13151a] border border-white/15 rounded px-3 py-2 text-xs shadow-xl">
      <p className="font-semibold mb-1">Lap {d.lap} in stint</p>
      <p className="text-muted">
        Cliff-free:{' '}
        <span className="font-mono text-[rgb(var(--color-text))]">
          {(d.survival * 100).toFixed(1)}%
        </span>
      </p>
    </div>
  )
}

function ScatterTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload as StintObservation | undefined
  if (!d) return null
  return (
    <div className="bg-[#13151a] border border-white/15 rounded px-3 py-2 text-xs shadow-xl">
      {d.driver_id && <p className="font-semibold mb-1">{d.driver_id}</p>}
      <p className="text-muted">
        Stint length:{' '}
        <span className="font-mono text-[rgb(var(--color-text))]">{d.endLap} laps</span>
      </p>
      <p className="text-muted">
        Degradation:{' '}
        <span className="font-mono text-[rgb(var(--color-text))]">{d.degradation_s.toFixed(3)}s</span>
      </p>
      <p className="mt-1 font-medium" style={{ color: d.cliffed ? CLIFFED_COLOR : CENSORED_COLOR }}>
        {d.cliffed ? 'Cliff observed' : 'Censored (pitted)'}
      </p>
    </div>
  )
}

export default function SurvivalCurve({
  kmCurve,
  stintObservations = [],
  cliffOnsetLap,
  fitDate,
  dataWindow,
  nStints,
  height = 380,
}: SurvivalCurveProps) {
  const hasScatter = stintObservations.length > 0
  const cliffedObs = stintObservations.filter(s => s.cliffed)
  const censoredObs = stintObservations.filter(s => !s.cliffed)

  // Map observations to scatter data: x=lap (required by shared XAxis), y=degradation_s (right axis)
  const toScatterPoint = (s: StintObservation) => ({
    lap: s.endLap,
    endLap: s.endLap,
    degradation_s: s.degradation_s,
    driver_id: s.driver_id,
    cliffed: s.cliffed,
  })

  return (
    <div className="w-full">
      {/* Legend */}
      <div className="flex flex-wrap gap-4 mb-4">
        <div className="flex items-center gap-1.5 text-xs text-muted">
          <span className="w-8 h-0.5 inline-block" style={{ background: KM_COLOR }} />
          KM survival curve (left axis)
        </div>
        {hasScatter && (
          <>
            <div className="flex items-center gap-1.5 text-xs text-muted">
              <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: CLIFFED_COLOR, opacity: 0.75 }} />
              Cliff observed (right axis)
            </div>
            <div className="flex items-center gap-1.5 text-xs text-muted">
              <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ background: CENSORED_COLOR, opacity: 0.6 }} />
              Censored-pitted (right axis)
            </div>
          </>
        )}
        {cliffOnsetLap != null && (
          <div className="flex items-center gap-1.5 text-xs text-muted">
            <span className="w-8 h-px inline-block border-t border-dashed" style={{ borderColor: 'rgba(251,191,36,0.7)' }} />
            Model onset (lap {cliffOnsetLap})
          </div>
        )}
      </div>

      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart margin={{ top: 20, right: 60, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />

          <XAxis
            dataKey="lap"
            type="number"
            name="Lap in stint"
            domain={['dataMin', 'dataMax']}
            tickFormatter={v => String(v)}
            label={{ value: 'Lap in stint', position: 'insideBottom', offset: -10, fontSize: 11, fill: 'rgb(var(--color-text-muted))' }}
            tick={AXIS_STYLE}
            allowDuplicatedCategory={false}
          />

          {/* Left y-axis: KM survival probability */}
          <YAxis
            yAxisId="survival"
            domain={[0, 1]}
            tickFormatter={v => `${Math.round(v * 100)}%`}
            label={{ value: 'Cliff-free probability', angle: -90, position: 'insideLeft', offset: 10, fontSize: 11, fill: 'rgb(var(--color-text-muted))' }}
            tick={AXIS_STYLE}
          />

          {/* Right y-axis: degradation in seconds */}
          {hasScatter && (
            <YAxis
              yAxisId="degradation"
              orientation="right"
              tickFormatter={v => `+${v.toFixed(2)}s`}
              label={{ value: 'Degradation (s)', angle: 90, position: 'insideRight', offset: 10, fontSize: 11, fill: 'rgb(var(--color-text-muted))' }}
              tick={AXIS_STYLE}
            />
          )}

          <Tooltip content={(props: any) => {
            // Detect which series the hovered point belongs to by checking payload type
            const payload = props.payload
            if (!payload?.length) return null
            const first = payload[0]?.payload
            if (first && 'endLap' in first) return <ScatterTooltip {...props} />
            return <KMTooltip {...props} />
          }} />

          {cliffOnsetLap != null && (
            <ReferenceLine
              yAxisId="survival"
              x={cliffOnsetLap}
              stroke="rgba(251,191,36,0.7)"
              strokeDasharray="4 4"
              label={{ value: `onset ~lap ${cliffOnsetLap}`, position: 'insideTopRight', fontSize: 10, fill: 'rgba(251,191,36,0.85)' }}
            />
          )}

          {/* KM step function */}
          <Line
            yAxisId="survival"
            data={kmCurve}
            dataKey="survival"
            type="stepAfter"
            stroke={KM_COLOR}
            strokeWidth={2.5}
            dot={false}
            isAnimationActive={false}
            legendType="none"
          />

          {/* Cliffed stints scatter */}
          {hasScatter && cliffedObs.length > 0 && (
            <Scatter
              yAxisId="degradation"
              data={cliffedObs.map(toScatterPoint)}
              dataKey="degradation_s"
              name="cliffed"
              fill={CLIFFED_COLOR}
              fillOpacity={0.7}
              shape="circle"
              isAnimationActive={false}
              legendType="none"
            />
          )}

          {/* Censored stints scatter */}
          {hasScatter && censoredObs.length > 0 && (
            <Scatter
              yAxisId="degradation"
              data={censoredObs.map(toScatterPoint)}
              dataKey="degradation_s"
              name="censored"
              fill={CENSORED_COLOR}
              fillOpacity={0.5}
              shape="square"
              isAnimationActive={false}
              legendType="none"
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      {/* Fit provenance */}
      {(fitDate || dataWindow || nStints != null) && (
        <div className="flex flex-wrap gap-3 mt-3 text-xs text-muted/60">
          {fitDate && <span>Fit date: {fitDate}</span>}
          {dataWindow && <span>Window: {dataWindow}</span>}
          {nStints != null && <span>n = {nStints} stints</span>}
        </div>
      )}
    </div>
  )
}
