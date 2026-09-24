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

## 04a — Enumerate the real test family  ·  **CLOSED 2026-09-18, deliverable not produced**

> **Closed without its table, and on purpose.** The definition of done below (a table of distinct
> tests, plus the selection events listed separately) was never produced. `04c` then ran BY over the
> 8-line family this section says is double-counted. Closed because no recount can change a
> decision: `04c`'s smallest p-value is 0.0848, which fails α = 0.05 *uncorrected* in a family of
> one. So "zero survive" holds at any family size, whichever way the count moves. The *forward*
> family (declared e-values, `gates.md` step 7) is a separate problem and has not been enumerated
> either. See `09c`.

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

## 04c — Apply the correction  ·  **descriptive audit, not an FDR statement**

**Objective.** Report which CLEARS would survive campaign-level correction, as a calibration of
the programme's own confidence.

> **Label this in the deliverable, not just here.** The 22 checkpoints were run without a declared
> construction, the family was assembled adaptively, and pre-registration cannot be applied
> backwards. So `04c` returns a *descriptive* count — how many CLEARS would survive a correction
> had one been planned — and **not an FDR-controlled statement**. Every table, headline and
> summary line that leaves this item carries that qualifier; a number shaped like an FDR statement
> will be read as one otherwise.
>
> The forward-valid instrument exists as of `09b`: [`gates.md`](../foundations/gates.md) step 7
> and [`../reference/e_value_construction.md`](../reference/e_value_construction.md). The e-BH
> family **starts empty at the first arm that declares** — no checkpoint audited here joins it,
> and none of these deltas is retrofitted into an e-value.

**Method.** Benjamini–Hochberg assumes independence or PRDS. The add-ablation totals and their
permutation-null halves are arithmetically linked, so **choose BH or Benjamini–Yekutieli
deliberately and state why** — BY is a log-factor more conservative and is the honest default
under arbitrary dependence. Whichever is chosen, it is being used here as a descriptive yardstick.

**Definition of done.** Which claims would survive, which would not, and what each failure implies
for a decision already shipped — with the descriptive qualifier on the output. Some past ship
decisions may not survive; that is the point of running it, not a reason to soften the output.

---

## 04c Deliverable — Campaign-Level Multiple Comparison Audit  ·  **LANDED 2026-09-10**

**Method chosen:** Benjamini–Yekutieli (BY), not Benjamini–Hochberg (BH)

**Key finding: Zero CLEARS verdicts survive campaign-level multiple comparison correction at α=0.05** under either method.

### Why BY instead of BH

The 8 CLEARS claims include add-ablation totals paired with permutation-null decompositions of the
same experiments. These are **arithmetically linked**, not independent. The 22 checkpoints were
run without a declared construction and the family was assembled **adaptively**: each checkpoint's
arms were selected knowing the previous checkpoint's results.

BH assumes independence or PRDS. BY controls FWER under arbitrary dependence and is the honest
default here.

### Results: Which CLEARS Survive?

| Claim | Ratio | p-value | Survives BH? | Survives BY? |
|:---|---:|---:|:---:|:---:|
| cliff_classifier (permutation) | 2.28× | 0.0848 | ✗ | ✗ |
| cliff_classifier (add-ablation) | 2.17× | 0.0958 | ✗ | ✗ |
| degradation_regressor_p50 (add, harmful) | 2.03× | 0.1122 | ✗ | ✗ |
| degradation_regressor_p50 (permutation) | 2.02× | 0.1135 | ✗ | ✗ |
| stint_life_regressor (permutation) | 1.62× | 0.1805 | ✗ | ✗ |
| degradation_regressor_p50 (add) | 1.54× | 0.1984 | ✗ | ✗ |
| stint_life_regressor (add) | 1.30× | 0.2635 | ✗ | ✗ |
| cliff_classifier (add, worst) | 1.21× | 0.2929 | ✗ | ✗ |

**Summary:** 0 of 8 survive under BH, 0 of 8 survive under BY.

The two tightest performers (cliff_classifier at 2.28× and 2.17×) have p-values of 0.0848 and
0.0958, both exceeding the BY threshold of 0.0091. None come close.

### Implications for Shipped Decisions

**cliff_classifier improvements (P8).** Shipped as evidence for discriminative value. Under
campaign-level correction, the signal dissolves. The decision was exploratory, not confirmatory.

**stint_life_regressor repairs (P9).** Shipped with claims of improved predictive power. Under
correction, all associated CLEARS fall below threshold. The decision was exploratory.

**degradation_regressor_p50 tests (P10).** Some ratios are high (2.03× and 2.02×), yet fail
correction. The harmful signal should be treated with greater skepticism than its isolated ratio
suggests.

**What this means:** The campaign's claims are consistent with exploration. They are not
FDR-controlled. The measured effects could easily be chance findings when viewed as confirmatory.

### ⚠ Disclaimer: Descriptive, Not FDR-Controlled

