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
>
> **`02d` was concluded 2026-09-21 and `02c` was re-run 2026-09-22 — see their Verdicts.** A third
> substrate has landed since the paragraph above was written: **`v13` (`e341152`, 2026-09-21)**
> bundles `02b`, `08o` and `08q`. `08q` moves the **label** again (`theta_air` 0.5 → 0.1310 s/lap),
> `08o` drops the IPW sample weight from the three quantile heads, and `02b` admits seven
> qualifying columns to `cliff_classifier` **only** — so the feature contract is no longer one
> width (39 for the classifier, 32 for everything else, via `schema.feature_columns_for()`). The
> floors moved a *second* time: `02c`'s 2026-09-22 re-run measured p10 at **0.00593**, which is
> **4.33×** the 2026-09-19 figure quoted just above. **Any floor in this document is a reading on a
> named substrate, never a constant to reuse** — measure it in the same process that measures the
> delta.
>
> **`02h` ran and closed 2026-09-22 on that same `v13` substrate — see its Verdict.** It
> re-measured all four floors independently and reproduced `02c`'s to **8 dp**, which is the
> cross-check that makes the two items' ratios directly comparable. Its own result is negative:
> drift against the driver's early-stint baseline is **less** persistent than `02c`'s pace
> residuals (0.0169–0.1397 against 0.0267–0.1756), and its mechanism arms clear nothing on any
> family. Tier 2's scalar-aggregation line is finished; R5 Option A/B is what remains.

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

> **Superseded by §11 — `09c` landed 2026-09-19, after this paragraph was written.** "Stays
> open until `09c` lands" is no longer the correct state: `09c` landed the same day and ruled
> non-retroactively, so the ceiling does not move for `02b`'s arms at all, ever. See §11 for
> the corrected ruling.

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

**`MEASURED` as of this Verdict; superseded by §11 below (2026-09-19, same day, after `09c`
landed).** Gates 1–5 run and passed; gate 6 satisfied for the original family on 2026-09-14 and
for the stint-life follow-on before it ran; gate 7 declared and reported but **structurally
unable to reject** until `09c` raises the e-value ceiling.

What a later session may quote from this item: the gate-3 floor ratios, on the post-`08m`
substrate, as measured above. What it may **not** quote: any 2026-09-14 delta, and §1's
`between_stint_share = 0.0094` as a live constraint.

Recommended next, none of it done here: (i) `09c`, which gates whether any of this survives
campaign-level correction; (ii) a decision on admitting B and C to `FEATURE_COLUMNS` for
`cliff_classifier` — the contract is unmoved at 32 and this item does not move it; (iii) §1's
tier table re-derived against 0.0643, since three tiers were sized against 0.0094.

#### 11. Ruling — `GATED`, addendum written 2026-09-19 after `09c` landed

`09c` closed the same day as this Verdict, after §6/§10 above were written against it as an
open dependency. Two things §6/§10 left as "pending `09c`" are now resolved, and the ruling
follows from `09c`'s own text plus `gates.md`'s own text, not from re-scoring anything.

**(a) The ceiling does not move for `02b`'s arms — not later, not ever, under this
construction.** `09c`'s landing note (`work/09-scoring-instruments.md`, `build-log.json`
`09c`) is explicit: *"NOT RETROACTIVE: every `E` already declared under `n=5,g=1` (`02b`,
`02c`, `08e`, ... `10e`, `11a`, `11b`, `07`) stands as declared; `n=10,g=1` applies only to
arms pre-registered after this landing."* `02b`'s sixteen original arms were declared
2026-09-14 and the four stint-life arms were declared 2026-09-19 *before that day's arm ran*
— both before `09c` landed. Re-running any of them at `n=10,g=1` to chase a clearer e-BH read
is barred by `09c`'s own ruling and is not done here. **§6's "until `09c` raises the e-value
ceiling" was written as if the ceiling might later rise for this item. It does not. Gate 7
returns a permanent, structural non-rejection for every one of `02b`'s twenty arms.**

**(b) The true campaign family (103, not 20) does not change the outcome — it can only make
it more true.** §6 sized its own threshold from `02b`'s 20 declared hypotheses alone
(`20 × 20 = 400`) and found the best `E` (32.6, cliff arm C) short of it. `09c`'s enumeration
puts the actual campaign family at 103 declared hypotheses as of 2026-09-19, and rules the
family is campaign-wide, not per item — citing `04c`'s own design text, *"the e-BH family
starts empty at the first arm that declares."* `09c` names `08e`, `10b` and `10e` specifically
(not `02b`) as items whose *local* per-item e-BH reads wrongly claimed a **rejection** against
an undersized family — a real error, because a smaller family understates the bar needed to
reject. §6's local framing is not the same mistake in the same direction: it used its own
20-hypothesis family to claim a **non-rejection** (`400` needed, `32.6` achieved), which is
conservative rather than risky — a smaller assumed family only makes non-rejection *harder* to
establish, not easier, so a conclusion of "fails to reject" reached under the smaller frame
survives a fortiori under the true, larger one. Checking that directly: the construction's
absolute ceiling is `E_max(5,1) = 36` (`e_value_construction.md` §4, checked numerically at
`t = 10⁶`), and a lone e-BH rejection needs `E ≥ 20·n` for a family of size `n`
(`e_value_construction.md` §6). `20 × 2 = 40` already exceeds 36 — so for *any* campaign
family of two or more declared hypotheses, `02b` cannot achieve a lone rejection. The actual
family (103, bar ≈2,080 per `09c`) only makes the same conclusion true by a wider margin.
**This is categorical, not a "cannot rule" pending some resolution: there is no possible
campaign size at which `02b`'s arms clear a lone e-BH rejection under `n=5,g=1`.**

**(c) What is genuinely still open, and why it does not block this ruling.** Whether any of
`02b`'s near-ceiling cliff `E`s (32.4 / 32.4 / 32.6) could be swept into a *joint* rejection
at some larger rank `k` alongside other near-ceiling arms elsewhere in the campaign (`08e`
30.03–35.91, `10e` up to 35.9, `08i` up to 35.9, `10b` 34.50/35.41) is not answerable from
`02b`'s own numbers — it needs the full sorted list of all 103+ declared `E`s, run through
e-BH's `k*` procedure in one place. `09c` names this undone: *"`04c` has not been re-run
against the union since `09b` landed... recomputing a true `k*` needs every declared `E`, not
just its per-item count, assembled in one place, which is `04c`'s job and remains undone."*
That gap belongs to `04c`, not to `02b` — it bears on whether the *campaign* currently has any
live e-BH rejections at all, not on `02b`'s own gate-7 outcome, which is settled by (b)
regardless of what `04c` eventually finds for other items.

**(d) Ruling: `02b` moves to `GATED`.** Per `build-log.json`'s `stage_vocabulary`: `MEASURED`
= "Numbers exist; the standing gate has not been run"; `GATED` = "Passed foundations/gates.md.
Eligible to land." All seven gate steps were run and reported, none skipped: gates 1–5 ran and
are correctly recorded above, including the ones that did not clear; gate 6 was satisfied
before either the original arms or the stint-life follow-on ran; gate 7 was declared before
the arm ran, computed, and reported honestly up to `E = 32.6`, including the arms that
returned wrong-direction or sub-1 `E` (§3's `↓` flags) — which is exactly what `gates.md` step
7 asks for: *"Report `E` whatever it comes out as, `E < 1` included, and count the arm in the
campaign family either way."* Nothing here was substituted or skipped the way `10d` skipped
gate 4 in its literal form and was held at `MEASURED` for it, citing `gates.md`'s own line
*"an item that skips a step is `MEASURED`, never `GATED`"* (`gates.md` line 4) — `02b`
substituted nothing.

`gates.md`'s own "What clears means" section licenses exactly the disagreement recorded here:
*"Clearing the floor and returning a large `E` are two instruments, not one. ... Step 3 rules
on whether the arm beat its own noise; step 7 rules on what that is worth across the campaign.
Report both numbers and let them disagree in public."* Cliff (all three arms) and p90 (B, C)
clear steps 3–4 decisively; gate 7 does not reject, campaign-wide, categorically, under the
declared construction. Both are reported above, and they disagree, as instructed.

**Direct precedent in this tree for not treating an unresolved or adverse campaign-e-BH read
as a gate-7 blocker on stage:** `08i` sits at `GATED` with the identical shape — its own
build-log note reports *"15 declared cross-floor hypotheses ... NOT yet counted in `04c`'s
campaign e-BH. STAYS GATED, NOT CLOSED"* — and `08e` reached `LANDED` even though `09c` later
ruled its own "rejects all five" line a local preview against an undersized family, not the
campaign's real verdict. Campaign-e-BH incompleteness has not been treated as a gate-7 blocker
anywhere else in this tree; `02b` is not being made a special case in either direction.

**What `GATED` does not decide here — named so it is not conflated with this ruling.**
(i) Whether `B`/`C`'s columns are admitted into `FEATURE_COLUMNS` for `cliff_classifier` (and
optionally `degradation_regressor_p90`) is a separate landing decision that this ruling does
not make — the contract stays at 32 columns until that decision is taken and executed, the
same shape as `08i`'s `GATED` floor-1 recommendation sitting behind open decision `D10` before
any rebuild happens. (ii) `04c`'s re-run over the union of all 103+ declared `E`s remains
undone, per (c), and could in principle produce a joint rejection touching other near-ceiling
arms elsewhere in the campaign — it cannot touch `02b` specifically, but it is real unfinished
work this ruling does not do and does not claim to have done.

#### 12. LANDED — the decision was taken and executed, verified independently 2026-09-22

The open item §11(d) left pending — "(i) ... is a separate landing decision that this ruling
does not make" — is no longer open. `D12` resolved **YES** on 2026-09-21: admit the seven
`02b` columns into `FEATURE_COLUMNS` for `cliff_classifier` only (arms B/C on the degradation
trio did not clear sufficiently to also move `degradation_regressor_p90`). It was executed the
same day as **one** `v12 → v13` bump together with `08i`/`D10`, `08o` and `08q`, exactly as
`D16` asked for — not as a standalone `02b` rebuild.

**The 2026-09-22 handoff pass flagged `02b` as an unverified bundle member** (its own `assumed`
field said it had not checked `ml/models/` or `S.MODEL_VERSION_DEFAULT`). This session checked
directly, mirroring the same cross-check `08i`'s landing note ran for itself the same day.
Everything below is read-only — nothing was written to `ml/models/`, `ml/artefacts/`, the
warehouse or git.

1. **The contract split is real in code, not just described in prose.** `ml/src/schema.py:243-246`
   lists the seven qualifying columns inside `FEATURE_COLUMNS` (now **39** wide, was 32);
   `feature_columns_for('cliff_classifier')` returns all **39**; `feature_columns_for()` for
   `degradation_regressor_p10`/`p50`/`p90` and `stint_life_regressor` returns **32** — the
   qualifying group is masked out of exactly the four families `D12` ruled it should not touch.
   This is `D12`'s resolution text implemented exactly, not approximated.
2. **The shipped artefacts are fitted on that split.** `S.MODEL_VERSION_DEFAULT = "v13"`
   (`schema.py:473`, comment names all four bundle members); all five `.bst`/`.onnx` pairs exist
   in `ml/models/` at `v13` (dated 2026-09-21); `ml/artefacts/evaluation_metrics.json` reads
   `version: "v13"`, `evaluated_at: 2026-09-21T11:58:27Z`, and its `cliff_classifier` block
   carries `headline: 0.38478356627919746` (macro-F1) against `baseline_headline: 0.20783`,
   `beats_baseline: true`, `n_eval_rows: 18877` — a live production number, not a staged one.
   `08i`'s own 2026-09-22 landing verification independently refit `cliff_classifier` through
   `evaluate.py`'s own `_fit`/`_score` at **39** columns and reproduced this exact headline to
   10 dp (`0.3847835663`), which is the cross-check that the shipped booster is actually trained
   on the widened contract rather than merely coexisting with it.
3. **The warehouse layer re-verified directly by this session, 2026-09-22.**
   `cd transform && ../.venv/bin/dbt test --profiles-dir profiles --target dev --select
   int_qualifying_driver_summary+ fct_cliff_prediction_features` → **PASS=8 WARN=0 ERROR=0
   SKIP=0**, unchanged from the original build. `PYTHONPATH=. ./.venv/bin/python -m
   ml.src.features --check` → forward-window audit CLEAN, aggregation-scope audit CLEAN,
   leakage guard CLEAN, fingerprint recomputed — the audits pass with the per-family mask in
   place, exactly as the original build-and-check section above reported before the mask
   existed.
