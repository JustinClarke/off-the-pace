// AX-13 pass bar (fixed before the first run) and the run summary: score per check, family, class,
// type and group; every failure with its cause; tokens, rounds, repair turns, neurons per answer and
// answers per day at the daily neuron cap; reasoning-token and output-cap evidence when the endpoint reports it.
import { CHECK_NAMES, RUN_TOKEN_LIMIT, type CheckName, type GradeResult, type RunObservation } from './grade'
import type { Question } from './questions'

/** Workers AI free allowance and the Worker's cap (worker/src/config.ts DEFAULT_DAILY_NEURON_CAP). */
export const DAILY_NEURON_CAP = 10000
/** worker/src/config.ts MAX_OUTPUT_TOKENS (a node test keeps these in step). */
export const WORKER_MAX_OUTPUT_TOKENS = 2500

/** The bar, verbatim from wi/AX-13.md "Decided" (carried from AI-07; do not change). */
export const BAR = {
  item: 'AX-13',
  source: '_roadmap/_ai-integration/wi/AX-13.md, Decided: "Pass bar (from AI-07, do not change)"',
  grounded_rate: 1.0,
  refusal_rate: 1.0,
  right_tool_rate_min: 0.95,
  max_run_tokens: RUN_TOKEN_LIMIT,
  human_read: 'pass on 10 answers (term defined or linked at first use; says what the number does not show when a wrong reading is likely; plain tone)',
  repeats: 5,
  definitions: {
    grounded_rate: 'share of runs (answered or not, endpoint errors excluded) whose every answer number matches a card the model received this question, a query_data / compare_lap_times / make_chart result, or a number in the question (findUngroundedNumbers, assistant/grounding.ts)',
    refusal_rate: 'share of runs of expect=refuse|hedge questions where the answer gives every held_reason key of the question (eval/grade.ts HELD_REASON_PATTERNS), carries no must_not claim, and, for refuse, has refusal wording and states no number other than those the user typed',
    right_tool_rate: 'share of runs where the first expected tool was called (and the expected bundle, when the question names one); a question with no expected tool passes only with zero tool calls',
    max_run_tokens: 'no run over 18,000 tokens of PEAK CONTEXT (budget.peak_context: the largest single-round context). AX-13 ruling 1 (2026-11-08): the bar was meant as a window-safety bar against the 20,480-token window (design-ai-access.md:269), not a sum over rounds. budget.total (prompt + completion summed over the rounds, what neurons are billed on) is reported and does not gate',
    human_read: 'owner (or a delegate) reads the 10 answers printed by --human-read and records pass/fail with a note per answer in human-read.json',
    repeats: 'each question is run 5 times; a run with an endpoint error is listed and re-run, not counted',
  },
  reported_not_gating: ['budget.total (tokens summed over rounds)', 'expected_value', 'honesty', 'rules_fired', 'must_not (part of refusal for refuse/hedge questions)', 'all_tools', 'limits', 'answered', 'repair-turn rate', 'neurons per answer', 'answers per day'],
} as const

export interface RateRow {
  pass: number
  fail: number
  na: number
  rate: number | null
}

export interface GroupRow {
  runs: number
  all_pass: number
  rate: number
  failed_checks: Partial<Record<CheckName, number>>
}

export interface HumanRead {
  status: 'pending' | 'pass' | 'fail' | 'not_applicable'
  answers?: { question_id: string; pass: boolean; note: string }[]
  note?: string
}

