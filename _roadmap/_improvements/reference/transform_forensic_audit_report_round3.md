# Forensic audit of the transform layer — round 3

**Run:** 2026-09-24, against `data/dev.duckdb` (the same v14 build as rounds 1 and 2). Every probe opens it
`read_only=True` through `round2/_db.py`. Charter: [`transform_forensic_audit.md`](transform_forensic_audit.md).
Earlier rounds: [round 1](transform_forensic_audit_report.md) (F1–F21) and
[round 2](transform_forensic_audit_report_round2.md) (F22–F37).

**What round 3 covered that rounds 1 and 2 did not:**
- what the field base actually contains, component by component (round 2 did rubber and ambient; this round does compound);
- proximity and air-state internals: pit-lane cars, DRS coding, the two races with no telemetry;
- thermal proxy semantics, compound seed fitter internals and the constant terms of the compound curve;
- anomaly flags against round 1's F1, and the driver-rating chain behind five fan pages;
- ghost car and ghost race; the ML evaluation and browser AFT path; app data plumbing; seeds; bronze consistency.

Finding IDs continue from round 2: **F38–F49**.

**How to verify while building.** The status board now covers all three rounds (51 checks, about 1 s):

```
.venv/bin/python _improvements/reference/transform_forensic_audit_artefacts/verify_findings.py            # all
.venv/bin/python _improvements/reference/transform_forensic_audit_artefacts/verify_findings.py F38 F40 F44
```

Today it prints **51 present / 51 checked**, with no ERROR. The round-3 probes are in `round3/r3_*.py`, and each
has a `.log` next to it. Every probe that runs a counterfactual first rebuilds the model from the compiled
production SQL in `transform/target/compiled/` and prints the reproduction error; the others read the built
tables and the page SQL directly.

---

## 1. Verdict

**Still not safe to retrain on, and the label bump gets bigger.** Round 3 found one more defect in the label
that is larger than any found before, and a group of fan-page defects in the driver-rating chain:

- **F38.** The field base the residual is measured against removes fuel but not tyre state. The residual
  subtracts each lap's own absolute compound cost, so it carries **minus the field's average compound cost**:
  2.29 s on average, moving 0.35 s over a typical 5-lap window. Measured against a compound-neutral base, the
  training label moves by a mean **1.12 s** (72% of rows by more than 250 ms), and **10.5%** of cliff labels
  change class. In windows where the field pits, the as-built label shows a spurious **+3.15 s** "degradation
  jump". This is also why the app's skill numbers put 99% of driver-races "faster than the field".
- **F40, F44, F45.** The equal-car rating compares a driver's 20th-percentile lap with his teammate's
  *median* lap. Teammates are therefore rated faster than each other in **79%** of two-driver cars. On the
  Driver Circuit Affinity page every one of 667 cells is green. The era offset reverses the between-era gap it
  claims to remove.

**Sequencing consequences (new):**
- F38 belongs in the same label version bump as F1, F22, F23 and F35. It should be designed **with** F22,
  because both come from one question: what the base already contains.
- θ_air has to be re-estimated after F48 as well as after F1. 06b's re-measure (proposed WI-12) waits for both.
- The seed refit in WI-2 needs F41 fixed first. Otherwise the new seed still cannot say which of its parameters
  were measured.

---

## 2. Findings, ranked (severity × blast radius)

| # | Sev | Where | What | Verdict | Headline number |
| :-- | :-- | :-- | :-- | :-- | :-- |
| F38 | **High** | `int_field_pace_curve.sql:43-103`; `int_lap_residual_decomposed.sql:199,300,311` | Base is fuel-neutral, not compound-neutral; residual carries −(field compound cost) | Definitely wrong | Label moves by a mean **1.12 s**; **10.5%** of cliff classes flip; residual level **−1.96 s** |
| F40 | Medium (fan) | `int_driver_race_skill_loro.sql:151-154,184-192,218` | Rating = own P20 − teammate **median**: a spread term plus a teammate term | Definitely wrong | **1,252 of 1,579** car-pairs (79%) both "faster than each other"; pair sum **−1.83 s** |
| F44 | Medium (fan) | `app/.../driver-circuit-affinity/queries.ts:28-37`, `page.tsx:27,60`, `methodology.tsx:7,14` | Draws the absolute rating as "vs the driver's own average" | Definitely wrong | **667 of 667** cells green (47.8% would be) |
| F41 | Med-Low | `fit_compound_cliff.py:250-258,293-316`; `survival.py:262-320` | (a) "Fitted" seed cells silently hold class defaults; (b) wear gradient fitted with the fuel burn left in | Definitely wrong (a), probably wrong (b) | (a) **124/337** cells, **35,377** training rows (30%); (b) gradient **+23%** when fuel-corrected |
| F48 | Low-Med | `int_lap_air_state.sql:110,116-125,144-152` | S2 gap < 1 s with DRS → `drs_train` → dirty-air share 0; a 1.0–1.5 s gap → 1 | Probably wrong | **45%** of sub-1 s S2 laps coded clean; θ **0.152 → 0.257** as built, **0.416 → 0.443** on measured laps |
| F43 | Low-Med | `int_lap_proximity.sql:65-155`; `stg_telemetry_position.sql:20-25` | A car in the pit lane counts as "the car ahead" | Definitely wrong | `gap_ahead_min_s` wrong on **6,355** training rows (4.5%); median 0.88 s vs **3.32 s** on track |
| F47 | Low-Med | `int_lap_thermal_proxy.sql:46-49,87-106` | Push residual built on raw lap time, so fuel burn reads as pushing | Probably wrong (feature meaning) | Laps 21+ of a stint: **67.7%** "pushing" as built vs **30.8%** fuel-corrected |
| F39 | Low-Med | `int_compound_cliff_predicted.sql:155-161,194-202` (DuckDB `LEAST` skips NULL) | NULL tyre age becomes the 10 s wear cap | Definitely wrong | **383** spine laps with residual −10 to −13 s; 2025 Miami app skill **−5.90 vs −2.10 s** |
| F45 | Low-Med (fan) | `int_era_normalized_driver_rating.sql:46-151` | Bridge-driver offset on a teammate-relative rating; t = −1.5; reverses the era gap | Probably wrong | Field-mean gap (pre − post) **−0.044 → +0.071 s** |
| F42 | Low | `int_compound_cliff_predicted.sql:108-116,194,202` | (a) Unitless `grip_peak` added as seconds, softer tyre charged more; (b) temperature term compares track surface with tyre carcass temperature | Definitely wrong | (a) +0.95–1.09 s on every lap; (b) term is 0 on **150,976 of 150,976** slick laps with a seed cell |
| F46 | Low (fan) | `hidden-performance/methodology.tsx:10,21`; `fct_ghost_race_finish.sql:167-169,230-233` | States a self-scenario identity that fails; published rank ignores the declared ranking key | Definitely wrong | Identity fails on **93.4%** of self rows; **1,299** page rows move ≥3 places |
| F49 | Low (fan) | `int_tyre_surface_vs_bulk_decoupling.sql:85-90,118-119`; `tyre-recovery-forecast/methodology.tsx:12,19` | Surface ≤ bulk by construction, so "surface-driven" can never occur; page quotes 86–89% recovery | Definitely wrong | Max ratio **0.50** vs 0.65 threshold; recovery **57.7–62.7%** |