4. **Do not re-score `02b`'s own pre-registered arms against the `v13` headline above.** `08q`
   moved the label in the same bump (the same caveat `08i`'s landing note gives for its own
   item), so `0.38478` is not comparable to the `0.35247 → 0.38404` (Arm A) delta §3's gate
   table reports — that table's admissible evidence is the fixed-`v12`-target arm-vs-arm
   comparison it was measured under, and stands as declared. This note confirms execution of
   the `D12` decision, not a re-measurement of the effect.

**Stage.** Per `build-log.json`'s own vocabulary, `LANDED` = "In the contract, warehouse or
app." All three are true here: the contract (`FEATURE_COLUMNS` / `feature_columns_for`), the
warehouse (`int_qualifying_driver_summary`, dbt-tested clean), and the app (the shipped `v13`
`cliff_classifier` booster, evaluated and carrying a beats-baseline macro-F1). `02b` should be
read as `LANDED`, not `GATED`, from 2026-09-21 forward. `build-log.json` is the authoritative
state store and is intentionally not edited by this note — its `stage` field for `02b` should
be updated to `LANDED` by whichever pass is authorized to write it (mirroring how `08i`'s
equivalent confirmation was recorded in `08-foundations-repair.md` without touching
`build-log.json` either).

---

## 3. Tier 2 — Corner-level driver inputs: the only lap-varying candidate

> **REPRIORITISED 2026-09-19 by the build-order restructure — read before running `02c`.** The
> pointer has been moved **off** `02c`, and the item now `depends_on` `00d`. Three reasons, all from
> source:
>
> 1. **One of its three arms reads a sign-inverted column.** Arm B is nine corner-residual
>    aggregates and three of them are the braking phase, which `00d` establishes enters with the
>    wrong sign (`int_corner_skill_residuals.sql:170-178` — `braking_loss_s = (own braking_point_m −
>    field median) × dt_per_dm`, so *positive = braking later = faster*, while the other two phases
>    are positive-is-worse). A monotone flip leaves a tree's predictions unchanged, so the arm
>    *outcomes* stand — but arm B's **deliverable is a per-phase attribution**, and that reading is
>    inverted on a third of it.
> 2. **Its evidence base is void, not merely stale.** The arms ran 2026-09-11 against the pre-`08m`
>    target, and `02b`'s 2026-09-19 re-score found the reseed **floors** themselves moved by up to
>    **3.2×** (p10 0.004311 → 0.00136797 — see the STALE banner at the top of this document). Every
>    ratio in `02c`'s table is a delta over a denominator that no longer exists, so "arm B clears at
>    1.30× / 1.63× / 2.17×" cannot be re-quoted or even re-scaled. The arms have to be re-run.
> 3. **It is the third attempt at scalar-aggregating a telemetry channel, and the first two failed
>    for a documented structural reason.** [`../research/R5-representation-and-transform.md`](../research/R5-representation-and-transform.md)
>    Part 1 reads Phase 9 (which dropped `powertrain` + `telemetry_cliff` — in `schema.py`'s own
>    words *"the mart's entire consumption of `int_lap_telemetry_aggregates`"* — all eleven summary
>    statistics clearing in none of three families) against Phase 10a (the never-aggregated
>    `proximity` channel, which cleared), and concludes: *"Hand-crafted scalar aggregation of the car
>    channel produced nothing that survived ablation … the channel is not information-poor — the
>    aggregation is lossy."* `02c` is hand-crafted scalar aggregation of the corner channel:
>    mean / sd / max per phase.
>
> **This is a re-ordering, not a closure.** Arm B did clear three floors on the old substrate and
> that is real information about the channel. `02c` runs **after** `00d` corrects its input and after
> `02d`, and `R5`'s Options A and B — path signatures, and FPCA on the registered 100-fraction
> `relative_distance` grid `int_lap_proximity` already builds — are the standing argument for why a
> **fourth** scalar attempt should not follow this third one.
>
> `02d` was given `order_hint` 4 in the same pass, ahead of `02c`: its expensive half (the
> season-lagged `int_sc_hazard_history` rebuild, 148/148 races) is already in the warehouse and
> verified, and what remains is one stale test plus an ablation that has never run.
>
> **AMENDED 2026-09-20 by the fan-value reprioritisation — `02d` slides 4 → 6, and `02c`'s position
> behind it is unchanged.** The substrate argument above stands and none of it is withdrawn; `02d`
> still runs ahead of `02b`, `02c` and `02g`. What was *corrected* is the cross-item claim it leaned
> on. `10c`'s line — *"the app has no SC term, and `int_sc_hazard_history`, which is exactly that
> term, feeds nothing"* — was re-verified against source on 2026-09-20 and is true: **zero**
> references to `int_sc_hazard_history` anywhere under `app/src`, and `scripts/export_app_data.py`
> exports neither it nor `int_stint_geometry` nor `stg_track_status`. **But `02d` does not fix
> that.** `02d` is a feature ablation aimed at `stint_life_regressor`; getting the SC term in front
> of a fan is an export, a ruling on which hazard column is defensible, and a page — and that is now
> its own item, [`11c`](11-parallel-surfaces.md), at `order_hint` 3. The two share a table, are
> independent, and block each other in neither direction.

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

### `02c` — Tier 2, corner-level driver inputs · BUILT 2026-09-11, ARMS RE-RUN 2026-09-22

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

> **SUPERSEDED 2026-09-22 — every delta, floor ratio and `E` in this subsection is void.** These
> arms scored a pre-`08m` target against a uniform 32-column `v12` contract. `08m` rebuilt the
> target, and `v13` (`e341152`, 2026-09-21) then moved the label again (`08q`), retrained the
> quantile heads (`08o`) and widened the cliff baseline to 39 columns (`02b`). The floors moved by
> up to **4.33×** and seven of these twelve cells change their ruling. **Read
> "Verdict — `02c` · MEASURED 2026-09-22" below instead.** This block is kept unedited because the
> pre-registration, the declared readings and the two self-corrections at the end of it are the
> record the re-run was judged against — but nothing numeric in it may be re-quoted or re-scaled.

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

### Verdict — `02c` · MEASURED 2026-09-22

**Re-run on the rebuilt substrate. The corner channel survives, but far more weakly than the
2026-09-11 table says, and on a different set of families.** The one outcome that admits the
group on its stated grounds — arm B clearing where arm C does not — now occurs on **p50 alone**.
On p10 and cliff the *bundle* clears while **neither half does**, which is the Phase 10a shape
`gates.md` step 4 exists to catch and is recorded as ambiguous, not rounded up. On p90 nothing
clears at all. Run: `PYTHONPATH=. ./.venv/bin/python scripts/arms_02c_corner_inputs.py`,
2026-09-22 05:03–05:33 UTC (~30 min). Artefacts: `ml/artefacts/02c_corner_inputs_arms.json`
(per-seed headlines, e-value components, instrument checks) and `.log`.

#### 0. What changed under this item since it last ran, and what that forced

The 2026-09-11 arms scored a pre-`08m` target against a uniform 32-column `v12` contract. **Two
rebuilds have landed since, and both move the denominator.**

* `08m` (2026-09-16) rebuilt the degradation target. `02b` re-measured the floors 2026-09-19.
* **`v13` (commit `e341152`, 2026-09-21) bundled `02b`, `08o` and `08q`** — and this Verdict is
  the first `02c` text written against it. `08q` moves the **label** for the trio and the
  classifier (`theta_air` 0.5 → 0.1310 s/lap); `08o` drops the IPW sample weight from the three
  quantile heads; `02b` admits seven qualifying columns to `cliff_classifier` **only**.

Three consequences, each a deviation from the brief this run was commissioned under, recorded
rather than quietly absorbed:

1. **The floors handed to this run were stale, and using them would have mis-ruled p10 by 4.3×.**
   The brief specified `02b`'s 2026-09-19 floors as measured values to reuse. They are measured —
   on a substrate two rebuilds back. Every ratio below divides by a floor measured **in-run** on
   the substrate actually scored, which is `02b`'s own §4(a) ruling applied one generation later.
2. **The baseline is `v13`, not `v12`, and it is no longer one width.** `schema.feature_columns_for()`
   gives the degradation trio **32** columns and `cliff_classifier` **39**. The brief said "32
   features, contract `v12`, do not add the `02b` qualifying columns". For the trio that is exactly
   what ran — the qualifying columns are masked out by `PER_TARGET_FEATURE_MASK` and the baseline
   is the same 32. For cliff it could not be: gate 1 requires reproducing the **published**
   headline, and the published cliff headline is the 39-column one. **So on cliff these arms
   measure the corner channel's *incremental* value over qualifying** — a strictly harder test
   than 2026-09-11's, and the reason cliff falls furthest.
3. **`00d` landed 2026-09-20 and inverted the braking phase at the source.** The marginal
   correlation of `corner_braking_loss_mean_s` with the label moves **+0.0627 → −0.1054**. The
   build-order audit predicted this: a monotone flip leaves a tree's predictions unchanged, so it
   is not why the arms moved — but arm B's *deliverable* is a per-phase attribution, and that
   reading was inverted on a third of it before `00d`.

#### 1. Gate 1 — instrument check: PASS, all four families

Every family's refit reproduces the **current** `evaluation_metrics.json` headline to ten decimal
places, anchored on `v13` (evaluated 2026-09-21), not on any `v12` or pre-`08m` figure.

| family | refit baseline | published | metric | baseline width |
| :--- | ---: | ---: | :--- | ---: |
| `degradation_regressor_p10` | 0.4557991687 | 0.4557991687 | pinball | 32 |
| `degradation_regressor_p50` | 0.9309607723 | 0.9309607723 | pinball | 32 |
| `degradation_regressor_p90` | 0.5070426104 | 0.5070426104 | pinball | 32 |
| `cliff_classifier` | 0.3847835663 | 0.3847835663 | macro-F1 | **39** |

The cliff row is doing double duty: it confirms `v13`'s per-family mask is the one in production,
and it confirms this runner feeds the classifier a 39-wide matrix rather than silently handing a
39-wide contract to a 32-wide booster. That would have produced a plausible wrong number rather
than an error — the failure mode gate 1 exists to catch.

#### 2. Gate 2 — add-ablation on the identical split

`cv_final_fold`, train 2018–2023, eval 2024, `evaluate.py`'s own `_fit`/`_score`, contract `v13`.
Degradation trio: **67,847 train / 13,711 eval**, one bundle shared across p10/p50/p90. Cliff:
**94,294 train / 18,877 eval**. No arm adds a column to the baseline other than its own.

#### 3. The floors moved again — a third set of numbers for the same four families

Measured in-run over seeds 20260528–20260532, beside the two sets this item has previously been
handed. **Neither earlier set is used as a denominator anywhere below.**

| family | `02c` 2026-09-11 (pre-`08m`, v12) | `02b` 2026-09-19 (post-`08m`, v12) | **measured 2026-09-22 (v13)** | vs 09-19 |
| :--- | ---: | ---: | ---: | ---: |
| p10 | 0.004311 | 0.00136797 | **0.00592996** | **4.33×** |
| p50 | 0.010431 | 0.01115092 | **0.00765339** | 0.69× |
| p90 | 0.009347 | 0.00839541 | **0.00809109** | 0.96× |
| cliff | 0.005772 | 0.00433972 | **0.00681449** | 1.57× |

p10's floor is **4.33× looser** than the number the brief said to reuse. Had it been reused, arm A
would have read **+9.28×** instead of +2.14× and arm B **+3.48×** instead of +0.80× — i.e. B would
have been reported as a clear when it is not one. This is the second consecutive re-run in which a
reused floor would have inverted a ruling, and it is the strongest available argument for measuring
the floor in the same process that measures the delta.

#### 4. Gates 3 + 4 — every delta, with its floor ratio

"raw" is the add-ablation delta over floor; "info" is the permutation-corrected delta
(`real − shuffled`) over the same floor. Positive is improvement on every metric. **Clears**
requires both, per `gates.md`'s "What clears means".

