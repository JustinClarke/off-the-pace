// Lazy-creates and caches one onnxruntime-web InferenceSession per model (AD-3).
// ort's WASM binaries are self-hosted under /ort/ (see scripts/copy-runtime-assets.mjs)
// so COEP `require-corp` (AD-11) doesn't block them; threads work when the page is
// cross-origin-isolated, and degrade to single-threaded otherwise.

import * as ort from 'onnxruntime-web'
import { loadModelManifest, getModelSpec, MODELS_BASE } from './manifest'

let configured = false

function configureOrt(): void {
  if (configured) return
  ort.env.wasm.wasmPaths = '/ort/'
  // Use threads only when the runtime can (cross-origin isolated → SharedArrayBuffer).
  const isolated = typeof globalThis !== 'undefined' && (globalThis as { crossOriginIsolated?: boolean }).crossOriginIsolated
  ort.env.wasm.numThreads = isolated
    ? Math.min(4, (globalThis.navigator?.hardwareConcurrency ?? 4))
    : 1
  configured = true
}

const sessions = new Map<string, Promise<ort.InferenceSession>>()

/** Get (creating + caching on first use) the InferenceSession for a named model. */
export function getSession(modelName: string): Promise<ort.InferenceSession> {
  const existing = sessions.get(modelName)
  if (existing) return existing

  const created = (async () => {
    configureOrt()
    const manifest = await loadModelManifest()
    const spec = getModelSpec(manifest, modelName)
    const url = `${MODELS_BASE}/${spec.onnx}`
    return ort.InferenceSession.create(url, {
      executionProviders: ['wasm'],
      graphOptimizationLevel: 'all',
    })
  })()

  // Don't cache a rejected promise let the next call retry a transient load failure.
  created.catch(() => sessions.delete(modelName))
  sessions.set(modelName, created)
  return created
}

/** Test/teardown helper: drop all cached sessions. */
export function resetSessions(): void {
  sessions.clear()
  runQueue = Promise.resolve()
}

// ort's InferenceSession.run() rejects with "Session already started" if a run is already in
// flight on the threaded WASM build's single shared proxy worker-even for a *different* session.
// So overlapping run() calls (the simulator re-scoring all five models on every slider move, plus
// React StrictMode double-invoking effects in dev) must be serialized GLOBALLY, not per model.
// We chain every run onto one queue so exactly one run() is ever outstanding against the worker.
let runQueue: Promise<unknown> = Promise.resolve()

/**
 * Run `session.run(feeds)` serialized against every other in-flight run (global queue, because the
 * threaded proxy worker is a single shared resource). Returns the run's output map. Preserves call
 * order; a rejected run does not poison the queue for subsequent calls.
 */
export function runSerial(
  _modelName: string,
  session: ort.InferenceSession,
  feeds: Record<string, ort.Tensor>,
): Promise<ort.InferenceSession.OnnxValueMapType> {
  const next = runQueue.catch(() => {}).then(() => session.run(feeds))
  runQueue = next.catch(() => {}) // keep the chain alive across failures
  return next
}

export { ort }
