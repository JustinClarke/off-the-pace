// Top navigation bar: mobile menu button (below lg), brand title (every route except home),
// EngineStatus indicator, theme toggle.
import { Link, useLocation } from 'react-router-dom'
import { useTheme } from '../../state/ThemeContext'
import EngineStatus from './EngineStatus'

interface TopBarProps {
  /** Opens the mobile nav drawer. Only wired up below the lg breakpoint. */
  onMenuClick?: () => void
}

export default function TopBar({ onMenuClick }: TopBarProps) {
  const { resolvedTheme, setTheme } = useTheme()
  const { pathname } = useLocation()
  // Home already carries a large "Off The Pace" hero, so the brand is redundant there.
  const showBrand = pathname !== '/'

  return (
    <header className="flex items-center justify-between px-4 border-b border-border bg-surface" style={{ height: 56 }}>
      <div className="flex min-w-0 items-center gap-2">
        {onMenuClick && (
          <button
            onClick={onMenuClick}
            className="lg:hidden -ml-2 inline-flex h-10 w-10 items-center justify-center rounded-md text-muted hover:bg-surface hover:text-[rgb(var(--color-text))] transition-colors"
            aria-label="Open navigation menu"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        )}
        {showBrand && (
          <Link to="/" className="flex shrink-0 items-center gap-2 text-[rgb(var(--color-text))] transition-colors hover:text-accent" aria-label="Off The Pace home">
            <span className="flex h-5 w-5 items-center justify-center text-[rgb(var(--color-accent))]">
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinejoin="round">
                <path d="M12 2.5l8.5 4.9v9.2L12 21.5 3.5 16.6V7.4z" />
                <path d="M12 7.5v9M8 9.5l8 5M16 9.5l-8 5" strokeWidth="1.1" opacity="0.55" />
              </svg>
            </span>
            <span className="truncate text-sm font-bold tracking-tight">Off The Pace</span>
          </Link>
        )}
        <EngineStatus />
      </div>
      <div className="flex items-center gap-2 ml-auto">
        <button
          onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
          className="-mr-1.5 inline-flex h-10 w-10 items-center justify-center rounded-md text-muted hover:bg-surface hover:text-[rgb(var(--color-text))] transition-colors text-base"
          aria-label="Toggle theme"
        >
          {resolvedTheme === 'dark' ? '☀' : '☾'}
        </button>
      </div>
    </header>
  )
}
