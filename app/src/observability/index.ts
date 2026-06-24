// Vendor-neutral observability facade.
//
// No-op until configured. Error tracking activates only when VITE_SENTRY_DSN is set; RUM
// metrics are emitted only when a DSN or a VITE_RUM_ENDPOINT beacon target exists. The Sentry
// SDK is *dynamically* imported, so it ships as a separate chunk fetched solely when a DSN is
// present the default (telemetry-off) build pays zero bundle cost for it.
//
// Telemetry must never break the app: every path here swallows its own errors.

type SentryModule = typeof import('@sentry/react')

const env = import.meta.env
const DSN = env.VITE_SENTRY_DSN
const RUM_ENDPOINT = env.VITE_RUM_ENDPOINT
const SAMPLE_RATE = clamp01(Number(env.VITE_RUM_SAMPLE_RATE ?? '1'))
const ENVIRONMENT = env.VITE_SENTRY_ENVIRONMENT ?? env.MODE
const RELEASE = env.VITE_APP_RELEASE

let sentry: SentryModule | null = null
let initStarted = false

function clamp01(n: number): number {
  return Number.isFinite(n) ? Math.min(1, Math.max(0, n)) : 1
}

export function isErrorTrackingEnabled(): boolean {
  return Boolean(DSN)
}

export function isRumEnabled(): boolean {
  return Boolean(DSN || RUM_ENDPOINT)
}

/** Initialise error tracking. Idempotent; safe to call before render. No-op without a DSN. */
export async function initObservability(): Promise<void> {
  if (initStarted || !DSN) return
  initStarted = true
  try {
    const Sentry = await import('@sentry/react')
    Sentry.init({
      dsn: DSN,
      environment: ENVIRONMENT,
      release: RELEASE,
      tracesSampleRate: clamp01(Number(env.VITE_SENTRY_TRACES_SAMPLE_RATE ?? '0')),
      sendDefaultPii: false, // privacy-respecting: no IP / user identifiers
    })
    sentry = Sentry
  } catch (err) {
    // Telemetry is best-effort; a failed SDK load must not take down the page.
    console.warn('[observability] Sentry init failed; continuing without it', err)
  }
}

/** Report a handled/boundary error. Falls back to console when tracking is off or not ready. */
export function captureException(error: unknown, context?: Record<string, unknown>): void {
  if (sentry) {
    sentry.captureException(error, context ? { extra: context } : undefined)
  } else {
    console.error('[observability]', error, context ?? '')
  }
}

function sampled(): boolean {
  return Math.random() < SAMPLE_RATE
}

export interface PerfMark {
  name: string
  value: number
  unit: 'millisecond' | 'none'
  ts: number
}

// Always-on, in-memory ring of the most recent timing marks recorded regardless of whether a RUM
// backend is configured. The default (telemetry-off) build still captures duckdb_init / first_query /
// onnx_warmup / web-vitals here, so the Playwright E2E + synthetic checks and devtools can verify the
// heavy client subsystems actually fired with finite values (exposed read-only on window.__OTP_PERF__).
// No PII, length-capped, best-effort never throws and pays no network cost.
const PERF_RING_MAX = 128
const perfRing: PerfMark[] = []

function recordMark(mark: PerfMark): void {
  try {
    perfRing.push(mark)
    if (perfRing.length > PERF_RING_MAX) perfRing.shift()
    if (typeof window !== 'undefined') {
      ;(window as unknown as { __OTP_PERF__?: PerfMark[] }).__OTP_PERF__ = perfRing
    }
  } catch {
    /* never throw from telemetry */
  }
}

/** Snapshot of the perf-mark ring (most-recent last). Consumed by the E2E suite and devtools. */
export function getPerfMarks(): PerfMark[] {
  return perfRing.slice()
}

/**
 * Generic metric/timing sink. Routes to (1) the beacon endpoint if configured and (2) Sentry
 * as a breadcrumb. Both app timings (duckdb_init, first_query, onnx_warmup) and Core Web Vitals
 * flow through here. Drops non-finite values and respects VITE_RUM_SAMPLE_RATE. Every finite mark is
 * also recorded to the in-memory ring (above) before the RUM gate, so it is observable even with
 * telemetry off.
 */
export function track(
  name: string,
  value: number,
  unit: 'millisecond' | 'none' = 'millisecond',
  attrs?: Record<string, string | number>,
): void {
  if (!Number.isFinite(value)) return
  recordMark({ name, value, unit, ts: Date.now() })
  if (!isRumEnabled() || !sampled()) return
  const payload = { name, value, unit, ...attrs, ts: Date.now() }
  if (RUM_ENDPOINT && typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
    try {
      navigator.sendBeacon(RUM_ENDPOINT, JSON.stringify(payload))
    } catch {
      /* ignore never throw from telemetry */
    }
  }
  if (sentry) {
    sentry.addBreadcrumb({ category: 'metric', message: name, level: 'info', data: payload })
  }
}

/** Time an async operation and emit its duration as a metric. Returns the operation's result. */
export async function timed<T>(
  name: string,
  fn: () => Promise<T>,
  attrs?: Record<string, string | number>,
): Promise<T> {
  const t0 = now()
  try {
    return await fn()
  } finally {
    track(name, now() - t0, 'millisecond', attrs)
  }
}

function now(): number {
  return typeof performance !== 'undefined' ? performance.now() : Date.now()
}
