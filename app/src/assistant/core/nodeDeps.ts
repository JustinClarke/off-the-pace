// AX-10 headless runtime (Node): the dispatcher's dependencies over a published-data folder laid out like
// app/public/data (or a scratch export), through the AX-04 adapter (duckdb-wasm's Node bundle: the same
// DuckDB build the browser runs). Used by the CLI and the node tests; the browser wires the same
// dispatcher over its own loaders (AX-14). Nothing here opens a network socket or a .duckdb file.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import type { Card } from '../cards/card.types'
import { createAdapter, createWasmEngine, type Adapter } from '../cards/headless/adapter'
import { parseCatalogue, type Catalogue } from '../catalogue/catalogue'
import { compareLapTimes } from '../charts/compareLapTimes'
import type { DataManifest } from '../../data/manifest'
import { listValuesFromRows, type EntityRow, type ListValuesInput } from '../listValues'
import { routeToPageId } from '../../nav/assistantTools'
import { runQuery, type Engine } from '../queryBuilder/run'
import { cardFromParquetRow, createCardStore, type CardStore } from './cardStore'
import { createDispatcher, type Dispatcher, type KindInfo } from './dispatcher'
import type { LoopDeps } from './loop'
import type { OnScreenSpec } from './preload'
import type { ModelClient } from './types'
import type { ToolDef } from './validateArgs'

export interface NodeRuntimeOptions {
  /** A data root with _manifest.json, assistant/catalogue.json, assistant/qv/** and dimensions/assistant_entities.parquet. */
  dataDir: string
  /** Cards to serve. Absent: read the published card parquet files the manifest lists (manifest.assistant.cards). */
  cards?: readonly Card[]
  tools: readonly ToolDef[]
  /** The Worker's system prompt (budget meter only). */
  system: string
  kinds: readonly KindInfo[]
  specs: readonly OnScreenSpec[]
}

export interface NodeRuntime {
  store: CardStore
  catalogue: Catalogue
  manifest: DataManifest
  /** Read from the data folder, never hard-coded: the export's manifest version and the catalogue version the Worker checks. */
  versions: DataVersions
  entities: EntityRow[]
  /** A fresh dispatcher (own list_values cache and session record) over the shared adapter. */
  newDispatcher(): Dispatcher
  loopDeps(model: ModelClient, dispatcher?: Dispatcher): LoopDeps
  close(): void
}

export interface DataVersions {
  manifest_version: string
  generated_at: string
  catalogue_version: string
  /** Where the cards came from: 'parquet' (the published files) or 'json' (a build-cards cards.json). */
  cards_source: 'parquet' | 'json'
  cards: number
}

/** The published card files (manifest.assistant.cards), decoded back to Cards. The files must sit in one folder
 *  (assistant/cards/); the folder is read whole and its row count checked against the manifest's list. */
export async function loadPublishedCards(adapter: Adapter, manifest: DataManifest): Promise<Card[]> {
  const files = manifest.assistant?.cards ?? []
  if (!files.length) throw new Error('the manifest lists no assistant cards (manifest.assistant.cards)')
  const dirs = new Set(files.map((f) => f.path.slice(0, f.path.lastIndexOf('/') + 1)))
  if (dirs.size !== 1) throw new Error(`card files are not in one folder: ${[...dirs].join(', ')}`)
  await adapter.registerParquet('assistant_cards', [...dirs][0])
  const rows = await adapter.query<Record<string, unknown>>('SELECT * FROM assistant_cards')
  const listed = files.reduce((n, f) => n + f.rows, 0)
  if (rows.length !== listed) throw new Error(`card folder holds ${rows.length} rows, the manifest lists ${listed}`)
  return rows.map(cardFromParquetRow)
}

export function loadCardsJson(path: string): Card[] {
  const cards = JSON.parse(readFileSync(path, 'utf8')) as Card[]
  if (!Array.isArray(cards)) throw new Error(`${path} is not a cards.json array`)
  return cards
}

