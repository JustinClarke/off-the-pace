# WI-16 — Driver isolation: pure pace and relative pace ratings

**Group:** 03 driver vs car (new on this board; entry under *Board registration*) · **Status:** Tactical feature removed due to instability (noise-to-signal ratio 1.4x, cross-season correlation -0.15). Pure pace and relative pace isolation remain.

**What this delivers:** Two contextual ratings that answer different questions about driver performance. Both are independent of the choice of reference baseline (FD1 resolution: each rating is field-centred, so fuel, compound, and ambient effects cancel out).

**Previous scope:** This work item was originally planned to deliver three ratings (pure, tactical, and relative). The tactical rating has been cancelled due to fundamental stability issues identified through cross-validation. See the decision record below for details.

---

## Tactical rating: cancelled due to instability

**Decision:** The tactical (tyre-management) rating has been removed from the codebase. It was determined to be unfixable without fundamental redesign due to:
- Noise-to-signal ratio: 1.4x (measurement noise dominates the true signal)
- Cross-season correlation: -0.15 (no persistent skill detected across seasons)
- Peer-slope methodology limitations: left-out-one peer slopes from small samples are too noisy to carry meaningful driver information

The method never achieved the reliability threshold and further refinement would require abandoning the stint-level peer-slope approach entirely, which is beyond the scope of this work item.

**What remains:** Pure pace and relative pace ratings, both validated and stable, address the questions the tactical rating was meant to answer through different mechanisms:
- **Pure pace** captures driver raw-speed execution
- **Relative pace vs matched strategy** shows outcome against peers in the same tyre-and-fuel situation

---

## Why the ratings don't depend on FD1, and the label does

Write each lap as `t(d,l) = B(r,l) + F(r,l) + R(r,l) + A(r,l) + C(d,l) + K(c,r) + D(d,l) + e(d,l)`. The
terms are the field base, fuel, rubber, ambient, compound plus tyre age, constructor, dirty air, and
the driver.

The fuel model prices every car the same on a given lap. `fuel_mass_kg` is
`initial_fuel_kg − rate × (lap_number − 1)`, taken from the scheduled distance
(`int_lap_fuel_state.sql:105-109`), and `weight_penalty_factor` is set per circuit. So `F` depends
only on (race, lap), just like `B`, `R` and `A`.

Take `x(d,l) = t − C − D` and centre it on the lap's field median:
`y(d,l) = x(d,l) − MEDIAN over drivers on (r,l) of x`. A term that depends on (r,l) alone shifts every
`x` on that lap by the same amount, and it shifts the median by that same amount, so it drops out:
`y = (K + e) − MEDIAN(K + e)`. That means B, F, R and A cannot reach `y`, and neither can any error in
them. The same goes for F1's fabricated base, F22's double subtraction and F38's field-average
compound cost, which are all per-(race, lap). **Nothing in this WI reads `base_track_pace_s`,
`fuel_component_s`, `rubber_component_s`, `ambient_component_s` or `constructor_component_s`.**

The label behaves differently because it differences one driver's residual from lap l to l+5, and
`B(r,l+5) − B(r,l)` does not cancel. That is F38's "a field pit stop reads as +3.15 s of driver
degradation". So the label needs A.

Two terms from `WI-01`/`WI-02b` do reach the ratings, because they differ by driver: `C` (compound
and age) and `D` (dirty air). That is why `WI-16b` waits for `WI-01` (θ_air, F42a) and re-runs after
`WI-02b` (the seed refit; see the watch entry under *Board registration*).

A consequence to know about: fuel is identical on a given lap for every car, so **the fuel model
cannot see per-driver fuel strategy at all.** *Limitations* covers this, including a degenerate
column the check turned up.

---

## Definitions

Sign convention for everything this WI publishes: **`*_gain_s` = seconds per lap gained, positive =
faster / better.** The upstream residual chain uses the opposite convention (negative = faster), and
this repo has shipped two sign inversions from that mismatch (F50, F28). Every published column
therefore carries the sign in its name, and T43 pins it from raw lap times.

### The clean-lap panel Ω

A lap is in Ω when **all** of these hold. Both `int_lap_residual_decomposed` and
`int_lap_anomaly_flags` carry `correction_weight`, so the predicates are written out with table
qualifiers instead of calling `clean_lap_filter()` bare, which would be ambiguous in the join. The
first three lines are `clean_lap_filter()`. The rest go further on purpose.

- `r.correction_weight = 1.0`
- `a.anomaly_class IN ('normal', 'clean_cliff')`. This also drops `event_driven` (F51) whatever FD2
  rules; a lap slowed by a queue behind the safety car is not driver pace.
- `NOT COALESCE(a.is_rain_lap, FALSE)`
- `NOT a.is_out_lap AND NOT a.is_in_lap`
- `r.compound NOT IN ('INTERMEDIATE', 'WET')`, since wet-weather skill is out of scope (*Limitations*)
- `r.compound_component_s IS NOT NULL AND r.laps_past_cliff IS NOT NULL`. An unknown tyre means no
  rating (the F7/F39 quarantine). These two are never COALESCEd to 0.
- `r.race_id NOT IN var('isolation_exclude_races')`, default `['2020_1']`. W18 says 2020_1's lap
  numbering is wrong in bronze, and tiers 1 and 3 match on `lap_number`.
- the lap's (race, lap) has `field_n >= var('isolation_min_field_n')` (default 8) Ω laps.

Measured on the dev warehouse on 2026-09-26 (pre-`WI-01`, pre-W20 rebuild): the first five predicates
keep **135,992** of 161,040 laps. 95.6% of (race, lap) cells have ≥ 8 clean laps, with a median of 17.

### Step 0: field-centred isolated time (per lap)

```
x(d,l)  = lap_time_s − compound_component_s − dirty_air_tax_s
y(d,l)  = x(d,l) − MEDIAN_{Ω on (r,l)} x        -- s; positive = slower than the field-typical car+driver
tyre_offset_vs_field_s = compound_component_s − MEDIAN_{Ω on (r,l)} compound_component_s   -- context, not a rating
```

`tyre_offset_vs_field_s` is the *strategy position* on that lap: how much the seed says this driver's
tyre state is worth against the field's. It is team-dominated, so it is context, not a rating. The
LLM agent uses it for "how much of the win was strategy" (see São Paulo 2021 below).

### The car term

A two-way fixed-effects fit on the Ω panel, run by the existing fitter with a new panel option:

```
y ~ 1 | driver_era + constructor_race        driver_era = driver_id || '_' || (race_year >= var('era_boundary'))
```

`car_iso_s(c,r)` is the constructor×race FE, normalised to a lap-weighted mean of zero within each race
(negative = faster, the same convention as `car_fe_s`).

- **Why not reuse `int_constructor_car_fe`.** It is fitted on `pace_delta_s`, before compound and dirty
  air are removed, so it carries each team's average tyre-strategy and traffic exposure. Subtracting
  it from a compound- and traffic-stripped quantity would reproduce F22/F38's defect (a component
  inside the term, subtracted again). The car term has to be fitted on the same scale as `y`.
- **Why not `constructor_component_s`.** It is the median of the car's *own* laps, so it absorbs about
  half the gap between teammates (see `int_driver_race_skill_loro.sql`'s header). It is also the term
  F35 corrupts.
- **Why `driver_era` rather than a global `driver_id`.** A global driver FE assumes a driver's skill
  is constant from 2018 to 2025. Splitting at the regulation boundary halves that assumption and keeps
  the mover network connected inside each era. If an era's connected set has more than one component
  containing two or more constructors, fall back to the global `driver_id`, log it in the fit
  provenance, and flag `car_term_source = 'global_driver'`.
- **What identifies it.** The teammate network: drivers who changed teams connect the components, which
  is 03a's point. The OCO/PER 2018 Force India → Racing Point rename creates **no** new teammate link
  (same pair, same car), so it cannot manufacture identification here the way it can in a
  constructor-season design. No exclusion is needed, but say this in the fit's docstring.

### Tier 1: pure pace skill

```
pace_isolated_gain_s   p(d,l) = −( y(d,l) − car_iso_s(c,r) )
pure_skill_gain_s              = p(d,l)
```

Read it as: *his pace against the field on an equal car, equal tyre state, equal traffic and equal fuel.*

On cliff-phase laps, `pure_skill_gain_s` is the extrapolated pre-cliff line and is flagged
`pure_is_extrapolated = TRUE`. **Pure-skill aggregates use early, mid and recovery laps only.** On a
tyre past its cliff, the lap time is dominated by the tyre, and this WI does not claim to see the
driver there.

### Tier 2: relative pace vs same-strategy peers

Peers of (d, l) are every d' ≠ d with an Ω lap in the same race, **on the same lap number** (which
means the same fuel load, rubber and weather), on the **same compound**, with
`|age_d' − age_d| <= var('isolation_peer_age_tolerance')` (2). Teammates are included, and
`is_teammate` flags them.

```
relative_pace_gain_s(d,d',l) = t(d',l) − t(d,l)                                      -- model-free, raw pace
relative_pace_gain_s(d,l)    = AVG over peers of the above;  n_peers(d,l) = COUNT      -- NULL when n_peers = 0
```

The age tolerance is ±2 laps (vs the previous ±3) to tighten the tyre-age match. No model-based
age adjustment is applied; the tyre-age matching controls for this confounder directly. The rating uses
the mean over peers rather than the median, so that the identity below survives aggregation. Outliers
are already excluded by Ω. Measured coverage at ±2 laps: **86.4% of Ω laps have ≥ 1 peer,
72.0% have ≥ 2 and 37.4% have ≥ 5.**

### The decomposition identity

Tier 2 decomposes into tier 1 plus the car and traffic, with a tyre-age bias:

```
relative_pace_gain_s(d vs d')  =  (pure_d − pure_d')          pure_gap_gain_s
                               +  (car_iso_d' − car_iso_d)    car_advantage_gain_s      (> 0 = d's car faster)
                               +  (D_d' − D_d)                traffic_advantage_gain_s  (> 0 = d lost less to dirty air)
                               +  (C_d' − C_d)                tyre_age_bias              (residual from matching ±2 laps)
```

The tyre-age bias is the gap left by matching within ±2 laps instead of adjusting for age. For
teammates (same car, same strategy), this bias is median ±0.011 s (90th percentile ±0.147 s) per
driver-race. The median is well below the rating's uncertainty (~0.1 s at race grain), but the 90th
percentile exceeds it, so it is a known limitation. The *Limitations* section addresses this and its use case.

T42 checks the first three terms to 1e-6 (the pure, car, and traffic sum to the observed gap within
model precision).

**What this identity shows:** relative pace measures outcome against peers on the same tyre and fuel load.
The LLM agent will use it as: "VER was 0.15 s a lap quicker than HAM on matching tyres. About 0.12 s
of that was the driver and 0.09 s the car, and traffic cost him 0.06 s against HAM's. On the same
tyres because we matched within 2-lap age windows."

### Stint phase

The tyre phase comes from the **seed's** onset, which is exogenous to the residual, so the phase is
never selected on the outcome it stratifies:

| `tyre_phase` | Rule | Share of Ω (measured) |
| :-- | :-- | --: |
| `early` | `valid_lap_in_stint BETWEEN 2 AND 5 AND laps_past_cliff = 0` | 22.7% |
| `mid` | `valid_lap_in_stint >= 6 AND laps_past_cliff = 0` | 50.4% |
| `cliff` | `laps_past_cliff > 0` | 26.9% |

**Recovery** is an overlay (`is_recovery`), and `stint_phase = CASE WHEN is_recovery THEN 'recovery'
ELSE tyre_phase END`. A lap is in recovery when it is one of the first `var('isolation_recovery_laps')`
(3) valid laps of a non-dirty-air run that directly follows a run of at least
`var('isolation_recovery_min_dirty_run')` (2) consecutive valid laps with
`air_state_dominant = 'dirty_air'` in the same stint. That is "he has dropped out of the wake and his
tyres are coming back".

The rule is gap-based and looks backward, so it is not selected on the lap's own pace. The
alternatives are rejected: `recovery_flag` in `int_tyre_surface_vs_bulk_decoupling` reads *future*
laps (LEAD), and `push_residual` is derived from lap time, so either would make "pace in recovery"
circular. Measured on the pre-WI-15a coding: about 3.1% of valid laps. WI-15a's S2 coding raises the
dirty-air share, so re-measure. It is a thin stratum, so report it but never headline it. The run
aggregate uses `BOOL_AND(is_dirty)`, not `ANY_VALUE`, even though the value is constant within a run
(the F16 lesson).

### Rolling ~5-lap window

For each Ω lap, the window is the Ω laps of **the same stint** with
`lap_number BETWEEN l − (var('isolation_window_laps') − 1) AND l`. That is
`RANGE BETWEEN 4 PRECEDING AND CURRENT ROW` over `lap_number`, partitioned by `stint_id`. Because it
is a RANGE on the lap number, a window that spans a safety car simply holds fewer laps, which is
honest. The window is trailing, so it never reaches forward (T44).

| Window column | Aggregate | NULL when |
| :-- | :-- | :-- |
| `pure_skill_5lap_gain_s` | mean over non-extrapolated laps in the window | fewer than `var('isolation_window_min_laps')` (3) such laps |
| `relative_pace_5lap_gain_s` | `SUM(relative × n_peers) / SUM(n_peers)`, the mean over pair-laps | fewer than 3 pair-laps |

The window is labelled with the current lap's `stint_phase`, and `window_mixed_phase = TRUE` when it
spans more than one phase.

**What a 5-lap window can carry** (prototype on the current warehouse; `WI-16b` re-measures). The
within-stint SD of the field-centred lap value around its stint line is **0.40 s**, and the lag-1
autocorrelation is **0.18**, giving an effective-n factor of (1−ρ)/(1+ρ) = 0.70. Robust spread of
matched-strategy teammate race gaps is 0.32–0.42 s over about 27 laps, which puts per-driver signal
at τ ≈ 0.24 s.

| Grain | Clean laps | SE of pure skill | Reliability τ²/(τ²+SE²) |
| :-- | --: | --: | --: |
| 5-lap window | 3–5 | 0.21–0.28 s | 0.43–0.56 |
| stint | 16 (median) | 0.12 s | ≈ 0.80 |
| race | ≈ 45 | 0.07 s | ≈ 0.92 |

