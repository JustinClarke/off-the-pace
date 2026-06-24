// Core Web Vitals → the metric sink.
// web-vitals is dynamically imported so it's only fetched when RUM is enabled. LCP/INP/CLS are
// the headline vitals; FCP/TTFB add load-path context. App-specific timings (DuckDB init, first
// query, ONNX warmup) are emitted separately via track() at their call sites.

import { isRumEnabled, track } from './index'

interface Vital {
  name: string
  value: number
  rating: string
  id: string
}

export async function reportWebVitals(): Promise<void> {
  if (!isRumEnabled()) return
  try {
    const { onLCP, onINP, onCLS, onFCP, onTTFB } = await import('web-vitals')
    const emit = (m: Vital) =>
      track(`web_vital.${m.name}`, m.value, m.name === 'CLS' ? 'none' : 'millisecond', {
        rating: m.rating,
        id: m.id,
      })
    onLCP(emit)
    onINP(emit)
    onCLS(emit)
    onFCP(emit)
    onTTFB(emit)
  } catch (err) {
    console.warn('[observability] web-vitals load failed', err)
  }
}
