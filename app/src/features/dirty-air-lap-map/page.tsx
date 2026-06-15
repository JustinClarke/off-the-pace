import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import FeaturePage from '../../ui/layout/FeaturePage'
import { Heatmap } from '../../ui/charts'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { useRaceOptions } from '../shared/useRaceOptions'
import { transform, toCsvRows } from './transform'
import './queries'
import type { LapAirStateRow } from './queries'

const STATE_LEGEND = [
  { label: 'Free air',  color: 'rgba(255,255,255,0.15)' },
  { label: 'Dirty air', color: 'rgb(194,65,12)' },
  { label: 'Tow zone',  color: 'rgb(21,128,61)' },
  { label: 'DRS train', color: 'rgb(180,83,9)' },
]

function AirTooltip({
  xLabel,
  yLabel,
  rows,
}: {
  xLabel: string
  yLabel: string
  rows: LapAirStateRow[]
}) {
  const row = rows.find(r => r.driver_id === yLabel && String(r.lap_number) === xLabel)
  const stateLabels: Record<string, string> = {
    free_air: 'Free air',
    dirty_air: 'Dirty air',
    tow_zone: 'Tow zone',
    drs_train: 'DRS train',
  }
  return (
    <div className="bg-[#13151a] border border-white/15 rounded px-3 py-2 text-xs shadow-xl">
      <p className="font-semibold mb-1">{yLabel} lap {xLabel}</p>
      {row && (
        <>
          <p className="text-muted">
            State:{' '}
            <span className="text-[rgb(var(--color-text))] font-mono">
              {stateLabels[row.air_state_dominant] ?? row.air_state_dominant}
            </span>
          </p>
          <p className="text-muted">
            Thermal load:{' '}
            <span className="font-mono text-[rgb(var(--color-text))]">
              {row.dirty_air_thermal_load_surface.toFixed(3)}
            </span>
          </p>
          {row.min_gap_s != null && (
            <p className="text-muted">
              Min gap:{' '}
              <span className="font-mono text-[rgb(var(--color-text))]">
                {row.min_gap_s.toFixed(2)}s
              </span>
            </p>
          )}
        </>
      )}
    </div>
  )
}

export default function DirtyAirLapMapPage() {
  const { season } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()
  const raceId = searchParams.get('race') ?? ''

  useEffect(() => {
    setSearchParams(p => { p.delete('race'); return p }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season])

  const { raceOptions, isLoading: racesLoading } = useRaceOptions(season)

  const { data, isLoading, error } = useQuery<LapAirStateRow[]>(
    'dirty-air-lap-map.race',
    { season, raceId: raceId || '' }
  )

  const heatmap = data ? transform(data) : null

  return (
    <FeaturePage
      title="Lap Air Map"
      hook="Which drivers spent the most laps stuck in dirty air, towing, or in a DRS train? This lap-by-lap map shows the aerodynamic environment each driver raced in, coloured by air state."
      badges={[
        {
          label: 'What It Means',
          content: 'Red laps are dirty air thermally loaded air behind a car ahead, disrupting downforce and overheating tyres. Green is a tow zone (slipstream without interference). Amber is a DRS train.',
        },
        {
          label: 'Why It Matters',
          content: 'A driver buried in dirty air for 20 laps carries a real pace and tyre-life penalty. This map separates car pace from traffic context crucial for understanding why a stint degraded faster than expected.',
        },
        {
          label: "How It's Calculated",
          content: 'Gap to car ahead is estimated from telemetry (distance-to-driver-ahead ÷ speed). The sector-2 gap classifies each lap into a state. Thermal load accumulates with an exponential weight (α=0.6, 5-lap lookback).',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024' }}
      csvRows={data ? toCsvRows(data) : undefined}
      csvFilename={`lap-air-map-${raceId || season}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={!isLoading && !!raceId && heatmap?.cells.length === 0}
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

      {heatmap && heatmap.cells.length > 0 && (
        <section className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5">
          <h2 className="text-sm font-semibold tracking-tight mb-1">
            Per-lap air state by driver
          </h2>
          <p className="text-xs text-muted mb-3">
            Rows = drivers (most dirty-air laps first). Columns = lap numbers.
            Hover a cell for thermal load and gap details.
          </p>

          {/* Legend */}
          <div className="flex flex-wrap gap-3 mb-4">
            {STATE_LEGEND.map(s => (
              <div key={s.label} className="flex items-center gap-1.5 text-xs text-muted">
                <div
                  className="w-3 h-3 rounded-sm border border-white/10"
                  style={{ backgroundColor: s.color }}
                />
                {s.label}
              </div>
            ))}
          </div>

          <Heatmap
            xLabels={heatmap.xLabels}
            yLabels={heatmap.yLabels}
            cells={heatmap.cells}
            colorMode="sequential"
            showLegend={false}
            cellWidth={14}
            cellHeight={22}
            yLabelWidth={52}
            renderTooltip={(_cell, xLabel, yLabel) => (
              <AirTooltip
                xLabel={xLabel}
                yLabel={yLabel}
                rows={data!}
              />
            )}
          />
        </section>
      )}

      {!raceId && !isLoading && (
        <p className="text-sm text-muted py-4">Select a race to view the lap air map.</p>
      )}
    </FeaturePage>
  )
}
