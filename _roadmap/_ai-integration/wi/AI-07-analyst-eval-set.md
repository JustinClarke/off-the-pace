# AI-07 — Analyst eval: questions, grader, pass bar, baseline

**Group:** 3 delivery and launch · **Depends on:** `AI-01`, `AI-02`, `AI-04` · **Blocker:** none.

**Sources:** `docs/app/race-lost.mdx`, `docs/app/pit-strategy.mdx`, `docs/app/tyre-cliff-survival.mdx`, `docs/app/families/`.

This is the measure of "feels like a trackside analyst" that can fail. It runs headless against AI-04, so it gives a baseline before the proxy or the UI exist. _Method corrected 2026-10-22 to the counts recorded under `AD2`; the launch run (production endpoint, not Ollama) is AI-12._

---

## What exists today

The family and feature pages show what the app can already answer: where a race was lost, whether a pit stop paid off, when a tyre falls away, how a driver compares with a teammate. There is no fixed list of fan questions and no way to score an answer.

## Method

1. Write questions in fan language, drawn from the pages above, covering all seven tools (`AD2`): every tool in 5 or more questions, 15 or more that need the query path, and 8 or more that must be refused or hedged (a 2026 race not in the data, an in-sample-only result, a driver-versus-car split the data cannot make, a thin sample). Each question runs 5 times, since the spikes were single runs.
2. For each question, store the card ids that should be used and the AI-02 rules that should fire. Expected values are read from the card table at grade time, so the set stays valid while CO items move the numbers.
3. Grader, per answer: every number matches a cited card; required wording is present; refusal questions are refused. Score plain language and tone by a human read of 10 answers (the term is defined or linked the first time it appears; the answer says what the number does not show when a wrong reading is likely).
4. Record the pass bar in the log before the first run: 100% of numbers grounded, 100% of refusal cases correct, the right tool used 95% of the time or more, no run over 18,000 tokens, and the human read passed. Log tokens per call and per budget slot.

## Acceptance

- The set covers at least 4 families and 3 seasons.
- The grader fails a deliberately wrong answer for every question type.

## Output

The baseline run: score per check and per family, a list of every failure with its cause, the share of questions no tool could answer, and mean tokens and cost per answer (this sizes the cap `AD4` sets).

## Definition of done

Set, grader and bar are recorded before the first run; one baseline run is saved as evidence. The launch run on settled numbers is AI-12.