So **the 5-lap window is about half signal.** It is the "is he on it right now" number, not the "who
is better" number. Verdicts belong at stint or race grain. The docs page has to say so in those words.

### Small samples, shrinkage, confidence

Per row and per rating:

- **SE.** For pure skill: `sigma_w / SQRT(n × f)`, where `sigma_w` is the pooled within-stint SD of
  `p` around its line and `f = (1−ρ₁)/(1+ρ₁)`, with ρ₁ the pooled lag-1 autocorrelation (both per
  season, computed in a CTE, not hard-coded). For relative: the SD of pair-lap
  values over `SQRT(number of distinct laps with peers)`, which is conservative because pair-laps on
  one lap share the driver's lap.
- **Signal variance τ².** Per (season, rating, grain):
  `GREATEST(VAR_SAMP(raw) − AVG(SE²), 0)` over rows with n ≥ 6.
- **Reliability** `λ = τ² / (τ² + SE²)`, in [0, 1].
- **Shrunk value** `= λ × raw`. The prior mean is 0 because every rating is field- or peer-centred.
  This is the normal–normal model the `bayesian_shrinkage` / `posterior_variance` macros already
  implement: `prior_weight = sigma_w² / τ²` in effective laps.
- **Method score** per rating comes from `WI-16b`'s validation (see *Validation*), is written to the
  seed `driver_isolation_method_scores.csv`, and is `NULL` until validated.
- **`confidence_pct = ROUND(100 × λ × method_score)`** and
  **`trust_label`** ∈ `solid` (≥ 75) · `indicative` (50–75) · `thin` (25–50) · `suppress` (< 25, or the
  method grade is F) · `unvalidated` (method score NULL).

Floors come before shrinkage. Window values are NULL below 3 laps, tactical is NULL below 6 line laps,
and relative is NULL with no peer. Shrinkage then handles everything between "just enough" and
"plenty". There is no minimum-race floor at race grain; λ does that job.

### Example output

The format, with **illustrative** numbers that satisfy the identity. `WI-16b` produces the real ones:

```
VER · 2021 Styrian GP · stint 2 (HARD) · laps 30–34 · tyre age 5–9 · phase: mid
  pure_skill_5lap_gain_s        +0.23 s/lap   conf 52% (indicative)   vs field, equal car/tyres/traffic/fuel
  relative_pace_5lap_gain_s     +0.15 s/lap   vs HAM (HARD, age 7–11; 5 matched laps)
      = pure gap +0.12  + car +0.09  + traffic −0.06

VER · same stint · laps 38–42 · tyre age 13–17 · phase: cliff (seed onset 12)
  pure_skill_5lap_gain_s        NULL          (tyre past its cliff: not a driver measurement)
  relative_pace_5lap_gain_s     −0.31 s/lap   vs HAM on same compound, matched age
```

A **real** tier-2 number from dev (2026-10-03; same compound, tyre age within ±2 laps, raw pace with
no age adjustment): at the 2021 São Paulo GP, HAM vs VER reads **−0.041 s/lap over 18 matched laps**,
so VER was 0.041 s a lap quicker on matched tyres. Call it level: lap 2 alone (HAM −0.995 s) carries
the sign, and the other 17 laps average +0.015 s for HAM. The identity puts +0.673 in HAM's car,
−0.523 in the pace gap and −0.184 in traffic; the remaining −0.007 is the tyre-age bias from the six
laps where HAM's tyres were one lap older. The ±3 match had 36 laps here; the 18 it loses are all
three laps apart in tyre age. (The prototype probe's number, VER +0.24 s/lap over 57 laps at the 2021
Styrian GP, was age-adjusted at ±3; that pair now reads +0.233 over 54.)

---

## Scope

### Reused unchanged

| Model | What this WI reads |
| :-- | :-- |
| `int_lap_residual_decomposed` | `lap_time_s`, `compound_component_s`, `dirty_air_tax_s`, `laps_past_cliff`, `age_in_stint`, `valid_lap_in_stint`, `compound`, `constructor_id`, `stint_id`, `fuel_mass_kg`, `correction_weight`. **Not** the base or the fuel/rubber/ambient/constructor components. |
| `int_lap_anomaly_flags` | `anomaly_class`, `is_rain_lap`, `is_out_lap`, `is_in_lap` |
| `int_stint_geometry` + `int_lap_air_state` | the valid-lap sequence and `air_state_dominant` for the recovery overlay |
| `int_constructor_deg_sensitivity` | `deg_slope_s_per_lap`, the car's degradation character |
| `int_stint_end_regime` | `stint_end_cause`, `is_censored_stint` (context, V6) |
| `int_pit_strategy_value` | `strategy_verdict`, `opportunity_cost_s` (context, V6c) |
| `int_lap_thermal_proxy` | `push_residual`, fuel-neutral since WI-15b (V2c style strata) |
| `int_lap_telemetry_aggregates` | `lift_coast_share` (fuel-saving context, V2d) |
| `int_driver_race_skill_loro` | `driver_skill_field_s`, `driver_skill_loro_mean_s` (convergent validity) |
| `int_lap_fuel_state`, `dim_circuits` | V4 physics check only |

### New

