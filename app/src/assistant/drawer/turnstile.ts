// AX-14: Cloudflare Turnstile token source. A token is single-use and only round 1 of a question needs one, so the
// chat asks for a fresh token per question. No site key = no widget (local development against a Worker run with
// TURNSTILE_ENABLED=false). The script comes from challenges.cloudflare.com, which the CSP change in AX-12 allows
// (script-src and frame-src); it was NOT loaded against the real service in this build (no network calls).
import { TurnstileFailure } from './useChat'

interface TurnstileApi {
  render(el: HTMLElement, o: Record<string, unknown>): string
  execute(id: string): void
  reset(id: string): void
}

declare global {
  interface Window {
    turnstile?: TurnstileApi
  }
}

const SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
let script: Promise<TurnstileApi> | null = null

function loadScript(): Promise<TurnstileApi> {
  if (window.turnstile) return Promise.resolve(window.turnstile)
  if (!script) {
    script = new Promise((resolve, reject) => {
      const s = document.createElement('script')
      s.src = SRC
      s.async = true
      s.onload = () => (window.turnstile ? resolve(window.turnstile) : reject(new TurnstileFailure('turnstile missing')))
      s.onerror = () => {
        script = null
        reject(new TurnstileFailure('turnstile script failed'))
      }
      document.head.appendChild(s)
    })
  }
  return script
}

export interface TurnstileSource {
  getToken(): Promise<string | undefined>
  /** Ref callback for the mount element. */
  attach(el: HTMLElement | null): void
}

export function createTurnstile(siteKey: string, timeoutMs = 30_000): TurnstileSource {
  let widget: string | null = null
  let container: HTMLElement | null = null
  let pending: { resolve(t: string): void; reject(e: Error): void } | null = null
  return {
    attach(el) {
      container = el
    },
    async getToken() {
      if (!siteKey) return undefined
      const api = await loadScript()
      const el = container
      if (!el) throw new TurnstileFailure('no container')
      if (widget === null) {
        widget = api.render(el, {
          sitekey: siteKey,
          execution: 'execute',
          appearance: 'interaction-only',
          callback: (t: string) => pending?.resolve(t),
          'error-callback': () => pending?.reject(new TurnstileFailure('turnstile error')),
          'expired-callback': () => undefined,
        })
      } else {
        api.reset(widget)
      }
      const id = widget
      return new Promise<string>((resolve, reject) => {
        const timer = setTimeout(() => reject(new TurnstileFailure('turnstile timeout')), timeoutMs)
        pending = {
          resolve: (t) => (clearTimeout(timer), resolve(t)),
          reject: (e) => (clearTimeout(timer), reject(e)),
        }
        api.execute(id)
      })
    },
  }
}
