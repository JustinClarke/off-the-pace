import { ReactNode } from 'react'
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  TooltipProps,
} from 'recharts'

export interface FanPoint {
  /** x-axis value lap number, time step, or any ordinal */
  x: number | string
  p10: number
  p50: number
  p90: number
  /** Optional: actual observed value overlaid as a separate line */
  actual?: number
}

export interface QuantileFanChartProps {
  data: FanPoint[]
  xLabel?: string
  yLabel?: string
  xFormatter?: (v: number | string) => string
  yFormatter?: (v: number) => string
  /** Colour of the p50 line and fan */
  color?: string
  /** Colour of the actual overlay line */
  actualColor?: string
  /** Vertical marker e.g. "current lap" or cliff prediction point */
  xRef?: number | string
  xRefLabel?: string
  height?: number
  renderTooltip?: (point: FanPoint) => ReactNode
}

const GRID = 'rgba(255,255,255,0.05)'
const AXIS_STYLE = { fontSize: 11, fill: 'rgb(var(--color-text-muted))' }

function DefaultTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload as FanPoint
  return (
    <div className="bg-[#13151a] border border-white/15 rounded px-3 py-2 text-xs shadow-xl">
      <p className="font-semibold mb-1">{String(d.x)}</p>
      <p className="text-muted">p50: <span className="font-mono text-[rgb(var(--color-text))]">{d.p50.toFixed(3)}</span></p>
      <p className="text-muted">p10–p90: <span className="font-mono text-[rgb(var(--color-text))]">[{d.p10.toFixed(3)}, {d.p90.toFixed(3)}]</span></p>
      {d.actual !== undefined && (
        <p className="text-muted">actual: <span className="font-mono text-[rgb(var(--color-text))]">{d.actual.toFixed(3)}</span></p>
      )}
    </div>
  )
}

function CustomTooltipWrapper({
  active,
  payload,
  renderTooltip,
}: TooltipProps<number, string> & { renderTooltip: (p: FanPoint) => ReactNode }) {
  if (!active || !payload?.length) return null
  return <>{renderTooltip(payload[0].payload as FanPoint)}</>
}

export default function QuantileFanChart({
  data,
  xLabel,
  yLabel,
  xFormatter = v => String(v),
  yFormatter = v => String(v),
  color = '#60a5fa',
  actualColor = '#f97316',
  xRef,
  xRefLabel,
  height = 380,
  renderTooltip,
}: QuantileFanChartProps) {
  // Recharts Area stacking for the fan:
  // Layer 1: transparent base from 0 to p10
  // Layer 2: opaque fan from p10 to p90 (delta)
  // Layer 3: p50 line on top
  const remapped = data.map(p => ({
    ...p,
    _p10base: p.p10,
    _fanDelta: p.p90-p.p10,
  }))

  const hasActual = data.some(p => p.actual !== undefined)

  return (
    <div className="w-full">
      {/* Quantile legend */}
      <div className="flex flex-wrap gap-4 mb-4">
        <div className="flex items-center gap-1.5 text-xs text-muted">
          <span className="w-8 h-0.5 inline-block" style={{ background: color }} />
          p50 (median)
        </div>
        <div className="flex items-center gap-1.5 text-xs text-muted">
          <span className="w-8 h-3 inline-block rounded-sm" style={{ background: color, opacity: 0.25 }} />
          p10–p90 band
        </div>
        {hasActual && (
          <div className="flex items-center gap-1.5 text-xs text-muted">
            <span className="w-8 h-0.5 inline-block" style={{ background: actualColor, borderTop: '2px dashed' }} />
            actual
          </div>
        )}
      </div>

      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={remapped} margin={{ top: 20, right: 30, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis
            dataKey="x"
            tickFormatter={xFormatter}
            label={xLabel ? { value: xLabel, position: 'insideBottom', offset: -10, fontSize: 11, fill: 'rgb(var(--color-text-muted))' } : undefined}
            tick={AXIS_STYLE}
          />
          <YAxis
            tickFormatter={yFormatter}
            label={yLabel ? { value: yLabel, angle: -90, position: 'insideLeft', offset: 10, fontSize: 11, fill: 'rgb(var(--color-text-muted))' } : undefined}
            tick={AXIS_STYLE}
          />
          <Tooltip
            content={
              renderTooltip
                ? (props: any) => <CustomTooltipWrapper {...props} renderTooltip={renderTooltip} />
                : (props: any) => <DefaultTooltip {...props} />
            }
          />

          {/* Transparent base to p10 */}
          <Area
            type="monotone"
            dataKey="_p10base"
            stroke="none"
            fill="transparent"
            legendType="none"
            isAnimationActive={false}
          />
          {/* Fan: p10 → p90 */}
          <Area
            type="monotone"
            dataKey="_fanDelta"
            stackId="fan"
            stroke="none"
            fill={color}
            fillOpacity={0.2}
            legendType="none"
            isAnimationActive={false}
          />

          {xRef !== undefined && (
            <ReferenceLine
              x={xRef}
              stroke="rgba(255,255,255,0.25)"
              strokeDasharray="4 4"
              label={{ value: xRefLabel ?? '', position: 'top', fontSize: 10, fill: 'rgba(255,255,255,0.4)' }}
            />
          )}

          {/* p50 median line */}
          <Line
            type="monotone"
            dataKey="p50"
            stroke={color}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />

          {/* Actual overlay */}
          {hasActual && (
            <Line
              type="monotone"
              dataKey="actual"
              stroke={actualColor}
              strokeWidth={1.5}
              strokeDasharray="4 2"
              dot={false}
              isAnimationActive={false}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
