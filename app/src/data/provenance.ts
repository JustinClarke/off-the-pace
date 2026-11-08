// AP-02: provenance for the page footer, read from the manifests, never hard-coded.
// A field is undefined until its manifest loads, and stays undefined if the load fails,
// so the footer omits it rather than showing a stale literal.
import { useEffect, useState } from 'react'
import { loadManifest } from './manifest'
import type { DataManifest } from './manifest'
import { loadModelManifest } from '../ml/manifest'
import type { ModelManifest } from '../ml/manifest'

export interface ProvenanceInfo {
  /** Seasons covered, from manifest stats.seasons, e.g. "2018–2025" */
  dataWindow?: string
  /** Data build id, from manifest version */
  dataVersion?: string
  generatedAt?: string
  /** TX-05 label version, e.g. "v16"; absent until the re-export carries it */
  labelVersion?: string
  /** Model version without the leading "v" (rendered with one), only when `models` was requested */
  modelVersion?: string
  datasetFingerprint?: string
  /** Largest ONNX-vs-booster abs difference, formatted, from the model manifest */
  onnxParityMaxAbs?: string
}

const nonEmpty = (v: unknown): string | undefined =>
  typeof v === 'string' && v.trim() !== '' ? v : undefined

export function deriveProvenance(
  data: DataManifest | null | undefined,
  models?: ModelManifest | null,
): ProvenanceInfo {
  const out: ProvenanceInfo = {}
  if (data) {
    out.dataWindow = nonEmpty(data.stats?.seasons)
    out.dataVersion = nonEmpty(data.version)
    out.generatedAt = nonEmpty(data.generatedAt)
    out.labelVersion = nonEmpty(data.provenance?.label_version)
  }
  if (models) {
    out.modelVersion = nonEmpty(models.model_version)?.replace(/^v/, '')
    out.datasetFingerprint = nonEmpty(models.provenance?.dataset_fingerprint)
    const diffs = Object.values(models.provenance?.onnx_parity?.max_abs_diff ?? {})
      .filter((n): n is number => typeof n === 'number' && Number.isFinite(n))
    if (diffs.length) out.onnxParityMaxAbs = Math.max(...diffs).toExponential(1)
  }
  return out
}

/** Loads the data manifest (and the model manifest when `opts.models`) once and derives the footer fields. */
export function useProvenance(opts: { models?: boolean } = {}): ProvenanceInfo {
  const wantModels = opts.models === true
  const [state, setState] = useState<{ data: DataManifest | null; models: ModelManifest | null }>({
    data: null,
    models: null,
  })

  useEffect(() => {
    let cancelled = false
    loadManifest().then(
      data => { if (!cancelled) setState(s => ({ ...s, data })) },
      () => { /* footer omits the fields */ },
    )
    if (wantModels) {
      loadModelManifest().then(
        models => { if (!cancelled) setState(s => ({ ...s, models })) },
        () => { /* footer omits the fields */ },
      )
    }
    return () => { cancelled = true }
  }, [wantModels])

  return deriveProvenance(state.data, wantModels ? state.models : null)
}
