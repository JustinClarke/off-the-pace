// AX-14 browser runtime for the AX-10 loop: the card store (manifest.assistant.cards parquet through the
// shared DuckDB-wasm), the catalogue, the entities, the bounded query engine, and the dispatcher over them.
// Loaded lazily on the first question (dynamic import in useChat), so opening the drawer costs nothing.
// The Worker owns the system prompt and the tool list; the tool schemas here (for argument validation) are
// the generated ones the Worker was built with.
import { TOOLS } from '../../../../worker/src/generated/tools'
import { DATA_CDN_BASE, loadManifest } from '../../data/manifest'
import { routeToPageId } from '../../nav/assistantTools'
import type { Card } from '../cards/card.types'
import { heldReasonFor, registry } from '../cards/registry'
import { loadCatalogue } from '../catalogue/catalogue'
import { compareLapTimes } from '../charts/compareLapTimes'
import { cardFromParquetRow, createCardStore, type CardStore } from '../core/cardStore'
import { createDispatcher, type Dispatcher } from '../core/dispatcher'
import type { LoopDeps } from '../core/loop'
import type { ModelClient } from '../core/types'
import type { ToolDef } from '../core/validateArgs'
import { listValuesFromRows, type EntityRow, type ListValuesInput } from '../listValues'
import { realEngine } from '../queryBuilder/realEngine'
import { runQuery } from '../queryBuilder/run'
import { registerParquet } from '../../data/duckdb/register'

export class RuntimeUnavailableError extends Error {}

export interface DrawerRuntime {
  store: CardStore
  catalogueVersion: string
  newDispatcher(): Dispatcher
  loopDeps(model: ModelClient, dispatcher: Dispatcher): LoopDeps
}

let loading: Promise<DrawerRuntime> | null = null

export function loadDrawerRuntime(): Promise<DrawerRuntime> {
  if (!loading) {
    loading = build().catch((e) => {
      loading = null // allow a retry after a failed load
      throw e
    })
  }
  return loading
}

async function build(): Promise<DrawerRuntime> {
  const [manifest, catalogue] = await Promise.all([loadManifest(), loadCatalogue()])
  const a = manifest.assistant
  if (!a || a.cards.length === 0) throw new RuntimeUnavailableError('the published data has no assistant cards')

  const url = (path: string) => `${DATA_CDN_BASE}${path}?v=${encodeURIComponent(manifest.version)}`
  const cards: Card[] = []
  for (const f of a.cards) {
    const alias = `assistant_cards_${f.season ?? 'global'}`
    await registerParquet(alias, url(f.path))
    for (const row of await realEngine.prepareRun(`SELECT * FROM ${alias}`, [])) cards.push(cardFromParquetRow(row))
  }
  const store = createCardStore(cards)

  const table = manifest.tables.find((t) => t.name === 'assistant_entities')
  if (!table) throw new RuntimeUnavailableError('assistant_entities is not in the manifest')
  await registerParquet('assistant_entities', url(table.path))
  const raw = await realEngine.prepareRun('SELECT domain, code, display, aliases, seasons, parent_code, extra FROM assistant_entities', [])
  const entities: EntityRow[] = raw.map((r) => ({
    domain: String(r.domain),
    code: String(r.code),
    display: String(r.display),
    aliases: JSON.parse((r.aliases as string | null) ?? '[]'),
    seasons: JSON.parse((r.seasons as string | null) ?? '[]'),
    parent_code: (r.parent_code as string | null) ?? null,
    extra: JSON.parse((r.extra as string | null) ?? '{}'),
  }))
  const kinds = registry.map((s) => ({ kind: s.kind, held_reason: heldReasonFor(s) }))
  const allEntities: EntityRow[] = [
    ...entities,
    ...Object.entries(routeToPageId).map(([route, id]) => ({
      domain: 'page', code: route, display: id, aliases: [id, id.replace(/-/g, ' '), route.split('/').filter(Boolean).join(' ')],
      seasons: [], parent_code: null, extra: { page_id: id },
    })),
    ...[...new Set(catalogue.views.flatMap((v) => v.columns.map((c) => c.name)))].map((name) => ({
      domain: 'columns', code: name, display: name.replace(/_/g, ' '), aliases: [], seasons: [], parent_code: null, extra: {},
    })),
    ...kinds.map((k) => ({ domain: 'card_kind', code: k.kind, display: k.kind.replace(/[._]/g, ' '), aliases: [], seasons: [], parent_code: null, extra: {} })),
  ]
  const runDeps = { catalogue, manifest, engine: realEngine, dataBase: DATA_CDN_BASE }
  const tools = TOOLS as ToolDef[]
  const newDispatcher = () =>
    createDispatcher({
      tools,
      cards: store,
      kinds,
      listValues: async (input: ListValuesInput) => listValuesFromRows(allEntities, input),
      queryData: (req) => runQuery(req, runDeps),
      compareLapTimes: (x, y, race) => compareLapTimes(x, y, race, { ...runDeps, entities }),
    })
  return {
    store,
    catalogueVersion: a.catalogue_version,
    newDispatcher,
    // system and toolsJson feed only the budget meter (the Worker injects the real ones).
    loopDeps: (model, dispatcher) => ({ model, dispatcher, store, system: '', toolsJson: JSON.stringify(tools), specs: registry }),
  }
}
