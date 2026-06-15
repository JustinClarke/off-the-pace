import { useState, useEffect } from 'react'
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
import type { SectorRow } from './queries'
import type { SectorDriverResult } from './transform'

function deltaClass(v: unknown): string | undefined {
  const n = v as number
  if (n <= -0.05) return 'text-emerald-400'
  if (n >= 0.05) return 'text-red-400'
  return undefined
}

function fmtDelta(v: unknown): string {
  const n = v as number
  return (n >= 0 ? '+' : '') + n.toFixed(3) + 's'
}

const columns: RankedTableColumn<SectorDriverResult>[] = [
  { key: 'rank', header: '#', align: 'right' },
  { key: 'driver_id', header: 'Driver', align: 'left' },
  {
    key: 'avg_pace_delta_s',
    header: 'Pace Δ',
    align: 'right',
    render: fmtDelta,
    cellClass: deltaClass,
  },
  {
    key: 'avg_skill_residual_s',
    header: 'Skill',
    align: 'right',
    render: fmtDelta,
    cellClass: deltaClass,
  },
  {
    key: 'avg_total_explained_s',
    header: 'Physics',
    align: 'right',
    render: fmtDelta,
    cellClass: deltaClass,
  },
  {
    key: 'avg_consistency_index',
    header: 'Spread σ',
    align: 'right',
    render: (v) => (v as number).toFixed(3) + 's',
  },
  { key: 'lap_count', header: 'Laps', align: 'right' },
]

type SectorTab = 'S1' | 'S2' | 'S3'

export default function SectorDecompositionPage() {
  const { season } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()
  const raceId = searchParams.get('race') ?? ''
  const [activeTab, setActiveTab] = useState<SectorTab>('S1')

  useEffect(() => {
    setSearchParams(p => { p.delete('race'); return p }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season])

  const { raceOptions, isLoading: racesLoading } = useRaceOptions(season)

  const { data, isLoading, error } = useQuery<SectorRow[]>(
    'sector-decomposition.race',
    { season, raceId: raceId || '' }
  )

  const result = data && raceId ? transform(data) : null
  const circuitLabel = raceId
    ? raceOptions.find(r => r.value === raceId)?.label ?? raceId
    : null

  const sectorRows = result?.[activeTab.toLowerCase() as 's1' | 's2' | 's3'] ?? []

  return (
    <FeaturePage
      title="Sector Decomposition"
      hook="Which sector of the lap is responsible for each driver's overall pace delta and how much of that gap is explained by physics versus driving? Pace, skill residual, and consistency broken down by S1/S2/S3."
      badges={[
        {
          label: 'What It Means',
          content: 'Pace Δ is the driver\'s average sector time vs the rolling field median. Skill is the part not explained by physics (fuel, tyres, ambient, constructor, dirty air). Negative = faster than field.',
        },
        {
          label: 'Why It Matters',
          content: 'A driver might be losing overall pace in S1 (braking zones) while gaining in S2 (high-speed corners) a pattern invisible in lap-level averages. Sector decomposition reveals where the time is being made or lost and whether the car or the driver is responsible.',
        },
        {
          label: "How It's Calculated",
          content: 'Lap-level physics components are allocated to sectors proportionally by sector time share. Skill residual = sector pace delta minus allocated physics components. Consistency is the within-race σ of the skill residual for each driver–sector pair.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024' }}
      csvRows={data && raceId ? toCsvRows(data) : undefined}
      csvFilename={`sector-decomposition-${raceId || season}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={!isLoading && !!raceId && result !== null && sectorRows.length === 0}
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
        <p className="text-sm text-muted py-8 text-center">Select a race to view sector-level decomposition.</p>
      )}

      {result && raceId && (
        <div className="flex flex-col gap-4">
          {circuitLabel && (
            <p className="text-xs text-muted uppercase tracking-wider font-mono">
              {circuitLabel} · {season}
            </p>
          )}

          {/* Sector tabs */}
          <div className="flex gap-0 border-b border-border">
            {(['S1', 'S2', 'S3'] as SectorTab[]).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-xs font-medium -mb-px border-b-2 transition-colors ${
                  activeTab === tab
                    ? 'border-accent text-accent'
                    : 'border-transparent text-muted hover:text-[rgb(var(--color-text))]'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          <section className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5">
            <h2 className="text-sm font-semibold tracking-tight mb-1">
              {activeTab} performance by driver
            </h2>
            <p className="text-xs text-muted mb-3">
              Ranked by avg pace delta vs field median. Negative = faster.
            </p>
            {sectorRows.length > 0 ? (
              <RankedTable rows={sectorRows} columns={columns} />
            ) : (
              <p className="text-sm text-muted py-4">No data for {activeTab}.</p>
            )}
          </section>
        </div>
      )}
    </FeaturePage>
  )
}
