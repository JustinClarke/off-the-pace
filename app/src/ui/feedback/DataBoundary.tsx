// Composite wrapper: ErrorBoundary + ChartSkeleton the standard outer shell for every data-driven route section.
import { ReactNode } from 'react'
import { ChartSkeleton } from './Skeleton'
import { ErrorBoundary } from './ErrorBoundary'
import EmptyState from './EmptyState'

interface DataBoundaryProps {
  isLoading: boolean
  error: Error | null
  isEmpty?: boolean
  children: ReactNode
  skeletonHeight?: number
}

export default function DataBoundary({ isLoading, error, isEmpty, children, skeletonHeight }: DataBoundaryProps) {
  if (isLoading) return <ChartSkeleton height={skeletonHeight} />
  if (error) {
    return (
      <div className="p-6 rounded border border-red-500/20 bg-red-500/5 text-sm text-muted">
        <p className="font-medium text-red-400 mb-1">Query failed</p>
        <p className="font-mono text-xs">{error.message}</p>
      </div>
    )
  }
  if (isEmpty) return <EmptyState />
  return <ErrorBoundary>{children}</ErrorBoundary>
}
