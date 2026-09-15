# 06 — Publication track

**Group:** 06 · **Depends on:** nothing · ***parallel*** — neither blocks nor is blocked by 01–05

Findings written for an external audience. The programme's other items ask "how good are our
models"; this one asks "what can this warehouse say that a team cannot say for itself".

## Positioning, which determines what is worth writing

A team has deep telemetry on its own two cars and only **public data on the other eighteen** —
the same data this warehouse holds. So competitor-facing findings are where a public-data
project is near the frontier, and own-model accuracy metrics are where it is hopelessly behind.

What travels: **a number, the identification strategy behind it, the error bar, and one
sentence on what would falsify it.** What does not: driver rankings without uncertainty, and
"my model achieved X".

Every item below must ship with its limitations stated in the post itself, not in a reply.

---

## 06a — The pit-timing tail

**Objective.** Publish the distribution, not the average.

**Verified 2026-09-07** from `int_pit_strategy_value` (7,129 stints): **median opportunity cost
0.0 s, mean 10.15 s.** Teams hit the tyre-optimal pit lap most of the time; all the lost time
sits in a tail. By constructor (n > 150), mean seconds lost per stint: Ferrari 7.32, Red Bull
9.00, Alpine 9.09, Aston Martin 9.93, Haas 10.05, Renault 10.11, McLaren 10.15, Racing Point
10.30, Alfa Romeo 10.37, Mercedes 10.62, AlphaTauri 10.79, Toro Rosso 12.36, Williams 12.53,
Alfa Romeo Racing 12.71.

**The finding is the nuance, not the ranking.** `int_pit_strategy_value` scores the pit lap
against the **tyre** optimum — its own header says "counterfactual cost calculation, not causal
inference". So a team that scores well here and is still criticised publicly is not making
tyre-modelling errors; it is making race-context errors — reacting to rivals, safety-car calls.
**That separates two failure modes that outside commentary conflates**, and it is the reason a
strategist would read it.

**Required caveats in the post.** No track-position or undercut dynamics; SC/VSC not modelled
as a decision input; the optimum is an argmin over a modelled cost surface, so it inherits that
model's assumptions.

**Definition of done.** Post drafted with the distribution as the headline, the tyre-vs-context
distinction stated, per-constructor n shown, and the caveats above in the body.

---

## 06b — Dirty air per season · the 2022 regulation question

**Objective.** Convert an assumption into a measurement.

**Verified 2026-09-07.** `int_dirty_air_tax_component` calibrates a **single global θ_air** and
applies `dirty_air_tax_s = CLAMP(θ_air × dirty_air_share_lag1, 0, 5.0)`. Output confirms it:
the tax at a given following intensity is identical in 2018 and 2024. **The model currently
assumes the cost of following never changed**, so as built it cannot answer the question at
all.

Also verified, and interesting on its own: mean following intensity rose from 0.197 (2018) to
0.237 (2024). Cars spend *more* of each lap in dirty air now, not less.

**Method.** Refit θ per season, keeping the existing lagged identification (prior-lap position
→ current-lap cost) that the model already uses to keep the causal arrow the right way round.
Then per era × corner-type using `dim_corners`, since the heterogeneity is the real finding —
the regulations were sold as a uniform improvement.

**Required caveat.** 2022 bundles the aero change with 18-inch tyres and porpoising. The
defensible claim is about the **bundle**; corner-geometry heterogeneity is what moves it toward
mechanism.

**Definition of done.** Per-season θ with confidence intervals; the corner-type breakdown; the
bundled-treatment caveat stated in the post; and the warehouse model either updated or a
written decision to keep the global θ in production and publish the per-season fit separately.

### 06b pre-registration — written before any coefficient was fitted

Per [`../foundations/gates.md`](../foundations/gates.md) step 6. Everything from **Estimand**
down was fixed on 2026-09-15 before any regression existed. Only the instrument check and two
covariate-only probes (corner-speed distribution, panel row counts) had been run at the time
it was written, and both are reported here in full so a reader can see exactly what was known.

#### Instrument check first (gate 1)

The leaf doc's Verified 2026-09-07 numbers must come back out of the warehouse before anything
is built on them. Ran (`scratchpad/d0_instrument_check_06b.py`), and they do — with one
addition that changes the item's framing.

