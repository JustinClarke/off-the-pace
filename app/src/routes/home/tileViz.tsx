// Hand-built SVG mini-visualisations for the home bento grid. Each is a faithful,
// lightweight sketch of the real feature chart-static and representative, no DuckDB
// on the home route (keeps the page zero-SQL per AD-12). They animate on mount via
// framer-motion and react to the parent tile's hover state through CSS group utilities.
import { motion } from 'framer-motion'

const ACCENT = 'rgb(var(--color-accent))'
const MUTED = 'rgb(var(--color-text-muted))'
const BORDER = 'rgb(var(--color-border))'

// Shared draw transition for stroke paths.
const draw = (delay = 0) => ({
  initial: { pathLength: 0, opacity: 0 },
  animate: { pathLength: 1, opacity: 1 },
  transition: { pathLength: { duration: 1.1, ease: 'easeInOut', delay }, opacity: { duration: 0.2, delay } },
})

function Frame({ children, label }: { children: React.ReactNode; label?: string }) {
  return (
    <svg viewBox="0 0 120 64" className="w-full h-full" preserveAspectRatio="xMidYMid meet" role="img" aria-label={label}>
      {children}
    </svg>
  )
}

// #1 Ghost Car-predicted vs actual ranked rows with a swap arrow.
export function GhostCarViz() {
  const rows = [0, 1, 2, 3]
  return (
    <Frame label="Predicted versus actual finishing order">
      {rows.map((r) => {
        const y = 10 + r * 13
        const actualW = 30 + ((r * 17) % 40)
        const predW = 30 + ((r * 29) % 45)
        return (
          <g key={r}>
            <motion.rect
              x={8} y={y} height={7} rx={2} fill={BORDER}
              initial={{ width: 0 }} animate={{ width: actualW }}
              transition={{ duration: 0.6, delay: 0.05 * r }}
            />
            <motion.rect
              x={8} y={y} height={7} rx={2} fill={ACCENT} opacity={0.85}
              initial={{ width: 0 }} animate={{ width: predW }}
              transition={{ duration: 0.7, delay: 0.05 * r + 0.15 }}
            />
          </g>
        )
      })}
      <motion.path
        d="M 95 14 C 108 22, 108 38, 95 50" stroke={ACCENT} strokeWidth={1.6} fill="none" strokeLinecap="round"
        {...draw(0.5)}
      />
      <motion.path
        d="M 95 50 l -4 -1 m 4 1 l -1 -4" stroke={ACCENT} strokeWidth={1.6} fill="none" strokeLinecap="round"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.4 }}
      />
    </Frame>
  )
}

// #5 Tyre Cliff-Kaplan-Meier step-down survival curve with a cliff drop.
export function SurvivalViz() {
  return (
    <Frame label="Tyre cliff survival curve">
      <line x1={10} y1={54} x2={114} y2={54} stroke={BORDER} strokeWidth={1} />
      <motion.path
        d="M 10 10 H 34 V 16 H 52 V 22 H 66 V 30 L 80 52 H 96 V 56 H 114"
        stroke={ACCENT} strokeWidth={2} fill="none" strokeLinejoin="round" strokeLinecap="round"
        {...draw(0.1)}
      />
      {/* cliff marker */}
      <motion.circle
        cx={73} cy={41} r={0} fill={ACCENT}
        initial={{ r: 0, opacity: 0 }} animate={{ r: 2.4, opacity: 1 }}
        transition={{ delay: 1.0, type: 'spring', stiffness: 300 }}
      />
      <motion.circle
        cx={73} cy={41} r={2.4} fill="none" stroke={ACCENT}
        initial={{ r: 2.4, opacity: 0.7 }} animate={{ r: 7.2, opacity: 0 }}
        transition={{ delay: 1.0, duration: 1.4, repeat: Infinity, repeatDelay: 0.6 }}
      />
    </Frame>
  )
}