export interface Summary {
  mode: string
  questions: number
  runs: number
  errored_runs: number
  repeats_min: number
  checks: Record<CheckName, RateRow>
  by_family: Record<string, GroupRow>
  by_class: Record<string, GroupRow>
  by_type: Record<string, GroupRow>
  by_group: Record<string, GroupRow>
  bar: {
    grounded: { value: number | null; threshold: number; pass: boolean }
    refusal: { value: number | null; threshold: number; pass: boolean }
    right_tool: { value: number | null; threshold: number; pass: boolean }
    tokens: { max: number; total_max: number; threshold: number; over: number; pass: boolean }
    human_read: HumanRead
    repeats: { min: number; required: number; pass: boolean }
  }
  verdict: 'PASS' | 'FAIL' | 'INCOMPLETE'
  tokens: { mean_total: number; p50_total: number; p90_total: number; max_total: number; mean_peak_context: number; estimated_runs: number }
  neurons: { mean: number; p90: number; max: number; answers_per_day_at_cap: number | null; from_usage: boolean }
  rounds: { mean: number; max: number; multi_round_runs: number; multi_round_ok: number }
  tool_calls: { mean: number; max: number }
  repair: { runs_repaired: number; rate: number; skipped: number; first_draft_codes: Record<string, number> }
  no_tool_could_answer: { questions: string[]; share: number }
  reasoning: {
    rounds_reporting_reasoning: number
    reasoning_tokens_total: number
    rounds_at_output_cap: number
    /** AX-12 ruling 1: rounds the endpoint reports finish_reason "length" for, of those that report one. */
    rounds_finish_length: number
    rounds_reporting_finish_reason: number
    usage_rounds: number
    /** Rounds with endpoint completion_tokens: their sum, and the chars/4 estimate of the visible reply in the same rounds. */
    completion_tokens_reported: number
    visible_tokens_estimated: number
    /** Rounds whose completion_tokens exceed 2 x the visible estimate + 20 (hidden tokens billed as output). */
    rounds_hidden_output: number
  }
  errors: { question_id: string; repeat: number; error: string }[]
  failures: { question_id: string; repeat: number; failures: string[] }[]
}

const rate = (p: number, f: number) => (p + f === 0 ? null : p / (p + f))
const quantile = (xs: number[], q: number) => {
  if (!xs.length) return 0
  const s = [...xs].sort((a, b) => a - b)
  return s[Math.min(s.length - 1, Math.floor(q * s.length))]
}
const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0)

function groupRows(questions: readonly Question[], grades: GradeResult[], key: (q: Question) => string): Record<string, GroupRow> {
  const byId = new Map(questions.map((q) => [q.id, q]))
  const out: Record<string, GroupRow> = {}
  for (const g of grades) {
    const q = byId.get(g.question_id)
    if (!q) continue
    const k = key(q)
    const row = (out[k] ??= { runs: 0, all_pass: 0, rate: 0, failed_checks: {} })
    row.runs++
    if (g.all_pass) row.all_pass++
    for (const c of CHECK_NAMES) if (g.checks[c].pass === false && c !== 'all_tools') row.failed_checks[c] = (row.failed_checks[c] ?? 0) + 1
  }
  for (const r of Object.values(out)) r.rate = r.runs ? r.all_pass / r.runs : 0
  return Object.fromEntries(Object.entries(out).sort(([a], [b]) => (a < b ? -1 : 1)))
}