Mean following intensity by season, from `int_dirty_air_tax_component`:

| | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mean `dirty_air_intensity_lag1` | 0.1969 | 0.2251 | 0.2590 | 0.2130 | 0.2396 | 0.2393 | 0.2374 |
| laps | 14,881 | 17,999 | 14,134 | 19,243 | 16,897 | 19,296 | 21,543 |

0.197 (2018) → 0.237 (2024) reproduces exactly. The implied θ is **0.5 in every season**, as
the doc says.

**The addition, and it is not a detail.** θ_air is not 0.5 because a regression returned 0.5.
`int_lap_air_state.dirty_air_share_lap` is **binary** — 127,310 laps at 0.0, 35,419 at 1.0,
because it is `MAX(...)` over the single S2 sector. The model's `calibration_panel` then
filters `dirty_air_share_lag1 > 0`, which leaves a **constant** regressor. Replaying the
model's own SQL: n=25,158, `VAR_POP(x) = 0`, `COVAR_POP(x,y) = 0`, the `NULLIF` returns NULL
and `COALESCE(..., 0.5)` fires.

> **The shipped dirty-air tax has never been estimated from data.** It is the SQL's hard-coded
> fallback prior, applied as a flat 0.5 s penalty to any lap whose predecessor was following.
> The leaf doc's "the model assumes the cost of following never changed" is true but too kind:
> the model does not know what the cost of following is in *any* season.

This makes 06b's deviation below mandatory rather than optional, and it is the single most
publishable sentence in the item.

#### Covariate-only probes run before pre-registering (no outcome touched)

- **Corner apex speeds.** 2,405 (race × corner) cells with a non-null `v_min_kph`; field-median
  apex speed quantiles 5/25/50/75/95 = 64 / 90 / 119 / 169 / 271 km/h. Used only to fix the
  class thresholds below before seeing any effect.
- **Panel sizes.** The shipped `panel` CTE holds 124k laps over 2018–2024, 18.0–22.8% treated.
- **Calendar composition.** 32 tracks appear pre-2022, 25 in 2022–2024, **23 in both**.
- **Corner-residual coverage.** `corner_residual_total_s` is non-null on 35.9–43.0% of corner
  rows, by season — the documented consequence of the trailing-5-lap `field_corner_sample_n ≥ 5`
  gate, not a new loss.

#### Estimand

**θ_s** = the average cost in lap time, in seconds, of having been in dirty air on the
*previous* lap of the same stint, in season s. Positive = following costs time.

#### Population and outcome — the shipped model's, unchanged

Exactly `int_dirty_air_tax_component`'s `panel` CTE: `lap_time_s` non-null,
`int_event_corrections.correction_weight = 1.0`, `int_track_evolution.rainfall_flag` false.

