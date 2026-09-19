# 00 — Standing corrections

**Group:** 00 · **Depends on:** nothing · **Cost:** hours

Three stale or wrong facts found 2026-09-07 that other work items cite. None is research;
all three are cheap; two of them silently break an item further down the ladder if left.

---

## 00a — The feature count is 33, not 24

**Objective.** Every document in `reference/` says the contract is 24 features. It has been
**33** since v11.

**Verified.** `ml/src/schema.py`'s `FEATURE_GROUPS` sums 4 (`stint_position`) + 7 (`compound`)
+ 5 (`cliff_prior`) + 4 (`thermal`) + 4 (`dirty_air`) + 9 (`proximity`) = 33, and
`MODEL_VERSION_DEFAULT`'s note records the v11 move as "contract, 24 -> 33".
`PER_TARGET_FEATURE_MASK` masks only `stint_length_laps`, for `stint_life_regressor`, and that
column is not in `FEATURE_COLUMNS` anyway — so all three degradation quantiles see all 33.

**Why it is not cosmetic.** `reference/ml_research_program.md` §3b's fix 2 is *"match in the
model's own feature space, not hand-picked keys"*, and its closing command specifies "the
scaled 24-feature space". Building that space from 24 columns drops `proximity` — the nine
columns that were the v11 win — and reintroduces a milder form of the failure mode §3a found.
The same section's §3a parenthetical also names "throttle decay, braking drift", which are
`racing_line` candidates that were measured and **not shipped**; they are not in the contract
at all.

**Method.**
```bash
grep -rn "24 features\|24-feature\|24 columns\|24 -> 33\|42 columns" _improvements/reference/ docs/
```
Correct each hit, and at each one check whether the surrounding argument survives the change
rather than only the number.

**Definition of done.** No document claims a 24-column contract; `reference/ml_research_program.md`
§3a/§3b and its closing command name 33 and drop the two non-contract feature names; the
history entry records which arguments changed as well as which numbers.

---

## 00b — §1a's "no safety-car signal exists" claim is false

**Objective.** `reference/ml_research_program.md` §1a caps the stint-life target at 0.80–0.85
of attainable on this reasoning:

> *"Remaining stint life is set partly by pit-wall strategy calls and safety-car timing —
> events that are not a tyre-degradation question at all and carry no signal in any feature
> this warehouse could build."*

**Verified.** The clause after the dash is wrong. `int_sc_hazard_history` holds
`sc_hazard_per_lap`, `vsc_hazard_per_lap`, `any_hazard_per_lap` and empirical-Bayes-shrunk
variants of each, for 36 circuits, estimated from `stg_track_status` deployment events with
racing-lap exposure from `stg_laps`.

**Scope of the correction.** §1a marks the paragraph "Inference, not measurement", so this
corrects an **Assumed** claim, not a Verified one. The 0.80–0.85 range was never measured; it
should be either deleted or replaced with a measurement, since the SC/VSC share of stint ends
*is* computable from `stg_track_status` now that it has landed.

**Definition of done.** §1a no longer asserts the signal cannot exist; it either cites
`int_sc_hazard_history` and states the cap as open, or replaces the range with a measured
SC/VSC share of stint ends. Work item `02d` is unblocked.

---

## 00c — LORO leakage ruling · RULED 2026-09-07

**This item was written on a false premise, and the premise is the whole item.** It is kept
here in corrected form because the mistake is instructive: an acronym was read, not traced.

**What it claimed.** That `int_driver_race_skill_loro.driver_skill_loro_s` is
*leave-one-race-out* — "precisely the construction that makes a skill term admissible in
principle — the focal race is excluded from the estimate that scores it" — and that D1 was
therefore a genuine judgement call between losing a legitimate feature and walking past a
leakage list.

**What the model actually does.** `LORO` there is **leave-one-DRIVER-out**. The model's own
first line says so: *"De-confounded absolute driver skill: leave-one-driver-out (LORO) car
baseline."* A driver is graded against the **other same-car drivers in the same race** —
for a two-car team, his teammate. The focal race is never excluded. The output is

```sql
d.driver_p20_pace_delta_s - d.loro_car_baseline_s AS driver_skill_loro_s
```

where `driver_p20_pace_delta_s` is the focal driver's own 20th-percentile clean-lap pace delta
**in the race being predicted**. Every CTE groups by `(race_year, race_id, ...)`; there is no
cross-race window anywhere in the file.

**Verified by construction, not by reading.** A driver with exactly one race in the entire
table still receives a non-NULL value — `DOO` (2024_24) = 0.0468 from 45 clean laps, `AIT`
(2020_16) = −1.3164 from 61. Under leave-one-race-out there is no other race to estimate from,
so the value would have to be NULL. It is not. The column is contemporaneous with the target.

