> **Round 3 (2026-09-24)** adds F38–F49 in [`transform_forensic_audit_report_round3.md`](transform_forensic_audit_report_round3.md); the status board now covers F1–F49.

# Forensic audit of the transform layer — round 2

**Run:** 2026-09-24, against `data/dev.duckdb` (the same v14 build as round 1, dataset fingerprint
`87e1d013…`). Every probe opens it `read_only=True`. The charter is
[`transform_forensic_audit.md`](transform_forensic_audit.md); round 1 is
[`transform_forensic_audit_report.md`](transform_forensic_audit_report.md) (F1–F21).

**What round 2 covered that round 1 did not:**
- the decomposition's own algebra, component by component;
- bronze tyre, stint and rain data checked against independent in-tree oracles (pit stops, compounds);
- the 25 app query files round 1 left unread (its Assumed list);
- the export script and the home page;
- whether each dbt test can fail at all.

Finding IDs continue round 1's, **F22–F37**.

**How to verify while building.** One command re-measures every finding from both rounds, read-only, in
under a second:

```
.venv/bin/python _improvements/reference/transform_forensic_audit_artefacts/verify_findings.py        # all
.venv/bin/python _improvements/reference/transform_forensic_audit_artefacts/verify_findings.py F22 F23a
```

Each line prints `PRESENT` or `CLEARED` with the measured value. Today: **37 present / 37 checked.** F9
and F15 have no mechanical check. The per-finding probes (`round2/r2_*.py`, each with its `.log`) are the
full evidence. All of them run from any cwd via `round2/_db.py`, and `OTP_DB=` points them at another build.

---

## 1. Verdict

**Round 1's verdict stands and gets worse: not safe to retrain on as-is, and several published fan
claims do not survive.** Three findings decide it:

- **F22.** The training label subtracts rubber and ambient twice: they are already inside the base it is
  measured against. Removing the second subtraction moves `next_5_lap_cumulative_jump_s` by a mean
  **0.30 s** (34% of labelled rows by more than 250 ms) and flips **3.7%** of cliff labels.
- **F23.** Round 1's fabricated laps (F1) drag the dirty-air coefficient θ down **2.7×**
  (0.416 → 0.152 s/lap). 06b's published finding, "no detectable directional cost 2021–2024", is an
  artefact of them. On measured laps, θ is positive with a CI excluding zero in every season.
- **F28, F27, F29, F30.** Four fan-facing pages state things their SQL does not compute. On Quali vs Race,
  the delta's sign flips for 17–23 of about 20 drivers per season. Wet-Race Specialist uses no wet laps.
  The Blind-Test Scoreboard's band coverage reads 91% where the trained target shows 79%. The Tyre-Cliff
  "validation" is circular.

**Sequencing consequence (new).** Fixing F1 moves θ by itself, because the fabricated laps leave the
calibration panel. F1, F22 and F23 therefore belong in **one** label version bump, not three.

---

## 2. Findings, ranked (severity × blast radius)