- Outcome `y` = `partial_residual_s` = `lap_time_s − field_pace_smoothed_s − weight_penalty_s`.
- Treatment `D` = `dirty_air_share_lag1` ∈ {0, 1}, lagged **over the full chronological stint
  sequence** (the model's `full_sequence_lag` CTE — SC/VSC/pit laps included) and only then
  filtered. Computing the lag after filtering is a different treatment and gets a different
  mean; the reproduction target is the per-season table above, to four decimals.

#### Deviation 1, logged — keep the untreated laps

The shipped `calibration_panel` drops `D = 0`. With a binary regressor that is the whole bug.
Every fit below uses both arms. This is the only change to the estimating sample.

#### Estimator ladder, loose to strict. Nothing is dropped; all rungs are reported

| Rung | Absorbed | What it buys |
| :--- | :--- | :--- |
| F0 | nothing | The pooled OLS the model's SQL would give with the filter removed. Confounded: slow cars both follow more and lap slower. |
| F1 | driver × race | The identification the model's own header *claims* ("within-driver-race variation") and does not implement. |
| **F2** | stint, + lap-in-stint bin (1–5 / 6–10 / 11–15 / 16–20 / 21–25 / 26+) | **Headline.** Stint FE nests driver × race. The bin FE is load-bearing: within a stint, tyre age and the chance of being caught both rise, so F1 alone lets degradation load onto D. |
| F3 | F2, dropping laps within 2 of an SC / VSC / red-flag / pit lap | Robustness. `dirty_air_share_lap` is forced to 0 on SC laps, so restart laps are mechanically untreated *and* abnormally paced. |

Inference: cluster-robust on `race_id`, within season. Traffic is a race-level state, not a
lap-level draw. G (the cluster count) is reported with every coefficient; at ~17–24 races per
season the intervals will be wide, and that is the honest width.

#### The 2022 question, as a pre-declared comparison

Ground-effect era = `race_year >= 2022` (the repo's own `era_boundary`, from
`mart_degradation_history_envelope.sql`). Pre-declared contrast, from one pooled F2 fit with an
era × D interaction, race-clustered:

**Δ = θ(2022–2024) − θ(2018–2021).** The regulations were sold as making following cheaper, so
the directional prediction is **Δ < 0**. A Δ whose CI spans zero is reported as "no detectable
change", never as "no change".

#### Falsification, declared now

1. **Lead placebo.** Re-fit F2 with `D_lead1` (the *next* lap's following state) in place of
   `D_lag1`. Dirty air is persistent, so a non-zero lead coefficient is expected; the design
   fails if the lead is **not materially smaller** than the lag. If it is not, the per-season
   numbers describe a persistent traffic state and must not be published as a cost of following.
2. **Binary-treatment ceiling.** `D` is one bit per lap from a single S2 median gap. θ is the
   cost of *a lap classified as following*, not a dose-response in gap. Nothing here can be
   read as "x seconds per car length".
3. **Relative-to-field attenuation, and why it is survivable.** `int_field_pace_curve` already
   restricts its baseline to `air_state_dominant IN ('free_air','tow_zone')`, so the reference
   is a clean-air reference by construction — but `air_state_dominant` is a mode over three
   sectors, and **48.1%** of D=1 laps still enter it. θ is therefore attenuated. The share is
   **stable across seasons** (63.1–66.1% of treated laps carry a non-`dirty_air` mode, 2018–2024),
   so the attenuation is close to a common factor and the *season contrast* survives it even
   though the *level* is a lower bound. Reported, not corrected.
4. **Centred smoothing in the baseline.** `field_pace_smoothed_s` is a 5-lap **centred** rolling
   mean, so y at lap t depends on field pace at t+1 and t+2. D is lagged, so this does not put
   the future into the treatment, but the level of y is not a strictly backward-looking object.

#### Corner-type breakdown — era × class

- **Outcome.** `int_corner_skill_residuals.corner_residual_total_s` (braking + mid + exit, in
  seconds against the trailing-5-lap field median at that corner), non-null rows only.
- **Treatment.** The same lap-level `D_lag1`. The treatment is lap-grain and the outcome is
  corner-grain; the design is a heterogeneity split, not a per-corner exposure measure.
- **Fixed effects.** driver × race × corner, plus the lap-in-stint bins. The comparison is the
  same driver, at the same corner, in the same race, on a lap after following vs a lap not.
  Cluster-robust on `race_id`.
- **Classes**, fixed now, from each (race × corner) cell's field-median `v_min_kph` in
  `int_corner_metrics` over the `dim_corners` windows: **slow < 125 km/h**, **medium 125–199**,
  **fast ≥ 200**. On the probe above these hold roughly 51–56% / 30–33% / 13–18% of corners per
  season.
- **Mechanism prediction, declared before the fit.** Downforce scales with v², so a genuine
  reduction in *wake sensitivity* should be concentrated in **fast** corners. A uniform drop
  across all three classes is evidence the bundle moved something that is not aero — tyre
  construction, the ~46 kg minimum-weight rise, or ride height. This is the sentence that turns
  a number into a mechanism claim, and it is the reason the breakdown is worth running.
- **Robustness.** (a) within-race tercile classification instead of absolute thresholds, since
  absolute cut-points let a corner change class between eras as cars get faster; (b) restricted
  to the 23 tracks present in both eras, since the calendar changed.

#### Required caveat, restated so it cannot be dropped

2022 bundles the aero regulations with 18-inch tyres, a minimum-weight rise and porpoising.
**The defensible claim is about the bundle.** The corner-class split is what moves it toward
mechanism, and it is the only thing here that does.

### 06b results — run 2026-09-15

Scripts (scratchpad, throwaway, not committed): `d0_instrument_check_06b.py`,
`d1_build_panels_06b.py`, `d2_fit_06b.py`, `d3_diagnostics_06b.py`. Every coefficient, SE and
interval below is in `scratchpad/06b_dirty_air_per_season.json` (93 fits) and
`scratchpad/06b_diagnostics.json`, so any number here is recomputable without refitting.

**Gate 1 passed at panel level too.** The rebuilt panel is 123,993 laps — the shipped table's
row count exactly — and its per-season mean of D reproduces `int_dirty_air_tax_component`'s to
**1e-9 in all seven seasons**. Every number below is therefore measured on the shipped
population, not a lookalike.

**The FE absorption was cross-checked against an independent implementation.** A hand-written
alternating-projection demeaning over `stint_id` and `age_bin` followed by plain OLS returns
+0.3955941954 (2018), +0.0107991272 (2022) and −0.0360629124 (2024) against pyfixest's absorbed
fit — maximum difference **1.6e-13**. The headline is not an artefact of the estimator's
internals.

#### Deviation 2, logged after the fact — the corner outcome

The pre-registration named `corner_residual_total_s`. It is reported below unchanged, but the
**headline corner outcome is `mid_corner_residual_s`**, for two reasons found while fitting:

1. **Only the mid-corner phase has an unambiguous sign.** `braking_loss_s` is
   `(own braking_point_m − field median) × dt_per_dm`, and `braking_point_m` is the *first*
   braking sample's distance along the lap — so a **larger** value is braking **later**, which
   is faster. The other two phases are losses when positive. The total sums all three with one
   sign. See the cross-item finding below; this is 06c's problem, but it makes the total
   uninterpretable as "seconds lost" here.
2. **Two of the three phases are scaled by a quantity the treatment could move.**
   `braking_loss_s` and `exit_residual_s` both multiply a metre deviation by
   `dt_per_dm = 1 / (own S2 trap speed)`; `mid_corner_residual_s` divides by the **field's**
   `v_min`. **This one was checked and is not a live problem:** following moves own S2 trap
   speed by between −0.21 and +0.24 km/h, and every season's CI spans zero. Recorded because
   the pre-registration should have caught the channel, not because it bit.

#### The headline — per-season θ, F2, race-clustered 95% CI

| Season | n | G | **θ (s/lap)** | SE | 95% CI |
| :--- | ---: | ---: | ---: | ---: | :--- |
| 2018 | 14,850 | 20 | **+0.396** | 0.086 | [+0.217, +0.575] |
| 2019 | 17,982 | 21 | **+0.151** | 0.071 | [+0.004, +0.298] |
| 2020 | 14,122 | 17 | **+0.170** | 0.056 | [+0.052, +0.288] |
| 2021 | 19,198 | 21 | +0.083 | 0.054 | [−0.030, +0.196] |
| 2022 | 16,864 | 22 | +0.011 | 0.068 | [−0.130, +0.151] |
| 2023 | 19,261 | 22 | +0.045 | 0.045 | [−0.050, +0.139] |
| 2024 | 21,528 | 24 | −0.036 | 0.067 | [−0.175, +0.103] |

The ladder moves the levels but not the shape — F0 (no FE) 0.418 / 0.292 / 0.250 / −0.034 /
0.065 / 0.106 / −0.011; F1 (driver × race) 0.343 / 0.180 / 0.079 / −0.032 / −0.105 / −0.003 /
−0.114; F3 (F2 minus laps within 2 of an SC/VSC/red-flag/pit lap) 0.327 / 0.090 / 0.120 /
0.062 / −0.061 / −0.012 / −0.070. Every rung agrees that the number was large in 2018 and is
indistinguishable from zero by 2022.

> **The production constant is too high in every season, and outside the interval in six of
> seven.** θ_air = 0.5 s sits inside only 2018's CI. The model has been charging every
> following car 0.5 s/lap since 2018 on the strength of a `COALESCE` default.

#### The 2022 question — the naive answer, and why it does not survive

The pre-declared contrast comes back exactly as a regulation story would predict:

- θ(2018–2021) = **+0.185** [+0.115, +0.255], n=66,152, G=79
- θ(2022–2024) = **+0.004** [−0.066, +0.075], n=57,653, G=68
- **Δ = −0.219 [−0.331, −0.106], p = 0.0002** (pooled F2, era × D interaction, n=123,805, G=147)

That is a clean, significant, correctly-signed result, and **publishing it as a 2022 effect
would be wrong.** Three post-hoc cuts, all of which should have been pre-registered:

**Placebo era boundaries.** Refit the same interaction with a fake boundary at each season:

| Boundary | Δ | 95% CI | p |
| :--- | ---: | :--- | ---: |
| ≥ 2019 | −0.359 | [−0.542, −0.176] | 0.0002 |
| ≥ 2020 | −0.238 | [−0.369, −0.106] | 0.0005 |
| ≥ 2021 | −0.224 | [−0.341, −0.108] | 0.0002 |
| **≥ 2022 (the real one)** | **−0.219** | [−0.331, −0.106] | 0.0002 |
| ≥ 2023 | −0.192 | [−0.312, −0.073] | 0.0018 |
| ≥ 2024 | −0.234 | [−0.409, −0.059] | 0.0091 |

**Every boundary "works", and 2022 is the second-weakest of the six.** A step-change test that
fires at every possible step is detecting a trend, not a step.

**A linear season trend fits it.** dθ/dseason = **−0.0667 [−0.0963, −0.0371]**, p < 0.0001,
θ(2021) = +0.115. **Dropping 2018** shrinks Δ to −0.163 [−0.277, −0.049]; dropping 2018 and
2019 leaves −0.154 [−0.282, −0.025]. The era contrast is carried substantially by one season
that is four years before the treatment.

> **The measured claim.** The cost of following in this warehouse **fell by roughly two thirds
> between 2018 and 2024, and the decline is gradual and pre-dates the 2022 regulations.** The
> regulations cannot be given credit for it on this evidence. This is the opposite of the
> result the item expected, and it is the result worth publishing: the naive pre/post test that
> most people would run *passes*, and the falsification test kills it.

**Falsification 1 (pre-registered) — the lead placebo, joint fit.** lag / lead: 2018
**0.365 / 0.132**, 2019 0.134 / 0.099, 2020 **0.162 / 0.040**, 2021 0.068 / 0.073, 2022
−0.006 / 0.113, 2023 0.039 / 0.040, 2024 −0.044 / 0.042.

Ruling by the rule written down beforehand: the directional design **holds for 2018 and 2020**
(lag materially larger), is **marginal for 2019**, and **fails for 2021–2024** — where lag and
lead are the same size and both near zero. So **the 2021–2024 numbers may not be published as
causal costs of following**; they are published as *no detectable directional cost*, which is
what the table says anyway. The placebo does not rescue a hidden late-era effect; it says
there is nothing there to certify either way.

#### The corner-type breakdown — where the real surprise is

Apex-speed deficit (`mid_corner_residual_s`), driver × race × corner FE + age bins,
race-clustered. The column is labelled seconds but is `(Δv / field v_min) / 0.2778`, so
**coefficient × 0.2778 = the fractional apex-speed deficit**, which is the interpretable form.

| Class | n (pre / ground) | θ pre | θ ground | as % apex speed | Δ | 95% CI |
| :--- | ---: | ---: | ---: | :--- | ---: | :--- |
| slow < 125 km/h | 235k / 209k | +0.0308 | +0.0342 | 0.86% → 0.95% | −0.0001 | [−0.0107, +0.0105] |
| medium 125–199 | 160k / 116k | +0.0308 | +0.0311 | 0.86% → 0.86% | −0.0023 | [−0.0184, +0.0138] |
| fast ≥ 200 km/h | 30k / 29k | +0.0226 | +0.0140 | 0.63% → 0.39% | −0.0114 | [−0.0316, +0.0089] |

**The point estimates are ordered exactly as the pre-declared mechanism predicts** — the fall
is concentrated in fast corners, where downforce matters most, and is literally zero in slow
corners. **And not one of the three Δs is distinguishable from zero.** The honest reading is:
the data is consistent with the aero mechanism and has nowhere near the power to confirm it.
Fast corners are 15% of corner-rows; that is where the precision went.

The finding that *is* precise is the level, not the change:

> **Following still costs about 0.9% of apex speed in a slow corner in 2024, exactly as it did
> in 2018.** Per season, slow-corner deficit: 0.027 / 0.036 / 0.031 / 0.029 / 0.038 / 0.025 /
> 0.039 — flat, and every season's CI excludes zero. **The lap-level cost of following
> collapsed; the cornering deficit did not move.** Whatever made following cheaper over a full
> lap did not make the car grip better in the corner.

**Phase decomposition (post-hoc), pre → ground, all three classes:** braking −0.032 → −0.012
(slow), −0.035 → −0.030 (medium), −0.059 → −0.053 (fast); exit −0.011 → −0.010, −0.012 →
−0.012, −0.010 → −0.017. Following makes a driver brake **earlier** (negative = smaller
`braking_point_m`) in every class and both eras, most in fast corners, which is the textbook
downforce mechanism and corroborates the apex result.

**The pre-registered total**, reported as promised: slow −0.012 → +0.013 (Δ +0.024
[+0.006, +0.042]), medium −0.016 → −0.011 (Δ +0.002 [−0.019, +0.022]), fast −0.046 → −0.056
(Δ −0.005 [−0.051, +0.041]). Not interpreted, for the sign reason in Deviation 2.

**Robustness (a), within-race speed terciles:** Δ = +0.017 [−0.009, +0.042] / +0.022
[+0.002, +0.041] / −0.010 [−0.036, +0.017] on the total, bottom to top tercile — same ordering.
**Robustness (b), the 23 tracks in both eras:** slow Δ +0.027 [+0.008, +0.046], medium +0.007
[−0.016, +0.031], fast −0.000 [−0.050, +0.050]. The calendar change is not driving it.

#### Cross-item finding for `06c`, found here and not chased here

`braking_loss_s` enters `mart_corner_skill_driver.corner_skill_index` with the **same sign** as
`mid_corner_skill_z` and `exit_skill_z`, and the mart orders `corner_skill_index ASC` — so a
lower index is better, and a **negative** `braking_loss_s` (braking **earlier**) counts as
skill.

06b supplies independent evidence on that sign from a treatment whose physical direction is
known a priori: **dirty air reduces downforce, and in this data it produces negative
`braking_loss_s` in every corner class and both eras.** Braking earlier is therefore the *bad*
direction, and the index rewards it. **This is a live candidate for the 06c Verstappen
anomaly** — VER's braking `+0.076` would read as *braking later than the same-car baseline*,
which is the received-wisdom answer, not a contradiction of it. 06c named "a baseline bug" as
one of two explanations; this is a specific, checkable one. Handed over, not resolved.

#### Decision on the warehouse model (the DoD's second half)

**KEEP the global θ in production. Do not change `int_dirty_air_tax_component` in this item.**
Written reason, not a deferral:

`fct_cliff_prediction_features` builds its regression target as a lead-difference of
`driver_skill_residual_s` (lines 490–573), and `int_lap_residual_decomposed` subtracts
`dirty_air_tax_s` when forming that column. **The dirty-air tax is inside the label.** Changing
θ_air rewrites the target for every model in the programme and invalidates the v11 headline
every arm result is measured against — which is a gated change under
[`../foundations/gates.md`](../foundations/gates.md), not something a publication item does on
the way past.

The defect's footprint, measured so the next item can price it: the tax injects a ±0.5 s step
into the label on **14.3% of panel laps** (the share where the following state flips between
t−1 and t; 12.6% in 2018 rising to 15.7% in 2022). The training label's own sd is **0.988 s**
and its median absolute value is **0.363 s**. So a `COALESCE` default is moving the label by
**half a standard deviation on one lap in seven**.

**Raise as a new gated item** (proposed `08l`, foundations-repair, not created by this session):
remove the `dirty_air_share_lag1 > 0` filter from `calibration_panel` so θ_air is estimated
rather than defaulted, decide global-vs-per-season on the evidence above, and run the full gate
ladder because the label moves. Two things that item must not repeat: a binary regressor
filtered to its treated arm identifies nothing, and `dirty_air_share_lap` is a **one-bit
S2-only** measure, so the natural fix is a dose-response on the gap, not a better-fitted
constant.

Per-season fits are therefore **published separately, not shipped** — exactly the second branch
the DoD allows.

#### The post — draft

**Headline.** *"F1's 2022 regulations were sold as making cars easier to follow. In this data
the cost of following did fall — by about two thirds since 2018 — but it was already falling
before the new cars arrived, and a placebo test fires at every season boundary, not just 2022."*

**Body, in order.**

1. The number nobody has: per-season θ, the table above, with intervals. Lead with 2018 +0.40
   s/lap and 2024 −0.04 s/lap, both with CIs.
2. The identification in one paragraph: prior-lap following state → this-lap pace, stint fixed
   effects, tyre-age bins, race-clustered errors. Say the treatment is one bit per lap.
3. **The falsification, in the post and not in a reply.** The pre/post-2022 contrast is
   −0.219, p = 0.0002 — and every fake boundary from 2019 to 2024 gives the same thing. Print
   the placebo table. This is the part a strategist or a journalist can check, and it is the
   reason to trust the rest.
4. The heterogeneity, honestly: fast-corner deficit 0.63% → 0.39% of apex speed, slow corners
   unchanged at ~0.9% — ordered as the aero mechanism predicts, **none of it significant**.
   State that the mechanism test was underpowered and say by how much.
5. The half that *is* precise: the cornering deficit did not move at all, in any season, while
   the lap-level cost collapsed.
6. What would falsify it, named: per-corner gap exposure instead of a lap-level bit; a
   dose-response in gap rather than a 1.5 s threshold; the same fit on a season the model has
   not seen.

**Caveats that must appear in the body.**

- **2022 is a bundle** — aero regulations, 18-inch tyres, a ~46 kg minimum-weight rise and
  porpoising. Nothing here separates them, and the corner split is underpowered to.
- **The treatment is one bit per lap**, from a single S2 median gap crossing 1.5 s. No
  dose-response; nothing here is "x seconds per car length".
- **θ is measured against a field-pace baseline that is only mostly clean-air.** 48.1% of
  treated laps still enter it (`air_state_dominant` is a mode over three sectors), so the level
  is a lower bound. The contamination share is flat across seasons (63.1–66.1%), which is why
  the season *contrast* survives it.
- **`field_pace_smoothed_s` is a 5-lap centred mean**, so the baseline is not strictly
  backward-looking. The treatment is lagged, so the future is not in the treatment.
- **The 2021–2024 estimates failed the lead placebo** and are reported as "no detectable
  directional cost", not as measured costs.
- **The warehouse still ships the 0.5 s constant**, and the post should say so rather than
  imply the production model was fixed.

#### Definition of done

| Requirement | Status |
| :--- | :--- |
| Per-season θ with confidence intervals | **Done** — table above, four estimator rungs, race-clustered |
| The corner-type breakdown | **Done** — era × class, per-season × class, phase decomposition, two robustness cuts; reported as underpowered, which is the honest result |
| Bundled-treatment caveat stated in the post | **Done** — first caveat in the draft |
| Warehouse model updated, or a written decision | **Done** — written decision to keep the global θ, with the label-lineage reason and a measured footprint, plus a proposed follow-up item |

Not done, and deliberately: the post is drafted, not published, and
`int_dirty_air_tax_component` is unchanged.

---

## 06c — Corner-phase skill

**Objective.** Publish the phase decomposition, and publish the anomaly.

**Verified 2026-09-07** from `mart_corner_skill_driver` (139 driver-seasons with a populated
index). 2024 leader **NOR at index −3.22, and it is nearly all exit** (exit −0.275 s vs braking
−0.041 s). "Norris's 2024 edge was traction, not braking" is specific and checkable.

**The anomaly, which is the more valuable half.** VER shows braking **+0.076 (weak)** and
mid-corner −0.078 (strong), against near-universal received wisdom about his braking. The
baseline is leave-one-race-out over same-car drivers, so for 2024 it is measured against PER.
**Post it as an open question, not a finding** — it is either something real or a baseline bug,
and working that out in public is worth more than another leaderboard.

**Required caveats.** The index is a sum of z-scores over winsorized (driver, race, corner)
cells with a `PHASE_MIN_CELLS = 30` floor; only 139 driver-seasons clear it; and the baseline
is teammate-relative, so a driver with a weak teammate and a driver with a strong one are not
on the same scale.

**Definition of done.** Post drafted with the phase split, the cell counts and SEs shown, the
teammate-relative baseline stated plainly, and the VER anomaly framed as an open question with
the two candidate explanations named.
