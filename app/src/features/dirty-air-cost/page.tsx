import { useState } from 'react'
import FeaturePage from '../../ui/layout/FeaturePage'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { useRaceOptions } from '../shared/useRaceOptions'
import {
  transform, totals, toCsvRows, assumptionNotes, fieldTotalLine,
  DD_WC2_DISCLAIMER, PLACEHOLDER_LINE, HOW_CALCULATED,
} from './transform'
import './queries'
import type { DirtyAirCostRow, DirtyAirLapRow } from './queries'
import { DriverCostBars, CostBuildDiagram } from './DirtyAirVisuals'
import DriverCostTable from './DriverCostTable'
import { useRaceParam } from './useRaceParam'

export default function DirtyAirCostPage() {
  const { season } = useFilters()
  const [raceId, setSearchParams] = useRaceParam()

  const { raceOptions, isLoading: racesLoading } = useRaceOptions(season)

  const { data, isLoading, error } = useQuery<DirtyAirCostRow[]>(
    'dirty-air-cost.race',
    { season, raceId: raceId || '' },
    // R3: no race picked, no download; a ?race= deep link sets raceId on first render.
    { enabled: !!raceId },
  )

  const [pickedDriver, setPickedDriver] = useState<string | null>(null)
  const pickKey = `${season}|${raceId}|`

  const result = data ? transform(data) : null
  const pickedId = pickedDriver?.startsWith(pickKey) ? pickedDriver.slice(pickKey.length) : null
  const driverId = (pickedId && data?.some(r => r.driver_id === pickedId && r.total_placeholder_cost_s != null))
    ? pickedId
    : (result?.find(r => r.total_placeholder_cost_s != null)?.driver_id ?? null)
  const { data: lapData } = useQuery<DirtyAirLapRow[]>(
    'dirty-air-cost.laps',
    { season, raceId: raceId || '', driverId: driverId ?? '' },
    { enabled: !!raceId && !!driverId },
  )
  const sum = data ? totals(data) : null
  const notes = sum ? assumptionNotes(sum) : null
  const circuitLabel = raceId
    ? raceOptions.find(r => r.value === raceId)?.label ?? raceId
    : null

  return (
    <FeaturePage
      title="Dirty Air Cost"
      hook="Roughly how much time did following other cars cost each driver? These are placeholder values: an assumed per-lap cost for this circuit and season, adjusted a little for the tyre, scaled by how much of each lap the driver spent close behind another car."
      badges={[
        {
          label: 'What It Means',
          content: 'Total is the sum of a placeholder wake cost over the driver\'s laps. It is modelled, not measured: the per-lap loss is an assumption for the circuit, season and tyre, and only the time spent close behind another car is measured. The car factor is a neutral 1.00 for every team: no team is assumed to suffer more or less in the wake.',
        },
        {
          label: 'Why It Matters',
          content: 'It sizes how much traffic shaped a race. It does not include being held up by a slower car, and it is not a verdict on the driver.',
        },
        {
          label: "How It's Calculated",
          content: HOW_CALCULATED,
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2025' }}
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

      {result && sum && raceId && result.length > 0 && (
        <div className="flex flex-col gap-4">
          {circuitLabel && (
            <p className="text-xs text-muted uppercase tracking-wider font-mono">
              {circuitLabel} · {season}
            </p>
          )}
          <section className="rounded-xl border border-amber-400/40 bg-amber-400/[0.04] p-4 text-xs leading-relaxed">
            <p className="font-semibold uppercase tracking-wider text-amber-400 mb-1">Placeholder values, modelled, not measured</p>
            <p>{DD_WC2_DISCLAIMER}</p>
            <p className="mt-1">{PLACEHOLDER_LINE}</p>
            <p className="mt-2 font-mono">{fieldTotalLine(sum)}</p>
            {notes && (
              <details className="mt-2 group">
                <summary className="cursor-pointer list-none flex items-start gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded">
                  <span aria-hidden="true" className="mt-0.5 text-muted transition-transform group-open:rotate-90">▸</span>
                  <span><span className="font-semibold">Assumptions</span>
                    <span className="text-muted"> · {notes.summary}</span></span>
                </summary>
                <div className="mt-1 pl-5 flex flex-col gap-1 font-mono text-muted">
                  {notes.rule && <p>{notes.rule}</p>}
                  <p>{notes.tyre}</p>
                  <p>{notes.car}</p>
                </div>
              </details>
            )}
          </section>
          <section className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5">
            <h2 className="text-sm font-semibold tracking-tight mb-3">Placeholder wake cost by driver (chart)</h2>
            <DriverCostBars rows={result} selected={driverId} onSelect={d => setPickedDriver(pickKey + d)} />
          </section>
          {driverId && (
            <section className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5">
              <h2 className="text-sm font-semibold tracking-tight mb-3">How the cost is built</h2>
              {lapData ? <CostBuildDiagram key={pickKey + driverId} driverId={driverId} laps={lapData} /> : <p className="text-sm text-muted">Loading laps…</p>}
            </section>
          )}
          <section className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5">
            <h2 className="text-sm font-semibold tracking-tight mb-3">Placeholder wake cost by driver (table)</h2>
            <p className="text-xs text-muted -mt-2 mb-3">Select a row for its tyre and car factors, lap counts and unavailable reasons.</p>
            {/* R4: keyed by race so expanded rows reset when the race changes */}
            <DriverCostTable key={pickKey} rows={result} selected={driverId} />
          </section>
        </div>
      )}
    </FeaturePage>
  )
}
