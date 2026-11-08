#!/usr/bin/env node
// AX-10 headless assistant CLI. Runs questions through the assistant core (dispatcher, loop, checker,
// grounding, budget meter) against published data files, with NO browser and NO network by default.
//
//   node scripts/assistant-cli.mjs --data <dir> --cards <cards.json> --stub --sample [--out run.json]
//   node scripts/assistant-cli.mjs --data <dir> --cards <cards.json> --stub --demo
//   node scripts/assistant-cli.mjs --data <dir> --cards <cards.json> --endpoint http://127.0.0.1:8787/v1/chat \
//        --protocol worker --catalogue-version <v> --question "How did Verstappen do against Perez in Bahrain 2024?" \
//        [--page /race-craft/race-control?season=2024&race_id=2024_1]
//   node scripts/assistant-cli.mjs --data <dir> --cards <cards.json> --call 'explain_page={"page":"/drivers/ratings-timeline"}'
//
// --data   a folder laid out like app/public/data (default: $AX06_DATA_DIR, else app/public/data). Read-only.
// --cards  a build-cards cards.json (the published parquet cards are read by the browser store, AX-14).
// --stub   scripted model for --sample / --demo (deterministic, no network).
// --endpoint  worker: the AX-12 contract (X-Catalogue-Version, tickets); openai: Ollama-style /v1/chat/completions
//          (then --model, and the system prompt + tools are sent by this CLI).
// --question "<text>" | --file questions.json (["q", ...] or [{question, page}]) | --page "<route>?k=v&k=v"
// Needs no extra dependency: it runs the TypeScript sources through Vite's SSR loader, as build-cards.mjs does.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const APP_DIR = resolve(HERE, '..')
const SRC = join(APP_DIR, 'src')

function parseArgs(argv) {
  const o = { calls: [], questions: [], protocol: 'worker' }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    const val = () => argv[++i]
    if (a === '--data') o.data = val()
    else if (a === '--cards') o.cards = val()
    else if (a === '--stub') o.stub = true
    else if (a === '--sample') o.sample = true
    else if (a === '--demo') o.demo = true
    else if (a === '--endpoint') o.endpoint = val()
    else if (a === '--protocol') o.protocol = val()
    else if (a === '--model') o.model = val()
    else if (a === '--catalogue-version') o.catalogueVersion = val()
    else if (a === '--turnstile-token') o.turnstile = val()
    else if (a === '--question') o.questions.push({ question: val() })
    else if (a === '--file') o.file = val()
    else if (a === '--page') o.page = val()
    else if (a === '--call') o.calls.push(val())
    else if (a === '--out') o.out = val()
    else if (a === '--text-out') o.textOut = val()
    else if (a === '-h' || a === '--help') o.help = true
    else throw new Error(`unknown argument ${a}`)
  }
  return o
}

function parsePage(s) {
  if (!s) return undefined
  const [route, qs] = s.split('?')
  const params = {}
  for (const [k, v] of new URLSearchParams(qs ?? '')) params[k] = /^\d+$/.test(v) ? Number(v) : v
  return { route, params }
}

const args = parseArgs(process.argv.slice(2))
if (args.help || (!args.calls.length && !args.sample && !args.demo && !args.questions.length && !args.file)) {
  console.log(readFileSync(fileURLToPath(import.meta.url), 'utf8').split('\n').slice(1, 22).map((l) => l.replace(/^\/\/ ?/, '')).join('\n'))
  process.exit(args.help ? 0 : 2)
}

const dataDir = resolve(args.data ?? process.env.AX06_DATA_DIR ?? join(APP_DIR, 'public/data'))
if (resolve(args.out ?? '/nonexistent').startsWith(join(APP_DIR, 'public/data'))) {
  console.error('refusing to write into app/public/data')
  process.exit(2)
}

