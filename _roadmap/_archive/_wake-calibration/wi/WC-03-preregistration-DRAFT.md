# WC-03 pre-registration: measured traffic cost against the flat penalty

**Status: SIGNED 2026-10-28.**
First draft 2026-10-27. Revised 2026-10-28 after the paper review (`_evidence/WC-03-2026-10-27/PAPER-REVIEW.md`; change log in `REVISION-LOG.md` beside it). Finalised for signature 2026-10-28 with the owner's decisions on the benchmark and on choices C1-C14 and N1-N5 (`FINALISE-LOG.md` beside it).

Nothing has been fitted on the pass table for this document. No curve, contest loss, coefficient on the pass table, verdict or gate result has been computed or looked at. No number from the archived dirty-air method (DA-03) is used. `data/ci.duckdb` was not touched. `data/bronze` was only read, never written: one bronze lap file was opened read-only to confirm the `race_id` format, and on 2026-10-28 the 1,214 bronze input files were hashed read-only (SHA-256 of file bytes, contents not inspected) for the proposed G3 check 4 (§12a). `data/dev.duckdb` was only byte-copied into a scratch folder; nothing was written to it. Two things *have* been seen and are declared in section 2e: the 2026-10-21 same-lap scoping result, and the 2026-10-28 read-only rerun of the reference fit that produced 0.331.

**Benchmark (owner decision, 2026-10-28).** The flat penalty under test is the shipped 0.331 s per lap, exactly as shipped. The reference fit no longer returns 0.331 on today's data; its 2026-10-28 rerun (0.305) is reported as a diagnostic only and is not the benchmark (§2e). Before any fit or score, G3 (section 12a) checks that the input data has not changed since 2026-10-28, using three checks (the scratch `dev.duckdb` hash, the panel row count, the pooled-slope fingerprint) plus a fourth (a hash of the bronze input files), signed off by the owner on 2026-10-28; if any check that is part of the registration fails, there is no verdict and the owner is told.

Sources read: the WC-02 evidence folder (`_evidence/WC-02-2026-10-27/`), the WC-01 evidence (PROVENANCE.txt, count files), work items WC-01 to WC-05 and WC-09, the design note, the build order rules, the paper review, the code that defines the flat penalty (`transform/models/intermediate/int_dirty_air_tax_component.sql`, `int_lap_air_state.sql`), the WI-12 panel and fit scripts (`_roadmap/_fixes/_evidence/wi-12-2026-09-27/d1_build_panels_wi12.py`, `d2_fit_wi12.py`, `d2_output.txt`), `_roadmap/_fixes/THETA_AIR_LABEL_VALUE_PROCEDURE.md`, the theta notes in `transform/dbt_project.yml`, and the WC-01 builder's column list (`transform/tasks/wake_calibration/build_pass_table.py`).

This document covers the fit (WC-03) and the held-out verdict (WC-04). It fixes every threshold those two items use.

---

## Changes since the first draft (2026-10-27)

1. **Flat-now comparator added** (§2d, §8b, §9 W1). The measured cost must beat both the shipped flat penalty and the flat penalty recalculated on the same lap's traffic. The sentence saying the contest "slightly favours the flat penalty" is corrected (§2e, §14).
2. **Prior knowledge declared** (§2e): the 2026-10-21 scoping (same-lap fits better, 0.473 vs 0.331; continuous same-lap share 0.881).
3. **Yardstick rerun done and recorded** (§2e, §12a G3): the reference fit returns **0.305**, not 0.331, on today's data. The owner kept the shipped 0.331 as the benchmark; 0.305 is a diagnostic only, and G3 now checks that the input data has not changed since 2026-10-28 (three checks, plus a fourth on the bronze input files, signed off 2026-10-28).
4. **Panel built from a scratch copy, written to scratch only** (§2d): `d1_build_panels_wi12.py` itself is not run.
5. **Unknown laps stay unknown** (§2d, §8a): no lap's missing traffic state is filled with 0.
6. **Trains check rewritten** (§8d, §9 W2, §14): states that a whole stint in traffic is invisible to the contest; W2 is scored on train laps and also reported on mixed stints; about a third of recent stints have no clean comparison.
7. **No car ahead** gets its own named reason, `no_car_ahead`, with a count (§4b, §6, §8a).
8. **Trim order made non-circular** (§8a).
9. **Lap totals derived from existing columns** (`seg_start_t`, `seg_end_t`), so no apex position column is needed (§7). Brake-offset sign corrected.
10. **Held-up and dirty-air classes** now cover every pass exactly once (§5).
11. **Join key stated** (§2f).
12. **Verdict scope** (§9): the verdict covers 2022-2025 only; 2018-2021 has its own curve and never decides the verdict. "No verdict" and "cannot be replace" made consistent.
13. **P1 tightened** (§10): a negative far band no longer passes automatically.
14. **Pit-stop ceiling is a reported figure, not pass/fail** (§11, §15).
15. **Bootstrap method, minimum races, fixed resample count, no reruns** (§0, §8c).
16. **The agent's fourteen choices** (C1-C14) and five new ones from this revision (N1-N5) are listed in §17a, confirmed by the owner on 2026-10-28; N1 is set to the refit option.
17. **Finalised for signature, 2026-10-28** (§0, §2e, §12a, §12b, §17): benchmark kept at the shipped 0.331; G3 rewritten as a data-unchanged gate run before any scoring (three checks); 0.305 recorded as a diagnostic only; choices confirmed; two cross-references corrected (`FINALISE-LOG.md`). Afterwards, the same day, G3 check 4 (bronze input files: 1,214 files, one combined SHA-256) was added as a pre-result amendment and signed off by the owner (`AMENDMENT-G3-bronze-hash.md` beside it).

---

## 0. The rule this document exists for

**Every threshold, margin, season split, definition and decision rule below is fixed now, before any loss value is seen. None of them may be changed after any result has been seen.** A change after a result can only be made as a written amendment that is labelled post-hoc, is committed separately, and cannot change the verdict this document produces. If a rule here turns out to be unworkable before any result is seen (for example, a column does not exist), the fix is a pre-result amendment, committed and hashed before the run.

**One run, no reruns.**
- Plain English: the real-data run happens once. If it crashes before printing any result, it may be restarted with the same code, data, seed and resample count; that is not a rerun because nothing was seen. Once any result has been printed, it is never run again. If a bug is found after a result has been printed, the verdict is "no verdict", the flat penalty stays, and any new attempt needs a new registration.
- Formal: a run is "completed" once any file under the WC-03 or WC-04 evidence folder contains a score, interval, curve value or gate result. After that, `n_runs = 1` is final. Every start is logged in PROVENANCE.txt with its reason and the time it ended.

### The fixed numbers in one place

