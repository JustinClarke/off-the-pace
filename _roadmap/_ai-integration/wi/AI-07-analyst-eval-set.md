# AI-07 — Analyst eval: questions, grader, pass bar, baseline

**Group:** C delivery · **Depends on:** `AI-01`, `AI-02`, `AI-04` · **Blocker:** none.

**Sources:** `docs/app/race-lost.mdx`, `docs/app/pit-strategy.mdx`, `docs/app/tyre-cliff-survival.mdx`, `docs/app/families/`.

This is the measure of "feels like a trackside analyst" that can fail. It runs headless against AI-04, so it gives a baseline before the proxy or the UI exist.

---

## What exists today

The family and feature pages show what the app can already answer: where a race was lost, whether a pit stop paid off, when a tyre falls away, how a driver compares with a teammate. There is no fixed list of fan questions and no way to score an answer.

## Method

1. Write about 40 questions in fan language, drawn from the pages above. At least 8 must be refused or hedged: a 2026 race not in the data, an in-sample-only result, a driver-versus-car split the data cannot make, a thin sample.
2. For each question, store the card ids that should be used and the AI-02 rules that should fire. Expected values are read from the card table at grade time, so the set stays valid while CO items move the numbers.
3. Grader, per answer: every number matches a cited card; required wording is present; refusal questions are refused. Score plain language and tone by a human read of 10 answers (the term is defined or linked the first time it appears; the answer says what the number does not show when a wrong reading is likely).
4. Record the pass bar in the log before the first run: 100% of numbers grounded, 100% of refusal cases correct, and the human read passed.

## Acceptance

- The set covers at least 4 families and 3 seasons.
- The grader fails a deliberately wrong answer for every question type.

## Output

The baseline run: score per check and per family, a list of every failure with its cause, the share of questions cards could not answer (this decides whether a SQL tool is worth adding), and mean tokens and cost per answer (this sizes AD1's cap).

## Definition of done

Set, grader and bar are recorded before the first run; one baseline run is saved as evidence. The launch run on settled numbers is part of AI-08.