export async function createNodeRuntime(o: NodeRuntimeOptions): Promise<NodeRuntime> {
  const adapter: Adapter = createAdapter({ dataDir: o.dataDir }, await createWasmEngine())
  const catalogue = parseCatalogue(JSON.parse(readFileSync(join(o.dataDir, 'assistant', 'catalogue.json'), 'utf8')))
  const manifest = JSON.parse(readFileSync(join(o.dataDir, '_manifest.json'), 'utf8')) as DataManifest

  const table = manifest.tables.find((t) => t.name === 'assistant_entities')
  if (!table) throw new Error('assistant_entities is not in the manifest')
  await adapter.registerParquet('assistant_entities', table.path as string)
  const raw = await adapter.query<Record<string, string | null>>('SELECT domain, code, display, aliases, seasons, parent_code, extra FROM assistant_entities')
  const entities: EntityRow[] = raw.map((r) => ({
    domain: String(r.domain),
    code: String(r.code),
    display: String(r.display),
    aliases: JSON.parse(r.aliases ?? '[]'),
    seasons: JSON.parse(r.seasons ?? '[]'),
    parent_code: r.parent_code ?? null,
    extra: JSON.parse(r.extra ?? '{}'),
  }))
  // The domains list_values builds in the browser from other sources: pages (route table), columns (catalogue), card kinds (registry).
  const extra: EntityRow[] = [
    ...Object.entries(routeToPageId).map(([route, id]) => ({
      domain: 'page', code: route, display: id, aliases: [id, id.replace(/-/g, ' '), route.split('/').filter(Boolean).join(' ')],
      seasons: [], parent_code: null, extra: { page_id: id },
    })),
    ...[...new Set(catalogue.views.flatMap((v) => v.columns.map((c) => c.name)))].map((name) => ({
      domain: 'columns', code: name, display: name.replace(/_/g, ' '), aliases: [], seasons: [], parent_code: null, extra: {},
    })),
    ...o.kinds.map((k) => ({ domain: 'card_kind', code: k.kind, display: k.kind.replace(/[._]/g, ' '), aliases: [], seasons: [], parent_code: null, extra: {} })),
  ]
  const allEntities = [...entities, ...extra]

  const engine: Engine = {
    registerPartition: (alias, url) => adapter.registerParquet(alias, url),
    prepareRun: (sql, params) => adapter.query(sql, params),
    cancel: async () => undefined,
  }
  const runDeps = { catalogue, manifest, engine }
  const cards = o.cards ?? (await loadPublishedCards(adapter, manifest))
  const store = createCardStore(cards)
  const catalogueVersion = catalogue.catalogue_version
  const listed = manifest.assistant?.catalogue_version
  if (listed && catalogueVersion && listed !== catalogueVersion) {
    throw new Error(`catalogue.json version ${catalogueVersion.slice(0, 12)} differs from the manifest's ${listed.slice(0, 12)}: mixed export`)
  }
  const versions: DataVersions = {
    manifest_version: manifest.version,
    generated_at: manifest.generatedAt,
    catalogue_version: catalogueVersion ?? listed ?? '',
    cards_source: o.cards ? 'json' : 'parquet',
    cards: cards.length,
  }

  const newDispatcher = () =>
    createDispatcher({
      tools: o.tools,
      cards: store,
      kinds: o.kinds,
      listValues: async (input: ListValuesInput) => listValuesFromRows(allEntities, input),
      queryData: (req) => runQuery(req, runDeps),
      compareLapTimes: (a, b, race) => compareLapTimes(a, b, race, { ...runDeps, entities }),
    })

  return {
    store,
    catalogue,
    manifest,
    versions,
    entities,
    newDispatcher,
    loopDeps: (model, dispatcher) => ({
      model,
      dispatcher: dispatcher ?? newDispatcher(),
      store,
      system: o.system,
      toolsJson: JSON.stringify(o.tools),
      specs: o.specs,
    }),
    close: () => adapter.close(),
  }
}
