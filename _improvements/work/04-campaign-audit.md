# 04 — Campaign audit

**Group:** 04 · **Depends on:** nothing · **Cost:** ~2d total, no refits

`reference/ml_execution_plan.md` carries CLEARS verdicts across 22 checkpoints, each tested
against its own ~2σ reseed floor. **None was corrected for the number of tests run across the
campaign.** With enough tests at a fixed per-test threshold, some proportion of CLEARS is
expected from chance alone, and several past ship decisions rest on a single 1.2×–1.5× floor
crossing.

**Runs before `01` and `02`, not after.** It is pre-registration for every test those items
add, and the problem only grows while it waits.

> **RESCOPED 2026-09-07 (research round R1).** `04a` and `04c` still run, but their output is a
> **descriptive audit** — how many CLEARS would survive a correction — and **not an
> FDR-controlled statement**. BH assumes a family fixed in advance; this campaign's family was
> chosen adaptively, each checkpoint's arms picked knowing the last one's results, stopping when
> it stopped for reasons related to what it found. Pre-registration cannot be applied backwards.
> Say so in the deliverable rather than letting the number read as more than it is.
> `04b` is **CLOSED** on the same finding. Forward-looking validity is `09b`'s job.

**The mitigating factor that makes it possible at all:** this project records its negatives.
Most campaigns cannot be corrected retrospectively because the failures were never written
down.

---

## 04a — Enumerate the real test family

**Objective.** Establish the numerator and denominator. `reference/ml_research_program.md` §5
instructs a session to re-count with `grep -c "^## Checkpoint"` and `grep -c CLEARS`. **That
instruction produces a wrong answer in both directions.**

**Verified 2026-09-07.**

- **The numerator is over-counted.** `grep -c CLEARS` returns 8, but it counts *lines*, and
  the lines double-report: 4348 / 4363, 4783 / 4794 and 4920 / 4929 are each one experiment
  reported twice — the add-ablation total, then its permutation-null decomposition. Distinct
  claims are nearer 5.
- **The denominator is under-counted.** The same checkpoint selects the 9-column proximity
  group as best-of-three subsets (0.40× → 0.91× → 1.54×), and the campaign ran Optuna
  searches. Those are implicit comparisons that never earned a CLEARS line.

So §5's load-bearing sentence — *"the denominator is on the page"* — is false as stated.

**Method.** Define the family as **one entry per decision**, not per line. Enumerate every
floor comparison and every selection-among-arms across all 22 checkpoints. State explicitly
that hyperparameter search is a separate selection problem BH does not address; it needs
nested CV or selective inference, and saying so is part of the deliverable.

**Definition of done.** A table of distinct tests with their deltas, floors, ratios and the
decision each fed; the selection events listed separately as out of BH's scope.

---

## 04b — The floor-ratio → p-value conversion  ·  **CLOSED 2026-09-07**

**Closed as dissolved, not solved.** The conversion is not needed, because BH is not the right
instrument for this family in the first place.

**Why it was hard.** BH takes p-values. The campaign's CLEARS verdicts are
`Δ / (2*sqrt(2)*sd)` ratios against a noise *scale* estimated from 5 reseeds
(`attribution.py::refit_noise_floor`). Turning 1.21× into a p-value needs a distributional
assumption and df from five reseeds, and that assumption then drives the answer BH ranks.

**Why it goes away.** An **e-value** — a non-negative statistic with expectation ≤ 1 under the
null — can be built **directly from the reseed distribution** by a betting or likelihood-ratio
construction. No p-value, no df on n=5, no distributional assumption smuggled in to make a
conversion work. And e-BH controls FDR under *arbitrary* dependence, which the add-ablation
totals and their permutation-null halves need, since they are arithmetically linked.

**Where the work went instead:** [`09-scoring-instruments.md`](09-scoring-instruments.md) `09b`.

Evidence: [`../research/R1-instruments.md`](../research/R1-instruments.md) §2.
**Do not re-open without a reason that survives the e-value argument.**

---

## 04c — Apply the correction

**Objective.** Report which CLEARS survive campaign-level correction.

**Method.** Benjamini–Hochberg assumes independence or PRDS. The add-ablation totals and their
permutation-null halves are arithmetically linked, so **choose BH or Benjamini–Yekutieli
deliberately and state why** — BY is a log-factor more conservative and is the honest default
under arbitrary dependence.

**Definition of done.** Which claims survive, which do not, and what each failure implies for a
decision already shipped. Some past ship decisions may not survive; that is the point of
running it, not a reason to soften the output.