const { createServer } = await import('vite')
const server = await createServer({
  configFile: false, root: APP_DIR, logLevel: 'warn', appType: 'custom',
  server: { middlewareMode: true, hmr: false, watch: null },
  optimizeDeps: { noDiscovery: true, include: [] },
  resolve: { alias: { '@': SRC } },
})
let rt
try {
  const load = (p) => server.ssrLoadModule(p)
  const [reg, nodeDeps, nodeTools, cli, samples, models] = await Promise.all([
    load('/src/assistant/cards/registry.ts'),
    load('/src/assistant/core/nodeDeps.ts'),
    load('/src/assistant/core/nodeTools.ts'),
    load('/src/assistant/core/cli.ts'),
    load('/src/assistant/core/sampleQuestions.ts'),
    load('/src/assistant/core/modelClient.ts'),
  ])
  const kinds = reg.registry.map((s) => ({ kind: s.kind, held_reason: reg.heldReasonFor(s) }))
  const gen = await nodeTools.generateTools({ catalogueJson: join(dataDir, 'assistant/catalogue.json'), kinds: kinds.map((k) => k.kind), appDir: APP_DIR })
  const cards = args.cards ? nodeDeps.loadCardsJson(resolve(args.cards)) : []
  if (!cards.length) console.error('warning: no --cards given; get_fact_cards will find nothing')
  rt = await nodeDeps.createNodeRuntime({ dataDir, cards, tools: gen.tools, system: gen.system, kinds, specs: reg.registry })

  if (args.calls.length) {
    const d = rt.newDispatcher()
    for (const c of args.calls) {
      const eq = c.indexOf('=')
      const name = c.slice(0, eq)
      const res = await cli.callTool(d, name, JSON.parse(c.slice(eq + 1)))
      console.log(`--- ${c}\n${JSON.stringify(res, null, 2)}`)
    }
  }

  let specs = []
  if (args.sample) specs = samples.SAMPLE_QUESTIONS
  else if (args.demo) specs = samples.DEMO_QUESTIONS
  else if (args.file) {
    const raw = JSON.parse(readFileSync(resolve(args.file), 'utf8'))
    specs = raw.map((x, i) => (typeof x === 'string' ? { id: `q${i + 1}`, kind: 'file', question: x } : { id: `q${i + 1}`, kind: 'file', ...x }))
  }
  for (const q of args.questions) specs.push({ id: `q${specs.length + 1}`, kind: 'cli', question: q.question, page: parsePage(args.page) })
  if (args.page && !args.questions.length && args.file) specs = specs.map((s) => ({ page: parsePage(args.page), ...s }))

  if (specs.length) {
    let modelFor
    if (args.stub) {
      modelFor = (spec) => {
        if (!spec.script) throw new Error(`--stub has no script for "${spec.question}" (use --sample, --demo, or a real --endpoint)`)
        return new models.ScriptedModel(spec.script)
      }
    } else if (args.endpoint) {
      const client =
        args.protocol === 'openai'
          ? models.createOpenAIClient({ endpoint: args.endpoint, model: args.model ?? 'gpt-oss:20b', system: gen.system, tools: gen.tools })
          : models.createWorkerClient({ endpoint: args.endpoint, catalogueVersion: args.catalogueVersion ?? gen.catalogue_version, turnstileToken: args.turnstile })
      modelFor = () => client
    } else {
      console.error('give --stub (scripted, no network) or --endpoint <url>')
      process.exit(2)
    }
    const text = []
    const records = await cli.runQuestions(specs, {
      modelFor,
      depsFor: (model) => rt.loopDeps(model),
      onRecord: (r) => {
        const t = cli.formatRecord(r)
        text.push(t)
        console.log(`${t}\n`)
      },
    })
    if (args.out) {
      mkdirSync(dirname(resolve(args.out)), { recursive: true })
      writeFileSync(resolve(args.out), JSON.stringify({ mode: args.stub ? 'stub' : `endpoint:${args.protocol}`, data_dir: dataDir, catalogue_version: gen.catalogue_version, tokens: gen.tokens, records }, null, 2))
      console.log(`wrote ${resolve(args.out)}`)
    }
    if (args.textOut) writeFileSync(resolve(args.textOut), text.join('\n\n') + '\n')
  }
} finally {
  rt?.close()
  await server.close()
}
