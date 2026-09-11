# 07 — Causal pit timing: the safety car as a natural experiment

**Group:** 07 · **Depends on:** `00b` (landed) · **Cost:** hours → 1–2w
**Parallel to the ML ladder.** Uses the warehouse, not the feature contract.

The highest-value research direction in the programme, and it exists because of a number
measured on 2026-09-07 while closing `00b`.

## The problem this solves

`int_pit_strategy_value` is honest about its own limit — its header says *"counterfactual cost
calculation, not causal inference"*. It scores the actual pit lap against a modelled tyre
optimum. That is a **descriptive** gap, and it cannot separate two very different worlds:

- late pitting *caused* the lost time, or
- the car was already struggling, which is *why* it was still out there.

Teams do not pit at random. Every naive comparison of early vs late pitting is confounded by
the state that produced the decision. This is the reason `06a` can publish a distribution but
not a claim about what teams *should* do.

## The identification

**Verified 2026-09-07 (`00b`), re-verified 2026-09-10 (`07a`).** 26.87% of uncensored stint
ends (a real pit decision, n=5,360) fall on a lap flagged `is_safety_car_lap` or `is_vsc_lap`,
against 6.49% of censored stints. Present in all seven seasons, **19.17–35.69%** (2019 low,
2020 high).

> The range above read "21–36%" until `07a` re-ran it. Measured under the same predicate that
> produces the 26.87% headline it is 19.17–35.69%, and no other predicate reproduces 21–36%
> either: on `end_regime IN ('safety_car','vsc')` the range is 16.87–28.62%, and on
> `end_regime <> 'green'` it is 19.17–38.89%. The claim the range supports — present in every
> season, never small — is unaffected. `scratchpad/p0_instrument_check.py`.

A safety car is deployed because **another driver** crashed or stopped. Conditional on a given
car's own tyre state, its arrival is close to exogenous — it assigns an earlier pit than the
team planned. That is an instrument for pit timing, and the first stage is large.

## Threats to identification — name them before running anything

Not incidental. Each needs a stated treatment or the design is decorative.

1. **SCs are not unconditionally random.** They cluster on street circuits, in rain, and on
   lap 1. Condition on circuit, era and `rainfall_flag` (`int_track_evolution`) at minimum.
2. **Common shock.** Under an SC the whole field pits, and the pit-lane time loss itself
   falls. So the treatment bundles "pitted earlier" with "pitted cheaply". Separating them is
   the core design problem, not a caveat to mention at the end.
3. **The excluded restriction is the weak point.** An SC affects the outcome through channels
   other than pit timing — field compression, position changes, tyre temperature on the
   restart. State plainly which outcome the exclusion is defensible for. It is far more
   defensible for a *pace/degradation* outcome than for finishing position.
4. **Censoring.** 46.2% of stint-life rows are right-censored. The estimand must be defined
   on stints that had a real decision, per `00b`'s censoring split.

## 07a — Feasibility, before any estimator

**Objective.** Establish whether the first stage survives the conditioning, before a week is
spent on the design.

**Method.** Read-only. Count matched pairs: same circuit, same era, similar tyre age and
similar pre-SC degradation state, one arm SC-assigned and one not. Report how many survive,
and how thin the thinnest identifying cell is — the same shape of go/no-go `03a` runs for the
mover panel.

**Definition of done.** A matched-pair count with the conditioning set stated; a go/no-go on
`07b`; and if no-go, the reason recorded so it is not re-proposed.

### 07a pre-registration — written before any count was run

Per [`../foundations/gates.md`](../foundations/gates.md) step 6. Everything below was fixed on
2026-09-10 before the counting script existed. Only two things were known at the time it was
written: the `00b` headline reproduces exactly from the warehouse (below), and three
*coverage* facts established by a schema probe that returned no result of interest —
`int_lap_residual_decomposed` holds 137,447 rows and **zero** SC or VSC laps, lap-grain
`rainfall_flag` is NULL on 39,035 of 162,729 `int_stint_geometry` laps, and `race_to_track`
resolves 148 of the 149 races the geometry table carries.

**Instrument check first (gate 1 substitute).** `00b`'s published numbers must come back out of
the warehouse before anything is built on them. Ran, and they do, to the stated precision:
5,360 uncensored / 2,973 censored stints; **26.87%** of uncensored stint ends carry
`is_safety_car_lap OR is_vsc_lap` against **6.49%** of censored; **46.26%** of
`is_training_eligible` mart rows sit on a censored stint. Script:
`scratchpad/p0_instrument_check.py`.