| # | Sev | Where | What | Verdict | A published number moves? |
| :-- | :-- | :-- | :-- | :-- | :-- |
| F22 | **High** | `int_lap_residual_decomposed.sql:215-216,301,312-313` | Rubber and ambient are subtracted from a residual already measured against a base that contains them (identity exact to 3e-14) | Definitely wrong | **Yes**, every trio and cliff headline; app residual surfaces |
| F23 | **High** | `int_dirty_air_tax_component.sql:146,169-170,257` | (a) θ is calibrated on F1's fabricated laps: 0.152 as built vs **0.416** on measured laps. (b) The tax is applied only to the calibration population, so 3,504 laps behind a car are billed 0 s | Definitely wrong | **Yes**: the label (tax is in it), the dirty-air page, and **06b's published per-season claim** |
| F28 | **Med-High** (fan) | `app/.../quali-vs-race-skill/queries.ts:34-36`; `methodology.tsx:20` | Q−R delta subtracts a *positive = faster* teammate proxy from a *negative = faster* field residual | Definitely wrong | Page ranking ≈ noise (Spearman −0.08…0.41 vs sign-consistent) |
| F24 | Medium | bronze → `int_stint_geometry.sql:36,43,100` | Stint numbering ignores the actual pit stops in 3 races (2018 China, 2022 Austria, 2025 Miami); tyre age/compound wrong across the missed stops | Definitely wrong (bronze) | 660 eligible rows on a wrong stint; stint-life targets and in-race seed fits for those races |
| F25 | Medium | bronze → `int_stint_geometry.sql:36-44` | 2018 rounds 1–17: lap 1 has no stint, so `lap_in_stint` **and** `age_in_stint` read one lap low on every stint-1 lap | Definitely wrong (bronze) | 3,667 eligible rows = 24.5% of 2018; two contract features |
| F26 | Medium | bronze `weather.Rainfall` → `int_lap_anomaly_flags.sql:216` | Rain flag says 83% raining at the dry 2018 Spanish and 2019 Monaco GPs; never set at the fully wet 2020/2021 Turkish GPs | Definitely wrong (bronze; false positives) | 1,656 dry laps excluded as `conditions`; 2,529 inter/wet laps kept |
| F27 | Medium (fan) | `fct_driver_skill_features.sql:99,140`; `app/.../wet-race-specialist/queries.ts:24-29` | "Wet skill" = teammate proxy on the **non-rain** laps of races where it rained somewhere; 0 rain laps reach the page | Definitely wrong | Whole Wet-Race Specialist ranking |
| F29 | Medium (fan) | `app/.../blind-test-scoreboard/queries.ts:74,90` | Plots the 5-lap cumulative prediction against the legacy **1-lap** undetrended actual | Definitely wrong | Page shows 90.8% p10–p90 coverage; true target 79.4% |
| F31 | Medium | `int_pit_strategy_value.sql:52-70,304-317,406-409,437`; `app/.../pit-strategy/queries.ts:101-116` | A stop is matched only within the last *valid* lap + 1, so stops after SC/VSC/red run-ins are lost | Definitely wrong | 430 stints ungraded (30% of SC stops, 83% of red-flag stops); Gantt misdrawn |
| F34 | Medium (process) | `transform/tests/` | 7 singular tests cannot fail, or cannot see the defect they are named for | Definitely | Suite's PASS count overstates coverage |
| F30 | Med-Low (fan) | `app/.../tyre-cliff-survival/queries.ts:119-120`; `methodology.tsx:26-27` | The KM "cliff event" *is* `age > seed onset`, so "KM crosses 0.5 near the model line = calibrated" is circular | Definitely wrong | Page's validation claim |
| F32 | Low-Med | `int_lap_fuel_state.sql:58`; seed `dim_circuits` | Modelled starting fuel exceeds the FIA maximum in 134/171 races (median 117.8 kg; Sakhir 2020 147.9 kg) | Definitely wrong | Fuel component magnitudes; cross-circuit `fuel_mass_kg` scale |
| F33 | Low-Med | bronze → `stg_laps_qualifying.sql:148` | 26% of 2018 timed quali laps fail `is_accurate` (≤0.4% other seasons); 2018 quali features 8% NULL or built on 1–2 laps | Definitely wrong (bronze-shaped gate) | Cliff classifier only |
| F35 | Low | `int_lap_residual_decomposed.sql:223-225` | Circuit×constructor interaction added on top of a **per-race** constructor level that already contains it; exactly 0 throughout 2018 | Probably wrong | Residual *levels* (app skill pages), season-shaped; cancels out of the ML label |
| F36 | Low | `app/.../lap-waterfall/queries.ts:61,90`; `race-lost/queries.ts:58` | "Observed delta" rebuilt as explained + skill + `track_unexplained_s`; the identity has no third term | Definitely wrong | Per driver-race mean 0.02 s, max 1.36 s |
| F37 | Low | `scripts/export_app_data.py:533-564`; `routes/home/index.tsx:199-201` | Home page: "44 circuits covered" (32 venues raced; 8 rows are events never held); "5/5 models beat baseline" = count of stale `*_v1.onnx` files | Definitely wrong | Home page |

---

### F22 — Rubber and ambient are subtracted twice

- **Severity:** High.
- **file:line:** `int_lap_residual_decomposed.sql:215-216` (joined from `int_track_evolution`), `:301`
  (in `total_explained_s`), `:312-313` (subtracted in `driver_skill_residual_s`). The base is `:211`
  (`field_pace_smoothed_s AS base_track_pace_s`); the components are `int_track_evolution.sql:85-109`.
- **Column / transformation:** `driver_skill_residual_s` → `next_5_lap_cumulative_jump_s`,
  `laps_until_cliff_class`.
- **Intended grain:** valid race lap.
- **Observed behaviour:** `int_track_evolution` decomposes *the same curve* the residual is measured
  against, so for every lap with an evolution row:
  `base_track_pace_s = race_mean + rubber_component_s + ambient_component_s + unexplained_residual_s`.
  This holds to a max error of **2.8e-14** over 135,655 laps. `pace_delta_s = lap_time − base` has therefore
  already removed rubber and ambient, and the residual removes them again:
  `residual = lap_time − race_mean − 2·rubber − 2·ambient − unexplained − fuel − compound − constructor − dirty_air`.
  Mean |ambient| is 0.117 s (p90 0.31, max 1.36); mean |rubber| is 0.026 s.
- **Magnitude, measured** (`round2/r2_rubber_ambient_double_count.py`/`.log`):
  - The label was rebuilt in SQL exactly as the mart builds it, re-fitting the per-stint drift the way
    `int_lap_residual_stint_detrend` does. It reproduces the mart to **7e-15** (label) and **0
    mismatches** (cliff class).
  - With the second subtraction removed, on 95,513 eligible labelled rows the label moves by a mean
    **0.300 s**, median 0.129, p90 0.787. **69.0%** move more than 50 ms, **34.5%** more than 250 ms.
    Correlation with the as-built label is 0.991; label SD is 4.15 s.
  - Every season moves by a mean 0.24–0.40 s.
  - **4,927 of 132,265 cliff labels (3.7%) change class**, mostly `6_plus ↔ none_in_stint`.
  - The linear rubber part is absorbed by the per-stint drift. What remains is the ambient term's
    lap-to-lap movement, plus the jump at every lap where the evolution row is missing: 24,552 spine laps
    have none, and the COALESCE-to-0 at `:215-216` means those laps are *not* double-subtracted.
- **Why it is wrong:** a term cannot both be removed by the reference and be an additive part of the
  deviation from that reference. The header identity (`:9-18`) and 07's closed-channel argument
  (`work/07-causal-pit-timing.md:558`, `:648`) both assume `pace_delta_s` still contains track state. It
  does not. **This is new evidence, not a re-litigation**: the identity above is exact.
