import { useEffect, useMemo, useState } from 'react'
import FeaturePage from '../../ui/layout/FeaturePage'
import BlindTestScoreboardChart from './BlindTestScoreboardChart'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { transform, toCsvRows, COMPOUND_COLORS } from './transform'
import './queries'
import type { ScoreboardRow } from './queries'
import { MODELS_BASE } from '../../ml/manifest'

const MODEL_CARD_URL = `${MODELS_BASE}/model_card.json`
// 2026 is the designated holdout season. Any season the shipped models trained on is in-sample.
const HOLDOUT_SEASON = 2026

interface CardProvenance {
  version: string
  dataset_fingerprint: string
  training_seasons: number[]
}

function formatCircuit(key: string) {
  return key
    .replace(/_grand_prix/g, ' GP')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
    .trim()
}

interface MismatchModal {
  compound: string
  circuit: string
}

export default function BlindTestScoreboardPage() {
  const { season } = useFilters()
  const [compoundFilter, setCompoundFilter] = useState<string | null>(null)
  const [circuitFilter, setCircuitFilter] = useState<string | null>(null)
  const [mismatch, setMismatch] = useState<MismatchModal | null>(null)
  const [card, setCard] = useState<CardProvenance | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch(MODEL_CARD_URL)
      .then(r => (r.ok ? r.json() : null))
      .then(raw => { if (!cancelled && raw?.model_card) setCard(raw.model_card) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  const isInSample = card ? card.training_seasons.includes(season) : season < HOLDOUT_SEASON
  const trainedOn = card
    ? `${Math.min(...card.training_seasons)}–${Math.max(...card.training_seasons)}`
    : null

  const { data: rows, isLoading, error } = useQuery<ScoreboardRow[]>(
    'blind-test-scoreboard.rows',
    { season },
  )

  const result = useMemo(
    () => transform(rows ?? [], compoundFilter, circuitFilter),
    [rows, compoundFilter, circuitFilter],
  )

  return (
    <>
    <FeaturePage
      title="Blind Test Scoreboard"
      hook={isInSample
        ? `Degradation model predictions vs actuals for ${season}. The shipped models trained on this season, so this is in-sample fit, not a blind test. ${HOLDOUT_SEASON} is the blind test.`
        : `Degradation model predictions vs actuals for ${season}, a season the shipped models never saw. Every call is locked against real race data.`}
      badges={[
        {
          label: 'What It Means',
          content: "Did the model actually call the cliff? This scoreboard plots every prediction against what really happened. Green = the actual jump landed inside the 80% confidence band. On a season the model trained on, that flatters the fit; on the 2026 holdout it is a real test.",
        },
        {
          label: 'Why It Matters',
          content: "A self-locking out-of-sample scoreboard is the difference between a demo and a real model. 2026 is the blind test: its races are scored by models that never saw them, as they ingest. Until then every season here is in-sample; the honest out-of-sample numbers are the 2025 cross-validation fold on Model Metrics.",
        },
        {
          label: "How It's Calculated",
          content: "mart_degradation_predictions.parquet (17-col schema) joined to fct_cliff_prediction_features on lap_id for actuals. Coverage = fraction of laps where actual falls in [p10, p90] (conformal target: 80%). Cliff confusion matrix: 4-class predicted vs actual.",
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{
        modelVersion: card?.version.replace(/^v/, ''),
        datasetFingerprint: card?.dataset_fingerprint,
        dataWindow: trainedOn
          ? `Trained on ${trainedOn}; ${HOLDOUT_SEASON} is the blind test`
          : `${HOLDOUT_SEASON} is the blind test`,
      }}
      csvRows={result.scatter.length ? toCsvRows(result) : undefined}
      csvFilename={`blind-test-scoreboard-${season}.csv`}
      isLoading={isLoading}
      error={error ?? null}
      isEmpty={!isLoading && !error && result.scatter.length === 0}
    >
      {/* Filters */}
      {result.compoundFilter.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 mb-6 p-3 rounded-lg bg-white/[0.03] border border-white/[0.06]">
          {/* Compound pills with compound-colour dots */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted shrink-0">Compound</span>
            <button
              onClick={() => setCompoundFilter(null)}
              className={`text-xs px-3 py-1 rounded-full border transition-colors
                ${compoundFilter === null
                  ? 'border-white/30 bg-white/10 text-white font-medium'
                  : 'border-white/10 text-white/40 hover:text-white/70 hover:border-white/20'}`}
            >
              All
            </button>
            {result.compoundFilter.map(c => {
              const dotColor = COMPOUND_COLORS[c] ?? '#a78bfa'
              const active = compoundFilter === c
              return (
                <button
                  key={c}
                  onClick={() => setCompoundFilter(active ? null : c)}
                  className={`flex items-center gap-1.5 text-xs px-3 py-1 rounded-full border transition-colors
                    ${active
                      ? 'border-white/30 bg-white/10 text-white font-medium'
                      : 'border-white/10 text-white/40 hover:text-white/70 hover:border-white/20'}`}
                >
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ background: dotColor, opacity: active ? 1 : 0.5 }}
                  />
                  {c}
                </button>
              )
            })}
          </div>

          {/* Divider */}
          <div className="w-px h-5 bg-white/10 hidden sm:block" />

          {/* Circuit dropdown-explicit dark styling */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted shrink-0">Circuit</span>
            <select
              value={circuitFilter ?? ''}
              onChange={e => {
                const newCircuit = e.target.value || null
                if (compoundFilter !== null && newCircuit !== null) {
                  const compoundsInCircuit = new Set(
                    (rows ?? []).filter(r => r.circuit_key === newCircuit).map(r => r.compound)
                  )
                  if (!compoundsInCircuit.has(compoundFilter)) {
                    setMismatch({ compound: compoundFilter, circuit: newCircuit })
                    return
                  }
                }
                setCircuitFilter(newCircuit)
              }}
              style={{ colorScheme: 'dark' }}
              className="text-xs bg-[#1a1d23] border border-white/15 rounded-md px-2.5 py-1.5
                text-white/80 hover:border-white/30 focus:outline-none focus:border-white/40
                cursor-pointer min-w-[160px]"
            >
              <option value="">All circuits</option>
              {result.circuitFilter.map(c => (
                <option key={c} value={c} className="bg-[#1a1d23] text-white">
                  {formatCircuit(c)}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      <BlindTestScoreboardChart result={result} />
    </FeaturePage>

    {mismatch && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
        <div className="bg-[#1a1d23] border border-white/15 rounded-xl p-6 max-w-sm w-full mx-4 shadow-2xl">
          <h3 className="text-sm font-semibold text-white mb-2">No {mismatch.compound} data at this circuit</h3>
          <p className="text-xs text-white/50 mb-5">
            {mismatch.compound} tyres were not used at{' '}
            {formatCircuit(mismatch.circuit)}.
            Switching to all circuits so the filter stays active.
          </p>
          <button
            onClick={() => {
              setMismatch(null)
              setCircuitFilter(null)
            }}
            className="w-full text-xs font-medium px-4 py-2 rounded-lg bg-white/10 hover:bg-white/15 text-white border border-white/15 transition-colors"
          >
            OK
          </button>
        </div>
      </div>
    )}
    </>
  )
}
