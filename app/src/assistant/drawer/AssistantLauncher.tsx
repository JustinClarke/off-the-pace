// AX-14: the entry point AppShell lazy-loads only when the build flag is on. Holds the conversation (so closing
// the drawer keeps it), the opener button, and the Turnstile token source. Everything heavy (DuckDB, the card
// parquet, the registry) loads on the first question, not here.
import { useMemo, useState } from 'react'
import type { PageContext } from '../core/preload'
import { routeParams } from '../../nav/routeParams'
import ChatDrawer from './ChatDrawer'
import { turnstileSiteKey, workerUrl } from './flag'
import { createTurnstile } from './turnstile'
import { useChat } from './useChat'

// The page the visitor is on when the question is sent (read at send time, from the address bar).
function getPage(): PageContext | null {
  const route = window.location.pathname
  if (!routeParams[route]) return null
  const params: Record<string, string> = {}
  new URLSearchParams(window.location.search).forEach((v, k) => {
    params[k] = v
  })
  return { route, params }
}

const loadRuntime = () => import('./runtime').then((m) => m.loadDrawerRuntime())

export default function AssistantLauncher() {
  const [open, setOpen] = useState(false)
  const turnstile = useMemo(() => createTurnstile(turnstileSiteKey()), [])
  const chat = useChat({ endpoint: workerUrl(), loadRuntime, getTurnstileToken: () => turnstile.getToken(), getPage })

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={open}
        className="fixed bottom-4 right-4 z-30 min-h-11 rounded-full border border-border bg-surface px-4 text-sm font-medium shadow-lg hover:text-accent focus-visible:outline focus-visible:outline-2"
      >
        Ask
      </button>
      <ChatDrawer open={open} onClose={() => setOpen(false)} chat={chat} turnstileRef={turnstile.attach} />
    </>
  )
}
