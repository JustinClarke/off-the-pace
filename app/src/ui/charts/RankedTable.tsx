import { ReactNode } from 'react'

export interface RankedTableColumn<T> {
  key: keyof T
  header: string
  /** Custom cell renderer. If omitted, value is stringified. */
  render?: (value: unknown, row: T) => ReactNode
  align?: 'left' | 'right' | 'center'
  /** Highlight the cell based on the row e.g. colour-code deltas */
  cellClass?: (value: unknown, row: T) => string | undefined
}

export interface RankedTableProps<T> {
  rows: T[]
  columns: RankedTableColumn<T>[]
  /** Column key to sort by (descending magnitude); omit to preserve input order */
  sortKey?: keyof T
  sortDir?: 'asc' | 'desc'
  /** Max rows to show before a "show all" toggle */
  initialRows?: number
  /** Highlight the row at this index (0-based) */
  pinnedRow?: number
  emptyMessage?: string
  /** Extra class(es) to apply to each row */
  rowClass?: (row: T) => string | undefined
}

const ALIGN: Record<string, string> = {
  left: 'text-left',
  right: 'text-right',
  center: 'text-center',
}

export default function RankedTable<T extends object>({
  rows,
  columns,
  sortKey,
  sortDir = 'desc',
  initialRows = 20,
  pinnedRow,
  emptyMessage = 'No data',
  rowClass,
}: RankedTableProps<T>) {
  const sorted = sortKey
    ? [...rows].sort((a, b) => {
        const av = (a as Record<keyof T, unknown>)[sortKey] as number
        const bv = (b as Record<keyof T, unknown>)[sortKey] as number
        return sortDir === 'desc' ? bv-av : av-bv
      })
    : rows

  const visible = sorted.slice(0, initialRows)
  const hidden = sorted.length-visible.length

  if (!rows.length) {
    return <p className="text-sm text-muted py-4">{emptyMessage}</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b border-border">
            {columns.map(col => (
              <th
                key={String(col.key)}
                className={`py-2 px-3 text-xs font-medium text-muted ${ALIGN[col.align ?? 'left']}`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visible.map((row, i) => (
            <tr
              key={i}
              className={`border-b border-border/50 transition-colors ${
                i === pinnedRow
                  ? 'bg-accent/10'
                  : 'hover:bg-surface'
              } ${rowClass ? (rowClass(row) ?? '') : ''}`}
            >
              {columns.map(col => {
                const val = (row as Record<keyof T, unknown>)[col.key]
                const extra = col.cellClass ? col.cellClass(val, row) : undefined
                return (
                  <td
                    key={String(col.key)}
                    className={`py-2 px-3 font-mono ${ALIGN[col.align ?? 'left']} ${extra ?? ''}`}
                  >
                    {col.render ? col.render(val, row) : String(val ?? '')}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {hidden > 0 && (
        <p className="text-xs text-muted/60 mt-2 px-3">
          + {hidden} more rows (export CSV for full data)
        </p>
      )}
    </div>
  )
}
