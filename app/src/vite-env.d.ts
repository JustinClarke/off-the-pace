/// <reference types="vite/client" />

// Observability + data-plane env vars. All optional 
// the app runs fully with none set; telemetry simply stays off.
interface ImportMetaEnv {
  /** Existing: overrides the GCS CDN base ("" = same-origin offline dev). */
  readonly VITE_DATA_BASE?: string
  /** Sentry DSN. Error tracking + RUM stay OFF entirely until this is set. */
  readonly VITE_SENTRY_DSN?: string
  /** Sentry environment label (defaults to import.meta.env.MODE). */
  readonly VITE_SENTRY_ENVIRONMENT?: string
  /** Sentry tracing sample rate, 0–1 (default 0 = no performance traces). */
  readonly VITE_SENTRY_TRACES_SAMPLE_RATE?: string
  /** Release identifier reported to Sentry / used for source-map association. */
  readonly VITE_APP_RELEASE?: string
  /** Optional privacy-respecting RUM beacon endpoint (JSON via navigator.sendBeacon). */
  readonly VITE_RUM_ENDPOINT?: string
  /** RUM sampling rate, 0–1 (default 1 = send every metric). */
  readonly VITE_RUM_SAMPLE_RATE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
