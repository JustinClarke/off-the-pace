import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Cell, Legend,
} from 'recharts'
import type { ModelMetricsResult, ModelSummaryRow } from './transform'
import { metricDirectionLabel, modelBeatsBaselineDescription } from './transform'

const COLOR_BEAT = '#34d399'   // emerald-400
const COLOR_MISS = '#f87171'   // red-400
const COLOR_SHAP = '#818cf8'   // indigo-400
const COLOR_PERM = '#fb923c'   // orange-400
const COLOR_NEUTRAL = '#64748b' // slate-500

function modelLabel(name: string): string {
  const MAP: Record<string, string> = {
    degradation_regressor_p10: 'Degradation p10',
    degradation_regressor_p50: 'Degradation p50',
    degradation_regressor_p90: 'Degradation p90',
    cliff_classifier: 'Cliff Classifier',
    stint_life_regressor: 'Stint Life',
  }
  return MAP[name] ?? name
}

// ------- Beats-Baseline bar grid -------
function BaselineGrid({ models }: { models: ModelSummaryRow[] }) {
  const data = models.map(m => {
    const dir = metricDirectionLabel(m.headline_metric)
    const improvement = dir === 'lower'
      ? ((m.baseline_headline-m.eval_headline) / m.baseline_headline * 100)
      : ((m.eval_headline-m.baseline_headline) / m.baseline_headline * 100)
    return {
      name: modelLabel(m.name),
      model: m.eval_headline,
      baseline: m.baseline_headline,
      improvement,
      beats: m.beats_baseline,
      metric: m.headline_metric,
    }
  })

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-[rgb(var(--color-text))]">Model vs Baseline</h3>
      <p className="text-xs text-muted">All five models beat their per-cohort baseline on the 2024 CV fold. Bar = % improvement over baseline.</p>
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 120, right: 40, top: 4, bottom: 4 }}>
            <XAxis type="number" tickFormatter={v => `${v.toFixed(1)}%`} tick={{ fontSize: 10 }} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={120} />
            <Tooltip
              formatter={(v: number, _name: string, props: { payload?: { metric?: string } }) =>
                [`${v.toFixed(2)}% vs baseline`, `(${props.payload?.metric ?? ''})`]
              }
              contentStyle={{ fontSize: 11 }}
            />
            <ReferenceLine x={0} stroke={COLOR_NEUTRAL} strokeDasharray="3 3" />
            <Bar dataKey="improvement" radius={[0, 3, 3, 0]}>
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.beats ? COLOR_BEAT : COLOR_MISS} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 mt-1">
        {models.map(m => (
          <div key={m.name} className="text-xs border border-border rounded px-3 py-2 flex flex-col gap-0.5">
            <span className="font-medium text-[rgb(var(--color-text))]">{modelLabel(m.name)}</span>
            <span className="text-muted font-mono">{m.headline_metric}: {m.eval_headline.toFixed(4)}</span>
            <span className="text-muted font-mono">baseline: {m.baseline_headline.toFixed(4)}</span>
            <span className={m.beats_baseline ? 'text-emerald-400' : 'text-red-400'}>
              {m.beats_baseline ? '✓' : '✗'} {modelBeatsBaselineDescription(m)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ------- SHAP / Permutation importance paired bars -------
function ImportanceSection({ importance }: { importance: ModelMetricsResult['importance'] }) {
  if (!importance.length) return null
  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-sm font-semibold text-[rgb(var(--color-text))]">Feature Importance (SHAP vs Permutation)</h3>
      <p className="text-xs text-muted">Agreement between SHAP and permutation importance corroborates that top features are genuine, not an artefact of tree structure.</p>
      <div className="flex flex-col gap-4">
        {importance.map(imp => {
          const allFeatures = Array.from(new Set([...imp.shap_top5, ...imp.permutation_top5]))
          const data = allFeatures.map(f => ({
            feature: f,
            SHAP: imp.shap_top5.includes(f) ? imp.shap_top5.length-imp.shap_top5.indexOf(f) : 0,
            Permutation: imp.permutation_top5.includes(f) ? imp.permutation_top5.length-imp.permutation_top5.indexOf(f) : 0,
          }))

          return (
            <div key={imp.model} className="flex flex-col gap-1">
              <p className="text-xs font-medium text-muted">{modelLabel(imp.model)}</p>
              <div className="h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data} layout="vertical" margin={{ left: 180, right: 20, top: 4, bottom: 4 }}>
                    <XAxis type="number" domain={[0, 5]} ticks={[1, 2, 3, 4, 5]} tickFormatter={v => `#${6-v}`} tick={{ fontSize: 10 }} />
                    <YAxis type="category" dataKey="feature" tick={{ fontSize: 10 }} width={180} />
                    <Tooltip contentStyle={{ fontSize: 11 }} formatter={(v: number) => [`Rank #${6-(v as number)}`]} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="SHAP" fill={COLOR_SHAP} radius={[0, 3, 3, 0]} />
                    <Bar dataKey="Permutation" fill={COLOR_PERM} radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              {imp.agreement_note && (
                <p className="text-xs text-muted/70 italic">{imp.agreement_note}</p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ------- Calibration strip -------
function CalibrationSection({ cal }: { cal: ModelMetricsResult['calibration'] }) {
  const coverageData = [
    { label: 'Nominal', value: cal.nominal * 100 },
    { label: 'Raw coverage', value: cal.raw_empirical_coverage * 100 },
    { label: 'Conformal', value: cal.conformal_empirical_coverage * 100 },
  ]
  const deviation = Math.abs(cal.conformal_empirical_coverage-cal.nominal) * 100

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-[rgb(var(--color-text))]">Interval Calibration</h3>
      <p className="text-xs text-muted">
        The p10-p90 interval should cover 80% of held-out laps. Conformal coverage is {cal.conformal_empirical_coverage.toFixed(3)} vs nominal {cal.nominal} (deviation {deviation.toFixed(2)} pp).
        Mean interval width: {cal.mean_interval_width.toFixed(3)} s on n={cal.n.toLocaleString()} laps.
      </p>
      <div className="h-28">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={coverageData} margin={{ left: 20, right: 40, top: 4, bottom: 4 }}>
            <XAxis dataKey="label" tick={{ fontSize: 11 }} />
            <YAxis domain={[0, 100]} tickFormatter={v => `${v}%`} tick={{ fontSize: 10 }} />
            <Tooltip formatter={(v: number) => [`${v.toFixed(2)}%`]} contentStyle={{ fontSize: 11 }} />
            <ReferenceLine y={80} stroke={COLOR_NEUTRAL} strokeDasharray="4 4" label={{ value: '80%', position: 'right', fontSize: 10 }} />
            <Bar dataKey="value" radius={[3, 3, 0, 0]}>
              {coverageData.map((entry, i) => (
                <Cell key={i} fill={Math.abs(entry.value-80) < 2 ? COLOR_BEAT : COLOR_MISS} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ------- Underperforming cohorts table -------
function CohortTable({ cohorts }: { cohorts: ModelMetricsResult['cohorts'] }) {
  const shown = cohorts.filter(c => !c.beats_baseline).slice(0, 15)
  if (!shown.length) return null

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-[rgb(var(--color-text))]">Underperforming Cohorts</h3>
      <p className="text-xs text-muted">Slices where the model does not beat its per-cohort baseline. Small n cohorts dominate check n before drawing conclusions.</p>
      <div className="overflow-x-auto">
        <table className="text-xs w-full border-collapse">
          <thead>
            <tr className="border-b border-border text-muted">
              <th className="text-left py-1.5 pr-3">Dimension</th>
              <th className="text-left py-1.5 pr-3">Cohort</th>
              <th className="text-right py-1.5 pr-3">n</th>
              <th className="text-right py-1.5 pr-3">Model</th>
              <th className="text-right py-1.5">Baseline</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((c, i) => (
              <tr key={i} className="border-b border-border/40 hover:bg-surface">
                <td className="py-1.5 pr-3 text-muted">{c.dimension}</td>
                <td className="py-1.5 pr-3 font-mono">{c.cohort}</td>
                <td className="py-1.5 pr-3 text-right font-mono">{c.n.toLocaleString()}</td>
                <td className="py-1.5 pr-3 text-right font-mono text-red-400">{c.model.toFixed(4)}</td>
                <td className="py-1.5 text-right font-mono text-emerald-400">{c.baseline.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ------- Limitations -------
function LimitationsSection({ limitations }: { limitations: string[] }) {
  if (!limitations.length) return null
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-[rgb(var(--color-text))]">Limitations & Caveats</h3>
      <ul className="text-xs text-muted list-disc pl-4 flex flex-col gap-1">
        {limitations.map((l, i) => <li key={i}>{l}</li>)}
      </ul>
    </div>
  )
}

// ------- Main export -------
export default function ModelMetricsChart({ result }: { result: ModelMetricsResult }) {
  return (
    <div className="flex flex-col gap-8">
      <BaselineGrid models={result.models} />
      <ImportanceSection importance={result.importance} />
      <CalibrationSection cal={result.calibration} />
      <CohortTable cohorts={result.cohorts} />
      <LimitationsSection limitations={result.limitations} />
    </div>
  )
}