**Ruling.** Barred, and not on the principle D1 was framed around. The column is built from
the focal race's own lap times, so for a model predicting that race's degradation it is
textbook leakage. `driver_skill_loro_s`, `driver_skill_field_s` and `driver_skill_loro_mean_s`
are now named in `EXCLUDED_LEAKAGE_COLUMNS` with the trace recorded beside them.

**A guard gap found on the way.** The leakage test is a set intersection on names —
`set(X.columns) & EXCLUDED_LEAKAGE_COLUMNS` (`ml/tests/test_features.py:45`) — so any column
not on the list passes straight through. These three were not on it. Nothing leaked, because
`fct_cliff_prediction_features` (64 columns) does not carry them; but that made the safety
**accidental rather than designed**, and a later session joining the rating chain into the mart
would have met no guard at all.

**What remains open, and it is not this.** Whether a *genuine* leave-one-race-out skill term
would be admissible is still unanswered — because nobody has built one. D1 as posed cannot
answer it, since its example turned out not to be an instance of the thing. If such a column is
ever built, it needs its own decision and its own trace.

**Definition of done.** Met: ruling written into `schema.py` beside `EXCLUDED_LEAKAGE_COLUMNS`;
the three columns barred; `int_synthetic_teammate` stays barred regardless, since
`driver_skill_proxy_s` is not leave-anything-out.

---

## 00d — `corner_skill_index` counts braking earlier as skill

**Found 2026-09-18** by the build-order audit, which ran the falsification `06c`'s own checklist
named and left unrun ("inspect SQL for braking z-score sign convention"). `06b` supplied the
candidate.

**Verified from source.**

- `int_corner_skill_residuals.sql:170-178` — `braking_loss_s = (own braking_point_m − field
  median) × dt_per_dm`. `braking_point_m` is the first braking sample's distance along the lap, so
  **positive = braking later = faster**.
- The other two phases are built the other way round: `mid_corner_residual_s = (field v_min − own
  v_min)` scaled by the field's apex speed, and `exit_residual_s = (own throttle_point_m − field
  median) × dt_per_dm`. **Positive = worse** for both.
- `mart_corner_skill_driver.sql:316-317` — `corner_skill_index = braking_skill_z +
  mid_corner_skill_z + exit_skill_z`, ordered `ASC` (lower = better). Nothing in `standardized`
  or upstream negates the braking term.

So the braking phase enters the index with the wrong sign. `06b` reached the same conclusion
independently, from a treatment whose physical direction is known a priori: dirty air produces
negative `braking_loss_s` in every corner class and both eras, and dirty air can only make a driver
brake earlier.

**Blast radius.**

- **The app.** `app/src/features/corner-phase-skill/queries.ts:37` ranks drivers by
  `corner_skill_index ASC`, and `transform.ts` passes the values through unchanged. The shipped
  leaderboard is built on the inverted term.
- **`06c`.** Its headline anomaly — VER braking `+0.0745` against PER — reads as *braking later
  than the same-car baseline*: the received wisdom, not a contradiction of it.
- **`corner_residual_total_s`** sums the three phases with one sign, so it is not "seconds lost"
  either. `06b` noticed and moved its headline to the mid phase.
- **`02c`'s mart-only braking aggregates** in `int_lap_corner_inputs` inherit the convention. A
  monotone sign flip leaves a tree's predictions unchanged, so `02c`'s arm results are unaffected in
  substance. Only how they read changes.

**The ruling this item makes — not made here.** There are two places to fix it. (a) At the
source: redefine `braking_loss_s` as `(field median − own) × dt_per_dm`, so all three phases read
"positive = loss" and `corner_residual_total_s` means what its name says. (b) In the mart only:
negate the braking z inside the index. (a) is the cleaner contract but touches `02c`'s columns and
the residual total. (b) is one line, but it leaves a column named "loss" that measures a gain.
Argue it in writing before editing, as `08m` did.

**Definition of done.**

- The sign convention is ruled and argued in writing.
- All three phases share one convention in whatever the index sums.
- `mart_corner_skill_driver` is rebuilt and its before/after reported, at minimum the 2024 rank
  changes, since that is the season the app shows. This also discharges `02g`'s one outstanding
  clause: the mart re-run whose output change was never reported.
- A dbt test pins the direction. For example, a driver who brakes later than the field median at
  every corner must score better, not worse.
- The `schema.yml` descriptions of `braking_loss_s` and `corner_skill_index` state the direction.
- The app page is re-checked against the rebuilt mart.

`06c`'s post is rewritten after this lands, not before.

**Cost:** ~0.5 day.
