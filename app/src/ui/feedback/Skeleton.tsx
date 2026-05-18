// Skeleton placeholder shapes (block, text, ChartSkeleton) used while DuckDB queries are in flight.
interface SkeletonProps {
  className?: string
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div className={`animate-pulse rounded bg-surface ${className ?? ''}`} />
  )
}

export function ChartSkeleton({ height = 320 }: { height?: number }) {
  return (
    <div className="flex flex-col gap-2 p-4" style={{ height }}>
      <Skeleton className="h-4 w-1/3" />
      <div className="flex-1 rounded bg-surface animate-pulse" />
    </div>
  )
}
