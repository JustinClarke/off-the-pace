// AX-14: the mount point for the Turnstile widget (interaction-only: it shows only if Cloudflare needs a click).
import { forwardRef } from 'react'

const TurnstileGate = forwardRef<HTMLDivElement>(function TurnstileGate(_props, ref) {
  return <div ref={ref} className="min-h-0" data-testid="turnstile-mount" aria-live="polite" />
})

export default TurnstileGate