export function summarize(questions: readonly Question[], observations: RunObservation[], grades: GradeResult[], humanRead: HumanRead, mode: string): Summary {
  const okRuns = grades.filter((_, i) => observations[i].status !== 'error')
  const okObs = observations.filter((o) => o.status !== 'error')
  const checks = {} as Record<CheckName, RateRow>
  for (const c of CHECK_NAMES) {
    let pass = 0
    let fail = 0
    let na = 0
    for (const g of okRuns) {
      const v = g.checks[c].pass
      if (v === true) pass++
      else if (v === false) fail++
      else na++
    }
    checks[c] = { pass, fail, na, rate: rate(pass, fail) }
  }
  const perQ = new Map<string, number>()
  for (const o of okObs) perQ.set(o.question_id, (perQ.get(o.question_id) ?? 0) + 1)
  const repeatsMin = questions.length ? Math.min(...questions.map((q) => perQ.get(q.id) ?? 0)) : 0

  const totals = okObs.map((o) => o.budget.total)
  const neurons = okObs.map((o) => o.budget.neurons)
  const meanNeurons = mean(neurons)
  const peaks = okObs.map((o) => o.budget.peak_context)
  const maxTokens = totals.length ? Math.max(...totals) : 0
  const maxPeak = peaks.length ? Math.max(...peaks) : 0
  const usageRounds = observations.flatMap((o) => o.usage_rounds)
  const reported = usageRounds.filter((u) => typeof u.completion_tokens === 'number')

  const anyOk = new Map<string, boolean>()
  for (const o of okObs) anyOk.set(o.question_id, (anyOk.get(o.question_id) ?? false) || o.tools.some((t) => t.status === 'ok'))
  const toolQs = questions.filter((q) => q.expected_tools.length > 0 && anyOk.has(q.id))
  const noTool = toolQs.filter((q) => anyOk.get(q.id) === false).map((q) => q.id)

  const firstDraft: Record<string, number> = {}
  for (const o of okObs) for (const c of o.first_draft_failed) firstDraft[c.replace(/^number .*/, 'UNGROUNDED_NUMBER')] = (firstDraft[c.replace(/^number .*/, 'UNGROUNDED_NUMBER')] ?? 0) + 1

  const bar = {
    grounded: { value: checks.grounded.rate, threshold: BAR.grounded_rate, pass: checks.grounded.fail === 0 },
    refusal: { value: checks.refusal.rate, threshold: BAR.refusal_rate, pass: checks.refusal.fail === 0 },
    right_tool: { value: checks.right_tool.rate, threshold: BAR.right_tool_rate_min, pass: (checks.right_tool.rate ?? 0) >= BAR.right_tool_rate_min },
    // AX-13 ruling 1: gates on the peak context; max is the largest peak, total_max (the sum over rounds) is reported only.
    tokens: { max: maxPeak, total_max: maxTokens, threshold: BAR.max_run_tokens, over: peaks.filter((t) => t > BAR.max_run_tokens).length, pass: peaks.length > 0 && maxPeak <= BAR.max_run_tokens },
    human_read: humanRead,
    repeats: { min: repeatsMin, required: BAR.repeats, pass: repeatsMin >= BAR.repeats },
  }
  const numeric = [bar.grounded.pass, bar.refusal.pass, bar.right_tool.pass, bar.tokens.pass]
  const errored = observations.length - okObs.length
  const verdict: Summary['verdict'] = numeric.includes(false)
    ? 'FAIL'
    : humanRead.status === 'fail'
      ? 'FAIL'
      : humanRead.status === 'pass' && bar.repeats.pass && errored === 0
        ? 'PASS'
        : 'INCOMPLETE'

  return {
    mode,
    questions: questions.length,
    runs: observations.length,
    errored_runs: errored,
    repeats_min: repeatsMin,
    checks,
    by_family: groupRows(questions, okRuns, (q) => q.family),
    by_class: groupRows(questions, okRuns, (q) => q.class),
    by_type: groupRows(questions, okRuns, (q) => q.type),
    by_group: groupRows(questions, okRuns, (q) => q.group),
    bar,
    verdict,
    tokens: {
      mean_total: Math.round(mean(totals)),
      p50_total: quantile(totals, 0.5),
      p90_total: quantile(totals, 0.9),
      max_total: maxTokens,
      mean_peak_context: Math.round(mean(okObs.map((o) => o.budget.peak_context))),
      estimated_runs: okObs.filter((o) => o.budget.estimated).length,
    },
    neurons: {
      mean: Math.round(meanNeurons * 10) / 10,
      p90: quantile(neurons, 0.9),
      max: neurons.length ? Math.max(...neurons) : 0,
      answers_per_day_at_cap: meanNeurons > 0 ? Math.floor(DAILY_NEURON_CAP / meanNeurons) : null,
      from_usage: okObs.length > 0 && okObs.every((o) => !o.budget.estimated),
    },
    rounds: {
      mean: Math.round(mean(okObs.map((o) => o.rounds)) * 100) / 100,
      max: okObs.length ? Math.max(...okObs.map((o) => o.rounds)) : 0,
      multi_round_runs: observations.filter((o) => o.usage_rounds.length >= 2).length,
      multi_round_ok: okObs.filter((o) => o.rounds >= 2 && o.tools.some((t) => t.status === 'ok') && o.status === 'answered').length,
    },
    tool_calls: { mean: Math.round(mean(okObs.map((o) => o.tools.length)) * 100) / 100, max: okObs.length ? Math.max(...okObs.map((o) => o.tools.length)) : 0 },
    repair: {
      runs_repaired: okObs.filter((o) => o.repaired).length,
      rate: okObs.length ? okObs.filter((o) => o.repaired).length / okObs.length : 0,
      skipped: okObs.filter((o) => o.repair_skipped).length,
      first_draft_codes: firstDraft,
    },
    no_tool_could_answer: { questions: noTool, share: toolQs.length ? noTool.length / toolQs.length : 0 },
    reasoning: {
      rounds_reporting_reasoning: usageRounds.filter((u) => typeof u.reasoning_tokens === 'number').length,
      reasoning_tokens_total: usageRounds.reduce((a, u) => a + (u.reasoning_tokens ?? 0), 0),
      rounds_at_output_cap: usageRounds.filter((u) => (u.completion_tokens ?? 0) >= WORKER_MAX_OUTPUT_TOKENS).length,
      rounds_finish_length: usageRounds.filter((u) => u.finish_reason === 'length').length,
      rounds_reporting_finish_reason: usageRounds.filter((u) => typeof u.finish_reason === 'string').length,
      usage_rounds: usageRounds.length,
      completion_tokens_reported: reported.reduce((a, u) => a + (u.completion_tokens ?? 0), 0),
      visible_tokens_estimated: reported.reduce((a, u) => a + Math.ceil((u.visible_chars ?? 0) / 4), 0),
      rounds_hidden_output: reported.filter((u) => (u.completion_tokens ?? 0) > 2 * Math.ceil((u.visible_chars ?? 0) / 4) + 20).length,
    },
    errors: observations.filter((o) => o.status === 'error').map((o) => ({ question_id: o.question_id, repeat: o.repeat, error: o.error ?? '' })),
    failures: grades.filter((g) => !g.all_pass).map((g) => ({ question_id: g.question_id, repeat: g.repeat, failures: g.failures })),
  }
}

