> **ARCHIVED 2026-09-07 — this file is a record, not a tracker.**
> Stage now lives only in `_improvements/status/build-log.json`; run
> `python3 _improvements/status/board.py` for the current board. Superseded as a tracker: §3/§3a → `work/01-ceiling-instrument.md` (**read that first — §3b is not safe to build as written**), §5 → `work/04-campaign-audit.md`, §6 → `work/05-model-family.md`. §4 stays closed.
> Paths written inside this file predate the restructure — every `_improvements/<name>.md`
> is now `_improvements/reference/<name>.md`. See `_improvements/README.md`.

# ML Research Program — What the Ceiling Actually Permits, and What It Would Take

Sixth document in the `_improvements/` series, after `PLAN.md`, `transform_gaps.md`,
`ml_headroom.md`, `ml_headroom_ii.md` and `ml_execution_plan.md`. Each of those asked a
question that could be answered by measurement inside the existing frame:

* `transform_gaps.md` — *is the transform layer correct?*
* `ml_headroom.md` / `_ii` — *are the models extracting what the warehouse can give them?*
* `ml_execution_plan.md` — *what does each candidate improvement actually buy, against a noise floor?*

This one asks the question none of them asked:

> **How much is left?** Not "does feature X help" — *what is the bound*, how close are we
> to it, and what would it take to move the bound rather than the model?

**Status: PROBED, NOT STARTED.** Written 2026-09-06 as a program to be opened *after*
`ml_execution_plan.md` closes. Since then: that plan **has** closed (its last open item,
the CDN publish, is a user decision, not work), §4 has been **closed as not viable**, and
§3's method has been **probed and redesigned** — see §3a. Nothing has been built or shipped.
Every figure in §1 is still read from artefacts that already exist; the only new measurement
in this document is §3a's feasibility probe, which was warehouse-read-only and changed no
model, contract, or artefact.

**Headline: on two of three model families, the project does not currently know how much
headroom remains, because the ceiling instrument it has does not bind.** One family
(`stint_life_regressor`) has a hard, trustworthy bound and sits at 71.9% of it. The other
two score *past* their nominal ceilings — not because they are superhuman, but because the
ceiling was built to bound a stint-level oracle on a target that is 99% within-stint
variation. Until a binding ceiling exists, "push harder" has no target, and the difference
between "3% left" and "40% left" is unmeasured.

---

## Provenance (read this before trusting a number)

Every figure in §1 is read directly from `ml/artefacts/evaluation_metrics.json`:

| field | value |
| :--- | :--- |
| `evaluated_at` | 2026-09-05T15:04:31Z |
| `version` | v11 |
| `evaluation_mode` | `cv_final_fold`, `eval_season` 2024 |
| `holdout_season` / populated | 2025 / `False` (2025 not yet ingested) |
| `all_models_beat_baseline` | `True` |
| `all_claims_significant` | `True` |
| `claims_inside_noise` | `[]` |

**That artefact is still current.** Both 2026-09-06 sessions recorded in
`ml_execution_plan.md` (the Phase 10b signed-lateral re-probe, and the 2022 regulation-era
diagnostic) were measurement-only and shipped nothing — no refit, no contract change, no
model artefact touched. The v11 numbers below therefore describe the live models.

No new fits were run for this document. Where a claim is an inference from those numbers
rather than a number, it is marked.

---

## 1. What the ceiling instrument says today

`ml/src/ceiling.py` writes an `attainable` block per model, on one of three bases. The
basis matters more than the number, and it differs by family.

### 1a. `stint_life_regressor` — a hard bound, 71.9% captured

Basis: `perfect_prediction`. The artefact's own note: *"a hard bound, not an estimate —
nothing can score past it, so this fraction cannot exceed 1."*

| quantity | AFT NLL |
| :--- | ---: |
| floor (global-mean remaining life) | 2.2074 |
| **model (v11)** | **1.9520** |
| oracle (perfect prediction) | 1.8524 |
| achieved reduction | 0.2553 |
| **fraction of attainable** | **0.7193** |

The entire remaining headroom is **0.0996 NLL**. The oracle is non-zero because the
log-normal scale is a fitted term, so even exact prediction of every stint's end lap
scores 1.8524.

