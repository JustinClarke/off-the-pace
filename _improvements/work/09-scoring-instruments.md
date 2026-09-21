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

**Landed 2026-09-10.** [`gates.md`](../foundations/gates.md) carries step 7;
[`../reference/e_value_construction.md`](../reference/e_value_construction.md) carries the worked
constructions and the fill-in pre-registration block; `04c` is relabelled a descriptive audit.

Three constructions rather than one, because the cheap one has a hole worth naming. **A** is the
single-delta betting e-value `exp(lambda*delta/s - lambda^2/2)`, which reduces to `exp((2/c^2)(z-1))` under
the gate's own floor as the declared alternative — one line, but valid only with a scale fixed
*independently of* the five reseeds being scored, since `sd/sigma ~ sqrt(chi2_4/4)` puts a ~16% chance
on those five understating `sigma` by 40%. **B** is the paired safe-t e-value on five paired
real-vs-shuffled deltas (Grünwald–de Heide–Koolen), exact for unknown `sigma`, and is the recommended
default at a price of 10 refits where step 4 spends 2. **C** is the shuffle-rank e-value, assumption-free
and capped at `K+1`.

The null is the **information contrast** (real vs row-shuffled), not arm vs baseline — under
arm-vs-baseline the delta is not mean-zero under H₀, because capacity moves whether or not the
columns carry signal, which is the Phase 10a failure step 4 already exists to catch.

Two calibration facts the doc states explicitly, both uncomfortable and both correct: `E > 1` does
not mean "clears" (a 0.8× floor delta returns `E = 3.3` at `c = 1`), and a lone rejection at
`alpha = 0.05` in a family of 30 needs `E >= 600`, i.e. ~2.1× the floor. A paired arm at `t = 7.3`
returns `E = 17` and does not clear e-BH alone. That is the price of arbitrary dependence plus
optional stopping, not a defect in the construction.

---

## 09c — Construction B cannot reject in any family larger than one

**Found 2026-09-18** by the build-order audit. `02c` hit the symptom first and recorded it as "a
defect in the pre-registration found by executing it". No item owned it after that.

**The arithmetic.** Construction B (`e_value_construction.md` §4, the recommended default) is
bounded above at the pre-registered `n = 5`, `g = 1`. As `t → ∞`,
`E → (1 + n·g)^((n−1)/2) = 6² = 36`. e-BH (§6) rejects the largest `E` only if `E ≥ m / alpha`,
which is `20·m` at `alpha = 0.05`. So a single rejection can only happen in a family of **one**.
At `m = 2` the threshold is 40, and no data can reach it. Checked numerically: `t = 10⁶` returns
36.0000.

**Every "e-BH rejects nothing" in the tree is this ceiling, not the data.**

- `02c`: 12 hypotheses, threshold 240.
- `10e`: 4 arms, threshold 80. Its best arm, `E_B = 35.9`, sits at the ceiling.
- `08i`: 35 declared arms, not yet counted. They could not clear even if they were.

`09b`'s landing note quotes a family-of-30 threshold (`E ≥ 600`) for Construction A, which is
unbounded. It does not state B's ceiling.

**Options — for this item to rule on.** The ceiling is `(1 + n·g)^((n−1)/2)`. `08i`, `02c` and
`10e` alone declare at least 51 hypotheses, which puts the threshold at **≥ 1,020**.

| `n` reseeds | `g` | ceiling | clears ≥ 1,020? | cost |
| ---: | ---: | ---: | :---: | :--- |
| 5 | 1 | 36 | no | today |
| 5 | 4 | 441 | no | same refits; bets on a 2-sd effect, so less power against small ones |
| 10 | 1 | ~48,600 | yes | 20 refits per arm instead of 10 |

Another option is to narrow what the family is: per item rather than per campaign. That is the
selection problem step 7 exists to prevent, so it has to be argued, not assumed. Sizing any option
needs the declared forward family enumerated. Nothing in the tree does that yet (`04a` was about
the retrospective family and closed without its table).

