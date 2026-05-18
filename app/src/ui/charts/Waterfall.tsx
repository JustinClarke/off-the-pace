import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
  TooltipProps,
} from 'recharts'

export interface WaterfallBar {
  label: string
  value: number
  /** Running start offset for the floating bar illusion */
  start: number
  /** Positive component or negative component */
  sign: 'positive' | 'negative'
  color?: string
}

export interface WaterfallProps {
  /** Ordered bars caller computes start/sign from cumsum */
  bars: WaterfallBar[]
  /**
   * Closure check: difference between sum of components and the observed total.
   * Rendered as a coloured foot badge: green if |gap| < 1e-4, amber otherwise.
   */
  closureGap?: number
  xLabel?: string
  yLabel?: string
  /** Whether negative values are "bad" (cost) affects colour defaults */
  negativeIsBad?: boolean
}

const POS_COLOR = 'rgb(52, 211, 153)'   // emerald-400
const NEG_COLOR = 'rgb(248, 113, 113)'  // red-400

function CustomTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload as WaterfallBar
  return (
    <div className="bg-[rgb(var(--color-bg-elevated,28,28,32))] border border-border rounded px-3 py-2 text-xs shadow-lg">
      <p className="font-medium text-[rgb(var(--color-text))]">{d.label}</p>
      <p className="font-mono text-muted mt-0.5">
        {d.value >= 0 ? '+' : ''}{d.value.toFixed(4)} s
      </p>
    </div>
  )
}

/** Floating-bar waterfall built on a transparent + coloured two-layer bar stack. */
export default function Waterfall({
  bars,
  closureGap,
  xLabel,
  yLabel = 'Δ seconds',
}: WaterfallProps) {
  // Recharts stacked bar trick: first layer = transparent spacer (the `start` offset),
  // second layer = the actual value magnitude.
  const data = bars.map(b => ({
    ...b,
    spacer: b.start,
    magnitude: Math.abs(b.value),
  }))

  const allValues = bars.map(b => b.start + b.value).concat(bars.map(b => b.start))
  const yMin = Math.min(...allValues)
  const yMax = Math.max(...allValues)
  const pad = (yMax-yMin) * 0.12 || 0.05

  const hasClosureIssue = closureGap !== undefined && Math.abs(closureGap) >= 1e-4

  return (
    <div className="flex flex-col gap-3">
      <ResponsiveContainer width="100%" height={380}>
        <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 56 }} barCategoryGap="30%">
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: 'rgb(var(--color-text-muted, 140,140,160))' }}
            angle={-30}
            textAnchor="end"
            interval={0}
            label={xLabel ? { value: xLabel, position: 'insideBottom', offset: -16, style: { fontSize: 11 } } : undefined}
          />
          <YAxis
            tickFormatter={v => `${v >= 0 ? '+' : ''}${v.toFixed(2)}`}
            tick={{ fontSize: 11, fill: 'rgb(var(--color-text-muted, 140,140,160))' }}
            domain={[yMin-pad, yMax + pad]}
            label={yLabel ? { value: yLabel, angle: -90, position: 'insideLeft', style: { fontSize: 11 } } : undefined}
            width={56}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
          <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" strokeWidth={1} />

          {/* Transparent spacer lifts the coloured bar to the right starting position */}
          <Bar dataKey="spacer" stackId="waterfall" fill="transparent" isAnimationActive={false} />

          {/* Coloured magnitude bar */}
          <Bar dataKey="magnitude" stackId="waterfall" isAnimationActive={false} radius={[2, 2, 0, 0]}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.color ?? (entry.sign === 'negative' ? NEG_COLOR : POS_COLOR)}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Closure badge */}
      {closureGap !== undefined && (
        <div className="flex items-center gap-2 self-end text-xs font-mono">
          <span className="text-muted">closure check</span>
          <span
            className={`px-2 py-0.5 rounded border font-medium ${
              hasClosureIssue
                ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
            }`}
          >
            {hasClosureIssue
              ? `gap ${closureGap >= 0 ? '+' : ''}${closureGap.toFixed(6)} s ⚠`
              : `✓ closed (${closureGap.toFixed(6)} s)`}
          </span>
        </div>
      )}
    </div>
  )
}