const p = (x: number | null) => (x === null ? 'n/a' : `${(x * 100).toFixed(1)}%`)

function groupTable(title: string, rows: Record<string, GroupRow>): string {
  const lines = [`### ${title}`, '', '| group | runs | all checks pass | rate | failed checks |', '| :--- | ---: | ---: | ---: | :--- |']
  for (const [k, r] of Object.entries(rows))
    lines.push(`| ${k} | ${r.runs} | ${r.all_pass} | ${p(r.rate)} | ${Object.entries(r.failed_checks).map(([c, n]) => `${c} ${n}`).join(', ') || '-'} |`)
  return lines.join('\n')
}

/** baseline-summary.md body. */
export function renderSummary(s: Summary, header: string, perQuestion: { id: string; tokens: number; rounds: number; repaired: boolean; neurons: number; tools: number; all_pass: boolean }[]): string {
  const b = s.bar
  const out: string[] = [
    header,
    '',
    `## Verdict: ${s.verdict}`,
    '',
    '| bar item (fixed before the first run) | measured | threshold | pass |',
    '| :--- | ---: | ---: | :--- |',
    `| numbers grounded | ${p(b.grounded.value)} | 100% | ${b.grounded.pass ? 'yes' : 'NO'} |`,
    `| refusal / hedge cases correct | ${p(b.refusal.value)} | 100% | ${b.refusal.pass ? 'yes' : 'NO'} |`,
    `| right tool | ${p(b.right_tool.value)} | >= 95% | ${b.right_tool.pass ? 'yes' : 'NO'} |`,
    `| max peak context in one run | ${b.tokens.max} (${b.tokens.over} over) | <= ${b.tokens.threshold} | ${b.tokens.pass ? 'yes' : 'NO'} |`,
    `| human read (10 answers) | ${b.human_read.status} | pass | ${b.human_read.status === 'pass' ? 'yes' : b.human_read.status === 'fail' ? 'NO' : '-'} |`,
    `| repeats per question | ${b.repeats.min} | 5 | ${b.repeats.pass ? 'yes' : 'NO'} |`,
    '',
    `Runs ${s.runs} over ${s.questions} questions; endpoint errors ${s.errored_runs}.`,
    '',
    '## Checks',
    '',
    '| check | pass | fail | n/a | rate |',
    '| :--- | ---: | ---: | ---: | ---: |',
    ...CHECK_NAMES.map((c) => `| ${c} | ${s.checks[c].pass} | ${s.checks[c].fail} | ${s.checks[c].na} | ${p(s.checks[c].rate)} |`),
    '',
    groupTable('By class', s.by_class),
    '',
    groupTable('By family', s.by_family),
    '',
    groupTable('By playbook type', s.by_type),
    '',
    groupTable('By group (AX-13 method step 2)', s.by_group),
    '',
    '## Cost and capacity',
    '',
    `- Peak context per run (the bar, max ${s.bar.tokens.max} against ${BAR.max_run_tokens}); tokens per run summed over all rounds (reported, not gating): mean ${s.tokens.mean_total}, p50 ${s.tokens.p50_total}, p90 ${s.tokens.p90_total}, max ${s.tokens.max_total}; mean peak context ${s.tokens.mean_peak_context}; runs on the chars/4 estimate: ${s.tokens.estimated_runs}.`,
    `- Neurons per answer: mean ${s.neurons.mean}, p90 ${s.neurons.p90}, max ${s.neurons.max} (${s.neurons.from_usage ? 'from endpoint usage' : 'ESTIMATED from chars/4, not a measurement'}).`,
    `- Answers per day at the ${DAILY_NEURON_CAP}-neuron cap: ${s.neurons.answers_per_day_at_cap ?? 'n/a'} (${s.neurons.from_usage ? 'measured usage' : 'estimate only'}).`,
    `- Rounds per run: mean ${s.rounds.mean}, max ${s.rounds.max}; runs with 2+ model rounds: ${s.rounds.multi_round_runs}, of which answered after a tool result: ${s.rounds.multi_round_ok}.`,
    `- Tool calls per run: mean ${s.tool_calls.mean}, max ${s.tool_calls.max}.`,
    `- Repair turns: ${s.repair.runs_repaired} runs (${p(s.repair.rate)}); repair skipped (no round left): ${s.repair.skipped}; first-draft failures: ${Object.entries(s.repair.first_draft_codes).map(([k, v]) => `${k} ${v}`).join(', ') || 'none'}.`,
    `- Questions no tool could answer (no ok tool result in any run): ${s.no_tool_could_answer.questions.join(', ') || 'none'} (${p(s.no_tool_could_answer.share)}).`,
    `- Reasoning tokens: ${s.reasoning.rounds_reporting_reasoning} of ${s.reasoning.usage_rounds} usage rounds report a reasoning-token field (total ${s.reasoning.reasoning_tokens_total}); rounds whose completion reached MAX_OUTPUT_TOKENS (${WORKER_MAX_OUTPUT_TOKENS}): ${s.reasoning.rounds_at_output_cap}; finish_reason "length" (truncated): ${s.reasoning.rounds_finish_length} of ${s.reasoning.rounds_reporting_finish_reason} rounds that report one (AX-12 ruling 4 rule: raise the cap only above 1%).`,
    `- Hidden output: in rounds with endpoint usage, completion_tokens total ${s.reasoning.completion_tokens_reported} against ${s.reasoning.visible_tokens_estimated} estimated (chars/4) for the visible reply; ${s.reasoning.rounds_hidden_output} rounds bill more than twice their visible text (reasoning tokens counted as output, so against MAX_OUTPUT_TOKENS). No endpoint usage = not measured.`,
    '',
    '## Per question',
    '',
    '| question | runs | all pass | tokens (mean) | rounds (mean) | repair runs | tool calls (mean) | neurons (mean) |',
    '| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |',
  ]
  const byQ = new Map<string, typeof perQuestion>()
  for (const r of perQuestion) byQ.set(r.id, [...(byQ.get(r.id) ?? []), r])
  for (const [id, rs] of byQ)
    out.push(
      `| ${id} | ${rs.length} | ${rs.filter((r) => r.all_pass).length} | ${Math.round(mean(rs.map((r) => r.tokens)))} | ${mean(rs.map((r) => r.rounds)).toFixed(1)} | ${rs.filter((r) => r.repaired).length} | ${mean(rs.map((r) => r.tools)).toFixed(1)} | ${Math.round(mean(rs.map((r) => r.neurons)))} |`,
    )
  out.push('', '## Every failure, with its cause', '')
  if (!s.failures.length) out.push('None.')
  for (const f of s.failures) out.push(`- ${f.question_id} #${f.repeat}: ${f.failures.join(' / ')}`)
  if (s.errors.length) {
    out.push('', '## Endpoint errors (not counted; re-run)', '')
    for (const e of s.errors) out.push(`- ${e.question_id} #${e.repeat}: ${e.error}`)
  }
  return out.join('\n') + '\n'
}
