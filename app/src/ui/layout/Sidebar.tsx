// Navigation sidebar-renders pillar links from nav/pillars.ts using monochrome line
// icons (PillarIcon), respects feature flags, and marks the active route with an accent
// rail. No emoji: every icon is a stroke SVG that inherits the nav text colour.
import { NavLink } from 'react-router-dom'
import { pillars } from '../../nav/pillars'
import { FEATURE_FLAGS } from '../../config'
import PillarIcon from './PillarIcon'

interface SidebarProps {
  collapsed?: boolean
  onToggle?: () => void
}

export default function Sidebar({ collapsed = false, onToggle }: SidebarProps) {
  const visible = pillars.filter(
    (p) => !p.featureFlag || FEATURE_FLAGS[p.featureFlag as keyof typeof FEATURE_FLAGS],
  )

  return (
    <nav
      className="flex h-full flex-col border-r border-border bg-surface transition-all"
      style={{ width: collapsed ? 56 : 220 }}
      aria-label="Main navigation"
    >
      {/* Brand mark */}
      <div className="flex items-center gap-2.5 border-b border-border px-4 py-4">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center text-[rgb(var(--color-accent))]">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinejoin="round">
            <path d="M12 2.5l8.5 4.9v9.2L12 21.5 3.5 16.6V7.4z" />
            <path d="M12 7.5v9M8 9.5l8 5M16 9.5l-8 5" strokeWidth="1.1" opacity="0.55" />
          </svg>
        </span>
        {!collapsed && <span className="text-sm font-bold tracking-tight">Off The Pace</span>}
      </div>

      <ul className="flex-1 space-y-0.5 overflow-y-auto px-2 py-3">
        {visible.map((pillar) => (
          <li key={pillar.id}>
            <NavLink
              to={pillar.path}
              end={pillar.path === '/'}
              title={collapsed ? pillar.label : undefined}
              className={({ isActive }) =>
                [
                  'group relative flex items-center gap-3 rounded-md px-3 py-2 text-[13px] transition-colors',
                  isActive
                    ? 'bg-accent-subtle font-medium text-accent'
                    : 'text-muted hover:bg-[rgb(var(--color-bg)/0.6)] hover:text-[rgb(var(--color-text))]',
                ].join(' ')
              }
            >
              {({ isActive }) => (
                <>
                  {/* active accent rail */}
                  <span
                    aria-hidden
                    className={[
                      'absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-[rgb(var(--color-accent))] transition-opacity',
                      isActive ? 'opacity-100' : 'opacity-0',
                    ].join(' ')}
                  />
                  <PillarIcon id={pillar.id} className="shrink-0" />
                  {!collapsed && <span className="truncate">{pillar.label}</span>}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>

      <div className="border-t border-border px-3 py-3 flex items-end justify-between gap-2">
        {!collapsed && (
          <p className="font-mono text-[10px] leading-relaxed text-muted/70">
            Client-side F1 analytics.
            <br />
            DuckDB-Wasm + ONNX.
          </p>
        )}
        {onToggle && (
          <button
            onClick={onToggle}
            className={[
              'shrink-0 p-1.5 rounded-full border border-border bg-surface text-muted text-xs shadow-sm hover:text-[rgb(var(--color-text))] transition-colors',
              collapsed ? 'mx-auto' : 'ml-auto',
            ].join(' ')}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? '→' : '←'}
          </button>
        )}
      </div>
    </nav>
  )
}
