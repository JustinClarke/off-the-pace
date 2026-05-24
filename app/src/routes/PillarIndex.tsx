// STATUS: done | Reusable pillar index lists child routes for current pillar from nav/routes.ts; re-used by every pillar index.tsx.
import { Link, useLocation } from 'react-router-dom'
import { routes } from '../nav/routes'
import { pillars } from '../nav/pillars'

export default function PillarIndex() {
  const { pathname } = useLocation()
  const pillar = pillars.find(p => p.path === pathname)
  const children = routes.filter(r => r.path.startsWith(pathname + '/') && r.path.split('/').length === pathname.split('/').length + 1)

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      {pillar && (
        <header className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-3xl">{pillar.icon}</span>
            <h1 className="text-2xl font-bold tracking-tight">{pillar.label}</h1>
          </div>
          <p className="text-muted">{pillar.description}</p>
        </header>
      )}
      {children.length > 0 && (
        <ul className="space-y-2">
          {children.map(route => (
            <li key={route.path}>
              <Link
                to={route.path}
                className="flex items-center justify-between p-4 rounded-lg border border-border bg-surface hover:border-[rgb(var(--color-accent))] transition-colors group"
              >
                <span className="text-sm font-medium group-hover:text-accent transition-colors">{route.label}</span>
                <span className="text-muted text-xs">→</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