| What | Fixed value |
|---|---|
| Flat penalty being tested against (the benchmark) | the shipped value: 0.331 s per lap × the previous lap's dirty-air share (`dirty_air_tax_s`), clamped 0-5 s; unknown stays unknown |
| Flat-now comparator | θ_now × the lap's own dirty-air share (`dirty_air_share_lap`), clamped 0-5 s; θ_now fitted on 2022-2024 only (§2d), refitted in every bootstrap draw (§8c) |
| Data-unchanged gate (G3), before any fit or score | scratch `dev.duckdb` SHA-256 `7173444b0745130769863c123fb5c04c7e5edd8be7a1fb2dbf614637d3214f9f`; panel rows 135,841; pooled-slope fingerprint 0.4777453471 (±1e-9); **[PRE-RESULT AMENDMENT, signed 2026-10-28] bronze input files: 1,214 files, combined SHA-256 `aed1c27da1cc00fb80eea470bb0c5c4879ee09556c81ff35bc17ad4aff1690b4`**; else no verdict and the owner is told (§12a) |
| Main fit seasons | 2022, 2023, 2024 (68 races) |
| Held-out season (the verdict) | 2025 (24 races) |
| Older-car check | its own curve, fit 2018-2020 (55 races), score 2021 (22 races); reported, never decides the verdict |
| Margin to win (W1) | mean squared error at least **0.5 % lower** than the flat penalty's **and** than flat-now's, each judged on the lower end of the 95 % interval |
| No worse in trains (W2) | on train laps: improvement over the flat penalty, point estimate ≥ 0 and lower end of the 95 % interval ≥ **-0.5 %** |
| Near-zero band check (P1) | |mean loss 2-3 s| ≤ **25 %** of mean loss 0.5-1.0 s, near band > 0, and the near band clearly above the far band (lower end of the interval of near − far > 0), every corner class |
| Fast versus slow check (P2) | dirty-air loss at 0.5-1.0 s: fast minus slow must not have its whole 95 % interval below zero |
| Chance | race-level (cluster) bootstrap, **1,000 draws, fixed**, seed 20261027, 95 % percentile intervals, no reruns |
| Bootstrap minimum races | ≥ 60 of 68 fit races contribute fit passes; ≥ 20 of 24 held-out races contribute scored laps |
| Pit-stop figure minimum | 200 distinct pit stops after all drops, else "not testable" |
| Contest minimums | ≥ 1,000 laps and ≥ 18 races in each of: the whole 2025 field, the clean-reference half, the train laps |
| Gap bins (s), each [lower, upper) | 0-0.3, 0.3-0.5, 0.5-0.75, 0.75-1.0, 1.0-1.5, 1.5-2.0, 2.0-2.5, 2.5-3.0 |
| Outlier trims (both fixed numbers, set before any fit) | corner loss beyond ±2 s left out of the curve fit; lap residual from the no-traffic baseline beyond ±5 s left out of the contest |

---

## 1. The question and the decision it feeds

**Question.** Is there a real, measurable traffic cost that depends on the gap to the car ahead and on the type of corner, and does it explain lap times on a season it never saw better than the flat penalty does, including when the flat penalty is given the same-lap timing the measured cost has?

**Decision (owner-approved, unchanged).** Replace the flat traffic penalty (`theta_air_label_value`), keep it, or keep it and show the measured figure beside it. The rule is in section 9. If the measured cost does not win, the flat penalty stays and the work stops: the product items (WC-05, WC-06, WC-08) do not start.

---

## 2. Data inputs (exact)

### 2a. The corner pass table (WC-01)

- Built by the WC-01 builder (`transform/tasks/wake_calibration/build_pass_table.py`) as committed in 97e0760, seasons 2018-2025, on a scratch folder, never on the warehouse.
- 2,927,753 rows; 169 races built; 4 skipped (2018 Australia and Bahrain: no car data; 2020 Sakhir and Tuscany: no corner positions). 2,188,484 kept passes, of which 1,071,162 have a measured own reference and 1,117,322 have none.
- The scratch build that WC-02 read has these fingerprints (from `_evidence/WC-02-2026-10-27/PROVENANCE.txt`): 2018 `d343a5be…`, 2019 `ad97ce5a…`, 2020 `abb44da2…`, 2021 `1c9e2f52…`, 2022 `58c87498…`, 2023 `94c1f79a…`, 2024 `572d587b…`, 2025 `bd4c2e4a…`, races list `de680b39…`. The scratch folder is temporary, so the run rebuilds the table from the committed builder and must reproduce the WC-01 count files byte for byte (G2). The run records the new file fingerprints.
- Columns used: `season`, `race_id`, `driver`, `lap`, `stint`, `compound`, `corner_id`, `corner_number`, `corner_class` (slow under 120 km/h, medium, fast 200 km/h and over), `segment_basis` (`brake_onset` or `fixed_before_apex`), `seg_offset_m`, `seg_start_t`, `seg_end_t`, `seg_time_s`, `min_speed_kph`, `leader`, `leader_lap`, `gap_s`, `clear_ahead`, `behind_1s`, `tag`, `reason`, `clean`, `ref_n`, `ref_time_s`, `ref_status`, `delta_time_s`, `layout_changed`. All exist in the builder's `PASS_COLUMNS`. No builder column is added or changed.

### 2b. The timing check outcome (WC-02, salvaged)

- Gaps are measured with each timing line placed **by the car's position on the track** (salvage methods C2 and C3; C3 is how the pass table itself measures gaps). On that basis the gap agrees with the official timing to within 0.1 s in **168 of 169 races**. Typical error is about 0.045 s per race (about 0.05 s since 2022).
- **2024 Las Vegas is flagged as failing** (0.101 s and 0.116 s). The fault is most likely in that race's own feed sector clock times, not in the car data. It stays in.
- **All 34 races flagged by the first timing check stay in**, as the owner ruled: 2018 Azerbaijan, China, United States; 2019 Azerbaijan, China, Germany, Mexico, Russia, United States; 2020 Austria, Hungary; 2021 Azerbaijan, Belgium; 2022 Azerbaijan, Belgium, Japan, Singapore, United States; 2023 Azerbaijan, Belgium, Netherlands, Las Vegas, United States; 2024 Azerbaijan, China, Las Vegas; 2025 Azerbaijan, Bahrain, Belgium, Britain, China, Las Vegas, Saudi Arabia, United States.
- **Stated risk:** one race (2024 Las Vegas, in the main fit) with an inconsistent timing feed; about 0.05 s of gap noise everywhere, which smears gaps closer than about 0.2-0.3 s so the closest end of the curve will read flatter than it really is; 2021 Belgium agrees on only 45 pairs; 2018 Azerbaijan and 2023 Las Vegas pass close to the line; in some races (for example 2023 Netherlands) lap start times sit about 2 s from the sector clock, so a pass near the start/finish line could carry the wrong lap number.

### 2c. The car-ahead-pits events (WC-02)

The 1,124 figure is retired (RECONCILE-1124.md). WC-02's own list (2,551 candidates, 1,970 where the follower stays out, 1,669 distinct stops among them) is **not** used as it stands. The pit-stop figure rebuilds its events from the pass table under the definition in section 11.

### 2d. The flat penalty, flat-now and the yardstick (scratch copy of the warehouse only)

**Where the data comes from.**
- Plain English: every warehouse read in WC-03 and WC-04 is made on a copy of `data/dev.duckdb` in its own scratch folder, with the copy named `dev.duckdb` (the staging views need that name). Everything produced is written into scratch. Nothing reads the warehouse file itself and nothing writes into a committed folder except the final evidence.
- Formal: the copy's SHA-256 is recorded in PROVENANCE.txt before any read. The yardstick panel is built by a **new wrapper script** that takes the scratch `dev.duckdb` path as a required argument, opens it `read_only=True`, asserts the path is not `data/dev.duckdb`, imports `WI01_PANEL_SQL` from `d1_build_panels_wi12.py` (the SQL only), changes directory to `transform/` for the views' relative parquet paths, and writes its output only into the scratch folder. **`d1_build_panels_wi12.py` itself is not run**: it hard-codes `data/dev.duckdb`, writes `panel_wi12_lap_wi01.parquet` into the committed WI-12 evidence folder, and reads a second warehouse for an arm this work does not use. The wrapper does not build the `as06b` arms or the corner panel.

