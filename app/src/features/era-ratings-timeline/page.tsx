import { useState, useEffect, useMemo, useCallback } from 'react'
import FeaturePage from '../../ui/layout/FeaturePage'
import EraRatingsTimelineChart from './EraRatingsTimelineChart'
import CareerSpanTimeline, { COHORT_STYLE } from './CareerSpanTimeline'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { transform, topDriversByConfidence, toCsvRows } from './transform'
import type { SpanCohort } from './transform'
import { lineColor } from './colors'
import './queries'
import type { EraRatingRow } from './queries'

const DEFAULT_SELECTED_N = 6
const COHORT_ORDER: SpanCohort[] = ['bridge', 'full-span', 'joined', 'left', 'cameo']

export default function EraRatingsTimelinePage() {
  const { data, isLoading, error } = useQuery<EraRatingRow[]>(
    'era-ratings-timeline.all',
    undefined
  )

  const result = data ? transform(data) : null
  const [selected, setSelected] = useState<string[]>([])
  const [showCI, setShowCI] = useState(false)
  const [hovered, setHovered] = useState<string | null>(null)
  // Set default selection once data arrives
  useEffect(() => {
    if (result && selected.length === 0) {
      setSelected(topDriversByConfidence(result.series, DEFAULT_SELECTED_N))
    }
  }, [result])  // eslint-disable-line react-hooks/exhaustive-deps

  const allDrivers = result?.series.map(s => s.driver_id) ?? []

  function toggleDriver(id: string) {
    setSelected(prev =>
      prev.includes(id) ? prev.filter(d => d !== id) : [...prev, id]
    )
  }

  function selectAll() { setSelected(allDrivers) }
  function clearAll() { setSelected([]) }

  const csvRows = result ? toCsvRows(result, selected) : undefined

  // Stable per-driver line colour, keyed by rating-sorted selection order so the
  // chart and the career-span timeline agree on each driver's hue.
  const colorMap = useMemo(() => {
    const map = new Map<string, string>()
    if (!result) return map
    const selectedSet = new Set(selected)
    let i = 0
    for (const s of result.series) {
      if (selectedSet.has(s.driver_id)) map.set(s.driver_id, lineColor(i++))
    }
    return map
  }, [result, selected])

  const colorOf = useCallback(
    (driverId: string) => colorMap.get(driverId) ?? '#94a3b8',
    [colorMap],
  )

  return (
    <FeaturePage
      title="Era-Adjusted Driver Rating Timeline"
      hook="How does each driver's pace rank across history, corrected for the 2022 regulation shift? Bayesian season ratings anchored on bridge drivers who raced on both sides of the boundary so Hamilton 2020 is genuinely comparable to Verstappen 2024."
      badges={[
        {
          label: 'What It Means',
          content: 'A single cross-era rating lets you ask: was Alonso 2021 as fast as Alonso 2023? Negative = faster than the era-normalised field average. The width of the CI ribbon is honesty made visible fewer races, wider uncertainty.',
        },
        {
          label: 'Why It Matters',
          content: 'Raw lap-time residuals shift at regulation changes (2022 ground-effect rules moved the absolute pace baseline). Without era calibration, a pre-2022 driver looks artificially faster or slower. The bridge-driver anchor corrects this systematically, not by hand.',
        },
        {
          label: "How It's Calculated",
          content: 'Source: int_era_normalized_driver_rating. Two-stage: (1) Bayesian shrinkage of per-season residuals toward the season league average; (2) era offset estimated from 20 bridge drivers (≥8 clean-race seasons pre- and post-2022), propagated to CI. Bridge drivers shown as solid lines.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018-2024', nObs: result?.series.length }}
      csvRows={csvRows}
      csvFilename="era-ratings-timeline.csv"
      isLoading={isLoading}
      error={error}
      isEmpty={result?.series.length === 0}
    >
      {result && (
        <div className="flex flex-col gap-6">
          {/* ── Rating chart (all seasons) ─────────────────────────── */}
          <section className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5">
            <div className="flex items-center justify-between mb-1">
              <div>
                <h2 className="text-sm font-semibold tracking-tight">Era-adjusted pace</h2>
                <p className="text-xs text-muted/70">
                  All seasons 2018-2024 · negative is faster than the era field average
                </p>
              </div>
              <label className="flex items-center gap-2 text-xs text-muted cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={showCI}
                  onChange={e => setShowCI(e.target.checked)}
                  className="accent-accent"
                />
                95% CI
              </label>
            </div>

            {selected.length === 0 ? (
              <p className="text-sm text-muted py-16 text-center">
                Select drivers from the career-span timeline below to compare.
              </p>
            ) : (
              <EraRatingsTimelineChart
                series={result.series}
                selected={selected}
                showCIRibbons={showCI}
                seasonRange={result.seasonRange}
                colorOf={colorOf}
                emphasised={hovered}
              />
            )}
          </section>

          {/* ── Career-span DAG ─────────────────────────────────────── */}
          <section className="rounded-xl border border-border bg-white/[0.015] overflow-hidden">
            <div className="flex items-center justify-between px-4 sm:px-5 py-3 border-b border-border/50">
              <div className="flex items-center gap-3">
                <span className="text-sm font-semibold tracking-tight">Who you are comparing</span>
                <span className="text-xs text-muted/60 tabular-nums">
                  {selected.length}/{allDrivers.length} selected
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-muted/60">
                <button onClick={selectAll} className="hover:text-accent transition-colors">all</button>
                <span className="text-muted/30">·</span>
                <button onClick={clearAll} className="hover:text-accent transition-colors">none</button>
              </div>
            </div>

            <div className="px-4 sm:px-5 pb-4">
              {/* cohort legend */}
              <div className="flex flex-wrap gap-x-4 gap-y-1 pt-3 pb-2">
                {COHORT_ORDER.map(c => {
                  const s = COHORT_STYLE[c]
                  return (
                    <div key={c} className="flex items-center gap-1.5 text-[11px]" title={s.hint}>
                      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: s.color }} />
                      <span className="text-muted font-medium">{s.label}</span>
                    </div>
                  )
                })}
              </div>

              <CareerSpanTimeline
                series={result.series}
                seasonRange={result.seasonRange}
                selected={selected}
                onToggle={toggleDriver}
                colorOf={colorOf}
                hovered={hovered}
                onHover={setHovered}
              />
            </div>
          </section>

          {result.lowAnchorSample && (
            <p className="text-xs text-amber-400/80 bg-amber-400/10 rounded px-3 py-2">
              Warning: era offset estimated from fewer than 3 bridge drivers-offset set to 0. Pre-2022 ratings are not era-adjusted.
            </p>
          )}
        </div>
      )}
    </FeaturePage>
  )
}
