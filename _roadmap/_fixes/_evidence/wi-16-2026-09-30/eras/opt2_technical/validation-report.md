# WI-16b validation report

Generated 2026-09-30T02:43:02 on `/private/tmp/claude-501/-Users-justin-github-off-the-pace/7cb13d4e-adf0-45bf-bb69-9d69959b58d8/scratchpad/eras/dev.duckdb` (mtime 2026-09-30T02:41:27, git 024e342).
Car term: [{'fit_method': 'scratch_opt2_technical', 'fit_timestamp': 'scratch', 'n_car_terms': 562, 'n_cells': 1619}].

Decisions use 2018-2024; 2025 is confirmation only. Thresholds are the WI doc's.

## V1

- **V1a_pure**: PASS (median_spearman=0.929)
- **V1a_tactical**: NOT_APPLICABLE (The tactical rating was cancelled on 2026-09-28 (WI-16b); this check tests it only.)
- **V1b**: FAIL (median_pearson=0.988; 2021-22=n/a vs required >= 0.692)
- **V1c**: FAIL (ratio=1.621; ci95=[0.220, 2.893])

## V2

- **V2a**: PASS (correlation=0.096)
- **V2b**: FAIL (max_abs_mean_diff_s=0.566; worst 2022 SOFT-HARD n=36)
- **V2c_i**: NOT_APPLICABLE (The tactical rating was cancelled on 2026-09-28 (WI-16b); this check tests it only.)
- **V2c_ii**: PASS (top tercile spearman=0.799 (n=22), bottom tercile spearman=0.847 (n=21))
- **V2d**: REPORT (within_driver_race_mean_diff_s=-0.089)
- **V2e**: MARGINAL (median_spearman_field=0.704; median_spearman_massey=0.461)

## V3

- **V3a**: PASS (correlation=-0.110)
- **V3b**: PASS (correlation=-0.073; dirty_minus_clean_gap_s=-0.038; gap_ci95=[-0.073, -0.005])
- **V3c**: FAIL (spearman=0.684)
- **V3d**: PASS (MAE model=0.388, base_car_traffic=0.523, base_last_delta=0.611; gain base_car_traffic=0.136 [0.115, 0.156], base_last_delta=0.223 [0.172, 0.273])
- **V3_tier3_coverage**: PASS (share_ge1_peer=0.904)
- **V3_tier3_age_adjustment**: FAIL (reduction=-0.007)

## V4

- **V4a**: FAIL (implied_total_s_per_kg=0.020; seed 0.025 + residual -0.0052 s/kg)
- **V4b**: FAIL (fuel_coef_s_per_kg=0.006)
- **V4c**: PASS (softer faster by (s): 2018: 0.309, 2019: 0.228, 2020: 0.835, 2021: 0.465, 2022: 0.455, 2023: 0.110, 2024: 0.101, 2025: 0.287)

## V5

- **V5a**: PASS (lag1_autocorr=0.186)
- **V5b**: PASS (median_ratio=0.293)
- **V5d_autocorr**: PASS (lag1_autocorr=0.381)
- **V5d_jitter**: PASS (median_ratio=0.317)
- **V5c**: NOT_APPLICABLE (The tactical rating was cancelled on 2026-09-28 (WI-16b); this check tests it only.)
- **V5_sign_flips_report**: REPORT (share_stints_2plus_sign_changes=0.158)

## V6

- **V6a**: NOT_APPLICABLE (The tactical rating was cancelled on 2026-09-28 (WI-16b); this check tests it only. V6 carries no weight for pure or relative in the matrix.)
- **V6b**: NOT_APPLICABLE (The tactical rating was cancelled on 2026-09-28 (WI-16b); this check tests it only. V6 carries no weight for pure or relative in the matrix.)
- **V6c**: NOT_APPLICABLE (The tactical rating was cancelled on 2026-09-28 (WI-16b); this check tests it only. V6 carries no weight for pure or relative in the matrix.)

## Coverage

