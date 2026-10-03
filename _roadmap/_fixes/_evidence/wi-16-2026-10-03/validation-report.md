# WI-16b validation report

Generated 2026-10-03T15:37:21 on `data/dev.duckdb` (mtime 2026-10-03T15:17:21, git a038fce).
Car term: [{'fit_method': 'constructor_car_fe_isolation_hdfe_v2', 'fit_timestamp': '2026-09-29T21:50:06Z', 'n_car_terms': 1356, 'n_cells': 1619}].

Decisions use 2018-2024; 2025 is confirmation only. Thresholds are the WI doc's.

## V1

- **V1a_pure**: PASS (median_spearman=0.897)
- **V1a_tactical**: NOT_APPLICABLE (The tactical rating was cancelled on 2026-09-28 (WI-16b); this check tests it only.)
- **V1b**: FAIL (median_pearson=0.916; 2021-22=0.603 vs required >= 0.652)
- **V1c**: PASS (ratio=0.796; ci95=[0.463, 1.612])

## V2

- **V2a**: PASS (correlation=0.054)
- **V2b**: FAIL (max_abs_mean_diff_s=0.910; worst 2018 SUPERSOFT-MEDIUM n=21)
- **V2c_i**: NOT_APPLICABLE (The tactical rating was cancelled on 2026-09-28 (WI-16b); this check tests it only.)
- **V2c_ii**: PASS (top tercile spearman=0.833 (n=44), bottom tercile spearman=0.891 (n=42))
- **V2d**: REPORT (within_driver_race_mean_diff_s=-0.098)
- **V2e**: PASS (median_spearman_field=0.608; median_spearman_massey=0.711)

## V3

- **V3a**: PASS (correlation=-0.040)
- **V3b**: MARGINAL (correlation=-0.012; dirty_minus_clean_gap_s=-0.059; gap_ci95=[-0.090, -0.031])
- **V3c**: PASS (spearman=0.730)
- **V3d**: PASS (MAE model=0.400, base_car_traffic=0.524, base_last_delta=0.655; gain base_car_traffic=0.124 [0.109, 0.139], base_last_delta=0.255 [0.222, 0.288])
- **V3_tier3_coverage**: PASS (share_ge1_peer=0.864)

## V4

- **V4a**: FAIL (implied_total_s_per_kg=0.020; seed 0.025 + residual -0.0052 s/kg)
- **V4b**: FAIL (fuel_coef_s_per_kg=0.006)
- **V4c**: FAIL (softer faster by (s): 2018: -0.019, 2019: 0.298, 2020: 0.310, 2021: 0.149, 2022: 0.546, 2023: 0.081, 2024: 0.135, 2025: 0.162)

## V5

- **V5a**: PASS (lag1_autocorr=0.195)
- **V5b**: PASS (median_ratio=0.323)
- **V5d_autocorr**: PASS (lag1_autocorr=0.371)
- **V5d_jitter**: PASS (median_ratio=0.336)
- **V5c**: NOT_APPLICABLE (The tactical rating was cancelled on 2026-09-28 (WI-16b); this check tests it only.)
- **V5_sign_flips_report**: REPORT (share_stints_2plus_sign_changes=0.176)

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
| 2018 | 0.419 | +0.538 | -0.879 | -0.080 |
| 2019 | 0.144 | +0.132 | -0.886 | -0.105 |
| 2020 | 0.194 | +0.136 | -0.874 | -0.048 |
| 2021 | 0.207 | +0.143 | -0.590 | -0.032 |
| 2022 | 0.181 | +0.049 | -0.491 | -0.042 |
| 2023 | 0.251 | +0.132 | -0.381 | -0.113 |
| 2024 | 0.323 | +0.201 | -0.242 | -0.119 |
| 2025 | 0.339 | +0.201 | -0.433 | -0.246 |

## Worked examples

- **VER_vs_HAM_2021_8**: expected +0.240/57, measured +0.233/54 (within tolerance: True); split pace gap +0.444, car -0.227, traffic +0.012
- **HAM_vs_VER_2021_19**: expected +0.178/41, measured -0.041/18 (within tolerance: False); split pace gap -0.523, car +0.673, traffic -0.184
- **VER_vs_PER_2023_2**: expected -0.459/37, measured -0.459/37 (within tolerance: True); split pace gap -0.370, car +0.000, traffic -0.089

## Method scores

- **pure**: 0.000 (F); weighted score before the critical rule 0.724; critical fails ['V1.V1b']; 10/16 sub-checks PASS. Test-level reading: 0.724 (C).
  - V1 (weight 2.0): 0.667
  - V2 (weight 2.0): 0.750
  - V3 (weight 1.0): 0.875
  - V4 (weight 0.5): 0.000
  - V5 (weight 1.0): 1.000
- **relative**: 0.857 (B); weighted score before the critical rule 0.857; critical fails none; 3/4 sub-checks PASS. Test-level reading: 0.857 (B).
  - V3_tier3 (weight 2.0): 1.000
  - V4 (weight 0.5): 0.000
  - V5 (weight 1.0): 1.000
- **tactical**: cancelled