**Flat penalty (the shipped one).**
- Plain English: today's charge, exactly as shipped: 0.331 s times the previous lap's dirty-air share. Where the shipped model leaves it unknown, it stays unknown and the lap is not scored.
- Formal: `x_flat = dirty_air_tax_s` from `int_dirty_air_tax_component`, joined on `lap_id`. It equals `0.331 × dirty_air_intensity_lag1`, clamped 0-5 s. Where `dirty_air_tax_s` is NULL (since FD6/CO-04 the shipped lag is NULL after a lap whose air state was not measured), the lap is not scored and is counted under `flat_unknown`.

**Flat-now (new).**
- Plain English: the flat penalty recalculated with the same lap's traffic instead of the previous lap's. One flat charge per lap, priced from the lap's own dirty-air share, with the charge per unit refitted by the same reference fit on the same seasons the measured curve is fitted on (2022-2024), so neither challenger sees 2025. It exists because the measured cost is built from the lap's own gaps, and the 2026-10-21 scoping (§2e) showed that same-lap timing on its own fits better than the lag. Beating the shipped flat penalty alone would therefore not show that the corner curve is right.
- Formal: `x_now = clamp(θ_now × dirty_air_share_lap, 0, 5)`, with `dirty_air_share_lap` from `int_lap_air_state` (no `COALESCE`; NULL stays NULL and the lap is not scored, counted under `flat_now_unknown`). θ_now is the coefficient on `dirty_air_share_lap` in `feols(partial_residual_s ~ dirty_air_share_lap | stint_id + age_bin, vcov = CRV1 race_id)` on the yardstick panel restricted to `race_year ∈ {2022, 2023, 2024}`. It is refitted inside every bootstrap draw on that draw's resampled fit races, exactly as the measured curve is. **(N1.)**

**Yardstick panel.**
- Plain English: lap time minus field pace, fuel and the lap's own tyre cost, with no traffic term. This is the panel the reference fit (and therefore 0.331) uses.
- Formal: the rows and columns of `WI01_PANEL_SQL`: `partial_residual_s`, `stint_id`, `age_bin` (laps 1-5, 6-10, 11-15, 16-20, 21-25, 26 and over in the stint), `lap_id`, `race_year`, `race_id`, `driver_id`, `lap_number`.
- **Unknown laps stay unknown.** `WI01_PANEL_SQL` fills a missing air share with 0 (`COALESCE(..., 0.0)` in its `d_lag1`). In WC-03/WC-04 that filled column is **never** used: the flat penalty comes from the shipped `dirty_air_tax_s` and flat-now from the unfilled `dirty_air_share_lap`, and a lap with either unknown is not scored. The panel's own `d_lag1` is used only inside G3 (the pooled-slope fingerprint) and the diagnostic reference-fit rerun (§12b), because both repeat the reference fit exactly as it was run to produce 0.331. On today's data the two differ on 12 panel laps only (§2e).
- The lap-time model's errors are **not** used, because that model's label already contains the flat penalty.
- The yardstick is not perfectly neutral: the field-pace base keeps only laps the existing air coder calls `free_air`/`tow_zone`, the same 1.5 s middle-third coder that defines the flat bit. That is the only link between the yardstick and the flat penalty.

### 2e. What has already been seen (declared prior knowledge)

1. **Same-lap scoping, 2026-10-21** (ai-integration build log, `_roadmap/_ai-integration/status/build-log.json`, the micro-sector dirty-air entry raised that day): read-only on the then-current warehouse, 2018-2025 including 2025, the reference fit gave "the current-lap bit fits better than the lag (0.473 vs 0.331 alone; 0.407 now / 0.130 lag jointly …), and continuous share_lap_within_1s fits better still (0.881). Better fit is not identification: shared local shocks (yellows, lapped cars) remain a threat." The measured cost is same-lap and continuous in the gap. **The flat-now comparator exists because of this result.**
2. **Reference-fit rerun, 2026-10-28** (this revision; `_evidence/WC-03-2026-10-27/REVISION-LOG.md`): the theta procedure (d1 Gate 1 and d2's F2 fit) rerun read-only on a scratch copy of today's warehouse (SHA-256 `7173444b…3214f9f`, the 2026-10-26 build that carries the v15 and v16 label changes). Result:

| Quantity | 2026-09-27 (produced 0.331) | 2026-10-28 rerun |
|---|---|---|
| Panel rows (= shipped calibration n) | 138,970 | 135,841 (shipped n also 135,841) |
| Pooled-slope fingerprint | 0.5033413666 | 0.4777453471 (Gate 1 **fails**, |d| 0.026) |
| F2 fit (stint + six tyre-age groups, race-clustered), n | 0.331347, n 138,679 | **0.304987**, n 135,675, 95 % CI 0.269-0.341 |
| F2 rounds to declared 0.331? (W40) | yes | **no** |
| F2 with unknown laps left unknown | not run | 0.305056, n 135,663 |
| Panel laps whose shipped tax is NULL | not checked | 12 (all other laps: shipped lag = panel lag) |

So the reference fit **does not reproduce 0.331**. The panel moved with the v15 (CO-04, 2026-10-15) and v16 (CO-09 + CO-15, 2026-10-24; sealed by CO-33 2026-10-26) label versions, and no rerun of d1/d2 after 2026-10-15 was found in the build logs. The shipped 0.331 is now about 0.026 above what the same procedure returns, though inside its interval. This is a look at the yardstick panel and the flat coefficient, not at any measured cost, contest score or curve.

**How the rerun is used (owner decision, 2026-10-28).** The benchmark stays the shipped 0.331, because that is what the label charges today. The rerun's result, **0.305 (95 % interval 0.269 to 0.341, n 135,675)**, is reported as a diagnostic only, not as the benchmark, with the note that the data moved after 0.331 was fitted (v15 and v16 label versions). Its two data fingerprints (the scratch copy's SHA-256 and the pooled-slope fingerprint, with the panel row count) define G3 checks 1-3. Check 4, signed off 2026-10-28, adds a combined hash of the bronze input files taken on 2026-10-28 (not part of the rerun). The run goes ahead only on data that has not changed since 2026-10-28.

