// Types mirroring model_card.json structure (loaded at runtime, never hand-typed)

export interface ModelSummaryRow {
  name: string
  family: string
  kind: 'quantile' | 'classification' | 'regression'
  headline_metric: string
  cv_headline: number
  eval_headline: number
  baseline_headline: number
  beats_baseline: boolean
  n_train_rows: number
  quantile_alpha: number | null
  // Phase 6. Optional because a card written before the ceiling work carries neither,
  // and a missing field must render as "not measured" rather than as a zero.
  attainable: AttainableSummary | null
  interval: IntervalSummary | null
  beats_baseline_significant: boolean | null
}

// How much of the REACHABLE quantity this headline is. A pinball of 0.20 is not 20% of
// anything; 1.0 is not a score any model of this data could reach. `fraction` divides
// the model's improvement over an uninformed floor by the improvement a predictor with
// perfect stint-level knowledge could achieve. Above 1 means the model is not bounded by
// stint-level information at all -- see `verdict`.
export interface AttainableSummary {
  fraction: number | null
  scope: 'stint_level' | 'absolute' | null
  isBinding: boolean | null
  verdict: string | null
  betweenStintShare: number | null
}

// The interval on "beats baseline". Laps inside a stint are not independent draws, so a
// lap-grain point estimate overstates certainty; this is a paired t over the season folds
// plus a bootstrap that resamples whole stints.
export interface IntervalSummary {
  meanDelta: number | null
  ciLow: number | null
  ciHigh: number | null
  pValue: number | null
  nFolds: number | null
  foldsWon: number | null
  significant: boolean | null
}

export interface ImportanceEntry {
  model: string
  shap_top5: string[]
  permutation_top5: string[]
  agreement_note: string
}

export interface CohortRow {
  dimension: string
  cohort: string
  n: number
  model: number
  baseline: number
  beats_baseline: boolean
}

export interface CalibrationSummary {
  nominal: number
  raw_empirical_coverage: number
  conformal_empirical_coverage: number
  mean_interval_width: number
  n: number
}

export interface ModelMetricsResult {
  name: string
  version: string
  generated_at: string
  summary: string
  n_training_rows: number
  feature_count: number
  training_seasons: number[]
  evaluation_season: number
  evaluation_mode: string
  holdout_note: string
  models: ModelSummaryRow[]
  importance: ImportanceEntry[]
  calibration: CalibrationSummary
  cohorts: CohortRow[]
  limitations: string[]
  dataset_fingerprint: string
  onnx_parity: string
  // Claims that do not clear their own interval. Kept and shown, never dropped: a claim
  // that fails its interval is more informative than one that was never tested.
  claimsInsideNoise: string[]
}

// Raw shape of model_card.json-only the fields we read
interface RawModelCard {
  name: string
  version: string
  generated_at: string
  summary: string
  data: {
    n_training_rows: number
    feature_count: number
    training_seasons: number[]
    evaluation_season: number
    evaluation_mode: string
    holdout_note: string
  }
  features: { columns: string[] }
  models: Array<{
    name: string
    family: string
    kind: string
    headline_metric: string
    cv_headline: number
    eval_headline: number
    baseline_headline: number
    beats_baseline: boolean
    n_train_rows: number
    quantile_alpha: number | null
    beats_baseline_significant?: boolean | null
    attainable?: {
      fraction_of_attainable?: number | null
      ceiling_scope?: string | null
      ceiling_is_binding?: boolean | null
      verdict?: string | null
      between_stint_share?: number | null
    } | null
    interval?: {
      mean_delta?: number | null
      ci_low?: number | null
      ci_high?: number | null
      p_value?: number | null
      n_folds?: number | null
      folds_won?: number | null
      significant?: boolean | null
    } | null
  }>
  validation: {
    calibration: CalibrationSummary
    claims_inside_noise?: string[]
    dual_importance: Record<string, {
      shap_top5: string[]
      permutation_top5: string[]
      agreement_note: string
    }>
    underperforming_cohorts: Array<{
      dimension: string
      cohort: string
      n: number
      model: number
      baseline: number
    }>
  }
  limitations: string[]
  reproducibility: {
    dataset_fingerprint: string
    onnx_parity: string
  }
}

