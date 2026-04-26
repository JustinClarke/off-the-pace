// Product home-a bento-grid showcase of the shipped features (Wave 1 + Wave 2).
// Stats come from the manifest JSON (zero SQL); a fire-and-forget DuckDB warm-up boots
// the engine in the background while the visitor browses (AD-12). Heavy on motion: the
// brief was "go crazy". Only features that actually render real data appear here.
import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion, useReducedMotion } from 'framer-motion'
import { APP_CONFIG } from '../../config'
import type { DataManifest } from '../../data/manifest'
import { DATA_CDN_BASE } from '../../data/manifest'
import BentoTile, { type BentoFeature } from './BentoTile'
import {
  GhostCarViz, SurvivalViz, WaterfallViz, EraRatingsViz, PitGanttViz,
  ScatterViz, QuantileFanViz, BlindTestViz,
} from './tileViz'
import HeroTrace from './HeroTrace'

function useManifestStats() {
  return useQuery<DataManifest>({
    queryKey: ['manifest'],
    queryFn: () => fetch(`${DATA_CDN_BASE}/data/_manifest.json`).then((r) => r.json()),
    staleTime: Infinity,
  })
}

// The nine shipped features, ordered fans-first. Spans build the bento rhythm on lg+.
const FEATURES: BentoFeature[] = [
  {
    id: 1, title: 'Ghost Car Standings', tag: 'Counterfactual', to: '/ghost-car/standings',
    Viz: GhostCarViz, flagship: true, span: '',
    hook: "What if every driver raced every team's car? Pace recombination rebuilds each driver's lap times in a host car and re-ranks the grid-revealing how much of the order is the car, and how much is the driver.",
  },
  {
    id: 5, title: 'Tyre Cliff Survival', tag: 'Strategy', to: '/tyre-strategy/survival',
    Viz: SurvivalViz, span: '',
    hook: 'How long does a compound last before the cliff? A Kaplan-Meier curve from every historical stint at the circuit, with real degradation overlaid to validate the fit in-view.',
  },
  {
    id: 4, title: 'Lap Decomposition', tag: 'The Core', to: '/lap-decomposition/waterfall',
    Viz: WaterfallViz, flagship: true, span: '',
    hook: 'Seven causes, one lap time. Fuel, compound, rubber, ambient, car, dirty air, driver skill-an additive identity that CI proves closes on every single lap.',
  },
  {
    id: 16, title: 'Degradation Simulator', tag: 'Live ONNX', to: '/ml/simulator',
    Viz: QuantileFanViz, flagship: true, span: '',
    hook: 'The trained tyre-degradation models running live in your browser. Dial a stint and watch predicted next-lap pace loss, cliff risk, and remaining tyre life update in real time via onnxruntime-web.',
  },
  {
    id: 3, title: 'Era-Adjusted Ratings', tag: 'Drivers', to: '/drivers/ratings-timeline',
    Viz: EraRatingsViz, span: '',
    hook: 'Driver pace ranked across history, corrected for the 2022 reg shift. Bayesian season ratings anchored on bridge drivers-so Hamilton 2020 is genuinely comparable to Verstappen 2024.',
  },
  {
    id: 14, title: 'Driver Consistency', tag: 'Drivers', to: '/drivers/consistency',
    Viz: ScatterViz, span: '',
    hook: 'How reliably does a driver extract the pace the car has? Lap-to-lap residual variance-after removing car, tyre, dirty air and conditions-separates dependably fast from brilliantly erratic.',
  },
  {
    id: 9, title: 'Pit Strategy Grader', tag: 'Strategy', to: '/tyre-strategy/pit-gantt',
    Viz: PitGanttViz, span: '',
    hook: 'Every stint laid out by lap. Bar colour is compound; border colour grades the call-did the team pit on time, or leave their driver on crumbling rubber?',
  },
  {
    id: 15, title: 'Blind-Test Scoreboard', tag: 'The Machine', to: '/ml/blind-test',
    Viz: BlindTestViz, span: '',
    hook: "Degradation predictions versus actuals, every call locked against real race data the model never trained on. Honesty made visible.",
  },
]

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07, delayChildren: 0.1 } },
}

