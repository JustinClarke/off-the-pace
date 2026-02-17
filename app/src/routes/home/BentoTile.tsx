// A single bento-grid tile: animated entrance, hover lift, and a cursor-tracking
// spotlight glow. Renders a feature's mini-viz, title, hook, and a tag row. The whole
// tile is a router Link into the live feature page.
import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

export interface BentoFeature {
  id: number
  title: string
  hook: string
  to: string
  tag: string
  Viz: () => JSX.Element
  /** Tailwind span classes for the bento layout (col/row spans). */
  span: string
  /** Optional accent flag for the flagship tiles. */
  flagship?: boolean
}

const tileVariants = {
  hidden: { opacity: 0, y: 24, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1 },
}

export default function BentoTile({ feature }: { feature: BentoFeature }) {
  const ref = useRef<HTMLAnchorElement>(null)
  const [glow, setGlow] = useState<{ x: number; y: number; on: boolean }>({ x: 0, y: 0, on: false })

  function onMove(e: React.MouseEvent) {
    const el = ref.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    setGlow({ x: e.clientX-rect.left, y: e.clientY-rect.top, on: true })
  }

  const { Viz } = feature

  return (
    <motion.div variants={tileVariants} className={feature.span}>
      <Link
        ref={ref}
        to={feature.to}
        onMouseMove={onMove}
        onMouseLeave={() => setGlow((g) => ({ ...g, on: false }))}
        className={[
          'group relative flex h-full flex-col overflow-hidden rounded-2xl border bg-surface',
          'transition-all duration-300 ease-out',
          'hover:-translate-y-1 hover:shadow-xl hover:shadow-black/5 dark:hover:shadow-black/40',
          feature.flagship
            ? 'border-[rgb(var(--color-accent))]/30 hover:border-[rgb(var(--color-accent))]/70'
            : 'border-border hover:border-[rgb(var(--color-accent))]/50',
        ].join(' ')}
      >
        {/* cursor spotlight */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
          style={{
            background: glow.on
              ? `radial-gradient(220px circle at ${glow.x}px ${glow.y}px, rgb(var(--color-accent) / 0.10), transparent 70%)`
              : 'transparent',
          }}
        />
        {/* gradient hairline at top, lights up on hover */}
        <div
          aria-hidden
          className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[rgb(var(--color-accent))]/0 to-transparent transition-all duration-500 group-hover:via-[rgb(var(--color-accent))]/60"
        />

        <div className="relative flex h-full flex-col p-3.5">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[9px] uppercase tracking-widest text-muted">
              {feature.tag}
            </span>
            <span className="font-mono text-[9px] text-muted/60">#{feature.id}</span>
          </div>

          {/* compact mini-viz strip */}
          <div className="my-2.5 h-12">
            <Viz />
          </div>

          <h3 className="text-[13px] font-semibold tracking-tight text-[rgb(var(--color-text))] transition-colors group-hover:text-accent">
            {feature.title}
          </h3>
          <p className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-muted">{feature.hook}</p>
        </div>
      </Link>
    </motion.div>
  )
}
