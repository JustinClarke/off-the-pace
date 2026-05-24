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
  Legend,
} from 'recharts'
import type { DriverSeries } from './transform'

const GRID = 'rgba(255,255,255,0.05)'
const AXIS_STYLE = { fontSize: 11, fill: 'rgb(var(--color-text-muted))' }

interface Props {
  series: DriverSeries[]
  selected: string[]
  showCIRibbons: boolean
  /** Full dataset season window, so the axis is stable across selections */
  seasonRange: [number, number]
  /** driver_id -> stable line colour, computed once by the page */
  colorOf: (driverId: string) => string
  /** Driver hovered in the career-span timeline; its line is emphasised here */
  emphasised?: string | null
}

interface ChartRow {
  season: number
  [key: string]: number | undefined
}

export default function EraRatingsTimelineChart({ series, selected, showCIRibbons, seasonRange, colorOf, emphasised }: Props) {
  const selectedSeries = series.filter(s => selected.includes(s.driver_id))

  // One row per season across the full dataset window, so the axis stays put
  // and every year gets a tick regardless of which drivers are selected.
  const [first, last] = seasonRange
  const seasons = Array.from({ length: last - first + 1 }, (_, i) => first + i)

  const chartData: ChartRow[] = seasons.map(season => {
    const row: ChartRow = { season }
    for (const s of selectedSeries) {
      const pt = s.points.find(p => p.x === season)
      if (pt) {
        row[s.driver_id] = pt.y
        row[`${s.driver_id}_lo`] = pt.lo
        row[`${s.driver_id}_hi`] = pt.hi
        // Recharts stacked Area needs delta (hi - lo) not absolute hi
        row[`${s.driver_id}_delta`] = (pt.hi as number) - (pt.lo as number)
      }
    }
    return row
  })

  const yFormatter = (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(2)}s`

  return (
    <ResponsiveContainer width="100%" height={440}>
      <ComposedChart data={chartData} margin={{ top: 16, right: 36, bottom: 48, left: 24 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
        <XAxis
          dataKey="season"
          type="number"
          scale="linear"
          domain={[seasons[0], seasons[seasons.length - 1]]}
          ticks={seasons}
          interval={0}
          allowDecimals={false}
          tickFormatter={v => String(v)}
          tick={AXIS_STYLE}
          tickMargin={8}
          padding={{ left: 12, right: 12 }}
        />
        <YAxis
          tickFormatter={yFormatter}
          tick={AXIS_STYLE}
          label={{ value: 'era-adjusted rating (s)', angle: -90, position: 'insideLeft', offset: 14, fontSize: 11, fill: 'rgb(var(--color-text-muted))' }}
        />
        <Tooltip
          cursor={{ stroke: 'rgba(255,255,255,0.2)', strokeWidth: 1 }}
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null
            const rows = payload
              .filter(p => !String(p.dataKey).includes('_lo') && !String(p.dataKey).includes('_delta'))
              // fastest (most negative) first
              .sort((a, b) => (a.value as number) - (b.value as number))
            return (
              <div
                className="rounded-lg border border-border px-3 py-2.5 text-xs shadow-xl"
                style={{ backgroundColor: 'rgb(var(--color-bg))' }}
              >
                <p className="font-semibold mb-2 text-[rgb(var(--color-text))]">{label}</p>
                <div className="grid grid-cols-[auto_auto_auto] gap-x-2.5 gap-y-1 items-baseline">
                  {rows.map(p => {
                    const driver = String(p.dataKey)
                    const row = p.payload as ChartRow
                    const lo = row[`${driver}_lo`]
                    const hi = row[`${driver}_hi`]
                    return (
                      <div key={driver} className="contents">
                        <span className="font-mono font-semibold" style={{ color: p.color }}>{driver}</span>
                        <span className="font-mono tabular-nums text-right text-[rgb(var(--color-text))]">
                          {yFormatter(p.value as number)}
                        </span>
                        <span className="font-mono tabular-nums text-muted/60 text-[10px]">
                          {lo !== undefined && hi !== undefined ? `[${yFormatter(lo)}, ${yFormatter(hi)}]` : ''}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          }}
        />
        <Legend
          wrapperStyle={{ fontSize: 11, paddingTop: 16 }}
          iconType="plainline"
        />

        {/* 2022 era boundary */}
        <ReferenceLine
          x={2022}
          stroke="rgba(255,255,255,0.2)"
          strokeDasharray="6 3"
          label={{ value: '2022 regs', position: 'top', fontSize: 10, fill: 'rgba(255,255,255,0.4)' }}
        />

        {selectedSeries.map(s => {
          const color = colorOf(s.driver_id)
          // When a lane is hovered, fade everything except that driver.
          const isEmph = emphasised === s.driver_id
          const dimmed = emphasised != null && !isEmph
          const baseWidth = s.isBridgeDriver ? 2.5 : 2
          return [
            // CI ribbon: transparent base up to lo, then coloured delta
            showCIRibbons && (
              <Area
                key={`${s.driver_id}_lo`}
                type="monotone"
                dataKey={`${s.driver_id}_lo`}
                stroke="none"
                fill="transparent"
                legendType="none"
                isAnimationActive={false}
                connectNulls
              />
            ),
            showCIRibbons && (
              <Area
                key={`${s.driver_id}_delta`}
                type="monotone"
                dataKey={`${s.driver_id}_delta`}
                stackId={`ci_${s.driver_id}`}
                stroke="none"
                fill={color}
                fillOpacity={dimmed ? 0.04 : 0.12}
                legendType="none"
                isAnimationActive={false}
                connectNulls
              />
            ),
            <Line
              key={s.driver_id}
              type="monotone"
              dataKey={s.driver_id}
              name={s.driver_id}
              stroke={color}
              strokeOpacity={dimmed ? 0.2 : 1}
              strokeWidth={isEmph ? baseWidth + 1.5 : baseWidth}
              strokeDasharray={s.isBridgeDriver ? undefined : '4 2'}
              dot={{ r: isEmph ? 4 : 3, fill: color, strokeWidth: 0, fillOpacity: dimmed ? 0.2 : 1 }}
              activeDot={{ r: 5 }}
              isAnimationActive={false}
              connectNulls
            />,
          ]
        })}
      </ComposedChart>
    </ResponsiveContainer>
  )
}
