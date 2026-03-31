// Product home-a single-viewport showcase (no scroll on desktop) split into three bands:
// Constructor & Strategy, Driver Craft, and a wide Showcase led by the live ONNX simulator.
// Stats come from the manifest JSON (zero SQL); a fire-and-forget DuckDB warm-up boots the
// engine in the background while the visitor browses (AD-12). Only shipped features appear-
// everything still waiting on data lives on /roadmap.
import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { motion, useReducedMotion } from 'framer-motion'
import { APP_CONFIG } from '../../config'
import type { DataManifest } from '../../data/manifest'
import { DATA_CDN_BASE } from '../../data/manifest'
import {
  GhostCarViz, SurvivalViz, WaterfallViz, PitGanttViz, QuantileFanViz,
  DegTimelineViz, MatrixViz, RankedBarsViz, AffinityViz, WetViz, CornerPhaseViz, AirMapViz,
} from './tileViz'
import HeroTrace from './HeroTrace'

interface Feature {
  title: string
  tag: string
  to: string
  hook: string
  Viz: () => JSX.Element
}

const CONSTRUCTOR_FEATURES: Feature[] = [
  { title: 'Degradation Timeline', tag: 'Strategy', to: '/tyre-strategy/degradation', Viz: DegTimelineViz, hook: "Observed pace against the model's expected degradation curve, lap by lap." },
  { title: 'Pit Strategy Gantt', tag: 'Strategy', to: '/tyre-strategy/pit-gantt', Viz: PitGanttViz, hook: 'Every stint as a swimlane, each call graded on its timing.' },
  { title: 'Circuit Interaction', tag: 'Constructors', to: '/constructors/circuits', Viz: MatrixViz, hook: 'Which teams overperform where-a constructor x circuit heatmap.' },
  { title: 'Structural Pace', tag: 'Constructors', to: '/constructors/structural', Viz: RankedBarsViz, hook: "The car's true pace, stripped of driver and circuit." },
]

const DRIVER_FEATURES: Feature[] = [
  { title: 'Circuit Affinity', tag: 'Drivers', to: '/drivers/circuit-affinity', Viz: AffinityViz, hook: 'The tracks where a driver consistently beats their own baseline.' },
  { title: 'Wet-Race Specialist', tag: 'Drivers', to: '/drivers/wet-race', Viz: WetViz, hook: 'Who loses the least pace when the rain arrives.' },
  { title: 'Corner-Phase Skill', tag: 'Drivers', to: '/drivers/corner-skill', Viz: CornerPhaseViz, hook: "Entry, apex, exit-where a driver's lap time really comes from." },
  { title: 'Lap Air Map', tag: 'Aero', to: '/aero/lap-map', Viz: AirMapViz, hook: 'Clean versus dirty air, mapped lap by lap across a stint.' },
]

const SHOWCASE_HERO: Feature = {
  title: 'Degradation Simulator', tag: 'Live ONNX', to: '/ml/simulator', Viz: QuantileFanViz,
  hook: 'The trained tyre-degradation models running live in your browser. Dial a stint-compound, fuel, dirty air, track temperature-and watch predicted pace loss, cliff risk and remaining tyre life update in real time.',
}

const SHOWCASE_TILES: Feature[] = [
  { title: 'Ghost Car Standings', tag: 'Counterfactual', to: '/ghost-car/standings', Viz: GhostCarViz, hook: 'Every driver re-ranked in equal machinery.' },
  { title: 'Lap Decomposition', tag: 'The Core', to: '/lap-decomposition/waterfall', Viz: WaterfallViz, hook: 'Seven causes, one lap time-an identity that always closes.' },
  { title: 'Tyre Cliff Survival', tag: 'Strategy', to: '/tyre-strategy/survival', Viz: SurvivalViz, hook: 'How long a compound lasts before the cliff.' },
]

function useManifestStats() {
  return useQuery<DataManifest>({
    queryKey: ['manifest'],
    queryFn: () => fetch(`${DATA_CDN_BASE}/data/_manifest.json`).then((r) => r.json()),
    staleTime: Infinity,
  })
}

const rise = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0 },
}

// A spotlight border + hover lift, shared by every tile on the page.
const tileBase =
  'group relative flex flex-col overflow-hidden rounded-xl border border-border bg-surface ' +
  'transition-all duration-300 ease-out hover:-translate-y-0.5 hover:border-[rgb(var(--color-accent))]/50 ' +
  'hover:shadow-lg hover:shadow-black/5 dark:hover:shadow-black/30'