// #4 Lap Waterfall-additive contribution bars summing to the total, with closure tick.
export function WaterfallViz() {
  // signed contributions that net to a small positive total
  const bars = [
    { x: 8, h: 18, up: true },
    { x: 22, h: 10, up: false },
    { x: 36, h: 14, up: true },
    { x: 50, h: 8, up: false },
    { x: 64, h: 11, up: true },
    { x: 78, h: 6, up: false },
  ]
  const base = 40
  return (
    <Frame label="Seven-term additive lap decomposition">
      <line x1={6} y1={base} x2={114} y2={base} stroke={BORDER} strokeWidth={1} strokeDasharray="2 2" />
      {bars.map((b, i) => {
        const y = b.up ? base-b.h : base
        return (
          <motion.rect
            key={i} x={b.x} width={10} rx={1.5}
            fill={b.up ? ACCENT : MUTED} opacity={b.up ? 0.85 : 0.55}
            initial={{ height: 0, y: base }}
            animate={{ height: b.h, y }}
            transition={{ duration: 0.5, delay: 0.08 * i, ease: 'backOut' }}
          />
        )
      })}
      {/* total bar */}
      <motion.rect
        x={96} width={12} rx={1.5} fill={ACCENT}
        initial={{ height: 0, y: base }} animate={{ height: 26, y: base-26 }}
        transition={{ duration: 0.5, delay: 0.6, ease: 'backOut' }}
      />
      {/* closure tick */}
      <motion.path
        d="M 99 22 l 2.5 2.5 L 106 18" stroke={ACCENT} strokeWidth={1.8} fill="none" strokeLinecap="round" strokeLinejoin="round"
        initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 1 }}
        transition={{ delay: 1.1, duration: 0.4 }}
      />
    </Frame>
  )
}

// #3 Era Ratings-multi-line timeline with a CI ribbon and the 2022 era boundary.
export function EraRatingsViz() {
  return (
    <Frame label="Era-adjusted driver rating timeline">
      {/* CI ribbon */}
      <motion.path
        d="M 10 38 C 30 30, 50 24, 70 20 C 86 17, 100 16, 112 18 L 112 30 C 100 28, 86 28, 70 30 C 50 33, 30 38, 10 46 Z"
        fill={ACCENT} opacity={0.12}
        initial={{ opacity: 0 }} animate={{ opacity: 0.12 }} transition={{ delay: 0.6, duration: 0.6 }}
      />
      {/* era boundary */}
      <motion.line
        x1={66} y1={6} x2={66} y2={58} stroke={MUTED} strokeWidth={1} strokeDasharray="3 3"
        initial={{ opacity: 0 }} animate={{ opacity: 0.6 }} transition={{ delay: 0.9 }}
      />
      <motion.path
        d="M 10 42 C 30 34, 50 27, 70 24 C 86 21, 100 21, 112 23"
        stroke={ACCENT} strokeWidth={2} fill="none" strokeLinecap="round" {...draw(0.1)}
      />
      <motion.path
        d="M 10 50 C 30 48, 50 40, 70 38 C 86 36, 100 32, 112 30"
        stroke={MUTED} strokeWidth={1.6} fill="none" strokeLinecap="round" {...draw(0.3)}
      />
    </Frame>
  )
}

// #9 Pit Strategy-stint swimlanes (gantt) with compound-coloured bars + pit markers.
export function PitGanttViz() {
  const lanes = [
    [{ x: 8, w: 34, c: ACCENT }, { x: 46, w: 30, c: MUTED }, { x: 80, w: 28, c: ACCENT }],
    [{ x: 8, w: 26, c: MUTED }, { x: 38, w: 40, c: ACCENT }, { x: 82, w: 26, c: MUTED }],
    [{ x: 8, w: 44, c: ACCENT }, { x: 56, w: 52, c: MUTED }],
  ]
  return (
    <Frame label="Pit strategy gantt across stints">
      {lanes.map((lane, li) =>
        lane.map((s, si) => (
          <motion.rect
            key={`${li}-${si}`}
            x={s.x} y={10 + li * 16} width={s.w} height={9} rx={2}
            fill={s.c} opacity={s.c === ACCENT ? 0.8 : 0.4}
            initial={{ scaleX: 0, originX: 0 }} animate={{ scaleX: 1 }}
            style={{ transformOrigin: `${s.x}px center` }}
            transition={{ duration: 0.45, delay: 0.1 * li + 0.12 * si, ease: 'easeOut' }}
          />
        )),
      )}
    </Frame>
  )
}

// #14 Driver Consistency-scatter of mean vs stddev with quadrant split.
export function ScatterViz() {
  const pts = [
    [28, 20], [40, 28], [34, 40], [55, 24], [62, 44], [48, 18], [70, 34], [82, 26], [90, 48], [22, 50],
  ]
  return (
    <Frame label="Driver consistency scatter">
      <line x1={56} y1={6} x2={56} y2={58} stroke={BORDER} strokeWidth={0.8} />
      <line x1={10} y1={32} x2={110} y2={32} stroke={BORDER} strokeWidth={0.8} />
      {pts.map(([cx, cy], i) => (
        <motion.circle
          key={i} cx={cx} cy={cy} r={2.6}
          fill={cx < 56 && cy < 32 ? ACCENT : MUTED}
          opacity={cx < 56 && cy < 32 ? 0.9 : 0.5}
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: cx < 56 && cy < 32 ? 0.9 : 0.5 }}
          transition={{ delay: 0.04 * i, type: 'spring', stiffness: 260 }}
        />
      ))}
    </Frame>
  )
}