| family | floor `2√2·sd` | arm | raw ×floor | info ×floor | capacity | E | clears |
| :--- | ---: | :--- | ---: | ---: | ---: | ---: | :--- |
| **p10** | 0.00592996 | **A full (10)** | **+2.14** | **+2.51** | −0.00218 | 21.8 | **YES** — but see §5 |
| | | B residuals (9) | +0.80 | +1.13 | −0.00195 | 2.59 | no — raw misses |
| | | C coverage (1) | +1.03 | +0.78 | +0.00150 | 23.5 | no — information misses |
| **p50** | 0.00765339 | **A full** | **+2.04** | **+2.01** | +0.00022 | 4.31 | **YES** |
| | | **B residuals** | **+1.19** | **+1.82** | −0.00482 | 2.21 | **YES** |
| | | C coverage | +0.62 | +0.87 | −0.00191 | 0.946 | no |
| p90 | 0.00809109 | A full | +0.92 | +0.26 | +0.00528 | 4.26 | no |
| | | B residuals | +0.46 | +0.41 | +0.00041 | 7.71 | no |
| | | C coverage | +0.21 | +0.38 | −0.00134 | 3.67 | no |
| **cliff** | 0.00681449 | **A full** | **+1.02** | **+1.42** | −0.00273 | 11.4 | **YES** — but see §5 |
| | | B residuals | +0.43 | +0.78 | −0.00244 | 27.7 | no |
| | | C coverage | +0.06 | +0.48 | −0.00285 | 8.01 | no |

**Harness is clean.** The shuffle-vs-shuffle negative control returned `E` = **0.445 / 0.413 /
0.410 / 1.05** on p10 / p50 / p90 / cliff. Three sit well below 1; cliff's 1.05 is unremarkable
under a null whose mean is exactly 1 (`d̄` = −0.00184, direction *against*), and it is two orders
of magnitude away from anything this table reads as evidence. The Monte-Carlo validity check
returned mean `E` = **1.0016 / 0.9992 / 1.0108 / 1.0014** at σ = 0.001 / 0.01 / 0.1 / 1.0 over
100k draws each, every one within Monte-Carlo error (±2·SE ≈ 0.010) of 1.00.

**Headline deltas for the clearing arms**, in their own units:

* `degradation_regressor_p10` pinball **0.455799 → 0.443107** (A, −0.012692 = improvement).
* `degradation_regressor_p50` pinball **0.930961 → 0.915338** (A, −0.015623), **→ 0.921828**
  (B, −0.009132).
* `cliff_classifier` macro-F1 **0.384784 → 0.391743** (A, +0.006959).

#### 5. Two of the three clears are the Phase 10a shape, and are not rounded up

On **p10** and **cliff**, arm A clears on both raw and information while **neither B nor C clears
on raw**. `gates.md`: *"A total that clears while neither half does is recorded as exactly that —
ambiguous — and never rounded up."* Both are recorded as ambiguous.

This is a reversal of 2026-09-11, which found the opposite and said so: *"A is also worse than B on
p10 and p50: adding `corner_input_coverage` to the nine residuals costs signal there."* On the
rebuilt substrate **A beats B on all four families**, and C alone is feeble everywhere (raw +1.03,
+0.62, +0.21, +0.06). So the coverage column is not a competing explanation and it is not a
dilutant — the two blocks are only worth anything **together**, which is an interaction and not a
mechanism claim. Neither the 2026-09-11 reading ("B beats C on three of four families") nor its
confound worry ("a naive nine-column arm could have cleared on the coverage channel") survives.

**p50 is the only family that produces a declared, non-ambiguous outcome.** B clears (+1.19 raw,
+1.82 info) and C does not (+0.62). That is the pre-registration's *"B clears, C does not → the
driver-input mechanism is supported"*, and it is the only cell in the table that admits the group
on its stated grounds.

#### 6. The declared readings, applied family by family

* **p10 — "A clears but neither B nor C does" → ambiguous.** Declared in advance as *"this is Phase
  10a's p50 outcome and it is not rounded up"*. Recorded as ambiguous.
* **p50 — "B clears, C does not" → the driver-input mechanism is supported.** The only family where
  it fires.
