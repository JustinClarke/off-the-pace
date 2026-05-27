import FeaturePage from '../../ui/layout/FeaturePage'
import { RankedTable } from '../../ui/charts'
import type { RankedTableColumn } from '../../ui/charts'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { transform, toCsvRows } from './transform'
import './queries'
import type { WorkloadRow } from './queries'

const COLUMNS: RankedTableColumn<WorkloadRow>[] = [
  {
    key: 'driver_id',
    header: 'Driver',
    align: 'left',
  },
  {
    key: 'avg_push_residual',
    header: 'Push residual',
    align: 'right',
    render: (v) => {
      const val = v as number
      return (
        <span className={val > 0.05 ? 'text-red-400' : val < -0.05 ? 'text-green-400' : ''}>
          {val > 0 ? '+' : ''}{val.toFixed(3)}s
        </span>
      )
    },
  },
  {
    key: 'avg_stint_age_laps',
    header: 'Avg stint age',
    align: 'right',
    render: (v) => `${(v as number).toFixed(1)} laps`,
  },
  {
    key: 'avg_dirty_air_share',
    header: 'Dirty air',
    align: 'right',
    render: (v) => `${((v as number) * 100).toFixed(1)}%`,
    cellClass: (v) => (v as number) > 0.15 ? 'text-orange-400' : undefined,
  },
  {
    key: 'cliff_flag_pct',
    header: 'Cliff risk',
    align: 'right',
    render: (v) => `${(v as number).toFixed(1)}%`,
  },
  {
    key: 'total_laps',
    header: 'Laps',
    align: 'right',
    cellClass: () => 'text-muted',
  },
]

export default function DriverWorkloadPage() {
  const { season } = useFilters()

  const { data, isLoading, error } = useQuery<WorkloadRow[]>(
    'driver-workload.season',
    { season }
  )

  const rows = data ? transform(data) : []

  return (
    <FeaturePage
      title="Driver Workload"
      hook="Who pushes hardest on their tyres, races deepest into stints, and spends the most time in dirty air? These four signals expose the physical and strategic workload each driver carries across a season."
      badges={[
        {
          label: 'What It Means',
          content: 'Push residual captures how hard a driver presses beyond the expected degradation curve. A high positive value means the driver consistently accelerates tyre wear relative to their stint position often a sign of aggressive racecraft.',
        },
        {
          label: 'Why It Matters',
          content: 'Workload metrics disentangle driver intent from car circumstance. A driver with high push residual and high dirty-air share is fighting both their own aggression and traffic explaining cliff risk better than either signal alone.',
        },
        {
          label: "How It's Calculated",
          content: 'Aggregated from the lap-grain cliff prediction feature table (training-eligible laps only). Push residual is the within-stint driver skill residual drift. Dirty air share uses telemetry gap-to-car-ahead estimates.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024' }}
      csvRows={data ? toCsvRows(data) : undefined}
      csvFilename={`driver-workload-${season}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={!isLoading && rows.length === 0}
    >
      {rows.length > 0 && (
        <section className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5">
          <h2 className="text-sm font-semibold tracking-tight mb-1">
            Driver workload {season}
          </h2>
          <p className="text-xs text-muted mb-4">
            Sorted by push residual (highest = most aggressive). Training-eligible laps only.
          </p>
          <RankedTable
            rows={rows}
            columns={COLUMNS}
            initialRows={25}
          />
        </section>
      )}
    </FeaturePage>
  )
}