**What this item must not do.** It must not re-score any arm already run under a new `g` or `n`.
Those `E`s were declared and stand as declared. Changing the construction after seeing them is
exactly what declaration exists to prevent. The new construction applies to arms declared *after*
it lands.

**Definition of done.**

- A construction whose ceiling clears the e-BH threshold at the enumerated family size, stated with
  its power cost.
- The ceiling formula added to `e_value_construction.md` §4, next to the worked example.
- `gates.md` step 7 says to check the ceiling against the family size before declaring.
- The 100k-draw null check re-run on the new parameters.

**Cost:** ~0.5 day. **Blocks** every future arm: `02b`, `02c` and `02d` depend on it in the log.

**Landed 2026-09-19.**

**1. The forward family, enumerated — and the ≥ 51 figure above was itself an undercount.**
`04a` closed without producing this table (see its closing note) and handed the job here. Swept
every leaf doc that has declared a gate-7 e-value since `09b` landed (2026-09-10) — not just the
three this section opened with:

| item | declared hypotheses | source |
| :--- | ---: | :--- |
| `02b` | 20 | "declares 20 hypotheses (the original 16, plus 4 for the stint-life follow-on)" |
| `02c` | 12 | "Twelve declared hypotheses are counted (A/B/C × four families)" — the doc itself flags a 16-count alternative reading (P per family included); unresolved, see §3 below |
| `07` | 1 | "this adds 1 hypothesis to the campaign family" |
| `08e` | 5 | "Within this item's declared family of five, e-BH ... rejects all five" |
| `08f-1` | 3 | AFTER-vs-BEFORE on the three continuous families; cliff/stint-life move 0.0 by construction and are not live tests |
| `08h` | 10 | 2 declared arms (candidate alone, candidate+`push_residual` pair) × 5 families, confirmed against `ml/artefacts/08h_baseline_observations_n_arms.json`'s `families` block |
| `08i` | 35 | "15 declared cross-floor hypotheses ... plus 20 within-floor information arms" |
| `10b` | 2 | "Two declared hypotheses, added to the campaign family" |
| `10d` | 5 | "The family is therefore five declared arms — A1, A2, A3, A4, A4x" |
| `10e` | 3 | "The family is therefore three declared arms — S1, S2, X1" (2026-09-19 re-run; supersedes the "4 arms" this section's opening note cited from the pre-rerun state) — flagged alternative reading of 6 below |
| `11a` | 4 | "this adds 4 hypotheses to the campaign family" |
| `11b` | 3 | "this adds 3 hypotheses to the campaign family" |
| **total** | **103** | |

The threshold for a lone rejection at `m = 103` is `20 × (103 + 1) ≈ 2,080`. **Not ≥ 1,020** — this
section's own opening estimate summed three of twelve contributing items and undercounted by
roughly half.

**2. Two counting-convention inconsistencies found while enumerating, not resolved here.**
`02c`'s own doc flags 12 vs 16 (whether the permutation-null arm `P` counts as its own declared
hypothesis per family) and leaves it open. `10e`'s doc reports both a Brier `E` and a slope `E` per
arm but states "the family is therefore three," implicitly not counting Brier and slope as separate
hypotheses — inconsistent with `02c`'s own "arms × families" convention, which would make it 6.
Both read the same either way for `09c`'s purpose (36 clears neither reading of either item's
threshold, 48,559 clears both), so the table above uses each item's own literal headline number
and does not adjudicate the ambiguity. Whoever runs `04c` next needs a single resolved convention
before computing an authoritative total; this note is not it.

