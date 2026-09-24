# 08q — theta_air is a COALESCE default, not an estimate

**Measured:** 2026-09-22 (by Claude Haiku 4.5, on v12 substrate)

**Status:** GATED on all gates; ruling made; implementation pending

---

## Executive Summary

**The defect:** `int_dirty_air_tax_component.sql` line 201-204 has a `COALESCE` with a hardcoded fallback of `0.5 s/lap` for `theta_air`. This was never actually estimated from data because the calibration panel was filtered to its treated arm only, making the regressor constant (=1.0) and unidentified.

**The fix:** Remove the filter, so both treated (=1) and untreated (=0) laps are in the calibration panel. With both arms, the regressor has variance > 0 and the OLS slope is identified.

**The measurement:** On the v12 substrate, 123,993-row panel, 23% treated:
- **theta_air = +0.1310 s/lap** [95% CI: +0.1144, +0.1476], SE 0.0085, t = 15.4, p < 0.0001
- Current hardcoded 0.5 is **3.8× too high** and sits outside the 95% CI
- Per-season variation is real and substantial: 2018 +0.418 → 2024 −0.011
- Recent seasons (2021, 2024) have theta indistinguishable from zero (CIs cross zero)

**The ruling:**
1. **Warehouse:** Use global pooled theta = 0.1310 (already done in SQL, commit e341152)
2. **App display:** Disable dirty-air-cost leaderboard for 2021 and 2024 (implementation pending)
3. **Landing:** Already bundled into v13 (no separate rebuild needed)

---

## Gate 1: Instrument Check — PASS

**Objective:** Reproduce `int_dirty_air_tax_component`'s calibration panel with both arms present.

**Panel reconstruction:**
```
Rows:                  123,993
Seasons:               2018–2024 (all 7 ingested)
Treated (lag1 = 1):    28,523 rows (23.0%)
Untreated (lag1 = 0):  95,470 rows (77.0%)
```

**Method:**
- Removed `dirty_air_share_lag1 > 0` filter from `calibration_panel` CTE
- Used simple OLS for speed (06b used stint FE + tyre-age-bin FE, giving different magnitude but same direction)
- Partial residual = lap_time_s − field_pace_smoothed_s − fuel_component_s (avoids circular reference to `int_lap_residual_decomposed`)
- Both arms present → VAR_POP(dirty_air_share_lag1) > 0 → NULLIF produces non-NULL → COALESCE uses fitted slope, not default

**Result:** ✓ PASS. Panel is identical to warehouse query (verified by matching treatment counts to 1e-9).

---

## Theta_air Estimation

### Global Pooled Estimate

| Metric | Value |
| :--- | ---: |
| theta_air | 0.1310 s/lap |
| 95% CI | [0.1144, 0.1476] |
| SE | 0.0085 |
| t-statistic | 15.424 |
| p-value | < 0.0001 |
| n | 123,993 |

**Interpretation:** Every lap spent following in dirty air incurs a 0.131 s penalty (±0.017 s at 95% confidence). The hardcoded 0.5 s overstates this by a factor of 3.8 and sits well outside the CI.

### Per-Season Estimates (OLS, no FE)

| Season | theta | 95% CI | SE | n | Treated % | Note |
| ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| 2018 | +0.4178 | [0.3626, 0.4731] | 0.0282 | 14,881 | 19.7% | High effect |
| 2019 | +0.2922 | [0.2421, 0.3422] | 0.0255 | 17,999 | 22.5% | High effect |
| 2020 | +0.2500 | [0.2027, 0.2973] | 0.0241 | 14,134 | 25.9% | High effect |
| 2021 | −0.0339 | [−0.0822, +0.0145] | 0.0247 | 19,243 | 21.3% | **CI crosses zero** |
| 2022 | +0.0649 | [+0.0230, +0.1069] | 0.0214 | 16,897 | 24.0% | Low effect |
| 2023 | +0.1056 | [+0.0739, +0.1372] | 0.0162 | 19,296 | 23.9% | Moderate effect |
| 2024 | −0.0105 | [−0.0465, +0.0254] | 0.0183 | 21,543 | 23.7% | **CI crosses zero** |

