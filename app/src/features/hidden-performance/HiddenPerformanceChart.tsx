import RankedTable from '../../ui/charts/RankedTable'
import type { HiddenPerformanceEntry, SeasonEntry } from './transform'

const fmtDelta = (d: number) => (d > 0 ? `+${d.toFixed(1)}` : d.toFixed(1))
const fmtAdj = (d: number | null) => d == null ? ' ' : (d > 0 ? `+${d.toFixed(1)}` : d.toFixed(1))
const fmtConf = (c: number) => `${(c * 100).toFixed(0)}%`
const fmtSe = (se: number) => `±${se.toFixed(1)}`
const fmtRating = (r: number | null) => r == null ? ' ' : r.toFixed(3)
const fmtAffinity = (s: number | null, conf: number | null) => {
  if (s == null) return ' '
  const arrow = s < -0.2 ? '▲' : s > 0.2 ? '▼' : '~'
  const label = `${arrow} ${Math.abs(s).toFixed(2)}s`
  return conf != null && conf < 0.4 ? `${label}*` : label
}

function DeltaCell({ delta }: { delta: number }) {
  const cls = delta < 0 ? 'text-emerald-400' : delta > 0 ? 'text-red-400' : 'text-muted'
  return <span className={cls}>{fmtDelta(delta)}</span>
}

function AdjCell({ delta }: { delta: number | null }) {
  if (delta == null) return <span className="text-muted"> </span>
  const cls = delta < 0 ? 'text-emerald-400' : delta > 0 ? 'text-red-400' : 'text-muted'
  return <span className={cls}>{fmtAdj(delta)}</span>
}

export function RaceChart({ data }: { data: HiddenPerformanceEntry[] }) {
  return (
    <RankedTable
      rows={data as unknown as Record<string, unknown>[]}
      sortKey="adjustedDelta"
      sortDir="asc"
      initialRows={30}
      columns={[
        { key: 'driver', header: 'Driver', align: 'left' },
        { key: 'team', header: 'Team', align: 'left', render: v => (v as string) ?? ' ' },
        { key: 'race', header: 'Race', align: 'left' },
        { key: 'predicted', header: 'Ghost P', align: 'right', render: v => `P${v}` },
        { key: 'actual', header: 'Actual P', align: 'right', render: v => `P${v}` },
        {
          key: 'finishPosSe',
          header: '±SE',
          align: 'right',
          render: v => <span className="text-muted">{fmtSe(v as number)}</span>,
        },
        {
          key: 'delta',
          header: 'Raw Δ',
          align: 'right',
          render: v => <DeltaCell delta={v as number} />,
        },
        {
          key: 'adjustedDelta',
          header: 'Adj Δ',
          align: 'right',
          render: v => <AdjCell delta={v as number | null} />,
        },
        {
          key: 'confidence',
          header: 'Conf',
          align: 'right',
          render: v => fmtConf(v as number),
        },
        {
          key: 'affinityS',
          header: 'Circuit Aff',
          align: 'right',
          render: (v, row) => {
            const r = row as unknown as HiddenPerformanceEntry
            return <span className={v == null ? 'text-muted' : ''}>{fmtAffinity(v as number | null, r.affinityConf)}</span>
          },
        },
        {
          key: 'driverRating',
          header: 'Rating',
          align: 'right',
          render: v => <span className="text-muted">{fmtRating(v as number | null)}</span>,
        },
      ]}
    />
  )
}

export function SeasonChart({ data }: { data: SeasonEntry[] }) {
  return (
    <RankedTable
      rows={data as unknown as Record<string, unknown>[]}
      sortKey="meanAdjustedDelta"
      sortDir="asc"
      initialRows={30}
      columns={[
        { key: 'driver', header: 'Driver', align: 'left' },
        { key: 'team', header: 'Team', align: 'left', render: v => (v as string) ?? ' ' },
        { key: 'nRaces', header: 'Races', align: 'right' },
        {
          key: 'meanRawDelta',
          header: 'Mean Raw Δ',
          align: 'right',
          render: v => <DeltaCell delta={v as number} />,
        },
        {
          key: 'meanAdjustedDelta',
          header: 'Mean Adj Δ',
          align: 'right',
          render: v => <AdjCell delta={v as number | null} />,
        },
        {
          key: 'sdAdjustedDelta',
          header: 'SD',
          align: 'right',
          render: v => v == null ? ' ' : (v as number).toFixed(1),
        },
        {
          key: 'meanConfidence',
          header: 'Avg Conf',
          align: 'right',
          render: v => fmtConf(v as number),
        },
        {
          key: 'driverRating',
          header: 'Rating',
          align: 'right',
          render: v => <span className="text-muted">{fmtRating(v as number | null)}</span>,
        },
      ]}
    />
  )
}
