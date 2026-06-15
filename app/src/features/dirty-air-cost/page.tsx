import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import FeaturePage from '../../ui/layout/FeaturePage'
import { RankedTable } from '../../ui/charts'
import type { RankedTableColumn } from '../../ui/charts'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { useRaceOptions } from '../shared/useRaceOptions'
import { transform, toCsvRows } from './transform'
import './queries'
import type { DirtyAirCostRow } from './queries'
import type { DirtyAirResult } from './transform'

const columns: RankedTableColumn<DirtyAirResult>[] = [
  { key: 'rank', header: '#', align: 'right' },
  { key: 'driver_id', header: 'Driver', align: 'left' },
  {
    key: 'total_dirty_air_cost_s',
    header: 'Total Cost',
    align: 'right',
    render: (v) => `${(v as number).toFixed(2)}s`,
    cellClass: (v) => {
      const n = v as number
      if (n >= 5) return 'text-red-400'
      if (n >= 2) return 'text-amber-400'
      return undefined
    },
  },
  {
    key: 'avg_tax_s',
    header: 'Avg/Lap',
    align: 'right',
    render: (v) => `${(v as number).toFixed(3)}s`,
  },
  { key: 'taxed_laps', header: 'Taxed Laps', align: 'right' },
  { key: 'total_laps', header: 'Total Laps', align: 'right' },
]

export default function DirtyAirCostPage() {
  const { season } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()
  const raceId = searchParams.get('race') ?? ''

  useEffect(() => {
    setSearchParams(p => { p.delete('race'); return p }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season])

  const { raceOptions, isLoading: racesLoading } = useRaceOptions(season)

  const { data, isLoading, error } = useQuery<DirtyAirCostRow[]>(
    'dirty-air-cost.race',
    { season, raceId: raceId || '' }
  )

  const result = data ? transform(data) : null
  const circuitLabel = raceId
    ? raceOptions.find(r => r.value === raceId)?.label ?? raceId
    : null

  return (
    <FeaturePage
      title="Dirty Air Cost"
      hook="Which drivers spent the most time in disturbed airflow, and how many seconds did it cost them? The dirty air model estimates the pace penalty from following another car at close range, lap by lap."
      badges={[
        {
          label: 'What It Means',
          content: 'Total Cost is the race-end cumulative dirty air penalty in seconds. A driver fighting through traffic all race, or stuck behind a slower car they cannot pass, accumulates the largest penalty.',
        },
        {
          label: 'Why It Matters',
          content: 'Dirty air is the hidden tax on racecraft. A high total cost can explain why a competitive car finished lower than expected and why circuits with close racing (Monaco, Hungary) systematically hurt mid-field drivers more than overtaking tracks (Monza, Spa).',
        },
        {
          label: "How It's Calculated",
          content: 'Per-lap gap-to-car-ahead is fed into a per-circuit OLS coefficient to estimate dirty_air_tax_s. The cumulative race total is the sum of all non-zero laps. Leader laps, safety car laps, and pit-in/out laps are excluded from the tax calculation.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024' }}
      csvRows={data ? toCsvRows(data) : undefined}
      csvFilename={`dirty-air-${raceId || season}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={!isLoading && !!raceId && result?.length === 0}
    >
      <div className="flex flex-col gap-1 mb-6">
        <label className="text-xs font-medium text-muted uppercase tracking-wider">Race</label>
        <select
          value={raceId}
          onChange={e =>
            setSearchParams(p => {
              e.target.value ? p.set('race', e.target.value) : p.delete('race')
              return p
            }, { replace: true })
          }
          disabled={racesLoading}
          className="bg-surface border border-border rounded px-3 py-1.5 text-sm font-mono
                     text-[rgb(var(--color-text))] focus:outline-none focus:ring-1 focus:ring-accent
                     disabled:opacity-40 cursor-pointer min-w-[220px]"
        >
          <option value="">  select a race  </option>
          {raceOptions.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {!raceId && (
        <p className="text-sm text-muted py-8 text-center">Select a race to view the dirty air cost leaderboard.</p>
      )}

      {result && raceId && result.length > 0 && (
        <div className="flex flex-col gap-4">
          {circuitLabel && (
            <p className="text-xs text-muted uppercase tracking-wider font-mono">
              {circuitLabel} · {season}
            </p>
          )}
          <section className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5">
            <h2 className="text-sm font-semibold tracking-tight mb-3">Dirty air cost by driver</h2>
            <RankedTable rows={result} columns={columns} />
          </section>
        </div>
      )}
    </FeaturePage>
  )
}
