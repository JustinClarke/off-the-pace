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
import { TechTooltip } from '../../ui/TechTooltip'

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
      title="Driver Rating Timeline"
      hook="How big was each driver's margin over his teammate, season by season? The rating is a lap-by-lap gap to the teammate in the same car, so the car, and the 2022 regulation change, cancel out and every season sits on one scale."
      badges={[
        {
          label: 'What It Means',
          content: 'Negative = faster than his teammate, in seconds per lap. Read a line as the driver\'s margin over whoever shared his car that season: a change of teammate can move it as much as a change in the driver. The width of the CI ribbon is honesty made visible: fewer races, wider uncertainty.',
        },
        {
          label: 'Why It Matters',
          content: 'Absolute lap times shift at regulation changes (2022 ground-effect rules moved the whole field). A gap to the teammate in the same car does not: the change moves both drivers alike and cancels, so no era correction is needed or applied.',
        },
        {
          label: "How It's Calculated",
          content: 'Source: int_era_normalized_driver_rating. Per race, the median lap-by-lap gap to the teammate on laps both ran clean; per season, the mean of those, shrunk toward the season mean with a 5-race prior. Drivers with 8+ races on each side of 2022 are shown as solid lines.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2025', nObs: result?.series.length }}
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
                <h2 className="text-sm font-semibold tracking-tight">Gap to teammate</h2>
                <p className="text-xs text-muted/70">
                  All seasons · negative is faster than his teammate
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
                    <TechTooltip key={c} content={s.hint}>
                      <div className="flex items-center gap-1.5 text-[11px] cursor-help">
                        <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: s.color }} />
                        <span className="text-muted font-medium">{s.label}</span>
                      </div>
                    </TechTooltip>
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

        </div>
      )}
    </FeaturePage>
  )
}
