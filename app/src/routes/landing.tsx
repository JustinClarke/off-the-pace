// Product home stats from manifest JSON (zero SQL), fire-and-forget DuckDB warm-up on mount (AD-12).
import { Link } from 'react-router-dom'
import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { pillars } from '../nav/pillars'
import { FEATURE_FLAGS, APP_CONFIG } from '../config'
import type { DataManifest } from '../data/manifest'
import { DATA_CDN_BASE } from '../data/manifest'

function useManifestStats() {
  return useQuery<DataManifest>({
    queryKey: ['manifest'],
    queryFn: () => fetch(`${DATA_CDN_BASE}/data/_manifest.json`).then(r => r.json()),
    staleTime: Infinity,
  })
}

function StatPill({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="flex flex-col items-center px-6 py-3">
      <span className="text-2xl font-bold tabular-nums">{typeof value === 'number' ? value.toLocaleString() : value}</span>
      <span className="text-xs text-muted mt-0.5">{label}</span>
    </div>
  )
}

export default function Landing() {
  // Fire-and-forget DuckDB warm-up starts the download while user reads the home page (AD-12).
  useEffect(() => {
    import('../data/duckdb/client').then(m => m.getConnection()).catch(() => {/* silently warm up */})
  }, [])

  const { data: manifest } = useManifestStats()
  const stats = manifest?.stats

  const visiblePillars = pillars.filter(
    p =>
      p.id !== 'home' &&
      (!p.featureFlag || FEATURE_FLAGS[p.featureFlag as keyof typeof FEATURE_FLAGS])
  )

  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      {/* Hero */}
      <header className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight mb-3">Off The Pace</h1>
        <p className="text-muted max-w-2xl leading-relaxed">
          Causal lap time decomposition for Formula 1. A seven-term additive identity, enforced
          by CI on every lap. Ghost car counterfactuals. Tyre cliff survival models. Live ONNX
          inference. Everything runs in your browser no backend, no cost.
        </p>
        <div className="flex flex-wrap gap-3 mt-6">
          <a
            href={APP_CONFIG.githubUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm px-4 py-2 rounded-md border border-border text-muted hover:text-[rgb(var(--color-text))] transition-colors"
          >
            GitHub →
          </a>
          <a
            href="https://off-the-pace.onrender.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm px-4 py-2 rounded-md border border-border text-muted hover:text-[rgb(var(--color-text))] transition-colors"
          >
            Methodology →
          </a>
          <a
            href="https://justinclarke.github.io"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm px-4 py-2 rounded-md border border-border text-muted hover:text-[rgb(var(--color-text))] transition-colors"
          >
            Portfolio →
          </a>
        </div>
      </header>

      {/* Stats strip from manifest JSON, zero SQL */}
      {stats && (
        <div className="flex flex-wrap divide-x divide-border border border-border rounded-lg mb-10 overflow-hidden">
          <StatPill value={stats.total_laps} label="laps decomposed" />
          <StatPill value={stats.dbt_models} label="dbt models" />
          <StatPill value={stats.ml_models + '/5'} label="ML models beat baseline" />
          <StatPill value={stats.seasons} label="seasons" />
        </div>
      )}

      {/* Pillar tiles */}
      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted mb-4">
          Analysis Pillars
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {visiblePillars.map(pillar => (
            <Link
              key={pillar.id}
              to={pillar.path}
              className="group flex items-start gap-3 p-4 rounded-lg border border-border bg-surface hover:border-[rgb(var(--color-accent))] transition-colors"
            >
              <span className="text-xl mt-0.5">{pillar.icon}</span>
              <div>
                <p className="text-sm font-medium group-hover:text-accent transition-colors">
                  {pillar.label}
                </p>
                <p className="text-xs text-muted mt-0.5">{pillar.description}</p>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