- **Verdict:** Definitely wrong. The creating lines, the exact algebra and a label measured both ways are
  all shown.
- **Earliest point:** `int_lap_residual_decomposed`.
- **Isolated or systematic:** systematic, every race.
- **ML impact:** four of five families' targets (trio and cliff). Stint life is unaffected.
- **App impact:** the Lap Waterfall and Race Lost pages draw rubber and ambient bars as parts of a delta
  that does not contain them. `int_sector_residual_decomposed` apportions the same term per sector.
- **Fix:** measure against the per-lap field base and drop rubber and ambient from the residual. Or
  measure against the race-mean base and keep them. Not both. It changes the label, so bundle it with F1
  and F23 in one version bump.
- **Test:** T16.
- **How I could be wrong:**
  1. If the authors *intend* the residual to include "minus the track trend", it is a definition choice.
     But then the header identity and 07's argument are false, and the doubled trend has no physical
     reading.
  2. The rebuild re-fits drift on the corrected residual. That is the right counterfactual, but it means
     part of the shift is drift re-estimation, not the ambient term alone.

### F23 — θ_air is calibrated on fabricated laps and applied to only part of the spine

- **Severity:** High. It rewrites a published fan claim and it sits in the label.
- **file:line:** `int_dirty_air_tax_component.sql:146` (the calibration residual uses
  `COALESCE(fp.field_pace_smoothed_s, f.lap_time_s)`, round 1's F1 pattern), `:169-170` (the panel keeps
  `correction_weight = 1.0` and non-rain laps), `:257` (`with_tax … FROM panel`, so the tax exists only
  for panel laps). `int_lap_residual_decomposed.sql:241` COALESCEs the missing tax to 0.
- **Observed behaviour** (`round2/r2_dirty_air_tax_population.py`, `r2_06b_theta_refit.py` and their logs):
  - **(a) θ.** 10,407 of 145,543 panel laps (7.2%) have no field base. Their partial residual is just
    `−fuel` (mean **−1.44 s**), and they are disproportionately "treated": 39% vs 22%. θ as built is
    **0.152123**, reproducing the shipped value exactly. On measured laps only it is **0.415821**.
  - **06b re-run.** 06b's own estimator was re-run: its panel SQL imported verbatim, F2 spec (stint +
    age-bin FE, race-clustered). The `as_06b` arm **reproduces 06b's published table exactly**:
    2018–2024 = +0.396, +0.151, +0.170, +0.083, +0.011, +0.045, −0.036, and trend −0.0667/season
    [−0.0963, −0.0371].
  - **06b without the fabricated laps.** θ is 0.437, 0.345, 0.307, 0.305, 0.221, 0.185, 0.192 (2025:
    0.245), and **every 95% CI excludes zero**. The trend is −0.0509/season [−0.0695, −0.0323] and θ(2021)
    is +0.288 instead of +0.115.
  - **Placebo.** On the measured arm the lead placebo still carries weight (joint lead 0.09–0.19). But lag
    exceeds lead by about 1.6–2× in 2021–2024, where 06b ruled "lag ≈ lead ≈ 0".
  - **(b) Missing tax.** 14,664 spine laps have no tax row, because they were downweighted (0.3/0.6) or
    wet. 3,504 of them followed a car on the previous lap (`share_lag1 > 0`) and are billed **0 s instead
    of θ**. 1,980 of those are training-eligible.
- **Why it is wrong:**
  - (a) The fabricated `pace_delta_s = 0` is not a measurement (F1). Here it enters a regression, where it
    is anti-correlated with treatment through race-start fuel and bunching.
  - (b) The calibration filter is right for *estimating* θ and wrong for *applying* it. An identical lap
    behind a car is charged or not depending on a yellow-flag weight.
- **Verdict:** Definitely wrong, for both (a) and (b).
- **What this changes in the tree:**
  - 06b's measured claim (`work/06-publication.md` 06b, "fell by roughly two thirds … 2021–2024 no
    detectable directional cost", `:403`, `:603`) is contaminated in level. The decline survives at about
    −0.05/season; "nothing there" does not.
  - 08q's per-season table and its "negative outcome must stay open" framing (`work/08-foundations-repair.md`
    08q) rest on the same panel.
  - The dirty-air page's methodology also says "per-circuit OLS coefficient" (`dirty-air-cost/methodology.tsx:19`).
    It is one global θ.
- **ML impact:** the tax is inside the label. **Fixing F1 alone moves θ 2.7×** and therefore the label on
  every dirty-air lap, which is why F1, F22 and F23 must ship together.
- **Fix:**
  - (a) follows from round 1's F1 fix (NULL base → NULL partial residual → out of the panel). Then re-run
    06b's pre-registered ladder before anything is re-published.
  - (b) compute the tax for every spine lap from the panel's θ.
- **Tests:** T17 and T18.
- **How I could be wrong:**
  1. The measured-arm θ is still an association: the lead placebo is not clean.
  2. Laps with a missing base are first, last and mixed-condition laps. Excluding them changes the
     population as well as removing the fabrication. But the fabricated values are not data, so the
     as-built number cannot be the right one either.

### F28 — Quali vs Race mixes two sign conventions

