// AX-11: renders a stored chart description. Title, labels and series names are React text children (never HTML).
// Text alternative: a visually hidden table of the plotted points.
import { LineChart, Line, BarChart, Bar, ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { tokens } from '../../ui/tokens'
import { ErrorBoundary } from '../../ui/feedback/ErrorBoundary'
import { getChart, type StoredChart } from './chartStore'

const PALETTE = [tokens.color.fuel, tokens.color.dirty_air, tokens.color.driver_skill, tokens.color.traffic, tokens.color.pitstop, tokens.color.tyre_cliff]

/** Merge series into one row per x so line and bar charts share an axis. */
function mergeSeries(chart: StoredChart): Record<string, number | string>[] {
  const byX = new Map<string | number, Record<string, number | string>>()
  chart.series.forEach((s, i) => {
    for (const p of s.points) {
      const row = byX.get(p.x) ?? { x: p.x }
      row[`s${i}`] = p.y
      byX.set(p.x, row)
    }
  })
  const rows = [...byX.values()]
  return rows.sort((a, b) => (typeof a.x === 'number' && typeof b.x === 'number' ? a.x - b.x : 0))
}

const AXIS = { fontSize: 11, fill: 'rgb(var(--color-text-muted))' }

function Plot({ chart }: { chart: StoredChart }) {
  const { spec } = chart
  const common = { margin: { top: 10, right: 20, bottom: 24, left: 10 } }
  const xAxis = <XAxis dataKey="x" tick={AXIS} label={{ value: spec.x.label, position: 'insideBottom', offset: -12, ...AXIS }} />
  const yAxis = <YAxis tick={AXIS} domain={['auto', 'auto']} label={{ value: spec.y.label, angle: -90, position: 'insideLeft', ...AXIS }} />
  if (spec.type === 'scatter') {
    return (
      <ScatterChart {...common}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
        <XAxis type="number" dataKey="x" tick={AXIS} name={spec.x.label} domain={['auto', 'auto']} />
        <YAxis type="number" dataKey="y" tick={AXIS} name={spec.y.label} domain={['auto', 'auto']} />
        <Tooltip />
        <Legend />
        {chart.series.map((s, i) => (
          <Scatter key={i} name={s.label} data={s.points} fill={PALETTE[i % PALETTE.length]} />
        ))}
      </ScatterChart>
    )
  }
  const rows = mergeSeries(chart)
  if (spec.type === 'bar') {
    return (
      <BarChart data={rows} {...common}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
        {xAxis}
        {yAxis}
        <Tooltip />
        <Legend />
        {chart.series.map((s, i) => (
          <Bar key={i} dataKey={`s${i}`} name={s.label} fill={PALETTE[i % PALETTE.length]} />
        ))}
      </BarChart>
    )
  }
  return (
    <LineChart data={rows} {...common}>
      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
      {xAxis}
      {yAxis}
      <Tooltip />
      <Legend />
      {chart.series.map((s, i) => (
        <Line key={i} type="monotone" dataKey={`s${i}`} name={s.label} stroke={PALETTE[i % PALETTE.length]} dot={false} connectNulls={false} />
      ))}
    </LineChart>
  )
}

export function ChartCardView({ chart, height = 320 }: { chart: StoredChart; height?: number }) {
  return (
    <figure className="rounded border border-white/10 p-3" aria-label={chart.spec.title}>
      <figcaption className="mb-2 text-sm font-medium">{chart.spec.title}</figcaption>
      <ErrorBoundary>
        <ResponsiveContainer width="100%" height={height}>
          <Plot chart={chart} />
        </ResponsiveContainer>
      </ErrorBoundary>
      <p className="mt-2 text-xs text-muted">
        <span>computed_not_card</span>
        {' · '}
        {chart.series.map((s, i) => (
          <span key={i}>
            {i > 0 ? ', ' : ''}
            {s.label}: n = {chart.n[i]}
          </span>
        ))}
        {chart.note ? ` · ${chart.note}` : ''}
      </p>
      <table className="sr-only">
        <caption>{chart.spec.title}: plotted points</caption>
        <thead>
          <tr>
            <th scope="col">Series</th>
            <th scope="col">{chart.spec.x.label}</th>
            <th scope="col">{chart.spec.y.label}</th>
          </tr>
        </thead>
        <tbody>
          {chart.series.flatMap((s, i) =>
            s.points.map((p, j) => (
              <tr key={`${i}-${j}`}>
                <td>{s.label}</td>
                <td>{p.x}</td>
                <td>{p.y}</td>
              </tr>
            )),
          )}
        </tbody>
      </table>
    </figure>
  )
}

/** Looks the chart up by id (the model-facing result carries only the id). */
export default function ChartCard({ chartId }: { chartId: string }) {
  const chart = getChart(chartId)
  if (!chart) return <p className="text-xs text-muted">Chart no longer available in this session.</p>
  return <ChartCardView chart={chart} />
}