**Corrected 2026-09-07 (`work/00-corrections.md` 00b). The original text asserted that
safety-car timing "carries no signal in any feature this warehouse could build". That clause is
false, and the 0.80–0.85 cap it justified was never measured. Both are replaced below.**

Remaining stint life is set partly by pit-wall strategy calls and safety-car timing, and those
are not tyre-degradation questions. That much stands. Three things are now measured rather than
inferred:

**Verified — SC/VSC ends a quarter of all stints.** Flagging each stint's final lap from
`int_stint_geometry`'s `is_safety_car_lap` / `is_vsc_lap` (n=8,333 stints, 2018–2024):

| population | SC on final lap | VSC on final lap | either | either, final 3 laps |
| :--- | ---: | ---: | ---: | ---: |
| all stints (8,333) | 15.82% | 4.42% | 19.60% | 21.29% |
| **uncensored — a real pit decision** (5,360) | **22.01%** | **5.75%** | **26.87%** | **27.69%** |
| censored — ends at flag/retirement (2,973) | 4.64% | 2.02% | 6.49% | 9.75% |

The split is the point: a stint that ends in an actual pit stop is **four times** more likely to
end under a deployment than one that runs to the flag. Present in every season (uncensored,
3-lap window): 26.2 / 22.1 / 36.2 / 31.5 / 28.6 / 29.4 / 21.1% for 2018–2024.

**Verified — a hazard feature exists.** `int_sc_hazard_history` holds `sc_hazard_per_lap`,
`vsc_hazard_per_lap`, `any_hazard_per_lap` and empirical-Bayes-shrunk variants for 36 circuits,
over 149 races and 119 SC onsets. So the "no signal in any feature this warehouse could build"
clause is falsified by a table that already exists.

**But do not over-read it in the other direction.** The shrunk per-lap hazard spans only
0.01661 (Spanish GP) to 0.02955 (Saudi Arabian GP) — a **1.8×** spread across all 36 circuits.
That is a per-circuit *base rate*: it says Jeddah interrupts more often per lap than Barcelona.
It cannot say a safety car is coming on lap 32 of this race. So the recoverable share of that
26.87% is bounded well below 26.87%, and nothing here measures where.

**The cap is therefore OPEN, not 0.80–0.85.** The old range was inference resting on a false
premise; deleting the premise does not license a new number. Converting an event share into an
NLL cap needs the loss actually attributable to deployment-ended stints, which is a
measurement nobody has run — see `work/02d`, which this unblocks.

### 1b. `cliff_classifier` — the ceiling does not bind

Basis: `stint_identity_oracle`.

| quantity | macro-F1 |
| :--- | ---: |
| floor (cohort baseline) | 0.2187 |
| oracle, cross-fitted | 0.3634 |
| oracle, in-sample | 0.3749 |
| **model (v11)** | **0.3810** |
| `fraction_of_attainable_in_sample` | 1.0387 |
| `fraction_of_attainable` (cross-fitted) | `None` — no usable denominator |

The model scores **above both oracles**. `between_stint_share` for this target is 0.1943,
so 80.6% of the variance is within-stint — and a *stint-identity* oracle, by construction,
cannot see within-stint variation. The instrument is bounding the wrong thing.

### 1c. `degradation_regressor` trio — the ceiling does not bind, by two orders of magnitude

Basis: `analytic_from_icc`. All three quantiles model the same column
(`next_5_lap_cumulative_jump_s`) and so share `between_stint_share = 0.0094`.

| model | floor | v11 model | oracle (cross-fitted) | achieved reduction | reduction as % of floor | `fraction_of_attainable` |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| p10 | 1.2512 | 0.5209 | 0.9297 | 0.7304 | 58.4% | 124.2× (not binding) |
| p50 | 1.9536 | 1.0121 | 1.7768 | 0.9415 | 48.2% | 102.6× (not binding) |
| p90 | 0.7859 | 0.5592 | 0.7650 | 0.2267 | 28.8% | 61.4× (not binding) |

**Only 0.94% of this target's variance is between-stint.** The ICC-analytic ceiling asks
what a stint-level oracle could achieve, and on a target that is 99.06% within-stint that
bound is nearly zero by construction. The model exceeding it 102× is a statement about the
instrument, not about the model.