- **Severity:** Medium-High (fan-facing).
- **file:line:** `app/src/features/quali-vs-race-skill/queries.ts:34-36`; `methodology.tsx:20`
  ("negative = faster" for both); `fct_driver_skill_features.sql:14` (proxy "positive = ego faster than
  synthetic teammate").
- **Observed behaviour** (`round2/r2_quali_vs_race_sign.py`):
  - The proxy correlates **−0.34** with the race residual, confirming the sign conventions are opposite.
  - The page's per-season ranking against a sign-consistent delta (quali residual − race residual) has
    Spearman **0.41, −0.05, 0.00, 0.32, 0.21, −0.05, 0.02, −0.08** for 2018–2025.
  - The delta's sign differs for **17–23 of 20–23 drivers every season**.
  - The two sides also use different reference frames: field-relative vs teammate-relative.
  - The warehouse's own `quali_vs_race_skill_delta_s` (`int_qualifying_decomposed`) uses the race
    residual, so it has one convention, but the page does not read it.
  - The join is at qualifying *lap* grain, so every average is weighted by push-lap count.
- **Verdict:** Definitely wrong.
- **Fix:** read `quali_vs_race_skill_delta_s`, or compute both sides as field residuals; aggregate at
  driver-race grain.
- **Test:** T22a.
- **How I could be wrong:** the "consistent" comparator inherits F1, F22 and F35. The sign mixing does not
  depend on them.

### F24 — Stint numbering that ignores the car's pit stops (bronze)

- **Severity:** Medium.
- **file:line:** bronze `Stint`, `TyreLife` and `Compound`, used verbatim by `int_stint_geometry.sql:36`
  (stint_id), `:43` (lap_in_stint), `:100` (`tyre_life AS age_in_stint`).
- **Observed behaviour** (`round2/r2_stint_boundary_vs_pits.py`/`.log`):
  - Every stint boundary was checked against `stg_pits`' in-laps, which round 1 matched 100% to Jolpica
    for 2019 and 2021–2025.
  - Three races are misaligned:
    - **2018_3 (China):** 26 boundaries have no stop; boundaries land 13–28 laps *after* the real stop.
      Ricciardo's lap-31 safety-car stop for new softs never appears: he runs "ULTRASOFT, age 38–49"
      through lap 47 at 96–98 s.
    - **2022_11 (Austria):** every driver's final stop is missed (19 stops with no boundary), and tyre age
      keeps counting through the new set.
    - **2025_6 (Miami):** laps 1–24 carry no stint, compound or age, then "stint 1" restarts at age 1 on
      lap 24/25, while the real stops fall on laps 19–36.
  - **660 eligible rows (317 with a 5-lap label) sit on a stint that contradicts the pit stops.** In
    addition, 2025_13 has 5 drivers with NULL age on laps 28–44.
  - `int_stint_end_regime`'s header says only 2018 has unassigned stints. 2025_6 adds 20 more
    `unassigned_stint` rows.
- **Why it is wrong:** tyre age is a contract feature and the stint-life target is stint length. Both are
  read from numbering that the pit stops falsify.
- **Verdict:** Definitely wrong (bronze).
- **Earliest point:** bronze (FastF1 TimingAppData). Stop there per the charter; the fix is detection in
  staging.
- **ML impact:**
  - `age_in_stint`, `lap_in_stint` and the `cliff_prior` block on those rows;
  - stint-life targets on merged stints;
  - the in-race compound seed cells for those three races (F2 fits them on these stints).
- **Fix:** rebuild stint boundaries from `stg_pits` (plus red-flag changes) and cross-check against
  bronze. Where they disagree beyond a tolerance, NULL the tyre columns for the race.
- **Test:** T19. It replaces `assert_stint_boundaries_correct`, which passes on all three (F34).
- **How I could be wrong:** drive-through penalties carry PitInTime without a tyre change. They inflate
  "pits without boundary" slightly. They do not explain boundaries with no pit, nor 13–28-lap offsets.

### F25 — 2018 rounds 1–17: stint 1 starts at lap 2 (bronze)

- **Severity:** Medium.
- **Observed behaviour** (`round2/r2_stint1_lap1_null_2018.py`):
  - In 17 of 21 races of 2018, lap 1 has a NULL `Stint`, so it becomes a pseudo-stint `…_DRV_`, since
    `CONCAT` skips NULL.
  - `lap_in_stint` at lap 2 is **1** there, against 2 in 2018 rounds 18–21 and in every later season.
  - Tyre age is also one lap low. Independent check: the Q2-tyre rule applies 2018–2021, so top-10
    starters' age at lap 2 is 3.89 in 2018 R1–17 vs 5.23 in 2018 R18–21 and 4.93 in 2019. Other starters
    show 1.12 vs 2.08 vs 2.15. The rule is identical across those seasons, and the offset is exactly −1 in
    both groups.
- **Blast radius:** 4,257 mart rows, **3,667 eligible (24.5% of 2018)**, 36 of them at the `age > 3`
  eligibility boundary. Both `lap_in_stint` and `age_in_stint` are contract features in all five families.
  The stint-life target is unaffected, since length and ordinal shift together.
- **Verdict:** Definitely wrong (bronze).
- **Fix:** assign lap 1 to the driver's first stint when it is the only unassigned lap. Offset TyreLife by
  +1 on those stints.
- **Test:** T20.
- **How I could be wrong:** if FastF1's TyreLife in those races already counted lap 1 and only `Stint` was
  missing, the age offset would be 0. The grid-group comparison says the offset is −1 in both groups.

### F26 — The rain flag contradicts the tyres the field ran (bronze)

- **Severity:** Medium.
- **Observed behaviour** (`round2/r2_rainfall_flag_vs_compound.py`):
  - The oracle is the compound actually run, `stg_laps.compound`.
  - **False positives:** 2019 Monaco has 83.5% of laps "raining" and 0.0% on inters/wets; 2018 Spain has
    82.5% and 0.0%. The track was 30–37 °C, and humidity while "raining" was 52% (genuinely wet races show
    83–90%).
  - **Unflagged wet races:** 2020 Turkey (100% inters/wets, 0% rain), 2021 Turkey (99.9%, 0%), 2022
    Singapore (62%, 0%), 2022 Imola (29%, 0%), 2025 Belgium (27%, 0%).
- **Consumers:**
  - `is_rain_lap` → `anomaly_class = 'conditions'` → training eligibility: **1,656 dry laps excluded**
    across 2018_5 and 2019_6;
  - the clean-panel filters of θ (F23) and constructor pace;
  - `race_wet_flag` (F27). The five unflagged races keep **2,529 eligible laps on inters/wets**.
- **Verdict:** Definitely wrong for the false positives. The unflagged races are *probably* wrong for this
  use: FastF1's Rainfall means "precipitation now", and a track stays wet after rain stops. The model uses
  the flag to mean wet conditions.
- **Fix:** derive wet conditions from tyre use (share of the field on inters/wets per lap), with Rainfall as
  secondary evidence.
- **Test:** T21.

### F27 — Wet-Race Specialist uses no wet laps

- **Severity:** Medium (fan-facing).
- **Observed behaviour** (`round2/r2_wet_race_specialist_dry_laps.py`):
  - `race_wet_flag = BOOL_OR(rainfall_flag)` (`fct_driver_skill_features.sql:99`). The skill proxy keeps
    only `is_rain_lap = FALSE` (`:140`).
  - Of 17 wet-flagged races, 8 had fewer than 10% rain laps. Rain laps reaching the page: **0**.
  - Two of the 17 "wet" races are the dry ones from F26, and both Turkish GPs count as dry races.
  - The methodology also says "relative to the field model" (it is relative to the teammate) and
    "2018–2024" (the data now runs to 2025). The k = 6 shrinkage it claims does exist (`transform.ts:21`).
- **Verdict:** Definitely wrong.
- **Fix:** compute the proxy on rain laps for the wet side; define "wet" per F26.

### F29 — Blind-Test Scoreboard compares different horizons

- **Severity:** Medium (fan-facing, model-trust page).
- **Observed behaviour** (`round2/r2_blind_test_horizon.py`, against the shipped
  `data/marts/mart_degradation_predictions.parquet`, v14):
  - The prediction is the p50 of the 5-lap cumulative detrended target. The page's "actual" is
    `next_lap_degradation_jump_s`: one lap, not detrended, ±10 s clip.
  - On 111,255 page rows the p10–p90 band covers **90.8%** of the page's actuals and **79.4%** of the
    trained target.
  - The actual's SD is 0.96 s against the target's 4.76 s. The scatter compares values whose spreads
    differ 5×.
- **Verdict:** Definitely wrong. **The page flatters the model.**
- **Fix:** actual = `next_5_lap_cumulative_jump_s`, taken from `S.DEGRADATION_TARGET` rather than
  hard-coded.
- **Test:** T22b.

### F31 — Pit-strategy verdicts lose stops taken after invalid laps

- **Severity:** Medium.
- **Observed behaviour** (`round2/r2_pit_strategy_unmatched_stops.py`):
  - `stint_end_lap` is the last *valid* lap (`:52-70`, `:293`), and a stop matches only up to
    `stint_end_lap + 1` (`:314-316`). Any SC/VSC/red run-in, or an invalid lap before the stop, puts the
    in-lap out of reach.
  - Pit-ended stints with `actual_pit_lap` NULL: green 105/4,061, **SC 191/644 (29.7%)**, VSC 38/230,
    **red 96/115 (83.5%)**. Each gets verdict NULL and `opportunity_cost_s = 0` (`:406-409`, `:437`), as if
    it never stopped.
  - In the app, `ORDER BY actual_pit_lap NULLS LAST` and `COALESCE(actual_pit_lap, total_laps)` re-order
    those stints and draw them to the flag, overdrawn by 28–36 laps on average.
- **Verdict:** Definitely wrong.
- **Fix:** match the stop on the stint's last lap of any validity, using `int_stint_end_regime.end_lap_number`.
- **Test:** T23.

### F34 — Tests that cannot fail

- **Severity:** Medium (process).
- **Evidence:** `round2/r2_vacuous_tests.py`/`.log`. These seven are counted in the PASS total.
  - **Placeholders** (`SELECT 1 WHERE FALSE`):
    - `assert_cliff_stints_have_falloff`
    - `assert_constructor_confidence_monotone`
    - `assert_sector_aggregates_to_lap`. Its header describes a real identity it never runs.
  - **Pass by construction:**
    - `assert_aero_penalty_negative` checks `tax < 0`, but the model clamps the tax at 0. A *negative* θ,
      exactly the "inverted" case the test names, zeroes every tax and the test still passes.
    - `assert_track_evolution_monotone`: the slope is `LEAST(…, 0)` (`int_track_evolution.sql:85`).
  - **Blind to their named defect:**
    - `assert_stint_boundaries_correct` ("laps assigned to wrong stint near pit stops") checks only that
      age rises. It passes on all three F24 races.
    - `assert_cliff_predictions_valid` ("seed failed to join") looks for exactly 0 or 0.5. The 1,492
      no-cell 2025 rows carry 0.050–0.060, the temperature term alone.
  - In addition, `assert_example_identity_closure` and `assert_residual_decomposition_identity` share
    round 1's tautology: the residual is defined as the remainder.
- **Fix:** T26, and wire `verify_findings.py` in as a non-blocking CI report.

### F30, F32, F33, F35, F36, F37 (lower severity; condensed)

**F30. Tyre-Cliff Survival validates the seed against itself**
- Observed (`round2/r2_tyre_cliff_km_circular.py`):
  - The KM event `cliffed = BOOL_OR(cliff_onset_passed)` equals `max age > seed onset` on **7,544/7,544**
    stints (0 mismatches). It is placed at stint *end*.
  - Against an observed >1 s detrended jump in the same stint, the page's event agrees on 55%. 2,538
    stints with an observed jump show "no cliff"; 785 show a cliff with none.
  - "Degradation" is the sum of the seed's expected rate. For 2018–2024 the onset is itself same-race
    (F2).
- Verdict: definitely wrong (the validation claim).
- Fix: event = the label's observed first crossing, placed at its lap.

**F32. Starting fuel above regulation**
- Observed (`round2/r2_fuel_over_regulatory_max.py`):
  - The initial load is laps × a hand-set per-slug rate with no constraint.
  - **134/171 races exceed** 105 kg (2018) / 110 kg (2019+). Median 117.8 kg; Hungary and Canada 126 kg;
    Sakhir 2020 **147.9 kg**, because 87 laps of the 3.5 km outer loop are charged at the full-layout rate.
- Verdict: definitely wrong.
- Impact: `fuel_component_s` magnitudes (the Waterfall's fuel bar) and cross-circuit scale of
  `fuel_mass_kg`. The label effect is largely absorbed by drift.
- Fix: rate = regulatory load / scheduled laps (pairs with F6's scheduled-laps column).
- Test: T24.

**F33. 2018 qualifying accuracy gate**
- Observed (`round2/r2_quali_2018_is_accurate.py`):
  - Accurate share of timed, non-pit quali laps: 2018 **0.736**; 2019–2025 0.996–1.000.
  - 2018_1 keeps 14 of 118 laps; 11 of 20 drivers have no valid lap.
  - 2018 training rows with NULL quali features: 8.0% vs ≤2.0%. The symptom was already in round 1's
    `feature_null_by_season.csv` without a cause.
- Verdict: definitely wrong as a gate: the lap times are real, only the sync flag is missing.
- Fix: drop `is_accurate` from the qualifying gate, or require it only where the season populates it.
- Test: T25.

**F35. Constructor interaction on top of a per-race level**
- `constructor_component_s = structural (this race's team median) + interaction (prior visits' shrunk
  deviation)` (`:223-225`).
- This race's circuit effect is already inside `structural`. The interaction explains almost none of this
  race's deviation (corr 0.086, slope 0.26) and shifts each team's residual level by a mean 0.078 s per
  driver-race (p90 0.21, max 0.54).
- It is **0 for all of 2018** (no prior visits), so it is season-shaped for cross-era pages.
- It cancels from the ML label, being constant within a stint.
- The Constructor×Circuit page averages the COALESCEd zeros (first visits, all of 2018) into its means.
- Verdict: probably wrong. The interaction was designed against a season-average level (its header),
  not a per-race one.

**F36. Waterfall "observed delta"**
- The pages add `track_unexplained_s`, but `pace_delta = explained + skill` exactly (7e-15).
- Error per lap: mean 0.228 s. Per driver-race: mean 0.019, max 1.357 (`round2/r2_waterfall_reconstruction.py`).
- The pages' comment "137,447 rows" is stale; the table has 160,207.

**F37. Home page**
- `total_circuits = COUNT(*) FROM dim_circuits` = 44. 36 slugs were raced, forming **32 venues**. The
  other 8 rows are events never held 2018–2025: Argentine, Danish, Greek, Indonesian, Luxembourg, South
  African, Thai and Vietnamese.
- `ml_models` counts `*_v1.onnx` files, stale v1 artefacts that happen to number 5, with `or 5` as the
  fallback. The v14 card itself records `beats_baseline_significant: false` for stint life.

---

## 3. Round-1 items this round settles

| Round-1 item | Was | Now |
| :-- | :-- | :-- |
| F1 reaches app skill surfaces | Assumed | **Verified** (`round2/r2_f1_reaches_app_skill.py`). 10,026 of 137,356 "clean" laps (7.3%) in `fct_driver_skill_features` are fabricated, touching 2,952 of 3,293 driver-races. Per driver-race mean shifts 0.17 s (max 3.7 s); Driver Consistency's stddev is inflated 0.13 s on average (max 3.1 s) |
| F1's reach beyond the label | — | **Verified** into θ_air (F23a). **Assumed** into `int_constructor_structural_pace`, whose team median uses the same COALESCE (`int_constructor_structural_pace.sql:92`); unmeasured |
| `stg_telemetry_position` session separation | Assumed | **Clean.** It reads `raw_telemetry` = `telemetry/*/*/*.parquet`; telemetry, race_control and circuit_info have no `session=` directories; `telemetry_full`/`pos_data` are empty |
| F12 | measured on `min_gap_s` | Also visible as `gap_ahead_*` NULL 9.7% (2018) vs 0% in the round-1 null table; on the board as F12 |
| 08q / 06b per-season θ | settled | **Reproduced exactly** on this build (`as_06b` arm), then shown to depend on F1 (F23) |

---

## 4. Verified / Assumed

**Verified** (script named per finding; each reproduces or rebuilds from production SQL):
- F22's identity (3e-14), the label and cliff rebuild (exact), and both shifts.
- F23: θ both ways; the 06b table and trend reproduced exactly, then re-fit; the 3,504 untaxed laps.
- F24's three races, the offsets and the 660/317 row counts. F25's offset and blast radius. F26 against
  compounds.
- F27–F31 against the page SQL and the shipped predictions parquet.
- F32–F37 counts. F34 by reading every flagged test and running two of them against their target
  defects.

**Assumed** (inferred, not run):
- That F22's fix leaves the trio's *ranking* of features roughly intact. Only the label was rebuilt; no
  model was retrained.
- The metric impact of F22, F23, F24, F25 and F26. Labels and populations were measured; no refit was run.
- That the ghost-car recombination is unaffected by F22 (host and ego share the lap's rubber and ambient,
  so the double term cancels). This is from the formula, not measured.
- That `int_qualifying_*` and sector identity tests share the tautology (headers read; not proven for
  qualifying).
- That the 2020 and 2021 Turkish GPs had no *falling* rain for most of the race. Only tyre use was checked.
- That F1 perturbs constructor structural pace materially (see §3).
- That the 8 never-raced `dim_circuits` rows feed nothing but the home count. Only the fuel join (INNER, via
  `race_to_track`) was checked.

---

## 5. Clean list (checked this round; no defect)

| Category | Evidence |
| :-- | :-- |
| 5-lap label never bridges a gap | `fct_cliff_prediction_features.sql` guard `LEAD(lap_in_stint,5) = lap_in_stint+5`; the rebuild reproduces the label exactly |
| Fuel component is *not* double-counted | `int_field_pace_curve` averages `weight_corrected_lap_time`, so `pace_delta_s` still contains the car's own fuel penalty |
| Validity inputs have no NULL route | `is_deleted`, `is_accurate` and `track_status` are 0% NULL every season (race and quali) |
| Session separation, all bronze sources | Only laps, weather, results, track_status and session_status have `session=Q`, each read only by a `*_qualifying` source |
| `int_event_corrections` precedence | Class and weight CASEs agree with the header; manual overrides win |
| Constructor interaction is point-in-time | Both windows `ROWS … 1 PRECEDING` (08f-2 holds) |
| Wet-Race shrinkage | `transform.ts:21` `SHRINK_K = 6` exists as the methodology says |
| `stg_pits` pairing | In-lap to out-lap LEAD with `+1` guard; used as the F24 oracle (100% Jolpica match, round 1) |
| App ghost/hidden-performance, race-control, field-pace, track-evolution, dirty-air-lap-map, driver-consistency, era pages | SQL read; no aggregation or grain defect beyond inherited upstream ones (F1, F22, F35) |

---

## 6. Guard coverage additions

| Guard | Does NOT reach (new this round) |
| :-- | :-- |
| `assert_lap_7term_identity` and the other identity tests | Whether a component is already inside the base (F22). Closure holds with the double subtraction |
| `audit_forward_window` / `audit_aggregation_scope` | Bronze semantic errors (F24–F26, F33); regression panels' populations (F23) |
| `assert_stint_boundaries_correct` | Stint numbering vs pit stops (F24) |
| `assert_cliff_predictions_valid` | Defaults that are not literally 0 or 0.5 (F7) |
| `assert_aero_penalty_negative` | A negative θ (clamped before the test sees it) |
| Every dbt test | App SQL (F27–F31, F36, F37) and export stats |
| `verify_findings.py` (new) | Only what is listed in it; a CLEARED line proves the named measurement, not the fix's correctness |

---

## 7. Recommended tests (tree style; continue round 1's T1–T15)

| ID | File | Checks | A failure means | Blocks |
| :-- | :-- | :-- | :-- | :-- |
| T16 | `transform/tests/assert_residual_components_not_in_base.sql` | For laps with an evolution row: if `base = race_mean + rubber + ambient + unexplained` within 1e-6, then the residual must not subtract rubber or ambient | A component removed twice (F22) | Yes |
| T17 | `transform/tests/assert_dirty_air_tax_covers_spine.sql` | Every spine lap with lagged share > 0 has a tax row (independent re-derivation of the lag, as in round-2 probe) | Tax applied only to the calibration panel (F23b) | Yes |
| T18 | `transform/tests/assert_theta_panel_has_measured_base.sql` | No calibration-panel lap lacks a field base | Fabricated laps in θ (F23a) | Yes |
| T19 | `transform/tests/assert_stint_boundaries_match_pits.sql` (replaces `assert_stint_boundaries_correct`) | Per race, stint boundaries without an in-lap or red flag ≤ 2 | Bronze stint numbering unusable (F24) | Warn + quarantine list |
| T20 | `transform/tests/assert_stint1_includes_lap1.sql` | Lap 1 belongs to the driver's first real stint | Stint-1 ordinals and ages offset (F25) | Yes |
| T21 | `transform/tests/assert_rain_flag_matches_tyres.sql` | Race rain share > 0.5 ⇒ inter/wet share > 0.05, and inter/wet share > 0.5 ⇒ a wet flag | Wet flag contradicts tyres (F26) | Warn |
| T22 | `app/src/features/*/…test.ts` + `ml/tests/test_app_query_contract.py` | (a) Quali-vs-Race: a driver faster in both sessions gets delta ≈ 0. (b) Blind-Test's actual column equals `S.DEGRADATION_TARGET`. (c) Tyre-Cliff's event is not a function of `cliff_onset_passed` | Page computes something other than it states (F28–F30) | Yes |
| T23 | `transform/tests/assert_pit_ended_stints_have_stop.sql` | Every `stint_end_cause LIKE '%pit'` or `'red'` stint has `actual_pit_lap` | Ungraded stops (F31) | Yes |
| T24 | `transform/tests/assert_fuel_within_regulation.sql` | Implied starting fuel ≤ regulatory max for the season | Fuel scale wrong (F32) | Yes |
| T25 | extend `snapshot_data_profile.py` | Per-season valid share of timed quali laps within tolerance of other seasons | A season-shaped gate (F33) | Yes after re-snapshot |
| T26 | `ml/tests/test_dbt_tests_can_fail.py` | No singular test body is `SELECT 1 WHERE FALSE`; tests on clamped columns read the pre-clamp expression | Vacuous guard (F34) | Yes |
| T27 | CI job running `verify_findings.py` | Prints the board; non-blocking | — | No |

---

## 8. Remediation, merged with round 1's plan

**Before training: one label version bump, not four.**
1. Round-1 F1 **together with F22, F23 (a+b) and F35**. All four change `driver_skill_residual_s`. F1's fix
   moves θ by itself (F23a), so landing them separately means three consecutive label moves and three
   fixed-target comparisons.
2. F24, F25, F26 and F33: a bronze tyre/stint/weather QA pass in staging, run before the seed is refitted
   (round-1 WI-2). F2's in-race fits consume the misaligned stints.
3. F32 alongside round-1 F6 (scheduled laps give both the lap count and a legal fuel rate).

**Before evaluation or publication**
1. **Re-run 06b's pre-registered ladder after F1 lands** (F23), and hold the 06b post until then. Its "no
   detectable cost from 2022" does not survive.
2. F29: fix the Blind-Test actual before the page is used as evidence of model quality.

**Fan surfaces (no model number moves; highest fan value per the 2026-09-20 win definition)**
1. F28, F27, F30 and F29: each page states something its SQL does not compute.
2. F31 (pit strategy), F36 and F37.

**Post-build monitoring**
1. F34, T26 and T27. Round 1's F11 (the red drift gates) still applies.

---

## 9. Proposed work items (for the user to place; not written to `build-log.json`)

| ID (proposed) | Title | Suggested group | Stage | Blocker |
| :-- | :-- | :-- | :-- | :-- |
| WI-1 (extend) | Label spine: F1 + **F22 + F23 + F35** in one version bump; T1, T2, T16–T18 | 08 foundations | SPEC | None; blocks v15 |
| WI-10 | Bronze tyre/stint/weather QA: pit-derived stints, lap-1 assignment, tyre-derived wet flag, quali accuracy gate (F24, F25, F26, F33; T19–T21, T25) | 12 season coverage (or 08) | SPEC | None; should precede WI-2's refit |
| WI-11 | Fan-page truth pass: Quali vs Race, Wet-Race, Blind-Test, Tyre-Cliff, Waterfall, home stats (F27–F30, F36, F37; T22) | 06 publication | SPEC | None; Wet-Race waits on WI-10's wet flag |
| WI-12 | 06b re-measure after F1 (F23a): re-run the pre-registered ladder, re-rule the placebo, rewrite the claim | 06 publication | SPEC | WI-1 |
| WI-13 | Pit-strategy stop matching (F31, T23) | 07 causal pit timing | SPEC | None |
| WI-7 (extend) | Guard repairs: + F34, T26, T27 | 09 scoring instruments | SPEC | None |
| WI-5 (extend) | Season onboarding: + F32 legal fuel from scheduled laps | 12 season coverage | SPEC | None |

---

## Artefact index

In `transform_forensic_audit_artefacts/`:
- `verify_findings.py`: status board for F1–F37 (round 1 and round 2).
- `round2/_db.py`: shared read-only connection (repo-relative; `OTP_DB` overrides).
- One probe per finding in `round2/`, each with its `.log`:

| Finding | Probe |
| :-- | :-- |
| F22 | `r2_rubber_ambient_double_count` |
| F23 | `r2_dirty_air_tax_population`, `r2_06b_theta_refit` (needs `pyfixest`; run with `.venv/bin/python`) |
| F24 | `r2_stint_boundary_vs_pits` |
| F25 | `r2_stint1_lap1_null_2018` |
| F26 | `r2_rainfall_flag_vs_compound` |
| F27 | `r2_wet_race_specialist_dry_laps` |
| F28 | `r2_quali_vs_race_sign` |
| F29 | `r2_blind_test_horizon` |
| F30 | `r2_tyre_cliff_km_circular` |
| F31 | `r2_pit_strategy_unmatched_stops` |
| F32 | `r2_fuel_over_regulatory_max` |
| F33 | `r2_quali_2018_is_accurate` |
| F34 | `r2_vacuous_tests` |
| F36 | `r2_waterfall_reconstruction` |
| Round-1 F1 → app | `r2_f1_reaches_app_skill` |