// #16 Degradation Simulator-quantile fan (p10-p90 ribbon) + live p50 line. The hero ML viz.
export function QuantileFanViz() {
  return (
    <Frame label="Live degradation simulation model">
      {/* Baseline */}
      <line x1={10} y1={52} x2={114} y2={52} stroke={BORDER} strokeWidth={1} />

      {/* Fresh-tyre anchor (flat reference) */}
      <motion.line
        x1={10} y1={48} x2={114} y2={48}
        stroke={MUTED}
        strokeWidth={1}
        strokeDasharray="2 2"
        opacity={0.4}
        {...draw(0.4)}
      />

      {/* Fuel burn-off component (pace improving as weight decreases) */}
      <motion.path
        d="M 10 38 C 40 41, 80 46, 114 48"
        stroke="rgb(56, 189, 248)"
        strokeWidth={1.2}
        strokeDasharray="2 2"
        fill="none"
        opacity={0.6}
        {...draw(0.3)}
      />

      {/* Tyre degradation uncertainty fan (ribbon widening over time) */}
      <motion.path
        d="M 10 48 C 40 48, 80 43, 114 12 L 114 28 C 80 45, 40 48, 10 48 Z"
        fill={ACCENT}
        opacity={0.12}
        initial={{ opacity: 0, scaleY: 0.3 }}
        animate={{ opacity: 0.12, scaleY: 1 }}
        style={{ transformOrigin: '10px 48px' }}
        transition={{ delay: 0.5, duration: 0.7 }}
      />

      {/* Combined net pace projection (solid curve showing crossover then cliff) */}
      <motion.path
        d="M 10 38 C 35 41, 70 42, 90 38 C 102 32, 110 24, 114 20"
        stroke={ACCENT}
        strokeWidth={2}
        fill="none"
        strokeLinecap="round"
        {...draw(0.1)}
      />

      {/* Tyre Cliff detection pulse */}
      <motion.circle
        cx={90} cy={38} r={0} fill={ACCENT}
        initial={{ r: 0, opacity: 0 }}
        animate={{ r: 2.4, opacity: 1 }}
        transition={{ delay: 1.0, type: 'spring', stiffness: 300 }}
      />
      <motion.circle
        cx={90} cy={38} r={2.4} fill="none" stroke={ACCENT} strokeWidth={1}
        initial={{ r: 2.4, opacity: 0.7 }}
        animate={{ r: 7.7, opacity: 0 }}
        transition={{ delay: 1.0, duration: 1.5, repeat: Infinity, repeatDelay: 0.5 }}
      />

      {/* Live point pulse at the stint end */}
      <motion.circle
        cx={114} cy={20} r={2.5} fill={ACCENT}
        initial={{ r: 0 }}
        animate={{ r: [2.5, 3.8, 2.5] }}
        transition={{ delay: 1.2, duration: 1.4, repeat: Infinity }}
      />
    </Frame>
  )
}

// #15 Blind Test-predicted vs actual scatter hugging the identity diagonal.
export function BlindTestViz() {
  const pts = [
    [16, 50], [28, 40], [34, 36], [44, 30], [52, 26], [60, 22], [70, 18], [80, 16], [90, 12], [38, 28], [56, 30],
  ]
  return (
    <Frame label="Blind test predicted versus actual">
      <motion.line
        x1={12} y1={54} x2={104} y2={8} stroke={MUTED} strokeWidth={1} strokeDasharray="3 3"
        initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.8, delay: 0.2 }}
      />
      {pts.map(([cx, cy], i) => (
        <motion.circle
          key={i} cx={cx} cy={cy} r={2.4} fill={ACCENT} opacity={0.8}
          initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 0.8 }}
          transition={{ delay: 0.3 + 0.05 * i, type: 'spring', stiffness: 260 }}
        />
      ))}
    </Frame>
  )
}

