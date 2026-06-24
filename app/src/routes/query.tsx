// Query Lab an in-browser SQL workbench over the gold warehouse. Everything runs client-side
// via DuckDB-Wasm: SQL editor, schema explorer, dynamic results grid, CSV export. Read-only.
import { useCallback, useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { runLabQuery, QueryLabError, type LabResult } from '../data/duckdb/queryLab'
import { loadManifest, type DataManifest } from '../data/manifest'
import { useDatabaseStatus } from '../data/hooks/useDatabaseStatus'
import { downloadCsv } from '../lib/csv'
import { getSearchParam, setSearchParam } from '../lib/url'
import { preferences, pushQueryHistory } from '../state/preferences'
import { EXAMPLES } from '../features/query-lab/examples'
import SchemaExplorer from '../features/query-lab/SchemaExplorer'
import ResultGrid from '../features/query-lab/ResultGrid'

const DEFAULT_SQL = `SELECT compound,
       count(*) AS stints,
       round(avg(end_of_stint_pace_falloff_s_per_lap), 4) AS avg_deg_per_lap
FROM fct_stint_features
WHERE compound IS NOT NULL
GROUP BY compound
ORDER BY avg_deg_per_lap DESC`

function encodeSql(sql: string): string {
  return btoa(encodeURIComponent(sql))
}
function decodeSql(b64: string): string | null {
  try {
    return decodeURIComponent(atob(b64))
  } catch {
    return null
  }
}

const rise = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0 },
}

function EngineDot({ status }: { status: string }) {
  if (status === 'error') {
    return <span className="h-1.5 w-1.5 rounded-full bg-red-400" aria-hidden />
  }
  if (status === 'ready') {
    return (
      <span className="relative flex h-1.5 w-1.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[rgb(var(--color-accent))] opacity-75" />
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[rgb(var(--color-accent))]" />
      </span>
    )
  }
  return <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-muted" aria-hidden />
}

function PanelKicker({ children }: { children: React.ReactNode }) {
  return <span className="font-mono text-[9px] uppercase tracking-widest text-muted">{children}</span>
}