**Population.** Uncensored stints only — `int_stint_end_regime.is_censored_stint = FALSE`,
n=5,360. This is threat 4 discharged at the population level, not as a covariate: a censored
stint ended at the flag or at retirement and never contained a pit decision, so it cannot be
in the estimand's domain.

**Unit of observation — a refinement of the method above, logged as a deviation.** The leaf
doc said "count matched pairs … one arm SC-assigned and one not" without naming the unit. It
is fixed here as the **(stint, lap) risk-set moment**, not the stint. The stint-level reading
is unusable: matching a treated stint to a control stint on tyre age *at the end* conditions
on the outcome, because stint length is what pit timing determines. The risk-set moment is
pre-treatment by construction. The stint-level count is still reported alongside, labelled as
the naive comparison it is.

**Panel.** One row per (stint, lap) over `int_stint_geometry` for every lap of every uncensored
stint. Geometry, not `fct_cliff_prediction_features`: the ML mart carries exactly the 137,447
green laps and would delete the instrument.

- `Z = 1` iff the lap carries `is_safety_car_lap OR is_vsc_lap` — the identical predicate `00b`
  measured 26.87% with. `Z = 0` otherwise.
- `pit = 1` iff the lap is the stint's chronologically final lap. Every uncensored stint
  contributes exactly one. This is the discrete-time pit hazard.

**Conditioning ladder, loose to strict.** Each rung adds one covariate and nothing is dropped.

