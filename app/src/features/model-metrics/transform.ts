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
  }>
  validation: {
    calibration: CalibrationSummary
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
    n_train: m.n_train_rows,
  }))
}
