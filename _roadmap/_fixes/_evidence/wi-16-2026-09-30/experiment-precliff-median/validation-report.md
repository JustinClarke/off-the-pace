# WI-16b validation report

Generated 2026-09-30T01:36:38 on `/private/tmp/claude-501/-Users-justin-github-off-the-pace/7cb13d4e-adf0-45bf-bb69-9d69959b58d8/scratchpad/w33/variant/dev.duckdb` (mtime 2026-09-30T01:33:57, git 024e342).
Car term: [{'fit_method': 'constructor_car_fe_isolation_hdfe_v2', 'fit_timestamp': '2026-09-29T21:33:54Z', 'n_car_terms': 1356, 'n_cells': 1619}].

Decisions use 2018-2024; 2025 is confirmation only. Thresholds are the WI doc's.

## V1

- **V1a_pure**: PASS (median_spearman=0.899)
- **V1a_tactical**: NOT_APPLICABLE (The tactical rating was cancelled on 2026-09-28 (WI-16b); this check tests it only.)
- **V1b**: FAIL (median_pearson=0.908; 2021-22=0.631 vs required >= 0.648)
- **V1c**: PASS (ratio=1.068; ci95=[0.567, 1.587])

## V2

- **V2a**: PASS (correlation=0.017)
- **V2b**: FAIL (max_abs_mean_diff_s=0.654; worst 2019 SOFT-HARD n=81)
- **V2c_i**: NOT_APPLICABLE (The tactical rating was cancelled on 2026-09-28 (WI-16b); this check tests it only.)
- **V2c_ii**: PASS (top tercile spearman=0.868 (n=44), bottom tercile spearman=0.886 (n=42))
- **V2d**: REPORT (within_driver_race_mean_diff_s=-0.101)
- **V2e**: PASS (median_spearman_field=0.611; median_spearman_massey=0.744)

## V3

- **V3a**: FAIL (correlation=0.173)
- **V3b**: MARGINAL (correlation=0.030; dirty_minus_clean_gap_s=-0.071; gap_ci95=[-0.098, -0.045])
- **V3c**: PASS (spearman=0.728)
- **V3d**: PASS (MAE model=0.390, base_car_traffic=0.515, base_last_delta=0.704; gain base_car_traffic=0.125 [0.113, 0.137], base_last_delta=0.314 [0.287, 0.341])
- **V3_tier3_coverage**: PASS (share_ge1_peer=0.904)
- **V3_tier3_age_adjustment**: FAIL (reduction=-0.034)

## V4

- **V4a**: FAIL (implied_total_s_per_kg=0.020; seed 0.025 + residual -0.0052 s/kg)
- **V4b**: FAIL (fuel_coef_s_per_kg=0.003)
- **V4c**: PASS (softer faster by (s): 2018: 0.086, 2019: 0.330, 2020: 0.333, 2021: 0.162, 2022: 0.540, 2023: 0.051, 2024: 0.105, 2025: 0.139)

## V5

- **V5a**: PASS (lag1_autocorr=0.155)
- **V5b**: PASS (median_ratio=0.455)
- **V5d_autocorr**: PASS (lag1_autocorr=0.389)
- **V5d_jitter**: PASS (median_ratio=0.314)
- **V5c**: NOT_APPLICABLE (The tactical rating was cancelled on 2026-09-28 (WI-16b); this check tests it only.)
- **V5_sign_flips_report**: REPORT (share_stints_2plus_sign_changes=0.202)

## V6

- **V6a**: NOT_APPLICABLE (The tactical rating was cancelled on 2026-09-28 (WI-16b); this check tests it only. V6 carries no weight for pure or relative in the matrix.)
- **V6b**: NOT_APPLICABLE (The tactical rating was cancelled on 2026-09-28 (WI-16b); this check tests it only. V6 carries no weight for pure or relative in the matrix.)
- **V6c**: NOT_APPLICABLE (The tactical rating was cancelled on 2026-09-28 (WI-16b); this check tests it only. V6 carries no weight for pure or relative in the matrix.)

## Coverage

- Driver-races without pure: 390 of 3102 (12.6%)
  - car term not estimated: only one of the team's drivers has pre-cliff laps in the race: 127
  - car term unidentified: team is an island in the era's teammate network: 263
  - island Alfa Romeo 2022-2023: 78 driver-races (BOT, ZHO)
  - island Haas F1 Team 2018-2021: 139 driver-races (FIT, GRO, MAG, MAZ, MSC)
  - island Kick Sauber 2024-2024: 46 driver-races (BOT, ZHO)

## Season levels

| season | cliff share | y pre-cliff | y cliff | mean race pure |
| --: | --: | --: | --: | --: |
| 2018 | 0.419 | -0.077 | -2.805 | +0.152 |
| 2019 | 0.144 | -0.011 | -1.869 | +0.062 |
| 2020 | 0.194 | -0.016 | -2.064 | +0.117 |
| 2021 | 0.207 | -0.025 | -1.899 | +0.152 |
| 2022 | 0.181 | -0.055 | -1.276 | +0.078 |
| 2023 | 0.251 | -0.007 | -1.661 | +0.051 |
| 2024 | 0.323 | -0.006 | -1.545 | +0.078 |
| 2025 | 0.339 | -0.015 | -1.721 | +0.012 |

## Worked examples

- **VER_vs_HAM_2021_8**: expected +0.240/57, measured +0.229/54 (within tolerance: True); split pace gap +0.419, car -0.202, traffic +0.012
- **HAM_vs_VER_2021_19**: expected +0.178/41, measured +0.178/36 (within tolerance: False); split pace gap -0.333, car +0.667, traffic -0.156
- **VER_vs_PER_2023_2**: expected -0.459/37, measured -0.459/37 (within tolerance: True); split pace gap -0.370, car +0.000, traffic -0.089

## Method scores

- **pure**: 0.000 (F); weighted score before the critical rule 0.705; critical fails ['V1.V1b']; 10/16 sub-checks PASS. Test-level reading: 0.705 (C).
  - V1 (weight 2.0): 0.667
  - V2 (weight 2.0): 0.750
  - V3 (weight 1.0): 0.625
  - V4 (weight 0.5): 0.250
  - V5 (weight 1.0): 1.000
- **relative**: 0.000 (F); weighted score before the critical rule 0.714; critical fails ['V3.V3_tier3.V3_tier3_age_adjustment']; 4/5 sub-checks PASS. Test-level reading: 0.714 (C).
  - V3_tier3 (weight 2.0): 0.500
  - V4 (weight 0.5): 1.000
  - V5 (weight 1.0): 1.000
- **tactical**: cancelled
