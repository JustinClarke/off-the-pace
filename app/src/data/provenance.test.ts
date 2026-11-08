import { describe, it, expect } from 'vitest'
import { deriveProvenance } from './provenance'
import type { DataManifest } from './manifest'
import type { ModelManifest } from '../ml/manifest'

const data = {
  version: '30f91247d7cb651e',
  generatedAt: '2026-11-01T00:00:00Z',
  stats: { seasons: '2018–2025' },
  tables: [],
} as unknown as DataManifest

const models = {
  model_version: 'v14',
  provenance: {
    dataset_fingerprint: '5dbd8e51502a0000',
    onnx_parity: { max_abs_diff: { a: 9.5e-6, b: 8.7e-5 } },
  },
} as unknown as ModelManifest

describe('deriveProvenance', () => {
  it('maps the manifests to the footer fields', () => {
    expect(deriveProvenance(data, models)).toEqual({
      dataWindow: '2018–2025',
      dataVersion: '30f91247d7cb651e',
      generatedAt: '2026-11-01T00:00:00Z',
      labelVersion: undefined,
      modelVersion: '14',
      datasetFingerprint: '5dbd8e51502a0000',
      onnxParityMaxAbs: '8.7e-5',
    })
  })

  it('carries the label version once the data manifest has it', () => {
    const d = { ...data, provenance: { label_version: 'v16' } } as DataManifest
    expect(deriveProvenance(d).labelVersion).toBe('v16')
  })

  it('returns undefined fields when a load failed', () => {
    const out = deriveProvenance(null, null)
    expect(Object.values(out).every(v => v === undefined)).toBe(true)
    const modelsOnly = deriveProvenance(data, null)
    expect(modelsOnly.modelVersion).toBeUndefined()
    expect(modelsOnly.datasetFingerprint).toBeUndefined()
    expect(modelsOnly.dataWindow).toBe('2018–2025')
  })
})
