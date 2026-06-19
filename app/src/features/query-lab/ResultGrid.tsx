// Dynamic-column results grid for the Query Lab. Unlike RankedTable (fixed columns), columns
// are derived from the query result at runtime. Renders up to RENDER_CAP rows with a note.
import type { LabResult } from '../../data/duckdb/queryLab'

const RENDER_CAP = 1000

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') return Number.isInteger(v) ? v.toLocaleString() : String(v)
  return String(v)
}

export default function ResultGrid({ result }: { result: LabResult }) {
  const { columns, rows } = result
  const visible = rows.slice(0, RENDER_CAP)

  if (!columns.length) {
    return <p className="px-4 py-6 text-sm text-muted">Query ran but returned no columns.</p>
  }
  if (!rows.length) {
    return <p className="px-4 py-6 text-sm text-muted">No rows.</p>
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full border-collapse text-[12px]">
          <thead className="sticky top-0 z-10 bg-surface">
            <tr>
              {columns.map(c => (
                <th
                  key={c}
                  className="border-b border-border px-3 py-1.5 text-left font-mono text-[10px] uppercase tracking-wider text-muted whitespace-nowrap"
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row, i) => (
              <tr key={i} className="hover:bg-white/[0.02]">
                {columns.map(c => {
                  const v = row[c]
                  const numeric = typeof v === 'number'
                  return (
                    <td
                      key={c}
                      className={[
                        'border-b border-border/40 px-3 py-1 whitespace-nowrap',
                        numeric ? 'text-right font-mono tabular-nums' : 'text-left',
                        v === null || v === undefined ? 'text-muted/50' : '',
                      ].filter(Boolean).join(' ')}
                    >
                      {formatCell(v)}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > RENDER_CAP && (
        <p className="shrink-0 border-t border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-wider text-muted">
          showing {RENDER_CAP.toLocaleString()} of {result.rowCount.toLocaleString()}
          {result.truncated ? '+ (capped)' : ''} rows — Export CSV emits the full set
        </p>
      )}
    </div>
  )
}
