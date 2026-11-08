// AX-14: the build-time switch and the Worker address. There is no runtime flag mechanism in the app,
// so the assistant is on only when a build sets VITE_ASSISTANT_ENABLED=true (default: off). With it off,
// AppShell never imports the drawer, nothing renders, and nothing is fetched.
export function assistantEnabled(): boolean {
  return import.meta.env.VITE_ASSISTANT_ENABLED === 'true'
}

/** The Worker chat endpoint (POST). Empty = not configured: the drawer says so instead of calling anything. */
export function workerUrl(): string {
  return (import.meta.env.VITE_ASSISTANT_WORKER_URL ?? '').trim()
}

/** Cloudflare Turnstile site key (public). Empty = no widget (local development against a Worker with TURNSTILE_ENABLED=false). */
export function turnstileSiteKey(): string {
  return (import.meta.env.VITE_TURNSTILE_SITE_KEY ?? '').trim()
}
