import { useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import FeaturePage from '../../ui/layout/FeaturePage'
import TyreCliffSurvivalChart from './TyreCliffSurvivalChart'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { useRaceOptions } from '../shared/useRaceOptions'
import { transform, toCsvRows } from './transform'
import './queries'
import type { RaceCompoundRow, CompoundProfileRow, StintSummaryRow } from './queries'

function Select({
  label,
  value,
  onChange,
  options,
  disabled,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
  disabled?: boolean
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-muted uppercase tracking-wider">{label}</label>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled || !options.length}
        className="bg-surface border border-border rounded px-3 py-1.5 text-sm font-mono
                   text-[rgb(var(--color-text))] focus:outline-none focus:ring-1 focus:ring-accent
                   disabled:opacity-40 cursor-pointer min-w-[160px]"
      >
        <option value="">-- select --</option>
        {options.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  )
}

export default function TyreCliffSurvivalPage() {
  const { season } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()

  const raceId = searchParams.get('race_id') ?? ''
  const compound = searchParams.get('compound') ?? ''

  const setParam = (key: string, value: string) =>
    setSearchParams(p => { value ? p.set(key, value) : p.delete(key); return p }, { replace: true })

  useEffect(() => {
    setSearchParams(p => { p.delete('race_id'); p.delete('compound'); return p }, { replace: true })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season])

  // Load available race x compound combinations for this season
  const { data: raceCompounds, isLoading: rcLoading } = useQuery<RaceCompoundRow[]>(
    'tyre-cliff-survival.race-compounds',
    { season }
  )

  const { raceOptions: allRaceOptions } = useRaceOptions(season)
  const raceOptions = useMemo(() => {
    if (!raceCompounds) return []
    const available = new Set(raceCompounds.map(r => r.race_id))
    return allRaceOptions.filter(o => available.has(o.value))
  }, [raceCompounds, allRaceOptions])

  const compoundOptions = useMemo(() => {
    if (!raceCompounds || !raceId) return []
    return raceCompounds
      .filter(r => r.race_id === raceId)
      .map(r => ({ value: r.compound, label: r.compound }))
  }, [raceCompounds, raceId])

  // Load compound profile (model fit parameters) for this race x compound
  const { data: profiles } = useQuery<CompoundProfileRow[]>(
    'tyre-cliff-survival.profiles',
    { season }
  )

  const profile = useMemo(() => {
    if (!profiles || !raceId || !compound) return null
    return profiles.find(p => p.circuit_key === raceId && p.compound_code === compound) ?? null
  }, [profiles, raceId, compound])

  // Load per-stint summaries only when both race and compound are selected
  const ready = Boolean(raceId && compound)
  const { data: stints, isLoading: stintsLoading, error } = useQuery<StintSummaryRow[]>(
    'tyre-cliff-survival.stints',
    { race_id: raceId, compound, season },
    { enabled: ready }
  )

  const result = (ready && stints)
    ? transform(profile, stints, compound)
    : null

  const csvFilename = raceId && compound
    ? `tyre-survival-${raceId}-${compound.toLowerCase()}-${season}.csv`
    : `tyre-survival-${season}.csv`

  return (
    <FeaturePage
      title="Tyre Cliff Survival Profile"
      hook="How long does a compound actually last before the cliff? A Kaplan-Meier curve built from every historical stint at this circuit shows the distribution of cliff onset and overlays actual stint degradation to validate the fit in-view."
      badges={[
        {
          label: 'What It Means',
          content: 'If S(t) = 60% at lap 18, it means 60% of comparable stints survived past lap 18 without a cliff. A strategy call at lap 18 is a 40% gamble.',
        },
        {
          label: 'Why It Matters',
          content: 'Kaplan-Meier handles censored observations correctly stints that pitted before cliffing are not failures, they tell us the cliff had not happened yet. Naive averages ignore this and underestimate cliff risk.',
        },
        {
          label: "How It's Calculated",
          content: 'Source: fct_cliff_prediction_features (per-lap cliff onset flag per stint) joined with dim_compounds_season (fit parameters). KM computed in-browser from the observed stint events. Rain laps and anomaly-flagged laps excluded.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{
        dataWindow: profile?.data_window ?? '2018-2024',
        nObs: result?.actualStintCount,
        fitDate: profile?.fit_date ?? undefined,
      }}
      csvRows={result ? toCsvRows(result) : undefined}
      csvFilename={csvFilename}
      isLoading={stintsLoading && ready}
      error={error}
      isEmpty={ready && result?.stintObservations.length === 0}
    >
      <div className="flex flex-wrap gap-4 mb-6">
        <Select
          label="Race"
          value={raceId}
          onChange={v => {
            setParam('race_id', v)
            setParam('compound', '') // reset compound when race changes
          }}
          options={raceOptions}
          disabled={rcLoading}
        />
        <Select
          label="Compound"
          value={compound}
          onChange={v => setParam('compound', v)}
          options={compoundOptions}
          disabled={rcLoading || !raceId}
        />
        {profile && (
          <div className="flex items-end gap-4 text-xs text-muted">
            <span>Model onset: <span className="font-mono text-[rgb(var(--color-text))]">lap {profile.compound_cliff_onset_laps}</span></span>
            <span>Severity: <span className="font-mono text-[rgb(var(--color-text))]">+{profile.compound_cliff_severity?.toFixed(2)}s</span></span>
            <span>Wear rate: <span className="font-mono text-[rgb(var(--color-text))]">{profile.compound_wear_gradient?.toFixed(4)}s/lap</span></span>
          </div>
        )}
      </div>

      {!ready && (
        <p className="text-sm text-muted py-6">Select a race and compound above to see the survival profile.</p>
      )}
      {result && <TyreCliffSurvivalChart result={result} />}
    </FeaturePage>
  )
}
