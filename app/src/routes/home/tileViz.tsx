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
        cx={73} cy={41} r={2.4} fill={ACCENT}
        initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 1.0, type: 'spring', stiffness: 300 }}
      />
      <motion.circle
        cx={73} cy={41} r={2.4} fill="none" stroke={ACCENT}
        initial={{ scale: 1, opacity: 0.7 }} animate={{ scale: 3, opacity: 0 }}
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
    <Frame label="Live degradation quantile forecast">
      <motion.path
        d="M 10 32 C 34 30, 60 30, 90 36 C 100 38, 108 40, 112 42 L 112 54 C 108 52, 100 50, 90 50 C 60 46, 34 40, 10 36 Z"
        fill={ACCENT} opacity={0.16}
        initial={{ opacity: 0, scaleY: 0.4 }} animate={{ opacity: 0.16, scaleY: 1 }}
        style={{ transformOrigin: '10px 34px' }}
        transition={{ delay: 0.5, duration: 0.7 }}
      />
      <motion.path
        d="M 10 34 C 34 33, 60 33, 90 40 C 100 42, 108 44, 112 46"
        stroke={ACCENT} strokeWidth={2} fill="none" strokeLinecap="round" {...draw(0.1)}
      />
      {/* live point pulse at the leading edge */}
      <motion.circle
        cx={112} cy={46} r={2.6} fill={ACCENT}
        initial={{ scale: 0 }} animate={{ scale: [1, 1.5, 1] }}
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