export default function QueryLab() {
  const reduce = useReducedMotion()
  const { status } = useDatabaseStatus()
  const [manifest, setManifest] = useState<DataManifest | null>(null)
  const [sql, setSql] = useState<string>(() => {
    const q = getSearchParam('q')
    return (q && decodeSql(q)) || DEFAULT_SQL
  })
  const [result, setResult] = useState<LabResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [history, setHistory] = useState<string[]>(() => preferences.queryHistory)
  const editorRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    loadManifest().then(setManifest).catch(() => {})
    // Warm the engine up in the background.
    import('../data/duckdb/client').then(m => m.getConnection()).catch(() => {})
  }, [])

  const run = useCallback(async () => {
    if (running) return
    setRunning(true)
    setError(null)
    try {
      const res = await runLabQuery(sql)
      setResult(res)
      pushQueryHistory(sql)
      setHistory(preferences.queryHistory)
    } catch (e) {
      setResult(null)
      if (e instanceof QueryLabError) setError(e.message)
      else setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }, [sql, running])

  // Insert text at the cursor in the editor (used by schema rail + examples).
  const insertAtCursor = useCallback((text: string) => {
    const el = editorRef.current
    if (!el) {
      setSql(s => `${s} ${text}`)
      return
    }
    const start = el.selectionStart ?? sql.length
    const end = el.selectionEnd ?? sql.length
    const next = sql.slice(0, start) + text + sql.slice(end)
    setSql(next)
    requestAnimationFrame(() => {
      el.focus()
      const pos = start + text.length
      el.setSelectionRange(pos, pos)
    })
  }, [sql])

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      run()
    }
  }

  function share() {
    const url = setSearchParam('q', encodeSql(sql))
    window.history.replaceState(null, '', url)
    navigator.clipboard?.writeText(window.location.href).catch(() => {})
  }

  const ghostBtn =
    'rounded-lg border border-border px-2.5 py-1.5 text-[11px] font-medium text-muted transition-colors hover:border-[rgb(var(--color-accent))] hover:text-[rgb(var(--color-text))]'

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-4 sm:px-6 lg:h-[calc(100vh-3.5rem)]">
      {/* Header band */}
      <header className="relative shrink-0 overflow-hidden rounded-xl border border-border/60 bg-gradient-to-br from-surface to-surface/40 px-5 py-3.5">
        <span aria-hidden className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-transparent via-[rgb(var(--color-accent))] to-transparent opacity-80" />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="mb-1 flex items-center gap-2">
              <EngineDot status={status} />
              <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-[rgb(var(--color-accent))]">
                {status === 'ready' ? 'engine ready' : status === 'error' ? 'engine error' : status === 'initializing' ? 'booting engine…' : 'engine idle'}
              </span>
            </div>
            <h1 className="text-xl font-extrabold tracking-tight">Query Lab</h1>
            <p className="mt-0.5 text-[12px] text-muted">
              Write SQL against the gold warehouse. {manifest?.tables.length ?? 36} tables, all client-side.
            </p>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[rgb(var(--color-accent))]/20 bg-[rgb(var(--color-accent))]/5 px-2.5 py-1 font-mono text-[9px] uppercase tracking-widest text-[rgb(var(--color-accent))]">
            runs in your browser
          </span>
        </div>
      </header>

      {/* Body: schema rail + editor/results */}
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-[220px_minmax(0,1fr)]">
        {/* Schema rail */}
        <aside className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-border bg-surface">
          <div className="shrink-0 border-b border-border px-3 py-2">
            <PanelKicker>schema</PanelKicker>
          </div>
          <div className="min-h-0 flex-1 overflow-auto p-3">
            {manifest ? (
              <SchemaExplorer manifest={manifest} onInsert={insertAtCursor} />
            ) : (
              <p className="text-[11px] text-muted">loading schema…</p>
            )}
          </div>
        </aside>

        {/* Editor + results */}
        <motion.div
          variants={reduce ? undefined : rise}
          initial={reduce ? undefined : 'hidden'}
          animate={reduce ? undefined : 'show'}
          className="flex min-h-0 flex-col gap-3"
        >
          {/* Editor card */}
          <div className="flex shrink-0 flex-col overflow-hidden rounded-xl border border-[rgb(var(--color-accent))]/30 bg-surface">
            <span aria-hidden className="h-[1.5px] bg-gradient-to-r from-transparent via-[rgb(var(--color-accent))] to-transparent" />
            <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
              <PanelKicker>editor</PanelKicker>
              <span className="font-mono text-[9px] uppercase tracking-widest text-muted/70">⌘⏎ to run</span>
            </div>
            <textarea
              ref={editorRef}
              value={sql}
              onChange={e => setSql(e.target.value)}
              onKeyDown={onKeyDown}
              spellCheck={false}
              rows={8}
              className="w-full resize-y bg-transparent px-3 py-2.5 font-mono text-[12.5px] leading-relaxed text-[rgb(var(--color-text))] outline-none placeholder:text-muted/50"
              placeholder="SELECT * FROM dim_circuits LIMIT 10"
            />
            <div className="flex flex-wrap items-center gap-2 border-t border-border px-3 py-2">
              <button
                onClick={run}
                disabled={running}
                className="group inline-flex items-center gap-1 rounded-lg bg-[rgb(var(--color-accent))] px-3 py-1.5 text-[11px] font-semibold text-white transition-transform hover:scale-[1.04] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {running ? 'Running…' : 'Run'}
                <svg width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden>
                  <path d="M2 7h9M7 3l4 4-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              <button onClick={() => { setSql(''); editorRef.current?.focus() }} className={ghostBtn}>Clear</button>
              <button onClick={share} className={ghostBtn}>Share link</button>
              <div className="relative">
                <button onClick={() => setShowHistory(v => !v)} className={ghostBtn} disabled={!history.length}>
                  History ▾
                </button>
                {showHistory && history.length > 0 && (
                  <div className="absolute left-0 top-full z-20 mt-1 max-h-72 w-80 overflow-auto rounded-lg border border-border bg-surface p-1 shadow-xl">
                    {history.map((h, i) => (
                      <button
                        key={i}
                        onClick={() => { setSql(h); setShowHistory(false) }}
                        className="block w-full truncate rounded px-2 py-1 text-left font-mono text-[10px] text-muted hover:bg-white/[0.04] hover:text-[rgb(var(--color-text))]"
                        title={h}
                      >
                        {h.replace(/\s+/g, ' ')}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Readout */}
              <div className="ml-auto flex items-center gap-3 font-mono text-[11px] tabular-nums text-muted">
                {result && (
                  <>
                    <span>{result.rowCount.toLocaleString()}{result.truncated ? '+' : ''} rows</span>
                    <span aria-hidden className="text-muted/30">·</span>
                    <span>{result.elapsedMs.toFixed(0)} ms</span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Examples */}
          <div className="flex shrink-0 flex-wrap items-center gap-1.5">
            <span className="font-mono text-[9px] uppercase tracking-widest text-muted/70">examples</span>
            {EXAMPLES.map(ex => (
              <button
                key={ex.label}
                onClick={() => { setSql(ex.sql); editorRef.current?.focus() }}
                className="rounded-full border border-border px-2.5 py-1 text-[10px] text-muted transition-colors hover:border-[rgb(var(--color-accent))] hover:text-[rgb(var(--color-text))]"
              >
                {ex.label}
              </button>
            ))}
          </div>

          {/* Results card */}
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-surface">
            <div className="flex shrink-0 items-center justify-between border-b border-border px-3 py-1.5">
              <PanelKicker>results</PanelKicker>
              {result && result.rows.length > 0 && (
                <button
                  onClick={() => downloadCsv('query-lab-export.csv', result.rows)}
                  className={ghostBtn}
                >
                  Export CSV
                </button>
              )}
            </div>
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              {error ? (
                <div className="m-3 rounded border border-red-500/20 bg-red-500/5 p-4 text-sm">
                  <p className="mb-1 font-medium text-red-400">Query failed</p>
                  <p className="font-mono text-xs text-muted">{error}</p>
                </div>
              ) : result ? (
                <ResultGrid result={result} />
              ) : (
                <p className="px-4 py-8 text-center text-sm text-muted">
                  Write a query and press <span className="font-mono text-[rgb(var(--color-text))]">⌘⏎</span> to run.
                </p>
              )}
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
