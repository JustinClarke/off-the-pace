# Unused Channels — What the Warehouse Already Holds That the Feature Contract Does Not

Seventh document in the `_improvements/` series, after `PLAN.md`, `transform_gaps.md`,
`ml_headroom.md`, `ml_headroom_ii.md`, `ml_execution_plan.md` and `ml_research_program.md`.

Those asked whether the transform layer is correct, whether the models extract what the
warehouse gives them, what each candidate improvement buys, and how much headroom is left.
This one asks a narrower question that none of them asked directly:

> **The feature contract reads 13 warehouse models. The warehouse has 79 tables.
> What is in the other 66, is any of it a new information channel rather than another
> transform of lap times, and what would each one cost to admit?**

**Status: INVENTORY, NOTHING BUILT.** Written 2026-09-07. Every row count and column list
below was read from `data/dev.duckdb` read-only on that date. No model, contract, artefact
or warehouse object was touched. Nothing here has been ablated, so nothing here is a claim
that any of it works — only that it exists, that it is a different channel, and that the
repo's own admission rule has not yet been pointed at it.

> **STALE AS OF `08m` (2026-09-16) — every number in this document that is measured against
> `next_5_lap_cumulative_jump_s` is on the OLD target.** `08m` fixed how the compound seed's
> `compound_cliff_severity` is consumed (it is fitted as a ~5.5-lap level shift and was being
> charged once per lap, up to 48 times) and dropped the never-fitted `0.002*age^2` term, then
> rebuilt the warehouse. The target's mean moved **−1.8793 s → −0.3946 s** and
> `is_training_eligible` moved **82,470 → 81,619** rows. Specifically affected here: the Phase 10a
> p50 pinball figures in §"Where the contract stands", and the `mean next_5_lap_cumulative_jump_s`
> columns in the §2 and §3 population tables. The *rulings* in this document — `02a`'s leakage
> ruling, the admission rule, the tier structure — are unaffected. Any arm in `02b`/`02c`/`02d`/`02g`
> that has already been scored must be re-scored on the rebuilt target before its delta is quoted
> again; `08m` did **not** re-measure them.
>
> **`02b` was re-scored 2026-09-19 — see its Verdict.** Two things that run found are not local
> to it: the reseed floors moved by up to **3.2×** (p10 0.004311 → 0.00136797), so any
> pre-registration saying to *reuse* a floor across `08m` is void; and §1's
> `between_stint_share = 0.0094` is **0.0643** on the rebuilt target, so §1's cap on Tiers 1/3/4
> is 6.8× looser than this document states. `02c`, `02d` and `02g` remain unre-measured and
> inherit both corrections.

---

## 0. The admission rule this document is written against

This is not a wish list, because the series already has a rule for what may be added, and
it was learned expensively.

**Phase 9 (2026-09-05)** dropped 18 of 42 columns — the `powertrain` (6), `telemetry_cliff`
(5), `weather_air` (2), `track` (2) and `context` (3) groups — on a noise-floor group
ablation across all three ablation-bearing families. Every dropped group cleared in none of
them. The contract went 42 → 24.

**Phase 10a (2026-09-05)** then added nine columns and cleared: p50 pinball 1.034661 →
1.012128 (1.54× floor), cliff macro-F1 0.372960 → 0.380950 (2.17× floor). The contract went
24 → **33**, which is where it stands at v11.

The stated reason 10a worked where the Phase 9 groups did not, in `schema.py`'s own words,
is that `proximity` is *"the first group in either series sourced from a DIFFERENT SENSOR
rather than from a further transform of the car channel or of lap times."*

**So the ranking principle here is channel novelty, not intuition about mechanism.** A
candidate that is another arithmetic rearrangement of lap-time residuals should be expected
to fail, because five such groups already have. A candidate that reads a sensor or a session
the contract has never touched is the only kind with a track record of clearing.

**Correction to carry forward:** `ml_research_program.md` and its predecessors repeatedly
say "24 features". The shipped contract has been **33** since v11. Anything that defines a
feature space — including §3b's k-NN ceiling design — must use 33, not 24.

---

## 1. The constraint that caps three of the four tiers

`ml_research_program.md` §1c measured `between_stint_share = 0.0094` for
`next_5_lap_cumulative_jump_s`. **99.06% of the degradation target's variance is within
stint.**

That is not a curiosity, it is a hard filter on everything below. A feature that is constant
within a stint — a weekend-level quali number, a per-circuit hazard rate, a season-level
constructor coefficient — can only ever address the 0.94%. It may still help the cliff
classifier (`between_stint_share` 0.1943) and stint life (a different target shape
entirely), but it **cannot** move the degradation trio much, and a design that expects it to
is misreading §1c.

Only one tier below varies lap to lap. That tier is where the degradation headroom is, and
it is not the cleanest one.

| tier | channel | varies within stint? | can move the p10/p50/p90 trio? |
| :--- | :--- | :--- | :--- |
| 1 — qualifying | different session | no (weekend-constant) | no — cliff & stint life only |
| 2 — corner inputs | position/telemetry, new construct | **yes (per lap)** | **yes** |
| 3 — marshalling | track status / race control | no (circuit-constant) | no — stint life mainly |
| 4 — misc | mixed | partly | marginal |

---

## 2. Tier 1 — Qualifying: an entire session the ML has never read

**What exists, verified by row count 2026-09-07:**

| table | rows | seasons |
| :--- | ---: | :--- |
| `int_qualifying_decomposed` | 14,165 | 2018–2024 |
| `int_qualifying_push_laps` | 46,234 | 2018–2024 |
| `int_qualifying_segments` | 447 | 2018–2024 |

Plus `int_constructor_structural_pace_qualifying`, `int_lap_fuel_state_qualifying`,
`stg_results_qualifying`, `int_lap_residual_decomposed_qualifying`. None of it is referenced
by `fct_cliff_prediction_features`, which reads 13 models, all race-session.

`int_qualifying_decomposed` carries a full pace decomposition per quali lap:
`quali_pace_delta_s`, `quali_skill_residual_s`, `quali_skill_session_avg_s`,
`quali_vs_race_skill_delta_s`, `constructor_component_s` (with SE and CI),
`ratio_to_segment_best`, `tyre_life`, `track_temp_c`, `quali_traffic_flag`, `dnq_flag`.

**Leakage: zero, by construction.** Qualifying is run before the race. No lag, no expanding
window, no leave-one-out wrapper is required — the session is strictly prior in wall-clock
time to every lap of the target. This is the only candidate in this document that needs no
anti-leakage treatment at all, and it should still go through the forward-window audit as a
formality.

**Why this is not Phase 10c, and why §4's closure does not reach it.** `ml_research_program.md`
§4 closed FP1/2/3 ingest as not viable because FP long runs have no fuel anchor:
`int_lap_fuel_state.sql` estimates starting fuel from a *known* race distance, and an FP long
run has no equivalent. That objection is real and it is fatal to FP.

It does not apply here, and the repo already says so. `int_lap_fuel_state_qualifying.sql`
assumes a flat 12 kg, which §4 itself describes as *"defensible only because quali burn-off
over one push lap is negligible (~0.006 s)"*. §4 raises that sentence as the contrast that
condemns FP. Read the other way round, it is a statement that **the fuel problem is already
solved for qualifying, by a model that has been in the warehouse the whole time.**

So: §4 correctly closed the largest untapped data lever and concluded *"there is no remaining
new data source lever in the program."* That conclusion is too strong. Qualifying is a
different session, already ingested, already decomposed, already fuel-corrected, and never
read. **Assumed, not verified:** that it carries signal. Nothing below is measured.

**Mechanism, stated so the ablation has a hypothesis to falsify.** Qualifying is the car and
driver at low fuel, new tyres and maximum push — the reference point race degradation is
implicitly measured against. Two constructs look most promising:

* `quali_vs_race_skill_delta_s` — a driver fast over one lap but not over a stint is the
  definition of poor tyre management, and that is the target.
* `constructor_component_s` with its SE — a car's one-lap aero/power level, measured on a
  session where strategy and traffic are near-absent, as a cleaner car term than the race
  session can give.

**The honest ceiling on this item.** Grain is (race_year, race_id, driver_id) — one row per
driver per weekend. Joined to a lap-level matrix it is stint-invariant, so per §1 it addresses
0.94% of the degradation target's variance. **Expect this to clear on `cliff_classifier` and
`stint_life_regressor` or not at all.** If it is pitched as a degradation-trio win, the pitch
is wrong before the ablation runs.

**Cost:** ~1 day. One join, no new ingestion, no refit of anything upstream.

---

### `02b` — Tier 1, qualifying: built 2026-09-14, arms pre-registered — definition of done

**What was built.**