function GroupHeader({ kicker, title, accent = false }: { kicker: string; title: string; accent?: boolean }) {
  return (
    <div className="mb-2 flex shrink-0 items-baseline gap-2">
      <span
        className={[
          'inline-block h-3 w-[3px] rounded-full',
          accent ? 'bg-[rgb(var(--color-accent))]' : 'bg-border',
        ].join(' ')}
        aria-hidden
      />
      <h2 className="text-[13px] font-semibold tracking-tight text-[rgb(var(--color-text))]">{title}</h2>
      <span className="font-mono text-[9px] uppercase tracking-widest text-muted/70">{kicker}</span>
    </div>
  )
}

// Compact tile for the two stat columns: viz fills, title + one-line hook beneath.
function CompactTile({ feature }: { feature: Feature }) {
  const { Viz } = feature
  return (
    <motion.div variants={rise} className="min-h-0 flex-1">
      <Link to={feature.to} className={`${tileBase} h-full min-h-[104px] p-3`}>
        <div className="flex items-center justify-between">
          <span className="font-mono text-[8px] uppercase tracking-widest text-muted">{feature.tag}</span>
          <svg width="11" height="11" viewBox="0 0 14 14" fill="none" className="text-muted/50 transition-all group-hover:translate-x-0.5 group-hover:text-accent" aria-hidden>
            <path d="M2 7h9M7 3l4 4-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <div className="min-h-0 flex-1 py-1.5">
          <Viz />
        </div>
        <h3 className="truncate text-[12px] font-semibold tracking-tight text-[rgb(var(--color-text))] transition-colors group-hover:text-accent">
          {feature.title}
        </h3>
        <p className="truncate text-[10px] leading-snug text-muted">{feature.hook}</p>
      </Link>
    </motion.div>
  )
}

// Smaller showcase tile (the three visual supporting features beneath the simulator).
function ShowcaseTile({ feature }: { feature: Feature }) {
  const { Viz } = feature
  return (
    <motion.div variants={rise} className="min-h-0 min-w-0 flex-1">
      <Link to={feature.to} className={`${tileBase} h-full min-h-[104px] p-3`}>
        <span className="font-mono text-[8px] uppercase tracking-widest text-muted">{feature.tag}</span>
        <div className="min-h-0 flex-1 py-1.5">
          <Viz />
        </div>
        <h3 className="truncate text-[12px] font-semibold tracking-tight text-[rgb(var(--color-text))] transition-colors group-hover:text-accent">
          {feature.title}
        </h3>
        <p className="truncate text-[10px] leading-snug text-muted">{feature.hook}</p>
      </Link>
    </motion.div>
  )
}

// The headline simulator card-large viz, fuller copy, accent-trimmed.
function ShowcaseHero({ feature }: { feature: Feature }) {
  const { Viz } = feature
  return (
    <motion.div variants={rise} className="min-h-0 flex-[1.5]">
      <Link
        to={feature.to}
        className={[
          'group relative flex h-full min-h-[150px] flex-col overflow-hidden rounded-2xl border bg-surface p-4',
          'border-[rgb(var(--color-accent))]/30 transition-all duration-300 ease-out',
          'hover:-translate-y-0.5 hover:border-[rgb(var(--color-accent))]/70 hover:shadow-xl hover:shadow-black/10 dark:hover:shadow-black/40',
        ].join(' ')}
      >
        <div
          aria-hidden
          className="pointer-events-none absolute -right-16 -top-16 h-44 w-44 rounded-full opacity-60 blur-3xl"
          style={{ background: 'radial-gradient(circle, rgb(var(--color-accent) / 0.18), transparent 70%)' }}
        />
        <div className="relative flex items-center gap-2">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[rgb(var(--color-accent))] opacity-75" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[rgb(var(--color-accent))]" />
          </span>
          <span className="font-mono text-[9px] uppercase tracking-widest text-accent">{feature.tag}</span>
        </div>

        <div className="relative my-2 min-h-0 flex-1">
          <Viz />
        </div>

        <div className="relative flex items-end justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-base font-bold tracking-tight text-[rgb(var(--color-text))] transition-colors group-hover:text-accent">
              {feature.title}
            </h3>
            <p className="mt-0.5 line-clamp-2 max-w-md text-[11px] leading-snug text-muted">{feature.hook}</p>
          </div>
          <span className="shrink-0 inline-flex items-center gap-1 rounded-lg bg-[rgb(var(--color-accent))] px-3 py-1.5 text-[11px] font-semibold text-white transition-transform group-hover:scale-[1.04]">
            Open
            <svg width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden>
              <path d="M2 7h9M7 3l4 4-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        </div>
      </Link>
    </motion.div>
  )
}

