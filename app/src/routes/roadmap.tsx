// Roadmap-the honest cabinet of features that are designed and routed but not yet shipped,
// because the public dataset doesn't (yet) carry the signal they need. Grouped by the data
// each cohort is blocked on, so the gap reads as a sourcing decision, not a missing feature.
import { motion, useReducedMotion } from 'framer-motion'

interface RoadmapItem {
  title: string
  blurb: string
}

interface RoadmapGroup {
  blocker: string
  detail: string
  items: RoadmapItem[]
}

const GROUPS: RoadmapGroup[] = [
  {
    blocker: 'Car-position & GPS telemetry',
    detail: 'The public timing feed ships lap and sector times, not the metre-by-metre track position these need to reconstruct.',
    items: [
      { title: 'Overtake Graph', blurb: 'A directed graph of every on-track pass per race-who passed whom, on which lap and at which corner, and whether DRS did the work.' },
      { title: 'Pass-Location Heatmap', blurb: 'Where overtakes actually happen, burned onto the circuit map-the braking zones and DRS traps that decide races.' },
      { title: 'Racing Line Fidelity', blurb: "Each driver's real line scored against the optimal arc, exposing who finds cleaner geometry through the high-speed corners and who sacrifices it for momentum." },
    ],
  },
  {
    blocker: 'High-rate telemetry traces',
    detail: 'Braking, throttle and speed channels at sub-second resolution are not part of the public dataset.',
    items: [
      { title: 'Telemetry Fingerprint', blurb: "A driver's braking-and-throttle signature, corner by corner-the unmistakable shape of how they attack a lap." },
      { title: 'Driver DNA Clusters', blurb: 'Unsupervised clustering of driving style from telemetry features-which drivers are secretly twins behind the wheel.' },
      { title: 'Corner Taxonomy', blurb: 'Every corner on the calendar classified by phase and load, so corner skill can be compared like-for-like across circuits.' },
    ],
  },
  {
    blocker: 'Power-unit & weather channels',
    detail: 'ERS harvest/deploy state is never broadcast, and per-corner wind and density-altitude only arrive partially in the feed.',
    items: [
      { title: 'Energy-Management Map', blurb: 'A circuit overlay of harvest and deployment zones, with per-driver ERS strategy laid bare straight by straight.' },
      { title: 'ERS & Short-Shift', blurb: 'Where drivers lift, coast and short-shift to save energy-and what each compromise costs in lap time.' },
      { title: 'Wind & Altitude', blurb: 'How headwinds, tailwinds and thin mountain air bend lap time, isolated cleanly from every other effect.' },
    ],
  },
  {
    blocker: 'Structured race-control feed',
    detail: 'Penalties, DRS-enable windows and race-control messages need a structured stewarding feed that has not been ingested yet.',
    items: [
      { title: 'Penalty Impact', blurb: 'What every stewarding decision actually cost on track-the real gap a five-second penalty opened up.' },
      { title: 'Race Control Timeline', blurb: 'Safety cars, VSCs, flags and investigations on one timeline, aligned to the pace story unfolding underneath.' },
      { title: 'DRS Dependency', blurb: "How much of a driver's overtaking leans on the DRS flap versus raw racecraft." },
    ],
  },
  {
    blocker: 'Awaiting an upstream model or mart',
    detail: 'The analytics largely exist-these views are waiting on a dedicated race-level model or a scoring mart to be promoted into the public export.',
    items: [
      { title: 'Race Story', blurb: 'A single-race narrative dashboard-lap chart, position swaps, tyre overlay and pace decomposition, end to end.' },
      { title: 'Career Twin', blurb: 'The most statistically similar career arc to any driver, matched on era-adjusted season residuals.' },
      { title: 'Ghost Car Lap Chart', blurb: "Lap-by-lap gap between a driver's real race and their equal-car ghost, drawn as it unfolds." },
      { title: 'Degradation Edge Cases', blurb: 'The stints where the tyre model and reality diverged most-the honest cabinet of where it breaks.' },
    ],
  },
]

const TOTAL = GROUPS.reduce((n, g) => n + g.items.length, 0)

export default function Roadmap() {
  const reduce = useReducedMotion()

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <header className="mb-10 max-w-2xl">
        <span className="font-mono text-[11px] uppercase tracking-widest text-muted">Not shipped-yet</span>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">Roadmap</h1>
        <p className="mt-3 text-sm leading-relaxed text-muted">
          {TOTAL} features are designed, routed and waiting in the wings. Each one is blocked on a
          specific data source the public dataset doesn't carry yet-not on the analysis. They're
          grouped below by what they're waiting on, so the gap reads for what it is: a deliberate
          sourcing boundary, not a loose end.
        </p>
      </header>

      <div className="space-y-10">
        {GROUPS.map((group, gi) => (
          <section key={group.blocker}>
            <div className="mb-4 flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-border pb-2">
              <h2 className="text-sm font-semibold tracking-tight text-[rgb(var(--color-text))]">
                {group.blocker}
              </h2>
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted/70">
                blocked on data
              </span>
            </div>
            <p className="mb-4 max-w-2xl text-xs leading-relaxed text-muted">{group.detail}</p>

            <motion.div
              className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
              initial={reduce ? undefined : 'hidden'}
              animate={reduce ? undefined : 'show'}
              variants={{ hidden: {}, show: { transition: { staggerChildren: 0.05, delayChildren: 0.05 * gi } } }}
            >
              {group.items.map((item) => (
                <motion.div
                  key={item.title}
                  variants={{ hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0 } }}
                  className="group relative flex flex-col rounded-xl border border-border bg-surface p-4 transition-colors hover:border-[rgb(var(--color-accent))]/40"
                >
                  <div className="mb-2 flex items-center justify-between">
                    <h3 className="text-[13px] font-semibold tracking-tight text-[rgb(var(--color-text))]">
                      {item.title}
                    </h3>
                    <span className="rounded-full border border-border px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-muted/70">
                      Planned
                    </span>
                  </div>
                  <p className="text-[12px] leading-snug text-muted">{item.blurb}</p>
                </motion.div>
              ))}
            </motion.div>
            {gi < GROUPS.length-1 && <div className="h-px" />}
          </section>
        ))}
      </div>

      <p className="mt-12 border-t border-border pt-6 text-xs text-muted/70">
        Everything in the rest of the app runs on real, exported data and renders live in your browser.
        The moment a source above lands in the public pipeline, its feature graduates out of this page.
      </p>
    </div>
  )
}
