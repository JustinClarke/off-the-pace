import { describe, it, expect } from 'vitest'
import { transform, metricDirectionLabel, modelBeatsBaselineDescription } from './transform'

const MINIMAL_CARD = {
  model_card: {
    name: 'Test Card',
    version: 'v1',
    generated_at: '2026-01-01T00:00:00Z',
    summary: 'A test card',
    data: {
      n_training_rows: 1000,
      feature_count: 38,
      training_seasons: [2023, 2024],
      evaluation_season: 2024,
      evaluation_mode: 'cv_final_fold',
      holdout_note: 'No live holdout.',
    },
    features: { columns: [] },
    models: [
      {
        name: 'degradation_regressor_p50',
        family: 'degradation_regressor',
        kind: 'quantile',
        headline_metric: 'pinball',
        cv_headline: 0.19,
        eval_headline: 0.19,
        baseline_headline: 0.22,
        beats_baseline: true,
        n_train_rows: 1000,
        quantile_alpha: 0.5,
      },
      {
        name: 'cliff_classifier',
        family: 'cliff_classifier',
        kind: 'classification',
        headline_metric: 'macro_f1',
        cv_headline: 0.36,
        eval_headline: 0.37,
        baseline_headline: 0.18,
        beats_baseline: true,
        n_train_rows: 1000,
        quantile_alpha: null,
      },
    ],
    validation: {
      calibration: {
        nominal: 0.8,
        raw_empirical_coverage: 0.803,
        conformal_empirical_coverage: 0.804,
        mean_interval_width: 1.1,
        n: 18000,
      },
      dual_importance: {
        degradation_regressor_p50: {
          shap_top5: ['push_residual', 'age_in_stint', 'cumulative_push_load_surface', 'cumulative_push_load_bulk', 'dirty_air_thermal_load_bulk'],
          permutation_top5: ['push_residual', 'cumulative_push_load_surface', 'cumulative_push_load_bulk', 'pct_drs_active', 'age_in_stint'],
          agreement_note: 'top-5 differ on: dirty_air_thermal_load_bulk, pct_drs_active',
        },
      },
      underperforming_cohorts: [
        { dimension: 'compound', cohort: '_other', n: 9, model: 0.23, baseline: 0.22 },
        { dimension: 'circuit_key', cohort: 'canadian_grand_prix', n: 817, model: 0.20, baseline: 0.24 },
      ],
    },
    limitations: ['The cliff classifier is the weakest model.'],
    reproducibility: {
      dataset_fingerprint: 'abc123',
      onnx_parity: 'all 5 round-trip within atol=1e-5',
    },
  },
}

describe('transform', () => {
  it('extracts all five top-level fields', () => {
    const result = transform(MINIMAL_CARD)
    expect(result.version).toBe('v1')
    expect(result.n_training_rows).toBe(1000)
    expect(result.feature_count).toBe(38)
    expect(result.training_seasons).toEqual([2023, 2024])
    expect(result.dataset_fingerprint).toBe('abc123')
  })

  it('maps models correctly', () => {
    const result = transform(MINIMAL_CARD)
    expect(result.models).toHaveLength(2)
    const p50 = result.models[0]
    expect(p50.name).toBe('degradation_regressor_p50')
    expect(p50.beats_baseline).toBe(true)
    expect(p50.quantile_alpha).toBe(0.5)
  })

  it('annotates cohort beats_baseline correctly', () => {
    const result = transform(MINIMAL_CARD)
    // first cohort: model=0.23 > baseline=0.22 -> does NOT beat (pinball lower-is-better)
    expect(result.cohorts[0].beats_baseline).toBe(false)
    // second cohort: model=0.20 < baseline=0.24 -> beats
    expect(result.cohorts[1].beats_baseline).toBe(true)
  })

  it('extracts importance entries', () => {
    const result = transform(MINIMAL_CARD)
    expect(result.importance).toHaveLength(1)
    expect(result.importance[0].model).toBe('degradation_regressor_p50')
    expect(result.importance[0].shap_top5[0]).toBe('push_residual')
  })

  it('passes through calibration unchanged', () => {
    const result = transform(MINIMAL_CARD)
    expect(result.calibration.nominal).toBe(0.8)
    expect(result.calibration.n).toBe(18000)
  })

  it('passes through limitations array', () => {
    const result = transform(MINIMAL_CARD)
    expect(result.limitations).toHaveLength(1)
  })
})

describe('metricDirectionLabel', () => {
  it('classifies pinball as lower-is-better', () => {
    expect(metricDirectionLabel('pinball')).toBe('lower')
  })
  it('classifies rmse as lower-is-better', () => {
    expect(metricDirectionLabel('rmse')).toBe('lower')
  })
  it('classifies macro_f1 as higher-is-better', () => {
    expect(metricDirectionLabel('macro_f1')).toBe('higher')
  })
})

describe('modelBeatsBaselineDescription', () => {
  it('computes improvement % for lower-is-better metrics', () => {
    const m = MINIMAL_CARD.model_card.models[0]
    const desc = modelBeatsBaselineDescription({
      ...m,
      kind: 'quantile',
    })
    // (0.22-0.19) / 0.22 * 100 = 13.6%
    expect(desc).toMatch(/13\.6%/)
  })

  it('computes improvement % for higher-is-better metrics', () => {
    const m = MINIMAL_CARD.model_card.models[1]
    const desc = modelBeatsBaselineDescription({
      ...m,
      kind: 'classification',
    })
    // (0.37-0.18) / 0.18 * 100 = 105.6%
    expect(desc).toMatch(/105\.6%/)
  })
})