* **p90 — "Nothing clears."** The declared reading is *"Tier 2 is closed, and with it the last
  lap-varying candidate in item 02 … a substantive result about the degradation ceiling."* It fires
  on p90 alone, not on the trio, so Tier 2 does not close — but the p90 tail is now the second
  family (after 2026-09-11's p90) to return nothing from this channel, and C's collapse there from
  **+2.59× to +0.21×** retires the 2026-09-11 claim that *"on the p90 quantile the corner channel
  is a coverage channel."*
* **cliff — "A clears but neither B nor C does" → ambiguous.** Same as p10. Note this is the family
  where the baseline gained `02b`'s seven qualifying columns, and the fall is the largest in the
  table (A 2.59× → 1.02×, B 2.17× → 0.43×). The straightforward reading is that **qualifying and
  the corner channel are substitutes for cliff onset**: once the classifier has the driver's
  one-lap form, the corner aggregates have much less left to add.

#### 7. The primary hypothesis holds, and it holds much more narrowly than before

It was: *"arm B clears its floor on at least one of the three degradation quantiles."* **B clears
on one — p50, at +1.19× raw and +1.82× information, with a negative capacity term (−0.00482), so
the nine columns as noise make the model slightly worse and help only when they carry real
values.** Tier 2 is still the only lap-varying candidate in this document and it still reaches the
within-stint variance. But the 2026-09-11 write-up recorded B clearing on **two** quantiles at
1.30× and 1.63×; on the rebuilt substrate p10 reverses to **+0.80×** and p50 falls to **+1.19×**.

Arm-by-arm against the superseded table, so the size of the move is visible:

| family | arm | 2026-09-11 ×floor | 2026-09-22 ×floor |
| :--- | :--- | ---: | ---: |
| p10 | A / B / C | 0.45 / **1.30** / 0.70 | **2.14** / 0.80 / 1.03 |
| p50 | A / B / C | **1.36** / **1.63** / **1.23** | **2.04** / **1.19** / 0.62 |
| p90 | A / B / C | **1.65** / 0.49 / **2.59** | 0.92 / 0.46 / 0.21 |
| cliff | A / B / C | **2.59** / **2.17** / **1.09** | **1.02** / 0.43 / 0.06 |

Seven of twelve cells cleared on 2026-09-11; **four** do now, and only one of those four is a
half rather than a bundle.

#### 8. Gate 7 — the e-values, and the ceiling that was already known to bind

Construction B (paired safe-t), n = 5, g = 1, seeds 20260528–20260532, exactly as pre-registered
2026-09-11. Sorted descending the twelve `E`s run **27.7, 23.5, 21.8, 11.4, 8.01, 7.71, 4.31,
4.26, 3.67, 2.59, 2.21, 0.946**. Every one is in the improvement direction
(`direction_is_improvement = true`), so no wrong-direction caveat applies here — unlike `02d`.

**e-BH rejects nothing, and could not have.** At α = 0.05 and m = 12, `k* = max{k : E_[k] ≥
12/(0.05k)}` needs 240 for a lone rejection; the construction's ceiling is
`(1 + ng)^((n−1)/2)` = **36**. **k\* = 0.** Against the campaign family `09c` enumerated (103 as of
2026-09-19, ≈123 after `02d`) the bar is ≈2,480 and the conclusion only widens.

**The parameters were not re-sized, deliberately.** `09c` raised the ceiling to `n = 10, g = 1`
but ruled **non-retroactively**: *"every `E` already declared under `n=5,g=1` (`02b`, `02c`, …)
stands as declared."* These twelve arms were declared 2026-09-11, before `09c` landed. Re-running
them at `n = 10` to chase a clearer read is barred by `09c`'s own ruling and is not done here.
Gate 7 therefore returns a permanent, structural non-rejection for all twelve — the same
categorical result `02b` §11 reached, for the same reason.

**Family accounting.** This is a **re-measurement of the same twelve declared hypotheses**, not
twelve new ones: the hypotheses, arms, construction and seeds are the 2026-09-11 pre-registration
unchanged, and only the substrate moved. The campaign family does not grow. `09c` §2's open
12-vs-16 counting question (whether the permutation arm `P` counts per family) is untouched and
still unresolved; `k*` is 0 under either reading. The stint-life column of every arm remains
**unrun and uncounted** — `10e` landed 2026-09-19 and discharges `10d`'s bar, but this item's own
text makes stint life a follow-on registration of its own rather than a retroactive family member,
and the runner refuses it rather than leaving that to a reader's memory.

#### 9. Coverage and the missingness bias, re-verified on the rebuilt substrate

Corner-grain availability over all 2,206,939 rows of `int_corner_skill_residuals` reproduces the
corrected 2026-09-11 figures exactly — braking **69.94%**, mid-corner **81.12%**, exit **47.00%**,
intersection **38.59%** — which is expected, since those are telemetry-presence facts and neither
`08q` nor `08o` touches them.

At the mart, on the **95,346** training-eligible rows (was 121,193 pre-`08m`):

| column | non-null | marginal corr with label |
| :--- | ---: | ---: |
| `corner_input_coverage` | 100.00% | **−0.2548** |
| `corner_braking_loss_mean_s` | 94.68% | −0.1054 *(was +0.0627 pre-`00d`)* |
| `corner_mid_residual_mean_s` | 94.83% | −0.2126 |
| `corner_mid_residual_max_s` | 94.83% | **−0.2553** |
| `corner_exit_residual_mean_s` | 88.75% | −0.0555 |

**The missingness bias is still there and is larger than before.** Rows where
`corner_braking_loss_mean_s` is NULL average **+5.6723 s** of 5-lap jump (sd 10.2945, n = 5,071)
against **−0.7378 s** for covered rows (sd 4.1326, n = 90,275). It remains a coverage artefact and
not forward leakage — a lap is uncovered because its own telemetry is absent or the trailing
*t−5…t−1* baseline held fewer than five valid observations, both settled strictly before *t+1* —
and it remains the reason arm C exists. What has changed is the conclusion: C no longer clears
anywhere, so the confound the arm was built to catch **did not fire on this substrate**.

#### 10. What this item does and does not conclude

* **Verified.** The ten columns as a bundle carry information the contract does not have, on p10,
  p50 and cliff, with the permutation arm attributing it to information and a negative capacity
  term on three of those four bundles.
* **Verified, and much weaker than previously recorded.** The nine residual aggregates *on their
  own* clear on **p50 only**. The 2026-09-11 statement that they clear on p10, p50 and cliff is
  superseded and must not be re-quoted.
* **Retired.** "On p90 the corner channel is a coverage channel" (C: 2.59× → 0.21×), and "arm A is
  worse than B on p10 and p50" (A now beats B everywhere).
* **Not done here, and deliberately.** The contract is unchanged: the ten columns are in the mart
  and still absent from `ml/src/schema.py`'s `FEATURE_COLUMNS`. Nothing in this table settles
  *which* set to move — A is uniformly the better arm but is ambiguous by gate 4 on two of its
  three clears, and B, the arm with the mechanism story, clears once.
* **The R5 cap stands and is now better evidenced.** This is the third hand-crafted scalar
  aggregation of a telemetry channel; Phase 9 dropped eleven such summary statistics of the same
  table for clearing in none of three families. `02c` clears more than that, but its one
  unambiguous mechanism cell out of twelve is a thin return for a 30-minute, 208-fit campaign, and
  it is consistent with R5's reading that *the aggregation is lossy, not the channel*. R5's Option
  A (path signatures) and Option B (FPCA on the existing 100-fraction `relative_distance` grid)
  remain the standing argument against a fourth scalar attempt.

#### 11. Standing

**`MEASURED`.** Gates 1–4 ran and are reported with no skips; gate 5's two leakage audits were
re-verified clean when the lineage was wired in; gate 6 was satisfied 2026-09-11 and this run adds
no arm to it; gate 7 is declared and reported and is **structurally unable to reject**, permanently,
under `09c`'s non-retroactivity.

What a later session may quote from this item: the gate-3 and gate-4 ratios in §4, on the `v13`
substrate, as measured above. What it may **not** quote: any 2026-09-11 delta or floor ratio, and
any `02b`-2026-09-19 floor as a denominator for `02c`.

Arm D (corner-type split) was unlocked 2026-09-11 conditional on B clearing. B still clears — on
p50 — so D stays unlocked, **unrun and uncounted**.

Recommended next, none of it done here: (i) a decision on whether an ambiguous bundle clear is
grounds to move anything into `FEATURE_COLUMNS`, which this item declines to make on its own;
(ii) the stint-life follow-on registration, if it is wanted, written before it runs; (iii) R5
Option A/B rather than arm D, if the corner channel is to be pursued at all.

---

### `02h` — Corner drift as persistence measurement · BUILT + ARMS PRE-REGISTERED 2026-09-22, ARMS RUN 2026-09-22, CLOSED

**Written 2026-09-22, from `audit_02c_corner_telemetry_underperformance.md`.** `02e` was
requested for this item but is already `CLOSED` (weather / air-density features, unrelated,
closed 2026-08-23) and `02f` is also taken (FP1/2/3 ingest); `02h` is the next free id in
group `02`, used throughout this section and in `build-log.json`.

**(a) Why instantaneous corner inputs failed.** The audit measured *persistent lap-varying
variance* (within-stint share × lag-1 within-stint autocorrelation) across every candidate
channel in the contract. `02c`'s nine residual aggregates sit at **.032–.176**; every column
that survives ablation elsewhere sits at **.266–.421** (proximity's `share_lap_in_train`
.421, thermal's `push_residual` .343, `dirty_air_share_lap` .266) — and even the
**degradation label itself** is only .241. `02c`'s own 2026-09-22 Verdict already shows the
consequence: arm B clears **one** quantile (p50) of three, down from the two the original
2026-09-11 run claimed. `(field trailing-5 median − own)`, what `int_corner_skill_residuals`
measures, is a **relative-pace** construct — a driver/car trait the contract already holds
three ways (qualifying, constructor pace, thermal push) — and pace has no reason to persist
lap-to-lap the way a **state** does.

**(b) Why drift should persist.** Residualizing the residual a second time — against the
driver's own early-stint level for that same corner and phase, not the field's — turns a pace
measurement into a state measurement. A driver steadily 0.05s off the field all race has zero
drift (pace, already captured three times over). A driver who opens that gap from 0.05s to
0.35s across the stint has +0.30s of drift, which should accumulate roughly monotonically as
the tyre degrades and therefore correlate with itself lap-to-lap by construction, the way
`age_in_stint` already does.

**(c) Hypothesis.** At least one of arms A/B clears its floor on the degradation trio, with
the effect more likely on p50/p90 (laps further into the stint, where drift has had time to
accumulate) than on p10.

**What was built.** `int_corner_drift_from_early_stint` (new, grain `(lap_id, corner_name)`,
2,206,939 rows — same grain and row count as `int_corner_skill_residuals`, which it
residualizes a second time). For each `(stint_id, corner_name)`, the mean of
`braking_loss_s` / `mid_corner_residual_s` / `exit_residual_s` over the stint's own first six
**valid** laps (`valid_lap_in_stint` 1–6) is taken as a baseline (requiring ≥ 3 non-NULL
observations in that window); every row with `valid_lap_in_stint ≤ 6` or
`stint_length_valid < 7` gets `NULL` — those rows define the baseline rather than measuring a
departure from it. `int_lap_corner_drift` aggregates to lap grain (mean/sd/max per phase +
`corner_drift_coverage`), mirroring `int_lap_corner_inputs`'s own shape exactly. Ten columns
wired into `fct_cliff_prediction_features`, mart-only — **in the mart and not in
`ml/src/schema.py`'s `FEATURE_COLUMNS`**, the same standing every prior item in this group held
before its ablation.

**Leakage, verified before anything else.** The baseline window is *fixed* per stint, not
trailing relative to the query lap. Measured directly on the built table: **zero** of the
1,552,813 non-baseline-window corner rows with a non-NULL drift value have
`valid_lap_in_stint ≤ 6`, and the **minimum** `valid_lap_in_stint` carrying a non-NULL value
of any of the three drift columns is exactly **7** — strictly after the window that defines
the baseline it is compared against. `python3 -m ml.src.features --check`: forward-window
audit CLEAN, aggregation-scope audit CLEAN (the new model's `(stint_id, corner_name)` GROUP BY
is declared in `schema.yml`'s `aggregation_scope_exemptions`, argued in full in that model's
header and exemption entry), leakage guard CLEAN at 32 features (contract unmoved).
`ml/tests/test_features.py`: 31/31 pass, unaffected. `dbt test` on both new models: 15/15
pass; on the rebuilt mart: 3/3 pass.

**Coverage, measured on the mart's 119,775 training-eligible rows** (same row count the
audit itself measured against). Mean `corner_drift_coverage` **0.6020**, well below `02c`'s
`corner_input_coverage` (0.7986) because this column now also gates on stint length and the
baseline window: 23.70% of stints never reach 7 valid laps at all. Per-phase non-null share at
lap grain: braking **73.17%**, mid **73.28%**, exit **67.36%**. Of the 32,140 training-eligible
rows with `corner_braking_drift_mean_s` NULL, **92.4%** (29,705) are NULL purely mechanically
— inside the baseline window or on a too-short stint, both already reachable from
`age_in_stint`/`lap_in_stint` — and only 7.6% (2,435) from the same corner-unmapped /
thin-baseline reasons `02c`'s coverage column exists for. **The missingness is not
label-neutral, same direction as every prior item in this group**: covered rows average
**−0.5552 s** of 5-lap jump (sd 3.827) against **−0.2158 s** (sd 5.130) for NULL rows —
missing rows degrade worse. Marginal correlation with the label is weaker than `02c`'s
residuals at every phase (braking mean **−0.118** vs `02c`'s −0.105 — comparable; mid mean
**−0.196** vs −0.213; mid max **−0.192** vs −0.255; `corner_drift_coverage` **−0.035** vs
`02c`'s −0.255, much weaker, consistent with 92.4% of its NULLs being mechanical rather than
telemetry-driven).

**(d) Three pre-registered arms**, on `corner_drift_coverage` and the nine mean/sd/max columns
of `int_lap_corner_drift`:

| arm | columns | what it tests |
| :--- | :--- | :--- |
| **A — full drift** | 10 (9 drift stats + `corner_drift_coverage`) | the group as designed |
| **B — drift by phase** | 3 (the three phase **means** only: `corner_braking_drift_mean_s`, `corner_mid_drift_mean_s`, `corner_exit_drift_mean_s`) | the mechanism at its coarsest — does the per-phase drift *level* alone carry signal, without arm A's sd/max elaboration |
| **C — coverage indicator** | 1 (`corner_drift_coverage`) | the confound control — 92.4% of this column's NULLs are mechanical (inside the baseline window or a stint shorter than 7 valid laps), a pattern already reachable from `age_in_stint`/`lap_in_stint` |
| **P — permutation null** | each arm's own columns, row-shuffled jointly in train *and* eval | gate step 4 — capacity and information reported separately |

**Declared readings, so no result can be reinterpreted after the fact** — the same shape
`02c`'s own pre-registration used:

* **A and/or B clears on the degradation trio, C does not** → the drift mechanism is
  supported: residualizing against the driver's own early-stint baseline recovers persistence
  `02c`'s pace residuals lacked.
* **C clears, A/B do not** → the group is a stint-progress/coverage proxy, not a driver-input
  drift signal — the same reading `02c`'s pre-registration gave a clearing coverage arm.
* **A clears but neither B nor C does** → ambiguous, recorded as exactly that and not rounded
  up — `02c`'s own p10/cliff outcome on the rebuilt substrate.
* **Nothing clears** → the audit's proposed fix does not rescue the corner channel either, and
  Tier 2 is closed for good: R5's Option A/B (path signatures, FPCA) become the only standing
  proposal for this sensor.

**E-value pre-registration.** Construction B (paired safe-t), **`n = 10, g = 1`** — per `09c`
(LANDED 2026-09-19), which sets `n = 10` for every arm pre-registered *after* that date; this
registration is written 2026-09-22, so it applies here, unlike `02b`'s and `02c`'s `n = 5`
arms, which `09c` ruled non-retroactive. Seeds `RANDOM_STATE + 0..9`; the floor stays at
**five** reseeds (gates.md step 3's own wording) and nests inside the ten e-value seeds,
exactly the choice `02d` made for the same open question `09c` left unresolved. Cap
`E_max(10,1) = 11^4.5 = 48,558.70`. Family size sized against: `09c`'s 103 (as of
2026-09-19) + `02d`'s 20 (declared 2026-09-20) + this item's 3 arms × 4 families = 12, giving
`m = 135` and a lone-rejection bar of `20*(135+1) = 2,720` — not an independent re-audit of
the full campaign, the same count-forward convention `02d` used. Declared alt: each family's
own floor, `2·√2·sd`. Validity check: 100k draws of ten i.i.d. `N(0,σ)` deltas must return
mean `E` = 1.00 before any arm's result is trusted.

**(e) Cost:** 2–3d, opus-5 — design + build + ablation, simpler than a path-signature/FPCA
rebuild (R5 Options A/B) because it reuses `int_corner_skill_residuals` rather than
re-deriving corner shape from raw telemetry.

**(f) Definition of done:** dbt models built, tested and leakage-verified (done, above); arms
pre-registered here before any arm runs (gates.md step 6, done, above);
`scripts/arms_02h_corner_drift.py` written following `arms_02c_corner_inputs.py`'s pattern at
`n=10,g=1` (done); gates 1–4 and 7 run and reported, whatever they show (**not done in this
session — see the standing note below**); a Verdict section written in `02b`/`02c`'s format;
`build-log.json` updated with the outcome.

> **SUPERSEDED 2026-09-22 — the arms have now run.** The standing paragraph below was written
> before any arm was executed and is kept unedited because it is the pre-registration's own
> record of what had and had not been done at that moment. The item is no longer `SPEC`:
> see **"Verdict — `02h` · CLOSED 2026-09-22"** immediately below.

**Standing, 2026-09-22: `SPEC`. Arms are pre-registered and the runner is written; no arm has
been executed.** Per `02b`'s own precedent for this exact shape of readiness ("`02b`'s item
stage is left at `SPEC`... because no ablation delta exists yet — only the build, tests, and
diagnostic coverage numbers... the numbers that matter for this item are the arm deltas,
which do not exist until the script runs"), this item stays `SPEC` despite the dbt build,
tests and coverage measurements above being complete. Running
`PYTHONPATH=. ./.venv/bin/python scripts/arms_02h_corner_drift.py` and writing the Verdict
section is left to a subsequent session, deliberately — nothing above should be read as a
result.

---

### Verdict — `02h` · CLOSED 2026-09-22

**The audit's proposed fix does not work, and it fails on the exact axis it was built to
repair.** Residualizing `02c`'s corner residuals a second time against the driver's own
early-stint baseline was supposed to convert a *pace* measurement into a persistent *state*
measurement. Measured directly with the audit's own statistic, the nine drift columns are
**less** persistent than the nine `02c` residuals they replace — **0.0169–0.1397** against
`02c`'s **0.0267–0.1756** — and the ablation agrees: **arms A and B clear nothing, on any of
the four families.** The single cell of twelve that clears is **arm C, the confound control**,
on `degradation_regressor_p10` — and the pre-registration declared in advance that exactly this
pattern means *"the group is a stint-progress/coverage proxy, not a driver-input drift
signal."* Run: `PYTHONPATH=. ./.venv/bin/python scripts/arms_02h_corner_drift.py`, 2026-09-22
07:28–08:32 UTC (~64 min, **368 fits**). Artefacts: `ml/artefacts/02h_corner_drift_arms.json`
(per-seed headlines, e-value components, instrument checks) and `.log`.

#### 0. The one measurement that answers the item, taken before the arms are read

`02h` exists because of a single number in `audit_02c_corner_telemetry_underperformance.md`:
*persistent lap-varying variance* = within-stint variance share × lag-1 within-stint
autocorrelation. The item's whole premise, written into both new models' headers, is that drift
against a fixed early-stint baseline *"persists by construction, because it accumulates with
tyre wear across the remainder of the stint."* **That premise is testable without fitting
anything, and it is false.**

Recomputed here on the **119,775** training-eligible mart rows (6,916 stints), with the lag-1
term taken on strictly consecutive `lap_in_stint` pairs within a stint, no gap bridging. The
method reproduces the audit's published anchors to three decimals — `share_lap_in_train`
**0.4211** (audit 0.421), `push_residual` **0.3426** (0.343), `dirty_air_share_lap` **0.2656**
(0.266), the degradation label itself **0.2406** (0.241) — so it is the audit's instrument, not
a near neighbour of it.

| channel | within-stint share | lag-1 autocorr | **persistent lap-varying variance** |
| :--- | ---: | ---: | ---: |
| `age_in_stint` (contract, pure stint clock) | 0.6226 | 1.0000 | 0.6226 |
| **`corner_drift_coverage`** (`02h`, arm C) | 0.7334 | 0.8271 | **0.6066** |
| `share_lap_in_train` (contract, proximity) | 0.6193 | 0.6799 | 0.4211 |
| `push_residual` (contract, thermal) | 0.6873 | 0.4985 | 0.3426 |
| `dirty_air_share_lap` (contract) | 0.6632 | 0.4005 | 0.2656 |
| **the degradation label** | 0.8328 | 0.2889 | **0.2406** |
| `02c`'s nine residual aggregates | — | — | **0.0267 – 0.1756** (median 0.0550) |
| **`02h`'s nine drift aggregates** | — | — | **0.0169 – 0.1397** (median 0.0471) |

**The drift construction moved persistence in the wrong direction.** Phase by phase, on the
three mechanism columns that arm B is made of:

| phase mean | `02c` residual | **`02h` drift** | moved |
| :--- | ---: | ---: | :--- |
| braking | 0.1075 | **0.0990** | worse |
| mid-corner | 0.1756 | **0.1397** | worse |
| exit | 0.0550 | **0.0749** | better |

Two of three worse, the best drift column (mid, 0.1397) below `02c`'s best (mid, 0.1756), and
the whole set still **3–4× below** the 0.266–0.421 band of every column that survives ablation
elsewhere in the contract, and below the label's own 0.2406. The second residualization removes
the stable driver/corner offset — which is most of what was autocorrelated in the first place —
and what it leaves behind is closer to lap-to-lap noise than what it started from. **The one
column in the group that does persist (`corner_drift_coverage`, 0.6066) persists because it is
a stint clock**, not because it is a tyre state; §5 takes that apart.

#### 1. Gate 1 — instrument check: PASS, all four families

Every family's refit reproduces the live `evaluation_metrics.json` headline to **ten** decimal
places, anchored on `v13` (`e341152`, evaluated 2026-09-21) — the same substrate `02c`'s
2026-09-22 re-run scored against.

| family | refit baseline | published | metric | baseline width |
| :--- | ---: | ---: | :--- | ---: |
| `degradation_regressor_p10` | 0.4557991687 | 0.4557991687 | pinball | 32 |
| `degradation_regressor_p50` | 0.9309607723 | 0.9309607723 | pinball | 32 |
| `degradation_regressor_p90` | 0.5070426104 | 0.5070426104 | pinball | 32 |
| `cliff_classifier` | 0.3847835663 | 0.3847835663 | macro-F1 | **39** |

As in `02c`, `v13` is not one width: `schema.feature_columns_for()` gives the degradation trio
32 columns and `cliff_classifier` 39 (`02b`'s seven qualifying columns, admitted to the
classifier only). **On cliff these arms therefore measure the corner-drift channel's
*incremental* value over qualifying**, the same strictly-harder test `02c`'s re-run faced, and
for the same reason: gate 1 requires reproducing the *published* headline.

#### 2. Gate 2 — add-ablation on the identical split

`cv_final_fold`, train 2018–2023, eval 2024, `evaluate.py`'s own `_fit`/`_score`, contract
`v13`. Degradation trio: **67,847 train / 13,711 eval**, one bundle shared across p10/p50/p90.
Cliff: **94,294 train / 18,877 eval**. No arm adds a column to the baseline other than its own.
Identical row counts to `02c`'s re-run, as they must be — the two items differ only in which
ten mart columns are attached.

#### 3. Gate 3 — the floors, measured in-run, and an exact reproduction of `02c`'s

Measured fresh over seeds 20260528–20260532, per `02b` §4(a) and `02c`'s own finding that a
reused floor had inverted a ruling by 4.33×. No floor is borrowed here either.

| family | `02c` in-run 2026-09-22 | **`02h` in-run 2026-09-22** | agreement |
| :--- | ---: | ---: | :--- |
| p10 | 0.00592996 | **0.00592996** | identical to 8 dp |
| p50 | 0.00765339 | **0.00765339** | identical to 8 dp |
| p90 | 0.00809109 | **0.00809109** | identical to 8 dp |
| cliff | 0.00681449 | **0.00681449** | identical to 8 dp |

This is a free and rather strong instrument check that neither item was designed to provide.
The reseed floor depends only on the family, the split and the seeds — never on the candidate
columns — so two independently written runners, executed eleven hours apart against the same
substrate, **must** agree to full precision, and they do. Any disagreement would have meant one
of the two runners was not scoring the baseline it claimed to.

#### 4. Gates 3 + 4 — every delta, with its floor ratio

"raw" is the add-ablation delta over floor; "info" is the permutation-corrected delta
(`real − shuffled`) over the same floor; "capacity" is `shuffled − baseline` in headline units.
Positive is improvement on every metric. **Clears** requires both raw and information, per
`gates.md`'s *"What clears means"*. `↓` marks an `E` whose direction is *against* the arm.

| family | floor `2√2·sd` | arm | raw ×floor | info ×floor | capacity | E | clears |
| :--- | ---: | :--- | ---: | ---: | ---: | ---: | :--- |
| **p10** | 0.00592996 | A full (10) | +0.86 | +0.67 | +0.00112669 | 209 | no — both miss |
| | | B drift-by-phase (3) | −0.19 | −0.18 | −0.00003926 | 5.21 ↓ | no |
| | | **C coverage (1)** | **+2.00** | **+1.59** | +0.00247718 | **743** | **YES** — see §5 |
| **p50** | 0.00765339 | A full | −0.03 | +0.34 | −0.00283571 | 2.63 | no |
| | | B drift-by-phase | +0.34 | **+1.23** | −0.00681136 | 1.01 | no — raw misses |
| | | C coverage | −0.74 | −0.21 | −0.00405083 | 0.740 | no |
| **p90** | 0.00809109 | A full | −0.27 | −0.35 | +0.00064674 | 2.88 ↓ | no |
| | | B drift-by-phase | −0.58 | −0.79 | +0.00173229 | 2.90 ↓ | no |
| | | C coverage | +0.12 | −0.22 | +0.00276999 | 35.3 ↓ | no |
| **cliff** | 0.00681449 | A full | −0.42 | −0.20 | −0.00152652 | 1.28 | no |
| | | B drift-by-phase | −0.39 | +0.47 | −0.00583284 | 0.859 | no |
| | | C coverage | −0.10 | +0.34 | −0.00302288 | 0.351 | no |

**One cell of twelve clears.** Seven of the twelve raw deltas are *negative* — the columns make
the model worse — and on p90 all three arms carry an `E` pointing against the feature.

**Harness is clean.** The shuffle-vs-shuffle negative control, where H0 is true by construction,
returned `E` = **0.509 / 0.314 / 0.348 / 0.817** on p10 / p50 / p90 / cliff — every one below 1
and three orders of magnitude from anything this table reads as evidence. The Monte-Carlo
validity check returned mean `E` = **0.9896 / 1.0314 / 0.9525 / 0.9962** at σ = 0.001 / 0.01 /
0.1 / 1.0 over 100k draws each, every one within Monte-Carlo error of 1.00, with
`P(E > 20)` ≈ 0.0035–0.0039.

**Headline values for the one clearing cell**: `degradation_regressor_p10` pinball
**0.455799 → 0.443910** (arm C, −0.011889 = improvement); its permutation arm lands at
0.453322, so **79%** of the raw gain survives the shuffle correction.

#### 5. The cell that clears is the confound arm, and the build session predicted it in writing

`int_lap_corner_drift.sql`'s own header, written 2026-09-22 *before* any arm ran:

> *"a model handed `corner_drift_coverage` as a bare number is free to relearn 'how far into the
> stint am I' through it rather than through the drift values themselves. That is exactly the
> shape `02c`'s confound arm (arm C) existed to isolate, and this item's own arm C repeats the
> test against the new confound."*

It is the only arm that clears anything. Taken apart on the 119,775 training-eligible rows:

* The mart `COALESCE`s the column to **0.0**, not NULL. It is **0.0 on 31,999 rows**, of which
  **29,705 (92.8%)** sit at `valid_lap_in_stint ≤ 6` — inside the baseline-defining window — and
  only **2,294 (7.2%)** are zero for the telemetry reason `02c`'s coverage column exists for.
* It is **> 0 only at `valid_lap_in_stint ≥ 7`**, minimum exactly 7. **No forward reach**: a row
  at valid lap ≥ 7 is in a stint that has already had ≥ 7 valid laps, so the column never
  discloses the stint's eventual length. Gate 5 is re-confirmed at the arm level, not merely at
  build time.
* It correlates **+0.5608** with `valid_lap_in_stint`, **+0.5232** with `age_in_stint` and
  **+0.5374** with `lap_in_stint` — against `02c`'s `corner_input_coverage` at **+0.0779** and
  **+0.0876**. Regressed on `age_in_stint` + `lap_in_stint`, `corner_drift_coverage` gives
  **R² = 0.290**; `02c`'s gives **R² = 0.010**. It is roughly thirty times more of a stint clock
  than the column it was modelled on.

**So what is the residual 71% that the contract does not already hold?** A *green-flag* lap
count. `valid_lap_in_stint` excludes safety-car, pit and out-laps; the contract carries
`lap_in_stint`, `age_in_stint` and `lap_number` but **no valid-lap count at all**. Regressing
`valid_lap_in_stint` on those three gives **R² = 0.95 with a residual sd of 2.281 laps**, and
the raw and valid counts differ on **98.87%** of rows (mean absolute gap **2.089 laps**). Arm C
is a one-column proxy for *how many racing laps this stint has actually run*, which is a
**stint-interruption channel, not a corner-telemetry channel** — its corner content is the 7.2%
of zeros that are telemetry-driven, and that is the part `02c` already tested and found weak.

Its marginal correlation with the label is **−0.0352**, against `corner_input_coverage`'s
**−0.1327** on the same population. The clear is not coming from the corner sensor.

#### 6. The declared readings, applied family by family

The pre-registration's four cases, applied as written:

* **"A and/or B clears on the degradation trio, C does not → the drift mechanism is
  supported."** **Did not occur, on any family.** A and B clear **0 of 8** trio cells and 0 of
  12 overall. This was the item's primary hypothesis and it is the case that did not fire.
* **"C clears, A/B do not → the group is a stint-progress/coverage proxy, not a driver-input
  drift signal."** **This is the case that fired**, on p10. It is a pre-declared reading and it
  is negative for the item: the arm that clears is the one built to catch the confound, and §5
  identifies the confound concretely.
* **"A clears but neither B nor C does → ambiguous."** Did not occur. A clears nowhere, and on
  p10 — the one family with a clear — it is C that clears and A that misses, which is the
  *opposite* of the Phase 10a bundle shape. **Nothing in this item is recorded as ambiguous**,
  unlike `02c`, where two of three clears were bundle-clears with neither half clearing.
* **"Nothing clears → Tier 2 is closed for good."** Did not fire literally — one cell clears —
  but it clears on the confound arm, so the *substantive* conclusion this branch draws is
  reached anyway by the branch that did fire. §11 records that distinction rather than
  collapsing it.

The one cell not covered by any declared case is **p50 arm B: information +1.23× with raw
+0.34×.** Information without raw is not a clear under `gates.md`, and it is recorded as a
miss, not promoted. It is worth one line only because it is the same family and the same arm
shape that produced `02c`'s single unambiguous mechanism clear — and here the raw delta is a
quarter of what it needs to be.

#### 7. Gate 7 — the e-values, and the first non-barred e-BH reading in group `02`

Construction B (paired safe-t), **n = 10, g = 1**, seeds 20260528–20260537, the ten nesting the
floor's five, exactly as pre-registered 2026-09-22 under `09c`'s post-2026-09-19 rule.
`E_max(10,1) = 11^4.5 = 48,558.70`. Sorted descending the twelve `E`s run **743, 209, 35.3,
5.21, 2.90, 2.88, 2.63, 1.28, 1.01, 0.859, 0.740, 0.351**.

**Four of the twelve point against the feature** and must not be read as support: p90 C
(35.3, `d̄` = −0.00264), p10 B (5.21, `d̄` = −0.00108), p90 B (2.90), p90 A (2.88). Construction
B is symmetric in `t`, so a consistently negative delta returns a large `E` too; the direction
flag is carried beside the number rather than folded into it, per `02d`'s handling.

**Against the pre-registered family, e-BH rejects nothing.** The registration declared
`m = 135` (`09c`'s 103 + `02d`'s 20 + this item's 12) and a lone-rejection bar of
`20·(135+1) = 2,720`. `k* = max{k : E_[k] ≥ 135/(0.05k)}` needs **2,700** at k = 1 and 1,350 at
k = 2; the largest `E` observed is **743**. **`k* = 0`.**

Reported for completeness and *not* as the declared family: taken against this item's own twelve
hypotheses alone, `k* = max{k : E_[k] ≥ 12/(0.05k)}` gives **k\* = 2** (743 ≥ 240, 209 ≥ 120,
35.3 < 80) — rejecting p10 C and p10 A. **This is the first time an item in group `02` has
produced a non-zero `k*` at all**: `02b` and `02c` were capped at `E_max(5,1) = 36` and were
structurally unable to reject whatever they measured, and `02d`'s three bar-clearing `E`s all
pointed the wrong way. `09c`'s headroom is real and it worked. But the family this item declared
in advance is 135, not 12, and **the operative answer is `k* = 0`** — choosing the smaller family
after seeing which numbers came out large is precisely the selection the gate exists to remove.

Note also that **p10 arm A returns `E` = 209 while failing its floor on both raw (+0.86×) and
information (+0.67×)**. That is `gates.md`'s *"two instruments, not one"* in its cleanest form:
ten paired seeds agree the arm is not exchangeable with its own shuffle (`d̄` = +0.00509,
`s_d` = 0.00266, `t` = +6.05), and the effect is still smaller than a reseed of the same model.
Reproducible and too small to matter are not in conflict.

**Family accounting.** These are **twelve newly declared hypotheses** (3 arms × 4 families),
declared 2026-09-22 and counted, bringing the count-forward convention's running total to
**m = 135** as the registration states. This is not an independent re-audit of the campaign
family — `04c`'s recount over every declared `E` remains undone, per `02b` §11(c) and `09c`.
`09c` §2's open question of whether the permutation arm counts separately is untouched; `k*` is
0 under either reading. Arm D (corner-type split) was never registered for this item and remains
non-existent, not merely unrun.

#### 8. Head to head: does drift beat `02c`'s instantaneous residuals?

**No, on both instruments, and the comparison is like-for-like** — same substrate, same split,
same floors to 8 dp, same four families, same arm shapes, eleven hours apart.

| | `02c` instantaneous residuals | **`02h` early-stint drift** |
| :--- | :--- | :--- |
| persistence of the 9 aggregates | 0.0267 – 0.1756 | **0.0169 – 0.1397** (worse) |
| cells clearing, of 12 | 4 | **1** |
| of which mechanism arms (A/B) | 3 (p10 A, p50 A, p50 B) | **0** |
| of which unambiguous mechanism cells | 1 (p50 B, +1.19× raw) | **0** |
| of which the confound arm C | 0 | **1** (p10, +2.00× raw) |
| e-BH `k*` vs declared family | 0 (structurally barred, cap 36) | **0** (cap 48,558; 743 observed) |

`02c`'s nine residuals clear on their own on p50. `02h`'s three phase-mean drifts clear nowhere,
and its full ten-column bundle clears nowhere. **The one thing `02h` adds over `02c` is a better
stint clock, which is not what it was built to add.**

One honest qualification in the other direction, since the pre-registration made a
cross-population comparison that this run can tighten. Marginal `|corr|` with the label,
recomputed for both column sets on the **same** 119,775-row population (the `02c` Verdict §9
figures are on a different, 95,346-row population and are not comparable to these):

| phase | `02h` drift | `02c` residual |
| :--- | ---: | ---: |
| braking mean | **−0.1182** | −0.0729 |
| mid mean | **−0.1959** | −0.1709 |
| mid max | −0.1920 | **−0.2264** |
| exit mean | **−0.0817** | −0.0460 |
| coverage | −0.0352 | **−0.1327** |

So drift is *marginally* the slightly better-correlated construct on three of four phase
columns. **It buys nothing once a booster already holds the 32-column contract** — which is the
whole point of an add-ablation, and the reason a marginal correlation was never the test.

#### 9. Coverage and the missingness bias, on the arms' own population

Re-confirming the pre-registration's build-time numbers on the population the arms scored:
mean `corner_drift_coverage` **0.6020** (vs `02c`'s `corner_input_coverage` **0.7986**);
per-phase non-null share at lap grain braking **73.17%**, mid **73.28%**, exit **67.36%**,
against `02c`'s 95.84% / 96.01% / 89.84%. The drift columns are missing on roughly a quarter of
training-eligible laps where `02c`'s are missing on 4% — 23.70% of stints never reach 7 valid
laps, and every stint loses its first six.

The missingness remains **not label-neutral**, the same direction every prior item in this group
found: covered rows average **−0.5552 s** of 5-lap jump (sd 3.827) against **−0.2158 s**
(sd 5.130) for NULL rows. That is a coverage artefact, not forward leakage — the baseline window
is fixed at valid laps 1–6 and settles strictly before any lap it is later subtracted from, and
§5 re-verified the minimum at exactly 7 — and it is the reason arm C exists. **Unlike `02c`,
where the confound arm did not fire, here it is the only thing that does.**

#### 10. What this item does and does not conclude

* **Verified, and it is the item's own hypothesis being falsified.** Residualizing against the
  driver's own early-stint baseline does **not** recover the persistence `02c`'s pace residuals
  lacked. It reduces it: 0.0169–0.1397 against 0.0267–0.1756, on the audit's own statistic,
  reproduced to its published anchors.
* **Verified.** The drift columns carry nothing the `v13` contract does not already have, on any
  of four families, in either the 10-column or the 3-column form. Seven of twelve raw deltas are
  negative.
* **Verified, and it is a confound, not a finding about corners.** `corner_drift_coverage`
  clears on p10 (+2.00× raw, +1.59× information, `E` = 743) because it is a green-flag lap
  counter, correlating +0.5608 with `valid_lap_in_stint` — a quantity the contract holds only to
  R² 0.95 with a 2.281-lap residual.
* **Not established, and deliberately not pursued here.** Whether a *properly built*
  `valid_lap_in_stint` / stint-interruption column belongs in the contract. Arm C is evidence
  that something in that channel is live on p10, and it is evidence on one family of four with
  the other three flat-to-negative (p50 −0.74×, p90 +0.12×, cliff −0.10×). If that channel is
  wanted it should be registered and built as what it is — a stint-geometry feature from
  `int_stint_geometry` — not admitted as a corner-telemetry coverage fraction that happens to
  encode it. **That is a new item, not this one**, and nothing here pre-registers it.
* **Not done here.** The contract is unchanged. All ten columns are in the mart and absent from
  `ml/src/schema.py`'s `FEATURE_COLUMNS`, where they were before this session and where this
  item leaves them.
* **The R5 cap stands, and this is the fourth data point for it.** Phase 9 dropped eleven scalar
  summaries of this table for clearing in none of three families; `02c` returned one unambiguous
  mechanism cell of twelve; `02h` returns **zero** of twelve, for a 64-minute, 368-fit campaign.
  R5's reading that *the aggregation is lossy, not the channel* now survives a test specifically
  designed to rescue the aggregation by changing its reference point. R5 Option A (path
  signatures) and Option B (FPCA on the existing 100-fraction `relative_distance` grid) remain
  the only standing proposals for this sensor.
* **Correction owed to two model headers.** `int_corner_drift_from_early_stint.sql` and
  `int_lap_corner_drift.sql` both assert that drift *"persists by construction."* §0 measures
  that claim false. The SQL is left untouched by this session — it is correct as built and the
  claim is in a comment, not in logic — but the assertion must not be re-quoted, and a later
  session touching either model should strike it.

#### 11. Ruling — `CLOSED`

**`CLOSED` 2026-09-22. The corner-drift line of work is finished, and it is a clean negative.**

Gates 1–4 and 7 ran with no skips and are reported in full above. Gate 1 PASS on all four
families to 10 dp. Gate 3 floors measured in-run and reproducing `02c`'s to 8 dp. Gate 4
permutation nulls on every arm, capacity and information separated, plus a shuffle-vs-shuffle
negative control per family, all four below `E` = 1. Gate 5 was clean at build time and is
re-confirmed at the arm level in §5 (coverage > 0 only at valid lap ≥ 7). Gate 6 was satisfied
2026-09-22 before the runner executed, and **no arm was added, dropped or reinterpreted after
the fact** — the declared reading that fired is the one recorded. Gate 7 declared at `n=10,g=1`
and reported against the family it was sized against: `k* = 0`.

This closes on a **measurement**, not on a landing, in the same shape `08o` and `08q` closed:
there is nothing to rebuild, nothing to bump and nothing to retrain, because the contract never
moved. The two dbt models and ten mart columns remain built, tested and lineage-clean; they are
left in place as the evidence base for this ruling and as the substrate any future
stint-interruption item would want to read `valid_lap_in_stint` from, but nothing consumes them.

What a later session may quote from this item: §0's persistence numbers as a measurement that
double residualization does not manufacture persistence; §4's ratios; §5's identification of
`corner_drift_coverage` as a green-flag lap counter. What it may **not** quote: arm C's p10 clear
as evidence that corner telemetry helps `degradation_regressor_p10` — it is not a corner result —
and none of the four wrong-direction `E`s as support for anything.

**`02c`'s open question is untouched by this item and still stands**: whether its ambiguous
bundle clears (p10 A, cliff A) justify moving any of *its* ten columns into `FEATURE_COLUMNS`,
given its only unambiguous mechanism cell is p50 arm B. Nothing measured here bears on it —
different columns, different item — and `02c` remains `MEASURED` with the contract unmoved.

**HANDOFF 2026-09-22.** At the user's request, `02c`'s leftover question above is now tracked
as **`D17`** in `build-log.json`'s `decisions[]` — same shape as `D12` for `02b`'s sibling
question — rather than living only in this prose and in three consecutive history
`next_action` fields. `02c` gains `blocked_by_decision: D17`. This item's negative result
means there is nothing cheaper left to measure before ruling `D17`; the only standing
alternative to a straight yes/no is the `R5` Option A/B rebuild `02c`'s own note already names.
The pointer moved off `02c` onto `08i` — the min_observations floor revert, already ruled `YES`
under `D10` and only awaiting execution, first of two `D16`-bundle members (`08i`, `02b`) that
never actually landed despite `08o` and `08q` shipping from the same decision. `D17` does not
block either.

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

### `02d` — Tier 3, SC hazard · REBUILT 2026-09-11, WIRED + ARMS PRE-REGISTERED 2026-09-20, CONCLUDED 2026-09-21

**Status of the two halves.** The expensive half — the expanding, season-lagged rebuild of
`int_sc_hazard_history` — was built 2026-09-11 and is verified. The second half, wiring it
into the feature lineage and ablating it, was done 2026-09-20 and is what this section
records. Nothing below asserts the feature works; the arms decide that.

#### What was built

`int_sc_hazard_history` is keyed `(circuit_slug, season)`, one row per venue per season,
149 rows over 36 circuits, 2018–2024. The row for season *S* is estimated from races at
that venue in seasons **strictly before** *S*, and the empirical-Bayes prior it shrinks
toward is season-lagged with it — shrinking toward an all-time pooled rate would have
leaked the future through the back door, which is the defect the rebuild exists to remove.

Five columns were wired into `fct_cliff_prediction_features` on 2026-09-20, joined
`rtt.circuit_key = sch.circuit_slug AND r.race_year = sch.season`:

| mart column | source | NULL policy |
| :--- | :--- | :--- |
| `circuit_sc_hazard_per_lap` | `sc_hazard_per_lap_shrunk` | NULL where unknowable |
| `circuit_vsc_hazard_per_lap` | `vsc_hazard_per_lap_shrunk` | NULL where unknowable |
| `circuit_any_hazard_per_lap` | `any_hazard_per_lap_shrunk` | NULL where unknowable |
| `circuit_hazard_prior_racing_laps` | `prior_racing_laps` | never NULL, 0 = no prior exposure |
| `circuit_hazard_prior_seasons_n` | `prior_seasons_n` | never NULL, 0 = debut season |

They are in the mart and **not** in `ml/src/schema.py`'s `FEATURE_COLUMNS` — the same
standing `02b`'s seven and `02c`'s ten hold until their arms rule.

**Join verified one-to-one:** 137,447 mart rows in, 137,447 out, 0 unmatched, all 36 mart
`circuit_key`s match a `circuit_slug`, no duplicate `(circuit_slug, season)` keys. The
season half of the key is not optional — a circuit-only join fans out 5–7× *and* reinstates
the leak, so it is now asserted structurally by
`test_the_sc_hazard_join_key_still_carries_the_season`, because neither leakage walker
looks at join keys and both would stay green through that regression.

**Trade-offs taken, and why:**

* **Shrunk rates only, not raw.** The raw rates are NULL on a venue's debut season (36 rows
  of 149). Carrying both would put a *second* missingness pattern in the block on a
  different axis from the first, and two overlapping NaN masks are two confounds to
  disentangle rather than one. Shrinkage is also what the existing dbt consumer
  (`int_pit_strategy_cost_curve`) already reads, so the two consume the same estimator.
* **`any` is carried although it is exactly redundant.** `any = sc + vsc` to 7e-18 —
  measured, not assumed: the onset counts add and the shrinkage priors add with them. It
  stays because a tree cannot form the sum itself, so it is a basis rotation, not new
  information. It should not be read as a third channel.
* **SC and VSC are *not* redundant with each other.** `corr(sc onsets, vsc onsets) = 0.125`
  per race over 149 races. Two channels, measured.
* **NULL, not 0.0, for the rates.** 0.0 would assert "this venue never throws a safety
  car", a measurement nobody made. The cost of that choice is the confound below.

#### The confound, named before the arms run

**The NaN mask of the three rate columns is *exactly* `race_year = 2018`** — verified
programmatically, not inferred: 14,982 of 119,822 training-eligible rows (12.504%), 100% of
2018 and 0% of every other season. 2018 is the earliest season in the warehouse, so no 2018
row has a prior season to estimate from *nor* a prior-season pooled rate to shrink toward.

`race_year` is **not** in the 32-column contract. So this block hands the model a free
season indicator it does not currently have, through its *missingness* rather than through
a value — and **a row-shuffle permutation null cannot destroy it**, because the shuffle
moves the NaNs with the values. `02c` found the identical shape in `corner_input_coverage`
and recorded it; this is its second instance, and the survey it was found through is the
one `08b` built.

Worse, the marginal correlations point the same way `02c`'s did — **the confound channel
out-correlates the mechanism channel**, measured on 119,822 training-eligible rows against
`next_5_lap_cumulative_jump_s`:

| column | marginal \|r\| with the 5-lap label | n |
| :--- | ---: | ---: |
| `circuit_hazard_prior_seasons_n` | **0.0301** | 81,619 |
| `circuit_hazard_prior_racing_laps` | **0.0246** | 81,619 |
| `circuit_sc_hazard_per_lap` | 0.0159 | 70,850 |
| `circuit_any_hazard_per_lap` | 0.0094 | 70,850 |
| `circuit_vsc_hazard_per_lap` | 0.0029 | 70,850 |
| the NaN-mask indicator alone | 0.0059 | 119,822 |

Label means either side of the mask: −0.5377 (sd 4.7785) on the NULL rows against −0.4490
(sd 4.2262) on the covered rows. Milder than `02c`'s split (+1.3926 against −2.3295) but
the same shape, and in the same direction.

One thing that makes the confound arm fair rather than a season dummy in disguise:
`prior_seasons_n` **varies within a season** from 2020 on (min 0 / max 2 in 2020, rising to
min 1 / max 6 in 2024), so it is genuinely a venue-tenure variable. It is still strongly
*correlated* with season — its mean runs 0, 1, 1.00, 1.65, 2.61, 3.41, 4.30 across
2018–2024 — and that is exactly why it needs its own arm rather than a footnote.

#### Pre-registered arms — written 2026-09-20, before any arm was run

Per [`../foundations/gates.md`](../foundations/gates.md) step 6.

**Primary family: `stint_life_regressor`.** This is the one target where §1's within-stint
argument does not obviously cap a circuit-constant feature, because the target is not
shaped like the degradation column: stint life is right-censored on 46.2% of training rows,
stint ends are pit-wall decisions, and `00b` measured that **26.87% of uncensored stint ends
fall on an SC/VSC lap against 6.49% of censored ones, in every season**. `10d`'s bar on this
family was discharged when `10e` LANDED 2026-09-19, so the floor is measured against the
model that is actually shipping.

**Secondary families, declared as secondary and not promoted afterwards:**
`cliff_classifier` and the degradation trio (`p10`/`p50`/`p90`). §1's cap applies to the
trio — a circuit × season constant can only address the 0.94%→6.43% of the target's variance
that is between-stint — so a clear there would be the surprise, not the expectation.

| arm | columns | what it tests |
| :--- | :--- | :--- |
| **A_full** | all five | the group as it would ship |
| **B_hazard** | the three shrunk rates | **the mechanism arm** — safety-car risk itself |
| **C_exposure** | `prior_racing_laps`, `prior_seasons_n` | **the confound arm** — venue tenure, never NULL, no SC mechanism in it |
| **D_unknowable_mask** | one synthetic indicator, `circuit_sc_hazard_per_lap IS NULL` | **the season channel** arm B gets for free through its missingness, isolated |
| **P** | each arm's own columns, row-shuffled jointly in train *and* eval | gate step 4 — capacity and information reported separately |

Plus the shuffle-vs-shuffle negative control on A's columns, as `02b`/`02c` ran it.

**Decision rule, fixed in advance:**

1. **B clears its floor and D does not** → the safety-car mechanism is supported, and `02d`
   is eligible to move into `FEATURE_COLUMNS`.
2. **D clears on its own** → the finding is the 2018 season channel, not safety-car risk.
   `02d` does not ship on it. The available repair is to admit `race_year` to the contract
   on its own merits, or to drop 2018, and both are separate items.
3. **C clears and B does not** → the finding is calendar tenure, not hazard. Same verdict as
   2, and the honest write-up is that Tier 3's channel-novelty argument did not survive.
4. **A clears while B, C and D all fail individually** → the Phase 10a shape, and gates.md
   step 4 exists because that once nearly shipped as a clean information win. It is reported
   as a joint effect and is **not** read as the mechanism.

**Protocol:** gates.md steps 1–4 and 7 — instrument check to 6 dp against the published
v12 headline per family; `cv_final_fold`, train 2018–2023, eval 2024, through
`evaluate.py`'s own `_fit`/`_score`; each family's own 5-reseed floor from
`attribution.refit_noise_floor` at `2*sqrt(2)*sd`; permutation null; and Construction B
(paired safe-t) e-values with the Monte Carlo validity check.

**The e-value construction is sized at `n=10, g=1`, not at `02b`'s and `02c`'s `n=5`.**
This is `09c`'s ruling applied, and it is the reason `02d` `depends_on` `09c`. At `n=5` the
ceiling is `E_max(5,1) = 36`, and gates.md step 7 requires the ceiling to clear
`20*(m+1)` — a construction below that bar cannot produce a lone rejection *whatever the
data show*, which is arithmetic rather than evidence. **Family sized against, recorded as
step 7 requires:** `09c` enumerated **103** declared hypotheses campaign-wide as of
2026-09-19; `02d` declares 4 arms × 5 families = **20** more, so `m = 123` and the bar is
`20*(123+1) = 2,480`. `E_max(10,1) = 11^4.5 = 48,558.70` clears it **19.6×**.

**A decision `09c` left open, closed here.** `09c` noted that Construction B's efficiency at
`n=5` came from reusing the floor study's five seeds, and that at `n=10` "the arm pays 5
(floor) + 20 (paired) = 25 refits rather than 20" unless the floor also moves to ten — then
explicitly left the choice to *"whoever runs the next arm at `n = 10`"*. `02d` is that arm.
**Decided: pay the extra five.** The floor stays at **five** reseeds, exactly as gates.md
step 3 words it, so `02d`'s floor is measured on the same instrument as `02a`'s, `02b`'s and
`02c`'s. Widening it to ten would tighten this item's floor while making its ratios
incomparable to the ones they will be read beside — the same class of mistake `02b`'s
re-score exists to undo. The paired e-value study runs at ten seeds whose **first five are
the floor's five**, so the two studies are nested rather than disjoint, and the assertion
that they nest is in the script rather than in a comment.

**Floors are measured fresh in this run and not reused.** `02b`'s 2026-09-19 re-score found
the reseed floors had moved by up to **3.2×** across the `08m` rebuild, so any figure
borrowed from a pre-`08m` run is void. Nothing in this section quotes one.

#### Gate status

| gate step | status |
| :--- | :--- |
| 1 — instrument check | run per family inside the arms script; abort on failure |
| 2 — add-ablation, identical split | `cv_final_fold`, same split for every family |
| 3 — delta vs that family's own floor | fresh 5-reseed floor per family |
| 4 — permutation null | arm P, capacity and information split |
| **5 — forward-window audit** | **CLEAN.** See below. |
| 6 — pre-registration | this section, written before the arms ran |
| 7 — e-value | Construction B, n=10, g=1 |

**Step 5 is fully discharged and is the item's headline result.** `gates.md` step 5 names
`02d` by name as one of two live instances of "a pooled historical rate leaks the future
into the past". That instance is now closed:

* `assert_sc_hazard_no_forward_leakage` re-derives the entire window from the sources with
  an **inequality join** (`h.season > p.race_year`) rather than a window frame, so a frame
  that silently ends at `CURRENT ROW` instead of `1 PRECEDING` surfaces as a count mismatch
  rather than as a plausible number. It also checks each published rate against its own
  numerator and denominator, and that `prior_racing_laps` is non-decreasing in season.
  **22/22 dbt tests pass** on the model and the mart, including this one and the
  `(circuit_slug, season)` uniqueness combination.
* `python3 -m ml.src.features --check`: **forward-window audit CLEAN, aggregation-scope
  audit CLEAN, leakage guard CLEAN (32 features)**, with the model now inside the audited
  lineage.
* Entering the lineage moved the model out of `08b`'s report-only survey and into
  `audit_aggregation_scope`'s enforced scope, which is the hand-off the survey was built to
  force. Its four non-pinning GROUP BYs are therefore now **ruled in `schema.yml`**, not
  merely quiet: `(race_year, race_id)` twice (both pin a race), `(circuit_slug, race_year)`
  (the deliberate pre-aggregation that forecloses `02g`'s fan-out defect), and `(season)`
  (the pooled EB prior, which pools across circuits by design and cannot pool across seasons
  because season is the key).

**The stale test is fixed.** `ml/tests/test_features.py::test_aggregation_survey_still_names_the_outstanding_instance`
had been red at HEAD since 2026-09-11, asserting that the survey still reported the pooling
defect — a defect that had been fixed the same day. A red test meaning "the bug is gone" is
worse than no test, because the next reader cannot distinguish it from a regression. It is
replaced by `test_the_sc_hazard_instance_left_the_survey_by_being_fixed_not_by_being_hidden`,
which asserts **both** halves the way `02c` did for the corner instance: the model is gone
from the survey by that exact string, *and* it is in the lineage, *and* the real audit is
clean on it — so it cannot be satisfied by a model dropping off the survey while still
carrying the defect. `ml/tests/test_features.py` is **31 passed, 0 failed**.

**Found while closing it, and left open on purpose.** The survey still reports the identical
all-time-pooled shape for **four other models**, none of which feeds a feature today:
`int_driver_circuit_affinity` (3 groups), `int_driver_circuit_era_affinity` (4),
`int_era_normalized_driver_rating` (2) and `int_pit_loss_circuit` (1). They are not live
leaks — they are the survey's advance notice working as designed, and if any is ever wired
into the mart it arrives in `audit_aggregation_scope` automatically and the build stops
until someone rules on it, which is the route `02d` has just taken. Recorded here so the
next reader does not mistake "02d is closed" for "the shape is gone from the warehouse".

**Coverage caveat discharged.** The §4 text above warns that track-status ingestion is
"incomplete for some seasons". Measured: every race with laps has a track-status timeline —
2018 21/21, 2019 21/21, 2020 17/17, 2021 22/22, 2022 22/22, 2023 22/22, 2024 24/24. The
caveat was stale. Timelines are thin on incident-free races (19 carry ≤3 messages), which is
an absence of *events*, not of ingestion, and the numerator counts onsets so it reads those
correctly as zero.

### Verdict — `02d` · MEASURED 2026-09-21

**Tier 3, SC hazard, is ruled out for `stint_life_regressor`.** All four arms make the model
*worse* than the 32-column baseline, and the mechanism arm — the three shrunk hazard rates,
the columns this whole item exists to test — is among them at **−1.86× its own floor**.
Nothing moves into `FEATURE_COLUMNS`. Run: `python3 scripts/arms_02d_sc_hazard.py`,
2026-09-21 10:04 UTC, ~2 minutes. Artefacts: `ml/artefacts/02d_sc_hazard_arms.json`
(per-seed headlines, e-value components, the Monte-Carlo validity check) and `.log`.

This is a null result and it is written up as one. The pre-registration above was built to be
able to say no, and this is it saying no.

#### 1. Gates 1 and 2 — instrument and split

**Gate 1 PASS.** The 32-column refit reproduced the published `v12` headline to six decimals:
`aft_nloglik` **2.1531517215** against **2.1531517215**. That anchors on the model actually
shipping — `10e`'s S1x parameters, landed 2026-09-19 — which is what discharged `10d`'s bar on
this family. The survival branch threads the censoring flags and the model's *fitted* AFT
scale through both fit and score, as `02b`'s runner does; scoring at the module-default scale
would have produced a plausible wrong number rather than an error.

**Gate 2.** `cv_final_fold`, train 2018–2023 (**99,849** rows), eval 2024 (**19,973**),
through `evaluate.py`'s own `_fit`/`_score`, one bundle shared across all four arms and the
control, contract `v12`. The unknowable mask covered **17,380 of 137,447** mart rows
(12.645%), the same channel the confound section above measures as 14,982 of 119,822
*training-eligible* rows (12.504%) — two row sets, one season.

**Only the primary family ran.** The four secondary families declared on 2026-09-20
(`cliff_classifier` and the `p10`/`p50`/`p90` trio) are **unrun**. Four of this item's twenty
declared hypotheses are reported below; sixteen stay open and uncounted, which is legitimate
under stopped e-BH for the same anytime-valid reason `02c` relied on. The ruling below is
scoped to the family that ran and says nothing about the other four.

#### 2. Gates 3 + 4 — every arm, against this family's own floor

Floor measured **fresh in-run**, seeds 20260528–20260532, per this section's own instruction
not to borrow one: headline sd **0.00285720**, `2√2·sd` = **0.00808138** on `aft_nloglik`.
Positive is improvement, i.e. lower NLL. "raw" is the add-ablation delta over that floor,
"capacity" is `shuffled − baseline`, "info" is `real − shuffled`.

| arm | cols | headline (AFT NLL) | raw Δ | raw ×floor | capacity ×floor | info ×floor | E | clears |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| **A_full** | 5 | 2.2246344 | −0.0714827 | **−8.85** | +0.24 | **−9.09** | 42,705 ↓ | no |
| **B_hazard** | 3 | 2.1682181 | −0.0150664 | **−1.86** | +0.04 | **−1.91** | 6,593 ↓ | no |
| **C_exposure** | 2 | 2.2337204 | −0.0805687 | **−9.97** | +0.22 | **−10.19** | 41,169 ↓ | no |
| **D_unknowable_mask** | 1 | 2.1554744 | −0.0023227 | −0.29 | −0.27 | −0.02 | 55.2 ↓ | no |

Baseline for every row is 2.1531517. ↓ = `direction_is_improvement: false`.

**Every delta in the table is negative**, and on three of the four arms the permutation split
puts the damage in *information*, not capacity. Row-shuffled, the same columns leave the
headline where it was — capacity +0.24× / +0.04× / +0.22× floor on A / B / C, every one of
them inside the floor and therefore indistinguishable from a reseed. The loss appears only
when the columns carry their real values. That is the mirror image of the failure mode gate 4
was written to catch: these are not inert columns the booster wastes splits on, they are
learnable, and what it learns from them on 2018–2023 does not transfer to 2024.

**The harness is clean.** The shuffle-vs-shuffle negative control on A's five columns —
H0 true by construction — returned **E = 1.52** (`d̄` = −0.000703, |t| = 1.98), three orders
of magnitude below the rejection bar and an unremarkable draw from a distribution with null
mean 1. The construction's own validity check returned mean `E` = 0.9896 / 1.0314 / 0.9525 /
0.9962 at σ = 0.001 / 0.01 / 0.1 / 1.0 over 100k draws, each within Monte-Carlo error of 1.00,
with `P(E > 20)` ≈ 0.0035–0.0039.

#### 3. Gate 7 — three e-values clear the bar, and all of them point away from the feature

At the pre-registered `n=10, g=1`, `E_max = 11^4.5 = 48,558.70` and the lone-rejection bar is
`20·(123+1) = 2,480`. **A (42,705), B (6,593) and C (41,169) all clear that bar. D (55.2) does
not.** Per `09c`'s non-retroactive landing note, every `E` declared before it was drawn at
`n=5, g=1` and capped at 36, so these are the first arms in the campaign with the headroom to
clear a campaign bar at all — and the rejection is worthless to this item, because **the
direction is against the feature**.

`09c`'s Construction B is symmetric in `t`: a delta that is consistently *negative* across ten
paired seeds produces the same large `E` as a consistently positive one. What these numbers
say is "these columns are not exchangeable with their own shuffle" — and the sign of `d̄` says
which way. A's `d̄` = −0.0795 with `s_d` = 0.0043 over ten seeds, i.e. `t` = −58.7: the
worsening is about as reproducible as anything this campaign has measured. **Reading these E's
as support for `02d` would be a misreading**, and the direction flag is carried beside the
number rather than folded into it because applying a one-sided transform now would be changing
the construction after seeing the data — the one thing that voids an e-value.

So `09c`'s headroom did its job in an unexpected way. `02b` and `02c` could not reject
anything whatever they measured; `02d` at `n=10` can, and what it rejects is its own
hypothesis.

#### 4. The mechanism arm, stated plainly

**B_hazard is the arm this item was built to run, and it is unsupported.** The three shrunk
per-circuit rates — the actual safety-car signal, empirical-Bayes shrunk, season-lagged,
leakage-audited — score **−1.86× floor raw and −1.91× on information**, with capacity at
+0.04× floor. They do not help, and the permutation arm says the harm is in their values.

And B is *not* explainable by the support problem that explains A and C. Its columns are
bounded rates, measured on training-eligible rows:

| column | 2018–2023 range | 2024 range | % of 2024 outside the training range |
| :--- | :--- | :--- | ---: |
| `circuit_sc_hazard_per_lap` | [0.009908, 0.018534] | [0.009232, 0.018288] | 5.51% |
| `circuit_vsc_hazard_per_lap` | [0.006565, 0.017617] | [0.007040, 0.016016] | **0.00%** |
| `circuit_any_hazard_per_lap` | [0.018520, 0.032582] | [0.018503, 0.031239] | 5.08% |

2024's rates sit inside the training envelope, and the small excursions are *below* the
training minimum on two columns, where a tree clamps to its lowest bin. **B is a clean
measurement, and it came back negative.** §4's correction to `ml_research_program.md` §1a
stands as a correction — the warehouse does hold a per-circuit safety-car rate, and the §1a
clause claiming no feature could carry that signal is still false — but the corrected claim
buys nothing for this model. A circuit × season constant, at most 36 distinct values per
season, is too coarse an instrument for a per-stint decision even when the mechanism behind it
is real. Whether a lap-varying or race-varying hazard would do better is a different feature
and a different item; it is not registered here, and folding it in now is the post-hoc
arm-adding gate 6 exists to prevent.

#### 5. A and C fail hardest, and that is a support mismatch, not a finding about tenure

**A (−8.85×) and C (−9.97×) are mechanically contaminated and must not be read as evidence
about venue tenure.** Both carry `circuit_hazard_prior_racing_laps` and
`circuit_hazard_prior_seasons_n`. Both of those columns are **monotone non-decreasing in
calendar time by construction** — they count what has already happened at a venue — and the
split is chronological, train 2018–2023, eval 2024. So the eval fold is systematically off the
end of the training support:

| column | 2018–2023 max | 2024 max | % of 2024 eval rows above the training max |
| :--- | ---: | ---: | ---: |
| `circuit_hazard_prior_racing_laps` | 352 | 423 | **21.50%** |
| `circuit_hazard_prior_seasons_n` | 5 | 6 | **34.89%** |
| either | — | — | **40.28%** |

A gradient-boosted tree cannot extrapolate past a split threshold: every 2024 row above the
training maximum lands in the same terminal region as the training maximum, so more than a
fifth of the eval fold on one column and more than a third on the other are collapsed onto the
boundary and predicted as if 2024 were 2023. **This is a sufficient explanation for A's and
C's anti-clearing on its own**, and it is a property of the feature's shape crossed with the
split, not a measurement of whether venue tenure carries information about stint life. That
question is not answered by this run and should not be quoted from it.

(Support figures re-measured 2026-09-21 on the split as it stands today, which is 19,991 eval
rows against the run's 19,973 — the warehouse moved by 18 rows, 0.09%, after the arms ran. A
difference that size cannot move a 21% or a 35%.)

**This also disposes of a premise the pre-registration built on.** The confound section above
argues C deserves its own arm because `prior_seasons_n` varies within a season and is
therefore "genuinely a venue-tenure variable" rather than a season dummy. That is true and it
is still the right reason to have built the arm — but it is not sufficient. Varying within a
season does not make a column *in support* across a chronological split, and this arm cannot
distinguish "tenure is uninformative" from "tenure is unmeasurable on this split".

#### 6. The pre-registered decision rule: none of its four cases fired

Applying the rule as written, case by case, including where it runs out:

* **1 — "B clears and D does not"** → did not occur. B does not clear; it anti-clears.
* **2 — "D clears on its own"** → did not occur, and this is the one genuinely reassuring
  line in the item. D is the flattest arm in the table (raw −0.29×, information −0.02×, and
  the only `E` below the rejection bar). The 2018 season channel that arrives free through the
  missingness pattern does **nothing** for stint life. `02c` found the analogous confound
  carrying real signal on p90; this one does not, so the NULL-not-0.0 choice recorded above
  cost nothing here.
* **3 — "C clears and B does not"** → did not occur, and §5 is why the rule could not have
  reached it. The rule's case 3 assumed the only way the exposure columns could matter was by
  *clearing*. It never anticipated C failing for a structural reason, which is the outcome
  that actually happened, and so the case is unreachable on this split rather than resolved
  against.
* **4 — "A clears while B, C and D all fail"** → did not occur. A is the second-worst arm.

**The outcome is the undeclared fifth cell: everything moves the wrong way.** It is recorded
as undeclared rather than assimilated to the nearest declared case, which is how `02c` handled
its own undeclared cell. The honest summary is that the rule was written to arbitrate between
three competing *positive* explanations and the data offered none.

#### 7. The contract is unmoved

**`FEATURE_COLUMNS` was not changed by this item and none of the five columns is in it.**
Verified after the run: no column matching `hazard` appears in `ml/src/schema.py`'s
`FEATURE_COLUMNS`. The contract did move on 2026-09-21 — 32 → 39 — but that is `02b`/D12
admitting the seven qualifying columns for `cliff_classifier` only, and
`PER_TARGET_FEATURE_MASK` masks `stint_life_regressor` back to **32**, which is the width this
run's baseline was measured at. The five sc-hazard columns stay in
`fct_cliff_prediction_features` and out of the contract, with this Verdict as the reason.

#### 8. Ruling

**`MEASURED` — Tier 3, SC hazard, is ruled out for `stint_life_regressor`.**

Gates 1–5 run and clean: instrument check to 6 dp; identical `cv_final_fold` split; fresh
per-family floor; permutation null on every arm; and the forward-window work above —
22/22 dbt tests, `features --check` clean on the forward-window, aggregation-scope and leakage
audits. Gate 6 satisfied: the arms were written 2026-09-20 21:55 and ran 2026-09-21 10:04 UTC.
Gate 7 declared at `n=10, g=1` per `09c` and reported in full, including the direction that
makes three bar-clearing e-values count against the item rather than for it.

What a later session may quote from this: B's `−1.86×` as a measurement that the per-circuit
safety-car rate does not help remaining stint life. What it may **not** quote: A's or C's
ratios as evidence about venue tenure, and none of the four e-values as support for anything.

**`gates.md` step 5's `02d` instance is closed** — the pooled-rate leak is rebuilt, audited and
in the enforced lineage — **and that closure is independent of this null result.** The rebuild
was worth doing whether or not the feature cleared; a leaking feature that had cleared would
have been the expensive outcome.

Left open on purpose: the four secondary families, unrun and uncounted. §1's within-stint
argument caps them — a circuit × season constant can reach only the between-stint share of the
degradation target's variance — so a clear there would be the surprise. They are not scheduled
by this Verdict.

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