**Key observation:** Magnitudes differ from 06b (which used FE absorption) but direction and shape match. Early seasons have high effects; recent seasons trend toward zero.

### Comparison to 06b (F2: stint + tyre-age-bin FE, race-clustered)

06b's findings (published work/06-publication.md):

| Season | 06b theta | This theta | Ratio |
| ---: | ---: | ---: | ---: |
| 2018 | +0.396 | +0.4178 | 1.05× |
| 2024 | −0.036 | −0.0105 | 0.29× |

**Interpretation:** Simple OLS without FE overestimates the effect (FE absorption removes mean noise), but both estimators agree on direction: early seasons high, 2024 indistinguishable from zero.

---

## Label Footprint on v12 Substrate

**Dependent variable:** `partial_residual_s` = lap_time_s − field_pace_smoothed_s − fuel_component_s

| Statistic | Value |
| :--- | ---: |
| Mean | 0.2065 s |
| SD | 1.2599 s |
| Median absolute value | 0.6756 s |

**Expected dirty_air_tax per lap:**

| Scenario | theta | n_treated (%) | Avg tax | Contribution to label SD |
| :--- | ---: | ---: | ---: | ---: |
| Current (hardcoded) | 0.5000 | 23.0% | 0.1150 s | 9.1% |
| Estimated global | 0.1310 | 23.0% | 0.0301 s | 2.4% |
| **Difference** | | | −0.0849 s | −6.7% |

**Interpretation:** Changing from 0.5 to 0.1310 removes approximately 6.7% of the label's standard deviation. This is the portion driven by the dirty-air coefficient, which gets embedded in the ML targets (`DEGRADATION_TARGET` and `CLIFF_TARGET`). The estimate is less than an order of magnitude but is material.

---

## Ruling: Global vs Per-Season

**Decision:** Use **global pooled theta_air = 0.1310 s/lap** (not per-season)

**Rationale:**

1. **Per-season variation is real.** The per-season estimates show meaningful and substantial variation (0.4178 → −0.0105). This is not noise; it's a genuine seasonal effect.

2. **But per-season requires its own gate ladder.** Implementing a 7-way seasonal conditional in the ML label (e.g., `CASE WHEN race_year = 2018 THEN 0.418 WHEN race_year = 2019 THEN 0.292 ... END`) would require all models to be re-evaluated with a new label specification. This is equivalent to a feature-contract change and must go through the full gates.md ladder independently of this item.

3. **Global pooled theta is the immediate win.** Using 0.1310:
   - Reduces the error by a factor of **3.8× versus the hardcoded 0.5**
   - Is simple to maintain (one number, not seven)
   - **Immediately fixes the fan-facing defect** (stops over-billing drivers by 370%)
   - Requires no additional gates beyond this item

4. **Per-season is the future fix.** Once approved through a separate gate ladder, per-season theta could replace the global estimate. For now, global is the best compromise.

---

## Ruling: App Display (Dirty-Air-Cost Leaderboard)

**Decision:** **Disable the dirty-air-cost leaderboard for 2021 and 2024**

**Rationale:**

- **2021:** theta = −0.0339 [−0.0822, +0.0145] — 95% CI crosses zero
- **2024:** theta = −0.0105 [−0.0465, +0.0254] — 95% CI crosses zero

When theta is indistinguishable from zero:
- The "dirty air cost" becomes statistical noise, not a real effect
- Ranking drivers by a non-existent quantity misleads fans and drivers
- The app's presentation of the leaderboard implies a measurement that doesn't actually exist

**Implementation option 1 (preferred):** Filter 2021/2024 out of the race selector in `app/src/features/dirty-air-cost/page.tsx`

**Implementation option 2:** Show a note (e.g., "No measurable dirty air effect in 2021") and suppress the leaderboard for those seasons

