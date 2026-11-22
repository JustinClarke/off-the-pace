import { useProvenance } from '../../data/provenance'
import { useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import FeaturePage from '../../ui/layout/FeaturePage'
import { LineWithCIRibbon } from '../../ui/charts'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { useRaceOptions } from '../shared/useRaceOptions'
import { transform, toCsvRows } from './transform'
import './queries'
import type { TrackEvolutionRow } from './queries'

export default function TrackEvolutionPage() {
  const prov = useProvenance()
  const { season } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()
  const raceId = searchParams.get('race') ?? ''

  // Clear 'race' when the season changes, not on mount, so a deep link survives load (AX-03)
  const prevSeason = useRef(season)
  useEffect(() => {
    if (prevSeason.current === season) return
    prevSeason.current = season
    setSearchParams(p => { p.delete('race'); return p }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season])

  const { raceOptions, isLoading: racesLoading } = useRaceOptions(season)

  const { data, isLoading, error } = useQuery<TrackEvolutionRow[]>(
    'track-evolution.race',
    { season, raceId: raceId || '' }
  )

  const result = data ? transform(data) : null

  const circuitLabel = raceId
    ? raceOptions.find(r => r.value === raceId)?.label ?? raceId
    : null

  return (
    <FeaturePage
      title="Track Evolution"
      hook="How does field pace change over a race? A linear pace trend and an ambient drift are extracted lap by lap from the field baseline."
      badges={[
        {
          label: 'What It Means',
          content: 'The pace trend is the fitted straight-line change in fuel- and compound-corrected field pace over the race, relative to the race mean. Positive means slower than the race mean, negative faster. It is usually read as rubber build, but it is not a direct measurement of rubber.',
        },
        {
          label: 'Why It Matters',
          content: 'Track temperature changes over the race window. The ambient component is the pace residual that tracks track temperature (fitted on track temperature only).',
        },
        {
          label: "How It's Calculated",
          content: 'One slope per race, fitted to the field baseline and capped at zero. Where a race has too few laps for a slope, the trend is not measured and the chart shows a gap. Laps flagged wet are marked; laps with no weather reading are neither wet nor dry.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: prov.dataWindow, dataVersion: prov.dataVersion, labelVersion: prov.labelVersion }}
      csvRows={data ? toCsvRows(data) : undefined}
      csvFilename={`track-evolution-${raceId || season}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={!isLoading && !!raceId && result?.rubberPoints.length === 0}
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
        <p className="text-sm text-muted py-8 text-center">Select a race to view track evolution.</p>
      )}

      {result && raceId && result.rubberPoints.length > 0 && (
        <div className="flex flex-col gap-6">
          {circuitLabel && (
            <p className="text-xs text-muted uppercase tracking-wider font-mono">
              {circuitLabel} · {season}
              {result.hasRain && (
                <span className="ml-2 text-blue-400">· rain recorded</span>
              )}
            </p>
          )}
          <section className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5">
            <h2 className="text-sm font-semibold tracking-tight mb-1">Pace trend over the race</h2>
            <p className="text-xs text-muted/70 mb-3">
              Linear pace trend vs the race mean (s). Positive = slower than the race mean, usually
              early in the race; negative = faster, usually late. Blank where not measured.
            </p>
            <LineWithCIRibbon
              data={result.rubberPoints}
              xLabel="lap"
              yLabel="pace vs race mean (s)"
              seriesLabel="pace trend"
              secondaryLabel="ambient"
              color="#34d399"
              secondaryColor="#fbbf24"
              yFormatter={v => (typeof v === 'number' && Number.isFinite(v) ? `${v >= 0 ? '+' : ''}${v.toFixed(3)}s` : '')}
              height={280}
            />
          </section>
        </div>
      )}
    </FeaturePage>
  )
}
