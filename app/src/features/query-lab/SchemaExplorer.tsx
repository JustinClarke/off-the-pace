// Schema rail for the Query Lab: manifest tables grouped by layer (dim/fct/int/mart/ml).
// Click a table name to insert it into the editor; expand to lazily DESCRIBE its columns.
import { useState } from 'react'
import type { DataManifest, TableManifest } from '../../data/manifest'
import { getTablePath } from '../../data/manifest'
import { registerParquet, registerPartitionedParquet } from '../../data/duckdb/register'
import { getLabConnection } from '../../data/duckdb/queryLab'

const LAYERS: { key: string; label: string; match: (n: string) => boolean }[] = [
  { key: 'dim', label: 'dimensions', match: n => n.startsWith('dim_') || n === 'race_to_track' || n === 'driver_network_rating' },
  { key: 'fct', label: 'facts', match: n => n.startsWith('fct_') },
  { key: 'int', label: 'intermediate', match: n => n.startsWith('int_') },
  { key: 'mart', label: 'marts', match: n => n.startsWith('mart_') },
  { key: 'ml', label: 'ml', match: n => n.startsWith('ml') },
]

function layerOf(name: string): string {
  return LAYERS.find(l => l.match(name))?.key ?? 'other'
}

async function describeColumns(table: TableManifest, manifest: DataManifest): Promise<string[]> {
  if (table.partitioned) await registerPartitionedParquet(table.name, manifest)
  else await registerParquet(table.name, getTablePath(manifest, table.name))
  const conn = await getLabConnection()
  const res = await conn.query(`DESCRIBE ${table.name}`)
  return res.toArray().map(r => String((r.toJSON() as Record<string, unknown>).column_name))
}

function TableRow({
  table,
  manifest,
  onInsert,
}: {
  table: TableManifest
  manifest: DataManifest
  onInsert: (text: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [cols, setCols] = useState<string[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function toggle() {
    const next = !expanded
    setExpanded(next)
    if (next && cols === null && !loading) {
      setLoading(true)
      setErr(null)
      try {
        setCols(await describeColumns(table, manifest))
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e))
      } finally {
        setLoading(false)
      }
    }
  }

  return (
    <div>
      <div className="flex items-center gap-1">
        <button
          onClick={toggle}
          className="flex h-4 w-4 shrink-0 items-center justify-center text-muted/60 hover:text-accent"
          aria-label={expanded ? 'Collapse' : 'Expand'}
        >
          <span className={`transition-transform ${expanded ? 'rotate-90' : ''}`}>›</span>
        </button>
        <button
          onClick={() => onInsert(table.name)}
          className="truncate text-left font-mono text-[11px] text-[rgb(var(--color-text))] hover:text-accent"
          title={`Insert ${table.name}`}
        >
          {table.name}
          {table.partitioned && <span className="ml-1 text-muted/50">⋮</span>}
        </button>
      </div>
      {expanded && (
        <div className="ml-5 mt-0.5 mb-1 flex flex-col gap-0.5">
          {loading && <span className="text-[10px] text-muted">loading…</span>}
          {err && <span className="text-[10px] text-red-400">{err}</span>}
          {cols?.map(c => (
            <button
              key={c}
              onClick={() => onInsert(c)}
              className="truncate text-left font-mono text-[10px] text-muted hover:text-accent"
              title={`Insert ${c}`}
            >
              {c}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function SchemaExplorer({
  manifest,
  onInsert,
}: {
  manifest: DataManifest
  onInsert: (text: string) => void
}) {
  const grouped = LAYERS.map(l => ({
    ...l,
    tables: manifest.tables.filter(t => layerOf(t.name) === l.key).sort((a, b) => a.name.localeCompare(b.name)),
  })).filter(g => g.tables.length)

  return (
    <div className="flex flex-col gap-3">
      {grouped.map(group => (
        <div key={group.key}>
          <div className="mb-1 font-mono text-[9px] uppercase tracking-widest text-muted/70">
            {group.label} · {group.tables.length}
          </div>
          <div className="flex flex-col gap-0.5">
            {group.tables.map(t => (
              <TableRow key={t.name} table={t} manifest={manifest} onInsert={onInsert} />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
