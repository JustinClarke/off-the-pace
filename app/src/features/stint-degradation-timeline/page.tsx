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
import type { DegradationProfileRow } from './queries'

const COMPOUND_COLOR: Record<string, string> = {
  SOFT: '#ef4444',
  MEDIUM: '#eab308',
  HARD: '#cbd5e1',
}

function getColor(compound: string) {
  return COMPOUND_COLOR[compound] ?? '#60a5fa'
}

export default function StintDegradationTimelinePage() {
  const { season } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()
  const raceId = searchParams.get('race') ?? ''

  useEffect(() => {
    setSearchParams(p => { p.delete('race'); return p }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season])

  const { raceOptions, isLoading: racesLoading } = useRaceOptions(season)

  const { data, isLoading, error } = useQuery<DegradationProfileRow[]>(
    'degradation-timeline.profile',
    { season, raceId: raceId || '' }
  )

  const profiles = data ? transform(data) : null

  return (
    <FeaturePage
      title="Degradation Timeline"
      hook="How quickly does each compound wear through a stint? The timeline shows the cumulative pace penalty vs fresh rubber, averaged across all stints in the race with the spread revealing how differently drivers managed their tyres."
      badges={[
        {
          label: 'What It Means',
          content: 'Each line is the average expected pace loss (seconds per lap slower than a fresh tyre) as a stint progresses. The shaded band shows ±1 standard deviation across stints wider = more driver-to-driver variation in tyre management.',
        },
        {
          label: 'Why It Matters',
          content: 'The shape of the curve reveals cliff risk: a gradual slope suggests manageable degradation; a sudden upturn after the cliff onset confirms the model\'s predicted onset lap. Circuits with abrasive asphalt (Bahrain, Abu Dhabi) show steeper early curves.',
        },
        {
          label: "How It's Calculated",
          content: 'Cumulative degradation is summed from fct_cliff_prediction_features using the compound-specific wear gradient and cliff-severity parameters fitted per circuit per season. SC laps, wet laps, out-laps, and in-laps are excluded.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024' }}
      csvRows={data ? toCsvRows(data) : undefined}
      csvFilename={`degradation-timeline-${raceId || season}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={!isLoading && !!raceId && profiles?.length === 0}
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
        <p className="text-sm text-muted py-8 text-center">Select a race to view degradation timelines.</p>
      )}

      {profiles && raceId && profiles.length > 0 && (
        <div className="flex flex-col gap-6">
          {profiles.map(profile => (
            <section
              key={profile.compound}
              className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5"
            >
              <div className="flex items-center gap-2 mb-1">
                <span
                  className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                  style={{ backgroundColor: getColor(profile.compound) }}
                />
                <h2 className="text-sm font-semibold tracking-tight">{profile.compound}</h2>
                {profile.cliffOnset !== null && (
                  <span className="text-xs text-muted/70">
                    · cliff onset ~{profile.cliffOnset} laps
                  </span>
                )}
              </div>
              <p className="text-xs text-muted/70 mb-3">
                Cumulative pace loss vs fresh · ribbon = ±1 SD across stints · higher = slower
              </p>
              <LineWithCIRibbon
                data={profile.points}
                xLabel="lap in stint"
                yLabel="pace loss (s)"
                seriesLabel="avg degradation"
                color={getColor(profile.compound)}
                yFormatter={v => v.toFixed(2) + 's'}
                height={200}
              />
            </section>
          ))}
        </div>
      )}
    </FeaturePage>
  )
}
