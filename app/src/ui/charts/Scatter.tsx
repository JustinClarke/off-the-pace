import { ReactNode } from 'react'
import {
  ScatterChart,
  Scatter as RechartsScatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
  TooltipProps,
} from 'recharts'

export interface ScatterPoint {
  x: number
  y: number
  /** Display label (driver code, constructor name, etc.) */
  label: string
  /** Dot fill colour */
  color?: string
  /** Any extra fields the caller wants in the tooltip payload */
  [key: string]: unknown
}

export interface ScatterProps {
  data: ScatterPoint[]
  xLabel?: string
  yLabel?: string
  xFormatter?: (v: number) => string
  yFormatter?: (v: number) => string
  /** Vertical reference line (e.g. median) */
  xRef?: number
  /** Horizontal reference line (e.g. median) */
  yRef?: number
  refLabel?: string
  height?: number
  /** Default dot colour when point.color is absent */
  defaultColor?: string
  /** Custom tooltip content. Receives the hovered point. */
  renderTooltip?: (point: ScatterPoint) => ReactNode
  /** Legend items rendered above the chart */
  legend?: Array<{ label: string; color: string }>
  /** Labelled grid below the chart (e.g. driver legend) */
  footnote?: ReactNode
}

const GRID = 'rgba(255,255,255,0.05)'
const AXIS_STYLE = { fontSize: 11, fill: 'rgb(var(--color-text-muted))' }
const REF_STYLE = { fontSize: 10, fill: 'rgba(255,255,255,0.3)' }

function DefaultTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload as ScatterPoint
  return (
    <div className="bg-[#13151a] border border-white/15 rounded px-3 py-2 text-xs shadow-xl">
      <p className="font-semibold mb-1">{d.label}</p>
      <p className="text-muted">
        x: <span className="font-mono text-[rgb(var(--color-text))]">{String(d.x)}</span>
      </p>
      <p className="text-muted">
        y: <span className="font-mono text-[rgb(var(--color-text))]">{String(d.y)}</span>
      </p>
    </div>
  )
}

function CustomTooltipWrapper({
  active,
  payload,
  renderTooltip,
}: TooltipProps<number, string> & { renderTooltip: (p: ScatterPoint) => ReactNode }) {
  if (!active || !payload?.length) return null
  return <>{renderTooltip(payload[0].payload as ScatterPoint)}</>
}

export default function Scatter({
  data,
  xLabel,
  yLabel,
  xFormatter = v => String(v),
  yFormatter = v => String(v),
  xRef,
  yRef,
  refLabel = 'median',
  height = 420,
  defaultColor = '#60a5fa',
  renderTooltip,
  legend,
  footnote,
}: ScatterProps) {
  return (
    <div className="w-full">
      {legend && legend.length > 0 && (
        <div className="flex flex-wrap gap-4 mb-4">
          {legend.map(item => (
            <div key={item.label} className="flex items-center gap-1.5 text-xs text-muted">
              <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: item.color }} />
              {item.label}
            </div>
          ))}
        </div>
      )}

      <ResponsiveContainer width="100%" height={height}>
        <ScatterChart margin={{ top: 20, right: 30, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis
            type="number"
            dataKey="x"
            name={xLabel}
            tickFormatter={xFormatter}
            label={xLabel ? { value: xLabel, position: 'insideBottom', offset: -10, fontSize: 11, fill: 'rgb(var(--color-text-muted))' } : undefined}
            tick={AXIS_STYLE}
          />
          <YAxis
            type="number"
            dataKey="y"
            name={yLabel}
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
          {xRef !== undefined && (
            <ReferenceLine
              x={xRef}
              stroke="rgba(255,255,255,0.15)"
              strokeDasharray="4 4"
              label={{ value: refLabel, position: 'top', ...REF_STYLE }}
            />
          )}
          {yRef !== undefined && (
            <ReferenceLine
              y={yRef}
              stroke="rgba(255,255,255,0.15)"
              strokeDasharray="4 4"
              label={{ value: refLabel, position: 'right', ...REF_STYLE }}
            />
          )}
          <RechartsScatter data={data} isAnimationActive={false}>
            {data.map((p, i) => (
              <Cell key={i} fill={p.color ?? defaultColor} fillOpacity={0.85} />
            ))}
          </RechartsScatter>
        </ScatterChart>
      </ResponsiveContainer>

      {footnote}
    </div>
  )
}
