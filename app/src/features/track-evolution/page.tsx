import { useEffect } from 'react'
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
  const { season } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()
  const raceId = searchParams.get('race') ?? ''

  useEffect(() => {
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
      hook="How does the track surface evolve over a race? Rubber buildup and ambient drift are extracted lap by lap, revealing when the track is fastest and how rain resets the grip window."
      badges={[
        {
          label: 'What It Means',
          content: 'As cars lay rubber on the racing line, grip improves and lap times fall. The rubber component captures this progressive surface change, independent of tyre degradation.',
        },
        {
          label: 'Why It Matters',
          content: 'Temperature and humidity change over the race window. The ambient component isolates this effect, which can be decisive in late-session qualifying or day-to-night races.',
        },
        {
          label: "How It's Calculated",
          content: 'Rainfall clears rubber and resets track state. Laps during flagged rainfall windows are marked. The subsequent rubbering-in process restarts.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024' }}
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
            <h2 className="text-sm font-semibold tracking-tight mb-1">Rubber buildup</h2>
            <p className="text-xs text-muted/70 mb-3">
              Lap-by-lap rubber component higher = more rubber laid, faster track
            </p>
            <LineWithCIRibbon
              data={result.rubberPoints}
              xLabel="lap"
              yLabel="rubber component (s)"
              seriesLabel="rubber"
              secondaryLabel="ambient"
              color="#34d399"
              secondaryColor="#fbbf24"
              yFormatter={v => `${v >= 0 ? '+' : ''}${v.toFixed(3)}s`}
              height={280}
            />
          </section>
        </div>
      )}
    </FeaturePage>
  )
}
