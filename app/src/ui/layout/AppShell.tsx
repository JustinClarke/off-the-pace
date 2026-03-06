// Root layout shell renders Sidebar + TopBar wrapper around the outlet; owns the mobile-drawer open state.
import { ReactNode, useState } from 'react'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import { preferences } from '../../state/preferences'

interface AppShellProps {
  children: ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(() => preferences.sidebarCollapsed)

  const handleToggle = () => {
    const next = !collapsed
    preferences.sidebarCollapsed = next
    setCollapsed(next)
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar collapsed={collapsed} onToggle={handleToggle} />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  )
}