### 1d. The finding

> Two of three families — and all four of the five shipped models outside stint life — have
> **no working headroom estimate**. The project's own gate reports "not binding" and moves
> on. Nobody knows whether the degradation trio is at 40% of what is achievable or at 97%.

That is the single most consequential gap in the ML program, and it is upstream of every
other decision: it prices whether the items below are worth doing at all. (§4 has since
closed as not viable, so what §3 prices is §5 and §6.)

---

## 2. The hard external wall (this one does not move)

Before any ladder, the constraint that caps the whole program:

**FastF1 exposes no tyre temperature, no tyre pressure, no wear measurement, and no setup
data** (ride height, camber, wing angle, differential). Tyre degradation is a
thermal-mechanical process, and its actual state variables are not in public data. Teams
have them; the public feed does not.

Two consequences, both permanent:

1. **A mechanistic tyre model can never be validated against ground truth here.** It can
   only be validated against lap time — which is what the current models already do. A
   physics-informed model would be a *reparameterisation* of the same evidence, not an
   appeal to independent measurement.
2. **Thermal state is latent and must be inferred.** The `thermal` feature group
   (`cumulative_push_load_surface` / `_bulk`, `surface_bulk_ratio`) is already an inference
   of exactly this kind. Any further physics work inherits the same unresolvable ambiguity.

Physics-informed *features* remain feasible — lateral load energy is derivable from the
speed trace plus the corner geometry `dim_corners` now provides. Physics *validation* is
not. A research program that claims otherwise is misrepresenting what public F1 data
supports, and this document will not.

---

## 3. Item 1 — build a ceiling that binds  *(do this first)*

**What:** an empirical irreducible-noise floor for the degradation target and the cliff
label, replacing the ICC-analytic construction that does not bind.

**Method sketch (the original one, now superseded — kept because the reasoning below only
makes sense against it):** take near-identical rows in *different* races — same driver,
same compound, same circuit, same tyre-age band, comparable fuel load and track state — and
measure how much the target varies anyway. That residual spread is noise no model can ever
explain, because the model cannot distinguish the rows either.

That sketch was probed on 2026-09-07 before anything was built. **It does not work, and it
fails in a direction that would have retired the program on an instrument artefact.** The
probe is below; the design that replaces it follows.

### 3a. The feasibility probe (run 2026-09-07, measurement only, nothing shipped)

Population: `data/dev.duckdb` read-only, `fct_cliff_prediction_features`,
`is_training_eligible` and `next_5_lap_cumulative_jump_s IS NOT NULL` — **82,315 rows,
6,200 stints, 147 races, 2018–2024**. Marginal SD of the target = **6.083**.

**Protocol anchor, stated because the numbers below are not the artefact's numbers.** The
constant-predictor pinball floors reproduced here are 1.2911 / 2.0094 / 0.8972 (p10/p50/p90)
against `evaluation_metrics.json`'s 1.2512 / 1.9536 / 0.7859. That 2–4% gap is *population,
not disagreement*: this probe pools all seasons, the artefact is `cv_final_fold` on
`eval_season` 2024. It is close enough to confirm the probe's pinball arithmetic matches
`evaluate.py`'s, and that is the only thing it is used for. **Do not diff a probe number
against an artefact number** — same failure mode this series has named repeatedly.

**Failure mode 1 — hand-picked matching keys do not resolve anything.** Within-matched-group
SD across a strictness ladder, one row per stint per group:

| level | usable groups | rows | avg m | within-group SD |
| :--- | ---: | ---: | ---: | ---: |
| circuit + compound + age band(4) | 1,122 | 26,336 | 23.5 | 5.470 |
| + driver | 5,990 | 16,977 | 2.83 | 5.674 |
| + fuel band(20kg) | 4,541 | 10,360 | 2.28 | 5.757 |
| age exact + fuel band | 10,011 | 22,183 | 2.22 | 5.521 |
| + dirty-air band + temp band | 7,405 | 15,990 | 2.16 | 5.305 |

