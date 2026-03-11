// STATUS: done | Root layout FilterProvider + AppShell + ErrorBoundary; updates document.title on navigation.
import { Outlet, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import { FilterProvider } from '../state/FilterContext'
import AppShell from '../ui/layout/AppShell'
import { ErrorBoundary } from '../ui/feedback/ErrorBoundary'
import { getPageMeta } from '../nav/seo'

export default function Root() {
  const { pathname } = useLocation()

  useEffect(() => {
    const { title } = getPageMeta(pathname)
    document.title = title
  }, [pathname])

  return (
    <FilterProvider>
      <AppShell>
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </AppShell>
    </FilterProvider>
  )
}
