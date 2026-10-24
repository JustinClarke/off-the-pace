import FeaturePage from '../../ui/layout/FeaturePage'
import RankedTable from '../../ui/charts/RankedTable'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { transform, toCsvRows } from './transform'
import type { TeamAverageRow } from './queries'
import './queries'

function fmt(v: unknown) {
  if (v === null || v === undefined) return ''
  const s = v as number
  return `${s >= 0 ? '+' : ''}${s.toFixed(3)}s`
}

function carClass(v: unknown) {
  const s = v as number | null
  if (s === null) return undefined
  if (s < -0.1) return 'text-green-400'
  if (s > 0.1) return 'text-red-400'
  return undefined
}

export default function ConstructorTeamAveragesPage() {
  const { season } = useFilters()

  const { data, isLoading, error } = useQuery<TeamAverageRow[]>(
    'constructor-team-averages.season',
    { season }
  )

  const entries = data ? transform(data) : []

  return (
    <FeaturePage
      title="Constructor Team Averages"
      hook="Each team's cars on the same laps: the car term, dirty-air cost, and driver-skill average, with every driver counted once and teammates never paired."
      badges={[
        {
          label: 'What It Means',
          content: 'Negative car term = faster car than the field. Each team is the equal-weight average of its drivers, so a team is not judged on one driver alone.',
        },
        {
          label: 'Not Paired',
          content: 'Drivers are not compared head to head. Cross-team gaps mostly measure the car, so the page shows each team on its own.',
        },
        {
          label: 'Blank Cells',
          content: 'An empty cell means no measured reading for that team. It is not zero.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018-2025' }}
      csvRows={entries.length ? toCsvRows(entries) : undefined}
      csvFilename={`constructor-team-averages-${season}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={!isLoading && entries.length === 0}
    >
      {entries.length > 0 && (
        <section className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5">
          <h2 className="text-sm font-semibold tracking-tight mb-1">Team averages {season}</h2>
          <p className="text-xs text-muted mb-4">
            Sorted by car term (lowest = fastest car). Training-eligible laps only.
          </p>
          <RankedTable
              rows={entries}
              columns={[
                { key: 'rank', header: '#', align: 'right' },
                { key: 'constructor', header: 'Constructor', align: 'left' },
                { key: 'drivers', header: 'Drivers', align: 'right' },
                { key: 'laps', header: 'Laps', align: 'right', cellClass: () => 'text-muted' },
                {
                  key: 'car_s',
                  header: 'Car term',
                  align: 'right',
                  render: v => fmt(v),
                  cellClass: carClass,
                },
                { key: 'dirty_air_s', header: 'Dirty-air tax', align: 'right', render: v => fmt(v) },
                { key: 'driver_skill_s', header: 'Driver skill', align: 'right', render: v => fmt(v) },
              ]}
            />
        </section>
      )}
    </FeaturePage>
  )
}