Against a marginal SD of 6.083. Going from three matching keys to seven moves the
within-group SD from 5.470 to 5.305 — **the curve is flat**. These keys explain ~24% of
variance at their strictest, so a floor built on them would report that ~87% of the target's
SD is irreducible and conclude the program is finished. That is exactly the "match on too
few → genuine signal counted as noise → wrongly retire the whole program" risk this section
already named — and it is not hypothetical, it is what these keys do. The model conditions
on 33 features (stint position, compound priors, cliff priors, thermal loads, dirty air,
and the nine `proximity` columns); circuit/compound/driver/age/fuel/temp proxies almost none
of that conditioning power. [Corrected 2026-09-07 by `work/00-corrections.md` 00a: the count
was 24, and the parenthetical named "throttle decay, braking drift" — `racing_line` candidates
that were measured and never shipped, so they are not in the contract at all. The argument is
unchanged in direction and **strengthened**: the wider the space the model conditions on, the
less of it six hand-picked keys can proxy.]

Secondary defect visible in the same table: the levels are **not comparable to each other**,
because each survives on a different row population (26k / 17k / 10k / 22k / 16k). A sweep
whose subsets shift underneath it is not a sweep.

**Failure mode 2 — strict matching cannot support a quantile-valued floor.** Leave-one-out
group-quantile floor at the strictest level (15,511 rows, 7,177 groups):

| q | matched-group LOO "floor" | constant-predictor floor | model v11 |
| :--- | ---: | ---: | ---: |
| 0.1 | 2.4175 | 1.2911 | 0.5209 |
| 0.5 | 2.5138 | 2.0094 | 1.0121 |
| 0.9 | 2.3770 | 0.8972 | 0.5592 |

The estimated "floor" lands **above the stint-blind floor at every quantile**. That is not a
bound, it is estimator variance: at avg m ≈ 2.2, leave-one-out means estimating a p10 from a
single point.

**The two failure modes trade off along the same axis the sweep was going to traverse** —
loosen for group size, lose resolution; tighten for resolution, lose estimability. There is
no good point on that line. The sweep as originally specified would have had to pick one
anyway.

### 3b. The design that survives the probe

Four changes, each aimed at a demonstrated failure rather than an anticipated one:

1. **Pool residuals; do not estimate per-group quantiles.** Centre within each matched
   group, pool the centred residuals into one empirical noise distribution (n ≈ 15k rather
   than m ≈ 2), then read the achievable pinball loss off *that* distribution's quantiles.
   Requires only m ≥ 2 per group. This is what kills failure mode 2. **Named caveat:** it
   assumes one noise distribution across all conditions, which is probably false — noise is
   likely wider near the cliff and in traffic — so stratify the pool (age band, or predicted
   risk decile) and report a conditional noise model rather than a single scalar.
2. **Match in the model's own feature space, not hand-picked keys.** k-NN over the scaled
   33-feature vector, which is the space the model actually conditions on. This is what
   kills failure mode 1. **Not circular:** the neighbour structure is defined on X only,
   never on y and never on the model's predictions. (A leaf-index or prediction-conditioned
   metric *would* be circular — it would measure the model's own resolution and return the
   model's own residual as the "ceiling". Do not use one.)
3. **Replace "strictness sweep" with a radius sweep plus a d→0 extrapolation.** At any
   finite radius the estimate is biased upward by the regression function's variation across
   the neighbourhood; at radius→0 that bias vanishes but neighbours run out. Plot the floor
   against mean neighbour distance and extrapolate the intercept. That gives the sweep a
   principled endpoint instead of an arbitrary rule — which is the thing this section was
   right to refuse to trust. Hold the row population fixed across the sweep (fixed k,
   varying radius reported) so the levels are actually comparable, per the secondary defect
   above.
4. **Independence constraint — kept from the original sketch, and hardened.** Neighbours
   must come from a different stint, preferably a different race, and thin to one row per
   stint per neighbourhood. Otherwise the overlapping 5-lap windows (consecutive rows share
   4 of their 5 terms) and shared stint-level shocks deflate the floor. `ceiling.py` already
   fights this hazard with its non-overlapping thinned ICC estimate — same hazard, same fix,
   and the probe above already applies the thinning.