**3. Family boundary ruled: campaign-wide, not per-item.** The fourth option this section named —
narrowing "the family" to per-item — is **rejected**. `04c`'s own "Forward-Valid Safeguard" section
states the design directly: *"The e-BH family starts empty at the first arm that declares... Future
arms will be evaluated under pre-registered e-value correction"* — one family, not one per item.
Several items have nonetheless been computing and reporting a **local** e-BH read using only their
own arm count as `n` (`08e`'s "within this item's declared family of five... rejects all five,"
`10b`'s "over the two declared hypotheses rejects both," `10e`'s "over the three declared arms
rejects all three on Brier") — `08e`'s own text already flags this as a within-item preview, not
the campaign verdict, and hands enumeration to `04a`. Narrowing to per-item would make every
family's size a matter of where a session happens to draw its leaf-doc boundary, which is exactly
the adaptive-family problem `04a`/`09b` closed the retrospective door on; it is not reopened here to
buy a smaller denominator. **Consequence, stated plainly:** none of `08e`'s, `10b`'s or `10e`'s
"rejects" statements are the campaign's actual e-BH verdict — each was computed against a family far
smaller than the 103 already declared at the time. `04c` has not been re-run against the union
since `09b` landed (its last run predates every row in the table above); doing so, correctly, is
follow-on work this item does not do — recomputing a true `k*` needs every declared `E`, not just
its per-item count, assembled in one place, which is `04c`'s job and remains undone.

**4. Construction ruled: `n = 10, g = 1`, for every arm declared after this lands.**
`E_max(10, 1) = 11^4.5 = 48,558.70`, clearing the `≈2,080` bar with a **~23.3×** margin, and does not
need revisiting again until the declared family approaches `E_max / 20 ≈ 2,428` hypotheses — the
family has taken about nine days to reach 103, so this is not assumed to be forever, but it is not
"before the next arm" fragile either. `g = 5·4 = 441`-style options (`n = 5, g = 4`) are ruled out:
441 does not clear 2,080 (nor the original, wrong, 1,020), and no `g` at `n = 5` can — the exponent
`(n-1)/2 = 2` is what caps it, not `g`. Construction A (unbounded) is not chosen instead: it is
still valid only for a scale fixed independently of the reseeds being scored (§3's stated hole),
which `n = 10, g = 1` does not need.

**Power cost, stated without hedging.** Raising `n` from 5 to 10 costs **20 refits per arm instead
of 10** (10 real + 10 shuffled, at ten paired seeds instead of five) — pure compute, paid once per
arm. It is **not** a power cost against small effects the way raising `g` would be: for a fixed true
effect size, `t` scales with `sqrt(n)`, so the same population delta produces a *larger* `t` at
`n = 10` than at `n = 5`, not a smaller one — a bigger `n` buys ceiling headroom and tightens the
estimate of the paired mean at the same time. The genuine operational cost not covered by "20
refits": `gates.md` step 3's reseed floor (`2*sqrt(2)*sd`) is defined over 5 reseeds, and
Construction B's efficiency (`10` refits, not `15`) came from *reusing* the floor study's five
seeds for the paired real/shuffled arms. At `n = 10` that reuse needs the floor study to also run
at ten seeds, or the arm pays 5 (floor) + 20 (paired) = 25 refits rather than 20. This item does not
change `gates.md` step 3's "5 reseeds" language — that is a separate step, out of this item's four
definition-of-done bullets — and flags it here as the thing whoever runs the next arm at `n = 10`
has to decide (reuse ten seeds for both, or pay the extra five).

**Not re-scored, per this item's own constraint.** `02c`'s `E ∈ {34.0, ..., 0.628}`, `08i`'s 35
`E`s, `10e`'s `E_B = 35.9` / `35.57`, `02b`'s `E` up to `32.6`, `08e`'s `30.03–35.91`, `08h`'s,
`08f-1`'s, `10b`'s `35.41`/`34.50`, `10d`'s, `07`'s, `11a`'s and `11b`'s — every `E` already declared
above under `n = 5, g = 1` (or whatever each item's own construction was) stands as declared. `09c`
does not touch any of them. `n = 10, g = 1` applies only to an arm whose pre-registration is written
after this landing note exists.

**5. Ceiling formula landed in `e_value_construction.md` §4**, next to the worked example:
`E_max(n, g) = (1 + n*g)^((n-1)/2)`, with the sizing rule ("check `E_max` against `20*(m+1)` before
fixing `n`, `g`") and a cross-reference back here for the current `m`.

**6. `gates.md` step 7 updated** to require looking up the current declared family size and sizing
`n`/`g` against `E_max(n, g) >= 20*(m+1)` before declaring, with the same non-retroactivity
statement as here.

**7. The 100k-draw null check, re-run at `n = 10, g = 1`.** Reimplemented the existing
`safe_t_e_value` / `e_value_validity_check` pair (verbatim formula from
`scripts/arms_08i_min_observations_floor.py:254-303`, which every `arms_*` script in the tree
copies) in a scratchpad probe, seeded at `S.RANDOM_STATE = 20260528` matching every existing arm
script, `n_draws = 100,000`, i.i.d. `N(0, sigma)` deltas:

| `sigma` | mean `E` (`n=5,g=1`, reproduced as a harness check) | mean `E` (`n=10,g=1`) | MC SE (`n=10,g=1`) |
| ---: | ---: | ---: | ---: |
| 0.001 | 1.0016 | 0.9896 | 0.0270 |
| 0.01  | 0.9992 | 1.0314 | 0.0464 |
| 0.1   | 1.0108 | 0.9525 | 0.0227 |
| 1.0   | 1.0014 | 0.9962 | 0.0332 |

The `n=5,g=1` column reproduces the numbers already on record in `08e`/`08i`/`08h` exactly,
confirming the reimplementation is faithful. At `n=10,g=1`, mean `E` sits within 1–2 MC SE of 1.00
at every `sigma`, but the MC SE itself is **4–9× larger** than at `n=5` — expected, not a defect:
the cap is 1,349× higher (48,559 vs 36), so the null distribution of `E` has a heavier right tail
and 100k draws resolves its mean less tightly. Re-run at 1,000,000 draws across three independent
seeds to confirm this is Monte Carlo noise and not a broken construction: mean `E` ranged
**0.976–1.033** (MC SE 0.010–0.021) across all twelve (seed × sigma) cells — consistent with a true
null mean of 1.00 throughout. The `t = 10^6`-style boundary check (`09c`'s opening arithmetic)
reproduces analogously at the new parameters: a synthetic near-zero-variance delta set at
`n = 10, g = 1` returns `E = 48558.7036`, matching `E_max(10, 1)` to the digits shown. The worked
example in `e_value_construction.md` §4 (`n=5,g=1`, `t=7.31`) reproduces at `E = 17.0468`, matching
its published `17.0` to three figures. Scratch script, not committed, per the standing ad-hoc-probe
rule.

**Definition-of-done check.** All four bullets met: (a) `n=10, g=1` ruled, ceiling `48,558.70`
clears the enumerated `≈2,080` bar with its refit cost stated plainly; (b) the ceiling formula is in
`e_value_construction.md` §4 beside the worked example; (c) `gates.md` step 7 now requires the
ceiling-vs-family-size check before declaring; (d) the 100k-draw null check re-ran at the new
parameters, table above, real output. **Left undone, named rather than hidden:** the `02c` 12-vs-16
and `10e` 3-vs-6 counting-convention ambiguities (§2); whether `gates.md` step 3's reseed floor
moves to 10 seeds alongside Construction B (§4's power-cost paragraph); and `04c` re-running the
*authoritative* union e-BH over all 103 (or more, once those ambiguities resolve) declared `E`s,
which would retroactively correct `08e`'s, `10b`'s and `10e`'s local "rejects" readings (§3). None
of these are this item's four bullets; all three are logged so the next session does not have to
re-discover them.