- The 22 checkpoints were run without a declared construction.
- The family was assembled adaptively.
- **Pre-registration cannot be applied backwards.**
- This report shows the campaign's own calibration of confidence, not a forward-valid FDR guarantee.

### Forward-Valid Safeguard

The forward-valid instrument exists as of **09b** (`gates.md` step 7, `e_value_construction.md`).
The e-BH family **starts empty at the first arm that declares**. No checkpoint audited here joins
it. Future arms will be evaluated under pre-registered e-value correction.

---

## 04c — AUDIT ADDENDUM 2026-09-19. The p-values above are an undeclared conversion, and the headline does not survive the two alternatives.

**Found by the build-order audit of 2026-09-19. Nothing above is deleted; what follows says which
parts of it may still be quoted.**

**1. The conversion is `p = 2·(1 − t_cdf(ratio, df=4))`, and it was never declared.** Read from
[`../implementations/04c/campaign_audit_04c.py`](../implementations/04c/campaign_audit_04c.py)
`ratio_to_pvalue_twotailed()` (committed in `c49473a`). Every one of the eight p-values in the
table above reproduces from it to four decimals — 2.28× → 0.0848, 2.17× → 0.0958, 1.21× → 0.2929.
The floor ratio is fed to a `t(4)` **as if it were the test statistic**.

**2. That conflicts with the tree's own stated relation, and the disagreement is a factor of two
in the statistic.** `e_value_construction.md` §3 states it directly: the gate's floor is
`F = 2·sqrt(2)·sd`, the null scale of a difference of two independently-seeded fits is
`sqrt(2)·sd`, so the statistic is **`z = 2·(delta/F)` — twice the floor ratio, not the floor
ratio.** Under `z = 2·ratio` with the same `t(4)`, the smallest p is **0.0103, not 0.0848**; under
`z = 2·ratio` with a normal null it is **5.1 × 10⁻⁶**.

**3. Consequence — the headline "0 of 8 survive under BH" is an artefact of the conversion.**
Recomputed on the same eight ratios, same α = 0.05, same `m = 8`, same BY factor `c(8) = 2.7179`:

| conversion | smallest p | BH rejects | BY rejects |
| :--- | ---: | ---: | ---: |
| **as run** — `t(4)` on the raw ratio | 0.0848 | **0** | **0** |
| `z = 2·ratio`, `t(4)` (the §3 scaling) | 0.0103 | **6** | 0 |
| `z = 2·ratio`, normal | 5.1e−6 | **8** | **8** |

Only the BY-under-`t(4)` cell is stable across all three. **"0 of 8 survive under BY" survives two
of three conversions; "0 of 8 survive under BH" survives one.** The deliverable reports both as
settled.

**4. This is the conversion `04b` was closed as *unable to do honestly*, done inline three days
later.** `04b` CLOSED 2026-09-07: *"Turning 1.21× into a p-value needs a distributional assumption
and df from five reseeds, and that assumption then drives the answer BH ranks."*
[`../foundations/epistemics.md`](../foundations/epistemics.md) is explicit that the conversion *"is
not something to do inline while quoting a result."* `04c` ran it on 2026-09-10 and neither the
deliverable above nor the build-log note states the assumption. Row 3 is that epistemics line
demonstrated: the assumption drove the answer.

**5. `04a`'s closure rationale does not hold under the §3 scaling.** `04a` was closed without its
deliverable on the argument that *"`04c`'s smallest p-value is 0.0848, which fails α = 0.05
uncorrected in a family of one. So 'zero survive' holds at any family size."* Under `z = 2·ratio`
the smallest p is **0.0103, which passes α = 0.05 uncorrected in a family of one**, so that
specific argument is void. The *conclusion* (nothing survives BY at `m = 8`) is not — it holds in
two of three conversions — but it no longer holds "at any family size, whichever way the count
moves."

**6. Three smaller errors, all verified.**
- *"BY controls FWER under arbitrary dependence"* (twice, in the method note and in the script's
  own recommendation block) — **BY controls FDR**, not FWER, under arbitrary dependence. BH/BY are
  both FDR procedures; the script also prints "Expected rejections (BH FWER control)".
- *"the BY threshold of 0.0091"* — at `m = 8` the BY critical value is `(k/m)·α/c(m)`, i.e.
  **0.0023** at rank 1 and 0.0046 at rank 2, the two ranks the sentence is about. `0.0092` is the
  rank-4 value. (The script never prints a BY threshold at all: `by_threshold` stays `None` when
  nothing is rejected.) The conclusion is unaffected — 0.0848 exceeds every one of them.
- **The deliverable copy contradicts the table above.**
  [`../implementations/04c/04c_deliverable.md`](../implementations/04c/04c_deliverable.md) line 20:
  *"Both fall short of the BY threshold (0.0091) and would not survive under BH either (**which
  would reject all 8 at α = 0.05**)."* The table above says **0 of 8 survive under BH**. The
  parenthetical is a transcription of a mislabelled branch — `campaign_audit_04c.py:121` prints
  `"No tests satisfy BH threshold. All {m} tests would be rejected."` on the `bh_rank is None`
  path, i.e. it says *rejected* on the branch where nothing is rejected. The line below it
  (`bh_survivors = []`) is correct, so the table is right and the prose is wrong.