* `int_qualifying_driver_summary` (new, grain `(race_year, race_id, driver_id)`, 2,912 rows)
  rolls `int_qualifying_decomposed`'s push-lap rows up to one row per driver-weekend: MEAN of
  `constructor_component_s` (+ SE), MIN of `quali_pace_delta_s` and `ratio_to_segment_best`
  (both "higher = slower" by construction, so MIN is the driver's best), MAX of
  `quali_skill_session_avg_s` and `quali_segments_contested_n` (already constant at this grain
  one level up, so MAX is a value-preserving collapse, not a real aggregation), plus
  `COUNT(*)` as `quali_push_laps_n`. `quali_vs_race_skill_delta_s` is deliberately **not**
  carried — it is the forward-reach construct `int_qualifying_decomposed`'s own
  `aggregation_scope_exemptions` entry names (a same-race average of
  `driver_skill_residual_s`, not knowable until the race has finished, the same shape `02a`
  ruled on one grain coarser).
* `fct_cliff_prediction_features` carries the resulting seven columns, joined on
  `(race_year, race_id, driver_id)` and broadcast onto every lap of that driver's race. They
  are **in the mart and not in `ml/src/schema.py`'s `FEATURE_COLUMNS`** — same standing as
  `02c`'s ten columns and Phase 10a's `proximity` group before their ablations. The contract
  moves only if the arms below say it should.
* `schema.yml`: an `aggregation_scope_exemptions` entry for `int_qualifying_driver_summary`'s
  one `GROUP BY` (accepted — every input row is a qualifying push lap, strictly prior to the
  race it will be joined onto, and the one column with a forward-reach defect is excluded from
  the `SELECT`), plus a full `columns:` block; a `dbt_utils.unique_combination_of_columns` test
  on the grain key; and the seven columns added to the mart's enforced dbt contract in
  `transform/models/marts/schema.yml`.
* `dbt run --select int_qualifying_driver_summary+ fct_cliff_prediction_features --target dev`
  — both models materialize clean. `dbt test` on the same selection — **8/8 pass** (the new
  model's `unique_combination_of_columns` and three `not_null`s, plus the mart's pre-existing
  cliff-horizon and bound tests, unaffected by the join).
* `python3 -m ml.src.features --check` — **CLEAN** end-to-end: forward-window audit clean,
  aggregation-scope audit clean (the new exemption is honoured), leakage guard clean at 32
  features (the contract has not moved), fingerprint recomputed.

**Coverage/missingness, measured on the mart's 121,193 training-eligible rows.**
`quali_push_laps_n` is never NULL — 0, not NULL, for a driver-weekend with no row in
`int_qualifying_driver_summary` at all, matching `corner_input_coverage`'s "measured zero, not
missing" convention from `02c`. The other six columns are NULL on exactly 2,360 rows
(**1.947%**), and verified NULL **if and only if** `quali_push_laps_n = 0` (checked both
directions: every one of the 2,360 NULL rows has `quali_push_laps_n = 0`, and zero rows with
`quali_push_laps_n = 0` carry a non-NULL pace/skill value). So `quali_push_laps_n` is a
**perfect** NULL indicator for the group — cleaner than `02c`'s `corner_input_coverage`, which
was continuous and only correlated with its group's missingness.

**The gap is not a random subset, and it has two distinct shapes.**

By season:

| season | n | NULL | % NULL |
| ---: | ---: | ---: | ---: |
| 2018 | 15,110 | 1,206 | **7.981** |
| 2019 | 17,722 | 358 | 2.020 |
| 2020 | 13,833 | 59 | 0.427 |
| 2021 | 18,585 | 301 | 1.620 |
| 2022 | 16,915 | 142 | 0.839 |
| 2023 | 18,756 | 145 | 0.773 |
| 2024 | 20,272 | 149 | 0.735 |

2018 alone carries 51.1% of all NULLs on 12.5% of the rows. Five 2018 races drive most of it —
`2018_1` (Australian GP) is **51.4%** NULL, `2018_11` 29.7%, `2018_8` 29.1%, `2018_7` 22.8%,
`2018_5` 21.7% — against a 147-race median of exactly 0.0% and a mean of 2.18%. **This is an
ingestion gap, not a DNQ pattern.** In `2018_1`, ten of the nineteen drivers on track have no
row in `int_qualifying_driver_summary` at all, and they include LEC, OCO, PER, ALO and BOT —
none of whom failed to qualify for the 2018 Australian GP. Within 2018, the NULL rate is
roughly uniform across the grid (STR 20.4%, VAN 18.2%, down to VER 7.6%, LEC 6.1%, HAM 2.7%,
SAI 0.0%) rather than concentrated on backmarkers, which is the signature of a season-wide
`int_qualifying_decomposed`/upstream ingestion defect, consistent with 2018 already being
flagged elsewhere in this warehouse as the first ingested season with known gaps (e.g.
`int_stint_geometry`'s 325 stints FastF1 never assigned).

Outside 2018, the shape flips to genuinely driver-concentrated and small: SAR (Sargeant) 15.1%,
KUB (Kubica) 7.5%, MSC (Mick Schumacher) 6.9%, GRO (Grosjean, 2019+) 4.5%, all other regulars
under 3%. These four are specifically the grid's weakest / part-season / substitute drivers in
their seasons, which reads as genuine per-session incidents (a Q1 exit with no representative
time, a red-flagged session) rather than a pipeline defect — but this is not verified row by
row, only inferred from the concentration pattern.

**The missingness is not label-neutral, though the effect is modest.** Same check `02c` ran on
its own coverage gap:

| rows | n | mean `next_5_lap_cumulative_jump_s` | sd | share `laps_until_cliff_class = 0_to_2` |
| :--- | ---: | ---: | ---: | ---: |
| pace/skill columns present | 118,833 | −2.1715 | 6.225 | 0.0923 |
| pace/skill columns NULL | 2,360 | **−1.7831** | 6.805 | **0.1288** |

Missing rows degrade slightly worse (less negative = closer to worsening) and are 39% more
likely to be within 2 laps of a cliff crossing. Smaller than `02c`'s gap (which ran
+1.393 vs −2.330 s) but the same direction. **Not forward leakage** — a driver-weekend's
qualifying record is settled before the race starts, full stop — but a model handed the six
columns as bare NaNs could still partly split on "this driver-weekend has no qualifying
record" rather than on the pace/skill values themselves. Because `quali_push_laps_n` is a
*perfect* indicator of that missingness (not merely correlated, as `corner_input_coverage`
was), it is carried in Arm A precisely so that channel is explicit rather than an implicit NaN
pattern, mirroring `02c`'s reasoning for admitting `corner_input_coverage` alongside its
residuals.

#### Pre-registered arms — written before any arm is run (gates.md step 6)

Baseline is the shipped 32-column contract on `cv_final_fold`, train 2018–2023, eval 2024,
using `evaluate.py`'s own `_fit`/`_score` — identical protocol to `02c`. Families:
`degradation_regressor` p10/p50/p90, `cliff_classifier`. Each delta is judged against that
family's own 5-reseed floor `2*sqrt(2)*sd` from `attribution.py::refit_noise_floor`, seeds
`RANDOM_STATE + 0…4` = 20260528…20260532 — the same five `02c` used, so the floors are
identical numbers already on record (p10 0.004311, p50 0.010431, p90 0.009347, cliff
0.005772) and do not need refitting.

| arm | columns | what it tests |
| :--- | :--- | :--- |
| **A — full** | 7 (all) | The group as designed: constructor pace + driver form + the coverage indicator. |
| **B — constructor pace** | 2 — `quali_constructor_pace_mean_s`, `quali_constructor_pace_se_mean_s` | A car's one-lap aero/power level at low fuel, near-zero traffic — a genuinely different measurement than anything in the 32-column contract, which carries no quali-session car term at all. |
| **C — driver form** | 4 — `quali_pace_delta_best_s`, `quali_ratio_to_segment_best_min`, `quali_skill_session_avg_s`, `quali_segments_contested_n` | A driver's one-lap pace and consistency this weekend — the safe proxy left after `quali_vs_race_skill_delta_s` was excluded for its forward-reach defect. |
| **P — permutation null** | 7 (Arm A's columns) | Arm A's columns row-shuffled in train *and* eval. Capacity = shuffled − baseline; information = real − shuffled, reported separately (gates.md step 4). |

`quali_push_laps_n` sits in Arm A only — it is not split into its own confound arm the way
`02c`'s `corner_input_coverage` was. That is a deliberate asymmetry, named here so it is not
mistaken for an oversight: `02c` needed a coverage-only arm because `corner_input_coverage` was
*continuous* and could plausibly carry a track-state signal of its own (and did, on p90).
`quali_push_laps_n` is a *binary-in-effect* indicator (0 vs a tight cluster of push-lap counts)
whose only measured job is marking exactly the six-column NULL pattern above — there is no
comparable hypothesis under which it is an independent channel. If B and C together clear
without A clearing by more, that would itself be evidence the indicator is inert, which is
checked in the readings below rather than pre-empted with a fourth arm.

**Primary hypothesis:** per §1, this group's grain is stint-invariant (every lap of a driver's
race sees the same value), so it can only address the 0.94% of the degradation target's
variance that is between-stint. The primary hypothesis is therefore that **Arm B and/or Arm C
clears its floor on `cliff_classifier`**, not on the degradation trio. A result on the trio
would be surprising enough to double-check the split before trusting it.

**Declared in advance as the reading of each outcome**, so no result can be reinterpreted after
the fact:

* **Only cliff clears (B and/or C), the trio does not.** This is what §1's argument predicts.
  Admits the group on `cliff_classifier`, closes the degradation-trio question for this
  channel.
* **B clears, C does not, on cliff.** Constructor pace is the carrying signal; driver form adds
  nothing beyond the car term. Ship B alone if either clears.
* **C clears, B does not, on cliff.** Driver form (this-weekend pace/consistency) is the
  carrying signal, not the car term. The mirror image of the case above.
* **A clears but neither B nor C does.** Ambiguous, recorded as ambiguous — `02c`'s p50 outcome
  on that item, not rounded up here either.
* **Any family clears on the degradation trio.** Recorded as a genuine surprise against §1's own
  argument, re-examined rather than assimilated to the qualifying reading before it is trusted
  — a stint-invariant feature moving lap-to-lap variance would mean something is wrong with the
  join (e.g. it is not actually constant within a stint) or with §1's own between-stint-share
  measurement, and that gets checked before the result gets celebrated.
* **Nothing clears.** Tier 1 is closed on the degradation-trio and cliff families. The
  stint-life family (below) is the only one left for this channel, and it remains barred until
  `10e`.

**One sequencing constraint, inherited from `10d` and unchanged since `02c`'s own copy of it.**
`10d` showed the shipped stint-life booster was tuned under the wrong label (the mixture NLL,
with 2024 in the validation folds), so a floor measured against it now would be measured
against a model about to change. **`10e` has NOT landed** as of 2026-09-14 — production
`ml/models/stint_life_regressor_best_params.json` is unchanged from its pre-S1x state (build-log
2026-09-11 D4: the landing agent hit a rate limit and never executed the retrain). `02b`'s arms
run only on the degradation trio and `cliff_classifier`; **`stint_life_regressor` is BARRED and
is not part of this pre-registration.** No arm above names it, and the runner script refuses it
outright rather than leaving the bar to a reader's memory, the same way `02c`'s did. When `10e`
lands, the stint-life column of every arm here becomes its own follow-on registration — it does
not retroactively join this one.

#### E-value pre-registration — `02b`

```
H0                : the seven 02b columns (per arm) carry no information (real vs
                    row-shuffled, gates.md step 4)
Statistic         : per family -- p10/p50/p90 pinball, cliff macro-F1;
                    cv_final_fold, train 2018-2023, eval 2024
Delta orientation : delta = score(shuffled) - score(real) for losses (pinball);
                    delta = score(real) - score(shuffled) for macro-F1. Positive = improvement.
Construction      : B (paired safe-t), identical to 02c's choice and for the same reason --
                    no separate reseed study of this substrate exists at the 32-column
                    contract, so Construction A's scale would be a plug-in from the same five
                    seeds it scores. B is exact for any unknown sigma.
Seeds             : 20260528, 20260529, 20260530, 20260531, 20260532  (RANDOM_STATE + 0..4,
                    the same five 02c used and the same five the floors above are quoted from)
Parameters        : n = 5, g = 1  (a one-sd effect; 02c's default, no better number available)
Formula           : E = (1 + 5g)^(-1/2) * [ (1 + t^2/4) / (1 + t^2/((1+5g)*4)) ]^(5/2),
                    t = sqrt(5) * d_bar / s_d   ->  at g = 1, max attainable E = 36 (n=5)
Declared alt      : delta* = the family's own floor 2*sqrt(2)*sd, reusing 02c's measured
                    floors (p10 0.004311, p50 0.010431, p90 0.009347, cliff 0.005772) since
                    the baseline contract and split are unchanged.
Family            : four arms (A/B/C/P) x four families = 16 declared hypotheses, every one
                    reported whatever E comes out as. Campaign-level decision is e-BH per 04c,
                    same convention 02c used. 02c's own family-size ambiguity (12 vs 16,
                    depending whether P counts per family) applies here identically and is not
                    re-litigated.
Validity check    : before trusting the implementation, push 100k draws of five i.i.d.
                    N(0, sigma) deltas through it at several sigma and confirm mean(E) = 1.00
                    to Monte Carlo error. Required by the reference; 02c's script already
                    implements this check and 02b's reuses the same function.
```

**Run 2026-09-14, and that run is superseded.** `scripts/arms_02b_qualifying.py` implements
the protocol above, modeled directly on `scripts/arms_02c_corner_inputs.py` (same
`_fit`/`_score` calls, same permutation and paired-seed machinery, same `safe_t_e_value`
implementation). It executed 2026-09-14 16:22–16:53 UTC. **Every delta it produced is on the
pre-`08m` target and none of them may be quoted** — see the STALE banner at the head of this
document. `08m` did not re-measure them; this item does, below.

#### Follow-on registration — `stint_life_regressor` · written 2026-09-19, before the arm ran

The original pre-registration barred `stint_life_regressor` outright and said why: `10d` had
shown the shipped booster was tuned under the wrong label, so a floor measured against it
would be measured against a model about to change. It also said what happens when that
changes — *"when `10e` lands, the stint-life column of every arm here becomes its own
follow-on registration — it does not retroactively join this one."*

**`10e` landed 2026-09-19** (commit `a17f147`; `ml/models/stint_life_regressor_best_params.json`
now carries S1x's parameters). The bar is discharged. This is that follow-on registration,
written before the arm was run, and it is deliberately a *separate* family — the four arms
below are four new declared hypotheses, not a fifth column bolted onto the sixteen already
declared.

| field | value |
| :--- | :--- |
| Family | `stint_life_regressor`, headline `aft_nloglik` (**lower is better**) |
| Columns | identical to Arms A / B / C / P above — the same seven columns, same three subsets |
| Split | `cv_final_fold`, train 2018–2023, eval 2024 — 99,849 train / 19,973 eval rows, 32 baseline features |
| Instrument anchor | `evaluation_metrics.json`'s current stint-life headline **2.153151721488012**, not any figure quoted before 2026-09-19 (the headline moved with `08m`/`08n` and again with `10e`'s landing) |
| Floor | measured in-run by `attribution.py::refit_noise_floor` over seeds 20260528–20260532. **Not borrowed from `10e`** — `10e`'s §3 floors are for `slope`, `Brier` and `AUC`, and gates.md step 3 forbids borrowing a floor across metrics as firmly as across families. The seed is injected into `AFTBooster`'s own params dict (it has no `set_params`), exactly as `arms_10d_calibration_arms.fit_seeded` does it. |
| E-value | Construction B (paired safe-t), n = 5, g = 1, same five seeds, cap **36** — unchanged from the block above |
| Family size | four more declared hypotheses (A/B/C/P × one family), every one reported whatever `E` comes out as |

**Primary hypothesis.** §1's table predicts stint life is the *other* family a weekend-constant
feature can reach — its target is a different shape from the degradation trio's, and a
stint-invariant covariate is not automatically inert against it the way it is against
within-stint variance. But this is a genuinely open prediction, not a dressed-up expectation:
qualifying measures one lap at low fuel on new tyres, and remaining stint life is a quantity
about the *end* of a long run. The mechanism connecting them is not obvious, and if nothing
clears that is the honest answer.

**Declared readings, before the numbers exist:**

* **B and/or C clears on stint life.** Admits the group on a second family. Which arm clears
  says whether it is the car's one-lap level or the driver's one-lap form doing the work.
* **A clears but neither B nor C does.** Ambiguous, recorded as ambiguous — the same treatment
  `02c`'s p50 got and the same treatment the block above declares.
* **Nothing clears.** Tier 1 closes on stint life too, and — with the degradation trio and
  cliff results below — the qualifying channel is closed on every production family.

**Re-scoring the original sixteen is a re-measurement, not a new registration.** The arms,
columns, families, split, seeds, construction and declared readings are all unchanged from
what was written down on 2026-09-14. Only the substrate moved, and it moved underneath the
item rather than being chosen by it. Re-running a declared hypothesis on a corrected target is
what the STALE banner *instructs*; treating it as a fresh registration would be the error,
because it would let the 2026-09-14 numbers quietly drop out of the family.

---

### Verdict — `02b` · MEASURED 2026-09-19

**Qualifying carries real, non-trivial information about tyre cliff onset, and the carrying
channel is the driver's one-lap form rather than the car's one-lap level.** It carries
nothing usable about remaining stint life, and nothing about the median or optimistic tail
of degradation. Run: `scripts/arms_02b_qualifying.py --allow-stint-life`, 2026-09-19
09:05–09:38 UTC (~33 min). Artefacts: `ml/artefacts/02b_qualifying_arms.json` (per-seed
headlines, e-value components, instrument checks) and `.log`.

#### 1. Gate 1 — instrument check: PASS, all five families

Every family's 32-column refit reproduced today's published headline to six decimals.
Anchored on the **current** `evaluation_metrics.json` as the 2026-09-19 build-log note
requires, not on any pre-`08m` figure.

| family | refit baseline | published | metric |
| :--- | ---: | ---: | :--- |
| `degradation_regressor_p10` | 0.4764640778 | 0.4764640778 | pinball |
| `degradation_regressor_p50` | 0.9823587336 | 0.9823587336 | pinball |
| `degradation_regressor_p90` | 0.5128462338 | 0.5128462338 | pinball |
| `cliff_classifier` | 0.3524660979 | 0.3524660979 | macro-F1 |
| `stint_life_regressor` | 2.1531517215 | 2.1531517215 | `aft_nloglik` |

The stint-life row is doing double duty: it confirms `10e`'s S1x parameters are the ones in
production, and it confirms the survival plumbing added to the runner for this item
(censoring flags and the model's *fitted* AFT scale threaded through both fit and score) is
correct. Scoring at the module-default scale would have produced a plausible wrong number
rather than an error, which is precisely the failure mode this gate exists to catch.

#### 2. Gate 2 — add-ablation on the identical split

`cv_final_fold`, train 2018–2023, eval 2024, `evaluate.py`'s own `_fit`/`_score`, 32 baseline
features, contract `v12`. Degradation/cliff bundle and the stint-life bundle each built once
and shared across their arms. Stint life: 99,849 train / 19,973 eval — the post-`08m`/`08n`
fold the build-log note flags.

#### 3. Gates 3 + 4 — every delta, with its floor ratio

Floors are each family's **own**, measured in-run over seeds 20260528–20260532. "raw" is the
add-ablation delta over floor; "info" is the permutation-corrected delta (`real − shuffled`)
over the same floor. Positive is improvement on every metric. **Clears** requires both,
per gates.md's "What clears means".

| family | floor `2√2·sd` | arm | raw ×floor | info ×floor | E | clears |
| :--- | ---: | :--- | ---: | ---: | ---: | :--- |
| p10 | 0.00136797 | A full | −0.22 | +0.03 | 2.86 ↓ | no |
| | | B constructor pace | +0.56 | +0.20 | 4.56 ↓ | no |
| | | C driver form | −2.93 | −2.38 | 4.07 ↓ | no |
| p50 | 0.01115092 | A full | +0.79 | +0.16 | 3.88 | no |
| | | B constructor pace | +0.73 | +0.16 | 0.709 | no |
| | | C driver form | +0.52 | +0.10 | 1.52 | no |
| **p90** | 0.00839541 | A full | +1.41 | +0.95 | 17.1 | **no** — raw clears, information misses |
| | | **B constructor pace** | **+1.90** | **+1.42** | 19.7 | **YES** |
| | | **C driver form** | **+1.04** | **+1.20** | 12.4 | **YES** |
| **cliff** | 0.00433972 | **A full** | **+7.27** | **+7.47** | 32.4 | **YES** |
| | | **B constructor pace** | **+4.60** | **+4.67** | 32.4 | **YES** |
| | | **C driver form** | **+6.80** | **+6.56** | 32.6 | **YES** |
| stint life | 0.00808138 | A full | +0.87 | +0.94 | 20.7 | no |
| | | B constructor pace | +0.67 | +0.36 | 3.28 | no |
| | | C driver form | +0.58 | **+0.00** | 2.7 | no |

↓ = `direction_is_improvement = false`; the E is evidence *against* exchangeability in the
wrong direction and must not be read as support. The declared formula is symmetric in `t`
and is reported as declared.

**Harness is clean.** The shuffle-vs-shuffle negative control returned `E` < 1 in all five
families (0.474–0.676), and the Monte-Carlo validity check returned mean `E` = 1.0016 /
0.9992 / 1.0108 / 1.0014 at σ = 0.001 / 0.01 / 0.1 / 1.0 over 100k draws.

**Headline deltas for the clearing arms**, in their own units:

* `cliff_classifier` macro-F1 **0.35247 → 0.38404** (Arm A, +0.03157), **→ 0.37245** (B,
  +0.01998), **→ 0.38196** (C, +0.02949).
* `degradation_regressor_p90` pinball **0.51285 → 0.49693** (B, −0.01592 = improvement),
  **→ 0.50415** (C, −0.00869).

#### 4. Two of this document's own premises were wrong, and both are corrected here

**(a) The floors moved, so the pre-registration's instruction to reuse them is void.** The
`02b` block above says to reuse `02c`'s floors "since the baseline contract and split are
unchanged". After `08m` they are not unchanged. Measured against reused floors, this item
would have mis-ruled on two families:

| family | floor quoted in the pre-registration | floor measured 2026-09-19 | ratio |
| :--- | ---: | ---: | ---: |
| p10 | 0.004311 | **0.00136797** | 0.32× |
| p50 | 0.010431 | 0.01115092 | 1.07× |
| p90 | 0.009347 | 0.00839541 | 0.90× |
| cliff | 0.005772 | **0.00433972** | 0.75× |

p10's floor is **3.2× tighter** than the reused number. Gates step 3 says each family gets
its own floor; it now also has to mean *on the substrate being scored*. The runner measures
floors in-run, so the numbers above are safe — but the text was wrong and is corrected.

**(b) §1's governing constraint is off by 6.8×, and it is the reason a "surprise" is not a
surprise.** §1 caps three of four tiers on `between_stint_share = 0.0094` — "99.06% of the
degradation target's variance is within stint". Re-measured on the rebuilt target with the
production estimator (`evaluate.variance_ceiling`, `anova_icc_oneway_non_overlapping`):

| target | §1's figure | measured 2026-09-19 | estimator |
| :--- | ---: | ---: | :--- |
| `next_5_lap_cumulative_jump_s` | 0.0094 | **0.0643** | `anova_icc_oneway_non_overlapping`, n = 81,619, 6,203 stints |
| `laps_until_cliff_class` | 0.1943 | **0.2688** | `gini_anova_icc_oneway`, n = 113,226, 6,782 stints |

So it is **93.6% within-stint, not 99.06%**. The estimator's own `n_rows = 81,619` matches
`08m`'s banner figure exactly, which cross-checks the substrate. §1's cap is real but far
looser than stated, and a weekend-constant feature reaching the p90 tail is no longer the
contradiction §1 says it would be.

**This check was run before the p90 result existed, not after it.** The pre-registration
declared that any clear on the degradation trio "gets checked before the result gets
celebrated", naming two suspects. Both were tested in advance:

1. *Is the join actually constant within a stint?* **Yes** — zero stints and zero
   driver-weekends in the 119,822 training-eligible rows carry more than one distinct value
   of `quali_constructor_pace_mean_s`. Not the explanation.
2. *Is §1's between-stint-share measurement wrong?* **Yes**, by 6.8×. That is the
   explanation, and it is a defect in this document rather than in the result.

#### 5. Reading each declared outcome

Against the block above, outcome by outcome:

* **"Only cliff clears (B and/or C), the trio does not"** — half right. Cliff clears on all
  three arms, decisively. But the trio is not uniformly closed: p90 clears on B and C.
* **"B clears, C does not" / "C clears, B does not"** — neither. On cliff both clear, and
  **C (+6.80/+6.56) beats B (+4.60/+4.67)**, so the carrying channel is the driver's one-lap
  form, not the car term. On p90 both clear, with B ahead. The pre-registered either/or does
  not describe the data.
* **"A clears but neither B nor C does" → ambiguous** — did not occur. The inverse did, on
  p90: **both halves clear and the 7-column union does not** (A raw +1.41, information
  +0.95). Recorded as exactly that. It is the mirror image of the Phase 10a trap gate 4 was
  written for, and it says the full set pays more capacity than the combination earns back.
* **"Any family clears on the degradation trio" → genuine surprise, re-examined** — occurred
  on p90; both named checks run in advance; resolved to §4(b), a stale constraint rather
  than a broken join.
* **Follow-on, "nothing clears" → Tier 1 closes on stint life** — occurred. Nothing reaches
  the floor (best raw +0.87×). Arm C is the cleanest negative in the whole item: capacity
  +0.00462, information **+0.00003**, i.e. the four driver-form columns do precisely nothing
  for remaining stint life once capacity is accounted for.

#### 6. What it is worth — the floor and the e-value disagree, as gates.md says to report

Gate 3 says B and C clear on p90 and all three clear on cliff. **Gate 7 cannot reject
anything, for reasons that have nothing to do with these numbers.** Under the declared
Construction B at n = 5, g = 1, `E` is capped at **36**; e-BH needs `E ≥ 20·m`. This item
declares **20 hypotheses** (the original 16, plus 4 for the stint-life follow-on), putting
the threshold at **400**. The best E here is 32.6. No arm could pass whatever it measured.

That ceiling is `09c`'s, not this item's, and `09c` forbids re-scoring any already-run arm
under a new `n` or `g` — so these E's stand as declared and the campaign-level question stays
open until `09c` lands. **The item therefore remains `MEASURED`, not `GATED`**, which is what
the build order's `02b → 09c` dependency has been encoding all along.

#### 7. Coverage, re-verified on the rebuilt substrate

The built-section figures were measured on 121,193 mart rows pre-`08m`. Re-measured on the
current 119,822 training-eligible rows, every claim reproduces:

* Six columns NULL on **2,325 rows (1.9404%)**; `quali_push_laps_n` never NULL.
* Still a **perfect** indicator, checked both directions: zero rows NULL-with-`n`≠0, zero
  rows present-with-`n`=0.
* 2018 still carries the gap — 7.983% vs 0.410–2.021% elsewhere; `2018_1` **51.39%** NULL
  (claimed 51.4%) with the same ten drivers missing, including LEC, OCO, PER, ALO and BOT.
* Outside 2018 still small and driver-concentrated: SAR 14.85%, KUB 7.46%, MSC 6.92%,
  GRO 4.33%.
* Missingness still not label-neutral, same direction: NULL rows mean
  `next_5_lap_cumulative_jump_s` **−0.2506** vs **−0.4652** present, and 0.1394 vs 0.0998
  share in the `0_to_2` cliff bucket.

#### 8. The written verdict: which drivers, and how much does it matter

**A caveat on the question as posed.** The brief for this run asked for "top drivers on
straights". **`02b` contains no straight-line channel** — its seven columns are whole-lap
qualifying pace and skill. Straight-line speed is a different measurement and is not in this
item, so the ranking below is *one-lap qualifying pace*, which is what was actually built and
measured. The straight-line question is answered separately, and negatively, in §9.

**`quali_skill_session_avg_s` cannot be ranked raw.** It averages a driver's best-lap skill
residual across the segments they contested, and which segments you contest is itself a
function of pace: mean residual runs −0.5861 (1 segment) → −0.6132 (2) → −0.6754 (3). A raw
leaderboard puts ALB, RUS and ZHO above VER and HAM, which is a composition artefact.
Restricted to Q3 weekends (3 segments, ≥30 weekends per driver) the confound is removed:

| driver | Q3 weekends | skill residual (s) | SE | gap to VER |
| :--- | ---: | ---: | ---: | ---: |
| **VER** | 132 | **−0.9114** | 0.0495 | — |
| ALO | 64 | −0.8488 | 0.0867 | 0.0626 |
| RUS | 65 | −0.7867 | 0.0857 | 0.1247 |
| LEC | 113 | −0.7392 | 0.0526 | 0.1722 |
| PIA | 36 | −0.7359 | 0.1195 | 0.1755 |
| HAM | 129 | −0.7281 | 0.0665 | 0.1833 |

**How much it matters, stated honestly.** Verstappen is top, and he is separably ahead of the
*middle* of the grid — 0.2043 s on the median driver, about 4 SE. He is **not** separably
ahead of Alonso: the 0.0626 s gap is smaller than Alonso's own SE (0.0867). The grid-wide sd
of driver means is 0.1101 s against a median per-driver SE of 0.0671 s, a ratio of roughly
1.6:1. **So a coarse top group is supportable and a fine-grained leaderboard is not.** Any
ordering below about third place is inside the noise.

**And it matters to the models, on two families.** This is the part that is not a descriptive
ranking: adding these columns moves `cliff_classifier` macro-F1 by **+0.0295** (Arm C, 6.6×
its own noise floor after the permutation correction) and `p90` pinball by **−0.0159**
(Arm B, 1.4×). Cliff onset is the prediction that matters operationally — it is the one a pit
wall acts on — and one-lap qualifying form is a genuine, previously unread input to it.

#### 9. The straight-line question, answered

The warehouse **does** hold a straight-line channel that nothing reads:
`stg_laps_qualifying.speed_st_kph` (speed trap), non-null on **45,272 of 46,234** qualifying
push laps (97.9%), 2018–2024, alongside `speed_i1_kph`, `speed_i2_kph` and `speed_fl_kph`.
Grepped across `transform/models/` and `ml/src/`, these appear **only** in staging —
`stg_laps.sql`, `stg_laps_qualifying.sql`, `stg_sector_times.sql` and their `schema.yml`. No
intermediate, no mart, no feature contract.

**But the driver signal in it is negligible.** Teammate-differenced (same car, same weekend,
best trap speed per driver-weekend, ≥40 pairings):

| driver | pairings | mean Δ vs teammate (kph) |
| :--- | ---: | ---: |
| ALB | 96 | +1.875 |
| ALO | 106 | +1.085 |
| HAM | 146 | +0.568 |
| LEC | 145 | +0.538 |
| VER | 144 | +0.319 |

The **entire grid spans under 2 kph on roughly 320 kph — below 1%** — and what spread exists
is best explained by tow and rear-wing level rather than driver input. This is the expected
answer physically: a driver does not drive a straight, the car does. **Recommendation: do not
raise a Tier 1 straight-line item on the strength of driver skill.** `speed_st_kph` may still
be worth an item as a *car* channel — it is a genuinely new sensor reading in the §0 sense,
which is the kind with a track record of clearing — but that is a different hypothesis and it
is not registered here. Folding it into `02b`'s arms after seeing these results is exactly the
post-hoc arm-adding gates step 6 exists to prevent.

#### 10. Standing

**`MEASURED`.** Gates 1–5 run and passed; gate 6 satisfied for the original family on
2026-09-14 and for the stint-life follow-on before it ran; gate 7 declared and reported but
**structurally unable to reject** until `09c` raises the e-value ceiling.

What a later session may quote from this item: the gate-3 floor ratios, on the post-`08m`
substrate, as measured above. What it may **not** quote: any 2026-09-14 delta, and §1's
`between_stint_share = 0.0094` as a live constraint.

Recommended next, none of it done here: (i) `09c`, which gates whether any of this survives
campaign-level correction; (ii) a decision on admitting B and C to `FEATURE_COLUMNS` for
`cliff_classifier` — the contract is unmoved at 32 and this item does not move it; (iii) §1's
tier table re-derived against 0.0643, since three tiers were sized against 0.0094.

---

## 3. Tier 2 — Corner-level driver inputs: the only lap-varying candidate

**What exists:**

| table | rows | grain |
| :--- | ---: | :--- |
| `int_corner_skill_residuals` | **2,206,939** | lap × corner |
| `int_corner_metrics` | 2,593,635 | lap × corner |
| `fct_telemetry_deltas` | 24,501,520 | race × driver-pair × corner × lap |

`int_corner_skill_residuals` carries `braking_loss_s`, `mid_corner_residual_s`,
`exit_residual_s`, `corner_residual_total_s`, `corner_residual_unexplained_s`, each already
expressed as seconds against a 5-lap-bucket field median. **The ML has never read any of it.**

**Why this is the highest-ceiling item despite Tier 1 being cleaner.** It varies lap to lap.
Per §1 it is the only tier that can address the 99.06% of degradation variance that lives
within a stint.

**Mechanism.** Braking, rotation and throttle application are the direct physical inputs of
energy into a tyre. The incumbent `thermal` group (`push_residual`,
`cumulative_push_load_surface`/`_bulk`, `surface_bulk_ratio`) *infers* push load from
lap-time residuals. This measures the inputs instead of inferring them. That is a genuinely
different construct even though it shares the telemetry sensor with `proximity`.

**The known risk, named precisely.** Phase 9 dropped `powertrain` and `telemetry_cliff`,
which were *"the mart's entire consumption of int_lap_telemetry_aggregates"*. So a previous
attempt to feed telemetry into the contract failed. But Phase 10a then re-read the same
ingestion through a different aggregation and cleared at 1.54×/2.17×. The evidence therefore
says **the aggregation failed, not the sensor.** That puts all the risk of this item in the
aggregation design, which is where it should be stated:

* per lap, aggregate the three phase residuals across the corners of that lap — mean, sd and
  max are the obvious three, and sd is the one with a tyre-management story behind it;
* consider splitting by corner type using `dim_corners` geometry, since a slow hairpin and a
  high-speed sweep load a tyre differently;
* `field_corner_sample_n < 5` yields NULL, and `corner_unmapped_flag` exists — **count the
  coverage gap before building**, because a feature that is NULL on a biased subset of laps
  is a leakage-shaped hazard, not just a sparse column.

**Leakage: RULED 2026-09-08 — barred as constructed.** See `02a` below. Values are
contemporaneous with lap *t* and the target spans *t+1…t+5*, so the construction is prima facie
safe — and it is not. The residuals are taken against a *"5-lap-bucket field median"* whose
bucket reaches into the target window.

---

### `02a` — the 5-lap field-median bucket · RULED 2026-09-08

**The item asked a binary — centred or backward-looking — and the SQL answers neither.**
`int_corner_skill_residuals` computes `FLOOR(CAST(cm.lap_number AS DOUBLE) / 5.0) * 5.0 AS
lap_window` and then `GROUP BY race_year, race_id, corner_name, lap_window`. That is a **fixed
block bucket**, not a window function: no `LEAD`, no `FOLLOWING` frame, no self-join inequality.
R5 flagged this shape and estimated the reach at "about two laps"; measured, it is **1.877**.

**Verified — the forward reach, measured over all 2,206,939 rows** by reconstructing the
`corners_with_keys` CTE from `int_corner_metrics` ⋈ `int_stint_geometry` (valid laps only) and
counting, for every focal lap, the rows in its own median group drawn from laps that had not yet
run:

| block position | mean forward reach | % of the median drawn from the future | mean own-driver future laps in own baseline | % of rows seeing their own future |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 3.739 laps | **76.00%** | 3.351 | **95.55%** |
| 1 | 2.814 | 56.44% | 2.558 | 95.00% |
| 2 | 1.909 | 40.00% | 1.751 | 92.04% |
| 3 | 0.968 | 20.67% | 0.907 | 90.67% |
| 4 | 0.000 | 0.00% | 0.000 | 0.00% |
| **all** | **1.877** | **38.45%** | — | — |

77.83% of lap-groups have some forward reach. Mean group size is ~70 rows.

**Method**, so the number is re-derivable rather than quoted. Run from `transform/` — `stg_laps`
and `stg_sector_times` are parquet-backed views with paths relative to it:

```sql
-- corners_with_keys, as the model builds it
CREATE OR REPLACE TEMP VIEW ck AS
SELECT cm.race_year, cm.race_id, cm.corner_name, cm.driver_id, cm.lap_number,
       cm.braking_point_m, FLOOR(CAST(cm.lap_number AS DOUBLE)/5.0)*5.0 AS lap_window
FROM int_corner_metrics cm
JOIN (SELECT race_year, race_id, driver_id, lap_number
      FROM int_stint_geometry WHERE is_valid_lap = TRUE) lk
  USING (race_year, race_id, driver_id, lap_number);

-- for every focal lap: rows in its own median group drawn from laps that had not yet run
WITH lapagg AS (
  SELECT race_year, race_id, corner_name, lap_window, lap_number,
         COUNT(*) FILTER (WHERE braking_point_m IS NOT NULL) AS n_lap
  FROM ck GROUP BY ALL),
gtot AS (
  SELECT race_year, race_id, corner_name, lap_window,
         SUM(n_lap) AS n_group, MAX(lap_number) AS max_lap
  FROM lapagg GROUP BY ALL),
reach AS (
  SELECT l.lap_number, g.n_group,
         g.max_lap - l.lap_number AS forward_reach_laps,
         g.n_group - SUM(l.n_lap) OVER (
           PARTITION BY l.race_year, l.race_id, l.corner_name, l.lap_window
           ORDER BY l.lap_number ROWS UNBOUNDED PRECEDING) AS n_future_rows
  FROM lapagg l JOIN gtot g USING (race_year, race_id, corner_name, lap_window))
SELECT lap_number % 5 AS block_pos,
       ROUND(AVG(forward_reach_laps), 3) AS mean_forward_reach_laps,
       ROUND(100.0*AVG(n_future_rows*1.0/n_group), 2) AS pct_from_future
FROM reach WHERE n_group >= 5 GROUP BY ALL ORDER BY 1;
```

The own-driver column is the same view self-joined on `(race_year, race_id, corner_name,
lap_window, driver_id)` with `b.lap_number > a.lap_number`. The materiality arms are the
`TRAILING` window given under `02g` below, aggregated to lap grain and joined to
`fct_cliff_prediction_features` on `lap_id`.

**The fact that decides it.** `DEGRADATION_TARGET` is `next_5_lap_cumulative_jump_s` — laps
*t+1…t+5*. Maximum forward reach is **4 laps**. So every future lap entering the median falls
*inside the label's own window*; the overlap is total containment, not partial. And it is not
only the field's future: at block position 0, **95.55% of rows are scored against a baseline
containing that driver's own future laps** — a mean of 3.351 of the 5 laps the label integrates.
The feature is not point-in-time correct.

**Verified — the contamination carries label signal, weakly.** Both arms were rebuilt from
identical source with identical formulae, differing only in the window: BLOCK (production, read
from the model's own table) and TRAILING (median over laps *t−5…t−1*, same race and corner, all
drivers, `n ≥ 5`). Aggregated to lap grain as §3 proposes (mean/sd across the lap's corners) and
joined to the real label on `is_training_eligible` rows (n = 80,381). Isolating the contamination
as `delta = BLOCK − TRAILING`, with block position 4 — zero forward reach — as the control:

| arm | n | corr(delta, label) | 95% CI (race-clustered bootstrap) |
| :--- | ---: | ---: | :--- |
| contaminated, positions 0–3 | 58,283 | **+0.0344** | [+0.0047, +0.0667] |
| control, position 4 | 15,055 | +0.0083 | [−0.0143, +0.0324] |
| paired difference | — | **+0.0261** | [−0.0008, +0.0531], one-sided *p* = 0.027 |

**Stated honestly: this half is suggestive, not decisive.** The contaminated arm's interval
excludes zero and the control's does not, and the paired difference is one-sided significant, but
its two-sided interval touches zero. The control is also imperfectly matched — at position 4 the
block and trailing windows overlap heavily, so its delta is a smaller contrast (sd 0.043 vs
0.116 at position 0). **The ruling does not rest on this table.** It rests on the row above it,
which is deterministic: the baseline contains the label's own laps, by construction, for 77.83%
of the data.

**The rebuild costs no signal.** Marginal |corr| with the label is equal or slightly *higher* for
the trailing arm at every block position (e.g. total-residual mean at position 0: −0.0666
trailing vs −0.0485 block). Contamination is behaving as noise on the baseline, not as a free
win — so nothing is lost by removing it, which is the cheap case.

**The rebuild's real cost is coverage, and it is concentrated and explainable.** Lap-grain
non-null falls 92.79% → 90.57% (−2.22pp), and the loss is almost entirely **lap 2** — the first
lap present in the table, which has no prior lap to build a backward median from:

| phase | non-null, block | non-null, trailing |
| :--- | ---: | ---: |
| lap ≤ 6 | 92.11% | **70.68%** |
| lap 7–11 | 92.61% | 91.59% |
| lap > 11 | 92.87% | 92.35% |

§3 warns that a feature NULL on a biased subset is "a leakage-shaped hazard, not just a sparse
column". This loss is deterministic on `lap_number` — an axis already in the contract via
`age_in_stint` — not correlated with the outcome, so the model can condition on it. It is
declarable, not hazardous. An expanding trailing window does not rescue lap 2 either; nothing
precedes it.

**Ruling.** **Barred as constructed.** `02c` must not ablate these columns as they stand. The fix
is the one R5 predicted — recompute the field median as a trailing window — and it is now `02g`,
which `02c` depends on instead of `02a`.

**Scope of the bar.** `mart_corner_skill_driver` consumes `braking_loss_s` /
`mid_corner_residual_s` / `exit_residual_s` today. That is a descriptive per-driver aggregate with
no forward label, so this is **not** leakage there and the mart is not barred. Its residuals are
still measured against a partly-future baseline, which is a measurement-consistency question
worth its own item — it is not this ruling.

**Confirms `08b`'s premise.** The reach lives in the scope of a `GROUP BY` and nowhere else, so
`audit_forward_window` sees nothing: no `LEAD`, no `FOLLOWING`, no self-join inequality. The
guard was clean on this model the whole time it was wrong.

Evidence: [`../research/R5-representation-and-transform.md`](../research/R5-representation-and-transform.md)
Part 2 for the shape; the measurements above are this item's, run against `data/dev.duckdb`.


### `02g` — rebuild the corner field median as a trailing window

**Created 2026-09-08 by `02a`'s ruling.** `02c` depends on this, not on `02a`.

**Objective.** Replace the `FLOOR(lap/5)*5` block bucket in `int_corner_skill_residuals` with a
backward-only field median, so the residual at lap *t* is measured against laps strictly before
*t*. Formulae, NULL rules and the `field_corner_sample_n < 5` gate stay exactly as they are; only
the window moves.

**The shape, already measured to work** (`02a`'s trailing arm):

```sql
quantile_cont(braking_point_m, 0.5) OVER (
  PARTITION BY race_year, race_id, corner_name
  ORDER BY lap_number RANGE BETWEEN 5 PRECEDING AND 1 PRECEDING)
```

`RANGE` (not `ROWS`) is load-bearing — it takes every driver's rows in the lap interval, which is
what makes it a *field* median rather than a per-driver one. `1 PRECEDING` excludes lap *t*
itself, which is what makes it backward-only.

**Two decisions this item must make and record, because `02a` did not.**

1. **Trailing-5 or expanding.** `02a` measured trailing-5 to keep the window width comparable to
   the block it replaces. An expanding window (all prior laps, `n ≥ 5`) is more stable late in a
   race but mixes early-race and late-race track states into one baseline, which is the same
   pooling defect `02d` is fixing in `int_sc_hazard_history`. Trailing-5 is the recommendation;
   whichever is chosen, record why.
2. **What to do about lap 2.** It has no predecessor and must go NULL — a 21.4pp coverage loss on
   laps ≤ 6, all of it that one lap. Declare it in `schema.yml` rather than back-filling it from
   the block median, which would reintroduce the leak on precisely the rows that cannot be built
   cleanly.

**R5's recommendation 2 applies here.** `02d` needs the same pattern for
`int_sc_hazard_history`. Write it once as a dbt macro (`{{ trailing_median(...) }}`) so the
second instance is a call, and so `08b`'s auditor has one shape to whitelist rather than two to
discover.

**Definition of done.** `int_corner_skill_residuals` uses a backward-only median; a test asserts
no row's baseline draws on `lap_number >= ` its own; the lap-2 NULL rule is declared in
`schema.yml` with the coverage figure; `mart_corner_skill_driver` is re-run and the change to its
outputs is reported, not assumed to be nil; `model_hashes.baseline.json` re-snapshotted.

**Cost:** ~0.5–1 day. The window is a two-line change; the test, the schema note and re-reading
the mart are the rest.

**Three defects found in `02g` when `02c` picked it up, 2026-09-11.** Recorded here rather than
silently repaired, because two of them were invisible to the checks `02g` reported passing.

1. **The rebuild fanned the model out 17.4×.** The block bucket collapsed `field_medians` with a
   `GROUP BY`; the window functions that replaced it do not. `corners_with_keys` is at *driver*
   grain, so every `(race, corner, lap)` emitted one copy of its medians per driver on track, and
   the `LEFT JOIN` back onto `(race_year, race_id, corner_name, lap_number)` multiplied the table
   by the field size: **2,206,939 → 38,444,069 rows**, against a `corner_id` that `schema.yml`
   declares `unique`. Every duplicate carried identical values — verified, zero `corner_id`s with
   more than one distinct value of any median — so no `MEAN` or `MEDIAN` downstream moved and
   nothing looked wrong. What moved were the `COUNT`s: `mart_corner_skill_driver`'s
   `HAVING COUNT(*) >= 100` admission floor and its `PHASE_MIN_CELLS = 30` gate were both being
   cleared ~17× too easily, and its LORO baseline `(sum − focal)/(n − n_focal)` silently became
   field-size weighted rather than unweighted. Fixed by a `QUALIFY ROW_NUMBER() ... = 1` on
   `(race_year, race_id, corner_name, lap_number)`. The dedupe is value-preserving rather than a
   choice of representative: the `RANGE` frame orders by `lap_number`, so every driver row at the
   same lap is a peer and sees an identical frame. `ROWS` would not have this property, which is a
   second reason `frame='range'` is load-bearing.
2. **`field_corner_sample_n` was floored to NULL below 5**, which contradicted its own `not_null`
   test in the same `schema.yml` block (416,639 failing rows) and destroyed the only thing the
   companion column is for — it made "no prior lap at all" and "four prior laps, one short of the
   gate" indistinguishable, so the residual NULLs became unexplainable from the data. The
   `trailing_observation_count` macro's docstring is explicit that the count "is reported
   unfloored". Now unfloored and never NULL; the residuals still NULL out through
   `trailing_median`'s own `min_observations=5`.
3. **`model_hashes.baseline.json` was re-snapshotted against `data/dev.duckdb`.** The byte-stability
   oracle is defined over `data/ci.duckdb` built with `--target ci` and the committed fixtures;
   `snapshot_model_hashes.py`'s own default is `ci.duckdb`. The committed baseline was replaced
   with dev-warehouse hashes for every model, which fails CI Gate 1c on all seven mandatory `fct_*`
   marts. Needs regenerating from a CI build.

**How they got through.** `02g` reported "test passes" on the strength of one singular test. Neither
`dbt test` nor `dbt build` was run on the model, so the `unique` and `not_null` generic tests — which
name defects 1 and 2 directly, and which is where they were found — never executed. This is the
same shape as `08b`'s finding one level down: the guard existed and was correct, and nobody pointed
it at the model.

---

### `02c` — Tier 2, corner-level driver inputs · BUILT 2026-09-11, ARMS RUN 2026-09-11

**What was built.**

* `int_lap_corner_inputs` (new, lap grain, 134,948 rows) rolls `int_corner_skill_residuals` up from
  (lap × corner) to lap grain: mean / sd / max of each of the three phase residuals, plus coverage.
* `fct_cliff_prediction_features` carries the ten resulting columns. They are **in the mart and not
  in `ml/src/schema.py`'s `FEATURE_COLUMNS`** — the same standing `proximity` had between Phase 10's
  build and its ablation. The contract moves only if the arms below say it should.
* Tests: `assert_corner_inputs_lap_grain_closure` (ties the lap aggregate back to the corner grain;
  would have caught the 17.4× fan-out) and a rewritten
  `assert_corner_trailing_window_no_forward_reach`.

**Each phase is aggregated over the corners where THAT phase is measurable**, not over the
intersection of all three. Corner-grain availability, re-measured on the shipped table 2026-09-11
over all 2,206,939 rows, is braking **69.94%**, mid-corner **81.12%**, exit **47.00%** — 18.88% of
corner rows are unmapped outright (`field_corner_sample_n < 5` under the trailing window), and among
the mapped rows the three run 86.21% / 100% / 57.94%. `braking_point_m` is NULL where a corner is
taken flat and `throttle_point_m` is NULL where the driver never reaches full throttle before the
next apex — both real answers about a corner, not missing data. `corner_residual_total_s` is exactly
that intersection and is non-null on only 38.59% of corner rows, which is why it is not used.
*(This paragraph first read "mid-corner 97.6%, exit 60.9%". Those two do not reproduce against the
table; see the corrections note at the end of this item.)*

**The corner-type split: considered, declined for the primary arm, recorded so it is not
re-derived.** §3 suggests splitting by corner type via `dim_corners`. Two grounds. (1) The only
within-warehouse measure of corner speed is apex speed, and a per-(race, corner) speed class pooled
over the race reaches forward into the label window — *the exact defect `02a` ruled on in this same
model*. A point-in-time classifier would have to be trailing, which makes a corner's type vary lap
to lap, which is not what a corner-type split means. (2) `dim_corners` carries only geometry (apex
distance, neighbour spacing), a weak proxy for how a corner loads a tyre. It stays available as arm
D below, conditional on the primary clearing.

**Verified — the coverage gap, counted before building as §3 requires.** Measured on the rebuilt
mart's 121,193 training-eligible rows:

| column | non-null on training-eligible rows |
| :--- | ---: |
| `corner_mid_residual_mean_s` | 96.03% |
| `corner_braking_loss_mean_s` | 95.85% |
| `corner_exit_residual_mean_s` | 89.85% |

**And the gap is NOT a random subset — this is the item's main finding so far.** §3 warned that a
feature NULL on a biased subset is "a leakage-shaped hazard, not just a sparse column". It is
biased, and measurably:

| rows | n | mean `next_5_lap_cumulative_jump_s` | sd |
| :--- | ---: | ---: | ---: |
| `corner_braking_loss_mean_s` present | 78,787 | **−2.3295** | 5.9377 |
| `corner_braking_loss_mean_s` NULL | 3,683 | **+1.3926** | 10.1960 |

The missing rows degrade worse and are far more variable. **It is not forward leakage** — a lap is
uncovered because its own telemetry is absent, or because the trailing baseline over *t−5…t−1* held
fewer than five valid observations, and both are settled strictly before *t+1*. But a model handed
these columns as bare NaNs is free to split on "corner inputs missing" and score a win that has
nothing to do with driver inputs.

**So coverage is admitted as its own column and ablated separately.** `corner_input_coverage`
(mapped corners / measured corners, mean 0.799 over the mart's training-eligible rows) is in the
group. Its marginal correlation with the label is **−0.0904**, which is larger in magnitude than
`corner_braking_loss_mean_s` (+0.0627) and than the three sd columns (−0.030 to −0.058) — **but not
larger than every residual aggregate, as this paragraph originally claimed**: the full set was
re-measured 2026-09-11 and `corner_mid_residual_max_s` is −0.1635 and `corner_mid_residual_mean_s`
−0.1556. The worry the arm was built on still stands — **a naive nine-column arm could have cleared
on the coverage channel and been read as the driver-input mechanism**, and the permutation-null arm
does *not* catch that on its own, because row-shuffling moves the NaNs with the values, so a
missingness-driven win is destroyed by the shuffle and reports as "information". Arm C exists to
prevent that reading, and on p90 it is exactly what happened. See the results below.

**Verified — both leakage audits are clean on the new lineage.** `02c` is the event
`ml/src/features.py::survey_aggregation_scope` was written to anticipate: wiring this model into a
feature moves it from the report-only survey into `audit_aggregation_scope`'s scope. Both audits
return CLEAN. `int_corner_skill_residuals` has no non-pinning `GROUP BY` left after `02g`, and
`int_lap_corner_inputs` groups on `lap_id`, which pins one lap. `ml/tests/test_features.py`'s
advance-notice test has been split accordingly — one half still holds `02d`'s instance under
notice, the other asserts the corner instance left the survey *by being fixed and entering the
lineage*, not merely by dropping out of a walk.

#### Pre-registered arms — written before any arm is run (gates.md step 6)

Baseline is the shipped 32-column contract on `cv_final_fold`, train 2018–2023, eval 2024, using
`evaluate.py`'s own `_fit`/`_score`. Families: `degradation_regressor` p10/p50/p90,
`cliff_classifier`, `stint_life_regressor`. Each delta is judged against **that family's own**
5-reseed floor `2*sqrt(2)*sd` from `attribution.py::refit_noise_floor`, seeds
`RANDOM_STATE + 0…4` = 20260528…20260532.

| arm | columns added | what it tests |
| :--- | ---: | :--- |
| **A — full** | 10 | The group as designed: nine residual aggregates + `corner_input_coverage`. |
| **B — residuals only** | 9 | Arm A minus `corner_input_coverage`. Isolates the driver-input channel from the coverage channel. |
| **C — coverage only** | 1 | `corner_input_coverage` alone. **The confound control.** If C ≈ A, the group is a track-state/telemetry-availability proxy and the driver-input mechanism is unsupported. |
| **P — permutation null** | 10 | Arm A's columns row-shuffled in train *and* eval. Capacity = shuffled − baseline; information = real − shuffled, reported separately (gates.md step 4). |
| **D — corner-type split** | TBD | **Conditional.** Runs only if B clears. Declared now so that running it later is not a new selection; if B does not clear, D is not run and is not counted. **Unlocked 2026-09-11 — B cleared on p10, p50 and cliff. Still unrun, so still uncounted.** |

**Primary hypothesis:** arm B clears its floor on at least one of the three degradation quantiles.
Tier 2 is the only lap-varying candidate in this document, so it is the only one that can address
the 99.06% within-stint variance — a Tier 2 that moves only `cliff_classifier` has not done the
thing it was admitted to attempt.

**Declared in advance as the reading of each outcome**, so no result can be reinterpreted after the
fact:

* **B clears, C does not** → the driver-input mechanism is supported. This is the only outcome that
  admits the group on its stated grounds.
* **C clears, B does not** → the channel is telemetry availability, not driver inputs. Do not ship
  as Tier 2; raise coverage as a separate candidate on its own merits, with its own registration.
* **A clears but neither B nor C does** → ambiguous, recorded as ambiguous. This is Phase 10a's
  p50 outcome and it is not rounded up.
* **Nothing clears** → Tier 2 is closed, and with it the last lap-varying candidate in item 02.
  That is a substantive result about the degradation ceiling, not a null to bury: it would say the
  remaining within-stint variance is not reachable from the corner channel.

**One sequencing constraint, inherited from `10d`.** `02b`'s note bars measuring
`stint_life_regressor`'s 5-reseed floor until `10e` resolves — `10d` showed the shipped booster was
tuned under the wrong label, on the mixture NLL, with 2024 in the validation folds. That bar applies
here unchanged. **Arms A–C may be run now on the degradation trio and the cliff classifier; the
stint-life column of every arm must wait for `10e`.** Running it now measures against a model that
is about to change.

#### E-value pre-registration — `02c`

```
H0                : the ten 02c columns carry no information (real vs row-shuffled, gates.md step 4)
Statistic         : per family — p10/p50/p90 pinball, cliff macro-F1, AFT NLL;
                    cv_final_fold, train 2018-2023, eval 2024
Delta orientation : delta = score(shuffled) - score(real) for losses (pinball, NLL);
                    delta = score(real) - score(shuffled) for macro-F1. Positive = improvement.
Construction      : B (paired safe-t), the reference's default. Chosen over A because no prior
                    separate reseed study of this substrate exists at the 32-column contract, so
                    A's scale would be a plug-in from the same five seeds it scores -- the hole
                    §3 of the reference names. B is exact for any unknown sigma.
Seeds             : 20260528, 20260529, 20260530, 20260531, 20260532  (RANDOM_STATE + 0..4,
                    the same five as the floor study)
Parameters        : n = 5, g = 1  (a one-sd effect; the reference's default, no better number
                    is available for this channel)
Formula           : E = (1 + 5g)^(-1/2) * [ (1 + t^2/4) / (1 + t^2/((1+5g)*4)) ]^(5/2),
                    t = sqrt(5) * d_bar / s_d     ->  at g = 1:
                    E = 6^(-1/2) * [ (1 + t^2/4) / (1 + t^2/24) ]^(5/2)
Declared alt      : delta* = the family's own floor 2*sqrt(2)*sd. The floor is the smallest
                    effect the programme has ever shipped on, so it is the smallest one worth
                    shipping here.
Family            : every arm declared above is counted in the campaign family whatever E comes
                    out as, E < 1 included. Arm D is conditional and is counted only if run.
                    Campaign-level decision is e-BH per 04c, not per-arm.
Validity check    : before trusting the implementation, push 100k draws of five i.i.d. N(0, sigma)
                    deltas through it at several sigma and confirm mean(E) = 1.00 to Monte Carlo
                    error. Required by the reference; costs a minute.
```

#### Arms run 2026-09-11 — results

**Command, artefact, log.** `python scripts/arms_02c_corner_inputs.py` →
`ml/artefacts/02c_corner_inputs_arms.json` (every fit's headline, per seed) and
`ml/artefacts/02c_corner_inputs_arms.log`. Nothing below was computed by hand.

**Step 1 first, and it passed on all four families.** The 32-column refit reproduces the published
v11 headline to ten decimal places, not six: p10 0.5320213274, p50 1.0467899119, p90 0.5785136178,
cliff macro-F1 0.3718655272. That is a result in its own right — `02g` rewrote
`int_corner_skill_residuals` and `02c` added ten columns to the mart, and the incumbent feature
matrix did not move by a float.

**The arms.** Positive = improvement on every metric. `x floor` is against **that family's own**
5-reseed floor (`2*sqrt(2)*sd`, seeds 20260528…20260532): p10 0.004311, p50 0.010431, p90 0.009347,
cliff 0.005772. `capacity` = shuffled − baseline and `info` = real − shuffled, per gates.md step 4.

| family | arm | delta | ×floor | clears | capacity | info | info ×floor | E |
| :--- | :--- | ---: | ---: | :---: | ---: | ---: | ---: | ---: |
| p10 | A — full (10) | +0.001926 | 0.45 | no | −0.003621 | +0.005547 | 1.29 | 27.2 |
| p10 | **B — residuals (9)** | +0.005585 | **1.30** | **yes** | −0.005597 | +0.011183 | **2.59** | 13.0 |
| p10 | C — coverage (1) | +0.003004 | 0.70 | no | +0.002094 | +0.000910 | 0.21 | 4.53 |
| p50 | A — full | +0.014205 | **1.36** | **yes** | +0.000041 | +0.014165 | **1.36** | 22.7 |
| p50 | **B — residuals** | +0.016971 | **1.63** | **yes** | −0.003894 | +0.020865 | **2.00** | **34.0** |
| p50 | C — coverage | +0.012785 | **1.23** | **yes** | +0.002208 | +0.010577 | **1.01** | 18.8 |
| p90 | A — full | +0.015457 | **1.65** | **yes** | +0.008475 | +0.006982 | 0.75 | 7.41 |
| p90 | B — residuals | +0.004619 | 0.49 | no | +0.006182 | **−0.001563** | −0.17 | 0.628 |
| p90 | **C — coverage** | +0.024241 | **2.59** | **yes** | +0.001442 | +0.022800 | **2.44** | 9.13 |
| cliff | A — full | +0.014940 | **2.59** | **yes** | +0.003955 | +0.010986 | **1.90** | 29.3 |
| cliff | **B — residuals** | +0.012536 | **2.17** | **yes** | +0.000799 | +0.011737 | **2.03** | 19.3 |
| cliff | C — coverage | +0.006295 | **1.09** | **yes** | +0.002520 | +0.003775 | 0.65 | 21.3 |

**The primary hypothesis holds.** It was: *arm B clears its floor on at least one of the three
degradation quantiles.* B clears on **two** — p10 at 1.30× and p50 at 1.63× — and on both the
permutation arm attributes the whole of it to information (2.59× and 2.00× floor) with a *negative*
capacity term, i.e. the nine columns as noise make the model slightly worse and only help when they
carry their real values. Tier 2 was admitted as the only lap-varying candidate, the only one that
could reach the 99.06% within-stint variance; it reached it.

**Applying the declared readings, one family at a time, including where they run out.**

* **p10 — "B clears, C does not."** The declared reading is *the driver-input mechanism is
  supported*, and it is the only outcome that admits the group on its stated grounds. p10 is that
  outcome exactly.
* **p90 — "C clears, B does not."** The declared reading is *the channel is telemetry availability,
  not driver inputs*. Taken at its word here: B's information delta is **negative** (−0.17× floor)
  while C's is +2.44×. On the p90 quantile the corner channel is a coverage channel.
* **p50 and cliff — both B and C clear. This outcome was not declared.** Recorded as an
  undeclared cell rather than assimilated to the nearest declared one, because the reading table was
  built on the assumption that B and C were competing explanations and they are not: on p50 B's
  information is 2.00× floor and C's is 1.01×, on cliff 2.03× and 0.65×, and both are positive in
  the same fit. The honest reading is the additive one — the driver-input channel and the
  coverage channel each carry information, on different rows.
* **Arm A is not the sum of its halves, and on p90 it is the Phase 10a shape.** A clears on p50,
  p90 and cliff but not p10, and on p90 its gain splits +0.91× capacity / +0.75× information with
  neither half clearing alone — the pattern gates.md step 4 exists to catch. A is also *worse than
  B* on p10 and p50: adding `corner_input_coverage` to the nine residuals costs signal there.

**The confound arm earned its place.** `02c` built arm C on the argument that a naive nine-column
arm might clear on telemetry availability and be read as driver inputs. That worry was justified on
p90, where exactly that happens — and the permutation arm alone would not have caught it, because
shuffling moves the NaNs with the values. C is also the arm that shows the cost of *not* separating
them: on p10, C alone does not clear and dilutes B when bundled with it.

**Negative control, run because a pipeline can produce evidence out of nothing.** A fifth set of
fits per family scores shuffle against a *second independent shuffle* of the same ten columns — H0
true by construction. E came back 0.451 / 0.539 / 0.581 / 0.470 on p10 / p50 / p90 / cliff, all
below 1, with mean deltas at or under a tenth of the floor. The instrument returns nothing when
there is nothing.

#### The e-values, and the thing they say that the floor ratios do not

The declared Construction B was implemented as pre-registered and checked before use: 100k draws of
five i.i.d. `N(0, sigma)` deltas return mean `E` = 1.0016 / 0.9992 / 1.0108 / 1.0014 at sigma =
0.001 / 0.01 / 0.1 / 1.0, each within Monte Carlo error of 1.00, and the reference's §4 worked
example reproduces at `E = 17.0` to three figures.

**e-BH rejects nothing, and it is structurally unable to reject anything here.** Sorted descending
the twelve E-values run 34.0, 29.3, 27.2, 22.7, 21.3, 19.3, 18.8, 13.0, 9.13, 7.41, 4.53, 0.628. At
α = 0.05 and n = 12, `k*` = max{k : E_[k] ≥ 12/(0.05k)} — that is 240 for a lone rejection, 120 for
two, 20 even if all twelve rejected together. **k\* = 0.**

**Why that was decided before any arm ran, not by the data.** The safe-t statistic at n = 5, g = 1
is bounded: as `t → ∞` it converges to `(1 + ng)^((n-1)/2)` = **36**. So the pre-registered
construction could never have produced a lone rejection in a family of 12 — the ceiling is 36 and
the threshold is 240 — and p50's arm B at E = 34.0 is not a near miss but a number pressed against
the cap. **This is a defect in the pre-registration, found by executing it, and it is recorded here
rather than repaired after the fact:** more seeds (n = 10 lifts the cap to 11^4.5 ≈ 4.6×10⁴) or a
larger `g` would have bought the headroom, and neither may be chosen now that the deltas are known.
Any future item declaring Construction B should price the cap against the family size it expects.

The two instruments therefore disagree in public, which is what gates.md's closing paragraph says
to do: **step 3 says B cleared on p10, p50 and cliff; step 7 says that is not yet worth a
campaign-level rejection.** Neither number is the other's correction.

**Family accounting.** Twelve declared hypotheses are counted (A/B/C × four families), every one
reported including p90's `E = 0.628`. The pre-registration's Family line can also be read to count
arm P per family, which would make n = 16; `k*` is 0 either way, and the ambiguity is flagged so a
later reader does not have to guess which convention the campaign used. The stint-life column of
every arm is still **unrun and barred** (below), so the 02c family will grow by three when `10e`
resolves — legitimate under stopped e-BH, which is anytime-valid, and the reason that property was
chosen in the first place.

#### What this item does and does not conclude

* **Verified.** The nine residual aggregates carry information the 32-column contract does not
  have, on p10, p50 and the cliff classifier, with the permutation arm attributing it to
  information and not capacity.
* **Verified.** `corner_input_coverage` is a separate channel that also carries information, and on
  p90 it is the only one of the two that does.
* **Not done here, and deliberately.** The contract is unchanged: the ten columns are in the mart
  and still absent from `ml/src/schema.py`'s `FEATURE_COLUMNS`. Moving it is a version bump with a
  retrain, artefact rebuild, ONNX export and model card behind it — `08k`'s shape, not this item's —
  and the arms above do not settle *which* set to move, since A is not uniformly better than B.
* **Follow-ons, named so they are scheduled rather than assumed.** (1) Ship arm B's nine columns as
  its own item, with the coverage question answered separately; per the declared reading for a
  clearing C, coverage gets **its own registration** rather than riding in on this one. (2) Arm D
  (corner-type split) is now unlocked — it was conditional on B clearing and B cleared — and it
  stays unrun and uncounted until it is. (3) The stint-life arms when `10e` lands.

**One sequencing constraint honoured.** The runner refuses `stint_life_regressor` outright rather
than leaving the bar to a reader's memory: `10d` showed the shipped booster was tuned under the
wrong label, on the mixture NLL, with 2024 in the validation folds, so a floor measured now is
measured against a model about to change.

#### Two figures in this section's build notes were wrong, and are corrected

Both were found by re-measuring against the shipped table while writing the results up.

1. **Corner-grain availability.** The build note said braking 69.9%, mid-corner 97.6%, exit 60.9%.
   Measured over all 2,206,939 rows of the rebuilt `int_corner_skill_residuals`: braking **69.94%**,
   mid-corner **81.12%**, exit **47.00%**, intersection (`corner_residual_total_s`) **38.59%**.
   Braking and the intersection reproduce; mid-corner and exit do not. 18.88% of corner rows are
   unmapped outright — `field_corner_sample_n < 5` under the trailing window, which the block bucket
   used to hide — and among the mapped rows the three phases run 86.21% / 100% / 57.94%. The
   aggregation decision is unaffected (intersecting still throws away most of the channel), but the
   exit phase is sparser than the note claimed. Corrected in `int_lap_corner_inputs.sql` and both
   `schema.yml` files.
2. **The marginal-correlation claim.** The note said `corner_input_coverage`'s |corr| with the label
   (0.0904) is *"larger in magnitude than any of the nine residual aggregates"*. It is not:
   `corner_mid_residual_max_s` is **−0.1635** and `corner_mid_residual_mean_s` **−0.1556**, both
   larger. The three sd columns (−0.030 to −0.058) and `corner_braking_loss_mean_s` (+0.0627) were
   quoted correctly; the mid-corner pair was not checked. The arms make the correction moot in the
   direction that matters — B beats C on three of four families — but the sentence as written
   overstated the confound and understated the channel.

**Cost:** ~2–3 days, most of it in the aggregation design and the leakage check. **Spent.** The
build, the audits, the twelve arms, the four negative controls and the e-values are done; what
remains of the pre-registered family is the stint-life column, barred until `10e`.

---

## 4. Tier 3 — The marshalling channel, and a correction to the research program

**What exists:** `int_sc_hazard_history` (36 circuits) with `sc_hazard_per_lap`,
`vsc_hazard_per_lap`, `any_hazard_per_lap` and shrunk variants of each; plus
`stg_track_status` and `stg_race_control`, neither read by the contract.

**This falsifies a load-bearing sentence in `ml_research_program.md` §1a.** That section
explains why the last 28% of stint-life headroom is probably unreachable:

> *"Remaining stint life is set partly by pit-wall strategy calls and safety-car timing —
> events that are not a tyre-degradation question at all and carry no signal in any feature
> this warehouse could build."*

The clause after the dash is false. A per-circuit safety-car hazard *per racing lap*, already
empirical-Bayes shrunk, is exactly that signal, and it has been in the warehouse the whole
time. §1a marks the paragraph "Inference, not measurement", so this is a correction to an
Assumed claim rather than to a Verified one — but it is the kind of claim that hardens into
received wisdom if left standing, and it is currently the stated reason for capping the
stint-life target at 0.80–0.85 of attainable.

**Why it should matter for stint life specifically.** Stint life is right-censored on 46.2%
of training rows, and stint ends are set by pit-wall decisions. Safety-car probability is the
largest exogenous input to those decisions. This is the one target where a circuit-constant
feature is not obviously capped by §1's within-stint argument, because the target is not
shaped like the degradation column.

**Leakage: needs an expanding window.** `int_sc_hazard_history` is a pooled historical rate
over every race with an ingested track-status timeline. Used as-is it puts 2024 races into
the hazard estimate a 2018 row sees. **Rebuild it as an expanding, season-lagged rate** —
hazard as of the start of season *S*, using seasons < *S* only — or it is a textbook temporal
leak with a plausible-looking gain attached.

**Coverage caveat:** the model's own header says track-status ingestion is *"incomplete for
some seasons"*. Establish which seasons before trusting a per-circuit rate.

**Cost:** ~1 day, most of it in the expanding-window rebuild.

---

## 5. Tier 4 — cheap, low expected value, recorded so they are not re-derived

* **`int_track_evolution`** (6,729 rows, race × lap): `track_state_index_s`,
  `rubber_component_s`, `track_temp_c`, `humidity_pct`, `rainfall_flag`. Lap-varying, which
  puts it above the rest of this tier. Note the weather closure (below) does **not** cover
  it: air density was closed as near-constant per circuit; track rubbering is a genuine
  within-race process on a different mechanism.
* **`int_sector_residual_decomposed`** (412,341 rows): `sector_consistency_index` has a
  tyre-management story. But sector times are another transform of lap times, which is the
  exact category Phase 9 dropped five groups from. Low prior.
* **`fct_telemetry_deltas`** (24,501,520 rows): pairwise driver corner deltas. The grain is
  a driver *pair*, which does not join to a lap-level feature matrix without an aggregation
  choice that is not obvious. Large, and probably not worth it before Tier 2 is settled.

**Barred, not merely unpromising — do not propose these:**

* **`int_synthetic_teammate`** (119,698 lap-level rows). Its headline column is
  `driver_skill_proxy_s`, and `driver_skill_proxy_s` is an explicit member of
  `EXCLUDED_LEAKAGE_COLUMNS` in `ml/src/schema.py`, listed under "causal leakage". The table
  is useful analysis; it is closed as a feature source.
* **`int_driver_race_skill_loro`** (2,825 rows) is the one genuine ambiguity. Its
  `driver_skill_loro_s` is leave-one-race-out, which is the correct anti-leakage construction
  and is precisely what makes a skill term admissible in principle. But the leakage list bars
  `driver_skill_residual_s` and relatives without carving out a LORO exception. **This needs a
  ruling, not an assumption.** Someone should decide explicitly whether LORO construction
  lifts the bar, and write the decision into `schema.py` beside the list. Until then, treat
  it as barred.

---

## 6. Dead ends, with reasons, so they stay closed

* **`stg_tyre_allocations` / `tyre_allocations` are EMPTY — 0 rows.** The staging model and
  its columns (`allocated_sets_per_driver`, `compound_code`, `circuit_key`) exist; nothing
  populates them. How many fresh sets of each compound a driver still has is a genuinely
  strong strategy signal and it is not derivable from anything else in the warehouse. **This
  is an ingestion gap, not a modelling one**, and it is the single clearest "new data source"
  still open now that §4 has closed FP. Raise it against ingestion, not against the ML
  contract.
* **Weather / air density.** Closed 2026-08-23 as a *measured negative*, not as unrealised
  value: built properly off bronze `pressure_hpa`, they move p50 RMSE −0.33% and cliff
  macro-F1 +0.70%, both inside harness noise, because air density is near a per-circuit
  constant and circuit identity already enters the set three times over. **Do not re-open.**
* **`int_lap_telemetry_aggregates` as previously aggregated.** Dropped Phase 9 with the
  `powertrain` and `telemetry_cliff` groups. The sensor was vindicated by Phase 10a; the
  aggregation was not. Re-approach only via a new construct (Tier 2), never by restoring the
  dropped columns.

---

## 7. The gate every candidate must pass

Unchanged from the standing protocol, restated so this document is executable without
re-reading `ml_execution_plan.md`:

1. **Instrument check first.** The N-column refit must reproduce the published v11 headline
   to six decimals before anything built on top of it is trusted. Phase 10b did this and it
   is what makes its numbers comparable.
2. **Add-ablation** on the identical `cv_final_fold` split (train 2018–2023, eval 2024),
   using `evaluate.py`'s own `_fit`/`_score`, not a reimplementation.
3. **Delta against that family's own 5-reseed floor** — `2*sqrt(2)*sd` from
   `ml/src/attribution.py::refit_noise_floor`. Never against a floor computed under the
   paired-t protocol in `intervals.py`; they are not interchangeable.
4. **Permutation-null arm.** Row-shuffle the new columns in train and eval so capacity is
   preserved and signal destroyed, then report capacity and information separately. Phase 10a
   found a group whose total cleared while neither half did; without this arm that would have
   shipped as a clean win.
5. **Forward-window audit** for anything label-adjacent, and the leakage checks named per
   tier above.
6. **Pre-register the arms before running them.** `ml_research_program.md` §5 documents an
   uncorrected multiplicity problem across 22 checkpoints. Adding four more tiers of tests
   without pre-registration makes that problem worse, and pre-registration costs nothing.

---

## 8. Recommended order

1. ~~**Tier 2 leakage check** (hours).~~ **Done 2026-09-08 — and it reached forward.** The
   bucket is a fixed `FLOOR(lap/5)*5` block; mean forward reach 1.877 laps, entirely inside the
   label's own *t+1…t+5* window, with the driver's own future laps in their own baseline on
   95.55% of block-position-0 rows. Barred as constructed. Per this list's own contingency, that
   changes the ordering: **`02g` (the trailing-window rebuild) now comes before Tier 2's
   ablation**, and `02c` depends on it. See §3.
2. **Tier 1, qualifying** (~1 day). Cleanest join in the document, zero leakage treatment,
   and it tests §4's "no remaining data source" conclusion directly. Expect cliff and stint
   life to move, not the trio.
3. ~~**Tier 2, corner inputs** (~2–3 days).~~ **Arms run 2026-09-11 — and it reached the trio.**
   The nine residual aggregates clear their family floor on p10 (1.30×), p50 (1.63×) and the cliff
   classifier (2.17×), with the permutation arm attributing the gain to information rather than
   capacity in all three. Coverage is a genuinely separate channel and is the only one of the two
   that clears on p90. Nothing survives campaign-level e-BH, which the pre-registered construction
   made impossible before the first fit — see §3 `02c`'s results. The contract has **not** moved;
   the ten columns are still mart-only. Remaining: the stint-life arms (barred until `10e`), arm D
   (now unlocked), and a shipping item for arm B's nine columns.
4. **Tier 3, SC hazard** (~1 day), with the expanding-window rebuild, aimed at stint life —
   and at §1a's capping assumption.
5. **Raise `tyre_allocations` as an ingestion item**, separately from all of the above.

---

## 9. What this document is not

* **Not a record of work done.** Nothing has been built, joined, ablated or shipped. Every
  number is a row count or a column list read from `data/dev.duckdb` on 2026-09-07,
  or a figure quoted from an existing artefact with its source named.
* **Not a claim that any candidate works.** No candidate here has been through the gate in
  §7. The document's claim is narrower: these are different channels, the admission rule has
  never been pointed at them, and three of them are one join away.
* **Not a reopening of anything closed.** FP1/2/3 (§4 of the research program), weather/air
  density, and the Phase 9 telemetry aggregates stay closed. §2 argues that §4's *conclusion*
  over-generalised to qualifying; it does not argue that §4 was wrong about FP.
* **Not independent of `ml_research_program.md` §3.** If the ceiling work lands and shows the
  degradation trio near a trustworthy empirical floor, Tier 2 is noise-chasing and this whole
  document reduces to Tier 1 and Tier 3. **§3 still prices this.**
