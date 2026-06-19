// CSV serialisation helpers; respects the user's separator preference from state/preferences.
import { preferences } from '../state/preferences'

export function toCsv(rows: Record<string, unknown>[]): string {
  if (!rows.length) return ''
  const delimiter = preferences.csvDelimiter
  const headers = Object.keys(rows[0])
  const lines = rows.map(row =>
    headers.map(h => {
      const v = row[h]
      const s = v === null || v === undefined ? '' : String(v)
      return s.includes(delimiter) || s.includes('"') || s.includes('\n')
        ? `"${s.replace(/"/g, '""')}"`
        : s
    }).join(delimiter)
  )
  return [headers.join(delimiter), ...lines].join('\n')
}

export function downloadCsv(filename: string, rows: Record<string, unknown>[]): void {
  const blob = new Blob([toCsv(rows)], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