---

### F38 — The field base removes fuel but not tyre state

- **Severity:** High. It is in the label of four of the five model families, it is larger than F22, and it
  sets the level of every residual-based app surface.
- **file:line:**
  - Base: `int_field_pace_curve.sql:43-62` (eligible laps), `:77-89` (10–90% trimmed mean of
    `weight_corrected_lap_time`), `:91-103` (±2-lap smoothing). `weight_corrected_lap_time` is lap time minus the
    car's own fuel penalty (`int_lap_fuel_state.sql:94-96`). It still contains every eligible car's tyre state.
  - Residual: `int_lap_residual_decomposed.sql:199` (`compound_component_s = expected_compound_pace_s`, an
    **absolute** per-lap cost), `:294` (`pace_delta_s = lap − base`), `:300` and `:311` (compound subtracted).
- **Column / transformation:** `driver_skill_residual_s` → `next_5_lap_cumulative_jump_s`,
  `laps_until_cliff_class`, and every consumer of the residual.
- **Intended grain:** valid race lap. The base is (race, lap_number).
- **Observed behaviour** (`round3/r3_compound_in_field_base.py`/`.log`):
  - The production base was rebuilt from compiled SQL while carrying each eligible car's own
    `expected_compound_pace_s` through the same eligibility, the same trim and the same smoothing. The rebuild
    matches the table to **2.8e-14**.
  - By linearity, base = compound-neutral base + **field_cc** exactly. field_cc averages **2.292 s**
    (SD 1.082), moves a mean **0.348 s** across a 5-lap window (p90 0.72 s, max 8.3 s), and drops sharply when
    the field pits onto fresh tyres.
  - Fuel is handled consistently: the base holds no fuel, and the residual subtracts the lap's own absolute fuel.
    Compound is not: the base holds the field's compound cost, and the residual subtracts the lap's own absolute
    compound cost. So residual = (terms measured against a neutral base) **− field_cc(race, lap)**.
  - **Level:** the mean residual on laps with a measured base is **−1.957 s** as built, against **+0.338 s**
    (arm A) or **+0.331 s** (arm B) against a neutral base. The component means close it:
    pace_delta 1.845 − fuel 1.498 − compound 2.295 ≈ −1.96.
  - **Label**, rebuilt exactly as the mart builds it (reproduction **8.9e-15** on the label and **0**
    mismatches on the cliff class; per-stint drift re-fitted in each arm):

    | Arm | Mean \|Δ label\| | Median | p90 | Share > 250 ms | Corr with built | Cliff classes flipped |
    | :-- | --: | --: | --: | --: | --: | --: |
    | A: add field_cc back on the production trim set | 1.137 s | 0.573 | 2.737 | 72.3% | 0.925 | 14,278 / 132,265 (10.8%) |
    | B: base rebuilt from compound-corrected laps (re-ranked, re-trimmed; how fuel is handled) | 1.121 s | 0.549 | 2.699 | 71.8% | 0.925 | 13,920 / 132,265 (10.5%) |

    Label SD is 4.15 s. Every season moves by a mean 0.90–1.46 s.
  - **Where the shift sits:** in the 2,743 labelled windows where the field's compound cost falls by more than
    0.5 s (a pit cycle), the built label is **3.15 s higher** than the neutral one. The as-built label records the
    field's pit stop as the driver's tyre degradation.
  - **App:** in `fct_lap_residuals` the Lap Waterfall's compound bar averages **2.30 s** and its skill bar
    **−2.14 s**. 94.5% of laps and **99%** of driver-races in `fct_driver_skill_features` show negative
    ("faster than the field") skill.
- **Reproducible query:** `r3_compound_in_field_base.py`. Board check F38: the mean residual on measured laps
  (−1.957).
- **Why it is wrong:** the base and the components must share one reference. For fuel they do; for compound they
  do not. The header identity (`:9-18`) reads the residual as "pace minus physics". In fact it is "pace minus
  physics minus the field's tyre state". This is the same defect class as F22, found by the same method, but
  for a component round 2 did not examine. Round 2's clean line ("fuel is not double-counted") checked fuel only.
- **Verdict:** Definitely wrong. The inconsistency is exact under the tree's own compound estimate, and the
  magnitude is measured two independent ways that agree.
- **Earliest point:** `int_field_pace_curve`, whose input carries the compound cost, combined with
  `int_lap_residual_decomposed`.
- **Isolated or systematic:** systematic. Every lap of every race, and concentrated at pit cycles.
- **ML impact:** the trio and cliff targets (stint life is unaffected). The as-built label contains a
  common-mode term that no feature can see: the field's pit cycle.
- **Fix:** build the base from fuel- **and** compound-corrected laps (arm B, the exact analogue of fuel), or
  subtract own-minus-field compound cost. Decide it together with F22 (rubber and ambient) in one design of
  "what the base contains". It changes the label, so it ships in the same version bump as F1, F22, F23 and F35.
- **Test:** T28.
- **How I could be wrong:**
  1. The neutral base removes the tree's **estimate** of the field's compound cost. That estimate has its own
     problems (F2 same-race fit, F41 silent defaults, F42 unitless grip). If the estimate were pure noise, adding
     it back would inject noise rather than remove a real term. But the as-built residual already subtracts the
     same estimate for the lap itself, and consistency requires the same estimate on both sides.
  2. The authors may want the residual to be relative to the field's tyre state ("pace against a field on these
     tyres"). Then the component subtracted should be own-minus-field, not own-absolute. The current mix matches
     neither reading.
  3. Arm A keeps the production trim set, while arm B re-ranks on corrected laps. They agree to within 0.02 s, so
     the trim choice does not drive the result.