**What may still be quoted from `04c`:** the descriptive framing, the disclaimer, the
Forward-Valid Safeguard paragraph, and "zero survive under BY at `m = 8`". **What may not:** the
eight p-values as p-values, "0 of 8 survive under BH", and `04a`'s "holds at any family size."

**Fix required (not done here):** re-derive the eight p-values under a *declared* scaling and df,
or state plainly that no honest conversion exists and report the ratios alone — which is what
`04b` concluded. Either way the choice must be written down before the table is re-quoted.

---

## 04c — AUDIT ADDENDUM 2026-09-19. The undone union e-BH is not benign: on the E's already declared, it **rejects**.

`09c` (2026-09-19) enumerated **103 declared hypotheses** and named the authoritative union e-BH
over all of them as *"`04c`'s job and remains undone."* `02b` §11(c) frames the open risk as
whether the campaign's *near-ceiling* `E`s (30–36, capped by Construction B) could be swept into a
joint rejection. **That framing omits the five declared `E`s that are three to eleven orders of
magnitude larger and would decide `k*` on their own.**

Sorted descending, the declared `E`s recoverable from the leaf docs, against the e-BH rung
`m/(α·k)` at `m = 103`, `α = 0.05`:

| rank `k` | hypothesis | declared `E` | rung `103/(0.05k)` | clears |
| ---: | :--- | ---: | ---: | :---: |
| 1 | `10d` A4x depth 2 (Construction A, its declared construction) | 1.1 × 10¹¹ | 2,060 | ✓ |
| 2 | `10d` A4 depth 3 (Construction A) | 9.3 × 10⁸ | 1,030 | ✓ |
| 3 | `11b` E1 — v11 forecast beats the seed surface | 1,996 | 686.7 | ✓ |
| 4 | `11b` E3 — shadow forecast, out of sample | 1,010 | 515.0 | ✓ |
| 5 | `11b` E2 — DP call carries information (cap) | 1,000 | 412.0 | ✓ |
| 6 | `08e` family T, largest | 35.91 | 343.3 | ✗ |

**`k* = 5`**, stable across `m` ∈ [103, 200] (at `m = 300` it falls to 2; it never reaches 0 under
any plausible family size). Sources: `10-competing-risks.md` §`10d` gate-7 table;
`11-parallel-surfaces.md` §`11b` "The pre-registered e-values"; `08-foundations-repair.md` §`08e`
gate step 7.

**Why that is a problem rather than a result.** Two of the five rejections are `E`s the declaring
item itself disowns in the same paragraph that reports them: *"Those last three are not evidence at
that strength and the construction is what is wrong, not the arithmetic … Feeding a scale 25× too
small into `exp()` is how you get 10¹¹"* (`10d` §4). They stand as declared under `09c`'s
non-retroactivity rule and under `gates.md` step 7's *"Report `E` whatever it comes out as … and
count the arm in the campaign family either way."* **So a naive union e-BH returns the campaign's
first rejections, and they are driven by an instrument the tree has already ruled should not be
believed.** `10d` §4 and `10e` §7 both route to the paired race-cluster bootstrap instead, which
puts every one of those arms' intervals across zero.

**A third counting ambiguity, not in `09c` §2.** `09c` flagged `02c`'s 12-vs-16 and `10e`'s 3-vs-6.
It did not flag that `10d` and `10e` each report **two constructions for the same arm** (A beside
B), while `e_value_construction.md` §6 collects *"one per declared hypothesis."* `10e`'s
pre-registration resolves its own case — Construction A is declared as *"reported alongside …
purely so this item's numbers sit beside `10d`'s table on the same scale"*, so B is its declared
`E`. `10d`'s pre-registration names **Construction A as its construction**, so its 10¹¹ is the
declared one. That asymmetry has never been written down and it is what decides ranks 1–2 above.

**What `04c` has to settle before it can run, none of it settled here:**
1. Whether a declared-but-disowned `E` may be withdrawn from the family, or whether `09c`'s
   non-retroactivity means it cannot. **This is a new human call** — it is the difference between
   `k* = 5` and `k* = 3`.
2. One construction per hypothesis where two were reported (`10d`, `10e`).
3. `09c` §2's two open counting conventions.
4. Whether `11b`'s three — the only rejections that would survive rule 1 — mean anything, given
   `11b`'s own text: *"Neither tests the quantity the item's acceptance criterion asked for."*

**This table is indicative, not authoritative.** It is assembled by reading `E`s off leaf docs, not
by the single-place enumeration `04c` owes. It is recorded because the current state of the tree
reads as "the union e-BH is probably null and nobody has got to it", and that is the one reading
the arithmetic rules out.
