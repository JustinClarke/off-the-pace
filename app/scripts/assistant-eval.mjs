#!/usr/bin/env node
// AX-13 analyst eval. Runs app/src/assistant/eval/questions.json through the AX-10 loop and grades every run.
//
//   Record the bar (once, BEFORE the first run; refuses to overwrite):
//     node scripts/assistant-eval.mjs --record-bar --evidence <dir>
//   STUB baseline (deterministic scripted model, no network; measures the harness, not a model):
//     node scripts/assistant-eval.mjs --stub --data <dir> --cards <cards.json> --evidence <dir> [--repeats 5] [--out-name stub-baseline]
//   Real run against the Worker v2 contract (wrangler dev or the AX-12 preview Worker):
//     node scripts/assistant-eval.mjs --endpoint http://127.0.0.1:8787/v1/chat --protocol worker --origin http://localhost:5173 \
//          --data <dir> --cards <cards.json> --evidence <dir> [--repeats 5] [--ids a,b] [--resume] [--out-name baseline]
//   Real run against an OpenAI-compatible endpoint (local Ollama; the CLI sends system prompt + tools itself):
//     node scripts/assistant-eval.mjs --endpoint http://127.0.0.1:11434/v1/chat/completions --protocol openai --model gpt-oss:20b ...
//   Human read sheet (10 answers marked human_read, first repeat) from a finished run:
//     node scripts/assistant-eval.mjs --human-read --evidence <dir> [--out-name baseline]
//
// --evidence  folder for bar.json, <out-name>.json (every run), <out-name>.runs.jsonl (incremental, for --resume),
//             <out-name>-summary.md. A run refuses to start unless bar.json exists and its questions_hash matches the
//             question file (no run counts before the bar is recorded).
// --data      a folder laid out like app/public/data (default $AX06_DATA_DIR). --cards a build-cards cards.json (default $AX10_CARDS).
// --catalogue-version (worker) defaults to the catalogue in --data; --turnstile-token for a Worker with Turnstile on.
import { readFileSync, writeFileSync, mkdirSync, existsSync, appendFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const APP_DIR = resolve(HERE, '..')
const SRC = join(APP_DIR, 'src')

function parseArgs(argv) {
  const o = { repeats: 5, protocol: 'worker', outName: null }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    const val = () => argv[++i]
    if (a === '--record-bar') o.recordBar = true
    else if (a === '--amend') o.amend = val()
    else if (a === '--evidence') o.evidence = val()
    else if (a === '--stub') o.stub = true
    else if (a === '--endpoint') o.endpoint = val()
    else if (a === '--protocol') o.protocol = val()
    else if (a === '--origin') o.origin = val()
    else if (a === '--model') o.model = val()
    else if (a === '--catalogue-version') o.catalogueVersion = val()
    else if (a === '--turnstile-token') o.turnstile = val()
    else if (a === '--data') o.data = val()
    else if (a === '--cards') o.cards = val()
    else if (a === '--repeats') o.repeats = Number(val())
    else if (a === '--ids') o.ids = val().split(',').map((s) => s.trim()).filter(Boolean)
    else if (a === '--resume') o.resume = true
    else if (a === '--out-name') o.outName = val()
    else if (a === '--human-read') o.humanRead = true
    else if (a === '-h' || a === '--help') o.help = true
    else throw new Error(`unknown argument ${a}`)
  }
  return o
}

