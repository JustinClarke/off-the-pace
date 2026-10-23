# Dynamic dirty air: design note (2026-10-23)

**The idea.** Today the cost is 0.331 s × the previous lap's dirty-air share. Instead, price each position sample by its time gap to the car ahead, then add the prices up per micro-sector, sector and lap. Stop gates come before any label moves.

**Measured on dev.duckdb** (stale until CO-17): 68.1M position samples across 171 races (2018 has 19). Median sample spacing on one race is 0.30 s (position channel) and 0.24 s (car channel). `distance_to_ahead_m` is NULL on about 5% of samples. The position table's `track_status` only says OnTrack or OffTrack, not the flag state.

## 1. Exposure

In words: at each sample, work out how many seconds this car is behind the car ahead at the same point on track. Turn that gap into seconds lost per second, then multiply by how long the sample lasts.

- **Gap g_i:** the time this car reached relative_distance r_i, minus the car ahead's interpolated time at r_i. This is the `int_lap_proximity` crossing logic per sample, with no bins.
- **Metres:** a sensitivity check only, since converting them to seconds assumes equal speeds.
- **Unit of time:** one position sample. dt_i is the time to the next sample, about 0.3 s, capped at 1 s.

cost_i = dt_i · β(g_i, z_i) · v_i, and the lap, sector or micro-sector cost is Σ cost_i over its samples.

β is a step function over gap bands: <0.5, 0.5-1, 1-1.5, 1.5-2 and 2-3 s, with >3 s as the reference band.

v_i marks valid samples; every invalid one gets a reason code:
- **Car ahead unknown:** cost NULL, not 0 (the CO-04 rule). A lap with more than 20% unknown gets a NULL lap cost.
- **Lapped car ahead within 3 s:** left out of β and logged as `lapped_ahead_s`. Beyond 3 s the sample is in the reference band whoever the car is (DD5, 2026-10-23).
- **Pit lane** (either car): excluded.
- **OffTrack, SC, VSC, red, local yellow, lap 1, and the 2 laps after a restart:** excluded.

## 2. Rich signals

- **Exist today:**
  - gap trend dg/dt;
  - speed, throttle and brake differences to the car ahead (car channel; brake is on/off only);
  - DRS active (`drs_active`). Raw code 8 ("eligible") needs a small staging change;
  - session flag state (`stg_track_status`);
  - tyre age (`stg_laps.tyre_life`);
  - position in the lap and corner class (`stg_circuit_info`).
- **NEW INGESTION:** a marshal-sector-to-track map (FastF1 `marshal_sectors`), needed to place the local yellows in `stg_race_control.marshal_sector`; and a live timing feed (out of scope).

## 3. Identification

y_{d,l,m} = α_{d,l} + Σ_k β_k·1[entry gap ∈ k] + γ·aheadResid_{l,m} + δ·(tyre-age × micro) + λ·z + ε, with standard errors clustered by race.

- **y** is micro-sector time (10-20 per lap) minus the field median for the same race, lap and micro-sector. This removes shocks that hit the whole field.
- **α (driver-lap fixed effect)** absorbs form, fuel and tyres.
- **aheadResid**, the car ahead's own field-relative time in the micro-sector, controls for a slow car ahead.
- **Only the entry gap is used.** The exit gap is an outcome.
- **Dropped samples:** as in section 1.

**Pre-registered placebos** (commit a hash before fitting):
- **P1, car behind within 1 s → about 0.** Rules out a general close-racing effect, but not a confound specific to the car ahead.
- **P2, β ≈ 0 above 3 s and shrinking with the gap.** Rules out a level shift that does not depend on the gap.
- **P3, mechanism:** loss in high-speed corners, tow gain on straights.
- **Lead window:** not a clean placebo, because losing time opens the gap mechanically (W11 saw -0.05). It must only be 0 or below.

**Nothing here rules out:**
- pair-local shocks that race control did not flag;
- deliberate tyre saving while following;
- selection in which drivers end up following.

Until P1 to P3 pass, call the result an adjusted "traffic cost".

## 4. Real-time use

