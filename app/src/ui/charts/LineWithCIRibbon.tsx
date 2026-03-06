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
  ReferenceArea,
  ResponsiveContainer,
  TooltipProps,
  Legend,
} from 'recharts'

export interface CIPoint {
  /** x-axis value number or string (e.g. year, race round) */
  x: number | string
  /** Central estimate */
  y: number
  /** Lower CI bound */
  lo: number
  /** Upper CI bound */
  hi: number
  /** Optional secondary series value */
  y2?: number
}

export interface EraMarker {
  /** x value at which the era boundary falls */
  x: number | string
  label: string
}

export interface AnnotationPoint {
  x: number | string
  label: string
}

export interface LineWithCIRibbonProps {
  data: CIPoint[]
  xLabel?: string
  yLabel?: string
  seriesLabel?: string
  secondaryLabel?: string
  xFormatter?: (v: number | string) => string
  yFormatter?: (v: number) => string
  /** Colour of the primary line + ribbon */
  color?: string
  secondaryColor?: string
  /** Shaded era bands */
  eraMarkers?: EraMarker[]
  /** Point annotations (driver labels, notable events) */
  annotations?: AnnotationPoint[]
  height?: number
  renderTooltip?: (point: CIPoint) => ReactNode
}

const GRID = 'rgba(255,255,255,0.05)'
const AXIS_STYLE = { fontSize: 11, fill: 'rgb(var(--color-text-muted))' }

function DefaultTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload as CIPoint
  return (
    <div className="bg-[#13151a] border border-white/15 rounded px-3 py-2 text-xs shadow-xl">
      <p className="font-semibold mb-1">{String(d.x)}</p>
      <p className="text-muted">
        value: <span className="font-mono text-[rgb(var(--color-text))]">{d.y.toFixed(3)}</span>
      </p>
      {d.lo !== undefined && (
        <p className="text-muted">
          CI: <span className="font-mono text-[rgb(var(--color-text))]">[{d.lo.toFixed(3)}, {d.hi.toFixed(3)}]</span>
        </p>
      )}
    </div>
  )
}

function CustomTooltipWrapper({
  active,
  payload,
  renderTooltip,
}: TooltipProps<number, string> & { renderTooltip: (p: CIPoint) => ReactNode }) {
  if (!active || !payload?.length) return null
  return <>{renderTooltip(payload[0].payload as CIPoint)}</>
}

export default function LineWithCIRibbon({
  data,
  xLabel,
  yLabel,
  seriesLabel = 'value',
  secondaryLabel,
  xFormatter = v => String(v),
  yFormatter = v => String(v),
  color = '#60a5fa',
  secondaryColor = '#f97316',
  eraMarkers,
  height = 380,
  renderTooltip,
}: LineWithCIRibbonProps) {
  const ribbonColor = color

  // Recharts Area needs [lo, hi] encoded as [base, delta] via its own stacking,
  // but it's cleaner to pass hi directly and use lo as the baseline.
  // We remap to {x, loHi: [lo, hi]} shape Recharts Area with baseValue not supported cleanly,
  // so we use two Areas stacked: a transparent base up to lo, then the ribbon from lo to hi.
  const remapped = data.map(p => ({
    ...p,
    _ciLo: p.lo,
    _ciDelta: p.hi-p.lo,
  }))

  const hasSecondary = data.some(p => p.y2 !== undefined)

  return (
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
        {(hasSecondary || eraMarkers?.length) && <Legend wrapperStyle={{ fontSize: 11 }} />}

        {/* CI ribbon: transparent base up to lo, then coloured delta */}
        <Area
          type="monotone"
          dataKey="_ciLo"
          stroke="none"
          fill="transparent"
          legendType="none"
          isAnimationActive={false}
        />
        <Area
          type="monotone"
          dataKey="_ciDelta"
          stackId="ci"
          stroke="none"
          fill={ribbonColor}
          fillOpacity={0.15}
          legendType="none"
          isAnimationActive={false}
        />

        {/* Era boundary markers */}
        {eraMarkers?.map(e => (
          <ReferenceLine
            key={String(e.x)}
            x={e.x}
            stroke="rgba(255,255,255,0.2)"
            strokeDasharray="6 3"
            label={{ value: e.label, position: 'top', fontSize: 10, fill: 'rgba(255,255,255,0.4)' }}
          />
        ))}

        {/* Primary line */}
        <Line
          type="monotone"
          dataKey="y"
          name={seriesLabel}
          stroke={color}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />

        {/* Optional secondary series */}
        {hasSecondary && (
          <Line
            type="monotone"
            dataKey="y2"
            name={secondaryLabel ?? 'secondary'}
            stroke={secondaryColor}
            strokeWidth={2}
            strokeDasharray="4 2"
            dot={false}
            isAnimationActive={false}
          />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  )
}

/** Convenience: shade a region between two x values (e.g. a regulation era) */
export function EraRegion({ x1, x2, label }: { x1: number | string; x2: number | string; label?: string }) {
  return (
    <ReferenceArea
      x1={x1}
      x2={x2}
      fill="rgba(255,255,255,0.03)"
      label={label ? { value: label, fontSize: 10, fill: 'rgba(255,255,255,0.3)' } : undefined}
    />
  )
}
