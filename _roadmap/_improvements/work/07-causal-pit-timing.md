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

### 07b pre-registration — written 2026-09-15, before any instrument-outcome contrast was run

Per [`../foundations/gates.md`](../foundations/gates.md) step 6, following 07a's own precedent:
everything below was fixed and saved to this file before `Z` and `Y` were ever compared. What
*was* computed first — matching 07a's move of establishing coverage facts before writing the
design — are pure structural/coverage numbers (row counts, join resolution, missingness): no
number below depends on how the instrument relates to the outcome. Scripts:
`scratchpad/b0_structural_checks.py` through `b3_boundary_flags.py`, throwaway, not in the repo
after this session.

**Gate 1 substitute, run first.** 07a's headline reproduces exactly before anything is built on
it: 5,360 uncensored / 2,973 censored stints, 26.87% / 6.49% SC-or-VSC stint ends, panel of
90,597 (stint, lap) moments, 6,967 carrying `Z=1`, 5,360 pit moments — all four numbers match
07a's own `p0_instrument_check.py` / `p2_ladder.py` figures to the digit. **Verified.**

**What 07b inherits from 07a, cited not re-derived.** The RR 7.42 first-stage at L5a (2,059
matched pairs, 31.1% retention), the GO verdict, the independent verification's boundary-lap
finding (30.2% of treated pit moments sit on a mixed-status slice; the conservative `Z` reading
is "already running at lap start", not "onset"), and the five items the leaf doc and build-log
hand to 07b. Nothing in that record is re-measured here except where a number needs to be
re-derived to build on it (the panel itself, for instance, is rebuilt rather than loaded from a
throwaway artefact that no longer exists).

#### Population