**Two gates before any number from this instrument is quoted anywhere:**

* **Synthetic recovery test**, following the house convention already set by
  `ml/tests/test_ceiling.py::test_anova_recovers_a_known_icc` (which recovers 0.030 from a
  known 0.03): inject a known noise floor, confirm the instrument returns it.
* **Falsification gate:** the estimated floor must come out **≤ the model's achieved loss**.
  A model cannot beat irreducible noise, so a floor above the model's loss proves the
  instrument is broken rather than the model superhuman. The naive design fails this
  outright (2.5138 vs 1.0121 at p50) — which is how we know it is broken and not merely
  pessimistic. It is free to run, and it is the check that would have caught this before the
  number reached a checkpoint.

**Cost:** ~1 day, unchanged. Warehouse-only; no refits required to establish the floor.

**What it settles:** unchanged in kind, narrower in scope — whether §5 and §6 are worth
starting (§4 is closed). If the degradation trio sits at 90%+ of a *trustworthy* empirical
floor, the last two years of feature work were
near-exhaustive and further feature search is noise-chasing, which is a genuinely valuable
thing to learn and cheap. The probe above does **not** answer that question; it only
establishes that the original instrument would have answered it wrongly.

---

## 4. Item 2 — ~~FP1/FP2/FP3 ingest~~ **CLOSED, NOT VIABLE (2026-09-07)**

> **Do not restart this item.** It was closed in `ml_execution_plan.md`'s
> "Phase 10c closed — not viable, no data pulled" checkpoint (2026-09-07), the day after
> this document was written. This section is retained as a record of why, not as a
> proposal. That checkpoint's own instruction stands: do not resurface 10c without a
> genuine fuel-load or engine-mode proxy in hand — re-raising it without one is
> re-litigating a closed, reasoned decision.

**Why it was closed.** The premise was backwards. The case for 10c was that FP long runs
trade race-strategy confounds for a cleaner degradation signal; checked against the two
fuel-correction models that already exist, FP has confounds of its own that neither can
handle:

* `int_lap_fuel_state.sql` estimates starting fuel as `race_lap_count ×
  fuel_consumption_rate_kg_per_lap` — sound only because a race car's fuel load is sized to
  a *known* distance. An FP long run has no equivalent anchor.
* `int_lap_fuel_state_qualifying.sql` assumes a flat 12 kg — defensible only because quali
  burn-off over one push lap is negligible (~0.006 s). FP long runs are the opposite case:
  many laps, high load, meaningful burn-off.

Fuel burn-off over a long run is comparable in magnitude to the degradation signal itself,
so uncorrected FP rows would corrupt exactly the thing 10c was meant to sharpen. Engine mode
is worse: it has no FastF1 telemetry channel at all, for any session type, so there is
nothing to attempt a correction against.

**What this section originally claimed, and which no longer holds:** that FP ingest was "the
largest untapped data lever" and that the value could be recovered as label enrichment
(better per-compound curves for `compound_cliff_params` / `dim_compounds_season`) rather than
row count. The label-enrichment route was always marked *assumed, not verified* here — it
survives only if sandbagging is tractable, and it inherits the same unestimable fuel load, so
it closed with the rest of the item.

**Consequence for this document:** the ladder is now three items, not four — §3, §5, §6.
There is no remaining "new data source" lever in the program. Whatever headroom §3 finds must
be claimed from the data already in the warehouse.

---

## 5. Item 3 — multiple-comparisons audit of the campaign's own history

`ml_execution_plan.md` carries **8 "CLEARS" claims across 22 checkpoints**, against 138
mentions of "floor". (The denominator moved after this document was written: 17 checkpoints
at 2026-09-06, 22 at 2026-09-07. The five added since are all measurement-, maintenance- or
closure-only and add no new CLEARS, so the numerator is unchanged at 8 — but re-count both
with `grep -c "^## Checkpoint"` and `grep -c CLEARS` before running the audit rather than
trusting this line, since it goes stale every session.) Each claim was tested against its own ~2σ reseed floor. **None was
corrected for the number of tests run across the campaign.**

With enough independent tests at a fixed per-test threshold, some proportion of "CLEARS"
verdicts is expected from chance alone. That is a real risk to any decision that was made on
a single 1.2×–1.5× floor crossing.