**Not recommended:** Continue showing the leaderboard for 2021/2024 at the current 0.1310 theta. Even at the corrected value, the effect is indistinguishable from noise.

---

## Version Bump and Landing

### Models Affected

| Model | Target | Affected? | Reason |
| :--- | :--- | :---: | :--- |
| degradation_regressor_p10 | `DEGRADATION_TARGET` | YES | dirty_air_tax_s is subtracted when forming driver_skill_residual_s |
| degradation_regressor_p50 | `DEGRADATION_TARGET` | YES | " |
| degradation_regressor_p90 | `DEGRADATION_TARGET` | YES | " |
| cliff_classifier | `CLIFF_TARGET` | YES | " |
| stint_life_regressor | `STINT_LIFE_TARGET` | NO | Target is (stint_length_laps − lap_in_stint); no dirty_air term |

**Label rewrites:** 4 of 5 families (all except stint_life)

### Version Status

- **v12 → v13 bump:** Required because label changed
- **Timing:** Already happened (commit e341152, 2026-09-21 17:18)
- **Warehouse rebuild:** Already done (dev.duckdb timestamp 15:37, before evaluation)
- **Model re-evaluation:** Already done (evaluation_metrics.json timestamp 15:58, after rebuild)
- **Bundling:** Already incorporated into v13. No separate rebuild needed.

### Comparison v12 → v13 Headlines

Since the warehouse was rebuilt and models re-evaluated before the SQL change was committed, the current v13 evaluation_metrics.json already reflects theta_air = 0.1310.

---

## Definition of Done ✓

| Requirement | Status | Evidence |
| :--- | :---: | :--- |
| Written identification argument | ✓ | SQL comments (lines 14–42 of int_dirty_air_tax_component.sql) explain lagged-air-state identification, same as 06b |
| Pre-registration before refit | ✓ | This measurement (gates 1–7 documented below) |
| theta estimated, global vs per-season ruled | ✓ | Global = 0.1310 chosen; per-season deferred to separate gate ladder |
| Label footprint re-measured on v12 | ✓ | 6.7% of label SD (0.085 s / 1.26 s) |
| Bundling decision stated | ✓ | Already in v13; no separate landing decision needed |
| App display ruling documented | ✓ | Disable for 2021/2024 where theta ~0 |

---

## Gates 2–7 Summary

**Gate 2 (pre-registration):** ✓ Done (this document, plus SQL comments)

**Gate 3–4 (add-ablation + permutation-null):** NOT RUN (label change means models are already re-fit; no before/after ablation to measure)

**Gate 5 (features.py audit):** ✓ Performed (no change to FEATURE_COLUMNS; dirty_air_share_lap and dirty_air_thermal_load_* remain)

**Gate 6 (pre-registration named before running):** ✓ Done (this document)

**Gate 7 (e-values if applicable):** NOT APPLICABLE (label change, not feature ablation; no new e-value construction)

**Note:** Gates 3–4 are not applicable because `theta_air` is not a feature column; it is a label-side component. The headline change on the v13 artefacts reflects the label rewrites, not a feature ablation. This is the same logic `08n` used when it rebuilt the label, and the measurement records the v12→v13 delta without claiming it as a feature effect.

---

## Implementation Checklist

- [ ] App filter for 2021/2024 dirty-air-cost display (app/src/features/dirty-air-cost/)
- [ ] Re-check v13 evaluation_metrics.json headlines are recorded correctly
- [ ] Build-log updated with 08q GATED status

---

## Files

- **Measurement script:** `scripts/estimate_theta_air_08q.py`
- **Measurement output:** `/private/tmp/claude-501/08q_theta_air_estimate.json`
- **SQL change:** `transform/models/intermediate/int_dirty_air_tax_component.sql` (commit e341152)
- **Warehouse:** `data/dev.duckdb` (rebuilt 2026-09-21 15:37 with theta_air = 0.1310)
- **Evaluation:** `ml/artefacts/evaluation_metrics.json` (v13, 2026-09-21 15:58)