**Which way the contest leans (corrects the first draft's "slightly favours the flat penalty").** Three effects pull in different directions, and their sum is unknown:
- 0.331 was fitted on 2018-2025, which includes the held-out 2025. That favours the flat penalty.
- On today's data the procedure returns 0.305, not 0.331, so the shipped flat penalty is off its own best value. That slightly favours the measured cost. The benchmark stays at 0.331, so this effect stays in and is stated on the scorecard.
- The measured cost uses this lap's traffic, the flat penalty last lap's, and same-lap timing alone is known to fit better (item 1). That favours the measured cost, probably strongly. **Flat-now is the control for this one.**

### 2f. How the tables are joined

- Plain English: a corner pass and a yardstick lap are the same lap when season, race, driver and lap number all match. The stint used for scoring is the warehouse's; the stint used for clean references is the pass table's own. Laps that fail to join are counted, not hidden.
- Formal: pass row ↔ panel row on (`season` = `race_year`, `race_id` = `race_id`, `driver` = `driver_id`, `lap` = `lap_number`). Both sides use the same `race_id` form (for example `2025_10`) and three-letter driver codes. Cross-check: `lap_id = season || '_' || race_id || '_' || driver || '_' || lap` must equal the panel's `lap_id` on every joined row, else G6 fails. The stint in §8a steps 3-4 and §8b step 3 is the panel's `stint_id` (the CO-09 tyre-run key); the stint in the reference rule is the pass table's `stint`. Counts reported: 2025 laps with passes but no panel row, and panel laps with no passes.

---

## 3. Seasons and what each is for

| Seasons | Role |
|---|---|
| 2022-2024 | Main fit (ground-effect cars). The main curve and θ_now are fitted here only. |
| 2025 | Held-out test. **The verdict rests on this season alone.** Nothing from 2025 enters any fit. |
| 2018-2020 fit, 2021 score | Older cars. **Its own curve**, fitted on 2018-2020 by the same estimator, and its own θ_now; same contest and thresholds. Reported beside the verdict; it never decides it, and the main curve is never applied to 2018-2021. |
| 2026 | A check that the measurement still works, plus an exploratory curve. No verdict. Section 13. |

---

## 4. Exclusions

### 4a. Inherited from WC-01 (unchanged)

A pass is left out (it carries an exclusion `reason`) when any of these apply, first match wins: lap 1; no lap record or no lap time; the lap overlaps safety car, virtual safety car or red flag (`neutralised`); a sector yellow in marshal sector k excludes corners in sectors k and k+1 (`yellow_sector`, marshal sectors evenly spaced); the first 2 laps after a restart (`restart`); a pit in or out lap for the follower (`pit_lap`) or the car ahead (`pit_lap_leader`); wet (`wet`); the follower's lap deleted for track limits (`track_limits`); a corner with no clean-air pass in the race (`no_segment`); off-track samples (`off_track`); a car ahead exists but no gap could be measured (`no_gap`).

Tags that do not exclude by themselves: car ahead is a lapped car within 3 s (`lapped`); the follower is shown a blue flag (`yielding`). The layout flag (`layout_changed`) never excludes.

Reference rule (inherited): the driver's own clean passes of the same corner within ±4 laps, same stint and compound; clean = more than 3 s behind the car ahead or no car ahead, and no car within 1 s behind; at least 2 such passes (`REF_MIN_N = 2`); reference = their median segment time.

### 4b. Added here, fixed now (choices C1-C3, N2)

- **No car ahead (new named reason).**
  - Plain English: when no other car went through the corner in the 30 s before this driver, there is no gap to put on the curve. Such a pass is given its own reason, `no_car_ahead`, so it is never dropped silently. It is left out of the curve fit. In the lap totals it is charged 0 (the driver is in clean air) and it does not stop the lap being scored. The count is reported per season, per class and for the race leader.
  - Formal: `reason_wc03 = 'no_car_ahead'` where `reason` is NULL and `clear_ahead` is true (the builder leaves `gap_s` NaN there). Assigned in the WC-03 analysis layer, not in the builder, so G2 is unaffected. **(N2.)**
- **Flat-out corners are kept out of the curve and out of lap totals** (`segment_basis = fixed_before_apex`). This settles watch item W5: no tow/wake split is attempted. **(C1.)**
- Yielding passes (tag `yielding` or `lapped+yielding`) are left out of the fit, and a lap with any yielding pass is left out of the contest. Passes with a lapped car ahead (tag `lapped`) are kept. **(C2.)**
- In the fit only: corner passes with `|delta_time_s| > 2.0` are left out as incidents. The 2.0 s threshold is a fixed number set here, not derived from any fit. **(C3.)**

---

## 5. The measures, in plain English with the formal rule

| Measure | Plain English | Formal rule |
|---|---|---|
| Corner pass | One driver through one braking corner on one lap. | A pass-table row with `segment_basis = brake_onset`, `reason` NULL and `reason_wc03` NULL. |
| Approach gap | How far behind the car ahead the driver was, in seconds, just before the corner. | `gap_s`: mean of (follower time minus car-ahead time) at 26 points from 300 m to 50 m before the segment start. |
| Corner loss | Time lost through the corner compared with the same driver's own clean passes nearby. | `delta_time_s = seg_time_s − ref_time_s`, only where `ref_status = measured`. |
| Following pass | Close enough behind another car to be in traffic. **(C4; departs from WC-03's 2.5 s so the curve meets the 3 s clean rule.)** | `0 ≤ gap_s < 3.0`. A pass with `gap_s < 0` is racecraft. |
| Reference spread | How much the driver's own clean passes vary. | Median absolute deviation of `seg_time_s` over the same donor passes the builder used (same driver, `corner_id`, `stint`, `compound`, `clean` true, lap within ±4, the pass itself excluded), floor 0.01 s. Recomputed from the pass table; not a stored column. |
| Car ahead's time | How long the car ahead took through the same corner on the lap it was on. | `seg_time_s` of the row at (`race_id`, `driver` = `leader`, `lap` = `leader_lap`, `corner_id`). Missing if that row does not exist or has no `seg_time_s`. |
| Racecraft | A pass or position change was happening. **(C5.)** | `gap_s < 0`, or the follower's `leader` differs between this corner and any braking corner within 3 corners before or after (same or adjoining lap). A missing leader at a neighbouring corner does not count as a change. No lateral rule (the table has no lateral measure). |
| Pass class (every following pass gets exactly one) **(C6, boundary changed: N3)** | Checked in this order: racecraft; then, if the car ahead's time is unknown, "no leader time"; then held up if the car ahead was clearly slower than this driver's normal; otherwise dirty air. No gap, no overlap. | Priority: (1) `racecraft`; (2) `no_leader_time` if the car ahead's time is missing; (3) `held_up` if car ahead's time > `ref_time_s` + 2 × reference spread; (4) `dirty_air` if car ahead's time ≤ `ref_time_s` + 2 × reference spread. All four go into the contest curve; only (3) and (4) have class curves. |
| Under attack | A car close behind. A flag, not a class. | `behind_1s` true. |
| Loss curve (main curve) | Typical corner loss at each gap, per corner class. | Section 6. "Main curve" and "contest curve" are the same thing. |
| Flat penalty for a lap | Today's charge. | `dirty_air_tax_s` (§2d). |
| Flat-now for a lap | Today's charge moved to the same lap. | `x_now` (§2d). |
| Measured cost for a lap | The curve added up over the lap without counting any stretch twice. | Section 7. |
| Clean-reference half / no-reference half | Laps where the driver mostly had a clean reference, against laps where they mostly did not. | A scored lap is in the clean-reference half if at least half of its braking-corner passes (excluding `no_car_ahead`) have `ref_status = measured`; otherwise the no-reference half. |
| Train lap **(N4)** | A lap spent close behind another car, without a clean comparison. | A no-reference-half lap whose median `gap_s` over its braking corners is under 1.5 s (`no_car_ahead` corners counted as 3 s). |
| Mixed stint | A stint with laps both in and out of traffic, so the driver's level in traffic can be compared with their own level out of it. | A panel `stint_id` with at least 2 scored laps in the clean-reference half and at least 2 scored train laps. |
| Coverage per team | How much of each team's racing the measurement speaks for. | Per constructor: share of scored laps in the clean-reference half, and share of following braking passes with a measured reference. |

---

## 6. The curve (estimator) (choices C7, C8)

- **Fit passes:** seasons 2022-2024; braking corners; `reason` NULL and `reason_wc03` NULL (so no `no_car_ahead`); `ref_status = measured`; not yielding; `0 ≤ gap_s < 3.0`; `|delta_time_s| ≤ 2.0`.
- **Main (contest) curve, used in the verdict:** one curve per corner class (slow, medium, fast) fitted on **all** following passes in the fit set, whatever their pass class. It needs only the gap and the corner class, so it can be applied to every lap, trains included.
- **Class curves:** the same estimator fitted separately on `held_up` and on `dirty_air` passes. Reported; the dirty-air curve is used in P2.
- **Estimator:** for each corner class, corner loss = a fixed effect for each of the 8 gap bins ([lower, upper)) + a random effect per circuit (the builder's circuit name after `CIRCUIT_ALIASES`, with `SEPARATE_LAYOUT_SLUGS` kept separate) + a random effect per `corner_id` + noise, fitted by restricted maximum likelihood. The 8 bin estimates are then forced to be non-increasing with gap (pool-adjacent-violators, weighted by the inverse of each bin's variance). Step function by bin; not forced to zero at 3 s.
- **Applying the curve:** `gap_s ≥ 3.0` gets 0; `no_car_ahead` gets 0; `gap_s < 0` gets the first bin's value (an overtaking pass is priced as the closest following pass; no separate racecraft cost is fitted); otherwise its bin's value. Only the fixed part is applied.
- **Intervals:** race-level bootstrap (§8c). Each draw refits the whole chain, including the non-increasing step.
- **Older cars:** identical, fitted on 2018-2020 only; this older curve is the only curve applied to 2021 laps.

---

## 7. Lap totals: no stretch of track counted twice (choice C9)

About 47 % of braking-corner segments start inside the previous corner's segment, so a plain sum would count that stretch twice. The pass table does not carry the apex's lap distance (the builder computes `cum_apex` but does not output it), so overlap is measured **in time from the existing columns** `seg_start_t` and `seg_end_t`. No builder column is added and G2 is unaffected.

- Plain English: each braking corner's stretch of track runs from where braking starts to 100 m past the apex. On each lap, take the driver's braking corners in the order the driver reached them. Each moment of the lap belongs to the first corner whose stretch covers it. A corner's weight is the share of its own stretch that it owns. The lap's measured cost is the sum of each corner's curve value times its weight. Only corners on the same lap are compared, so nothing wraps across the start/finish line.
- Formal:
  1. Geometry (for meaning; the computation uses times): segment k runs from `apex_k + seg_offset_m` to `apex_k + 100 m`. **`seg_offset_m` is negative** (the median brake offset, `min(·, 0)`), so the start is before the apex. The builder stores the segment's session times as `seg_start_t` and `seg_end_t`.
  2. For one (`race_id`, `driver`, `lap`), take its braking-corner rows, sorted by `seg_start_t`, ties by `corner_number`. Let `I_k = [seg_start_t_k, seg_end_t_k]`.
  3. `owned_k = |I_k| − |I_k ∩ (I_1 ∪ … ∪ I_{k−1})|`; `w_k = owned_k / |I_k|`, in [0, 1].
  4. Measured cost for the lap = `Σ_k w_k × curve(class_k, gap_k)` over the lap's braking corners (with `no_car_ahead` corners contributing 0 but still owning their time). Straights and flat-out corners contribute 0.
  5. If any braking corner on the lap has `seg_start_t` or `seg_end_t` missing or `seg_end_t ≤ seg_start_t`, the lap is not scored (counted under `no_segment_time`).
  6. Assumption: loss is spread evenly in time along a segment.

A synthetic test (G1 iii) checks that no instant is weighted more than once and each weight lies in [0, 1].

---

## 8. The contest on 2025

### 8a. Which laps are scored (the whole field), in a fixed order (choice C10)

- Plain English: the filters run once, in this order, on the real 2025 sample. The ±5 s threshold is a fixed number set here; the residual it is applied to comes from a baseline with **no traffic term at all**, fitted once before any candidate is scored. The scored set is then frozen and not recomputed inside bootstrap draws.
- Formal:
  1. Start from 2025 laps in the yardstick panel that join to the pass table (§2f).
  2. Keep laps where: `dirty_air_tax_s` is not NULL; `dirty_air_share_lap` is not NULL; every braking corner of that race has a pass row on that lap whose `reason` is NULL and whose `reason_wc03` is NULL or `no_car_ahead`; every such corner with a car ahead has a gap; no pass on the lap is yielding; §7 step 5 holds.
  3. On the set from step 2, regress `partial_residual_s` (no traffic term) on `stint_id` and `age_bin` indicators once; drop laps with |residual| > 5 s.
  4. Drop stints left with fewer than 2 laps. Do not repeat steps 3-4.
  5. Count every drop by its reason.

A lap does **not** need a clean reference to be scored. The scored set is then split into the clean-reference half and the no-reference half, and the train laps are picked out of the no-reference half (§5).

### 8b. The yardstick and the score (choice C11)

For each candidate c (none, flat, flat-now, measured):
1. `x_c` is the candidate's traffic cost for the lap: 0, `x_flat`, `x_now` or the measured cost (§7).
2. `e_c = y − x_c`, where y is `partial_residual_s`.
3. Remove each stint's own level and the tyre-age group: regress `e_c` on `stint_id` and `age_bin` indicators over all scored 2025 laps, keep the residual `r_c`. No traffic number is rescaled: its coefficient is fixed at 1.
4. Score on a set of laps S: `MSE_c(S) = mean of r_c²` over S.
5. **Improvement over the flat penalty** `R_flat(S) = 1 − MSE_measured(S) / MSE_flat(S)`; **improvement over flat-now** `R_now(S) = 1 − MSE_measured(S) / MSE_now(S)`. Positive means the measured cost does better.

Also reported, for context only: each candidate's gain over no traffic term (`1 − MSE_c / MSE_none`), and R on laps where any candidate is non-zero.

### 8c. Allowing for chance

- Plain English: to see how much of a difference could be luck, the races are reshuffled 1,000 times. Each reshuffle draws the fit races and the held-out races with replacement, refits the curve and θ_now on the drawn fit races, and rescores the drawn held-out races. The interval is the middle 95 % of the 1,000 results. The number 1,000 is fixed now; it is not reduced or increased after anything is seen, and the run is not repeated.
- Formal:
  - Method: nonparametric cluster bootstrap with the race as the cluster. Fit races (68) and held-out races (24) are resampled independently, with replacement, each to its original count; a race drawn twice counts twice and its stints count as separate stints. The old flat penalty is not re-estimated in a draw (it is the shipped value); θ_now and the measured curve are.
  - Draws: **B = 1,000, fixed**. Seed 20261027 (numpy `default_rng`). No fallback count. If the synthetic timing (G1) shows 1,000 draws cannot finish, that is fixed by a pre-result amendment before any real score exists, never after.
  - Interval: 95 % percentile interval (2.5th to 97.5th percentile of the B values).
  - Minimum races: at least 60 of the 68 fit races must contribute fit passes and at least 20 of the 24 held-out races must contribute scored laps; otherwise G5 fails. Each scored set in §8d must meet the contest minimums.
  - Stated limitation: 24 held-out races is a small number of clusters; percentile intervals may run somewhat narrow, which makes W1 slightly easier to pass than its 95 % label suggests.

### 8d. What the trains check can and cannot see

- **Plain English, stated plainly:** the contest takes out each stint's own level before scoring (§8b step 3). So **a stint spent entirely in traffic cannot be told apart from a stint with no traffic charge at all**: whatever constant cost the stint carried is removed along with its level, from every candidate alike. The contest only tests how the traffic cost *changes within a stint*. It cannot show whether a whole stint in a train is priced at the right level; neither could the fit that produced 0.331.
- **About a third of recent stints have no clean comparison:** in the WC-01 counts, the share of stints with kept passes but no measured reference at all is 0.32 (2022), 0.36 (2023), 0.32 (2024) and 0.36 (2025).
- **Where W2 is scored:** on the **train laps** (§5): no-reference-half laps with a median braking-corner gap under 1.5 s. Laps in the no-reference half only because a car sat close *behind* (and so could not donate a reference) are not train laps.
- **Also reported:** R_flat and R_now on the laps of **mixed stints** (§5), the only stints where the driver's level in traffic is compared with the same driver's level out of it. Reported, not a verdict input.
- The scorecard prints under the verdict: "This contest checks changes in traffic within a stint, not the level of a whole stint spent in a train."

---

## 9. The win rule and the verdicts

The owner's decision rule is unchanged. The only change is that "beats the flat penalty" now means beating both the shipped flat penalty and flat-now.

**W1: beats the flat penalty by the margin.**
- Plain English: the measured cost's error must be at least 0.5 % lower than the shipped flat penalty's, and at least 0.5 % lower than flat-now's, even at the unlucky end of the reshuffles.
- Formal: on all scored 2025 laps, the lower end of the 95 % interval of `R_flat` ≥ **0.005**, **and** the lower end of the 95 % interval of `R_now` ≥ **0.005**. (Applying the owner's 0.5 % margin to flat-now as well: N5.)

**W2: no worse for drivers stuck in trains.**
- Plain English: on train laps, the measured cost is on average no worse than the shipped flat penalty, and even at the unlucky end no more than 0.5 % worse.
- Formal: on the train laps, the point estimate of `R_flat` ≥ 0 **and** the lower end of its 95 % interval ≥ **-0.005**. (Threshold: C12.) `R_now` on train laps is reported beside it.

**W3: physics checks pass.** Both checks in section 10 pass.

| Outcome (owner-approved) | Verdict |
|---|---|
| Any check in 12a fails, or any minimum in 12a is not met | **No verdict.** The flat penalty stays. The report says which check failed. |
| W1, W2 and W3 all pass | **Replace** the flat penalty with the measured cost (scope below). |
| W1 and W3 pass, W2 fails | **Keep the flat penalty** and show the measured figure beside it. |
| W1 fails (including: beats the shipped flat penalty but not flat-now) | **Keep the flat penalty and stop.** WC-05, WC-06 and WC-08 do not start. |
| W3 fails | **Keep the flat penalty and stop.** A curve that fails the physics checks is not measuring what it claims. |

Rows are read top to bottom; the first that applies is the verdict. "No verdict" is the only outcome when a setup check fails or a minimum is short, including the train-lap minimum; there is no separate "cannot be replace" case. A "nearly" result is not argued up: an interval that misses its threshold by any amount is a fail.

**Scope of the verdict (part of N5).**
- Plain English: the verdict is about 2022-2025 only, using the main curve. The main curve is never applied to 2018-2021. The 2018-2021 cars have their own curve (fitted 2018-2020, scored on 2021); its result is shown beside the verdict and never decides it. Under any verdict, 2018-2021 laps keep the flat penalty in this registration; changing them would need its own owner ruling after reading the older-car result. Laps the measured cost cannot price (§8a drops) keep the flat penalty. 2026 keeps the flat penalty until a 2026 registration exists.
- Formal: `replace` applies to 2022-2025 laps that pass §8a steps 1-2. Older-car result → Table 2 only.

---

## 10. Physics checks (W3) (choice C13)

Both use the main curve fitted on 2022-2024, with its bootstrap intervals.

- **P1, almost no loss well clear of the car ahead.**
  - Plain English: for each corner class, the loss 2-3 s back must be small compared with the loss 0.5-1.0 s back, in either direction, and the near loss must be clearly above it. A far band below zero (following at 2.5 s *faster* than the clean reference) does not pass automatically: it means the reference is off.
  - Formal: per class, with `near` = mean of the 0.5-0.75 and 0.75-1.0 bins and `far` = mean of the 2.0-2.5 and 2.5-3.0 bins: (a) `near > 0`; (b) `|far| ≤ 0.25 × near` (point estimates); (c) the lower end of the 95 % interval of `near − far` > 0. All three classes must pass.
- **P2, more wake loss in fast corners than slow ones.**
  - Plain English: on the dirty-air curve, fast corners must not clearly lose less than slow corners at 0.5-1.0 s. This checks only against a clearly reversed sign; it does not show that fast corners lose more.
  - Formal: the 95 % interval of (fast − slow) of the dirty-air curve's 0.5-1.0 s mean must not lie wholly below zero.

The straight-line tow is not tested: straights are not in the pass table.

---

## 11. Pit-stop figure (reported only; never pass or fail) (choice C14)

**Purpose.** When the car ahead pits, the follower suddenly has clean air. The jump in the follower's pace is an upper limit on the traffic cost, because the follower often pushes at that moment. The figure shows how the curve's predicted drop compares with that jump. It is reported as numbers, never as pass or fail, and it is not a verdict input.

**Events (one per pit stop).**
- A stop is the car ahead's pit-entry lap L. Each stop is counted **once**. If more than one follower qualifies, the one with the smallest mean gap on laps L−2 and L−1 is kept.
- **Close:** on laps L−2 and L−1 (never L itself), the follower has that same car ahead at every braking corner, and the mean approach gap over those corners is under 1.5 s.
- **Drop** the event if, at any of those corners, `lap ≠ leader_lap`.
- The follower has no pit in or out on laps L−2 to L+2; the car ahead has none on L−2 or L−1.
- **The follower's reference comes from outside the window:** own clean passes of the same corner, same stint and compound, on laps L−6 to L−3 and L+3 to L+6, at least 2, median. Without one the event is dropped and counted.

**Jump.** The follower's mean corner loss against that outside reference on L−2 and L−1, minus the same on L+1 and L+2, braking corners measured on both sides only.

**Comparison group.** In the same race, pairs whose car ahead does **not** pit (and neither car pits on P−2 to P+2), same car ahead at every braking corner of P−2 and P−1, same lap numbers, mean gap in the same band (0-0.5, 0.5-1.0, 1.0-1.5 s), P within 5 laps of L. **Adjusted jump** = event jump minus the mean comparison jump in its cell. An event with no comparison pair is dropped and counted.

**Predicted drop.** The main curve at the follower's gaps on L−2 and L−1 minus at its gaps on L+1 and L+2, same corners.

**What is reported.** The number of stops after each drop; the mean predicted drop; the mean adjusted jump with its 95 % race-bootstrap interval; and their ratio (predicted ÷ adjusted jump) with its interval. Words used: "predicted drop is X % of the observed jump"; never "pass" or "fail".

**Minimum.** At least **200 distinct stops** after every drop. Below that, only the counts are reported, marked "not testable".

**Seasons.** Main: events 2022-2025 against the main curve (2025 also on its own). Older cars: 2018-2021 against the older curve, own 200-stop minimum. 2026: against the 2026-only exploratory curve.

---

## 12. Checks before a verdict, and what is reported beside it

### 12a. Must pass before a verdict is issued (setup checks)

- **G1 synthetic tests**, committed with the estimator and passing before the real run: (i) the estimator recovers a known non-increasing curve from simulated passes, and its 95 % intervals cover the true values in at least 90 % of 200 simulations (each with 200 draws); (ii) the contest returns `R = 0` when two candidates are identical; (iii) the lap-total weights never count an instant twice and each lies in [0, 1]; (iv) the pit-stop event builder counts each stop once, drops different-lap pairs and never takes the reference from laps L−2 to L+2; (v) no fit row (curve or θ_now) comes from the held-out season; (vi) the class rule puts every following pass in exactly one class; (vii) a NULL flat penalty or NULL same-lap share leaves the lap unscored, never 0; (viii) the timing of one full draw, recorded before any real score.
- **G2 inputs reproduce:** the rebuilt pass table reproduces the WC-01 count files (`counts_by_season.csv`, `passes_by_corner_class.csv`, `exclusion_reasons_by_season.csv`) byte for byte.
- **G3 the input data has not changed since 2026-10-28. Runs before any scoring.**
  - Plain English: the benchmark is the shipped 0.331, tested as it is. Before anything is fitted or scored, the run checks that the warehouse data it reads is the same data the 2026-10-28 rerun read (checks 1-3) and, check 4, that the bronze input files are the ones hashed on 2026-10-28. If anything has changed, nothing is fitted or scored, the verdict is "no verdict", and the owner is told.
  - Formal, in this order; checks 1-3 on the run's scratch copy of `data/dev.duckdb` (§2d), check 4 read-only on the files under `data/bronze`:
    1. The SHA-256 of the scratch copy equals `7173444b0745130769863c123fb5c04c7e5edd8be7a1fb2dbf614637d3214f9f` (the data-source fingerprint recorded in `REVISION-LOG.md`).
    2. The yardstick panel built by the wrapper from `WI01_PANEL_SQL` has exactly 135,841 rows, and the shipped calibration n equals 135,841.
    3. The panel's pooled-slope fingerprint (d1 Gate 1, the reference fit's first step, computed exactly as d1 computes it) equals 0.4777453471 within 1e-9 (d1's own Gate 1 tolerance).
    4. **[PRE-RESULT AMENDMENT, signed 2026-10-28.]** The bronze parquet inputs are unchanged. Take every file the warehouse build reads (`data/bronze/{laps,race_control,results,weather,telemetry}/season=*/race=*/*.parquet`, 863 files) plus every file the WC-01 builder `build_pass_table.py` reads beyond those (`data/bronze/track_status/season=*/race=*/track_status.parquet`, `data/bronze/circuit_info/season=*/race=*/*.parquet`, `data/bronze/schedule/season=*/schedule.parquet`, 351 files). Hash each with SHA-256, write one line `<hash>  <path relative to data/bronze>` per file, sort the lines bytewise (`LC_ALL=C`) by path, and take the SHA-256 of that text. The file count must equal **1,214** and the digest must equal `aed1c27da1cc00fb80eea470bb0c5c4879ee09556c81ff35bc17ad4aff1690b4`. Why: checks 1-3 do not cover the parquet files the staging views and the pass-table builder read (`_evidence/WC-03-2026-10-27/AMENDMENT-G3-bronze-hash.md`).
  - All four must hold (checks 1-3 only, if check 4 is not accepted at signing). G3 is computed and written to PROVENANCE.txt before any curve, θ_now, contest score or other gate on the pass table is computed. If any part fails: the run stops at once, nothing is fitted or scored, the verdict is **no verdict**, the flat penalty stays, and the scorecard's first line says "No verdict: G3 failed, the input data has changed since 2026-10-28" with the value found; the owner is told before anything else is done. A new run on changed data needs a new registration (or a pre-result amendment, signed before any result).
  - The scorecard states that 0.331 is about 0.026 above what its own procedure returns on the 2026-10-28 data (0.305, a diagnostic only; §2e, §12b).
- **G4 no leakage:** asserted in code that no 2025 row (2021 for the older check) is in any fit.
- **G5 minimums:** at least 1,000 scored laps and 18 races in each of the whole 2025 field, the clean-reference half and the train laps; at least 60 fit races and 20 held-out races contributing (§8c). If any is short: no verdict.
- **G6 joins:** every joined pass row satisfies the `lap_id` cross-check (§2f); the counts of unjoined laps are reported.

### 12b. Reported beside the verdict (none rescues or sinks it)

- Pit-stop figure (§11).
- Reference-fit diagnostic: the 2026-10-28 rerun of the procedure that produced 0.331 gave 0.305 (95 % interval 0.269 to 0.341, n 135,675) because the data moved after 0.331 was fitted (§2e). Reported as recorded; it is not the benchmark, is not re-estimated in the run, and never enters the verdict.
- Older-car curve and contest, 2018-2020 fit on 2021, with W1-W3 computed the same way.
- Reference window ±2 and ±6 laps instead of ±4 (rebuilt references, refit, rescored; 1,000 draws each, same seed). If W1 holds at ±4 but not at ±2 or ±6, the report says so in its first lines.
- 2025 scored without 2024 Las Vegas in the fit.
- Held-up and dirty-air class curves; the under-attack difference at the same gap (expected near zero).
- Mixed-stint results (§8d).
- Minimum-speed agreement per corner class (observation only, as ruled in WC-02).
- Coverage per team and the contest result per team.
- Each candidate's gain over no traffic term.
- Counts: passes per class, bin, season and race; `no_car_ahead` passes (per season, class, and for the race leader); every §8a drop by reason; unjoined laps; `flat_unknown` and `flat_now_unknown` laps.

---

## 13. 2026: method check and exploratory curve, no verdict

**Precondition, not a solved step.** On 2026-10-27, loading the public timing and car data for the first 2026 race failed from this machine. The 2026 part runs only after WC-09 has ingested 2026 into bronze **with car and position data** for the races used. Until then it is reported as "not run: no data". If only timing data can be obtained, only timing-based counts are reported; no corner checks and no curve. No 2026 data is looked at, beyond a one-race test of whether it loads, before this document is committed.

**Once the data exists**, the 2026 checks run **once**, on the race list frozen when WC-09 lands, with the WC-01 builder unchanged (later runs are labelled updates):
- Gap agreement with the timing feed per race, by the position method (WC-02 salvage method C2, not choice C2 below), flagged at 0.1 s.
- Share of kept passes with a measured reference, per team.
- Near-zero band (P1 rule, per class) on a 2026-only curve.
- Fast versus slow (P2 rule) on a 2026-only dirty-air curve.
- The pit-stop figure within 2026 against the 2026-only curve (expected "not testable").
- A 2026-only curve with the same estimator, **marked exploratory on every table and chart**.

No contest, no verdict, no comparison of a 2022-2024 curve with 2026. There is no DRS in 2026; flat-out corners stay out.

---

## 14. Stated risks

- **Prior knowledge.** Declared in §2e: same-lap traffic is known to fit better than the lag on data that includes 2025; and the reference fit is known to return 0.305 on today's data. Flat-now controls the first. For the second, the benchmark stays the shipped 0.331, 0.305 is reported as a diagnostic only, and G3 stops the run if the data has changed since 2026-10-28.
- **Which way the contest leans** is not known (§2e): the 2025 overlap in 0.331's fit favours the flat penalty; same-lap timing and 0.331 sitting above today's fit favour the measured cost.
- **Selection and levels.** The curve is fitted only where a clean reference exists. The contest removes each stint's own level, so a whole stint in a train is invisible to it (§8d), and about a third of 2022-2025 stints have no clean comparison at all. W2 guards against the measured cost making within-stint predictions worse in trains; it does not validate the level charged to a train.
- **Shared local shocks.** A mis-mapped yellow (marshal sectors are approximated by even spacing) or a slow lapped car closes the gap and slows the follower on the same lap; that reads as traffic cost in both the fit and the contest. Flat-now shares this exposure, so W1's flat-now leg partly controls it.
- **Gap noise** of about 0.05 s flattens the closest bin; 2024 Las Vegas has an inconsistent feed.
- **Slow corners** are where held up and dirty air are hardest to tell apart (minimum-speed agreement 0.47 there); expect the slow-corner curve to be the least reliable.
- **Lap totals leave out flat-out corners and straights**, which biases the measured cost low; the "first stretch owns it" rule hands a braking zone that overlaps the previous corner's tail to that corner, also biasing low.
- **Coverage figures.** "49 % of kept passes measured; 43 % in 2025" includes clean and flat-out passes; the share of following braking passes with a reference (the real fit population) is lower and is reported.
- **Baseline drift** inside the ±4-lap window; reported via ±2 and ±6.

---

## 15. What gets reported, and in what form

Into `_roadmap/_wake-calibration/_evidence/WC-03-<date>/` (the curve) and `_evidence/WC-04-<date>/` (the verdict):

- **SCORECARD.md**, one page, plain English. First line: the verdict from section 9. Second line: "This contest checks changes in traffic within a stint, not the level of a whole stint spent in a train." Then two tables:
  - **Table 1 (verdict inputs):** W1 (both legs), W2, W3/P1, W3/P2, G1-G6: the rule, its fixed threshold, the result with its interval, pass or fail.
  - **Table 2 (context, never a verdict input):** pit-stop figure, older cars, mixed stints, sensitivity runs. Reported as figures; never "pass" or "fail".
- **PROVENANCE.txt**: commands, scratch paths, the scratch copy's SHA-256, interpreter, seed, number of draws, every run start and its reason, fingerprints of every input and output, and this document's SHA-256.
- Tables (CSV): main curve (class, bin, estimate, interval, passes, races); class curves; older curve; θ_now with interval; contest (set of laps, MSE for none, flat, flat-now and measured, R_flat, R_now, intervals, laps, races); coverage and result per team; physics checks; pit-stop events with every drop counted by reason; sensitivity runs; all counts in §12b.
- One chart: loss against gap per corner class with intervals, main curve and older curve.
- 2026, when run, in its own folder, labelled exploratory.

The owner reads the scorecard before anything else uses the result. No figure from this work goes into the app, the label or the replay view until the owner has read it and ruled.

---

## 16. What this registration does not do

- It does not change the label, the flat penalty value, or any warehouse table.
- It does not build the modelled tier (WC-05) or any product item.
- It does not split tow from wake, or price straights.
- It uses no number from the archived dirty-air method.
- It supersedes WC-04's scorecard items 1 ("match") and 2 ("the straight tow is a gain"): item 1 is replaced by W1-W3; item 2 is dropped because straights are not measured.

---

## 17. Owner sign-off

### 17a. Confirmed choices

The owner-approved decisions (the verdict rule in §9, the 0.5 % margin, fit 2022-2024 / score 2025, older cars 2018-2020 / 2021 as a separate check, no verdict on a failed setup check) are not open. The benchmark is the shipped 0.331, with G3 checking the data has not changed since 2026-10-28 (owner decision 2026-10-28; §2e, §12a). Everything below is **confirmed by owner on 2026-10-28**.

The fourteen choices from the first draft (the covering note that listed them is not in the repo, so they are listed here as found in the draft):

| # | Choice | Where |
|---|---|---|
| C1 | Flat-out corners out of the curve and lap totals (settles W5) | §4b |
| C2 | Yielding passes out of the fit and their laps out of the contest; lapped-car passes kept | §4b |
| C3 | Corner-loss trim ±2 s in the fit | §4b |
| C4 | Following = gap 0-3.0 s (not WC-03's 2.5 s) | §5 |
| C5 | Racecraft rule (3 corners either side, no lateral rule) | §5 |
| C6 | Held up = car ahead slower than reference + 2 × spread | §5 |
| C7 | Estimator: 8 gap bins, circuit and corner random effects, REML, non-increasing step | §6 |
| C8 | Contest curve fitted on all following passes, applied to every lap | §6 |
| C9 | Lap totals: first stretch owns the overlap | §7 |
| C10 | Whole field scored; ±5 s trim on the no-traffic baseline; stints need 2 laps | §8a |
| C11 | Score: stint level and tyre-age group removed, coefficient fixed at 1, mean squared error | §8b |
| C12 | W2 threshold: point ≥ 0 and lower end ≥ -0.5 % | §9 |
| C13 | P1 (25 %, now two-sided with an interval) and P2 (reversed-sign only) | §10 |
| C14 | Bootstrap 1,000 draws, seed 20261027; pit-stop figure design and 200-stop minimum; contest minimums 1,000 laps and 18 races | §8c, §11, §12a |

New in this revision:

| # | Choice | Where |
|---|---|---|
| N1 | Flat-now = θ_now × same-lap share, θ_now refitted on 2022-2024 | §2d |
| N2 | No car ahead: named reason `no_car_ahead`, out of the fit, charged 0 in lap totals, lap still scored | §4b |
| N3 | Dirty air = car ahead not slower than reference + 2 × spread (closes the gap between the classes); `no_leader_time` as its own class | §5 |
| N4 | Train lap = no-reference-half lap with median braking-corner gap under 1.5 s | §5 |
| N5 | W1's 0.5 % margin applied to flat-now too; failing only the flat-now leg = keep and stop (owner rule "doesn't win"); 2018-2021 keep the flat penalty under any verdict | §9 |

### 17b. Signature

Signed 2026-10-28 by the owner. The owner kept the pooled-slope tolerance in G3 check 3 (and §0) at 1e-9, d1's own Gate 1 tolerance; the earlier branch B text used 1e-6 and is not used. Check 4 (bronze file hash) was signed with the registration.

```
Benchmark:          [x] Shipped 0.331 as the benchmark; G3 = input data unchanged since 2026-10-28 (incl. bronze-file hash, check 4)
Choices C1-C14:     [ ] Confirmed as written    [x] Confirmed with the edits made above
Choices N1-N5:      [ ] Confirmed as written    [x] Confirmed with the edits made above
Decision:           [ ] Approved as written    [x] Approved with the edits made above
Margin confirmed:   0.5 % (W1, both legs)    Trains non-inferiority: -0.5 % (W2)
Signed (owner):     Owner, by instruction in session, 2026-10-28
Date:               2026-10-28
```

**After signing:**
1. Change the status line at the top from "DRAFT FOR SIGNATURE" to "SIGNED <date>".
2. Commit **this file alone**, with no other file in the commit.
3. Compute its fingerprint as committed: `shasum -a 256 _roadmap/_wake-calibration/wi/WC-03-preregistration-DRAFT.md`.
4. Record that SHA-256 and the commit on **WC-03 in the build log** (`status/build-log.json`), which clears watch items W1 and W5. Then run `board.py --check` and `--write-order`.
5. Nothing is fitted before step 4 is done.