| Rung | Cell definition |
| :--- | :--- |
| L0 | none — the unconditional first stage |
| L1 | circuit (`race_to_track.track_id`, 36 tracks) |
| L2 | + era (`race_year < 2022` vs `>= 2022`; the repo's own `era_boundary` from `mart_degradation_history_envelope.sql`) |
| L3 | + wet race (`MAX(int_track_evolution.rainfall_flag)` over the race) — **the leaf doc's stated minimum** |
| L4 | + tyre-age bin (`age_in_stint` in 1–5 / 6–10 / 11–15 / 16–20 / 21–25 / 26+) |
| L5a | + realised pre-SC degradation-state tercile |
| L5b | + ex-ante degradation state (`laps_past_cliff` in ≤0 / 0–3 / 3–6 / >6), as an alternative to L5a |
| L6 | L5a + compound — one rung past what the leaf doc asks, to show where it goes if a referee tightens further |

**Deviation on rainfall, logged.** The leaf doc names `int_track_evolution.rainfall_flag`.
Lap-grain it is NULL on 24% of geometry laps, because `int_track_evolution` drops
`low_sample_flag` laps and a neutralised lap is exactly the low-sample case — so lap-grain
rainfall would delete a quarter of the panel, and non-randomly. Race-grain (`MAX` over the
race) is substituted. Same column, same table, coarser grain.

**Realised pre-SC degradation state.** `deg_state_s(ℓ) = mean(driver_skill_residual_s) over the
last 3 available laps strictly before ℓ − mean over the stint's first 3 available laps`, from
`int_lap_residual_decomposed`. Differencing against the stint's own opening pace removes the
driver and car level, leaving how much this set has fallen away. It reuses the column and the
trailing-3 window that `fct_stint_features.end_of_stint_pace_falloff_s_per_lap` already
regresses. It cannot be contaminated by the neutralisation, because that table holds no
SC/VSC laps at all. Terciles over the risk-set panel. Moments with fewer than 4 prior
available laps get NULL and fall out of L5a; that attrition is reported, not absorbed.

**What is counted at each rung.**

1. **Identifying cells** — cells holding at least one `Z=1` and at least one `Z=0` moment.
2. **Matched pairs** — `Σ min(n_Z1, n_Z0)` over identifying cells. The 1:1 matching bound.
3. **Instrument retention** — share of all `Z=1` moments that land in an identifying cell.
   This is the quantity the go/no-go actually turns on.
4. **Thinnest identifying cell** — `min` over identifying cells of `min(n_Z1, n_Z0)`.
5. **Concentration** — share of retained `Z=1` mass in the top 10 cells. An instrument that
   is really one wet Monaco is not an instrument.
6. **Stratified first stage** — Mantel-Haenszel pooled pit-hazard risk ratio and risk
   difference over identifying cells.

**Robustness row.** The ladder again with `Z=1` restricted to the **onset** lap of a
neutralisation within a stint. Laps 2+ of a running SC are not fresh assignments.

**Pre-registered thresholds. These are the decision rule, fixed now.**

- **GO on 07b** — at L5a: instrument retention ≥ 30%, matched pairs ≥ 500, and the MH pooled
  first-stage risk ratio ≥ 2.0.
- **CONDITIONAL GO** — the three hold at L3 or L4 but fail at L5a. 07b is viable, but its
  conditioning set is capped at the rung that held, and the write-up must say that pre-SC
  degradation state is unmatched.
- **NO-GO** — any of the three fails at **L3**, the leaf doc's own stated minimum. Retention is
  the binding threshold; 500 pairs is deliberately a low bar so that a pass on pairs alone
  cannot rescue a shattered instrument.

**Gate substitutions, declared here rather than claimed afterwards.** Gates 2 and 3 are refit
gates and there is no fit in a counting exercise; substituted by computing every rung on one
identical panel with only the cell definition changing, so rungs are comparable to each other
and to nothing else. Gate 4's permutation arm is run in its proper spirit: `Z` is shuffled
**within cells**, preserving cell sizes and the conditional `Z` rate exactly, and the MH risk
ratio must return to 1.0 — if the counting machinery manufactures a contrast out of shuffled
assignment, every number above is an artefact. Gate 5 is run as a mechanical assertion that
every input to `deg_state_s(ℓ)` comes from a lap strictly before ℓ. Gate 7 is not applicable:
07a declares no hypothesis whose e-value enters the campaign family — it is a feasibility
count and enters nothing. 07b must declare one.

### 07a results — 2026-09-10

Every number below was computed on `data/dev.duckdb` read-only by
`scratchpad/p2_ladder.py`, `p3_diagnostics.py`, `p4_attrition.py`, `p5_attrition2.py`. The
scripts are throwaway and are not in the repo.

**The panel.** 90,597 (stint, lap) risk-set moments over the 5,360 uncensored stints. 6,967
carry `Z=1` (7.69%); 83,630 carry `Z=0`; 5,360 are pit moments, one per stint.

Internal consistency check, and the reason to trust the panel: 1,440 of the 6,967 `Z=1`
moments are pit moments, and 1,440 / 5,360 = **26.87%** — `00b`'s headline falls straight out
of the risk-set construction rather than being asserted alongside it.

**Unconditional first stage (L0).** Pit hazard 0.2067 under `Z=1` (1,440 / 6,967) against
0.0469 under `Z=0` (3,920 / 83,630). **RR 4.41, RD +0.160.**

**Ladder A — `Z` = any SC/VSC lap.**

| Rung | cells | identifying | panel n | Z=1 retained | retention | pairs | thinnest | top-10 share | MH RR | MH RD |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| L0 none | 1 | 1 | 90,597 | 6,967 | 100.0% | 6,967 | 6,967 | 100% | 4.41 | +0.160 |
| L1 +circuit | 36 | 35 | 90,066 | 6,914 | 99.2% | 6,914 | 33 | 45.1% | 4.40 | +0.158 |
| L2 +era | 59 | 56 | 90,066 | 6,914 | 99.2% | 6,914 | 1 | 36.1% | 4.47 | +0.159 |
| **L3 +wet race** | 71 | 63 | 90,066 | 6,914 | **99.2%** | **6,914** | 1 | 34.8% | **4.41** | +0.159 |
| L4 +tyre-age bin | 435 | 269 | 90,066 | 6,798 | 97.6% | 6,620 | 1 | 20.1% | 6.56 | +0.173 |
| **L5a +realised deg tercile** | 939 | 302 | 63,047 | 2,166 | **31.1%** | **2,059** | 1 | 18.6% | **7.42** | +0.304 |
| L5b +ex-ante `laps_past_cliff` | 821 | 254 | 63,047 | 2,185 | 31.4% | 2,108 | 1 | 20.0% | 7.38 | +0.296 |
| L6 L5a +compound | 2,270 | 431 | 63,047 | 2,132 | 30.6% | 1,905 | 1 | 17.2% | 9.32 | +0.327 |

**Ladder B — `Z` = neutralisation onset lap only** (non-onset SC laps removed from the risk
set; 2,953 onset moments). Same shape, stronger throughout: L3 retention 98.8% / 2,917 pairs /
RR 6.95; L5a retention 37.9% / 1,108 pairs / **RR 9.65**, RD +0.402; L6 RR 11.20.

**The first stage does not weaken under conditioning — it strengthens.** RR goes 4.41 → 4.41 →
7.42 → 9.32 as the conditioning tightens. That is the opposite of the failure this item was
run to look for, and it has a plain reading: unconditionally, most at-risk moments are
early-stint laps where nobody pits under any regime, which drags the `Z=0` hazard down and
flatters nothing. Once tyre age and degradation state are held fixed, the `Z=0` arm is
comparing against cars that were genuinely in the pit window, and the SC still moves the
decision by a factor of seven.

**L5b is not an independent confirmation.** `laps_past_cliff` is carried forward by the same
ASOF join from the last green lap before ℓ — it had to be, because
`int_lap_residual_decomposed` holds no SC laps — so L5a and L5b are eligible on exactly the
same 63,047 moments and differ only in how those moments are binned. That they agree
(7.42 vs 7.38) says the result is not an artefact of the tercile cut points; it does not say
the degradation state was measured two independent ways.

**Retention decomposes, and the decomposition is the finding.**

| | count | |
| :--- | ---: | :--- |
| all `Z=1` risk-set moments | 6,967 | |
| … with `deg_state_s` defined | 2,190 | **31.4%** — covariate attrition |
| … landing in an identifying cell | 2,166 | **98.9%** of those — cell thinning |
| net retention | | 31.1% |

The 99.2% → 31.1% fall between L4 and L5a is **not conditioning shattering the sample.**
Conditional on the covariate existing, 98.9% of treated moments still find a control in their
own cell. The loss is missingness in the covariate itself: `deg_state_s` needs four prior
green laps in the stint, so it is **0% defined for `lap_in_stint ≤ 5` by construction**, and
61% of `Z=1` moments (4,253 / 6,967) sit there against 22.6% of `Z=0` moments. Part of that is
mechanical — a car that pits under an SC starts a new stint whose first laps are still
neutralised — but not all of it: those early moments carry 626 real SC pit decisions.

Net, L5a keeps **750 of the 1,440 SC-driven pit decisions (52.1%)** and 3,355 of 3,920
green ones (85.6%).

**Thinnest identifying cell is 1 from L2 onward — but the distribution is what matters.**

- **L3**, 63 identifying cells: `min(n1,n0)` median 95, p25 59, p75 152, max 302. 99.8% of
  retained treated mass sits in cells with `min ≥ 20`. This rung is not thin anywhere.
- **L5a**, 302 identifying cells: `min(n1,n0)` median 4, p25 2, p75 8, p90 16, max 53. Cells
  with `min ≥ 5` number 134 and hold 80.8% of retained treated mass; `min ≥ 10`, 70 cells and
  61.7%; `min ≥ 20`, 23 cells and 32.4%.

So L5a is thin *per cell* while being adequate *in total*, and top-10 concentration is 18.6% —
the instrument is spread across the calendar, not one wet Monaco.

**Permutation null (gate 4 substitute).** 200 within-cell shuffles of `Z` at L5a, seed
`20260528` (`ml/src/schema.py::RANDOM_STATE`). Null MH RR mean **0.9933**, sd 0.0711, range
[0.773, 1.189]; null MH RD mean −0.00066, sd 0.00617. Observed RR 7.4225 sits **90.4 null-sd**
above the null mean and 0 of 200 permutations reach it. The counting machinery does not
manufacture a contrast out of shuffled assignment.

**Forward-window assertion (gate 5 substitute).** 0 of 63,047 covariate-defined moments have a
degradation source lap at or after the moment itself.

**The naive stint-level comparison, for contrast.** 5,360 uncensored stints, 1,156 treated
(`end_regime` SC/VSC), 4,204 control. Circuit only: 34 identifying cells, 1,137 pairs. +era: 55
cells, 1,101 pairs. Adding the tyre age *at the stint end* — which is post-treatment, and is
why the risk-set unit was substituted — gives 184 cells and 676 pairs at 81% retention. Every
one of these numbers is smaller than the risk-set count and the last is not identified at all.

**Four things 07b inherits, none of them blocking.**

1. **Red-flag contamination of the control arm.** 103 `Z=0` moments are red-flag-only laps and
   **all 103 are stint ends** — pit hazard 1.000 against 0.0457 for clean green control
   moments. A red flag is the same free stop an SC is. It is 0.12% of the control arm so it
   biases the first stage *down*, but 07b must fold red flag into `Z` or drop those moments,
   not leave them as controls.
2. **`race_to_track` misses 2018_14** (927 geometry laps, 531 uncensored risk-set moments).
   Those moments drop out from L1 onward. Immaterial here; fix or exclude explicitly in 07b.
3. **Conditioning on pre-SC degradation costs 47.9% of the treated pit decisions**, and it
   costs them non-randomly — they are the early-stint ones. 07b either accepts a restricted
   estimand (a LATE over stints past their fifth lap) and says so, or builds a degradation
   measure that is defined from lap 2.
4. **Exact-cell matching at L5a will not do.** 19.2% of retained treated mass is in cells with
   `min(n1,n0) < 5`. 07b needs coarsened matching, a propensity score, or regression-adjusted
   stratification — a design choice, not a sample problem.

### 07a verdict — GO on 07b

Against the thresholds fixed before the counts were run:

| Pre-registered test | Threshold | L3 | L5a | |
| :--- | :--- | ---: | ---: | :--- |
| Instrument retention | ≥ 30% | 99.2% | 31.1% | pass |
| Matched pairs | ≥ 500 | 6,914 | 2,059 | pass |
| MH pooled first-stage RR | ≥ 2.0 | 4.41 | 7.42 | pass |

All three hold at the strictest declared rung, so the rule returns **GO**, not conditional go.
The one marginal number — 31.1% retention against a 30% threshold — is the one that decomposes
into 31.4% covariate availability × 98.9% cell survival, so it is a missing-covariate result
and not the shattering the threshold was written to catch. Had the threshold been applied to
cell survival, which is what "does conditioning shatter the sample" actually asks, it would
have passed at 98.9%.

**What this verdict is, and is sharply not.** It rules on threat 1 and threat 4 only.

- **Threat 1 (SCs are not unconditionally random)** — discharged. Circuit, era and rainfall
  cost 0.8% of the instrument (53 of 6,967 moments, all of them the 2018_14 rows that have no
  `race_to_track` circuit). Tyre age then costs 1.7% (6,914 → 6,798), and degradation state a
  further 1.1% of the moments that have it (2,190 → 2,166).
- **Threat 4 (censoring)** — discharged by construction, at the population level rather than
  as a covariate: the panel is the 5,360 uncensored stints and nothing else.
- **Threat 2 (common shock — the SC bundles "pitted earlier" with "pitted cheaply")** —
  untouched, and it is now the binding problem. It is not a sample-size problem, and 2,059
  matched pairs do nothing about it. 07b's design stands or falls here.
- **Threat 3 (exclusion restriction)** — untouched. Still to be argued for one named outcome,
  and per the section above it is defensible for a pace/degradation outcome and not for
  finishing position.

**What would overturn this.** (a) The pit hazard under `Z=1` proving to be mechanical rather
than behavioural — if `is_safety_car_lap` on an in-lap were being set *by* the pit stop rather
than by the race control message, the first stage would be definitional. `stg_race_control`
landed recently and was not consulted here; deriving the SC flags from race-control messages
rather than from `track_status` would settle it. (b) A demonstration that the 47.9% of treated
pit decisions dropped at L5a differ systematically in the outcome, which would make the L5a
estimand something other than a restricted LATE. (c) A pit-lane time-loss measure showing that
the "cheaply" channel in threat 2 accounts for the whole of the effect, which would kill 07b at
the design stage — but that is a finding for 07b, not a reason to skip it.

**Gates.** 1 substituted (`00b` reproduced exactly before anything was built on it). 2 and 3
substituted (no fit exists; every rung computed on one identical panel with only the cell
definition changing). 4 run in substance (within-cell permutation null, above). 5 run as a
mechanical assertion. 6 run properly — the pre-registration above was written and saved before
the counting script existed. 7 not applicable and declared so in advance: 07a enters no
hypothesis into the campaign family. **This item is `MEASURED`, not `GATED`.**

**Deviations from the leaf doc as written, all logged above and corrected in place:** the unit
of observation fixed as the (stint, lap) risk-set moment rather than the stint; race-grain
rather than lap-grain `rainfall_flag`; and the per-season range in "The identification" above
corrected from an inherited 21–36% to the measured 19.17–35.69%.

### 07a independent verification — orchestrating session, 2026-09-10

Per [`../status/BUILD-ORDER.md`](../status/BUILD-ORDER.md) ("the agent's own summary of what it
did is not verification"). Everything below was re-run by the reviewing session, not read from
the agent's report. Probes: `scratchpad/v1_provenance.py`, `v2_boundary.py`.

**Reproduction — exact.** `p0_instrument_check.py` and `p2_ladder.py` re-run end to end.
5,360 / 2,973 stints, 26.87% / 6.49%, per-season 19.17–35.69%. Ladder A reproduces to four
decimals at every rung: L3 retention 0.9924 / 6,914 pairs / MH RR 4.4079; **L5a retention
0.3109 / 2,059 pairs / MH RR 7.4225**; L6 RR 9.3197. Ladder B likewise (L5a RR 9.6484). The
gate-5 assertion returns 0. The pre-registered thresholds are met as claimed and the **GO
stands**.

**Overturning-evidence (a) is now closed, and it closes in the verdict's favour.** The agent
left the provenance of `is_safety_car_lap` assumed. It is decidable by construction:
[`stg_laps.sql:124`](../../transform/models/staging/stg_laps.sql#L124) defines it as
`REGEXP_MATCHES(track_status, '.*4.*')`, and `is_vsc_lap` as digits `[67]`. The only input is
the FastF1 `TrackStatus` string — a race-control field. **No pit column enters the flag**, so
it cannot be set *by* the stop and the first stage is not definitional. Behavioural
confirmation: across 8,866 (race, lap) slices of ≥10 cars, **96.89% are unanimous** — the
whole field flagged or none of it — which is what a race-wide state looks like and not what a
per-car artefact looks like. (`stg_race_control` could not be cross-checked: it is a view over
`data/bronze/race_control/` and those parquet files are absent from this checkout.)

**A new bounded caveat the agent did not find — the boundary lap.** A lap spanning a status
change carries *every* code in effect during it, by the documented decode above. A car that
pits takes longer over that lap, so it is **mechanically** likelier to pick up the `4` digit
than a car that stayed out — no decision required. Those are exactly the 276 non-unanimous
slices. Within them the differential is large: pit laps are flagged **85.63%** against
**42.95%** for non-pit laps (n=508 / 2,084). They carry **435 of the 1,440 treated pit moments
(30.2%)**, so this is not a rounding concern.

**The first stage survives dropping them**, which is what makes the caveat bounded rather than
fatal:

| L5a, `Z` = any SC/VSC | ident. cells | pairs | MH RR | MH RD |
| :--- | ---: | ---: | ---: | ---: |
| all moments | 302 | 2,059 | 7.423 | +0.3044 |
| **unanimous slices only** | 221 | **1,337** | **6.950** | +0.2775 |
| mixed slices only | 145 | 427 | 8.239 | +0.3403 |

At L3 the same cut gives RR 4.408 → 3.789. So the boundary laps do inflate the first stage,
mildly and in the direction predicted — but strip all 1,330 of them and 1,005 treated pit
decisions remain at **RR 6.95**, still 3.5× the pre-registered floor of 2.0. One honest
qualification: instrument retention on the unanimous subset is **1,382 / 5,637 = 24.5%**,
which is *below* the 30% bar. The bar was met on the panel the rule was pre-registered
against, and this subset is a robustness cut rather than a re-application of the rule — but a
referee should be told the number, so it is recorded here rather than left out.

**This inverts the reading of Ladder B.** An onset lap is by definition the first flagged lap
of a neutralisation within the stint, so it is *disproportionately* a boundary lap: **31.8% of
onset moments and 36.0% of onset pit moments** sit on mixed slices, against 19.1% of all `Z=1`.
Ladder B's stronger RR (9.65 vs 7.42) is therefore **partly this artefact**, not purely the
cleaner assignment it reads as. 07b must not reach for the onset restriction as the
conservative choice — on this channel it is the *less* conservative one. The conservative
restriction is `Z` = SC already deployed at lap start.

**Added to what 07b inherits:** fold the boundary-lap channel into the design — either restrict
`Z` to laps whose neutralisation was already running at lap start, or carry the unanimous-only
cut as the headline robustness row.

**One citation slip, no substance.** The pre-registration attributes "46.26% of
`is_training_eligible` mart rows" to `p0_instrument_check.py`, which computes the figure
*unfiltered* and prints 46.37%. Both numbers are real and I reproduced both: 46.37% over all
137,447 mart rows, **46.26% over the 121,193 `is_training_eligible` ones**. The sentence's
claim is correct; only its named source is.

## 07b — The estimator

**Blocked on `07a`.** Design written only once the first stage is known to survive. Pre-register
the arms per [`../foundations/gates.md`](../foundations/gates.md) step 6 before running them —
this item is exactly the kind of flexible design that multiplicity punishes.

**Definition of done.** An effect with an interval, the exclusion restriction argued for the
specific outcome chosen, all four threats above addressed in the write-up, and a stated
falsification test.