// #10 Degradation Timeline-observed pace climbing away from a flat expected line as the tyre ages.
export function DegTimelineViz() {
  return (
    <Frame label="Observed versus expected degradation over a stint">
      <line x1={10} y1={50} x2={114} y2={50} stroke={BORDER} strokeWidth={1} />
      {/* gap fill between expected and observed */}
      <motion.path
        d="M 10 38 C 40 37, 64 36, 90 30 C 100 27, 108 22, 112 18 L 112 36 C 108 36, 100 36, 90 36 C 64 36, 40 37, 10 38 Z"
        fill={ACCENT} opacity={0.12}
        initial={{ opacity: 0 }} animate={{ opacity: 0.12 }} transition={{ delay: 0.7, duration: 0.6 }}
      />
      {/* expected (flat-ish, dashed) */}
      <motion.path
        d="M 10 38 C 40 37, 70 36, 112 36" stroke={MUTED} strokeWidth={1.4} fill="none"
        strokeDasharray="3 3" strokeLinecap="round" {...draw(0.3)}
      />
      {/* observed (rising = slowing) */}
      <motion.path
        d="M 10 38 C 40 37, 64 36, 90 30 C 100 27, 108 22, 112 18" stroke={ACCENT} strokeWidth={2}
        fill="none" strokeLinecap="round" {...draw(0.1)}
      />
    </Frame>
  )
}

// #12 Circuit Interaction-constructor x circuit heatmap grid, accent intensity = pace edge.
export function MatrixViz() {
  const cols = 6
  const rows = 4
  // deterministic pseudo-intensity per cell
  const cell = (r: number, c: number) => ((r * 7 + c * 5) % 10) / 10
  return (
    <Frame label="Constructor by circuit interaction heatmap">
      {Array.from({ length: rows }).map((_, r) =>
        Array.from({ length: cols }).map((_, c) => {
          const v = cell(r, c)
          return (
            <motion.rect
              key={`${r}-${c}`}
              x={10 + c * 17} y={8 + r * 13} width={15} height={11} rx={1.5}
              fill={v > 0.45 ? ACCENT : MUTED} opacity={0.18 + v * 0.6}
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 0.18 + v * 0.6 }}
              style={{ transformOrigin: `${17.5 + c * 17}px ${13.5 + r * 13}px` }}
              transition={{ delay: 0.03 * (r * cols + c), type: 'spring', stiffness: 280 }}
            />
          )
        }),
      )}
    </Frame>
  )
}

// #7 Structural Pace-ranked horizontal bars (a constructor pace leaderboard), leader in accent.
export function RankedBarsViz() {
  const bars = [52, 44, 38, 30, 22]
  return (
    <Frame label="Constructor structural pace ranking">
      {bars.map((w, i) => (
        <motion.rect
          key={i} x={10} y={8 + i * 11} height={7} rx={2}
          fill={i === 0 ? ACCENT : MUTED} opacity={i === 0 ? 0.9 : 0.45-i * 0.05}
          initial={{ width: 0 }} animate={{ width: w }}
          transition={{ duration: 0.55, delay: 0.08 * i, ease: 'easeOut' }}
        />
      ))}
    </Frame>
  )
}

// #11 Circuit Affinity-a circuit loop with a glowing node where the driver over-performs.
export function AffinityViz() {
  return (
    <Frame label="Driver circuit affinity">
      <motion.path
        d="M 24 44 C 14 34, 18 18, 36 16 C 52 14, 56 26, 72 24 C 92 21, 104 30, 100 42 C 96 54, 72 54, 56 50 C 42 46, 34 54, 24 44 Z"
        stroke={MUTED} strokeWidth={1.6} fill="none" strokeLinecap="round" {...draw(0.1)}
      />
      {/* affinity node */}
      <motion.circle
        cx={36} cy={16} r={0} fill={ACCENT}
        initial={{ r: 0, opacity: 0 }} animate={{ r: 3, opacity: 1 }}
        transition={{ delay: 1.1, type: 'spring', stiffness: 300 }}
      />
      <motion.circle
        cx={36} cy={16} r={3} fill="none" stroke={ACCENT}
        initial={{ r: 3, opacity: 0.7 }} animate={{ r: 9, opacity: 0 }}
        transition={{ delay: 1.1, duration: 1.6, repeat: Infinity, repeatDelay: 0.5 }}
      />
    </Frame>
  )
}