function StatChip({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="flex flex-col leading-none">
      <span className="font-mono text-lg font-bold tabular-nums text-[rgb(var(--color-text))]">
        {typeof value === 'number' ? value.toLocaleString() : value}
      </span>
      <span className="mt-1 text-[9px] uppercase tracking-wider text-muted">{label}</span>
    </div>
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

  const stagger = reduce ? undefined : { hidden: {}, show: { transition: { staggerChildren: 0.05, delayChildren: 0.1 } } }

  return (
    <div className="flex flex-col gap-3 px-4 py-3 sm:px-6 lg:h-full">
      {/* ---------- Condensed hero ---------- */}
      <header className="relative shrink-0 overflow-hidden rounded-2xl border border-border bg-surface px-5 py-4">
        <HeroTrace />
        <div className="relative flex flex-wrap items-center justify-between gap-x-8 gap-y-4">
          <div className="min-w-0 max-w-xl">
            <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-border bg-[rgb(var(--color-bg)/0.6)] px-2.5 py-0.5 backdrop-blur">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[rgb(var(--color-accent))] opacity-75" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[rgb(var(--color-accent))]" />
              </span>
              <span className="font-mono text-[10px] uppercase tracking-widest text-muted">Runs entirely in your browser</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Off The Pace</h1>
            <p className="mt-1.5 text-[13px] leading-snug text-muted">
              Causal lap-time decomposition for Formula 1-ghost-car counterfactuals, tyre-cliff
              survival models and live ONNX inference, with{' '}
              <span className="text-[rgb(var(--color-text))]">no backend and no cost.</span>
            </p>
          </div>

          <div className="flex items-center gap-5">
            {stats && (
              <div className="hidden items-center gap-5 sm:flex">
                <StatChip value={stats.total_laps} label="laps decomposed" />
                <StatChip value={stats.dbt_models} label="dbt models" />
                <StatChip value={`${stats.ml_models}/5`} label="beat baseline" />
                <StatChip value={stats.seasons} label="seasons" />
              </div>
            )}
            <Link
              to="/ghost-car/standings"
              className="group inline-flex shrink-0 items-center gap-2 rounded-lg bg-[rgb(var(--color-accent))] px-4 py-2 text-sm font-semibold text-white transition-transform hover:scale-[1.03]"
            >
              Explore the grid
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="transition-transform group-hover:translate-x-0.5" aria-hidden>
                <path d="M2 7h9M7 3l4 4-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </Link>
          </div>
        </div>
      </header>

      {/* ---------- Three bands (fills the remaining viewport on desktop) ---------- */}
      <motion.div
        variants={stagger}
        initial={reduce ? undefined : 'hidden'}
        animate={reduce ? undefined : 'show'}
        className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-12"
      >
        {/* Constructor & Strategy */}
        <section className="flex min-h-0 flex-col lg:col-span-3">
          <GroupHeader title="Constructor & Strategy" kicker="The car & the call" />
          <div className="flex min-h-0 flex-1 flex-col gap-2">
            {CONSTRUCTOR_FEATURES.map((f) => (
              <CompactTile key={f.to} feature={f} />
            ))}
          </div>
        </section>

        {/* Driver Craft */}
        <section className="flex min-h-0 flex-col lg:col-span-3">
          <GroupHeader title="Driver Craft" kicker="The hands on the wheel" />
          <div className="flex min-h-0 flex-1 flex-col gap-2">
            {DRIVER_FEATURES.map((f) => (
              <CompactTile key={f.to} feature={f} />
            ))}
          </div>
        </section>

        {/* Showcase */}
        <section className="flex min-h-0 flex-col lg:col-span-6">
          <GroupHeader title="Showcase" kicker="Where the modelling shows" accent />
          <div className="flex min-h-0 flex-1 flex-col gap-3">
            <ShowcaseHero feature={SHOWCASE_HERO} />
            <div className="flex min-h-0 flex-1 flex-col gap-3 sm:flex-row">
              {SHOWCASE_TILES.map((f) => (
                <ShowcaseTile key={f.to} feature={f} />
              ))}
            </div>
          </div>
        </section>
      </motion.div>

      {/* ---------- Minimal footer row ---------- */}
      <footer className="flex shrink-0 flex-wrap items-center justify-between gap-3 text-[11px] text-muted">
        <span>{APP_CONFIG.title}-a portfolio data product.</span>
        <div className="flex flex-wrap gap-4">
          <Link to="/roadmap" className="transition-colors hover:text-[rgb(var(--color-text))]">Roadmap</Link>
          <a href="https://offthepace.mintlify.app" target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-[rgb(var(--color-text))]">Docs</a>
          <a href={APP_CONFIG.githubUrl} target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-[rgb(var(--color-text))]">GitHub</a>
          <a href="https://justinclarke.github.io" target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-[rgb(var(--color-text))]">Portfolio</a>
        </div>
      </footer>
    </div>
  )
}
