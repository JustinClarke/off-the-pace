# 09 — Scoring instruments

**Group:** 09 · **Depends on:** nothing · **Prices:** `01a`, `01b`, `04`, `05`

Opened 2026-09-07 out of research round R1. Two changes to *how the programme scores things*,
both cheap, both of which have to land before the measurements they would otherwise invalidate.
Evidence: [`../research/R1-instruments.md`](../research/R1-instruments.md) §2 and §3.

---

## 09a — CRPS alongside the pinball trio, with its decomposition

**Objective.** One proper score for the predictive distribution, plus a decomposition that reads
on the headroom question for free.

**The problem.** The degradation family reports pinball at α ∈ {0.10, 0.50, 0.90}. Each is a
strictly proper scoring rule *for its own quantile* — that part is sound — but three losses are
three headlines, and the programme repeatedly has to reason about "p50 clears but p90 does not"
with no rule for combining them.

**Method.** Averaged quantile loss over a refining grid converges to the **CRPS**, which is
strictly proper for the whole distribution, sits in the target's units, and reduces to MAE for a
point forecast — so it is directly comparable to the existing baselines. Report it beside the
trio; do not replace the trio.

Then publish the **calibration / resolution / uncertainty** decomposition (Murphy's
calibration–resolution principle; the CRPS decompositions of Arnold et al.). The third term is an
empirical irreducible-difficulty term — **an independent read on the same quantity `01b` is trying
to estimate**, from a different direction, at the cost of arithmetic over predictions that already
exist.

**Why before `01a`.** Learning curves read in pinball and then re-read in CRPS is the same work
twice. And a distributional model (`05`) cannot be compared to the incumbent trio at all without
a score that covers both.

**Acceptance.** CRPS reported per degradation model on the `cv_final_fold` split, with the
three-term decomposition, and the uncertainty term stated next to whatever `01b` returns.

**Definition of done.** `make ml-evaluate` emits CRPS and its decomposition; the history entry
states whether the uncertainty term and `01b`'s floor agree, and by how much.

**Landed 2026-09-08, with one logged deviation from this spec.** `ml/src/crps.py`: CRPS is a
3-point trapezoidal approximation of `2 * integral pinball_alpha dalpha` over the trio's own
{0.10, 0.50, 0.90}, flat-extended to [0, 1] (exact only in the point-forecast limit, per
`ml/tests/test_crps.py`). The decomposition uses **equal-frequency binning of the raw forecast**
as the recalibration step, not the full isotonic/PAV recalibration Arnold et al. actually use —
that is more exact and was out of `09a`'s "hours" budget. Consequence, checked against real
data: **`dsc >= 0` is a provable guarantee under binning** (a finer partition's per-bin optimum
weakly dominates the 1-bin global constant `unc` uses), but **`mcb` is not** — a negative `mcb`
means the raw forecast beats its own binned recalibration, i.e. it carries real within-bin
information a bin constant cannot capture. This is not hypothetical: the first `make ml-evaluate`
run against real data landed `mcb = -0.0049` (crps=1.460, dsc=1.299, unc=2.765) — the model is
strong enough to trip exactly this case. Only `reconstructed_crps == crps` and `dsc >= 0` are
asserted anywhere; do not add an `mcb >= 0` assertion, it would be asserting something false. If
a future item wants the full isotonic/PAV version (a `mcb >= 0` guarantee too), that is new
scope, not a bug fix here.

---

## 09b — e-value pre-registration, and campaign-level e-BH

**Objective.** Make `gates.md` step 6 mechanically useful, and give the campaign a multiplicity
statement that is actually valid.

**The problem.** `04` proposes retrospective Benjamini–Hochberg over 22 checkpoints. **BH assumes
a fixed family chosen in advance.** This campaign's family was chosen adaptively — each
checkpoint's arms were picked knowing the last one's results, and it stopped when it stopped for
reasons related to what it found. Retrospective BH over that produces a number shaped like an FDR
statement. Pre-registration cannot be applied backwards.

**Method.** An **e-value** is a non-negative statistic with expectation ≤ 1 under the null — the
betting analogue of a p-value. Two properties fit this campaign exactly:

- **e-BH controls FDR under arbitrary dependence** between the e-values. No independence
  assumption, no PRDS, no assumption about how the family was assembled.
- **Stopped e-BH is anytime-valid** — FDR controlled at any data-dependent stopping time, which
  is the literal shape of a research campaign that stops when it stops.

Each new arm declares its e-value construction **in its leaf doc, before it runs**. The campaign
carries a running e-BH decision that stays valid however many arms are added.

**And it dissolves `04b`.** An e-value is built directly from the reseed distribution by a betting
or likelihood-ratio construction — no p-value, no df on n=5, no distributional assumption
smuggled in to make a conversion work. `04b` is closed on that basis, not solved.

**Acceptance.** `gates.md` carries a seventh step requiring a declared e-value construction per
arm; one worked construction exists for the reseed-floor setting so the next arm has a template.

**Definition of done.** The next item that runs an arm declares its e-value before running, and
`04c`'s output is labelled a descriptive audit rather than an FDR-controlled statement.
