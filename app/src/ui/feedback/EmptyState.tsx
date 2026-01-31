// Empty-state component shown when a query returns zero rows; displays title, description, and optional action.
interface EmptyStateProps {
  title?: string
  description?: string
  icon?: string
}

export default function EmptyState({ title = 'No data', description, icon = '📭' }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center text-muted">
      <span className="text-4xl">{icon}</span>
      <p className="text-sm font-medium">{title}</p>
      {description && <p className="text-xs max-w-xs">{description}</p>}
    </div>
  )
}