// #26 Wet-Race Specialist-rain streaks over a dry/wet delta pair; specialist loses less in the wet.
export function WetViz() {
  const rain = [20, 34, 48, 62, 76, 90, 100]
  return (
    <Frame label="Wet versus dry pace delta">
      {rain.map((x, i) => (
        <motion.line
          key={i} x1={x} y1={6} x2={x-6} y2={20} stroke={MUTED} strokeWidth={1}
          initial={{ opacity: 0, y: -6 }} animate={{ opacity: 0.4, y: 0 }}
          transition={{ delay: 0.05 * i, duration: 0.3 }}
        />
      ))}
      <line x1={10} y1={54} x2={114} y2={54} stroke={BORDER} strokeWidth={1} />
      {/* dry baseline bar vs shorter wet-loss bar (specialist) */}
      <motion.rect
        x={32} width={18} rx={2} fill={MUTED} opacity={0.4}
        initial={{ height: 0, y: 54 }} animate={{ height: 28, y: 26 }}
        transition={{ duration: 0.5, delay: 0.4 }}
      />
      <motion.rect
        x={68} width={18} rx={2} fill={ACCENT} opacity={0.85}
        initial={{ height: 0, y: 54 }} animate={{ height: 16, y: 38 }}
        transition={{ duration: 0.5, delay: 0.55 }}
      />
    </Frame>
  )
}

// #30 Corner-Phase Skill-a corner arc split into entry / apex / exit, apex phase highlighted.
export function CornerPhaseViz() {
  return (
    <Frame label="Corner-phase skill: entry, apex, exit">
      <motion.path
        d="M 12 14 C 12 36, 26 50, 60 50" stroke={MUTED} strokeWidth={2.4} fill="none"
        strokeLinecap="round" {...draw(0.1)}
      />
      <motion.path
        d="M 60 50 C 94 50, 108 36, 108 14" stroke={ACCENT} strokeWidth={2.4} fill="none"
        strokeLinecap="round" {...draw(0.35)}
      />
      {/* phase markers */}
      {[
        { cx: 12, cy: 14, c: MUTED },
        { cx: 60, cy: 50, c: ACCENT },
        { cx: 108, cy: 14, c: MUTED },
      ].map((m, i) => (
        <motion.circle
          key={i} cx={m.cx} cy={m.cy} r={2.6} fill={m.c}
          initial={{ scale: 0 }} animate={{ scale: 1 }}
          transition={{ delay: 0.8 + 0.12 * i, type: 'spring', stiffness: 300 }}
        />
      ))}
    </Frame>
  )
}

// #13 Lap Air Map-per-lap clean/dirty air barcode along a stint, with an airflow wave behind.
export function AirMapViz() {
  const laps = Array.from({ length: 16 })
  const dirty = (i: number) => [3, 4, 5, 9, 10, 13].includes(i)
  return (
    <Frame label="Per-lap clean and dirty air timeline">
      <motion.path
        d="M 8 22 C 28 14, 48 30, 68 22 C 88 14, 104 28, 114 22" stroke={ACCENT} strokeWidth={1.2}
        fill="none" opacity={0.5} strokeLinecap="round" {...draw(0.2)}
      />
      {laps.map((_, i) => (
        <motion.rect
          key={i} x={8 + i * 6.6} y={34} width={5} height={18} rx={1}
          fill={dirty(i) ? ACCENT : MUTED} opacity={dirty(i) ? 0.85 : 0.3}
          initial={{ scaleY: 0, originY: 1 }} animate={{ scaleY: 1 }}
          style={{ transformOrigin: `${10.5 + i * 6.6}px 52px` }}
          transition={{ duration: 0.35, delay: 0.03 * i, ease: 'easeOut' }}
        />
      ))}
    </Frame>
  )
}

// #17 Model Metrics-model-vs-baseline paired bars, all models beating baseline.
export function MetricsViz() {
  const models = [0, 1, 2, 3, 4]
  return (
    <Frame label="Five models beating baseline">
      <line x1={6} y1={54} x2={114} y2={54} stroke={BORDER} strokeWidth={1} />
      {models.map((m) => {
        const x = 12 + m * 20
        const baseH = 12 + ((m * 7) % 10)
        const modelH = baseH + 14 + ((m * 5) % 8)
        return (
          <g key={m}>
            <motion.rect
              x={x} width={7} rx={1.5} fill={MUTED} opacity={0.4}
              initial={{ height: 0, y: 54 }} animate={{ height: baseH, y: 54-baseH }}
              transition={{ duration: 0.5, delay: 0.08 * m }}
            />
            <motion.rect
              x={x + 8} width={7} rx={1.5} fill={ACCENT} opacity={0.85}
              initial={{ height: 0, y: 54 }} animate={{ height: modelH, y: 54-modelH }}
              transition={{ duration: 0.55, delay: 0.08 * m + 0.15 }}
            />
          </g>
        )
      })}
    </Frame>
  )
}