export function transform(raw: { model_card: RawModelCard }): ModelMetricsResult {
  const mc = raw.model_card

  const models: ModelSummaryRow[] = mc.models.map(m => ({
    name: m.name,
    family: m.family,
    kind: m.kind as ModelSummaryRow['kind'],
    headline_metric: m.headline_metric,
    cv_headline: m.cv_headline,
    eval_headline: m.eval_headline,
    baseline_headline: m.baseline_headline,
    beats_baseline: m.beats_baseline,
    n_train_rows: m.n_train_rows,
    quantile_alpha: m.quantile_alpha,
    attainable: m.attainable
      ? {
          fraction: m.attainable.fraction_of_attainable ?? null,
          scope: (m.attainable.ceiling_scope as AttainableSummary['scope']) ?? null,
          isBinding: m.attainable.ceiling_is_binding ?? null,
          verdict: m.attainable.verdict ?? null,
          betweenStintShare: m.attainable.between_stint_share ?? null,
        }
      : null,
    interval: m.interval && m.interval.p_value != null
      ? {
          meanDelta: m.interval.mean_delta ?? null,
          ciLow: m.interval.ci_low ?? null,
          ciHigh: m.interval.ci_high ?? null,
          pValue: m.interval.p_value ?? null,
          nFolds: m.interval.n_folds ?? null,
          foldsWon: m.interval.folds_won ?? null,
          significant: m.interval.significant ?? null,
        }
      : null,
    beats_baseline_significant: m.beats_baseline_significant ?? null,
  }))

  const importance: ImportanceEntry[] = Object.entries(
    mc.validation.dual_importance ?? {}
  ).map(([model, v]) => ({
    model,
    shap_top5: v.shap_top5,
    permutation_top5: v.permutation_top5,
    agreement_note: v.agreement_note,
  }))

  const cohorts: CohortRow[] = (mc.validation.underperforming_cohorts ?? []).map(c => ({
    dimension: c.dimension,
    cohort: c.cohort,
    n: c.n,
    model: c.model,
    baseline: c.baseline,
    beats_baseline: c.model < c.baseline,
  }))

  return {
    name: mc.name,
    version: mc.version,
    generated_at: mc.generated_at,
    summary: mc.summary,
    n_training_rows: mc.data.n_training_rows,
    feature_count: mc.data.feature_count,
    training_seasons: mc.data.training_seasons,
    evaluation_season: mc.data.evaluation_season,
    evaluation_mode: mc.data.evaluation_mode,
    holdout_note: mc.data.holdout_note,
    models,
    importance,
    calibration: mc.validation.calibration,
    cohorts,
    limitations: mc.limitations ?? [],
    dataset_fingerprint: mc.reproducibility.dataset_fingerprint,
    onnx_parity: mc.reproducibility.onnx_parity,
    claimsInsideNoise: mc.validation.claims_inside_noise ?? [],
  }
}

// Lower-is-better metrics (quantile pinball, RMSE) vs higher-is-better (F1)
export function metricDirectionLabel(metric: string): 'lower' | 'higher' {
  if (metric === 'macro_f1') return 'higher'
  return 'lower'
}

export function modelBeatsBaselineDescription(m: ModelSummaryRow): string {
  const dir = metricDirectionLabel(m.headline_metric)
  const improvement = dir === 'lower'
    ? ((m.baseline_headline-m.eval_headline) / m.baseline_headline * 100).toFixed(1)
    : ((m.eval_headline-m.baseline_headline) / m.baseline_headline * 100).toFixed(1)
  return `${improvement}% vs baseline`
}

export function toCsvRows(result: ModelMetricsResult): Record<string, unknown>[] {
  return result.models.map(m => ({
    model: m.name,
    metric: m.headline_metric,
    cv: m.cv_headline,
    eval: m.eval_headline,
    baseline: m.baseline_headline,
    beats_baseline: m.beats_baseline,
    beats_baseline_significant: m.beats_baseline_significant,
    fraction_of_attainable: m.attainable?.fraction ?? null,
    interval_p_value: m.interval?.pValue ?? null,
    interval_ci_low: m.interval?.ciLow ?? null,
    interval_ci_high: m.interval?.ciHigh ?? null,
    n_train: m.n_train_rows,
  }))
}

/** How to say "of attainable" without it reading as a broken percentage.
 *
 * Above 1.0 the model has scored past the stint-level ceiling, which is a statement
 * about the ceiling rather than about the model: laps inside a stint share a compound,
 * a car, a circuit, a fuel load and a driver, so that ceiling only ever bounded
 * predictors that are constant within a stint. Rendered as a multiple, not a percentage.
 */
export function attainableLabel(m: ModelSummaryRow): string | null {
  const f = m.attainable?.fraction
  if (f == null) return null
  if (f > 1) return `${f.toFixed(1)}× the stint-level ceiling`
  return m.attainable?.scope === 'absolute'
    ? `${(f * 100).toFixed(1)}% of an absolute bound`
    : `${(f * 100).toFixed(1)}% of attainable`
}

/** The interval, in the format the model card publishes it. */
export function intervalLabel(m: ModelSummaryRow): string {
  const iv = m.interval
  if (!iv || iv.pValue == null) return 'no interval'
  const verdict = m.beats_baseline_significant ? 'clears its interval' : 'inside noise'
  return `${verdict} · p=${iv.pValue.toFixed(4)} · ${iv.foldsWon}/${iv.nFolds} folds`
}