- Driver-races without pure: 1978 of 3102 (63.8%)
  - car term not estimated: only one of the team's drivers has pre-cliff laps in the race: 39
  - car term unidentified: team is an island in the era's teammate network: 1939
  - island Alfa Romeo 2022-2023: 78 driver-races (BOT, ZHO)
  - island Alfa Romeo Racing 2019-2021: 106 driver-races (GIO, KUB, RAI)
  - island AlphaTauri 2020-2021: 57 driver-races (GAS, KVY, TSU)
  - island Alpine 2021-2025: 80 driver-races (ALO, COL, DOO, GAS, OCO)
  - island Aston Martin 2021-2025: 71 driver-races (ALO, STR, VET)
  - island Ferrari 2018-2025: 175 driver-races (HAM, LEC, RAI, SAI, VET)
  - island Force India 2018-2018: 18 driver-races (OCO, PER)
  - island Haas F1 Team 2018-2025: 182 driver-races (BEA, FIT, GRO, MAG, MAZ, MSC, OCO)
  - island Kick Sauber 2024-2025: 88 driver-races (BOR, BOT, HUL, ZHO)
  - island McLaren 2018-2025: 180 driver-races (ALO, NOR, PIA, RIC, SAI, VAN)
  - island Mercedes 2018-2025: 280 driver-races (ANT, BOT, HAM, RUS)
  - island Racing Bulls 2025-2025: 2 driver-races (HAD, LAW)
  - island Racing Point 2018-2020: 65 driver-races (HUL, OCO, PER, STR)
  - island Red Bull Racing 2018-2025: 235 driver-races (ALB, GAS, PER, RIC, TSU, VER)
  - island Renault 2018-2020: 84 driver-races (HUL, OCO, RIC, SAI)
  - island Sauber 2018-2018: 33 driver-races (ERI, LEC)
  - island Toro Rosso 2018-2019: 56 driver-races (ALB, GAS, HAR, KVY)
  - island Williams 2018-2025: 149 driver-races (AIT, ALB, KUB, LAT, RUS, SAI, SIR, STR)

## Season levels

| season | cliff share | y pre-cliff | y cliff | mean race pure |
| --: | --: | --: | --: | --: |
| 2018 | 0.419 | +0.538 | -0.879 | -0.156 |
| 2019 | 0.144 | +0.132 | -0.886 | -0.249 |
| 2020 | 0.194 | +0.136 | -0.874 | +0.023 |
| 2021 | 0.207 | +0.143 | -0.590 | +0.003 |
| 2022 | 0.181 | +0.049 | -0.491 | -0.302 |
| 2023 | 0.251 | +0.132 | -0.381 | -0.257 |
| 2024 | 0.323 | +0.201 | -0.242 | -0.242 |
| 2025 | 0.339 | +0.201 | -0.433 | -0.220 |

## Worked examples

- **VER_vs_HAM_2021_8**: expected +0.240/57, measured +0.231/54 (within tolerance: True); split pace gap n/a, car n/a, traffic +0.012
- **HAM_vs_VER_2021_19**: expected +0.178/41, measured +0.147/36 (within tolerance: False); split pace gap n/a, car n/a, traffic -0.156
- **VER_vs_PER_2023_2**: expected -0.459/37, measured -0.459/37 (within tolerance: True); split pace gap n/a, car n/a, traffic -0.089

## Method scores

- **pure**: 0.000 (F); weighted score before the critical rule 0.583; critical fails ['V1.V1b', 'V1.V1c']; 9/16 sub-checks PASS. Test-level reading: 0.000 (F).
  - V1 (weight 2.0): 0.333
  - V2 (weight 2.0): 0.625
  - V3 (weight 1.0): 0.750
  - V4 (weight 0.5): 0.250
  - V5 (weight 1.0): 1.000
- **relative**: 0.000 (F); weighted score before the critical rule 0.714; critical fails ['V3.V3_tier3.V3_tier3_age_adjustment']; 4/5 sub-checks PASS. Test-level reading: 0.714 (C).
  - V3_tier3 (weight 2.0): 0.500
  - V4 (weight 0.5): 1.000
  - V5 (weight 1.0): 1.000
- **tactical**: cancelled