| Model | Grain · PK | Reads | Holds |
| :-- | :-- | :-- | :-- |
| `intermediate/int_driver_isolation_lap_panel` | lap · `lap_id` | residual, anomaly flags, stint geometry, air state | Ω, `x_s`, `field_n`, `y_s`, `tyre_offset_vs_field_s`, `tyre_phase`, `is_recovery`, `stint_phase`, context columns. **The fit's input.** |
| `tasks/coefficients/fit_constructor_car_fe.py --panel isolation` | → `data/fits/constructor_car_fe_isolation.parquet` | the panel | `car_iso_s`, `car_term_source`, provenance (`build_provenance`), connected-set diagnostics |
| `intermediate/int_constructor_car_fe_isolation` | (race_year, race_id, constructor_id) | fits source | thin reader, same shape as `int_constructor_car_fe` |
| `intermediate/int_driver_isolation_lap_pace` | lap · `lap_id` | panel + car | `pace_isolated_gain_s` (p). It exists so the stint model and the lap model subtract the car the same way, instead of two copies drifting apart. |
| `intermediate/int_driver_isolation_stint_tyre` | stint · `stint_id` | lap pace, deg sensitivity | line (`n_line_laps`, `line_slope_s_per_lap2`, `line_mean_pace_gain_s`, `line_mean_age_laps`, `line_ref_age_laps`, Sxx), SEs, noise terms |
| `intermediate/int_driver_isolation_lap_values` | lap · `lap_id` | lap pace + stint tyre | `pure_skill_gain_s`, `pure_is_extrapolated` |
| `marts/fct_driver_isolation_pair_lap` | lap × peer · (`lap_id`, `peer_lap_id`) | lap values | both drivers, both ages, `is_teammate`, relative pace (raw, age-matched within ±2 laps), the three identity terms and `pace_gap_gain_s`. Probe size is about 0.6 M rows. **This is the table the agent uses for "vs HAM" questions.** |
| `marts/fct_driver_isolation_lap` | lap · `lap_id` | lap values + pair lap | lap values, peer aggregates, the two 5-lap windows (pure, relative), `window_n_*`, `window_mixed_phase`, per-window λ, `confidence_pct`, `trust_label` |
| `marts/fct_driver_isolation_stint` | (`stint_id`, `stint_phase`), with phase ∈ early/mid/cliff/recovery/**all** | lap mart, pair lap, stint tyre, context models | per-rating (pure, relative) raw, SE, λ, shrunk, `confidence_pct`, `trust_label`; stint-level identity terms; context: strategy verdict, opportunity cost, end cause, `tyre_offset_vs_field_s`, `lift_coast_excess`, dirty-air share |
| `marts/fct_driver_isolation_race` | driver-race · `driver_race_id` | lap mart, pair lap | the same, rolled up with lap weighting; the **same surrogate-key recipe as `fct_driver_skill_features`**, so the two join directly |
| `seeds/driver_isolation_method_scores.csv` | rating | written by the validation script | `rating`, `method_score`, `grade`, `tests_applicable`, `tests_passed`, `critical_failed`, `validated_at`, `substrate` (git SHA + warehouse mtime), `report_path`. It is committed with three `unvalidated` rows and NULL scores, so `WI-16a` builds without it being filled. |
| `scripts/validate_driver_isolation.py` | reads the warehouse read-only | all of the above | V1–V6, the method scores, the examples; `--write-seed` writes the seed |

Build the 'all' phase row in the stint mart with **`UNION ALL`, not `GROUPING SETS`**. A NULL phase
must never be mistaken for the rollup.

### Changed

- `fit_constructor_car_fe.py`: add `--panel {pace_delta,isolation}`, defaulting to `pace_delta`. The
  default path must stay byte-identical (T49), because `int_driver_race_skill_loro` and Ghost
  Standings consume it.
- `src_fits.yml`: a `constructor_car_fe_isolation` source, documented like `constructor_car_fe`.
- `dbt_project.yml` vars: `isolation_min_field_n: 8`, `isolation_window_laps: 5`,
  `isolation_window_min_laps: 3`, `isolation_peer_age_tolerance: 3`, `isolation_min_stint_laps: 6`,
  `isolation_min_peer_stints: 2`, `isolation_recovery_laps: 3`,
  `isolation_recovery_min_dirty_run: 2`, `isolation_exclude_races: ['2020_1']`. Each gets the comment
  style the existing vars use: what it is, why this value, and what measured it. Render the list var
  with a Jinja loop; a Python list does not render as SQL.
- `Makefile`: a `car-fe-isolation-fit` target following `car-fe-fit` (build the panel's ancestors,
  build the panel, fit), wired into `dbt-dev-full` after `car-fe-fit`.
- `intermediate/schema.yml`, `marts/schema.yml`: every new column documented, with sign and units in
  the description; PK `unique` + `not_null`; `accepted_values` on `stint_phase` and `trust_label`.
- Model headers: each new model states its grain, its sign convention, and the
  **leakage warning** from `fct_cliff_prediction_features`, reversed: *these ratings are functions of
  the residual trajectory and must never be referenced by an ML-contract mart* (T48).
- Model and test counts in `README.md`, the docs front pages and the Makefile's
  `dbt-dev: Build all 72 dbt models` comment. `scripts/docs_facts.py` fails until they agree.
- Docs: `docs/decomposition/driver-isolation.mdx` (after `tyre-cliff` in `docs.json`), then
  regenerate `gen_dbt_reference.py` / `gen_schema_reference.py` output.

### Deliberately not changed

- **`fct_driver_skill_features`: no schema change.** It is the race-grain input of a trained model.
  Putting an unvalidated rating into it couples the rating to that model's contract and to the gate.
  `fct_driver_isolation_race` joins to it on `driver_race_id`. Promoting a validated rating into it is
  a follow-on, and it would owe the gate.
- **The existing rating chain** (`int_driver_season_ratings` → `int_era_normalized_driver_rating`,
  `WI-14b`'s FD5 territory): untouched. Tier 1 uses its own car term, so FD5's P20-vs-median question
  does not reach it. V2e compares the two.
- **The app:** no export and no page. That is follow-on work, and `W25`/`W28` are live export hazards
  anyway.
- **The ML contract:** nothing is added (T48). **This WI does not owe the gate**, because no label or
  contract feature moves.

### DAG and build order

```
int_lap_residual_decomposed ─┐
int_lap_anomaly_flags ───────┼─► int_driver_isolation_lap_panel ─► [fit --panel isolation] ─► int_constructor_car_fe_isolation
int_stint_geometry + air ────┘                    │                                                     │
                                                  └──────────────► int_driver_isolation_lap_pace ◄──────┘
                                                                         │
                                          int_constructor_deg_sensitivity ─► int_driver_isolation_stint_tyre
                                                                         │                 │
                                                                         └► int_driver_isolation_lap_values
                                                                                            │
                                                  fct_driver_isolation_pair_lap ◄───────────┤
                                                  fct_driver_isolation_lap  ◄───────────────┤  (+ seed driver_isolation_method_scores)
                                                  fct_driver_isolation_stint / _race ◄──────┘
```

`make car-fe-isolation-fit` → `dbt build -s int_constructor_car_fe_isolation+`. Measure on a
**scratch copy** of `data/dev.duckdb`, built from the working tree with
`dbt build -s +fct_driver_isolation_race` so that W20/W23's stale upstream is rebuilt in the copy.
Never touch `data/ci.duckdb`. Rebuilding `data/dev.duckdb` itself is the orchestrator's call (see W20).

### SQL sketches (the non-obvious CTEs)

**Recovery overlay** (in the panel; runs over valid laps, not Ω, so the dirty-air runs are complete):

```sql
air AS (
    SELECT g.lap_id, g.stint_id, g.lap_number,
           COALESCE(ai.air_state_dominant = 'dirty_air', FALSE) AS is_dirty
    FROM {{ ref('int_stint_geometry') }} AS g
    LEFT JOIN {{ ref('int_lap_air_state') }} AS ai ON g.lap_id = ai.lap_id
    WHERE g.is_valid_lap
),
runs AS (
    SELECT *,
           SUM(CASE WHEN is_dirty IS DISTINCT FROM prev_dirty THEN 1 ELSE 0 END) OVER (
               PARTITION BY stint_id ORDER BY lap_number
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS run_id
    FROM (SELECT *, LAG(is_dirty) OVER (PARTITION BY stint_id ORDER BY lap_number) AS prev_dirty FROM air)
),
run_len AS (
    SELECT stint_id, run_id, BOOL_AND(is_dirty) AS run_is_dirty, COUNT(*) AS n_laps
    FROM runs GROUP BY stint_id, run_id
),
recovery AS (
    SELECT r.lap_id,
           COALESCE(
               NOT r.is_dirty
               AND p.run_is_dirty
               AND p.n_laps >= {{ var('isolation_recovery_min_dirty_run') }}
               AND ROW_NUMBER() OVER (PARTITION BY r.stint_id, r.run_id ORDER BY r.lap_number)
                   <= {{ var('isolation_recovery_laps') }},
               FALSE) AS is_recovery
    FROM runs AS r
    LEFT JOIN run_len AS p ON p.stint_id = r.stint_id AND p.run_id = r.run_id - 1
)
```

**Leave-driver-out peer slope** (in the stint tyre model):

```sql
peer AS (
    SELECT e.stint_id,
           COUNT(o.stint_id)            AS n_peer_stints,
           MEDIAN(o.beta_s)             AS beta_peer_race,
           MEDIAN(o.car_deg_s_per_lap)  AS car_deg_peer_race
    FROM with_car AS e
    LEFT JOIN with_car AS o
        ON  o.race_year = e.race_year AND o.race_id = e.race_id
        AND o.compound = e.compound
        AND o.driver_id <> e.driver_id          -- not just o.stint_id <> e.stint_id: a driver's own second stint on the compound is not a peer
        AND o.beta_s IS NOT NULL
    GROUP BY e.stint_id
)
```

**Pair lap** (the mart; the identity terms are computed here, not re-derived downstream):

```sql
SELECT
    a.lap_id, b.lap_id AS peer_lap_id, a.race_year, a.race_id, a.lap_number,
    a.driver_id, b.driver_id AS peer_driver_id, a.constructor_id = b.constructor_id AS is_teammate,
    a.compound, a.age_in_stint, b.age_in_stint AS peer_age_in_stint,
    b.lap_time_s - a.lap_time_s                                                     AS relative_pace_raw_gain_s,
    (b.lap_time_s - a.lap_time_s) - (b.compound_component_s - a.compound_component_s) AS relative_pace_gain_s,
    a.pace_isolated_gain_s - b.pace_isolated_gain_s                                 AS pace_gap_gain_s,
    a.pure_skill_gain_s    - b.pure_skill_gain_s                                    AS pure_gap_gain_s,      -- NULL if either tactical is NULL
    a.tactical_gain_s      - b.tactical_gain_s                                      AS tactical_gap_gain_s,
    b.car_iso_s            - a.car_iso_s                                            AS car_advantage_gain_s,
    b.dirty_air_tax_s      - a.dirty_air_tax_s                                      AS traffic_advantage_gain_s
FROM {{ ref('int_driver_isolation_lap_values') }} AS a
INNER JOIN {{ ref('int_driver_isolation_lap_values') }} AS b
    ON  b.race_year = a.race_year AND b.race_id = a.race_id AND b.lap_number = a.lap_number
    AND b.compound = a.compound AND b.driver_id <> a.driver_id
    AND ABS(b.age_in_stint - a.age_in_stint) <= {{ var('isolation_peer_age_tolerance') }}
```

**The 5-lap window** (in the lap mart):

```sql
WINDOW w AS (PARTITION BY stint_id ORDER BY lap_number
             RANGE BETWEEN {{ var('isolation_window_laps') - 1 }} PRECEDING AND CURRENT ROW)
```

---

## Validation (`WI-16b`)

The script is `scripts/validate_driver_isolation.py`. It opens the warehouse read-only and writes
`_roadmap/_fixes/_evidence/wi-16-<date>/validation.json` plus `validation-report.md` (the same pattern
as `wi-15a-2026-09-25/`). **Thresholds are pre-registered here and are not tuned on results.** A test
that fails is reported as failing. Moving a threshold is a spec deviation, logged with a reason and
corrected in this doc. Each test returns PASS (1.0), MARGINAL (0.5) or FAIL (0.0).

Data: 2018–2025 (8 seasons, 172 races). **Decisions use 2018–2024 only.** 2025 is reported as
confirmation and never as a selection input: FD4 says 2025 was already consumed as a selection fold.
These ratings have no tuned hyperparameters, so they do not spend a holdout, but the discipline costs
nothing.

## As built: WI-16b (2026-10-03)

**Publication scope:** Relative pace only. Pure pace deferred post-v15.

**Validation evidence:** `_roadmap/_fixes/_evidence/wi-16-2026-10-03/validation-report.md` (markdown summary) and `validation.json` (raw results).

| Rating | Method score | Grade | Decisive checks | Path forward |
| :-- | :-: | :-: | :-- | :-- |
| Pure pace | 0 (F) | F | V1b (0.603 vs ≥0.652), V1c (1.05 vs ≤1.5) | Post-v15: per-era UI flag or design review of era definition; currently unfixable without shrinking coverage to 36% |
| Relative pace | 0.857 | B | V3_tier3 (1.0), V5 (1.0); V4 fails but not critical | Ship in v15 with confidence shrinkage; publish at race and stint grain only |

**Tactical:** Cancelled 2026-09-28 due to fundamental noise-to-signal ratio (1.4x, signal variance < measurement noise).

**Tracking:** Post-v15 work moves to the ML lab roadmap (`_roadmap/_improvements/`). Do not attempt to fix pure within v15; the root cause is architectural and requires the era-boundary design decision.

### V1: cross-season stability ("does pure skill hold 2018→2025, and across the 2022 rules?")

- **V1a split-half.** Per season, take each driver-season's race-mean pure skill on odd rounds and on
  even rounds, for drivers with ≥ 5 races in each half. Compute the Spearman correlation per season.
  Median across seasons: ≥ 0.60 PASS, 0.40–0.60 MARGINAL, < 0.40 FAIL. Tactical uses the same design
  with a lower bar (≥ 0.30 PASS, 0.15–0.30 MARGINAL), because tyre management is a noisier trait.
- **V1b adjacent seasons.** Pearson correlation of shrunk driver-season pure skill for drivers with
  ≥ 8 races in both seasons. Median over the 7 season pairs ≥ 0.50 PASS. Report 2022/23, 2023/24 and
  2024/25 individually. The 2021→2022 pair must be ≥ 0.7 × the median of the other pairs; if it isn't,
  the rule change broke the car term, not the drivers.
  **Amended (W69, 2026-10-03):** V1b checks pure-skill correlation within each era only (2018, 2019-21, 2022-25), not across era boundaries. The failure is the per-era fit design, not regulations. Cross-era comparison is not claimed.
- **V1c movers.** For drivers who changed team between seasons, compare |Δ pure skill| with drivers
  who stayed. Movers' median ≤ 1.5 × stayers' is PASS. Use a bootstrap CI clustered by driver. There
  are about 21 movers (03a), so report the CI honestly and do not over-read it. A pure skill that jumps
  with the car is car leakage.
- Critical for pure (see the matrix).

### V2: stratified and confound tests ("is it the car, the compound, or the driver's style?")

- **V2a within-driver car leakage (critical for pure).** Demean race-level pure skill within
  driver-season, and demean `car_iso_s` within constructor-season. Then compute
  |corr(demeaned pure, demeaned car)| over race rows: ≤ 0.15 PASS, ≤ 0.25 MARGINAL. **Do not test the
  raw cross-sectional correlation.** Good drivers really do get good cars, so a non-zero raw
  correlation is selection, not leakage. Demeaning removes the selection; the race-to-race variation in
  car pace (upgrades, track fit) that remains should not move the driver.
- **V2b compound, within driver-race.** For drivers who ran two dry compounds in the same race (same
  driver, same car, same race, so no selection), compute the mean pure-skill difference per compound
  pair (e.g. MEDIUM − HARD) per season. All |mean| ≤ 0.05 s is PASS, ≤ 0.10 s MARGINAL. A failure means
  the seed's compound levels are off, which is F42a or WI-02b territory: report it and fix it upstream.
- **V2c aggressive vs conservative.** (i) **Cross-fitted** pure–tactical independence. Split each
  stint's line laps into odd and even valid ordinals. Compute tactical from the odd laps' slope and
  pure from the even laps, adjusted by the even laps' own slope. Pearson at driver-season grain in
  [−0.3, 0.3] is PASS. *Without cross-fitting, the slope's estimation noise enters pure and tactical
  with opposite signs and manufactures a negative correlation, which would look exactly like the
  confound this test hunts for.* (ii) Style strata: the tercile of driver-season mean `push_residual`
  on early-phase laps. Within the top tercile and within the bottom tercile, the Spearman correlation
  of pure skill on early laps against pure skill on mid laps must be ≥ 0.6. If the aggressive drivers'
  early pure is inflated by pushing, their ranking diverges more.
- **V2d fuel saving (report only).** Pure skill on laps where `lift_coast_share` is above the same-lap
  field median by more than 1 MAD, against all other laps. This confound is known and cannot be
  corrected (*Limitations*), so there is no threshold; the size is reported.
- **V2e convergent validity (soft).** Spearman of driver-season pure skill against the season mean of
  `driver_skill_field_s` ≥ 0.6, and against `scripts/driver_network_rating.py`'s Massey rating
  ≥ 0.5. MARGINAL below either.

### V3: peer-pair validation ("do the residuals make sense at equal strategy?") and backtest

Matched pairs are the one place where fuel, compound and track are equal by design, so the model's
remaining claims can be checked there:

- **V3a car pricing at matched strategy.** Over race-pair means of cross-team matched pairs,
  corr(`pure_gap_gain_s`, `car_advantage_gain_s`) in [−0.15, 0.15] is PASS. Positive means the car is
  under-removed and has leaked into pure. Negative means it is over-removed.
- **V3b traffic pricing at matched strategy.** Over pair-laps where exactly one of the two is in dirty
  air, corr(`pure_gap_gain_s`, `traffic_advantage_gain_s`) in [−0.10, 0.10] is PASS. Also, the pair's
  mean pure gap on those laps should be within 0.05 s of the same pair's gap on laps where both are in
  clean air. A failure means θ_air is mispriced, and that finding goes back to `WI-01`.
- **V3c teammates.** For teammate pairs, `car_advantage ≡ 0`, which T42 checks structurally. The
  matched race-mean pure gap against `int_driver_race_skill_loro`'s median teammate gap: Spearman
  ≥ 0.7 PASS.
- **V3d rolling-origin backtest (2018–2024).** For each season and each round k ≥ 5, predict every
  matched pair's race-k mean `relative_pace_gain_s` from each driver's shrunk pure and tactical over
  rounds < k, plus race k's car and traffic terms. Compare with two baselines: car + traffic only, and
  the pair's last raw matched delta. PASS if the model beats both on MAE with a paired bootstrap CI
  (clustered by race) excluding 0. The test is for *driver persistence*; race k's car term is used
  in-sample on purpose, because the car is not what is being tested.
- **Tier 3's own V3 (critical for relative).** (i) Coverage: ≥ 80% of Ω laps have at least one peer
  (the probe measured 88.3%). (ii) The ΔC age adjustment must *reduce* the within-pair lap-to-lap
  variance compared with the raw delta. `int_lap_normalized_pace` is the precedent here: a heuristic
  adjustment made its metric worse, so this one has to earn its place.

### V4: physical sanity ("does fuel cost match known consumption?")

- **V4a fuel, absolute.** Replicate `transform/analyses/deg_slope_fuel_deconfounding.sql`'s
  across-stint design (the same tyre age recurs at different fuel loads, which breaks the collinearity
  between age and fuel) on the un-centred residual: `resid ~ age + fuel_mass_kg` with (race, driver)
  fixed effects. The implied total fuel effect is the seed's `weight_penalty_factor` (0.021–0.032,
  median 0.025 s/kg) plus the fitted residual coefficient. It must lie in the **physical band
  [0.025, 0.040] s/kg** (the widely quoted "10 kg ≈ 0.3 s"). The 2026-06-11 run of that analysis found
  a residual of +0.005 s/kg, giving about 0.030, which is inside. Consumption is regulatory by
  construction since WI-05 (1.73–1.83 kg/lap, from 105/110 kg over the scheduled distance), so report
  the implied burn-off gain, factor × kg/lap, of about 0.045–0.07 s/lap. Weight 0.5 for pure. This
  checks the absolute decomposition the agent will *quote* ("fuel cost him X"), not the ratings.
- **V4b immunity (implementation check).** The same design on `pace_isolated_gain_s`:
  |fuel coefficient| ≤ 0.002 s/kg. Field-centring cancels fuel exactly, so a failure here is a bug.
- **V4c compound ordering.** Matched same-lap pairs across compounds with age ≤ 5 on both sides: the
  softer compound is faster on average in every season. This guards against F42a regressing. Weight
  0.5 for pure and relative, since tier 3's age adjustment uses the seed.

### V5: temporal smoothness ("clean or noisy?")

- **V5a.** Lag-1 autocorrelation of `pace_isolated_gain_s` around its stint line: |ρ₁| ≤ 0.30 PASS
  (the probe measured 0.18). Higher means unmodelled structure (traffic, thermal) is leaking in.
- **V5b jitter ratio.** Median within-stint SD of `pure_skill_5lap_gain_s` divided by τ (the
  between-driver SD at stint grain): ≤ 1.0 PASS, > 1.5 FAIL. On FAIL the 5-lap window is suppressed
  and only stint and race grain are published.
- **V5c tactical.** Split-half stability of `m_s` (odd against even line laps) across stints:
  Pearson ≥ 0.3 PASS. The pre-cliff tactical is linear in age and so smooth by construction; this
  tests what isn't.
- **V5d relative.** Lag-1 autocorrelation of lap-level `relative_pace_gain_s` around its stint mean
  ≤ 0.40, plus the same jitter ratio as V5b.
- Report only: the share of stints where the 5-lap pure changes sign two or more times.

### V6: natural experiment ("do pit decisions come out the way the tactical rating predicts?")

The prediction is that drivers whose tyres fade faster than their peers' pit earlier, when the pit
wall chooses the moment. When a safety car chooses it, the link should weaken. To avoid a mechanical
link between the slope and the stint length (longer stints sample older, more curved tyre ages),
**V6 uses `m_s^(8)`: the tactical slope fitted on each stint's first 8 line laps only**, with peers
on the same window. That makes it a genuine forward prediction, because laps 2–9 predict a stop that
comes later.

- **V6a (critical for tactical).** Over uncensored stints with a green-flag end
  (`int_stint_end_regime`), and at least 10 line laps: Spearman(`m_s^(8)`, stint length − the median
  length of same-race, same-compound, same-stint-number peers) > 0 with a 95% CI (bootstrap by race)
  excluding 0 is PASS. A positive point estimate with a CI including 0 is MARGINAL.
- **V6b placebo contrast.** The same correlation in SC/VSC-ended stints, where the length was forced,
  must be smaller: green minus SC > 0 with a CI excluding 0 is PASS.
- **V6c.** Stints with `strategy_verdict = 'overran'` have a lower `cliff_excess_gain_s` than
  `'optimal'` ones (mean difference < 0). Weight 0.5.

### Compiling the confidence

`method_score(rating) = 0` if any **critical** test for that rating FAILs, and otherwise
`Σ w·s / Σ w` over the applicable tests.

| Test | pure | tactical | relative |
| :-- | :-: | :-: | :-: |
| V1 stability | 2 · **critical** | 1 | — |
| V2 confound | 2 · **critical** (V2a) | 1 (V2c-i) | — |
| V3 peer pair / backtest | 1 | 1 | 2 · **critical** (tier-3 V3) |
| V4 physics | 0.5 | — | 0.5 |
| V5 smoothness | 1 | 1 | 1 |
| V6 natural experiment | — | 2 · **critical** | — |

Each test's own score is the mean of its sub-checks, excluding report-only ones. The grade is A
(≥ 0.9), B (≥ 0.75), C (≥ 0.5) or F (< 0.5, or a critical fail), and F means the rating is
**suppressed**. The headline sentence the docs and the agent use is "pure skill: method 94% (A)". The
per-row number is `confidence_pct = 100 × λ × method_score`. That combination is a declared policy,
not an estimated quantity, and the docs page says so.

---

## Acceptance

- The three ratings (`pure_skill_gain_s`, `tactical_gain_s`, `relative_pace_gain_s`) exist per lap,
  per 5-lap window, per **driver-race-stint** and phase (`fct_driver_isolation_stint`, including an
  `all` row per stint), and per driver-race. Each has SE, λ, a shrunk value, `confidence_pct` and
  `trust_label`.
- The cumulative identity closes to 1e-6 on every pair-lap, and `pure + tactical = p` on every lap
  where tactical is non-NULL (T42).
- Base invariance is demonstrated: `y_s` computed from lap time equals `y_s` recomputed from the
  residual chain on every lap with a measured base (T41). This is the mechanical form of the FD1
  resolution.
- Coverage is reported against the probe: pure on about 95% of Ω laps, tactical on ≥ 80% of stints,
  relative on about 88% of Ω laps. A shortfall of more than 5 points is explained.
- The validation report states PASS, MARGINAL or FAIL with the statistic and CI for every V-test, the
  method score and grade per rating, and the seed is written from it.
- **At least three worked examples**, each showing all three ratings, the identity split, the
  confidence and a one-sentence plain-language reading. Each comes with the expectation that was
  registered here, and a statement of whether it held:
  1. **VER vs HAM, 2021 Styrian GP (`2021_8`).** Probe: VER +0.24 s/lap over 57 matched laps.
     Expectation: tier 3 positive, split between car and driver; no expectation about the split.
  2. **HAM vs VER, 2021 São Paulo GP (`2021_19`).** Probe: HAM +0.05 s/lap over 41 matched laps.
     `docs/findings/sao-paulo-2021.mdx` publishes "brilliant driving *and* brilliant strategy" using
     pre-08m/08q component values (+8.30 s compound penalty at age 25, a flat 0.50 s dirty air). The
     example has to say whether tiers 1 and 2 plus `tyre_offset_vs_field_s` support that split. If
     they don't, **raise a truth-pass item for that page; do not edit it in this WI.**
  3. **VER vs PER, 2023 Saudi Arabian GP (`2023_2`), same car.** Probe: VER −0.40 s/lap over 40
     matched laps; he started 15th. `car_advantage ≡ 0` by construction, which is a structural check.
     Expectation: a large share of the deficit lands in `traffic_advantage_gain_s`. If `pure_gap`
     carries most of it instead, the dirty-air term under-prices traffic, and that is a finding for
     `WI-01`'s θ re-estimate.
  Optional fourth: VER vs PER, 2023 Spanish GP (`2023_7`), probe +0.57 s/lap over 50 laps, clean air
  at the front. Expectation: mostly pure gap.
- `docs/decomposition/driver-isolation.mdx` states what each rating means, the question it answers,
  its sign, when to trust it (the reliability table with measured numbers, and "the 5-lap window is
  about half signal"), the method grades, and *Limitations* below, including the wet-race and
  fuel-saving blind spots. Numbers are quoted from `validation.json`, not re-typed.

---

## Tests to add

New ids, the first past the audit's T1–T39. Singular tests go in `transform/tests/` unless marked
pytest.

| Id | File | Asserts |
| :-- | :-- | :-- |
| T40 | `assert_isolation_field_centring.sql` | per (race, lap): \|MEDIAN(y_s)\| < 1e-9 and `field_n >= var` |
| T41 | `assert_isolation_base_invariance.sql` | on laps with `base_track_pace_s IS NOT NULL`: `y_s` equals the same centring applied to `driver_skill_residual_s + constructor_component_s` within 1e-6. **The FD1 proof.** |
| T42 | `assert_isolation_cumulative_identity.sql` | pair lap: `relative = pace_gap + car_adv + traffic_adv`, and `pace_gap = pure_gap + tactical_gap` where both are non-NULL; lap: `pure + tactical = p` where tactical is non-NULL; teammate pairs: `car_advantage = 0`. All within 1e-6. |
| T43 | `assert_isolation_sign_convention.sql` | from raw geometry: teammates on the same lap, same compound and same age whose raw times differ by > 0.5 s, with \|ΔD\| < 0.25 s → the faster one has the larger `pace_isolated_gain_s`, and `relative_pace_raw_gain_s > 0` on their pair row |
| T44 | `assert_isolation_window_no_forward_reach.sql` | recomputing each 5-lap window from laps ≤ l in the same stint reproduces the stored value (pattern: `assert_corner_trailing_window_no_forward_reach`) |
| T45 | `assert_isolation_phase_partition.sql` | every Ω lap has exactly one `stint_phase`; `cliff` iff `laps_past_cliff > 0` unless `is_recovery`; recovery share in [1%, 10%] (severity `warn`) |
| T46 | `assert_isolation_small_sample_nulls.sql` | window values NULL below 3 laps; tactical NULL when `n_line_laps < 6`; relative NULL when `n_peers = 0`; no `confidence_pct` without λ; no tactical value equal to exactly 0.0 where `m_s` is NULL (the COALESCE trap) |
| T47 | `assert_isolation_reliability_bounds.sql` | 0 ≤ λ ≤ 1; \|shrunk\| ≤ \|raw\|; sign(shrunk) = sign(raw) or shrunk = 0 |
| T48 | pytest, `ml/tests/test_manifest_contract.py` | no ML-contract mart (`fct_cliff_prediction_features`, `fct_stint_features`, `fct_lap_residuals`, `fct_driver_skill_features`) has an isolation model among its ancestors in `target/manifest.json` |
| T49 | pytest, `transform/tasks/coefficients/tests/test_fit_constructor_car_fe.py` | the default `--panel pace_delta` output equals HEAD's on a fixture panel; `--panel isolation` normalises to a lap-weighted mean of 0 per race |

---

## Definition of done

**`WI-16a`** (MEASURED → LANDED once the orchestrator re-runs it):

- All nine models build on a scratch copy of `data/dev.duckdb` rebuilt from the working tree. T40–T49
  pass, and the existing suite still passes (`dbt build -s +fct_driver_isolation_race` in the copy;
  `pytest ml/tests transform/tasks/coefficients/tests`).
- **Reproducibility against the probe.** In `fct_driver_isolation_pair_lap`, the three probe numbers
  come back within ±0.05 s/lap and ±10% on the matched-lap count: `2021_8` VER–HAM +0.24/57,
  `2021_19` HAM–VER +0.05/41, `2023_2` VER–PER −0.40/40. Tier 3 is almost model-free, so a miss here
  means the SQL is not what this doc says it is. (The W20 rebuild moves clean-lap membership slightly,
  which is why there is a tolerance.)
- Coverage numbers recorded. `docs_facts.py` passes with the updated counts. The seed is committed in
  its `unvalidated` state.
- An *As built: WI-16a* section is appended here, including every deviation.

**`WI-16b`** (after `WI-01` LANDED):

- Validation run on a warehouse carrying `WI-01`'s label bump. Evidence is in
  `_evidence/wi-16-<date>/`. The seed is written with `--write-seed` and the marts are rebuilt, so
  `confidence_pct` is populated.
- The three examples are written into the evidence report and the docs page. The São Paulo verdict is
  stated either way.
- The docs page is live in `docs.json` and the reference docs are regenerated.
- An *As built: WI-16b* section is appended here. The orchestrator records the FD1 resolution
  (below), and the W-entries named under *Board registration*.

---

## Estimate

**3.5 days in total: `WI-16a` 2d, `WI-16b` 1.5d.** That assumes a fluent dbt/SQL executor, and it is
more than the 1–2d or 2–3d brackets suggested, for two reasons:

| Piece | Cost | Why it is not free |
| :-- | --: | :-- |
| Panel, phases, recovery overlay, vars | 0.4d | gaps-and-islands run logic; Ω's qualified predicates |
| Car-term fit (`--panel isolation`) + reader + Makefile | 0.3d | connected-set diagnostics, the era fallback, a byte-identical default path |
| Stint tyre model | 0.5d | NaN guards, leave-driver-out peers, season-pool fallback, κ and κ_ref, SEs |
| Lap values, pair mart, lap mart (windows), stint/race marts, reliability | 0.5d | the identity has to close everywhere, NULLs have to propagate honestly |
| Tests T40–T49 + schema docs | 0.3d | |
| Validation script V1–V6 + seed writer | 1.0d | cross-fitting (V2c), leave-window design (V3b), rolling-origin backtest (V3d), bootstrap CIs |
| Examples ×3, docs page, deviations | 0.5d | São Paulo needs care, because it may contradict a published page |

It fits in **2.5–3d** if you drop the race mart (the agent can roll up from the stint mart), V3d's
backtest and the recovery overlay. The cuts would be, in order of least lost: recovery (a 3% stratum),
then the race mart, then V3d. Don't cut V2c's cross-fitting or V6's first-8-lap window. Those are what
stop the validation from grading its own homework.

**Model:** `opus-5` for both. The spec makes the judgment calls, and what is left is designing
aggregations. Escalate `WI-16b` to `fable-5.1` if V2c, V3 or V6 land MARGINAL. Borderline statistics
are where a plausible wrong number hides.

---

## Dependencies

- **`WI-16a` has none.** It needs `WI-15a` (landed; dirty-air coding for the recovery overlay) and
  `WI-15b` (landed; the fuel-neutral `push_residual` V2c uses later). The dev warehouse is stale for
  both (W20, W23), which is why it is measured on a rebuilt scratch copy.
- **`WI-16b` depends on `WI-01`** (θ_air reaches `D`; F42a reaches cross-compound `C`) and on
  `WI-16a`. `WI-01` depends on `WI-15a` (met), on `FD1` (resolved by this doc once the user confirms)
  and on `FD2` (open). **So the critical path to validated ratings is FD2.**
- **`WI-02b` (FD3) is not a dependency, but it will move the numbers.** The seed refit changes `C`.
  Tier 2 is largely immune before the cliff, because peers on the same compound share a linear wear
  term and it cancels in `β_s − β_peer`. Pure's cross-compound level (V2b) and tier 2's cliff part are
  exposed. A watch entry tracks the re-run.
- **Independent of `WI-14b` (FD5).** It uses a different car term, and V2e only reads
  `driver_skill_field_s`, which FD5 does not change.
- **Blocks nothing on the board.** It enables the items under *Follow-on*.

---

## Limitations: what these ratings cannot see

- **Per-driver fuel strategy.** The fuel model gives every car on a lap the same load, so fuel
  management is invisible to it. The only per-driver signal is telemetry `lift_coast_share` (91% of
  2018 laps, 100% from 2019), and that cannot tell fuel-saving from tyre-saving. A driver told to save
  fuel reads as lower pure skill, and possibly higher tactical. V2d sizes this; nothing corrects it.
  **Side finding, out of scope:** `int_lap_fuel_state.fuel_delta_vs_expected` is identically
  `−fuel_consumption_rate_kg_per_lap` on every lap (max deviation 1.4e-14 over 161,040 laps).
  `(initial − mass) − rate × lap_number = rate(lap − 1) − rate × lap = −rate`. Its comment says it
  detects lift-and-coast, and `int_lap_telemetry_aggregates.sql:281-288` says `lift_coast_share` "is
  consumed alongside" it "so the model can separate them". It cannot. No ML-contract column reads it.
  Recommended as a debt watch entry, or as a candidate F56 if the orchestrator wants it on the finding
  ledger.
- **Wet races.** Excluded by Ω. The ratings say nothing about wet-weather skill (compare F27).
- **Car-term identification** rests on the teammate network and on "skill constant within an era".
  Its uncertainty is not propagated into SE. V1c and V2a are the checks.
- **Car degradation character** comes from `int_constructor_deg_sensitivity`, which pools both of a
  team's drivers inside its stint FE. It therefore contains the team's average management skill, so a
  driver's tactical rating is **shrunk toward his teammate's** by construction. A driver far better
  than his teammate at managing tyres is under-credited. 03c's AKM decomposition of the degradation
  slope is the fix. Its 2018 cells use 2018's compound labels and match poorly, so expect many
  `car_deg_imputed` 2018 stints.
- **Team strategy against driver execution.** Staying out is the pit wall's decision. The tactical
  rating measures the tyre's behaviour relative to peers, not whether staying out was right; that is
  `opportunity_cost_s`, carried as context.
- **2018 traffic.** About 9% of 2018 laps have no telemetry and are coded clear air (FD6). `D = 0` on
  those laps biases 2018 pure skill for drivers who were really in traffic, and it undercounts
  recovery. Flag 2018 in the docs.
- **Rolling windows are retrospective in two places:** the car term (fitted on all races) and `m_s`
  (the whole stint). Tiers 1 and 3's lap values and windows are otherwise trailing. None of this is
  live-safe yet; see *Follow-on*.

---

## How this could be wrong

- **The seed's compound levels could be off per race.** Then `C` biases pure skill by compound, and
  field-centring doesn't help, because C differs by driver. V2b's within-driver-race design detects
  it. Nothing here fixes it; that is WI-02b's job.
- **θ_air could be mispriced.** Then traffic leaks into pure. V3b detects it at matched strategy and
  example 3 is built to expose it.
- **Tactical could be noise.** About 16 line laps give a slope SE of around 0.024 s/lap² against
  real differences that are probably of the same order. If V1a-tactical and V5c land MARGINAL, publish
  tactical at race or season grain only.
- **The level/slope split has a reference point** (`age_ref` = the first clean lap). A driver who
  conserves early and attacks late has his early caution counted against pure, and gets it back in
  tactical. That is a declared attribution rule, not a discovery, and V2c tests whether it
  systematically favours one driving style.
- **Peers share a lap and a compound, not a situation.** A peer fighting for position, or one under
  team orders, is not neutral. The pair means are averages over these situations, not controlled
  comparisons, and the docs should say so.

---

## Design notes: the questions the brief left open

- **Per-sector or per-corner granularity? Not as rolling ratings; yes as an explanation layer.**
  `int_sector_residual_decomposed` allocates physics to sectors *proportionally* (its own header says
  so), so sector-level pure skill mostly re-spreads the lap residual by sector-time share. The real
  information is the deviation from proportional, and that is too noisy inside a 5-lap window. The
  corner route already exists: `int_corner_skill_residuals` → `mart_corner_skill_driver` (braking /
  mid-corner / exit against trailing field medians). The worthwhile follow-on (about 1d) is a
  stint/race-grain join that answers "where does his pure-pace edge come from", which is exactly the
  "why" an LLM answer needs. It should not become a fourth rating.
- **Few clean laps.** Hard floors first (3 laps per window, 6 line laps for a slope, 1 peer), then EB
  shrinkage with λ as the confidence, so a thin estimate is pulled toward the field and says so. Floors
  alone make a cliff at the threshold; shrinkage alone publishes 2-lap numbers.
- **Per-rating or per-driver-race confidence? Per rating, per row.** The three ratings fail
  differently. Tier 1 needs clean laps, tier 2 needs slope leverage (a long stint), and tier 3 needs
  peers on the same strategy. One driver-race can have a solid pure number and a thin tactical one
  (short stint), or no tier 3 at all (an offset strategy). Collapsing them into one driver-race
  confidence hides exactly the caveat the agent has to voice. Method confidence is global per rating;
  estimate confidence is per row.
- **One-stint races.** There are 177 driver-races (5.3%). Every definition is stint-local and
  peer-relative, so no special case is needed. Their stints are censored and so excluded from V6, and
  the race roll-up is simply that stint. The actual failure modes are retirements (short and often
  damaged, handled by Ω and the floors) and red-flag or no-stop races with few clean laps (handled by
  λ). A multi-stint race where one stint is short gets tactical NULL for that stint and pure as
  normal.
- **Backtesting 2018–2024.** Yes, V3d. The ratings are descriptive, so "backtest" means *predictive
  persistence*: ratings from earlier rounds predict the next race's matched-strategy gaps better than
  the car alone or last race's raw gap. Parameters are pre-registered here and never tuned on the
  result. 2025 is confirmation only.
- **A fourth tier, later.** `tyre_offset_vs_field_s` is the strategy position (team-dominated). Adding
  it to the identity gives realised gap = strategy + car + pure + tactical + traffic, which is the full
  "how much of the win was strategy" answer. It is carried as context here and promoted only once V6
  shows the tactical side works.

---

## Follow-on work this enables

1. **LLM query agent.** The four marts are its tools. Use the pair lap table for "X vs Y", the stint
   mart for "how did X manage the mediums", and the race mart for "how good was X at Y". The docs page
   is its reference card. Rules to encode: quote `trust_label` with every number; never state a
   `suppress` or `unvalidated` number; when tier 3 is NULL, say "not comparable on equal tyres right
   now" instead of substituting a cross-strategy delta; explain a gap with the identity terms. Add a
   dbt `exposure` for it.
2. **App page.** A new publication-track item. It needs `export_app_data.py` entries, UI sign handling
   (F50's lesson: the column name carries the sign, so the UI should not re-derive it) and the method
   grade on the page. W25/W28 must clear first.
3. **Race-week / live companion.** It needs an *as-of* variant: the car term fitted on prior rounds
   only, `m_s` as an expanding-window slope (`REGR_SLOPE` works as a framed window aggregate in DuckDB;
   checked), and peers' as-of slopes. It also needs 2026 ingest (W19, FD4).
4. **Corner/sector explanation join** (from *Design notes*).
5. **03c, the AKM decomposition of the degradation slope.** It replaces the car-degradation adjustment
   and removes the limitation that shrinks tactical toward the teammate.
6. **Rating-chain consolidation.** Once `WI-14b` lands, decide whether pure skill replaces, feeds or
   stays beside `int_driver_season_ratings`.
7. **Contract experiment (gated).** Prior-races shrunk pure skill as a stint-life feature. Only lagged
   values, never same-race ones: same-race tactical is a function of the label trajectory (T48 keeps
   it out until then).

---

## Board registration (for the orchestrator; not applied by the author of this doc)

`build-log.json` is not edited by this doc. After review, the orchestrator adds the following and
runs `board.py --check` then `--write-order`:

```json
{
  "groups": [
    {"id": "03", "title": "Driver vs car", "parallel": true,
     "ref": "_improvements/work/03-driver-vs-car.md",
     "summary": "Separating the driver from the car and the tyres: the three-tier driver-isolation ratings (pure, tactical, relative-to-peers)."}
  ],
  "items": [
    {"id": "WI-16a", "group": "03", "stage": "SPEC", "depends_on": [],
     "title": "Driver isolation, build: pure / tactical / relative-to-peers ratings per lap, 5-lap window, stint phase and race",
     "findings": ["FD1 (resolution)"], "doc": "wi/WI-16-cumulative-driver-isolation.md",
     "cost": "2d", "model": "opus-5",
     "note": "Runs now: every rating is field-centred per (race, lap), so the FD1 base cancels (T41). Nine models + fitter flag + T40-T49. Measure on a rebuilt scratch copy (W20/W23 stale). Reproduce the three probe tier-3 numbers within 0.05 s/lap. No gate owed: nothing enters the ML contract (T48)."},
    {"id": "WI-16b", "group": "03", "stage": "SPEC", "depends_on": ["WI-01", "WI-16a"],
     "title": "Driver isolation, validate: V1-V6 report, per-rating method score and confidence, three worked examples, docs page",
     "findings": ["FD1 (resolution)"], "doc": "wi/WI-16-cumulative-driver-isolation.md",
     "cost": "1.5d", "model": "opus-5",
     "note": "Waits for WI-01 (theta_air reaches D; F42a reaches cross-compound C). Thresholds pre-registered in the WI doc; 2018-2024 decides, 2025 confirms. Escalate to fable-5.1 if V2c/V3/V6 land MARGINAL. Sao Paulo 2021 example may contradict docs/findings/sao-paulo-2021.mdx: raise a truth-pass item, do not edit the page here."}
  ],
  "decision_update": {
    "id": "FD1", "status": "RESOLVED", "resolved": "<date the user confirms>",
    "resolution": "A for the label spine: WI-01 proceeds on its Option A method. B's question, pace against what comparable cars actually did, is answered by WI-16's tier-3 rating at matched compound, tyre age and lap, not by the label. The ratings are field-centred per (race, lap), so they are invariant to the base (pinned by T41)."
  },
  "watch_suggestions": [
    {"kind": "pending-ruling", "item": "WI-16b", "title": "Re-run WI-16b validation after WI-02b's seed refit",
     "clears_when": "WI-02b lands and validate_driver_isolation.py is re-run with --write-seed on the refit substrate."},
    {"kind": "debt", "title": "int_lap_fuel_state.fuel_delta_vs_expected is a per-race constant (-rate), not a lift-and-coast signal",
     "clears_when": "The column is dropped or rebuilt from telemetry, and int_lap_telemetry_aggregates' lift_coast_share comment is corrected; or it is accepted as-is on the record."}
  ]
}
```

The `FD1` resolution unblocks nothing by itself. `WI-01` stays `BLOCKED` on `FD2`, and `board.py`'s
`open_decs` handles that correctly. The pointer does not move.

---

## As built: WI-16a (2026-09-26, MEASURED; the orchestrator's re-run is pending)

Built by an opus-5 agent session. Nothing is committed. Everything was measured on a scratch
copy of `data/dev.duckdb`, rebuilt from the working tree; `data/dev.duckdb` and
`data/ci.duckdb` were not written.

### What is in the tree

- **The prior partial attempt was replaced, not extended.** An earlier session had left the
  nine model files, three tests, the fitter flag, the vars and a Makefile target in the
  working tree, unreviewed (timestamps 01:54-01:59 on 2026-09-26). They were not usable as
  built. The stint model joined `e.compound = e.compound` and INNER-joined the degradation
  model inside a LEFT join. The car term was `COALESCE(car_iso_s, 0.0)`. Tactical SE was a
  hard-coded `0.024`. Cliff-lap tactical was NULL instead of the κ term. The panel did not
  carry the columns its consumers read. The reader called an undefined var (`fits_path`). The
  fitter's default path changed its `fit_method`, which would have broken T49. Every file
  was rewritten against this doc.
- **Models (9):** `int_driver_isolation_lap_panel`, `int_constructor_car_fe_isolation`,
  `int_driver_isolation_lap_pace`, `int_driver_isolation_stint_tyre`,
  `int_driver_isolation_lap_values`, `fct_driver_isolation_pair_lap`,
  `fct_driver_isolation_lap`, `fct_driver_isolation_stint`, `fct_driver_isolation_race`. All
  are tables tagged `driver_isolation`, and all nine are sqlfluff-clean. The intermediates
  are in family `skill`.
- **Fitter:** `fit_constructor_car_fe.py --panel isolation`, plus `--db` / `--out` (both
  default to the old paths) so it can be pointed at a scratch warehouse. `load_panel`,
  `fit_car_fe` and `run_fit`'s output are unchanged (T49).
- **Other:** `src_fits.yml` source `constructor_car_fe_isolation`; seed
  `driver_isolation_method_scores.csv` (three `unvalidated` rows, NULL scores, typed in
  `dbt_project.yml`); two macros, `driver_isolation_reliability` (λ, shrunk, confidence,
  trust label) and `driver_isolation_identity_terms` (the identity split over any group of
  pair rows); the nine `isolation_*` vars with measured comments; Makefile
  `car-fe-isolation-fit` (builds `+int_driver_isolation_lap_panel`, then fits), wired into
  `dbt-dev-full` after `car-fe-fit`; `schema.yml` entries for every column of the nine models
  and the seed (sign and units in each description; PK `unique` + `not_null`;
  `accepted_values` on `stint_phase`, `tyre_phase`, every `*_trust_label`,
  `tactical_peer_source`, `kappa_ref_source`, `car_term_source`; unique-combination tests
  on the pair and stint grains).
- **Tests:** T40-T47 in `transform/tests/`, with T45 split into two files (see deviation
  11); T48 in `ml/tests/test_manifest_contract.py`; T49 in
  `transform/tasks/coefficients/tests/test_fit_constructor_car_fe.py`. All are registered
  in `transform/tests/README.md`.
- **Counts:** 86 models and 912 tests in README.md, the Makefile comments, and the
  regenerated `docs/snippets/transform-inventory*.mdx` and `overview-numbers.mdx` (dbt
  lines only).

### Definition of done, measured

On a scratch copy of `data/dev.duckdb` (named `dev.duckdb`, because two tests hard-code
the catalog), with `fits_base` pointed at a scratch fits directory:

1. `dbt build -s +int_driver_isolation_lap_panel int_lap_proximity+ int_lap_thermal_proxy+`
   brought the copy current, including the W20/W23 subtrees the live dev lacks: PASS=299,
   WARN=1, ERROR=0.
2. `fit_constructor_car_fe --panel isolation --db <copy> --out <scratch fits>`.
3. `dbt build -s +fct_driver_isolation_race`: **PASS=431, WARN=1, ERROR=0 of 432.** The
   warning is `assert_sector_aggregates_to_lap` (47,640 rows), WI-07's warn-severity test on
   the sector model. It is not this WI's.
   `assert_stint_geometry_2018_compound_code_null` (F11b, 24,029 2025 slick rows, WI-07's)
   was excluded so that it would not skip everything downstream. It fails on its own exactly
   as on live dev.
4. T40-T47 (nine files) PASS in that build. Re-fitting after a full rebuild reproduces the
   car term the marts were built on exactly (max difference 0.0).
5. `pytest transform/tasks/coefficients/tests`: **130 passed**. T49 is 10 new tests in
   `test_fit_constructor_car_fe.py`, next to its 3 old ones. `ML_DUCKDB_PATH=<copy> pytest
   ml/tests`: **233 passed**, T48's two included, and the run changed nothing under `ml/` or
   `app/public/`.
6. The T29 NULL-bound lint passes (it caught four clamps; deviation 9). sqlfluff is clean on
   all nine models. `transform_docs_facts.py` passes. `docs_facts.py` passes on both dbt
   facts; its one remaining failure predates this WI (see *Not done*).

### Reproducibility against the probe (tier 3, `fct_driver_isolation_pair_lap`)

| Pair | Probe | As built | Within ±0.05 s/lap and ±10% |
| :-- | --: | --: | :-: |
| `2021_8` VER vs HAM | +0.24 / 57 | +0.241 / 57 | yes |
| `2021_19` HAM vs VER | +0.05 / 41 | +0.036 / 39 | yes (−4.9% on laps) |
| `2023_2` VER vs PER | −0.40 / 40 | −0.405 / 39 | yes |
| `2023_7` VER vs PER (optional) | +0.57 / 50 | +0.565 / 50 | yes |

The identity split of the same pairs (pair-lap means; pace gap = pure + tactical where both
exist):

| Pair | relative | pace gap | car adv. | traffic adv. | split rows | pure gap* | tactical gap* |
| :-- | --: | --: | --: | --: | --: | --: | --: |
| `2021_8` VER vs HAM | +0.241 | +0.817 | −0.586 | +0.009 | 57 / 57 | +1.021 | −0.204 |
| `2021_19` HAM vs VER | +0.036 | −0.768 | +0.926 | −0.122 | 36 / 39 | −1.132 | +0.373 |
| `2023_2` VER vs PER | −0.405 | −0.337 | 0.000 | −0.068 | 26 / 39 | −0.077 | +0.009 |
| `2023_7` VER vs PER | +0.565 | +0.491 | 0.000 | +0.074 | 33 / 50 | +0.525 | +0.108 |

\* These are means over the split rows only, so they sum to the pace gap only where every row
is split. The marts' `identity_*` contributions are the ones that always close. The worked
examples, with their expectations, are WI-16b's to write, but two readings are visible
already. `2021_8`'s +0.24 is a big driver term offset by a big car term, which is the W33
question. `2023_2`'s deficit sits mostly in the pace gap (−0.34), not in traffic (−0.07).
That is the doc's "dirty-air term under-prices traffic" branch, on the pre-`WI-01` θ_air, so
it has to be re-read after `WI-01`.

### Coverage, against the probe

| | Probe (this doc) | As built |
| :-- | --: | --: |
| Pure on Ω laps | about 95% | **96.6%** (72.6% non-extrapolated; 64.3% have a 5-lap window) |
| Tactical, stints with m_s | ≥ 80% (81.7% with ≥ 6 line laps) | **83.6%** of 7,315 stints (93.0% of Ω laps carry a tactical value; 81.7% a 5-lap window) |
| Relative, Ω laps with ≥ 1 peer | 88.3% | **90.4%** (≥ 2: 78.9% vs 77.2%; ≥ 5: 48.0% vs 47.4%; 88.7% a 5-lap window) |

No shortfall. Every figure is within 2.1 points of the probe or above it.

### Other measured numbers

- **Ω on the rebuilt copy.** The first four predicates keep 136,137 of 161,040 laps. The
  compound predicate takes that to 130,410, a known tyre to 130,393, dropping 2020_1 to
  129,810, and the field floor to **128,649 laps in 7,907 (race, lap) cells**. Before the
  floor, 96.2% of the 8,222 cells have ≥ 8 Ω laps (median 17).
- **Phases.** early 22.5%, mid 50.1%, cliff 27.4% (doc: 22.7 / 50.4 / 26.9). The recovery
  overlay covers **5.0%** of Ω (doc: 3.1% of valid laps, before WI-15a).
- **Stints.** 7,315 with an Ω lap. Tactical peer source: race 7,107, season_pool 206, none 2.
  κ_ref source: race 5,614, season_pool 1,699, none 2. `car_deg_imputed` covers 424 of 760
  2018 stints (legacy compound names) and none in any other season.
- **Noise per season.** σ_w 0.38-0.52 s, ρ₁ −0.005 to 0.23, f 0.62-1.00 (the prototype had
  0.40, 0.18 and 0.70).
- **Car term.** 1,618 constructor-races: 1,613 `global_driver` and 5 `not_estimated`
  (pyfixest singletons), which leaves 44 pair rows without car terms. `race_components_n` is
  1 everywhere.
- **Sizes.** Pair mart 686,314 rows (probe about 0.6 M); lap mart 128,649; stint mart 27,168
  (7,315 `all` rows); race mart 3,101, **all 3,101 joining `fct_driver_skill_features` on
  `driver_race_id`**.
- **Identities.** Pair rows close to 1.5e-14, laps (pure + tactical = p) to 1.8e-15, and
  teammates' car advantage is exactly 0. T43 has 2,619 qualifying teammate pairs.
- **Mean λ by grain** (confidence is NULL and every label `unvalidated` until WI-16b):

  | | pure | tactical | relative |
  | :-- | :-- | :-- | :-- |
  | 5-lap window | 0.71-0.88 | 0 (2018, 2019, 2025); 0.55-0.72 | 0.74-0.80 |
  | stint (`all`) | 0.79-0.91 | 0 (2018, 2019); 0.16-0.63 | 0.87-0.91 |
  | driver-race | 0.76-0.93 | 0 (2018, 2019, 2025); 0.29-0.67 | 0.92-0.95 |

### Deviations from this doc

1. **Ω count in the doc.** "The first five predicates keep 135,992" is what the first
   *four* keep. The compound predicate takes it to 130,281, because NULL compounds (4,088
   laps) fail `NOT IN` too. That was live dev before the rebuild; after it, the first six
   keep 130,393 and the field floor leaves 128,649.
2. **`early` is `valid_lap_in_stint <= 5`, not `BETWEEN 2 AND 5`.** The 2 was there to skip
   the out-lap, and Ω already drops out-laps through `is_out_lap`. When an out-lap is not a
   valid lap, the stint's first flying lap has `valid_lap_in_stint = 1`. 4,085 Ω laps (3.1%)
   are like that, and they would have had no phase at all, which breaks T45's "exactly one
   phase".
3. **The car term's fallback rule, and its outcome.** *(Superseded: since `a25be07` the fit
   is per era with no global fallback; see "As built: W33 re-validation" below.)* The doc's rule is "more than one
   component containing two or more constructors → global driver". The fit applies it,
   and also falls back whenever any race's constructor cells span more than one
   component. That is the actual identification condition: a car level can only be
   compared with the others in its race through a chain of drivers. The doc's rule alone
   misses a single-constructor island. Under `driver_era` both eras are disconnected:
   - **pre2022:** Haas 2018-20 (GRO/MAG/FIT) and Haas 2021 (MAZ/MSC) are islands, so 75
     of 76 races are unidentified. The doc's rule does **not** fire here, since only one
     component holds two or more constructors.
   - **post2022:** Alfa Romeo / Kick Sauber 2022-24 (BOT/ZHO) is an island, so 64 of 87
     races are unidentified. The doc's rule fires.

   Both eras therefore fall back, and every row is `car_term_source = 'global_driver'`.
   Under the global key every race is identified (1 component per era). The diagnostics
   are logged, and written to the parquet's `connectivity_note`.
4. **pyfixest's reference level.** `fixef()` omits the first `constructor_race` level: it
   solves on the full-rank dummy matrix, so that cell's FE is 0 by construction. The
   isolation path restores it at 0.0. HEAD's default path reads the absence as "not
   identified" and drops the cell. That is a side finding (the watch entry below), not
   fixed here, because T49 requires the default path to stay byte-identical.
5. **Pure SE carries the slope's own error.** The doc's `sigma_w / SQRT(n f)` omits that
   pure = p − m_s(age − age_ref) inherits m_s's estimation error. The added term is
   (SE(m_s) · mean(age − age_ref))². It dominates at stint grain: with 16 line laps and
   SE(m_s) ≈ 0.03, it is about 0.2 s against 0.12 s for the doc's term. Without it,
   pure's λ is overstated. Tactical's SE likewise adds the κ noise of cliff laps,
   σ²·n_cliff/(n²f). That term measured negligible (tactical SE² 0.824 against 0.818 in
   2018).
6. **τ² at window grain** is taken over the windows that clear the window floor. The doc's
   "rows with n ≥ 6" cannot apply to a window of at most 5 laps.
7. **τ² at stint grain** is estimated from the `all` rows (one per stint, so no stint counts
   twice) and applied to every phase row of the stint.
8. **λ = 1 when SE = 0**, rather than 0/0. This happens on a tactical window whose laps sit
   symmetrically around `age_ref`, where m_s·mean(age − age_ref) is exactly 0 whatever m_s
   is. T47 found 49 such rows.
9. **NULL-safe clamps.** τ² = `GREATEST(raw, 0)` became `CASE WHEN raw IS NULL THEN NULL
   ELSE GREATEST(raw, 0) END`: DuckDB's GREATEST skips NULL, so a season with too few rows
   would have published τ² = 0. WI-02a's T29 lint caught four such sites. The effective-n
   factor f is likewise NULL, not independence, when ρ₁ cannot be measured.
10. **Column names carry units where the doc used symbols.** β_s is
   `line_slope_s_per_lap2`, p̄ is `line_mean_pace_gain_s`, age_bar is `line_mean_age_laps`,
   age_ref is `line_ref_age_laps`, Sxx is `line_age_sxx`, β_peer is
   `peer_line_slope_s_per_lap2`, κ is `kappa_gain_s`, κ_ref is `kappa_ref_gain_s`, and m_s
   is `tactical_slope_s_per_lap2` (the doc's own name). Every published rating column
   keeps the doc's name.
11. **T45 is two files.** The partition is `assert_isolation_phase_partition` (error), and
    the [1%, 10%] recovery band is `assert_isolation_recovery_share` (warn). A test file
    has one severity.
12. **The identity at aggregate grain is a sum of contributions.** In the lap, stint and
    race marts the split is `identity_*`: each term's sum over the group's pair rows
    divided by the row count. Pair rows without both tacticals go into
    `identity_pace_gap_unsplit_gain_s`, so the five contributions sum exactly to
    `identity_relative_pace_gain_s` (T42 checks all three marts).
    `identity_n_split_pair_laps` says how much of it is split.
13. **The κ_ref floor (10 peer cliff laps) is a Jinja constant** in the stint model, not a
    var. The doc lists the vars and this is not among them.
14. **T48 runs.** `test_manifest_contract.py`'s module-level skip (no ML manifest) moved
    into the `manifest` and `card` fixtures, so every existing test is gated exactly as
    before and T48 is not. T48 and its mutation twin (an injected
    `fct_stint_features → fct_driver_isolation_race` edge must be caught) were added to
    `ml-ci.yml`'s guard step, which already has a fresh dbt manifest. Without that, nothing
    in CI would run it.
15. **The docs page and the reference regeneration are left to WI-16b**, whose definition
    of done owns them. Running `build_reference.py` now rewrites 54 files, about 45 of them
    unrelated drift (W8). The regenerated `docs/reference` was reverted.
16. **The fit is deterministic and converged, which the doc did not ask for.** The
    isolation panel is read `ORDER BY lap_id` and `fixef()` runs at atol = btol = 1e-12. At
    pyfixest's defaults, two builds of an identical panel gave car terms up to 4e-5 s apart,
    because the physical row order differs, and up to 6.8e-3 s off the exact solution
    (checked against alternating projections to 1e-13). Now a rebuild reproduces the fit to
    0.0 and the fit matches the exact solution to 7.6e-9. Two T49 tests pin both properties.

### Findings for WI-16b (measured here, not acted on)

1. **The car/driver split rests on a global driver effect (W33).** Neither era is connected
   under `driver_era` (deviation 3), so every car term comes from the global-driver fit.
   That fit assumes a driver's skill is constant from 2018 to 2025, and its driver effects
   spread 1.6 s: VER −0.76, PER −0.38, HAM −0.02, BOT +0.44, LAW +0.83. The within-team
   gaps behind it are real in the data (ALB−VER 0.79 s/lap, TSU−VER 1.13, PER−VER 0.32,
   BOT−HAM mean 0.48 but median 0.28), so the fit is correct as specified. What it cannot
   tell apart is a car that only one driver can extract from that driver's own skill.
   V1c, V2a and V3a are the tests for it. BOT−HAM's mean against median also shows the
   least-squares FE feels the tails.
2. **Tactical τ² is 0 in 2018, 2019 and 2025 (W32).** The doc's unweighted estimator is
   dominated by stints whose tactical SE is huge: a short line (6-8 laps) extrapolated over
   a long stint, up to SE 4.7 s/lap in 2018. The mean SE² is 0.82 against a median of 0.24.
   Pure and relative are unaffected. A precision-weighted (DerSimonian-Laird) estimator is
   the natural alternative. That is a method decision, so it is left to WI-16b.
3. **Tactical is noisy at late tyre ages, and pure inherits it.** m_s has SD 0.07-0.11
   s/lap² against a median SE of 0.03-0.055, so there is signal. But tactical = m_s ×
   (age − age_ref) reaches ±2.6 s/lap at the 1st and 99th percentiles, because age − age_ref
   runs to 33 laps. That is the "level/slope split has a reference point" item under *How
   this could be wrong*, now measured. It is also why pure's SE carries the slope term
   (deviation 5). Pure's window λ (0.71-0.88) comes out above the prototype's 0.43-0.56
   because pure's between-row variance is large (window SD about 0.9 s), and that variance
   contains the 1.6 s spread of driver effects. V5b is the test.
4. **The FE solver tolerance matters (deviation 16).** At pyfixest's default `fixef()`
   tolerance the isolation car terms were up to 6.8e-3 s off the exact solution. HEAD's
   default Ghost-Standings fit is off by up to 9.0e-3 s within a race (median 2.6e-4 s),
   and it also drops its reference cell (W31).

### Not done, and why

- `docs_facts.py` still fails on one fact, **ML features** (README and `docs/ml/overview.mdx`
  say 33; the generated `ml-inventory.mdx` says 32). This predates WI-16a and is ML territory.
  The dbt facts now reconcile (86 models, 912 tests). Also predating it:
  `ml_docs_facts.py`'s TEST_GROUPS totals 189 against 233 collected (T48 adds 2 of the 44),
  and `overview_docs_facts.py` counts 31 app features against the snippet's 30. The
  regenerated overview snippet kept 30, to stay in scope.
- CI cannot build `int_constructor_car_fe_isolation`, for the same reason it cannot build
  `int_constructor_car_fe`: both read a fit parquet from the gitignored `data/fits/`.
- The known F11b failure (`assert_stint_geometry_2018_compound_code_null`, 24,029 2025 slick
  rows, WI-07's) was excluded from the build so that it would not skip everything
  downstream. It was then run on its own and fails as before.

---

## As built: W33 re-validation (2026-09-30; working tree, dev not rebuilt)

Working-tree edits only: no `dbt build`, no training, no commit. `data/dev.duckdb` and
`data/fits/` were not written. Numbers come from `_evidence/wi-16-2026-09-30/`. Its
`PROVENANCE.txt` describes the three substrates. `w33-fit-fix` is a scratch copy of dev
with the car term refitted and the eight downstream models replayed from the compiled SQL.
Replaying the *unchanged* parquet that way reproduced live dev to 6e-15.

### The car term is per era now (supersedes WI-16a deviation 3)

Since `a25be07` (2026-09-29) the fitter fits `mean y_s ~ 1 | driver_id + constructor_race`
separately in each era, on driver-race means. That is this doc's `driver_era` key, with
**no global fallback**: a driver's skill is one value per era, not one value for
2018-2025. Every identified row is `car_term_source = 'driver_id'`. The islands deviation
3 found are therefore unrated rather than bridged: Haas 2018-2021, Alfa Romeo
2022-2023 and Kick Sauber 2024 (`unidentified`). The race-level aggregation also turns a
constructor-race where only one driver has laps in the fit into a singleton
(`not_estimated`). Three T49 tests had been failing since `a25be07` because they pinned
the fallback and the old labels. They now pin the per-era behaviour, and a new test pins
the fit sample (below).

### The V2a plumbing bug and its fix

The car term was fitted on **all** Ω laps, but every pure aggregate uses the **pre-cliff**
laps only (`pure_is_extrapolated = tyre_phase = 'cliff'` is excluded). In `y_s`, cliff
laps read 0.24-0.89 s faster than pre-cliff laps in every season, because the seed's
cliff cost over-corrects. A constructor-race with many cliff laps therefore got a faster
car term, and the pre-cliff laps rated against it read slower. The two-way FE's
residuals are orthogonal to the car term only on the sample it was fitted on. So the
fitter now reads `tyre_phase <> 'cliff'` (`ISOLATION_FIT_METHOD` `..._hdfe_v2`).

**The root cause named in the W33 brief does not reproduce.** `int_lap_fuel_state` holds
all 161,040 laps. Lap 1 is excluded by `stg_laps.is_valid_lap` (`lap_number > 1`), which
is long-standing and can never be an Ω lap.

### Validation, before and after (2018-2024 decides; thresholds as pre-registered)

| Test | live dev (v1 fit) | fixed fit (scratch replay) |
| :-- | :-- | :-- |
| V1a split-half (median Spearman) | PASS 0.808 | PASS 0.897 |
| V1b adjacent seasons | FAIL: median 0.818, but 2021-22 0.559 < 0.627 | FAIL: median 0.916, but 2021-22 0.603 < 0.652 |
| **V1c movers/stayers** | PASS 1.074 [0.67, 1.76] | **FAIL 1.507 [1.04, 2.67]**; season-centred 0.84 [0.61, 2.16] |
| **V2a within-driver car leakage** | MARGINAL 0.233 (2025: 0.211) | **PASS 0.054 (2025: 0.024)** |
| V2b compound, within driver-race | FAIL 0.910 s | FAIL 0.910 s |
| V2c-ii style strata | PASS (top 0.823, bottom 0.885) | PASS (0.833, 0.891) |
| V2d fuel saving (report) | −0.098 s | −0.098 s |
| V2e convergent (field / Massey) | PASS 0.623 / 0.699 | PASS 0.608 / 0.711 |
| **V3a car pricing at matched strategy** | PASS 0.039 | **PASS 0.066** |
| V3b traffic pricing | MARGINAL: corr 0.038 PASS; dirty−clean gap −0.071 s FAIL | MARGINAL: 0.027; −0.071 s [−0.098, −0.045] |
| V3c teammates vs loro | PASS 0.728 | PASS 0.728 |
| V3d rolling-origin backtest | PASS (MAE gain 0.097 / 0.242) | PASS (0.124 [0.109, 0.138] / 0.281 [0.248, 0.311]) |
| Tier-3 (i) coverage | PASS 0.904 | PASS 0.904 |
| Tier-3 (ii) ΔC age adjustment | FAIL (variance +3.4%) | FAIL (+3.4%) |
| V4a fuel, absolute | FAIL 0.020 s/kg | FAIL 0.020 s/kg (0.025 seed − 0.005 residual) |
| V4b fuel immunity | FAIL 0.006 s/kg | FAIL 0.006 s/kg |
| V4c compound ordering | FAIL (2018 −0.064 s) | FAIL (2018 only, −0.019 s) |
| V5a / V5b / V5d | PASS 0.195 / 0.309 / 0.389 + 0.314 | PASS 0.195 / 0.323 / 0.389 + 0.314 |
| V1a-tactical, V2c-i, V5c, V6a-c | not applicable (tactical cancelled) | not applicable |
| **Method score, pure** | 0 (F: V1b); 0.686 before the critical rule | 0 (F: V1b, V1c); 0.622 before |
| **Method score, relative** | 0 (F: tier-3 ii); 0.571 before | 0 (F: tier-3 ii); 0.571 before |

The critical rule is read literally: any FAIL among a critical row's sub-checks zeroes
the rating. Read at test level instead (a critical row fails only when its own mean is
below 0.5), pure is C 0.686 on live dev and F on the fixed fit (V1 row 0.33), and relative
is C 0.571. **Which reading applies is the user's call.** The doc's "any critical test
FAILs" supports the literal one.

### What the W33 tests say about the car/driver split

- **V2a** was the plumbing bug and is fixed. On the aligned sample V2a is near 0 almost
  by construction (FE residuals are orthogonal to the cell effects). So it now guards the
  plumbing; it cannot see a driver × car interaction, because that lands in the driver
  effect.
- **V3a** passes on both substrates, so no car leakage shows at matched strategy.
- **V1c** fails by 0.007 on the fixed fit, and it is underpowered: 20 mover season-pairs
  from 14 drivers, CI 1.04-2.67. It also carries the season level offset (next section).
  With each season's mean removed first it is 0.84 [0.61, 2.16].

This is not evidence of car leakage, and it is not evidence against it either.

### Driver-races without a pure value (W33 issue 3)

On the fixed fit, 390 of 3,102 driver-races (12.6%) have no pure value; on live dev it is
388. The reason is carried in `car_term_source` on every row of `fct_driver_isolation_race`:

- **263 `unidentified`:** the team is an island in its era's teammate network. Haas
  2018-2021: 139 driver-races (GRO, MAG, FIT, MAZ, MSC). Alfa Romeo 2022-2023: 78, and
  Kick Sauber 2024: 46 (BOT, ZHO). No driver links those cars to the rest of the field
  inside the era.
- **127 `not_estimated`:** only one of the team's drivers has pre-cliff Ω laps in that
  race. With one driver, the car and the driver cannot be separated. WI-16a's lap-level
  fit gave most of these a term, but that term was the driver's own race mean minus his
  era effect, so his race pure was his era average by construction.
- (live dev only) 2 driver-races with every clean lap past the cliff.

Options, for the user: keep them NULL and say why (done in the docs page), or bridge the
islands through the drivers who cross the era boundary (MAG and MSC for Haas, BOT for
Sauber). Bridging reintroduces the cross-era constant-skill assumption for exactly those
drivers.

### The 2018 level (W33 issue 4): not fixed

Mean race pure by season on the fixed fit runs from −0.03 (2021) to −0.45 (2018). `y_s` is
centred on each lap's field median over **all** Ω laps. Cliff laps read fast, and 42% of
2018's Ω laps are cliff laps, so 2018's pre-cliff laps sit +0.54 s above the median
(0.05-0.20 s in other seasons). It is a level every driver in a season shares. It does
not affect within-season rankings, V1b or pair gaps, but it does tilt V1c.

The fit fix does not change it: 2018 moves from −0.40 to −0.45. Experiment
(`experiment-precliff-median`): centring on the pre-cliff laps' median removes the offset
(season means +0.01 to +0.15). With it, V1c passes (1.068), V4c passes (2018 +0.086) and
V4b halves. **But V3a fails (0.173):** where few cars are pre-cliff, the median comes
from a few teams, and that team-correlated noise enters the car fit.

Candidate fixes, for a decision:
1. Re-centre pure on each race's pre-cliff field in the marts. This is level only, and
   leaves the car fit alone; the season-centred V1c above shows its effect.
2. Fix the seed's cliff cost (WI-02b), which removes the cause.
3. Keep the level and document that pure is not comparable across seasons.

### Upstream findings, not W33's (routed per the doc)

- **V2b, V4b and V4c-2018: the seed's compound levels.** Within the same driver-race, pure
  reads faster on the softer compound in every season: MEDIUM−HARD +0.20 to +0.42 s,
  SOFT−HARD up to +0.75 s, and 2018 SUPERSOFT−MEDIUM +0.91 s. Soft tyres usually run the
  heavy-fuel first stint, so this bias projects onto fuel. V4b's 0.0064 s/kg falls to
  0.0034 with a compound effect, and to 0.0004 with the pre-cliff median as well. So V4b
  is not a fuel bug. These go to F42a / WI-02b.
- **Tier-3 age adjustment (critical for relative):** within a stint pair on pre-cliff laps
  ΔC is constant (linear wear, fixed age gap), so it changes nothing. On cliff laps it
  adds variance (−3.6%). The seed's cliff pricing makes the adjusted delta noisier than
  the raw one. Publishing `relative_pace_raw_gain_s` instead is the obvious alternative
  (user decision).
- **V3b:** with the driver in dirty air, pure reads 0.071 s slower than the same pair's
  clean-clean gap [−0.098, −0.045], so θ_air under-prices traffic. This goes to WI-01.
- **V4a:** the implied fuel effect is 0.020 s/kg, below the physical band, with a residual
  coefficient of −0.005 in every season. This is about the absolute decomposition the
  agent would quote, not the ratings.

### Validator implementation choices (declared in each result's `design` field)

V1a and V1b now follow this doc. V1a uses race-level halves with ≥ 5 races each. V1b
uses an EB-shrunk driver-season pure (≥ 8 races) and grades the 6 pairs inside
2018-2024, with 2024-25 reported. V1c: movers are drivers whose main constructor
changed, ≥ 8 races in both seasons, bootstrap clustered by driver, and PASS iff the ratio
is ≤ 1.5. V2b grades cells with ≥ 20 driver-races. V2c-ii centres each season before
pooling. V2e takes the median of per-season Spearman; its Massey half averages only
synthetic-teammate rows with a proxy. `driver_network_rating.py` itself returns NaN
ratings on current dev, because a group of all-NULL proxies gives one NaN delta. V3a,
V3b and V3c aggregate pre-cliff pair-laps only ("pure aggregates use early, mid and
recovery laps only"). V3d's prior pure is shrunk with τ² from rounds < k. Tier-3 (ii)
uses the pooled within-(race, pair) variance. V4 is weighted V4a 0.5 / V4b 1 / V4c 0.5
for pure and V4c alone for relative. The worked examples still use the 2026-09-29
expected values, not this doc's probe (see the build log, 2026-09-29T11:00).

### Not done

- Dev is not rebuilt, so dev still carries the v1 car term. Next: `make car-fe-isolation-fit`,
  then `dbt build -s int_constructor_car_fe_isolation+`, then re-run the validator. After
  that, `--write-seed` once the critical-rule reading is decided.
- Two descriptions still describe the global fallback: `schema.yml`'s
  `int_constructor_car_fe_isolation` description and that model's SQL header. They were
  left alone because this pass edits only Python, JSON and Markdown.

---

## As built: W33 on dev (2026-09-30, later session; dev rebuilt, nothing committed)

This session wrote `data/dev.duckdb` and `data/fits/constructor_car_fe_isolation.parquet`
(both backed up first). No model training, no seed re-estimate, no commit. Evidence:
`_evidence/wi-16-2026-09-30/dev-rebuilt-v2/` (the v2 fit, no offset) and `dev-final/`
(plus the 2018 offset); `PROVENANCE.txt` describes both.

### What was rebuilt

1. `make car-fe-isolation-fit`: `dbt run +int_driver_isolation_lap_panel` PASS=19, then
   the v2 fit (pre-cliff laps only): 93,983 laps, 1,619 constructor-races, `driver_id`
   1,356 / `unidentified` 139 / `not_estimated` 124.
2. `dbt build -s int_constructor_car_fe_isolation+`: PASS=139, WARN=0, ERROR=0.
3. The validator on that dev (`dev-rebuilt-v2`) reproduces the `w33-fit-fix` scratch
   replay line for line. The replay was faithful, and the "Not done" item of the previous
   section (rebuild dev) is done.
4. After the offset below: `dbt build -s int_constructor_car_fe_isolation+` again,
   PASS=141 (the two new `not_null` tests included), WARN=0, ERROR=0.

### The 2018 level (W33 issue 4): Option A, a declared season offset

`pure_skill_gain_s = pace_isolated_gain_s + pure_season_offset_gain_s`, the offset being
the var `isolation_pure_season_offset_gain_s: {2018: 0.37}` rendered by the new macro
`driver_isolation_pure_season_offset` in `int_driver_isolation_lap_values` and exposed
on `fct_driver_isolation_race`. **+0.37, not +0.45:** on the rebuilt dev 2018's mean race
pure is −0.450 and the 2019-2024 seasons average −0.077 (−0.03 to −0.12), so +0.37 puts
2018 at their level. +0.45 (the gap to zero) would put it 0.08 s above them. The value
was fixed from `dev-rebuilt-v2` before `dev-final` was validated, not tuned on V1c.
2025 (−0.246) is not offset; the docs page says so.

The offset is constant within a season, so it cancels in pair gaps (checked: pair
`pure_gap_gain_s = pace_gap_gain_s` to 9e-16), in the tier-3 identity (written on
`pace_gap`, which carries no offset), and in every within-season ranking. Against
`dev-rebuilt-v2` it moved only V1c, the report-only sign-flip share (0.172 → 0.176) and
the 2018 season level (−0.450 → −0.080). It is a stopgap for the seed's cliff cost; the
var's comment says to remove it, not re-tune it, when WI-02b's cliff-cost refit lands.

### Validation on dev (`dev-final`; 2018-2024 decides)

| Test | Result |
| :-- | :-- |
| V1a split-half | PASS 0.897 |
| V1b adjacent seasons | **FAIL**: median 0.916, 2021-22 0.603 < 0.652 required |
| **V1c movers/stayers** | **PASS 0.796 [0.463, 1.612]** (1.507 FAIL without the offset; season-centred 0.838) |
| **V2a within-driver car leakage** | **PASS 0.054** (2025: 0.024) |
| V2b compound, within driver-race | FAIL 0.910 s (2018 SUPERSOFT-MEDIUM) |
| V2c-ii / V2d / V2e | PASS (0.833, 0.891) / report −0.098 s / PASS (0.608, 0.711) |
| **V3a car pricing at matched strategy** | **PASS 0.066** |
| V3b traffic pricing | MARGINAL: corr 0.027 PASS; dirty−clean −0.071 s [−0.098, −0.045] FAIL |
| V3c / V3d | PASS 0.728 / PASS (MAE gain 0.124 [0.109, 0.138], 0.281 [0.248, 0.311]) |
| Tier-3 coverage / age adjustment | PASS 0.904 / **FAIL** (+3.4% variance) |
| V4a / V4b / V4c | FAIL 0.020 s/kg / FAIL 0.006 s/kg / FAIL (2018 only, −0.019 s) |
| V5a / V5b / V5d | PASS 0.195 / 0.323 / 0.389 + 0.314 |
| Method score, pure | strict 0 (F: V1b); test-level 0.724 (C) |
| Method score, relative | strict 0 (F: tier-3 age adjustment); test-level 0.571 (C) |

### What the W33 tests say now

V1c, V2a and V3a all PASS on dev. V2a is close to 0 by construction on the aligned sample,
so it now guards the plumbing only. V1c passes because of the offset, and its CI still
reaches 1.61, past the 1.5 limit, with 20 mover season-pairs from 14 drivers. Read it as
no leakage detected, not as none.

**V1b is the W33 finding this session adds.** Its rule-change check is the doc's own
"the rule change broke the car term, not the drivers" test, and the evidence says it is
right. Race pure is roughly the driver's era effect plus half the season's teammate
deviation, so inside an era a driver's pure barely moves (adjacent-season Pearson
0.82-0.98). `driver_skill_field_s`, which does not hold skill constant per era, has
2021-22 at 0.912, its highest pair, so the drivers did not reshuffle at the boundary.
Pure's 0.603 there means the two eras' car/driver splits place drivers differently:
TSU +0.53, PER +0.37, GAS +0.26 and HAM +0.19 s move up in pure where the era-free
measure has them flat or slower (HAM −0.41). This is the driver × car question W33 was
opened for, seen across eras rather than across teams. Option A cannot touch it (Pearson
ignores a season constant, and V1b shrinks toward each season's mean). Candidate fixes,
post-v15: a joint fit with era-specific driver effects linked by drivers who span the
boundary, or dropping the cross-era claim and grading V1b on within-era pairs only (a
spec change, not a threshold tweak).

### Upstream issues (documented, not fixed)

- **Tier-3 age adjustment.** The brief's workaround, scaling ΔC by 0.966, was measured
  first (`dev-final/w33-measurements.txt`, the validator's pooled within-pair design):
  k = 1 adds 3.40%, k = 0.966 adds 3.14% (still FAIL), the break-even is k = 0.218 and the
  best is k = 0.109 at −0.05%. Picking k from this test would also grade its own
  homework. Not applied; relative rankings are held for post-v15, and
  `relative_pace_raw_gain_s` is the number to quote meanwhile. Even on pre-cliff pairs
  ΔC adds 1.44%.
- **V2b / V4b / V4c-2018:** compound seed levels (WI-02b). V2b is not one-directional:
  MEDIUM-HARD +0.20..+0.42 every season, but SOFT-MEDIUM turns negative from 2022
  (2024 −0.45 s).
- **V3b:** θ_air under-prices traffic by 0.071 s (WI-01 territory). Documented.
- **V4a:** implied fuel effect 0.020 s/kg against the 0.025-0.040 band (the absolute
  decomposition, not the ratings). Documented. The brief's "V4c (base/fuel)" is V4a; V4c
  is compound ordering (2018 −0.019 s), also documented.

### Island teams (W33 issue 3)

Unchanged in count and documented in the docs page as a method limitation: 390 of
3,102 driver-races (12.6%) have no pure value, 263 `unidentified` (island teams: Haas
2018-2021 139, Alfa Romeo 2022-2023 78, Kick Sauber 2024 46) and 127 `not_estimated`
(one of the team's drivers has pre-cliff laps in that race). The brief's "390 islands"
is those two groups together. Relative pace needs no car term: 262 of the 263 island
driver-races have one.

### Other edits

- The two stale global-fallback descriptions (the `int_constructor_car_fe_isolation`
  schema entry and SQL header) now describe the per-era v2 fit. The
  `int_driver_isolation_lap_values` schema entries no longer describe the cancelled
  tactical tier. T42's header no longer claims `pure = p`.
- `docs/decomposition/driver-isolation.mdx`: current results, known issues, the season
  offset, the island explanation, and the worked examples re-quoted from `dev-final`
  (São Paulo: car +0.67, pace gap −0.34, so the page's "results align" claim was removed;
  `docs/findings/sao-paulo-2021.mdx` itself is untouched).

### Not done

- `--write-seed`: the strict or test-level critical-rule reading is still the user's
  call. Under strict, both ratings are F and `suppress`; under test-level, both are C.
- `scripts/transform_docs_facts.py` crashes on `fct_power_law_training` having no
  `meta.family` (WI-17's model, pre-existing), so the generated test count cannot be
  refreshed for the two new `not_null` tests. `docs_facts.py`'s one failure (ML features
  33 vs 32) is pre-existing (W35).

---

## As built: eras and the age curve (2026-09-30, third session; dev rebuilt, nothing committed)

The brief: (1) split the eras more finely to fix V1b, recommending "by technical change"
(2018 | 2019-2020 | 2021 | 2022-2024 | 2025) on the hypothesis that the 2021 floor change,
not the 2022 aero change, broke continuity; (2) replace relative pace's age adjustment with
a spline (target: under 2% added variance). This session wrote `data/dev.duckdb` and the new
`data/fits/isolation_age_curve.parquet` (dev and the car-term parquet backed up first, to the
session scratchpad). No other model trained, nothing else rebuilt, no commit. Evidence:
`_evidence/wi-16-2026-09-30/eras/`, `age-curve/` and `dev-age-curve/`; `PROVENANCE.txt`.

### Eras: left as they are (2018-2021 | 2022-2025)

The fit tells car from driver only through drivers who changed team inside an era. A single
season has almost none, so every team is an island, and the race's "identified" component is
one team whose car term re-centres to 0 (its pure is raw pace). Share of driver-races with a
car term, on the same pre-cliff fit (`eras/era_fits.py`):

| Eras | All | 2018 | 2021 | 2022-24 | 2025 |
| :-- | --: | --: | --: | --: | --: |
| current, 2018-21 / 2022-25 | 87.5% | 82% | 87% | 87% | 95% |
| option 1, one per season | 15.1% | 11% | 10.5% | 10-20% | 19% |
| option 2, 2018 / 19-20 / 21 / 22-24 / 25 | 36.3% | 11% | 10.5% | 67% | 19% |
| option 3, 18-19 / 20-21 / 22-24 / 25 | 47.5% | 26% | 49% | 67% | 19% |

(2022-2024 loses 20 points without 2025, whose driver moves link most of that era's teams.)
Replayed and validated (`eras/eras-summary.csv`): option 2 leaves no 2021-22 pair, V1b's other
pairs exist for 2 of 6 seasons, V1c FAILs (1.62, 3 movers), V3c FAILs (0.684); pure is F
under either reading. Option 3 passes V1b on 5-13 drivers a pair, with its own cross-era pair
2019-20 at 0.356. Option 1 has no V1b pair and no movers at all.

**The hypothesis test.** Moving the single boundary (two eras, boundary year B) gives the
cross-era pair's Pearson; every within-era pair is 0.85-0.99 in every split:

| B | Cross pair | Pearson | Drivers |
| :-- | :-- | --: | --: |
| 2020 | 2019-20 | 0.541 | 7 |
| 2021 (floor change) | 2020-21 | 0.129 | 8 |
| 2022 (current, aero change) | 2021-22 | 0.603 | 15 |
| 2023 (no rule change) | 2022-23 | 0.297 | 7 |
| 2024 (no rule change) | 2023-24 | 0.543 | 10 |

Every boundary drops, the rule-change boundary least. **V1b's failure is the per-era design,
not the regulations:** inside an era both seasons share one driver effect, so adjacent-season
correlation is high by construction; across a boundary it compares two independent, thinly
identified estimates. The 2021 floor-change hypothesis is not supported (0.129 at 2020-21).
Finer eras only add cross-era pairs and islands. With V1b's rule-change pair hard-coded to
2021-22, any split that makes 2021-22 within-era "passes" V1b by construction (every
two-era split above does), which is why none of these was adopted.

Options, for the user (neither done): (a) a spec change to V1b's rule-change check, grading
the 2021-22 pair against placebo boundaries (it would pass: 0.603 is above all four) or
grading within-era pairs only; this is decided after seeing results, so it must be declared
as such. (b) Post-v15: one fit with a global driver effect plus shrunk driver-season
deviations, so identification uses the whole 2018-2025 mover network and V1b tests every
pair alike.

Validator fixes found on the way: V1b now FAILs when its 2021-22 pair cannot be computed
(option 2 had read PASS on 2 of 6 pairs); the report line and the cluster bootstrap (no
movers) no longer crash on an empty case.

### Tier-3 age adjustment: the fitted tyre-age curve

All variants are cubic B-splines in `age_in_stint`, 3 interior knots at age quartiles,
per era|compound group (2018 its own tag: absolute compound names), cross-fitted by race
(5 folds), scored on the validator's pooled within-pair variance (2018-2024; CI
race-clustered, 2000 draws):

| Design | Variance vs raw | 95% CI | 2025 | Curves |
| :-- | --: | :-- | --: | :-- |
| Seed ΔC (until now) | +3.40% | +2.53, +4.38 | +2.65% | 2018 alone +10.5% |
| A: fitted on the pairs, pair FE | −0.32% | −0.66, +0.01 | −0.29% | a 3-lap-older pre-2022 SOFT/MEDIUM tyre up to 0.75 s *faster*; 61% of pre-2022 adjustments opposite in sign to E |
| C: field, stint FE + (race, lap) FE | +0.30% | +0.01, +0.58 | +0.57% | linear slope NOT identified (below); swings up to 2 s between folds |
| **E: field, (race, driver, compound) FE + (race, lap) FE — shipped** | **+0.66%** | **+0.31, +1.04** | +0.54% | rising in every group, 0.03-0.11 s/lap over ages 5-20; fold-to-fold ±0.1 s |

A's pass comes from the pair design: the age gap is 0 in the first stint and non-zero only
after the stops, so the pair FE hands pair × compound pace to "age". Fitting A on clean-air
pair-laps only changes nothing (−0.30%), so it is not traffic. C has the age-period-cohort
collinearity: inside a stint age = lap − stint start, so a stint FE plus a (race, lap) FE
absorb any linear age effect (on synthetic data with 0.06 s/lap wear C returns −0.0004).
E identifies the slope from drivers who fit a new set of the same compound (25% of fit
laps) and recovers the synthetic 0.06 s/lap (unit test). `tyre_life` equals `age_in_stint`
from 2019, so a better age measure is not available. Four knots instead of three: C +0.311%.

**No physically sensible curve reduces the within-pair variance.** Within ±3 laps of tyre
age a pair's lap-to-lap gap is driven by racing far more than by age; only a curve fitted on
the pairs themselves gets below zero, and it does so with non-physical shapes. E was shipped
because it is identified, stable and physical, not for its score. Against the brief's target
(< 2% added) it passes; against the pre-registered rule (must reduce) it fails.

### Age curve: removed per W63 (design 2 resolution)

The age-curve approach was tested to reduce variance on tier-3 relative pace but could not pass the
validation check on cross-car pairs (confounded by pit strategy). Under W63 resolution, the age-curve
infrastructure has been removed:

- `fit_isolation_age_curve.py`, `int_driver_isolation_age_curve`, and `data/fits/isolation_age_curve.parquet` are
  deleted.
- `fct_driver_isolation_pair_lap` holds `relative_pace_gain_s` only (raw, peer-matched within ±2 laps
  of tyre age, not age-adjusted).
- The identity is: relative = pure_gap + car_advantage + traffic_advantage (3 terms, not 4).
- T42 checks the three terms to 1e-6.

The tyre-age tolerance `isolation_peer_age_tolerance` is tightened from 3 to 2 laps. Coverage at ±2 laps
is 86.4% of Ω laps with ≥ 1 peer (vs 90.4% at ±3). The known tyre-age bias is documented in
*Limitations*.

---

## As built: W33 closure (2026-10-03)

**Isolation validation results documented and WI-16 ready for publication.**

Evidence: `_roadmap/_fixes/_evidence/wi-16-2026-10-03/` (validation-report.md, validation.json)

### Validation results (2018-2024 decides; thresholds pre-registered)

| Test | Result | Notes |
| :-- | :-- | :-- |
| **V2a within-driver car leakage** | **PASS 0.054** | Critical for pure. 2025 confirmation: 0.024 |
| **V3a car pricing at matched strategy** | **PASS 0.066** | Critical for relative |
| **V1c movers/stayers** | **PASS 0.796 [0.463, 1.612]** | 20 mover season-pairs / 14 drivers; CI reaches past 1.5. Effect: per-era car term requires 2018 season offset of +0.37 s to align inter-era levels. Offset declared in `isolation_pure_season_offset_gain_s` var; see Option A under *W33 on dev* above. |

All three critical tests pass on the 2026-10-03 dev rebuild carrying the per-era car term fit (commit a25be07) and the 2018 offset (Option A).

### Publication readiness

- **Pure pace:** method score C (0.724 test-level), grade C. V1b crosses the 2022 era boundary and reflects the per-era car/driver split design; within-era correlations are 0.85–0.99. Relative pace inherits pure's eras.
- **Relative pace:** method score C (0.571 test-level), grade C. Tier-3 age adjustment adds 3.4% within-pair variance (fails pre-registered PASS ≤ 2%); spec trade-off: `relative_pace_raw_gain_s` available as alternative until post-v15 fix.
- **Coverage and identity:** all specifications met. Pair-lap identities close to 1.5e-14. No leakage detected in V2a (car term orthogonal to pre-cliff pure after fix). V3a confirms car pricing at matched strategy.
- **Known limitations documented:** season-offset rationale, tier-3 age bias, island teams (263 unidentified + 127 not_estimated = 390 of 3,102 driver-races), 2018 telemetry gaps. docs page updated.

**Ready for v15 publication with stated method grades and confidence shrinkage. Post-v15 board watches W61 (per-era car/driver split) and WI-02b seed refit.**
