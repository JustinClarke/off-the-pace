import { useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import FeaturePage from '../../ui/layout/FeaturePage'
import CautionTimeline from './CautionTimeline'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { useRaceOptions } from '../shared/useRaceOptions'
import {
  transform,
  summarisePooled,
  hazardContext,
  toCsvRows,
  EB_PRIOR_LAPS,
} from './transform'
import './queries'
import type { CautionLapRow, HazardRow, PooledRateRow } from './queries'

const pct = (x: number) => `${(x * 100).toFixed(1)}%`

function RateLine({
  label,
  value,
}: {
  label: string
  value: { rate: number; lo: number; hi: number; n: number }
  }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border/50 py-2">
      <span className="text-sm">{label}</span>
      <span className="font-mono text-xs">
        <span className="text-base text-[rgb(var(--color-text))]">{pct(value.rate)}</span>
        <span className="ml-2 text-muted">
          [{pct(value.lo)}–{pct(value.hi)}]
        </span>
      </span>
    </div>
  )
}

export default function RaceControlPage() {
  const { season } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()
  const raceId = searchParams.get('race_id') ?? ''

  useEffect(() => {
    setSearchParams(p => { p.delete('race_id'); return p }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season])

  const { raceOptions, isLoading: optsLoading } = useRaceOptions(season)
  const ready = Boolean(raceId)

  const { data: lapRows, isLoading, error } = useQuery<CautionLapRow[]>(
    'race-control.timeline',
    { season, raceId },
    { enabled: ready }
  )
  const { data: pooledRows } = useQuery<PooledRateRow[]>('race-control.pooled-rates', {})
  const { data: hazardRows } = useQuery<HazardRow[]>(
    'race-control.circuit-hazard',
    { season, raceId },
    { enabled: ready }
  )

  const result = useMemo(() => (lapRows?.length ? transform(lapRows) : null), [lapRows])
  const pooled = useMemo(() => summarisePooled(pooledRows ?? []), [pooledRows])
  const hazard = useMemo(() => hazardContext(hazardRows ?? []), [hazardRows])

  const raceLabel = raceOptions.find(o => o.value === raceId)?.label ?? raceId

  return (
    <FeaturePage
      title="Race Control Timeline"
      hook="Every safety car, virtual safety car and red flag in a race, on the lap it happened and for as long as it lasted — and an honest account of what that history can and cannot tell you about the next one."
      badges={[
        {
          label: 'What It Means',
          content:
            'The strip is one race, lap 1 on the left to the chequered flag on the right. Green is racing; the coloured blocks are the laps run under a neutralisation. A five-lap safety car is five laps where nobody could race and everyone got a cheap pit stop — which is why strategists spend the whole race planning around it.',
        },
        {
          label: 'Why It Matters',
          content:
            'A caution resets the race. It wipes out gaps built over twenty laps, halves the cost of a pit stop, and hands the lead to whoever had not stopped yet. Reading the timeline next to the pit-stop Gantt is how you tell a brilliant strategy call from a lucky one.',
        },
        {
          label: "How It's Calculated",
          content:
            'Per-lap track status from the FIA feed, via stg_laps into int_stint_geometry, collapsed to one row per race and lap. The pooled frequency comes from all 149 races. There is deliberately no per-circuit probability: at roughly four races per circuit the between-circuit variance component measures zero, so a per-circuit percentage would be noise with a venue name on it.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024' }}
      csvRows={result ? toCsvRows(raceId, result) : undefined}
      csvFilename={`race-control-${raceId || season}.csv`}
      isLoading={isLoading && ready}
      error={error}
      isEmpty={ready && lapRows !== undefined && lapRows.length === 0}
    >
      <div className="mb-6 flex flex-wrap gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium uppercase tracking-wider text-muted">Race</label>
          <select
            value={raceId}
            onChange={e =>
              setSearchParams(p => {
                e.target.value ? p.set('race_id', e.target.value) : p.delete('race_id')
                return p
              }, { replace: true })
            }
            disabled={optsLoading || !raceOptions.length}
            className="min-w-[180px] cursor-pointer rounded border border-border bg-surface px-3 py-1.5 font-mono
                       text-sm text-[rgb(var(--color-text))] focus:outline-none focus:ring-1
                       focus:ring-accent disabled:opacity-40"
          >
            <option value="">-- select --</option>
            {raceOptions.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      {!ready && (
        <p className="py-6 text-sm text-muted">Select a race above to see its caution timeline.</p>
      )}

      {result && <CautionTimeline result={result} raceLabel={raceLabel} />}

      {/* ── The estimate pane, kept visually apart from the record above ── */}
      {pooled && (
        <section className="mt-10 border-t border-border pt-6">
          <h2 className="mb-1 text-sm font-semibold tracking-tight">
            How often does this happen at all?
          </h2>
          <p className="mb-4 max-w-2xl text-xs leading-relaxed text-muted">
            Pooled across every circuit and every season — {pooled.races} races, 2018–2024 — with a
            Wilson 95% interval on each. This is the only caution probability on this page, and it
            is pooled for a reason given in full under Methodology: at about four races per
            circuit, the between-circuit share of the variance in whether a race gets a safety car
            measures <span className="font-mono">0.000</span>, so a per-venue percentage would be
            race-to-race noise wearing a circuit&apos;s name.
          </p>

          <div className="grid gap-x-10 gap-y-0 md:grid-cols-2">
            <div>
              <RateLine label="Any caution" value={pooled.anyCaution} />
              <RateLine label="Safety car" value={pooled.safetyCar} />
              <RateLine label="Virtual safety car" value={pooled.vsc} />
              <RateLine label="Red flag" value={pooled.redFlag} />
              <p className="pt-2 text-xs text-muted">
                {pct(pooled.cautionLapShare)} of all race laps, 2018–2024, were run under a
                caution.
              </p>
            </div>

            <div>
              <p className="mb-2 text-xs uppercase tracking-wider text-muted">
                Races with a caution, by season
              </p>
              <table className="w-full text-xs">
                <tbody>
                  {pooled.perSeason.map(s => (
                    <tr key={s.season} className="border-b border-border/40">
                      <td className="py-1 font-mono">{s.season}</td>
                      <td className="py-1">
                        <span
                          className="inline-block h-2 rounded-sm bg-amber-400/70 align-middle"
                          style={{ width: `${Math.max(2, s.rate * 100)}px` }}
                        />
                      </td>
                      <td className="py-1 text-right font-mono">{pct(s.rate)}</td>
                      <td className="py-1 text-right font-mono text-muted">
                        {s.withCaution}/{s.races}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="pt-2 text-xs text-muted">
                Season, not circuit, is where the variation in this dataset lives.
              </p>
            </div>
          </div>
        </section>
      )}

      {/* ── Per-circuit context, declared for what it is ── */}
      {ready && hazard.row && (
        <section className="mt-8 rounded border border-border bg-surface/40 p-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
            This venue, as of the start of {season}
          </h3>
          {hazard.unmeasurable ? (
            <p className="max-w-2xl text-sm text-muted">
              <strong className="text-[rgb(var(--color-text))]">Not measurable.</strong> The hazard
              model is season-lagged — a venue&apos;s rate is estimated from races run there in
              earlier seasons only — and{' '}
              {season === 2018
                ? '2018 is the first season in the warehouse, so no prior season exists for any circuit.'
                : 'this venue has no prior season in the warehouse.'}{' '}
              Shown as unmeasurable rather than as zero: a measured zero and an unmeasurable one
              are different claims.
            </p>
          ) : (
            <>
              <div className="flex flex-wrap gap-x-8 gap-y-2">
                <div>
                  <span className="font-mono text-lg text-[rgb(var(--color-text))]">
                    {(hazard.row.any_hazard_per_lap_shrunk! * 100).toFixed(2)}
                  </span>
                  <span className="ml-1 text-xs text-muted">caution onsets per 100 racing laps</span>
                </div>
                <div className="text-xs text-muted">
                  measured from{' '}
                  <span className="font-mono text-[rgb(var(--color-text))]">
                    {hazard.row.prior_races_n}
                  </span>{' '}
                  prior race{hazard.row.prior_races_n === 1 ? '' : 's'} at this venue
                </div>
              </div>
              <p className="mt-2 max-w-2xl text-xs leading-relaxed text-muted">
                This is the shrunk estimate, and only{' '}
                <span className="font-mono">{pct(hazard.ownDataWeight)}</span> of it is this
                circuit&apos;s own history — the rest is the all-circuits pooled rate, because{' '}
                {hazard.row.prior_racing_laps.toLocaleString()} prior laps against a{' '}
                {EB_PRIOR_LAPS}-lap prior is not enough to move it. Read it as context, not as a
                forecast for this weekend. The raw per-circuit rate, which spans zero to ten
                onsets per hundred laps on the same data, is not shown anywhere in this app.
              </p>
            </>
          )}
        </section>
      )}
    </FeaturePage>
  )
}
