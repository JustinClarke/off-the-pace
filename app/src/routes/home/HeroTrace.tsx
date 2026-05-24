// Decorative hero backdrop: a faint engineering grid plus an F1-red telemetry trace that
// draws itself on mount, with a glowing dot that laps the line on a loop. Purely
// ornamental (aria-hidden); respects prefers-reduced-motion by rendering the static line.
import { motion, useReducedMotion } from 'framer-motion'

const ACCENT = 'rgb(var(--color-accent))'

// A speed-trace-style path across the hero width.
const TRACE = 'M 0 120 C 120 60, 200 150, 320 90 C 430 35, 520 140, 640 70 C 760 5, 840 110, 980 60'

export default function HeroTrace() {
  const reduce = useReducedMotion()

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      {/* engineering grid */}
      <svg className="absolute inset-0 h-full w-full opacity-[0.04]" preserveAspectRatio="none">
        <defs>
          <pattern id="hero-grid" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M32 0H0V32" fill="none" stroke="currentColor" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#hero-grid)" />
      </svg>

      {/* radial accent wash, top-right */}
      <div
        className="absolute -right-24 -top-24 h-72 w-72 rounded-full blur-3xl"
        style={{ background: `radial-gradient(circle, ${ACCENT}, transparent 65%)`, opacity: 0.12 }}
      />

      {/* telemetry trace */}
      <svg
        viewBox="0 0 980 200"
        className="absolute bottom-0 right-0 h-2/3 w-full opacity-60"
        preserveAspectRatio="xMaxYMax slice"
      >
        <defs>
          <linearGradient id="trace-fade" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor={ACCENT} stopOpacity="0" />
            <stop offset="40%" stopColor={ACCENT} stopOpacity="0.5" />
            <stop offset="100%" stopColor={ACCENT} stopOpacity="0.9" />
          </linearGradient>
        </defs>

        <motion.path
          d={TRACE}
          fill="none"
          stroke="url(#trace-fade)"
          strokeWidth="2.5"
          strokeLinecap="round"
          initial={reduce ? { pathLength: 1 } : { pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.8, ease: 'easeInOut' }}
        />

        {/* glowing dot lapping the trace */}
        {!reduce && (
          <motion.circle r="4" fill={ACCENT}>
            <animateMotion dur="6s" repeatCount="indefinite" path={TRACE} keyPoints="0;1" keyTimes="0;1" calcMode="spline" keySplines="0.4 0 0.2 1" />
          </motion.circle>
        )}
      </svg>
    </div>
  )
}