function StatPill({ value, label, delay }: { value: string | number; label: string; delay: number }) {
  return (
    <motion.div
      className="flex flex-col items-center px-6 py-4"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
    >
      <span className="font-mono text-2xl font-bold tabular-nums text-[rgb(var(--color-text))]">
        {typeof value === 'number' ? value.toLocaleString() : value}
      </span>
      <span className="mt-1 text-[11px] uppercase tracking-wider text-muted">{label}</span>
    </motion.div>
  )
}

export default function Home() {
  const reduce = useReducedMotion()

  // Fire-and-forget DuckDB warm-up: download + boot the engine while the visitor reads (AD-12).
  useEffect(() => {
    import('../../data/duckdb/client').then((m) => m.getConnection()).catch(() => {})
  }, [])

  const { data: manifest } = useManifestStats()
  const stats = manifest?.stats

  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      {/* ---------- Hero ---------- */}
      <header className="relative mb-12 overflow-hidden rounded-3xl border border-border bg-surface px-8 py-12 sm:px-12 sm:py-16">
        <HeroTrace />
        <div className="relative max-w-2xl">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-[rgb(var(--color-bg)/0.6)] px-3 py-1 backdrop-blur"
          >
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[rgb(var(--color-accent))] opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-[rgb(var(--color-accent))]" />
            </span>
            <span className="font-mono text-[11px] uppercase tracking-widest text-muted">
              Runs entirely in your browser
            </span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.05 }}
            className="text-4xl font-bold tracking-tight sm:text-5xl"
          >
            Off The Pace
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.12 }}
            className="mt-4 text-base leading-relaxed text-muted sm:text-lg"
          >
            Causal lap-time decomposition for Formula 1. A seven-term additive identity,
            enforced by CI on every lap. Ghost-car counterfactuals, tyre-cliff survival models,
            and live ONNX inference-<span className="text-[rgb(var(--color-text))]">no backend, no cost.</span>
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.2 }}
            className="mt-7 flex flex-wrap gap-3"
          >
            <Link
              to="/ghost-car/standings"
              className="group inline-flex items-center gap-2 rounded-lg bg-[rgb(var(--color-accent))] px-5 py-2.5 text-sm font-semibold text-white transition-transform hover:scale-[1.03]"
            >
              Explore the grid
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="transition-transform group-hover:translate-x-0.5" aria-hidden>
                <path d="M2 7h9M7 3l4 4-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </Link>
            <a
              href="https://offthepace.mintlify.app" target="_blank" rel="noopener noreferrer"
              className="rounded-lg border border-border px-5 py-2.5 text-sm font-medium text-muted transition-colors hover:text-[rgb(var(--color-text))]"
            >
              Methodology
            </a>
          </motion.div>
        </div>

        {/* stats strip */}
        {stats && (
          <div className="relative mt-10 flex flex-wrap divide-x divide-border overflow-hidden rounded-xl border border-border bg-[rgb(var(--color-bg)/0.5)] backdrop-blur">
            <StatPill value={stats.total_laps} label="laps decomposed" delay={0.3} />
            <StatPill value={stats.dbt_models} label="dbt models" delay={0.36} />
            <StatPill value={`${stats.ml_models}/5`} label="ML beat baseline" delay={0.42} />
            <StatPill value={stats.seasons} label="seasons" delay={0.48} />
          </div>
        )}
      </header>

      {/* ---------- Bento grid ---------- */}
      <section>
        <div className="mb-5 flex items-baseline justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-muted">
            Shipped features
          </h2>
          <span className="font-mono text-[11px] text-muted/70">{FEATURES.length} live</span>
        </div>

        <motion.div
          variants={reduce ? undefined : container}
          initial={reduce ? undefined : 'hidden'}
          animate={reduce ? undefined : 'show'}
          className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4"
        >
          {FEATURES.map((f) => (
            <BentoTile key={f.id} feature={f} />
          ))}
        </motion.div>
      </section>

      {/* ---------- Footer ---------- */}
      <footer className="mt-14 flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6 text-sm text-muted">
        <span>{APP_CONFIG.title}-a portfolio data product.</span>
        <div className="flex flex-wrap gap-4">
          <a href={APP_CONFIG.githubUrl} target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-[rgb(var(--color-text))]">GitHub</a>
          <a href="https://offthepace.mintlify.app" target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-[rgb(var(--color-text))]">Docs</a>
          <a href="https://justinclarke.github.io" target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-[rgb(var(--color-text))]">Portfolio</a>
        </div>
      </footer>
    </div>
  )
}