### F40 — The equal-car rating compares a ceiling with a median

- **Severity:** Medium (fan). It feeds Era Translator, Era Ratings Timeline, Hidden Performance's season rating
  and Driver Circuit Affinity.
- **file:line:** `int_driver_race_skill_loro.sql:151-154` (each driver's median and P20 pace delta), `:184-192`
  (car baseline = mean of the other drivers' **medians**), `:218`
  (`driver_skill_loro_s = P20(own) − baseline`). Consumers: `int_driver_season_ratings.sql:28`,
  `int_driver_circuit_affinity.sql:55`.
- **Observed behaviour** (`round3/r3_loro_rating_asymmetry.py`; the rebuild matches the table to 0.0):
  - The rating splits exactly into a **spread term**, P20(own) − median(own), with mean **−0.916 s** and SD 0.51,
    plus a **teammate term**, median(own) − median(teammate), with mean 0.000 and SD 0.795. The entire −0.92 s
    level is spread. The rating correlates 0.43 with the spread term, so a driver whose laps scatter more is rated
    faster.
  - A teammate-relative rating must sum to about 0 across a pair. Here the mean pair sum is **−1.831 s**, and in
    **1,252 of 1,579** two-driver cars both teammates are rated faster than each other.
  - **100%** of the 163 driver-seasons on the Era Translator are negative. The pages say "negative = faster than
    the (era-normalised) field average" (`era-translator/methodology.tsx:13`,
    `era-ratings-timeline/methodology.tsx:8`).
  - Against the symmetric ceiling the header's own intent implies (own P20 − teammates' P20): season rankings
    agree at Spearman **0.891**, and **48 of 163** driver-seasons move by 3 or more places. 2025's agreement is
    0.795.
- **Why it is wrong:** the header (`:13-17`) says the ceiling is used to kill cruise drag. The ceiling is then
  compared with the teammate's *typical* lap, so the statistic mixes location with dispersion.
- **Verdict:** Definitely wrong. The pair-sum property fails 79% of the time, and the decomposition is exact.
- **ML impact:** none (barred by 00c). Fan surfaces only.
- **Fix:** compare like with like: P20 vs the teammates' P20, or median vs median. Then re-check the "field
  average" wording on every page that shows it.
- **Test:** T30.
- **How I could be wrong:** the asymmetry could be deliberate ("the driver's best against the car's typical").
  Even so, no page says that, and the level makes the pages' sign text false for every row.

### F44 — Driver Circuit Affinity paints every cell green

- **Severity:** Medium (fan). The whole heatmap's colour signal is inverted into a constant.
- **file:line:** `int_driver_circuit_affinity.sql:65-76,107-113` (the circuit mean is shrunk toward the driver's
  own mean, so `shrunk_affinity_s` is a **level**) and its header `:21-22`; the page reads it raw
  (`driver-circuit-affinity/queries.ts:28-37`) and colours it on a zero-centred diverging scale
  (`transform.ts:52`, `ui/charts/Heatmap.tsx:89-95`, `page.tsx:27`). The claims are at `methodology.tsx:7`
  ("relative to their own season-average pace"), `:14` ("negative = faster than driver average at that circuit")
  and `page.tsx:60` ("Green = faster than the driver's own global average").
- **Observed behaviour** (`round3/r3_circuit_affinity_page.py`): **667 of 667** page cells (n_obs ≥ 2) are
  negative, so all 32 drivers' rows are fully green. Relative to each driver's own mean, 47.8% would be green, and
  only 1 of 32 rows would be all green. The page also says "shrunk toward neutral" (`:13`); it is shrunk toward
  the driver's mean. It says "All seasons 2018–2024" (`:26`); the data runs to 2025.
- **Verdict:** Definitely wrong.
- **Fix:** draw `shrunk_affinity_s − global_driver_mean_s` (expose the prior mean from the model), or change the
  text and scale.
- **Test:** T34.
- **How I could be wrong:** once F40 is fixed the level offset shrinks, but the page would still draw a level as a
  deviation, so a driver who beats his teammates everywhere stays all green.

### F41 — Compound seed fitter internals

