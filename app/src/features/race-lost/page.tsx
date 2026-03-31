import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import FeaturePage from '../../ui/layout/FeaturePage'
import { Waterfall } from '../../ui/charts'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { useRaceOptions } from '../shared/useRaceOptions'
import { transform, toCsvRows } from './transform'
import './queries'
import type { RaceLostRow } from './queries'

export default function RaceLostPage() {
  const { season } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()
  const raceId = searchParams.get('race') ?? ''
  const [driverId, setDriverId] = useState<string>('')

  useEffect(() => {
    setSearchParams(p => { p.delete('race'); return p }, { replace: true })
    setDriverId('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season])

  useEffect(() => {
    setDriverId('')
  }, [raceId])

  const { raceOptions, isLoading: racesLoading } = useRaceOptions(season)

  const { data: driverList, isLoading: driversLoading } = useQuery<{ driver_id: string }[]>(
    'race-lost.drivers',
    { season, raceId: raceId || '' }
  )

  const { data, isLoading, error } = useQuery<RaceLostRow[]>(
    'race-lost.driver',
    { season, raceId: raceId || '', driverId: driverId || '' }
  )

  const row = data?.[0] ?? null
  const result = row && driverId ? transform(row) : null
  const circuitLabel = raceId
    ? raceOptions.find(r => r.value === raceId)?.label ?? raceId
    : null

  return (
    <FeaturePage
      title="How the Race Was Lost"
      hook="Select a race and driver to see the cumulative race-time contribution of every pace component fuel, tyres, car, dirty air, and driver skill summed across all classified laps."
      badges={[
        {
          label: 'What It Means',
          content: 'Each bar shows the total seconds gained (negative) or lost (positive) from that factor vs the per-lap field median, cumulated across the entire race. Driver Skill is the residual after removing all physics components.',
        },
        {
          label: 'Why It Matters',
          content: 'A per-lap average hides compounding effects. If a driver ran in dirty air for 20 consecutive laps, the cumulative tax can dwarf their skill advantage. This view reveals which factor actually determined the race result especially useful for mid-field battles.',
        },
        {
          label: "How It's Calculated",
          content: 'The 7-term lap decomposition identity (fuel + compound + rubber + ambient + constructor + dirty_air + skill) is summed across all non-SC, non-outlier laps for the selected driver. All terms are vs the smoothed per-lap field trimmed mean.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024' }}
      csvRows={row && driverId ? toCsvRows(driverId, row) : undefined}
      csvFilename={`race-lost-${raceId}-${driverId}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={!isLoading && !!raceId && !!driverId && !row}
    >
      {/* Controls */}
      <div className="flex flex-wrap gap-6 mb-6">
        <div className="flex flex-col gap-1">
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

        {raceId && (
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted uppercase tracking-wider">Driver</label>
            <select
              value={driverId}
              onChange={e => setDriverId(e.target.value)}
              disabled={driversLoading || !raceId}
              className="bg-surface border border-border rounded px-3 py-1.5 text-sm font-mono
                         text-[rgb(var(--color-text))] focus:outline-none focus:ring-1 focus:ring-accent
                         disabled:opacity-40 cursor-pointer min-w-[160px]"
            >
              <option value="">  select a driver  </option>
              {(driverList ?? []).map(d => (
                <option key={d.driver_id} value={d.driver_id}>{d.driver_id}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {!raceId && (
        <p className="text-sm text-muted py-8 text-center">Select a race to begin.</p>
      )}
      {raceId && !driverId && (
        <p className="text-sm text-muted py-8 text-center">Select a driver to view their race decomposition.</p>
      )}

      {result && (
        <div className="flex flex-col gap-4">
          {circuitLabel && (
            <p className="text-xs text-muted uppercase tracking-wider font-mono">
              {driverId} · {circuitLabel} · {season} · {result.nLaps} laps
            </p>
          )}
          <section className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5">
            <h2 className="text-sm font-semibold tracking-tight mb-1">
              Race-total pace component contributions
            </h2>
            <p className="text-xs text-muted mb-4">
              Negative = gained time vs field median. Summed across all classified laps.
            </p>
            <Waterfall
              bars={result.bars}
              closureGap={result.closureGap}
              yLabel="Cumulative seconds vs field"
            />
          </section>
        </div>
      )}
    </FeaturePage>
  )
}
