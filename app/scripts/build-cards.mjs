#!/usr/bin/env node
// AX-04 headless card builder. Loads each feature's own queries.ts + transform.ts through Vite's
// SSR loader (Node cannot resolve their extensionless imports itself, finding 2), swaps the three
// browser-only seams for the headless adapter (finding 3), and runs buildCards over a data dir
// laid out like app/public/data (a scratch export from scripts/export_app_data.py --out).
//
//   node scripts/build-cards.mjs --data <dir> [--kind K ...] [--limit N] [--out <dir>]
//
// Writes nothing unless --out is given; then writes <out>/cards.json and <out>/ungrounded.json.
// --stage (AX-08) writes <data>/assistant/_staging/{cards,build}.json and <data>/assistant/index.json for
// `export_app_data.py --finalize` (which converts to parquet, hashes, and writes the manifest block).
// It refuses an --out inside app/public/data unless --allow-public is also passed.
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
export const APP_DIR = resolve(HERE, '..')
const SRC = join(APP_DIR, 'src')
const HEADLESS = join(SRC, 'assistant/cards/headless')

/** Real module (resolved path) -> headless stand-in. */
export const SEAMS = {
  [join(SRC, 'data/duckdb/client.ts')]: join(HEADLESS, 'client.ts'),
  [join(SRC, 'data/duckdb/register.ts')]: join(HEADLESS, 'register.ts'),
  [join(SRC, 'data/manifest.ts')]: join(HEADLESS, 'manifest.ts'),
}

/** Vite plugin: after normal resolution, redirect the three seams (except from the stand-ins). */
export function headlessSeams() {
  return {
    name: 'ax04-headless-seams',
    enforce: 'pre',
    async resolveId(source, importer, options) {
      if (!importer) return null
      const r = await this.resolve(source, importer, { ...options, skipSelf: true })
      if (!r) return null
      const real = r.id.split('?')[0]
      if (!SEAMS[real]) return null
      // A stand-in that imports the real module gets it under a distinct id, so Vite's url->module
      // cache cannot hand the stand-in back to itself.
      if (importer.split('?')[0].startsWith(HEADLESS + sep)) return `${real}?ax04-real`
      return SEAMS[real]
    },
  }
}

/** Start a Vite SSR loader with the seams swapped and the adapter configured for dataDir. */
export async function createHeadless({ dataDir }) {
  const { createServer } = await import('vite')
  const server = await createServer({
    configFile: false,
    root: APP_DIR,
    logLevel: 'warn',
    appType: 'custom',
    server: { middlewareMode: true, hmr: false, watch: null },
    optimizeDeps: { noDiscovery: true, include: [] },
    resolve: { alias: { '@': SRC } },
    plugins: [headlessSeams()],
  })
  const load = (p) => server.ssrLoadModule(p)
  const adapter = await load('/src/assistant/cards/headless/adapter.ts')
  const seamManifest = await load('/src/assistant/cards/headless/manifest.ts') // re-exports DATA_CDN_BASE
  await adapter.configureHeadless({ dataDir: resolve(dataDir), cdnBase: seamManifest.DATA_CDN_BASE })
  const build = await load('/src/assistant/cards/build.ts')
  return {
    server,
    load,
    adapter,
    build,
    async close() {
      try {
        adapter.headless().close()
      } catch {
        /* not configured */
      }
      await server.close()
    },
  }
}

function parseArgs(argv) {
  const out = { kinds: [], allowPublic: false }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a === '--data') out.data = argv[++i]
    else if (a === '--out') out.out = argv[++i]
    else if (a === '--kind') out.kinds.push(argv[++i])
    else if (a === '--limit') out.limit = Number(argv[++i])
    else if (a === '--allow-public') out.allowPublic = true
    else if (a === '--stage') out.stage = true
    else if (a === '-h' || a === '--help') out.help = true
    else throw new Error(`unknown argument ${a}`)
  }
  return out
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (isMain) {
  const args = parseArgs(process.argv.slice(2))
  if (args.help || !args.data) {
    console.log('usage: node scripts/build-cards.mjs --data <dir> [--kind K ...] [--limit N] [--out <dir>] [--stage]')
    process.exit(args.help ? 0 : 2)
  }
  const publicData = join(APP_DIR, 'public/data')
  if (args.out && (resolve(args.out) + sep).startsWith(publicData + sep) && !args.allowPublic) {
    console.error(`refusing to write into ${publicData} without --allow-public`)
    process.exit(2)
  }
  const t0 = Date.now()
  const h = await createHeadless({ dataDir: args.data })
  try {
    const report = await h.build.buildCards({
      kinds: args.kinds.length ? args.kinds : undefined,
      limitPerKind: args.limit,
    })
    const reasons = {}
    for (const u of report.ungrounded) reasons[`${u.kind}: ${u.reason.slice(0, 90)}`] = (reasons[`${u.kind}: ${u.reason.slice(0, 90)}`] ?? 0) + 1
    console.log(JSON.stringify({ versions: report.versions, counts: report.counts, cards: report.cards.length, ungrounded: report.ungrounded.length, ungroundedReasons: reasons, ms: Date.now() - t0 }, null, 2))
    if (args.stage) {
      const reg = await h.load('/src/assistant/cards/registry.ts')
      const live = [...reg.classesLive].sort()
      const allClasses = [...new Set(reg.registry.map((x) => x.class))].sort()
      const stageDir = join(resolve(args.data), 'assistant', '_staging')
      mkdirSync(stageDir, { recursive: true })
      const cards = [...report.cards].sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0))
      writeFileSync(join(stageDir, 'cards.json'), JSON.stringify(cards))
      const kinds = reg.registry
        .map((x) => ({ kind: x.kind, class: x.class, held: !!x.held, ...report.counts[x.kind] }))
        .sort((a, b) => (a.kind < b.kind ? -1 : 1))
      const build = { versions: report.versions, classes_live: live, classes_held: allClasses.filter((c) => !live.includes(c)), kinds, ungrounded: report.ungrounded.length }
      writeFileSync(join(stageDir, 'build.json'), JSON.stringify(build, null, 1))
      writeFileSync(join(resolve(args.data), 'assistant', 'index.json'), JSON.stringify({ card_schema: '1', ...build, ungrounded: undefined, cards: cards.length }, null, 1))
      console.log(`staged ${cards.length} cards in ${stageDir}`)
    }
    if (args.out) {
      mkdirSync(args.out, { recursive: true })
      writeFileSync(join(args.out, 'cards.json'), JSON.stringify(report.cards, null, 1))
      writeFileSync(join(args.out, 'ungrounded.json'), JSON.stringify(report.ungrounded, null, 1))
      console.log(`wrote ${join(args.out, 'cards.json')} and ungrounded.json`)
    }
  } finally {
    await h.close()
  }
}