const args = parseArgs(process.argv.slice(2))
if (args.help || !args.evidence) {
  console.log(readFileSync(fileURLToPath(import.meta.url), 'utf8').split('\n').slice(1, 23).map((l) => l.replace(/^\/\/ ?/, '')).join('\n'))
  process.exit(args.help ? 0 : 2)
}
const evidence = resolve(args.evidence)
if (evidence.startsWith(join(APP_DIR, 'public/data'))) {
  console.error('refusing to write into app/public/data')
  process.exit(2)
}
mkdirSync(evidence, { recursive: true })
const barPath = join(evidence, 'bar.json')
const sha = (p) => createHash('sha256').update(readFileSync(p)).digest('hex')

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
  const [Q, report] = await Promise.all([load('/src/assistant/eval/questions.ts'), load('/src/assistant/eval/report.ts')])
  const questionsHash = Q.questionsHash()

  if (args.recordBar) {
    const prior = existsSync(barPath) ? JSON.parse(readFileSync(barPath, 'utf8')) : null
    if (prior && !args.amend) {
      console.error(`${barPath} exists (recorded ${prior.recorded_at}); the bar is fixed. Use --amend "<reason>" only to re-record the question hash after a question-file fix; the thresholds never change.`)
      process.exit(2)
    }
    const rec = {
      recorded_at: new Date().toISOString(),
      note: 'Recorded BEFORE any eval run (stub or real). The thresholds are wi/AX-13.md Decided verbatim and are not tuned to any result. The orchestrator appends this to status/build-log.json history; this script never edits the log.',
      bar: report.BAR,
      questions_file: 'app/src/assistant/eval/questions.json',
      questions_hash: questionsHash,
      questions_file_sha256: sha(join(SRC, 'assistant/eval/questions.json')),
      grader_sha256: { 'eval/grade.ts': sha(join(SRC, 'assistant/eval/grade.ts')), 'eval/report.ts': sha(join(SRC, 'assistant/eval/report.ts')) },
      counts: Q.countQuestions(),
      ...(prior ? { amended_from: { recorded_at: prior.recorded_at, questions_hash: prior.questions_hash, reason: args.amend }, history: [...(prior.history ?? []), { recorded_at: prior.recorded_at, questions_hash: prior.questions_hash }] } : {}),
    }
    writeFileSync(barPath, JSON.stringify(rec, null, 2) + '\n')
    console.log(`wrote ${barPath}\nquestions_hash ${questionsHash}`)
    process.exit(0)
  }

  const outName = args.outName ?? (args.stub ? 'stub-baseline' : 'baseline')
  const jsonl = join(evidence, `${outName}.runs.jsonl`)

  if (args.humanRead) {
    const recs = readFileSync(jsonl, 'utf8').trim().split('\n').map((l) => JSON.parse(l))
    const picks = Q.QUESTIONS.filter((q) => q.human_read).map((q) => ({ q, r: recs.find((x) => x.obs.question_id === q.id && x.obs.repeat === 1) })).filter((x) => x.r)
    const sheet = picks.map(({ q, r }) => ({ question_id: q.id, question: q.text, answer: r.obs.answer, pass: null, note: '' }))
    for (const s of sheet) console.log(`--- ${s.question_id}\nQ: ${s.question}\nA: ${s.answer}\n`)
    const out = join(evidence, `${outName}.human-read.json`)
    if (!existsSync(out)) writeFileSync(out, JSON.stringify({ status: 'pending', checklist: report.BAR.human_read, answers: sheet }, null, 2) + '\n')
    console.log(`human-read sheet: ${out} (fill pass true/false and a note per answer, then status pass|fail; re-run the eval with --resume to refresh the summary)`)
    process.exit(0)
  }

  // No run counts before the bar is recorded, and the bar must be for this question file.
  if (!existsSync(barPath)) {
    console.error(`no ${barPath}: record the bar first (--record-bar). No run counts before it.`)
    process.exit(2)
  }
  const bar = JSON.parse(readFileSync(barPath, 'utf8'))
  if (bar.questions_hash !== questionsHash) {
    console.error(`bar.json questions_hash ${bar.questions_hash} != current question file ${questionsHash}: re-record with --amend after a question fix (thresholds unchanged).`)
    process.exit(2)
  }
  if (!args.stub && !args.endpoint) {
    console.error('give --stub (scripted, no network) or --endpoint <url>')
    process.exit(2)
  }

  const dataDir = resolve(args.data ?? process.env.AX06_DATA_DIR ?? join(APP_DIR, 'public/data'))
  const cardsPath = args.cards ?? process.env.AX10_CARDS
  if (!cardsPath) {
    console.error('give --cards <cards.json> (or AX10_CARDS)')
    process.exit(2)
  }
  const [reg, nodeDeps, nodeTools, models, runMod, gradeMod, stub] = await Promise.all([
    load('/src/assistant/cards/registry.ts'),
    load('/src/assistant/core/nodeDeps.ts'),
    load('/src/assistant/core/nodeTools.ts'),
    load('/src/assistant/core/modelClient.ts'),
    load('/src/assistant/eval/run.ts'),
    load('/src/assistant/eval/grade.ts'),
    load('/src/assistant/eval/stubModel.ts'),
  ])
  const kinds = reg.registry.map((s) => ({ kind: s.kind, held_reason: reg.heldReasonFor(s) }))
  const gen = await nodeTools.generateTools({ catalogueJson: join(dataDir, 'assistant/catalogue.json'), kinds: kinds.map((k) => k.kind), appDir: APP_DIR })
  const cards = nodeDeps.loadCardsJson(resolve(cardsPath))
  rt = await nodeDeps.createNodeRuntime({ dataDir, cards, tools: gen.tools, system: gen.system, kinds, specs: reg.registry })
  const table = gradeMod.createCardTable(cards)

  const mode = args.stub ? 'STUB' : `endpoint:${args.protocol}`
  let modelFor
  if (args.stub) modelFor = (q) => new models.ScriptedModel(stub.stubScript(q))
  else {
    const client =
      args.protocol === 'openai'
        ? models.createOpenAIClient({ endpoint: args.endpoint, model: args.model ?? 'gpt-oss:20b', system: gen.system, tools: gen.tools })
        : models.createWorkerClient({ endpoint: args.endpoint, catalogueVersion: args.catalogueVersion ?? gen.catalogue_version, turnstileToken: args.turnstile, origin: args.origin })
    modelFor = () => client
  }

  const questions = args.ids ? Q.QUESTIONS.filter((q) => args.ids.includes(q.id)) : Q.QUESTIONS
  const prior = args.resume && existsSync(jsonl) ? readFileSync(jsonl, 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l)) : []
  // Resume keeps good runs only; errored runs are re-run.
  const kept = prior.filter((r) => r.obs.status !== 'error' && r.questions_hash === questionsHash)
  if (!args.resume) writeFileSync(jsonl, '')
  else writeFileSync(jsonl, kept.map((r) => JSON.stringify(r)).join('\n') + (kept.length ? '\n' : ''))
  const done = new Set(kept.map((r) => runMod.runKey(r.obs.question_id, r.obs.repeat)))

  const started = new Date().toISOString()
  let n = 0
  const { observations, grades } = await runMod.runEval(questions, {
    repeats: args.repeats,
    mode,
    modelFor,
    deps: { loopDeps: (m) => rt.loopDeps(m), store: rt.store },
    table,
    done,
    onRun: (obs, g) => {
      appendFileSync(jsonl, JSON.stringify({ questions_hash: questionsHash, obs, grade: g }) + '\n')
      n++
      console.log(`${String(n).padStart(4)} ${obs.question_id} #${obs.repeat} ${obs.status} tokens=${obs.budget.total} rounds=${obs.rounds}${obs.repaired ? ' REPAIRED' : ''} ${g.all_pass ? 'pass' : `FAIL ${g.failures.join(' / ')}`}`)
    },
  })
  const allObs = [...kept.map((r) => r.obs), ...observations]
  const allGrades = [...kept.map((r) => r.grade), ...grades]
  const hrPath = join(evidence, `${outName}.human-read.json`)
  const humanRead = args.stub
    ? { status: 'not_applicable', note: 'STUB answers are templates composed by eval/stubModel.ts; the human read applies to a real model run.' }
    : existsSync(hrPath)
      ? JSON.parse(readFileSync(hrPath, 'utf8'))
      : { status: 'pending' }
  const summary = report.summarize(questions, allObs, allGrades, humanRead, mode)
  const meta = {
    mode,
    label: args.stub ? 'STUB: deterministic scripted model. Measures the harness (dispatcher, loop, budget meter, checker, grounding, grader), NOT a model.' : `REAL: ${args.endpoint}`,
    started,
    finished: new Date().toISOString(),
    questions_hash: questionsHash,
    bar_recorded_at: bar.recorded_at,
    data_dir: dataDir,
    cards: resolve(cardsPath),
    cards_count: cards.length,
    catalogue_version: gen.catalogue_version,
    static_tokens: gen.tokens,
    repeats: args.repeats,
  }
  writeFileSync(join(evidence, `${outName}.json`), JSON.stringify({ ...meta, summary, runs: allObs.map((o, i) => ({ ...o, grade: allGrades[i] })) }, null, 2) + '\n')
  const perQuestion = allObs.map((o, i) => ({ id: o.question_id, tokens: o.budget.total, rounds: o.rounds, repaired: o.repaired, neurons: o.budget.neurons, tools: o.tools.length, all_pass: allGrades[i].all_pass }))
  const header = [
    `# AX-13 ${args.stub ? 'STUB baseline (harness measurement, not a model)' : 'baseline'} - ${meta.finished.slice(0, 10)}`,
    '',
    `${meta.label}`,
    '',
    `Question file hash ${questionsHash} (bar recorded ${bar.recorded_at}). Cards: ${meta.cards} (${cards.length}). Data: ${dataDir}. Repeats: ${args.repeats}.`,
  ].join('\n')
  writeFileSync(join(evidence, `${outName}-summary.md`), report.renderSummary(summary, header, perQuestion))
  console.log(`\nverdict ${summary.verdict}  grounded ${summary.checks.grounded.rate}  refusal ${summary.checks.refusal.rate}  right_tool ${summary.checks.right_tool.rate}  max tokens ${summary.tokens.max_total}`)
  console.log(`wrote ${join(evidence, `${outName}.json`)}, ${outName}-summary.md, ${outName}.runs.jsonl`)
} finally {
  rt?.close()
  await server.close()
}