- **Severity:** Medium-Low. It is a provenance defect in the feature seed that F2 and WI-2 depend on.
- **(a) Silent class defaults.** `fit_compound_cliff.py:250-258` sets `source = "cox_km_survival"` once a group
  has ≥ 8 stints. `:293-302` then replaces any parameter that came back None or out of range with
  `COMPOUND_DEFAULTS` (`:57-71`), without changing `fit_source` or `notes` (`:316`: "fitted from N stints via
  cox_km_survival"). None comes back when KM never crosses 0.5 and ≤ 3 stints cliffed (`survival.py:184-190`),
  when no slope is positive with R² > 0.1 (`:311-316`), or when no cliff has 2 pre and 2 post laps (`:228-229`).
  - Measured (`round3/r3_seed_fitter_internals.py`): **124 of 337** "fitted" cells hold at least one class
    default (onset 70, gradient 77, severity 19). The modal "fitted" onsets are exactly the defaults: MEDIUM
    **33.0** (26 cells; the next most common value has 7), SOFT **22.0** (19), HARD **50.0** (12).
  - **35,377 of 116,385** training-eligible rows on those cells (30.4%) carry a defaulted parameter: onset 15,256,
    gradient 25,217, severity 4,136. `compound_cliff_onset_laps` and the cliff-prior block cannot tell them apart
    from measured values (§5.8's pattern).
- **(b) Fuel left in the wear gradient.** `load_stint_data` (`:130`) feeds `normalized_pace_s`
  (= lap − θ·time in dirty air, `int_lap_normalized_pace.sql`) into `estimate_wear_gradient`
  (`survival.py:262-320`). That pace still contains the fuel burn, about 0.05 s/lap faster every lap (mean fuel
  gain 0.0508 s/lap). The estimator also keeps only positive slopes. The decomposition subtracts fuel separately,
  so the gradient is (wear − fuel gain) on a truncated sample.
  - Re-run with the production estimator, the seed's own onset per cell, and fuel-corrected pace: median
    gradient **0.0640 → 0.0773**, a median ratio of **1.23**; 226 of 337 cells rise.
  - The docstring (`survival.py:274-275`) says it "uses uncensored stints only". The code uses every fresh-tyre
    stint. `estimate_cliff_severity`'s docstring (`:205-206`) likewise claims forced stops; the code uses detected
    cliffs only.
  - The seed was fitted on 2026-09-08 (c7de693). Today's warehouse reproduces **107 of 337** cells exactly and
    agrees in mean (0.0780 vs 0.0783), so the ratio is quoted against both.
- **Verdict:** (a) Definitely wrong (provenance). (b) Probably wrong: the positive-slope truncation means the fuel
  correction does not shift the mean by the full 0.05 s, and the "right" gradient needs a decision on that filter
  too.
- **ML impact:** (a) about 30% of training rows have seed parameters that carry no same-race information,
  which bounds F2's leakage for those parameters. It does not change F2's measured magnitude. (b) The wear term
  under-removes wear. In the label the linear part is absorbed by drift; in the app's compound bar and
  `expected_degradation_rate` it shows directly.
- **Fix:** record provenance **per parameter** (`onset_source`, `gradient_source`, `severity_source`), and fit the
  gradient on fuel-corrected pace. Both must land **before** WI-2's point-in-time refit.
- **Test:** T31.
- **How I could be wrong:** a fitted value can coincide with a default. That cannot explain 26 MEDIUM cells at
  exactly 33.0 when the next most common value has 7.

### F48 — The closest followers are coded "no dirty air"

- **Severity:** Low-Medium. It affects a contract feature and the treatment variable of θ_air, which sits in the
  label.
- **file:line:** `int_lap_air_state.sql:110` (`drs_active` = MAX over the sector's samples), `:116-125` (S2: gap
  < 1.0 s with DRS → `drs_train`; 1.0–1.5 s → `dirty_air`), `:144-152` (`dirty_air_share_lap` = 1 only for
  `dirty_air`). Treatment: `int_dirty_air_tax_component.sql:101-109` (lag 1) and `:195-206` (θ).
- **Observed behaviour** (`round3/r3_dirty_air_drs_train.py`; the rebuild matches the table exactly):
  - Of 25,927 training-eligible laps with an S2 median gap under 1 s, **11,657 (45%)** are coded `drs_train` and
    get share 0. All 16,303 laps at 1.0–1.5 s get share 1. The feature is not monotone in the gap.
  - θ with S2 < 1 s coded as dirty air: **0.152123 → 0.257401** on the as-built panel, and **0.415821 →
    0.443167** on the measured-laps panel (round 2's F23a fix). Both baselines reproduce the shipped and round-2
    values exactly.
- **Why it is wrong:** a car 0.4 s behind through S2 is deeper in the wake than one 1.3 s behind. DRS opening on
  the S2 straight does not take the car out of the wake through S2's corners, because the classification uses
  the whole third.
- **Verdict:** Probably wrong. The coding is traced and measured. Whether DRS laps carry less aero loss is a
  physics question the tree does not settle.
- **ML impact:** `dirty_air_share_lap` changes on 11,657 training rows. After F1 is fixed, θ (and therefore every
  dirty-air lap's label) moves by a further +6.6%.
- **Fix:** base dirty-air exposure on the gap alone, keep DRS as a separate column, and re-estimate θ in the same
  pass as F1 and F23.
- **Test:** T38.
- **How I could be wrong:** if DRS-open S2 laps really lose little aero load, the coding is a defensible choice.
  It still needs saying, because the label prices it.

### F43 — A car in the pit lane counts as "the car ahead"

- **Severity:** Low-Medium. `gap_ahead_min_s` is a contract feature in all five families.
- **file:line:** `int_lap_proximity.sql:65-99` (one crossing per driver, lap and 1% bin) and `:122-155` (every
  crossing of a bin ordered by session clock; the previous one is "ahead"). Nothing removes pit-lane crossings.
  `stg_telemetry_position.sql:20-25` keeps pit-lane samples so that proximity can "exclude them downstream with a
  reason rather than silently". No such exclusion exists.
- **Observed behaviour** (`round3/r3_proximity_pitlane_car_ahead.py`; the rebuild matches all 189,418 rows):
  - The oracle is `stg_pits.pit_in_time_s` / `pit_out_time_s`, which run on the same session clock. 45,329
    crossings fall inside a pit window, and **7,466** "within 1 s" crossings have a pit-lane car as the car
    ahead.
  - On training-eligible rows, `gap_ahead_min_s` changes on **6,355 (4.5%)**: a median of **0.88 s** as built
    against **3.32 s** on track (median shift +1.76 s, p90 +8.3 s). **2,932** rows cross the 1 s threshold. The
    share features move little (mean |Δ| 0.0003).
- **Verdict:** Definitely wrong.
- **Fix:** drop crossings made between a car's pit-in and pit-out time before the ordering step.
- **Test:** T33.
- **How I could be wrong:** pit-lane geometry differs by circuit. At a few tracks the pit entry is on the racing
  line for a few bins, so a strict pit-window cut drops some real proximity. That is a small fraction of 4.5%.

### F47 — The push proxy reads fuel burn as pushing

- **Severity:** Low-Medium. It is about the feature's meaning. The trees also hold `lap_in_stint` and
  `fuel_mass_kg`.
- **file:line:** `int_lap_thermal_proxy.sql:46-49` (raw `stg_laps.lap_time_s`), `:87-99` (expanding median of
  earlier valid laps in the stint), `:106` (`push_residual = baseline − lap`), `:118-150` (loads accumulate the
  positive part). Header `:22-23`: "faster than the stint baseline = pushing harder".
- **Observed behaviour** (`round3/r3_push_residual_fuel.py`; the rebuild matches exactly). This is the
  production SQL re-run on `weight_corrected_lap_time`:

  | lap_in_stint | Mean push, built | Mean push, fuel-corrected | Share "pushing", built | Fuel-corrected | Bulk load built → corrected |
  | :-- | --: | --: | --: | --: | --: |
  | 1–5 | 0.543 | 0.462 | 61.7% | 55.5% | 1.69 → 1.60 |
  | 11–20 | 0.153 | −0.162 | 58.8% | 35.1% | 1.60 → 1.06 |
  | 21+ | 0.265 | −0.378 | **67.7%** | **30.8%** | **2.17 → 0.80** |

  Late in a stint, about 63% of the bulk load is fuel burn.
- **Verdict:** Probably wrong. The feature does not measure what its header says. The ML effect is unmeasured.
- **Fix:** use `weight_corrected_lap_time`, as `int_field_pace_curve` does. Re-run the thermal ablation (08e/08i)
  on the corrected feature.
- **Test:** T37.
- **How I could be wrong:** F32 says the per-slug fuel rate is about 10–15% high, so the correction slightly
  over-corrects. At 85% of the correction, laps 21+ still average about −0.28 s, so the conclusion holds.

### F39 — A NULL tyre age becomes 10 seconds of wear

- **Severity:** Low-Medium. No training rows are affected; app surfaces are.
- **file:line:** `int_compound_cliff_predicted.sql:155-161` (`compound_wear_s`) and `:194-202`
  (`expected_compound_pace_s`) evaluate `LEAST(COALESCE(wear_gradient,0) * age_in_stint + …, 10.0)`. With
  `age_in_stint` NULL the first argument is NULL, and **DuckDB's `LEAST` skips NULL arguments**, so the result is
  the 10 s cap. `int_lap_thermal_proxy.sql:114-117` already documents the same DuckDB behaviour for `GREATEST`
  and guards against it.
- **Observed behaviour** (`round3/r3_null_age_wear_cap.py`): **383** spine laps have NULL tyre age, and all 383
  carry `compound_wear_s = 10.0`. Their compound component is 10.0–11.0 s and their residual −10.2 to −13.3 s,
  against −1.5 to −4.3 s for the rest of the race. The laps are 2025_6 (306; round 2 F24's Miami laps 1–24),
  2025_13 (70), 2025_1 (2) and five single laps in 2018. None is training-eligible (age > 3 fails). In the app's
  `fct_driver_skill_features`, the 15 affected Miami 2025 driver-races average **−5.90 s** against −2.10 s for
  the rest of the field; Belgium 2025 shows −5.76 vs −3.11.
- **Latent sibling (checked, not firing):** the label clips (`fct_cliff_prediction_features.sql:634-704`) use
  `GREATEST(LEAST(x, 50), −50)`. A NULL `x` would become **+50**. Today no residual is NULL and drift is
  COALESCEd, so 0 rows are affected (§5).
- **Verdict:** Definitely wrong.
- **Fix:** `CASE WHEN age_in_stint IS NULL THEN NULL ELSE LEAST(…) END`, applied in the macro. Add a lint for
  `LEAST`/`GREATEST` over nullable expressions.
- **Test:** T29.
- **How I could be wrong:** it could only matter less if these laps were filtered from every app surface. They
  are not.

### F45 — The era offset reverses the gap it removes

- **Severity:** Low-Medium (fan).
- **file:line:** `int_era_normalized_driver_rating.sql:46-73` (bridge drivers, ≥ 8 races each side), `:76-122`
  (mean of each bridge driver's pre-minus-post shrunk rating), `:144-151` (subtracted from every pre-2022
  driver-season whenever n ≥ 3; there is no significance or robustness check). Claims:
  `era-translator/methodology.tsx:6-8` ("Ratings from 2018 are directly comparable to ratings from 2024") and
  `era-ratings-timeline/methodology.tsx:18-22`.
- **Observed behaviour** (`round3/r3_era_offset.py`):
  - The offset is **−0.1153 s**, with SE 0.077 (t = −1.5). The median bridge shift is −0.040. Leave-one-out
    runs from −0.149 to −0.072. The most influential driver is MSC, whose shift of −0.941 s reflects a change of
    teammate (Mazepin, then Magnussen), not a change of era.
  - The rating is teammate-relative (F40), and a car era moves both teammates alike. The field-mean rating shows
    no step at 2022: before adjustment pre − post = **−0.044 s**, after it **+0.071 s**. The adjustment turns a
    small gap into a larger one of the opposite sign.
  - The pages also say "≥8 clean-race **seasons**"; the code counts races.
- **Verdict:** Probably wrong. The "true" era shift of a teammate-relative metric is not identified in-tree, but
  the applied value is outside both natural references (0, and the field-mean gap).
- **Fix:** drop the offset for a teammate-relative rating, or estimate the era level from field means with an
  uncertainty that gates its use.
- **Test:** T35.
- **How I could be wrong:** P20-minus-median dispersion (F40) could change with the regulations, giving the metric
  a real era level. The field means would show that. They do not.

### F42 — Two constant terms of the compound curve

- **Severity:** Low. Both terms are constant within a stint and cancel from the label. They matter for levels and
  pairwise comparisons.
- **(a) Grip.** `int_compound_cliff_predicted.sql:194` adds `compound_grip_peak` to a pace in seconds. It is a
  hand-set, unitless ratio: WET 0.95, HARD 0.97, INTER 0.98, MEDIUM 1.00, SOFT 1.03, SUPERSOFT 1.05, ULTRASOFT
  1.07, HYPERSOFT 1.09 (`fit_compound_cliff.py:57-71`; one value per compound in all 510 cells, never fitted).
  - Every lap is therefore charged +0.95 to +1.09 s (32–56% of `compound_component_s`), and the **softer, faster
    tyre is charged more**.
  - In `int_synthetic_teammate`, 42,596 of 139,772 pair-laps are cross-compound. The adjustment is
    `tm + (ego_cc − tm_cc)`, so in 21,086 of them the ego on the softer tyre has his teammate made slower by the
    grip gap (mean |term| 0.032 s): the tyre advantage is credited to the driver, not removed.
- **(b) Temperature.** `:108-116`: `ambient_temp_delta = clamp(track_temp_c − compound_optimal_temp_low, 0, 30)`.
  Track surface temperature runs 13.8–57.5 °C; the slick operating floor is 76–82 °C. The term is **0 on 150,976
  of 150,976** slick laps with a seed cell. It fires on 100% of the 1,492 no-cell slick laps (the NULL floor
  COALESCEs to 20 °C: round 2 F34's "0.050–0.060") and on 91% of inter/wet laps. 08l recorded this term as "≈0"
  without the cause.
- **Probe:** `round3/r3_compound_constant_terms.py`.
- **Verdict:** Definitely wrong (units).
- **Fix:** drop grip from the pace sum, or replace it with a fitted per-compound offset in seconds with the right
  sign. Compare temperature on one scale, or drop the term.
- **Test:** T32.
- **How I could be wrong:** a within-race constant cannot move the ML label. The defect is in levels and in the
  synthetic-teammate adjustment only.

### F46 — Hidden Performance: a false identity, and a rank key nobody validates

- **Severity:** Low (fan).
- **(a)** `hidden-performance/methodology.tsx:21`: "when the host constructor equals the driver's own team,
  predicted finish equals actual finish, any deviation … signals a data issue". A scenario puts **every** driver
  in the host car (`fct_ghost_race_finish.sql:230-233` ranks the whole scenario). In the self scenario the ego
  keeps his pace while the other 19 are transplanted, so the result is an equal-car rank.
  - Measured (`round3/r3_hidden_performance_claims.py`): the identity fails on **93.4%** of the 2,921 self rows
    the page shows. The mean |delta| is 5.53 places, and 2,071 rows are 3 or more places off.
  - `:10` says "re-ranked by predicted cumulative race time"; the mart ranks by mean lap (`:5-9`).
- **(b)** `predicted_finish_position` ranks on `predicted_mean_lap_s`, which includes fuel.
  `fct_ghost_car_pace.sql:335-352` builds a fuel-adjusted twin "so ranking by pace isn't biased by which lap
  window (heavy vs. light fuel) a driver happened to run". `fct_ghost_race_finish.sql:167-169` calls that twin
  "the ranking key", and `assert_ghost_self_scenario_rank` validates it. The published rank uses neither.
  - 16,832 of 32,075 scenario rows differ, 2,934 by 3 or more places, **1,299** of them on the page.
  - Both keys correlate about equally with official results in the self scenario (Spearman 0.865 vs 0.861), so
    the test would pass either way.
- **Verdict:** Definitely wrong (text and key).
- **Fix:** rank on the declared key, and rewrite the identity sentence (the identity that holds is per-lap pace).
- **Test:** T36.

### F49 — "Surface-driven" can never happen

- **Severity:** Low (fan).
- **file:line:** `int_tyre_surface_vs_bulk_decoupling.sql:85-90`: ratio = surface / (surface + bulk). Both loads
  sum the same positive push residuals (`int_lap_thermal_proxy.sql:122-142`). Every surface weight (1, .717,
  .514, .369, .264) is ≤ the bulk weight at the same lag (1, .819, .670, .549, .449), and bulk has three more lags.
  So surface ≤ bulk and the ratio is ≤ 0.5. `surface_driven` needs > 0.65 (`:118`).
- **Observed behaviour** (`round3/r3_surface_bulk_ratio_bound.py`): surface exceeds bulk on 0 of 164,030 laps. The
  classes are `bulk_driven` 11,617 and `mixed` 30,142, with no `surface_driven`. The contract feature #19 is also
  capped at 0.5. The Tyre Recovery page (`methodology.tsx:12,19`) describes a surface-driven regime and a
  recovery rate of "~86–89%"; its own query returns **57.7–62.7%**.
- **Verdict:** Definitely wrong.
- **Fix:** normalise each load by its weight sum before comparing (the ratio then reads 0.5 at steady push), or
  drop the class. Refresh the text.
- **Test:** T39.

---

## 3. Round-1 and round-2 items this round settles

| Item | Was | Now (evidence in `round3/r3_settles_assumed.py` unless named) |
| :-- | :-- | :-- |
| R1 Assumed: "F1 perturbs `anomaly_class` and therefore eligibility" | Assumed | **Verified, small.** With F1's fabricated residuals NULL, 1,465 laps change class (mistake→normal 1,026; clean_cliff→normal 230; normal→mistake 203). **943** rows (0.67% of eligible) flip eligibility: 697 of them on laps with a measured base whose MAD window held a fabricated neighbour, and 558 of those with a label |
| R2 Assumed: "ghost recombination unaffected by F22" | Assumed | **Verified**, and stronger: predicted = actual + (host − ego constructor) + deg/cliff interactions to **5.7e-14** on 1,501,422 laps. F1, F22 and F35's level terms all cancel. The corollary is that the ghost's "physics recombination" is decorative: only the constructor difference and the two interactions carry information |
| R2 Assumed: "F1 perturbs constructor structural pace materially" | Assumed | **Verified, modest.** Excluding fabricated laps moves `constructor_structural_pace_s` by a mean **0.071 s** (p90 0.147, max 1.90) over 1,656 team-races. It is a per-race constant, so it cancels from the ML label and moves app levels only |
| R2 Assumed: "the 8 never-raced `dim_circuits` rows feed nothing but the home count" | Assumed | **Refuted.** The Degradation Simulator's circuit picker (`degradation-simulator/queries.ts:140-151`) groups `dim_circuits` by venue and offers **7** never-raced venues (Fangio, Buriram, Hanoi, Hellenic, Jyllandsringen, Kyalami, Pertamina) among its 39. Extends F37 |
| R1 Assumed: "shrinkage floors bind for reserve drivers (§5.2)" | Assumed | **Verified with a caveat.** Season ratings shrink toward the season mean: drivers with fewer than 5 races are pulled a mean 0.39 s (confidence 0.25). Circuit affinity shrinks toward the **driver's own** mean, so a reserve's level is never pulled toward the field (F44) |
| Brief: telemetry has 171 race files vs 173 races | Open | **2018_1 and 2018_2** have no telemetry file. Their 1,450 eligible rows (9.7% of 2018) are all `free_air` with zero proximity and NULL gaps. This is round 1 F12's entire population (board: 0.0968) |
| Brief: 2018 has 0 deleted laps | Open | **Real in source.** Race control carries 0 lap-deletion messages in 2018, against 15/15 in 2019 and 221 vs 220 in 2020 (§5) |
| R2 F23a θ on measured laps | 0.416 | **0.443** once F48's coding is also fixed |

---

## 4. Verified / Assumed

**Verified** (each reproduces a production table first, then measures):
- F38: the base rebuild (2.8e-14); the field_cc identity; label and cliff reproduction (8.9e-15 / 0), then two
  counterfactual arms that agree.
- F39: DuckDB's `LEAST` NULL behaviour; the 383 laps; the app-table shift.
- F40: rebuild (0.0); the exact two-term split; the pair sums; the symmetric comparison.
- F41: (a) 124 cells and 35,377 rows from the seed and `COMPOUND_DEFAULTS`; (b) the production estimator re-run
  both ways.
- F42: seed constants, weather range, the temperature term's firing pattern, and the synthetic-teammate
  cross-compound counts.
- F43: rebuild (all 189,418 rows); pit windows from `stg_pits`.
- F44–F46 and F49 against the page SQL and the table values. F47 and F48: rebuilds exact, counterfactuals re-run
  through compiled production SQL.
- Everything in §3 and §6.

**Assumed** (inferred, not run):
- That F38's neutral base is closer to truth than the as-built one. It relies on the tree's own compound estimate,
  which F2, F41 and F42 show is flawed. The *inconsistency* is exact; the *correct* level is not.
- Published-metric impact of F38, F43, F47 and F48. Labels and features were measured; no model was retrained.
- That DRS-open S2 laps carry real aero loss (F48's physical premise). No telemetry-based aero measure exists
  in-tree.
- That F39 also corrupts `int_synthetic_teammate` for the 2025_6 pairs (±10 s adjustments). This follows from the
  formula at `int_synthetic_teammate.sql` (`ego_cc − tm_cc`) and was not measured.
- That the teammate-relative rating has no genuine era level (F45). Only field means were used as the reference.
- That 2018's zero deleted laps reflect race practice rather than a race-control feed gap. Race control agrees,
  but no FIA document was checked.
- `tyre_allocations.csv` correctness. It is user-attested and there is no in-tree oracle for C-codes, so it was
  not checked.
- That the production CDN serves the same app code, so F44, F46 and F49 are visible in production.
- That the fuel-model slope error (F32) is small enough not to reverse F47's conclusion. It was bounded at 85% of
  the correction, not measured.

---

## 5. Clean list (checked this round; no defect)

| Category | Evidence |
| :-- | :-- |
| Bronze lap time equals the sector sum | 17 of 182,780 laps with all three sectors differ by > 10 ms (1 by > 1 s, 2018); `select season, count(*) filter (where abs(s1+s2+s3-laptime)/1e9 > 0.01) from bronze laps` |
| Bronze `LapStartTime` ordering and lap contiguity | 0 decreasing start times and 0 lap-number gaps per driver-race, all seasons. The count of NULL `Position` equals the count of FastF1-generated laps in every season (28–52) |
| 2018 has 0 `Deleted` laps | Race-control "DELETED" messages by season: 0, 15, 221, 186, 256, 422, 345, 324 vs bronze deleted laps 0, 15, 220, 183, 254, 394, 326, 299. `Deleted` is 0% NULL |
| `race_to_track` slugs vs bronze event slugs | 171/172 identical; the only miss is 2018_14 (F8). Renamed venues collapse correctly (Red Bull Ring, Silverstone, Interlagos, Rodríguez, Spa) |
| Baseline cells in `evaluate.py` | `_cell_lookup` keys on the mart's `circuit_key`, which is the track slug (36 keys over 171 races), so baseline cells match across seasons |
| Browser AFT post-transform vs `predict.py` | `lapsFromMargin` = exp(raw + margin_offset + scale·Φ⁻¹(q)) − shift, clipped ≥ 0 (`app/src/ml/survival.ts`); `survival.laps_from_margin` is the same, and the offset and scale come from the manifest. The only difference: the browser also clamps the trio at the manifest's ±50 bounds, which `predict.py` does not (F3 blocks the browser anyway) |
| App season partitions | Every page that registers a season partition uses a season-suffixed view name (`fct_lap_residuals_${season}`, etc.), and the sector page uses a race-suffixed alias, so no stale partition is reused across seasons. No page reads a table the export omits |
| `mart_degradation_history_envelope` join | `CAST(REPLACE(race_id,'_','') AS INTEGER) = race_to_track.race_id` joins 171/171 spine races |
| Label clips with NULL inputs (latent F39 sibling) | 0 NULL residuals and 0 NULL component columns in `int_lap_residual_decomposed`; drift COALESCEd (`fct_cliff_prediction_features.sql:535`). Exactly-at-bound labels: +50: 1, −50: 19, all from non-NULL inputs |
| `lap_length_km` across layout changes | Read by no model or page (one Query Lab example only), so round 1 F6's caveat is moot today |
| Ghost race actual finish | From `stg_results` classified position; the lap fallback fires only when no result row exists |
| Stint-life target and censoring | `remaining = stint_length_laps − lap_in_stint` over the geometry that includes the in-lap; censoring from `is_censored_stint` (`features.py:146-166`); AFT bounds [y+1, ∞) for censored rows (`survival.py:32-47`) |

---

## 6. Guard coverage additions

| Guard | Does NOT reach (new this round) |
| :-- | :-- |
| `assert_lap_7term_identity` and the other identity tests | What the base contains (F38). The identity closes with −field_cc inside the residual |
| `assert_ghost_self_scenario_rank` | The published `predicted_finish_position`. It validates the fuel-adjusted twin (F46) |
| `assert_proximity_crossing_total_order` | Whether the "car ahead" is on track (F43); it proves determinism, not membership |
| `assert_no_future_leakage` | What push_residual measures (F47); it proves timing only |
| Shrinkage bound tests (`_shrinkage_lower/upper_bound`) | Whether the prior is the right one (F44: own-mean prior on a level) |
| `assert_cliff_seed_severity_bounded`, `check_freshness.py` | Per-parameter provenance of seed cells (F41a) |
| Range and null checks in `data-profile-check` | Cap-valued fabrications. A NULL age produces a *valid-looking* 10.0 (F39) |
| No test anywhere | Monotonicity of `dirty_air_share_lap` in gap (F48); reachability of classes (F49); antisymmetry of teammate ratings (F40) |
| `verify_findings.py` | F41b, F43, F46 (part), F47 and F48 are **text** checks: a change that moves the defect elsewhere would read CLEARED. Re-run the named probe to confirm a fix |

---

## 7. Recommended tests (tree style; continue from T27)

| ID | File | Checks | A failure means | Blocks |
| :-- | :-- | :-- | :-- | :-- |
| T28 | `transform/tests/assert_field_base_component_neutral.sql` | Independent re-derivation: the trimmed field mean of each component the residual subtracts (compound, fuel, rubber, ambient, dirty air) over the base's own eligible set is ~0, or the residual subtracts own-minus-field for that component | A component is inside the base and subtracted as absolute (F38, F22) | Yes |
| T29 | `transform/tests/assert_no_cap_valued_wear.sql` + `ml/tests/test_sql_least_greatest_nullable.py` | No lap with NULL `age_in_stint` has non-NULL `compound_wear_s`; a lint flags `LEAST`/`GREATEST` over a nullable arithmetic expression in model SQL, including the label clips | A NULL becomes a bound (F39) | Yes |
| T30 | `transform/tests/assert_teammate_rating_antisymmetric.sql` | For two-driver cars, \|mean pair sum\| of `driver_skill_loro_s` < 0.1 s | The rating mixes statistics (F40) | Yes |
| T31 | `transform/tasks/coefficients/tests/test_seed_param_provenance.py` | Every seed parameter carries its own source; no "fitted" parameter equals the class default unless its source says default; the wear-gradient pace column is fuel-corrected | Silent defaults or fuel in the gradient (F41) | Yes, once the columns exist |
| T32 | `transform/tests/assert_compound_pace_units.sql` | `expected_compound_pace_s − compound_wear_s − temperature term` = 0 (no unitless constant); the temperature term is non-zero on > 5% of slick laps with a cell, or is removed | Unit errors (F42) | Yes |
| T33 | `transform/tests/assert_proximity_excludes_pit_lane.sql` | No lap's car-ahead crossing lies inside that car's `stg_pits` pit window (join on session time) | Pit-lane cars as traffic (F43) | Yes |
| T34 | `app/src/features/driver-circuit-affinity/transform.test.ts` + era pages | Drawn values are deviations (about half negative on the fixture); sign text matches the data's share | Page draws a level as a deviation (F44, F40) | Yes |
| T35 | `transform/tests/assert_era_offset_shrinks_gap.sql` | After adjustment, \|field-mean gap across the boundary\| ≤ before, and the offset's \|t\| ≥ 2 or it is 0 | Offset reverses or invents an era gap (F45) | Warn |
| T36 | `transform/tests/assert_ghost_rank_uses_declared_key.sql` + methodology lint | `predicted_finish_position` = RANK over `predicted_mean_residual_pace_s`; no page states the self-scenario identity | Published rank not the validated one (F46) | Yes |
| T37 | `transform/tests/assert_push_residual_fuel_neutral.sql` | Mean `push_residual` by `lap_in_stint` bucket does not trend with the fuel-burn slope (\|slope\| < 0.01 s/lap) | Fuel read as push (F47) | Warn |
| T38 | `transform/tests/assert_dirty_air_share_monotone.sql` | Over S2 median-gap bins, the share of laps coded dirty air is non-increasing in gap | Closest followers coded clean (F48) | Yes |
| T39 | `transform/tests/assert_categorical_classes_reachable.sql` | Every class a model's CASE can emit is emitted on the build, or is declared unreachable | Dead categories (F49) | Warn |

---

## 8. Remediation, merged with rounds 1 and 2

**Before training: one label version bump, now larger.**
1. F1 + F22 + F23 (a and b) + F35 + **F38**, with **F42a** (the grip constant sits in the same compound term) and
   **F48** (θ's treatment). Design F22 and F38 together: decide what the base contains, then subtract only what it
   does not. Re-estimate θ once, after F1 and F48.
2. **F39**: NULL-safe wear term. Independent of the bump, but it lands in the same model.
3. Bronze QA (WI-10: F24, F25, F26, F33) before any seed refit, as before.
4. **F41 before WI-2's refit**: per-parameter provenance and a fuel-corrected gradient. Without it T3 cannot be met
   honestly, because a lagged fit that falls back to a default would still read "fitted".

**Feature semantics (need a contract ablation per gates.md, not a label bump):**
1. F43 (pit-lane crossings), F47 (fuel-neutral push), F48 (the feature side of the DRS coding).

**Before evaluation or publication:**
1. 06b re-measure (WI-12) waits for **F1 and F48**: θ on measured laps moves 0.416 → 0.443.
2. Any v15 headline must be compared at fixed target against a v14 rebuilt on the new label, not against v14's
   published numbers. F38 alone moves 72% of labels by more than 250 ms.

**Fan surfaces (no model number moves; highest fan value per the 2026-09-20 win definition):**
1. Rating chain: F40 → F44 → F45, in that order, since each consumes the one before.
2. F46 (Hidden Performance text and rank key), F49 (Tyre Recovery), F37's extension (simulator picker).

**Post-build monitoring:**
1. T29's lint, and T39 across all CASE-built categoricals. Wire `verify_findings.py` into CI (round 2 T27).

---

## 9. Proposed work items (for the user to place; not written to `build-log.json`)

| ID (proposed) | Title | Suggested group | Stage | Blocker |
| :-- | :-- | :-- | :-- | :-- |
| WI-1 (extend) | Label spine: + **F38** (compound-neutral base, designed with F22), + F42a, + F48 in θ; T28, T32, T38 | 08 foundations | SPEC | Ruling: what the base contains (one decision covers F22 and F38) |
| WI-2 (extend) | Seed point-in-time: prerequisite **F41** (per-parameter provenance, fuel-corrected gradient); T31 | 08 foundations | SPEC | Existing human ruling; F41 first |
| WI-14 | Rating-chain truth pass: symmetric teammate statistic, affinity drawn as a deviation, era-offset rule (F40, F44, F45; T30, T34, T35) | 06 publication | SPEC | Ruling: P20-vs-P20 or median-vs-median |
| WI-15 | Traffic and thermal feature semantics: pit-lane exclusion, DRS-train coding, fuel-neutral push (F43, F47, F48 feature side; T33, T37) | 02 feature expansion | SPEC | Contract ablation per gates.md; F48's θ part rides WI-1 |
| WI-16 | NULL-safe bounds: `LEAST`/`GREATEST` audit and macro fix (F39; T29) | 08 foundations (low) | OPEN | None |
| WI-11 (extend) | Fan-page truth pass: + F46, F49, and the simulator picker's never-raced venues (F37 extension); T36, T39 | 06 publication | SPEC | None |
| WI-12 (extend) | 06b re-measure after F1 **and F48** | 06 publication | SPEC | WI-1 |

---

## 10. Artefact index

In `transform_forensic_audit_artefacts/`:
- `verify_findings.py`: the status board, now F1–F49 (51 checks). Round-3 checks are appended after F37. Fixed a
  docstring slip: it said round 2 ran to F38; round 2 ended at F37. No existing check was changed.
- `round3/` has one probe per finding, each with its `.log`. All exit 0 from a clean run with
  `.venv/bin/python` (F41's needs `lifelines`/`scipy`, which `.venv` has).

| Finding | Probe |
| :-- | :-- |
| F38 | `r3_compound_in_field_base` |
| F39 | `r3_null_age_wear_cap` |
| F40 | `r3_loro_rating_asymmetry` |
| F41 | `r3_seed_fitter_internals` |
| F42 | `r3_compound_constant_terms` |
| F43 | `r3_proximity_pitlane_car_ahead` |
| F44 | `r3_circuit_affinity_page` |
| F45 | `r3_era_offset` |
| F46 | `r3_hidden_performance_claims` |
| F47 | `r3_push_residual_fuel` |
| F48 | `r3_dirty_air_drs_train` |
| F49 | `r3_surface_bulk_ratio_bound` |
| §3 (settles R1/R2 Assumed items; F12's population; F37 extension) | `r3_settles_assumed` |
