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
import type { FieldPaceRow } from './queries'

export default function FieldPaceCurvePage() {
  const { season } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()
  const raceId = searchParams.get('race') ?? ''

  useEffect(() => {
    setSearchParams(p => { p.delete('race'); return p }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season])

  const { raceOptions, isLoading: racesLoading } = useRaceOptions(season)

  const { data, isLoading, error } = useQuery<FieldPaceRow[]>(
    'field-pace.race',
    { season, raceId: raceId || '' }
  )

  const result = data ? transform(data) : null

  const circuitLabel = raceId
    ? raceOptions.find(r => r.value === raceId)?.label ?? raceId
    : null

  function fmtTime(s: number) {
    const min = Math.floor(s / 60)
    const sec = (s % 60).toFixed(3)
    return min > 0 ? `${min}:${sec.padStart(6, '0')}` : `${Number(sec).toFixed(3)}s`
  }

  return (
    <FeaturePage
      title="Field Pace Curve"
      hook="What did the entire field actually lap in each lap of the race? The smoothed field average captures the combined effect of fuel load, tyre age, and track evolution the living baseline every driver is measured against."
      badges={[
        {
          label: 'What It Means',
          content: 'The smoothed trimmed-mean lap time of all cars on track per lap. Safety car periods and pit entry/exit laps are filtered out from the eligible set.',
        },
        {
          label: 'Why It Matters',
          content: 'The shaded band shows the gap between the LOWESS-smoothed curve and the raw trimmed mean. Wide band = high spread or few cars in that lap window.',
        },
        {
          label: 'Why It Matters',
          content: 'This curve is the reference baseline for the seven-term decomposition. Isolating it lets you see when the race was "fast" and when incidents, strategy, or track limits pulled the field slower.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024' }}
      csvRows={data ? toCsvRows(data) : undefined}
      csvFilename={`field-pace-${raceId || season}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={!isLoading && !!raceId && result?.points.length === 0}
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
        <p className="text-sm text-muted py-8 text-center">Select a race to view the field pace curve.</p>
      )}

      {result && raceId && result.points.length > 0 && (
        <div className="flex flex-col gap-6">
          {circuitLabel && (
            <p className="text-xs text-muted uppercase tracking-wider font-mono">
              {circuitLabel} · {season}
              {result.hasLowSample && (
                <span className="ml-2 text-amber-400/80">· some laps low-sample</span>
              )}
            </p>
          )}
          <section className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5">
            <h2 className="text-sm font-semibold tracking-tight mb-1">Field pace</h2>
            <p className="text-xs text-muted/70 mb-3">
              Smoothed trimmed mean · ribbon = gap to raw mean · lower is faster
            </p>
            <LineWithCIRibbon
              data={result.points}
              xLabel="lap"
              yLabel="lap time"
              seriesLabel="smoothed"
              secondaryLabel="raw mean"
              color="#60a5fa"
              secondaryColor="#94a3b8"
              yFormatter={fmtTime}
              height={300}
            />
          </section>
        </div>
      )}
    </FeaturePage>
  )
}
