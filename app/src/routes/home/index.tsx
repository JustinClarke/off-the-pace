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

// The OTP hexagon mark (matches the sidebar brand), used in the footer.
function BrandMark({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinejoin="round" className={className} aria-hidden>
      <path d="M12 2.5l8.5 4.9v9.2L12 21.5 3.5 16.6V7.4z" />
      <path d="M12 7.5v9M8 9.5l8 5M16 9.5l-8 5" strokeWidth="1.1" opacity="0.55" />
    </svg>
  )
}

// The hero's headline numbers, presented as a single self-contained "instrument cluster"
// (divided cells, mono numerals, accent tick on the lead metric) rather than four floating
// figures reads like a pit-wall readout instead of a spreadsheet row.
function StatCluster({ stats }: { stats: NonNullable<DataManifest['stats']> }) {
  const items: { value: string | number; label: string; lead?: boolean }[] = [
    { value: stats.total_laps, label: 'laps decomposed', lead: true },
    { value: stats.total_drivers ?? 40, label: 'drivers modeled' },
    { value: stats.total_circuits ?? 44, label: 'circuits covered' },
    { value: stats.dbt_models, label: 'dbt models' },
    { value: `${stats.ml_models}/5`, label: 'ml models beat baseline' },
    { value: stats.seasons, label: 'seasons' },
  ]
  return (
    <div className="relative hidden overflow-hidden rounded-xl border border-border/60 bg-[rgb(var(--color-bg)/0.7)] backdrop-blur-md shadow-inner sm:grid sm:grid-cols-3">
      <span aria-hidden className="absolute inset-x-0 top-0 h-[1.5px] bg-gradient-to-r from-transparent via-[rgb(var(--color-accent))]/70 to-transparent opacity-80" />
      {items.map((s, i) => (
        <div
          key={s.label}
          className={[
            "group flex flex-col justify-center px-4 py-2.5 transition-colors hover:bg-white/[0.02]",
            i < 3 ? "border-b border-border/50" : "",
            i % 3 !== 0 ? "border-l border-border/50" : ""
          ].filter(Boolean).join(" ")}
        >
          <span className="font-mono text-[18px] font-bold leading-none tracking-tight tabular-nums text-[rgb(var(--color-text))] drop-shadow-sm transition-all group-hover:scale-[1.02]">
            {typeof s.value === 'number' ? s.value.toLocaleString() : s.value}
          </span>
          <span className="mt-1.5 flex items-center gap-1.5 whitespace-nowrap text-[8.5px] font-semibold uppercase tracking-[0.15em] text-muted/90">
            <span className={`h-[3.5px] w-[3.5px] rounded-full transition-colors ${s.lead ? 'bg-[rgb(var(--color-accent))] shadow-[0_0_8px_rgba(var(--color-accent),0.6)]' : 'bg-muted/30 group-hover:bg-muted/50'}`} aria-hidden />
            {s.label}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function Home() {
  const reduce = useReducedMotion()

  // Fire-and-forget DuckDB warm-up: download + boot the engine while the visitor reads (AD-12).
  useEffect(() => {
    import('../../data/duckdb/client').then((m) => m.getConnection()).catch(() => { })
  }, [])

  const { data: manifest } = useManifestStats()
  const stats = manifest?.stats

  const stagger = reduce ? undefined : { hidden: {}, show: { transition: { staggerChildren: 0.05, delayChildren: 0.1 } } }

  return (
    <div className="flex flex-col gap-3 px-4 py-3 sm:px-6 lg:h-full">
      {/* ---------- Condensed hero ---------- */}
      <header className="relative shrink-0 overflow-hidden rounded-[1.25rem] border border-border/50 bg-gradient-to-br from-surface to-surface/40 shadow-sm">
        <HeroTrace />
        {/* striking top accent */}
        <span aria-hidden className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-[rgb(var(--color-accent))]/0 via-[rgb(var(--color-accent))] to-[rgb(var(--color-accent))]/0 opacity-80" />

        {/* ambient glow behind title */}
        <div aria-hidden className="absolute -left-32 -top-32 h-64 w-64 rounded-full bg-[rgb(var(--color-accent))]/10 blur-3xl" />

        <div className="relative flex flex-col gap-4 px-5 py-4 lg:flex-row lg:items-center lg:justify-between lg:gap-8 lg:px-6">
          <div className="min-w-0 flex-1">
            <div className="mb-2.5 inline-flex items-center gap-2 rounded-full border border-[rgb(var(--color-accent))]/20 bg-[rgb(var(--color-accent))]/5 px-2.5 py-0.5 shadow-inner backdrop-blur-md">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[rgb(var(--color-accent))] opacity-75" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[rgb(var(--color-accent))]" />
              </span>
              <span className="font-mono text-[9px] font-medium uppercase tracking-[0.2em] text-[rgb(var(--color-accent))]">Runs entirely in your browser</span>
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight sm:text-[2rem] lg:leading-none">
              Off The Pace
            </h1>
            <p className="mt-2 max-w-xl text-[13px] leading-relaxed text-muted/90 sm:text-[14px]">
              Causal lap-time decomposition for Formula 1 ghost-car counterfactuals, tyre-cliff
              survival models and live ONNX inference, with{' '}
              <strong className="font-medium text-[rgb(var(--color-text))]">no backend and no cost.</strong>
            </p>
          </div>

          <div className="flex shrink-0 flex-col items-start gap-4 lg:items-end">
            {stats && <StatCluster stats={stats} />}
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

      {/* ---------- Footer ---------- */}
      <footer className="shrink-0">
        <span aria-hidden className="mb-3 block h-px w-full bg-gradient-to-r from-[rgb(var(--color-accent))]/40 via-border to-transparent" />
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 text-[11px]">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="text-[rgb(var(--color-accent))]"><BrandMark /></span>
            <span className="font-semibold text-[rgb(var(--color-text))]">{APP_CONFIG.title}</span>
            <span className="text-muted/60">a portfolio data product</span>
            <span className="hidden items-center gap-1.5 md:flex">
              {['DuckDB-WASM', 'ONNX Runtime', 'dbt'].map((t) => (
                <span key={t} className="rounded border border-border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-muted/70">
                  {t}
                </span>
              ))}
            </span>
          </div>
          <nav className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] uppercase tracking-wider text-muted">
            <Link to="/roadmap" className="transition-colors hover:text-[rgb(var(--color-text))]">Roadmap</Link>
            <span aria-hidden className="text-muted/30">/</span>
            <a href="https://offthepace.mintlify.app" target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-[rgb(var(--color-text))]">Docs</a>
            <span aria-hidden className="text-muted/30">/</span>
            <a href={APP_CONFIG.githubUrl} target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-[rgb(var(--color-text))]">GitHub</a>
            <span aria-hidden className="text-muted/30">/</span>
            <a href="https://justinclarke.github.io" target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-[rgb(var(--color-text))]">Portfolio</a>
          </nav>
        </div>
      </footer>
    </div>
  )
}
