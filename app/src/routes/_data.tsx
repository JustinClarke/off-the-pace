// STATUS: done | Data layout triggers DuckDB init on mount; shows spinner while initialising; renders FilterBar above data routes.
import { Outlet } from 'react-router-dom'
import { useEffect } from 'react'
import { getConnection } from '../data/duckdb/client'
import FilterBar from '../ui/layout/FilterBar'
import { useDatabaseStatus } from '../data/hooks/useDatabaseStatus'
import Spinner from '../ui/feedback/Spinner'

export default function DataLayout() {
  const { status } = useDatabaseStatus()

  useEffect(() => {
    getConnection()
  }, [])

  if (status === 'initializing') {
    return (
      <div className="flex items-center justify-center h-64 gap-3 text-muted text-sm">
        <Spinner />
        Initialising query engine…
      </div>
    )
  }

  return (
    <>
      <FilterBar />
      <Outlet />
    </>
  )
}