- **dbt:** `int_sample_proximity` (about 68M rows) and `int_microsector_proximity`.
- **Outside dbt:** a fit script in the style of `estimate_theta_air_08q.py`, with results stored as declared vars.
- **Outputs:** a per-sample cost, micro, sector and lap totals, and a running cumulative value.
- **For users:** shown as a session replay, not live, because FastF1 data is post-session. App copy must say this is attribution from a same-lap model, not a causal label.

## 5. Label paths

- **A. Sit beside the label.** Add `dirty_air_cost_dynamic_s`. The label, residuals, `theta_air`, `cumulative_dirty_air_tax_s` and the ML models are unchanged, and the dirty-air-cost page gets a replay. Not a label-version change. An ML feature built on it would be a new arm needing a retrain.
- **B. Replace the label's tax** with the same-lap Σ cost_i, roughly 3x higher on laps spent following. **LABEL-VERSION CHANGE.** It moves `dirty_air_tax_s`, `cumulative_dirty_air_tax_race_s`, `driver_skill_residual_s`, the lap and sector residuals, and `cumulative_dirty_air_tax_s` in `fct_stint_features`. It also needs a `label_stability_baseline` retake, a CO-18-style retrain, and updated app pages, page summaries and docs.
- **B-lite.** Keep lap totals and split them across sectors by exposure. Sector labels only: **LABEL-VERSION CHANGE**.

## 6. Phases (about 16-24 weeks)

| Phase | Weeks | Gate to continue | Stop if | Owner decides |
|---|---|---|---|---|
| 0 Audit: sample spacing per season, NULL and lapped shares, FastF1 gap vs crossing-time gap, `driver_ahead` vs own ordering, marshal-sector feasibility | 2-3 | ≥90% of green samples valid. Gap disagreement under 0.1 s (median) for gaps under 2 s | Gap unreliable under 1 s, or spacing differs by season | Accept the CO-17 dependency. Approve marshal-sector ingestion |
| 1 Tables + descriptives: two dbt models, tests (total order, pit exclusion, blue-flag agreement), loss-vs-gap curves | 3-4 | Build takes minutes. Loss rises as the gap shrinks and is flat above 3 s | No gap gradient | Micro-sector grain. Seconds or metres |
| 2 Identification: pre-registration, fit, P1-P3, era split (2018-21 vs 2022+) | 4-6 | β(<1 s) CI excludes 0. P1 below β/3 with a CI that includes 0. P2 and P3 pass | P1 ≈ β, or the sign flips by era | "Causal" or "adjusted traffic cost" |
| 3 Fit + validation: held-out season, plus honesty tests (`assert_lap_7term_identity`, `assert_no_future_leakage`, `assert_prior_season_labels_frozen`, `assert_proximity_agrees_with_blue_flags`, `assert_dirty_air_tax_null_only_when_unmeasured`) | 3-4 | Out-of-sample gain. Lap totals between 0.331 and the 0.881 lap-share fit | No out-of-sample gain | Path A, B or B-lite |
| 4 Label + app | A: about 3. B: 6 or more | Tests green, label diff reviewed | Unacceptable churn | Ship |

## 7. Risks and stop conditions

- It may measure battling or tyre saving, not aero (P1 and P3 guard against this).
- Regulation eras differ (2022 ground effect, no DRS in 2026), so fit by era.
- At 68M rows, the byte-stability oracle needs ROUND and total ordering throughout.
- Path B moves every downstream number.
- 2018 has two races missing, and dev.duckdb is stale.

Stop on any of: a failed placebo, an unreliable gap, unexplained instability across eras, or no held-out gain.

## 8. UNVERIFIED

- Sample spacing beyond the one race measured.
- Whether position-row `speed_kph` is native or interpolated.
- Whether `distance_to_ahead_m` is accurate (2 m to 1.9 km, never checked against timing).
- Whether `DriverAhead` includes lapped cars.
- Whether DRS code 8 is reliable, including in 2018.
- Whether FastF1 marshal-sector data exists for 2018-2020.
- Whether `telemetry.schema.json` covers sessiontime, x, y, status and driverahead (it lists only 10 fields).
- The W11 probe's precision (no standard errors), and whether 0.09-0.10 s survives the section 1 drops.