**The mitigating factor, which is what makes this auditable at all:** this project records
its negatives. Most campaigns cannot be corrected retrospectively because the failures were
never written down and the denominator is unknown. Here the denominator is on the page.

**What to do:** enumerate every floor comparison across all 22 checkpoints, apply
Benjamini–Hochberg at the campaign level, and report which CLEARS survive. Some past ship
decisions may not — that is the point of running it, not a reason to avoid it.

**Cost:** ~1 day of document archaeology plus arithmetic. No refits.

---

## 6. Item 4 — the model-family question, which has never been asked

Seventeen checkpoints of hyperparameter search inside **one model class**. Whether
gradient-boosted trees are the right class for this data has not been tested once.

The data has structure that trees handle only implicitly:

* **Nesting** — lap within stint within race within season, with driver and constructor
  crossing that hierarchy. A hierarchical / mixed-effects model represents this directly and
  would give per-level variance components as output, which is *itself* an answer to the
  headroom question in §3.
* **Smooth, monotone physical curves** — degradation against tyre age is physically expected
  to be smooth and mostly monotone. A GAM encodes that as a prior; a tree ensemble has to
  spend capacity rediscovering it and can produce non-monotone artefacts (which
  `behaviour_audit`'s monotonicity probe already checks for, and which would become
  unnecessary under the right model class).

**Cost:** days to weeks. **Lowest expected value of the three — unless §3 shows real headroom
remains**, in which case it moves up, because a model-class change is the kind of move that
could actually claim it.

---

## 7. What this document is not

* **Not a record of work done.** Nothing here has been implemented. §1 is read from an
  existing artefact; §2–§6 are unstarted.
* **Not a commitment to all items.** §3 is explicitly designed to price the others, and a
  plausible outcome is that §5 and §6 are never worth starting. §4 is already closed, and
  the program shrank from four items to three without any of them being attempted.
* **Not a replacement for `ml_execution_plan.md`.** That file stays the tracker until it is
  closed. This one opens after it.
* **Not a claim that the models are underperforming.** All five beat their baselines in every
  season 2020–2024 (verified 2026-09-06, `ml_execution_plan.md`'s regulation-era checkpoint).
  The claim is narrower and different: *we cannot currently say how much better they could
  be*, on four of the five.

---

## The first command the next session should run

> **Superseded 2026-09-07.** The live handoff is `_improvements/status/build-log.json`; run
> `status/board.py` for the current pointer. §3b's estimator **must not be built as written** —
> `work/01-ceiling-instrument.md` 01b carries five defects in it, four of which §3b's own
> falsification gate cannot detect. The feature-space figure below was corrected 24 → 33 by
> `work/00-corrections.md` 00a; the rest of the section is kept as the record of what it asked for.

`ml_execution_plan.md` is closed — its only remaining open item is the CDN publish/app-deploy
decision, which is explicitly the user's call and not work this program depends on. **This
program is open.** §4 is closed as not viable, so the ladder is §3 → then §5 and §6 priced by
whatever §3 returns.

Start with **§3b, not §3's original sketch** — the sketch is disproven, not merely untested,
and §3a carries the numbers. Concretely, the first artefact this program should produce is:

> a curve of estimated irreducible **pinball loss** (p10/p50/p90, in the headline units, not
> in variance) against **mean k-NN distance in the scaled 33-feature space**, for
> `next_5_lap_cumulative_jump_s`, on `data/dev.duckdb`, **read-only** — with the d→0
> extrapolated intercept reported alongside the curve, never instead of it.

Build the synthetic recovery test **before** running it on real data, and run the
falsification gate (floor ≤ model's achieved loss) on every point of the curve. A point that
violates it is an instrument failure and must be reported as one, not dropped from the plot.

Two standing constraints inherited from `ml_execution_plan.md`'s handoff protocol, both of
which apply to this program too: the probe scripts are throwaway, live in the scratchpad, are
never committed, and must not touch `ml/models/*.json`, warehouse data, or git state; and any
number produced here is quoted with the protocol that produced it, never diffed against a
number from a different protocol (§3a's own anchor paragraph is the worked example).
