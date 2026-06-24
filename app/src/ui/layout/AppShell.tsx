// Root layout shell renders Sidebar + TopBar wrapper around the outlet. The sidebar is docked at
// lg and up; below lg it becomes an off-canvas drawer (hamburger in the TopBar opens it, the
// backdrop / a nav tap / Escape / any route change closes it).
import { ReactNode, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import { preferences } from '../../state/preferences'

interface AppShellProps {
  children: ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(() => preferences.sidebarCollapsed)
  const [mobileOpen, setMobileOpen] = useState(false)
  const { pathname } = useLocation()

  const handleToggle = () => {
    const next = !collapsed
    preferences.sidebarCollapsed = next
    setCollapsed(next)
  }

  // Close the mobile drawer whenever the route changes (covers programmatic / back-button nav).
  useEffect(() => {
    setMobileOpen(false)
  }, [pathname])

  // Close on Escape while the drawer is open.
  useEffect(() => {
    if (!mobileOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [mobileOpen])

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Docked sidebar (lg and up) */}
      <div className="hidden lg:block">
        <Sidebar collapsed={collapsed} onToggle={handleToggle} />
      </div>

      {/* Mobile off-canvas drawer (below lg) */}
      <div className="lg:hidden">
        <div
          className={[
            'fixed inset-0 z-40 bg-black/50 transition-opacity duration-200',
            mobileOpen ? 'opacity-100' : 'pointer-events-none opacity-0',
          ].join(' ')}
          onClick={() => setMobileOpen(false)}
          aria-hidden
        />
        <div
          className={[
            'fixed inset-y-0 left-0 z-50 transition-transform duration-200 ease-out',
            mobileOpen ? 'translate-x-0' : '-translate-x-full',
          ].join(' ')}
        >
          <Sidebar onNavigate={() => setMobileOpen(false)} />
        </div>
      </div>

      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <TopBar onMenuClick={() => setMobileOpen(true)} />
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  )
}