Uncensored stints only (07a's threat-4 discharge, carried over unchanged): `int_stint_end_regime
.is_censored_stint = FALSE`. Unit of observation: the (stint, lap) risk-set moment, identical to
07a, built from every lap of every uncensored stint in `int_stint_geometry` (90,597 rows,
**verified** against 07a's own count).

Three exclusions applied, each resolving one inherited item, each logged as a population
restriction rather than a covariate:

1. **Item 1 (red-flag control-arm contamination).** Drop the 103 moments that are
   `is_red_flag_lap AND NOT (is_safety_car_lap OR is_vsc_lap)` — **verified**: all 103 are stint
   ends, matching 07a's figure exactly. Chosen over folding red flag into `Z`: a red flag is not
   an encouragement, it is closer to compulsion (hazard 1.000, deterministic), and mixing a
   deterministic sub-instrument into a probabilistic one would let 0.15% of the panel dominate a
   stratified or regression-weighted estimator out of proportion to its size. Dropped, not
   recoded to control — recoding would put 103 true near-certain-hazard moments in the `Z=0` arm,
   which is the contamination this step exists to remove. (**Note, logged rather than acted on**:
   moments that are both red-flag AND SC/VSC — 284 of them — are left in the `Z=1` arm unchanged;
   the item only names the control-arm contamination, and these are already correctly classified
   there.)
2. **Item 2 (`race_to_track` misses `2018_14`).** Excluded explicitly rather than fixed: 531
   uncensored risk-set moments drop, **verified** to be exactly the 2018_14 rows (no other race is
   affected; `race_to_track` resolves 148 of the 149 (year, race) pairs the geometry table
   carries, confirmed by direct query). The join is not "fixed" because `race_to_track` keys on
   `race_id` alone and that column already encodes the year (`race_id` values look like
   `"2018_14"`), so there is no year-ambiguity to repair — the seed table is simply missing that
   one row, and there is no other source in this warehouse to backfill it from without leaving
   the read-only boundary.
3. **Item 3 (degradation-state missingness costs treated decisions non-randomly).** Accepted as a
   restricted estimand rather than built around: `deg_state_s(ℓ)` must be defined, which requires
   ≥4 valid laps strictly before ℓ in the stint (07a's own rule, reproduced below). This is a
   **LATE over stints past their fifth lap**, stated plainly rather than smoothed over. The
   alternative the item offers — a degradation measure defined from lap 2 — is not built here;
   time is spent instead on the estimator (item 4) and the exclusion argument (threat 3), which
   are 07b's actual mandate.

**`deg_state_s(ℓ)`, reproduced exactly from 07a's definition:** `mean(driver_skill_residual_s)`
over the last 3 available (valid) laps strictly before ℓ, minus the mean over the stint's own
first 3 available laps, from `int_lap_residual_decomposed`. Requires ≥4 valid laps strictly
before ℓ or the moment is dropped. **Verified as an exact reproduction**: this session's
independent implementation returns 63,047 covariate-defined moments out of 90,597 — the identical
count 07a reports, to the digit, computed from a from-scratch pandas implementation rather than
07a's SQL. This is the strongest available cross-check that both sessions read `int_stint_geometry`
/ `int_lap_residual_decomposed` the same way.

**Fourth restriction, new to 07b, not one of the inherited items but required by the outcome
choice below.** The forward-outcome window (next section) must find at least one valid lap after
ℓ; 773 of 90,597 moments (0.85%) have none (end-of-race / retirement within the window) and are
dropped. Coverage is otherwise near-total: 89,367 of 90,597 moments (98.6%) find the full 3 laps,
220 find 2, 220... (220 find 2, 237 find 1) — **verified**, `scratchpad/b2_covariates_outcome.py`.

**Net analytic population, all four restrictions applied:** **n = 62,889** moments, of which
**2,130 carry `Z=1`** and **4,037 are pit moments**. Of the 1,421 SC-driven pit decisions that
survive exclusions 1–2, **710 (50.0%) survive into this population** — close to, and slightly
below, 07a's reported 52.1%/750, because this population also requires the forward-outcome
window (item absent from 07a's L5a, which only needed `deg_state_s`). **Verified**,
`scratchpad/b3_boundary_flags.py`. Minimum `lap_in_stint` in the final population is 5, confirming
the restricted estimand is literally "past the stint's fifth lap" and not merely "usually late in
the stint."

#### Instrument `Z`

**Headline** — identical to 07a's cleared definition: `Z = 1` iff `is_safety_car_lap OR
is_vsc_lap`, `Z = 0` otherwise, computed on the population above (red-flag-only and 2018_14
already excluded, so there is no remaining red-flag ambiguity in either arm of the headline
definition).

**Two robustness variants of `Z`, addressing item 5 (the boundary-lap channel) from both sides
the independent-verification section named:**

- **R1 — unanimous-slice-only** (the leaf doc's suggested headline robustness row). Drop every
  moment sitting on a non-unanimous (race, lap_number) slice — a slice where, among ≥10 cars
  observed on that lap, some carry the flag and some do not, which is the observable signature of
  a status change falling inside that lap for only some of the field. **Verified** reproduction of
  the independent-verification session's own number: 8,866 slices with ≥10 cars, 8,590 unanimous
  (96.89%), to the digit. Population after this cut: n = 61,351, `Z=1` on 1,409 moments, 3,724 pit
  moments.
- **R2 — conservative `Z`** ("already running at lap start", the independent-verification
  section's own stated conservative choice, not the onset restriction 07a's Ladder B used). A
  moment's *previous chronological lap for the same driver, in the same race, regardless of
  stint* is checked: if that lap also carried `Z=1`, the neutralisation was already running when
  this lap began and the moment is conservative-`Z=1`; if this lap is flagged but the previous one
  was not (an **onset** lap — 3,201 of 11,656 total `Z=1` laps across the full field, **verified**),
  it is dropped from this variant entirely, not recoded to control, for the same reason item 1's
  red-flag moments are dropped rather than recoded. Population after dropping onset moments: n =
  61,791, conservative-`Z=1` on 1,032 moments, 3,555 pit moments.

Both robustness rows are run and reported below the headline; neither replaces it, per the
research judgement logged under "Deviations" at the end of this pre-registration.

#### Treatment `D`

`D = 1` iff the moment is the stint's chronologically final lap (the discrete-time pit hazard),
identical to 07a.

#### Outcome `Y` — the design's answer to threat 2 (common shock)

**`Y(ℓ) = mean(driver_skill_residual_s)` over the next *up to* 3 valid laps strictly after ℓ,
crossing the stint boundary freely** — i.e., on whichever tyre the driver is actually running once
green-flag racing resumes. For a moment where `D = 1` this is the *new* stint's opening pace; for
a moment where `D = 0` it is the *continuing* stint's next laps. Both arms get an outcome measured
at the same forward horizon from the same decision point; nothing about which arm gets which tyre
is baked into how `Y` is defined.

**Why this outcome, and why it is the design's answer to threat 2.** 07a's verdict named the
common-shock threat in concrete terms: under an SC the whole field pits *and* the pit-lane time
loss itself falls, so a race-time or finishing-position outcome cannot separate "pitted earlier"
from "pitted more cheaply." `Y` is a **per-lap pace residual over laps that start only once the
car is back at racing speed** — `is_pit_lap` (both the in-lap and the out-lap) is excluded from
`is_valid_lap` by construction (`stg_laps.sql:132-138`), and `int_lap_fuel_state`, which
`int_lap_residual_decomposed` is built on, is itself filtered to `is_valid_lap = TRUE`
(`int_lap_fuel_state.sql:18-20`) — **verified** by reading both files. The one-time pit-lane
transit cost, cheap or expensive, never enters a lap that appears in `Y` at all. Threat 2's
mechanism has no channel into this outcome by construction, not by assumption.

**Why `driver_skill_residual_s` specifically, and not a coarser pace measure.** Six of the seven
terms `int_lap_residual_decomposed` subtracts before writing down the residual are exactly the
channels through which a race-wide SC state could move pace for *every* car, treated or not:
`fuel_component_s`, `compound_component_s` (the age-conditional expected pace for whatever tyre
the car is on — so a car on lap 2 of a stint post-SC-pit is not being unfairly compared to a car
on lap 30 of its stint), `rubber_component_s` and `ambient_component_s` (the exact terms
`int_track_evolution` builds to capture a cooling, less-rubbered track after a full-course
caution), `constructor_component_s`, and `dirty_air_tax_s` (the exact term built to capture the
bunched-field traffic a restart produces). Using the raw `pace_delta_s` or `lap_time_s` instead
would leave every one of those channels live in `Y`; using `driver_skill_residual_s` closes five
of the six by construction (fuel, compound-age, rubber, ambient, constructor) and the sixth
(dirty air / restart traffic) by an explicit modelled term rather than an assumption that it
washes out. What is *not* closed by this construction is argued honestly under "Exclusion
restriction" below — it is a real remaining threat, not a solved one.

#### Falsification outcome `Y_placebo`

**`Y_placebo(ℓ) = mean(driver_skill_residual_s)` over the (up to) 3 valid laps strictly *before*
ℓ** — the mirror-image construction of `Y`, pointed backward instead of forward. Defined
identically to the trailing-mean component already computed inside `deg_state_s(ℓ)`, so it is
available on exactly the same 63,047 covariate-defined moments (**verified**, exact match). This
is not a second outcome for the headline estimate; it exists solely for the falsification test
below and is declared here, before running, for the same reason the headline outcome is.

#### Conditioning / estimator — the design's answer to item 4 (thin-cell matching)

**Regression-adjusted stratification**, not exact-cell matching, chosen for the reason item 4
states plainly: 07a's own L5a tercile grid put 19.2% of retained treated mass in cells with
`min(n1,n0) < 5`, and building a 939-cell (or finer) grid for 07b would inherit the same problem
one rung earlier, since `deg_state_s` is now the *only* remaining covariate beyond what 07a's L4
already discharged cleanly (L4: 97.6% retention, 6,620 pairs, RR 6.56 in 07a's own table — not
thin anywhere near the degree L5a is).

**The fix: keep `deg_state_s` continuous rather than binning it into terciles, and use L4's
circuit × era × wet-race × tyre-age-bin cell as a fixed effect rather than as a matching stratum.**
Concretely, via the Frisch–Waugh–Lovell theorem: demean `D`, `Y`, `Z` and `deg_state_s` within
each L4 cell (subtract the cell's own mean from each), then run

```
first stage:  D_tilde ~ Z_tilde + deg_state_s_tilde        (OLS, no intercept, demeaned already)
reduced form: Y_tilde ~ Z_tilde + deg_state_s_tilde
LATE         = coef(Z_tilde) in reduced form / coef(Z_tilde) in first stage      (Wald / 2SLS)
```

which is algebraically identical to running the same regressions with a full set of L4 cell
dummies plus a linear `deg_state_s` control, and is what "regression-adjusted stratification"
concretely means here. **Verified that this resolves item 4's stated problem**: on the final
population (n = 62,889), there are 353 L4 cells, of which 176 are identifying (hold both `Z=1`
and `Z=0`), and **99.86% of `Z=1` mass (2,127 / 2,130) sits in an identifying cell** —
`scratchpad/b3_boundary_flags.py`. A singleton or non-identifying cell contributes exactly zero
to `Z_tilde`'s variance after demeaning (its residual is 0 for every variable), so it is
automatically and gracefully dropped from the estimator rather than needing to be matched,
imputed, or hand-excluded. This is the direct resolution of the "sample-size problem to shrug
at" the item warns against: at L4 granularity with a continuous covariate, there is effectively
no thin-cell problem left to solve.

**Robustness on the linearity assumption (R3):** add `deg_state_s_tilde^2` (also demeaned within
cell) as a second control in both stages, checking whether the linear-in-`deg_state_s` assumption
drives the headline number.

**Robustness cross-check against 07a's own coarser design (R4):** replace the continuous
`deg_state_s` control with a fixed effect for its own tercile — i.e., cell = L4 × deg-tercile,
reproducing something close to 07a's L5a cell structure (939-cell scale) as a *regression* rather
than a *matching* design. This is run purely to confirm the continuous-covariate resolution is not
hiding a result the coarser cross-cut would contradict; it inherits L5a's own thinness and is
reported with that caveat rather than as an equally-trusted number.

#### Interval — reused production code, not a new protocol

`ml/src/intervals.py::cluster_bootstrap`, unmodified, called as
`cluster_bootstrap(score, race_key, n_rows, resamples=400, seed=S.RANDOM_STATE)` where `score(idx)`
recomputes the *entire* FWL-demeaned Wald/2SLS pipeline (cell means, demeaning, both regressions,
the ratio) on the resampled rows — cell means must be recomputed per resample, not fixed from the
original data, since resampling changes cell composition. `race_key` (`race_year` + `race_id`, 147
distinct races in the final population) is the cluster: an SC is a race-wide event, so a race is
the coarsest honest cluster here, exactly the logic `intervals.py`'s own docstring already uses to
justify season-level clustering elsewhere ("a whole season moves together"). `resamples=400`
matches the module's own default (`BOOTSTRAP_RESAMPLES`); `seed=20260528` is
`ml/src/schema.py::RANDOM_STATE`, "imported everywhere; any other seed is a defect."

**This is a new statistical protocol, named as such per `epistemics.md`'s hard line, not
conflated with either `paired_t` or `refit_noise_floor`.** It is not compared against a floor from
either of those, and no delta computed under it will be quoted against a threshold computed under
a different protocol.

#### Exclusion restriction, argued for this specific outcome

Threat 3, 07a's own text: the exclusion is "far more defensible for a pace/degradation outcome
than for finishing position." Argued concretely for `Y` as defined above, not in the abstract:

**What is closed.** An SC/VSC lap could move `Y` through channels other than "did this car pit
now" via: (a) fuel state — closed, `fuel_component_s` subtracted; (b) the tyre's own
age-conditional expected pace — closed, `compound_component_s` subtracted, so a fresh tyre is not
mechanically "faster" in `Y`, only faster or slower than its *own* age-conditional model
prediction; (c) track-wide state (a cooling, de-rubbered track after the caution) — closed,
`rubber_component_s` and `ambient_component_s` subtracted, and these are literally the terms
`int_track_evolution` was built to isolate this exact effect; (d) restart traffic / bunched-field
dirty air — closed by an explicit modelled term, `dirty_air_tax_s`, rather than by assumption;
(e) constructor-level structural pace shifts across the caution — closed, `constructor_component_s`
subtracted.

**What is not closed, stated plainly rather than assumed away.** A **restart-psychology / track-
position channel**: a car that does *not* pit under the SC still experiences the restart itself —
a bunched pack, defensive driving, cars on old tyres running exposed next to cars on new ones — and
that could move its own subsequent pace independent of its own pit decision. `dirty_air_tax_s`
models proximity-based drag/downforce loss from *following* a car; it is not built to model
race-craft caution specific to a restart, and there is no restart-specific term in this
decomposition to subtract. This is a genuine, outcome-specific residual threat to the exclusion
restriction, and it is the reason a **falsification test and a supporting diagnostic** are
pre-registered below rather than the exclusion argument resting on the six closed channels alone.

**Supporting diagnostic (not the pre-registered falsification test, but declared here so it is
not added after the result is known): the reduced form restricted to `D = 0` moments only.** If
the restart-psychology channel is operating, `Z` should predict `Y` even among moments that did
not pit — since, by definition, nothing about *their own* treatment status changed. A reduced-form
`Y ~ Z` (same L4 + `deg_state_s` controls) computed on the `D = 0` subset only is reported
alongside the headline as a direct, if heuristic, exclusion diagnostic. (Heuristic because `D = 0`
at this specific moment does not mean "never-taker" in the Angrist–Imbens sense — a driver who
does not pit on lap ℓ may still pit two laps later — so this is suggestive, not dispositive.)

#### Falsification test — pre-registered, one test, stated before running

**`Y_placebo ~ Z`, with the identical L4 + `deg_state_s` controls used in the headline reduced
form, on the identical 62,889-moment population.** `Y_placebo` is realised strictly *before* ℓ;
`Z` is realised *at* ℓ. Under correct identification, `Z` cannot cause something that already
happened, so the reduced-form coefficient on `Z` in this regression should be statistically
indistinguishable from zero. **What a failure would mean:** a nonzero coefficient here says the
conditioning set (circuit, era, wet-race, tyre-age bin, `deg_state_s`) has not fully purged
whatever selects an SC's timing relative to a given car's *pre-existing* state — a threat-1-style
failure that would also cast doubt on reading any headline `Z → Y(forward)` relationship as pure
`D`-mediated causation, since the same unpurged channel could reach forward as easily as it
reaches into this backward-looking placebo.

#### Gate 7 — e-value construction, declared before the arm runs

**Construction C (shuffle-rank, assumption-free)**, reusing 07a's own gate-4 permutation
machinery — within-L4-cell shuffles of `Z`, preserving each cell's size and `Z=1` count exactly —
extended from 07a's first-stage-only statistic to the full LATE.

```
H0                : Z carries no information about (D, Y) beyond what the L4 cell and
                    deg_state_s already explain (the within-cell exchangeability null,
                    the same one 07a's gate-4 substitute used for the first stage alone)
Statistic         : LATE_hat, the headline Wald/2SLS ratio defined above
Construction      : C (shuffle-rank)
K                 : 999 within-cell permutations of Z (cell sizes and each cell's Z=1
                    count held exactly fixed, matching 07a's gate-4 substitute)
Ranking           : two-sided, by |LATE|, rank of |LATE_hat| among {|LATE_hat|} union
                    {|LATE_perm_1|, ..., |LATE_perm_999|}
k                 : 1 (the sharpest)
E                 : (K+1)/rank = 1000/rank
Seed              : 20260528 (ml/src/schema.py::RANDOM_STATE)
Declared alt      : no directional prior -- unlike a model-beats-baseline claim, there is
                    no a priori "improvement" sign for whether SC-forced pit timing helps
                    or hurts next-stint pace, so this deviates from e_value_construction.md
                    section 2's one-sided-by-direction default and ranks on |LATE| instead.
                    Logged here as a deviation, not discovered after the fact.
Hypothesis count  : this adds 1 hypothesis to the campaign family -- the headline LATE
                    (R0). R1-R4 and the D=0 diagnostic are robustness views of the same
                    estimate, not independent bets, and are not separately declared, on
                    the same logic 07a used for its own ladder rungs (one feasibility
                    count, not seven campaign entries).
Reported          : E, whatever it comes out as, including E < 1.
```

#### Deviations logged before running (per `epistemics.md`, stated not discovered)

1. The leaf doc's boundary-lap item offered "restrict `Z` to already-running-at-lap-start" or
   "carry the unanimous-slice cut as the headline robustness row" as alternatives. Both are run
   (R1, R2); the headline estimator itself keeps 07a's cleared `Z` definition unchanged, for
   continuity with the GO verdict's own pre-registered thresholds, and the boundary-lap concern is
   fully carried in the robustness rows rather than folded into the headline definition.
2. Item 3 is resolved by accepting the restricted LATE rather than building a from-lap-2
   degradation measure — a scope decision, logged rather than silently taken.
3. The e-value's ranking is two-sided (by `|LATE|`) rather than one-sided by a pre-registered
   improvement direction, because this hypothesis has no natural "improvement" orientation the
   way a model-beats-baseline claim does. Stated here, before the permutation is run.
4. `Y` and `Y_placebo` both use "up to 3" available laps rather than requiring exactly 3, decided
   from the coverage check (0.85% have zero, 98.6% have the full 3) rather than from any
   Z-conditional pattern — the decision was made looking at missingness alone, the same posture
   07a took toward `deg_state_s` missingness.

### 07b results — 2026-09-15

Every number below was computed on `data/dev.duckdb` read-only, on the population and
specification fixed in the pre-registration above with nothing changed after the fact.
Scripts: `scratchpad/b1_build_panel.py` through `b4_estimate.py`, throwaway, not in the repo.

**Headline population, reproduced exactly as pre-registered.** n = 62,889 moments, `Z=1` on
2,130, 4,037 pit moments, 147 distinct races. **Verified.**

**First-stage strength.** Z coefficient on `D` (FE(L4) + `deg_state_s`, demeaned): **0.2898**,
cluster-robust SE (clustered by race) 0.0288, race-clustered **F = 101.5**. No weak-instrument
concern on the headline specification — this is the same first stage 07a already established at
L5a (RR 7.42), read here as a linear-probability coefficient instead of a risk ratio. **Verified**.

**The five pre-registered specifications, none dropped, none added after seeing a result:**

| Spec | Population | n | Z̄=1 | First stage (Z) | Reduced form (Z) | LATE | 95% cluster-boot CI | Excludes 0? |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- | :--- |
| **R0 headline** — FE(L4) + linear `deg_state_s` | pop3 | 62,889 | 2,130 | 0.2898 | 0.5416 | **+1.869** | [−0.216, 3.375] | No |
| R1 — unanimous-slice only | popB | 61,351 | 1,409 | 0.2736 | 0.3670 | +1.341 | [−1.986, 3.559] | No |
| **R2 — conservative Z (onset dropped)** | popA | 61,791 | 1,032 | 0.1706 | −0.0387 | **−0.227** | [−6.418, 3.884] | No |
| R3 — quadratic `deg_state_s` | pop3 | 62,889 | 2,130 | 0.2905 | 0.5631 | +1.939 | [−0.213, 3.406] | No |
| R4 — tercile-FE cross-check (≈ L5a cell structure) | pop3 | 62,889 | 2,130 | 0.2962 | 0.5835 | +1.970 | **[0.455, 3.336]** | **Yes** |

`LATE` is seconds of forward degradation-adjusted pace per unit of SC-induced pit probability;
positive means an SC-induced pit produces a *slower*-than-model-expected next stint. R4's
939-cell-scale tercile structure inherits 07a's own L5a thinness (299 of 936 cells identifying,
99.1% of `Z=1` mass retained in them — **verified**, `scratchpad/b4_estimate.py`), reported
alongside rather than as an equally-trusted number, exactly as pre-registered.

**The result is not robust across the pre-registered specifications, and the disagreement is
informative rather than noise to average away.** R0, R3 and R4 — which all keep 07a's cleared
`Z` definition and so all still include onset-boundary moments — cluster around a LATE of
roughly +1.9 to +2.0 seconds, and R4's narrower cell structure happens to produce a CI that
excludes zero. **R2 is the one specification built to remove exactly the contamination the
independent-verification session flagged** ("the conservative restriction is `Z` = SC already
deployed at lap start", not onset), and it does not merely attenuate the effect — the reduced-form
coefficient **flips sign** (0.542 → −0.039) and the point estimate collapses to essentially zero
(−0.227) with the widest interval of the five. Because R2 targets a *named, mechanistically
argued* contamination rather than being one arbitrary cut among many, this session reads the
disagreement as R2 overturning R0/R3/R4 rather than as R0/R3/R4 outvoting R2: the moments that
carry the apparent effect are disproportionately the ones where a car's own pit stop made it
mechanically more likely to still be flagged when the SC status changed mid-lap — precisely the
channel 07a's independent verification described as capable of inflating the first stage, now
shown to inflate (or manufacture) the *reduced form* on this outcome as well, which 07a's own
first-stage-only boundary check (RR 7.42 → 6.95, a 6% attenuation) did not have the outcome data
to see.

**Bottom line: no reliable evidence of an effect in either direction.** The headline point
estimate (R0, +1.869s) is not small, but its interval spans zero, three of five specifications
have intervals spanning zero, and the one specification built to close the boundary-lap gap
collapses to near-zero with the widest interval of all. This is reported as the finding, not
smoothed into either "the effect is +1.9s" or "there is no effect" — the honest read is that this
design, even resolved to L4-plus-continuous-covariate regression adjustment, is not powered to
distinguish a real effect from the boundary-lap-driven artefact at this outcome and sample size.

#### Exclusion-restriction diagnostics

**Falsification test (pre-registered): `Y_placebo ~ Z`, identical controls, identical
population.** Coefficient **−0.188**, cluster-robust SE 0.110, t = −1.70, p ≈ 0.091 (n = 62,889,
147 race clusters). Does not reach conventional significance, and — more informative than the
p-value alone — it is **opposite in sign and about a third the magnitude** of the headline
reduced-form coefficient (+0.542). A confound that leaked into the headline result through
unpurged pre-existing state would be expected to show up in `Y_placebo` with a similar sign and
comparable size to what it produces in `Y`, since the same pre-ℓ state would bias both a backward-
and forward-looking pace measure the same way; this pattern does not look like that. **This is
mild reassurance, not a clean pass** — p = 0.091 does not license calling threat 1 fully closed at
this outcome, and it is reported as exactly that: a test that did not fail, not a test that
strongly passed. **Verified**, `scratchpad/b4_estimate.py`.

**Supporting diagnostic (pre-registered, not the falsification test): reduced form among `D=0`
moments only.** Coefficient **−0.158**, cluster-robust SE 0.334, t = −0.47, p ≈ 0.637 (n = 58,852).
No detectable direct effect of `Z` on `Y` among moments where no pit happened — consistent with
(though, per the pre-registration's own caveat, not proof of) the exclusion restriction holding,
since a car that did not change its own timing this lap shows no reduced-form pace effect from the
SC's presence. **Verified.**

**Exclusion restriction verdict for this outcome.** The six closed channels named in the
pre-registration (fuel, compound-age-expected pace, rubber, ambient, constructor, dirty-air/
traffic) are closed by construction, not by assumption — traced to the specific columns each
subtracts. The one open channel (restart psychology / track-position effects not mediated by the
driver's own pit decision) is not closed, but the two diagnostics available point the same
direction: no detectable `Z`→`Y` effect among non-pitters, and a placebo test that does not fail.
Neither diagnostic can rule out a small residual leak — that would need a study built around it
specifically — but neither finds one either.

#### Gate 7 — e-value, as declared

**The declared statistic (LATE ratio) returns E = 1.15 — essentially no evidence beyond noise —
and this is the number that counts for the campaign family, exactly as pre-registered.** 999
within-L4-cell permutations of `Z` (cell sizes and each cell's `Z=1` count held exactly fixed,
seed 20260528): observed `|LATE| = 1.869` ranks 871st (by absolute value) among the 1,000
statistics {999 permuted LATEs, the observed one}, giving `E = 1000/871 = 1.15`.

**A methodological finding surfaced while running the pre-registered arm, reported because it
explains the weak `E` rather than because it improves it.** The permutation-null *first-stage*
coefficient is centred at 0.0002 with sd 0.0060 — 91% of permutations land inside ±0.01, nowhere
near the real first stage's 0.290. Dividing a reduced-form coefficient (itself well-behaved:
permutation-null mean 0.0006, sd 0.051) by a first-stage coefficient that is frequently near zero
produces a ratio with a heavy, near-Cauchy tail — the permuted-LATE distribution observed here
has range **[−63,155, 20,906]** against an observed value of 1.87. Construction C's validity does
not depend on the null being well-behaved (it is exact by exchangeability alone, regardless of
tail shape), so `E = 1.15` is a legitimate e-value — but it has **very low power for a ratio
statistic whose denominator's null distribution has mass near zero**, because a handful of
division-by-near-zero permutations inflate the comparison set with enormous, uninformative
values that outrank the real (well-identified) effect on magnitude alone.

**Diagnostic-only, explicitly not a declared or counted e-value:** ranking the observed
*reduced-form* coefficient alone (0.542) against its own permutation null (999 draws, none
exceeding |0.167|) gives rank 1/1000. This is **not** reported as `E = 1000` for this item — it
was not pre-registered, computing it after seeing the ratio's weak result is exactly the
after-the-fact statistic-shopping gate 7 exists to prevent, and it does not enter the campaign
family. It is recorded here only as the explanation for *why* the declared `E` is weak: the first
stage and the reduced form are each individually far from their own null distributions (which is
consistent with 07a's already-cleared first stage and with the headline reduced-form coefficient
being real rather than noise on its own terms) — it is specifically the **ratio's** permutation
null that is degenerate. **A lesson for the next ratio-statistic gate-7 in this programme:**
Construction C ranked on a Wald/2SLS ratio directly is likely to under-power whenever the
first-stage permutation null has mass near zero; ranking the reduced form (or a weak-IV-robust
statistic such as Anderson–Rubin) instead would be the better-powered pre-registered choice next
time. Recorded here rather than acted on retroactively.

#### The four threats, addressed in full

| Threat | Status | Evidence |
| :--- | :--- | :--- |
| **1. SCs not unconditionally random** | Discharged at 07a's rungs (circuit, era, wet, tyre-age); not re-litigated here. The falsification test (p ≈ 0.091, wrong-signed relative to the headline) gives mild further support at 07b's own conditioning set, not a clean pass. | 07a L1–L4; this item's falsification test |
| **2. Common shock (timing bundled with cost-of-stop)** | **Discharged by outcome construction.** `Y` excludes both pit-lane laps by construction (`is_valid_lap` excludes `is_pit_lap`) and the mechanical channels an SC could move pace through for the whole field (fuel, compound-age, rubber, ambient, constructor, dirty-air) are each subtracted out of `driver_skill_residual_s` before it is used. | `stg_laps.sql:132-138`, `int_lap_fuel_state.sql:18-20`, `int_lap_residual_decomposed.sql` |
| **3. Exclusion restriction (outcome-specific)** | **Argued for this outcome, not fully closed.** Six channels closed by construction; the restart-psychology/track-position channel is named, not closed, and two diagnostics (D=0 reduced form null; placebo test does not fail) point toward it being small, without proving it is zero. | This item's exclusion-restriction section and diagnostics |
| **4. Censoring** | Discharged at the population level, inherited from 07a unchanged (uncensored stints only). | 07a population definition |

**One threat 07a did not have to face and 07b does: fragility to the boundary-lap channel on the
*outcome* side.** 07a found the first stage attenuates mildly (RR 7.42 → 6.95) when boundary laps
are stripped. 07b finds the *treatment-effect* estimate on next-stint pace does not merely
attenuate under the equivalent cut (R2) — it reverses sign and loses all of its apparent
precision. This is the headline empirical finding of this item, not a caveat appended to one.

### What remains open

- **The restart-psychology exclusion channel** is named and diagnosed but not closed by a
  dedicated instrument. A future item could isolate it directly — e.g. comparing `Z`'s
  reduced-form effect on cars separated by post-restart running order — but that is new design
  work, not a gap in this one.
- **R2's own power is low** (1,032 treated moments, CI width 10.3s) — this session cannot
  distinguish "the true effect is zero" from "R2 is simply underpowered to detect the same +1.9s
  effect R0/R3/R4 see." Both readings are consistent with the numbers reported above; the
  write-up above states why this session leans toward reading R2 as the more trustworthy
  specification rather than claiming the point is settled.
- **Item 3's restricted estimand** (a LATE over stints past their fifth lap) means this result
  says nothing about the 47.9%-of-treated-decisions population 07a identified as excluded by
  construction — an early-stint degradation measure remains unbuilt.
- No go/no-go fork requiring a human decision was hit in this item. Every choice above (outcome,
  estimator, which robustness cut to trust more, the e-value construction and its stated
  limitation) is a research judgement, made and justified in place.
