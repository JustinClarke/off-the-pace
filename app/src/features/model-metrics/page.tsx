import { useState, useEffect } from 'react'
import FeaturePage from '../../ui/layout/FeaturePage'
import ModelMetricsChart from './ModelMetricsChart'
import { methodologyContent, methodologyHref } from './methodology'
import { transform, toCsvRows } from './transform'
import type { ModelMetricsResult } from './transform'
import { MODELS_BASE } from '../../ml/manifest'

const MODEL_CARD_URL = `${MODELS_BASE}/model_card.json`

export default function ModelMetricsPage() {
  const [result, setResult] = useState<ModelMetricsResult | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    fetch(MODEL_CARD_URL)
      .then(r => {
        if (!r.ok) throw new Error(`Failed to load model card: ${r.status}`)
        return r.json()
      })
      .then(raw => {
        if (!cancelled) {
          setResult(transform(raw))
          setIsLoading(false)
        }
      })
      .catch(err => {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)))
          setIsLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [])

  return (
    <FeaturePage
      title="ML Model Metrics"
      hook="Every number here is read from model_card.json a machine-generated audit trail. Five XGBoost models, all beating their per-cohort baseline, trained on 110k laps of real F1 data."
      badges={[
        {
          label: 'What It Means',
          content: "The degradation trio (p10/p50/p90) predicts how much pace a tyre will lose next lap. The cliff classifier catches the window before a tyre falls off a cliff. Stint life estimates how many laps remain.",
        },
        {
          label: 'Why It Matters',
          content: "Every fitted number traces to a tracked artefact and beats a strong baseline. The 2025 season is the true held-out blind test this page shows results on the 2024 CV fold until that data ingests.",
        },
        {
          label: "How It's Calculated",
          content: "Season-grouped TimeSeriesSplit (5 folds, expanding window). Final fold = 2024 data. Baselines are per-cohort group-means / majority-class priors. Calibration: conformal coverage targeting 80% at nominal.",
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={result ? {
        fitDate: result.generated_at.slice(0, 10),
        dataWindow: result.training_seasons.join(', '),
        nObs: result.n_training_rows,
        modelVersion: result.version,
        datasetFingerprint: result.dataset_fingerprint,
      } : undefined}
      csvRows={result ? toCsvRows(result) : undefined}
      csvFilename="ml-model-metrics.csv"
      isLoading={isLoading}
      error={error}
      isEmpty={result?.models.length === 0}
    >
      {result && <ModelMetricsChart result={result} />}
    </FeaturePage>
  )
}
