# 08e Measurements — Materiality, Gates, Re-read

## Materiality (2026-09-09)
Position-matched on `lap_in_stint` (21 strata holding ≥300 rows on both sides, n=85,693), the swing in feature correlation when switching from BLOCK to TRAILING baseline:

| target | swing, contaminated | swing, control | matched difference | 95% CI | one-sided p |
|:---|---:|---:|---:|:---|---:|
| `next_5_lap_cumulative_jump_s` | −0.0317 | +0.0033 | **−0.0350** | [−0.0633, −0.0073] | 0.010 |
| `laps_until_cliff_class` (P(0–2)) | −0.0316 | +0.0042 | **−0.0357** | [−0.0518, −0.0230] | 0.000 |
| `remaining_stint_life_laps` | +0.1310 | +0.0255 | **+0.1055** | [+0.0361, +0.1776] | 0.001 |

**Sign inversions** (the critical finding):

| population | n | corr(`push_residual`, y) BLOCK | TRAILING |
|:---|---:|---:|---:|
| `remaining_stint_life_laps`, contaminated rows | 52,922 | **−0.1231** [−0.1504, −0.0943] | **+0.0315** [−0.0231, +0.0897] |
| `remaining_stint_life_laps`, control rows | 56,982 | +0.0945 [+0.0580, +0.1373] | +0.1251 [+0.0914, +0.1639] |
| `next_5_lap_cumulative_jump_s`, `lap_in_stint <= 4` | 7,701 | **−0.1191** | **+0.1197** |
| `next_5_lap_cumulative_jump_s`, `lap_in_stint >= 5` | 113,492 | +0.1984 | +0.2490 |

**Minimum-observation floor pricing** (BLOCK coverage 99.69%):

| floor | coverage | vs BLOCK | corr(pr, deg) | corr(pr, cliff) | corr(pr, life) |
|---:|---:|---:|---:|---:|---:|
| BLOCK | 99.69% | — | +0.0867 | −0.0239 | −0.1041 |
| **n ≥ 1** | **98.28%** | **−1.41pp** | **+0.2031** | **+0.0354** | **+0.0738** |
| n ≥ 2 | 96.20% | −3.49pp | +0.2324 | +0.0373 | +0.0702 |
| n ≥ 3 | 90.87% | −8.82pp | +0.2519 | +0.0315 | +0.0627 |
| n ≥ 5 | 80.60% | −19.09pp | +0.2539 | +0.0288 | +0.0652 |

→ Recommend floor n ≥ 1: costs 1.41pp coverage, **raises** marginal correlation on all three targets.

---

## Gates 2–4 on Original Substrate (2026-09-09)

**Family T** (four thermal columns: push_residual, cumulative_push_load_surface, cumulative_push_load_bulk, surface_bulk_ratio):

| target | metric | A (no T, no C) | A+T | delta | ×floor | capacity | information | ×floor |
|:---|:---|---:|---:|---:|---:|---:|---:|---:|
| `degradation_regressor_p10` | pinball | 0.5829013 | 0.5298958 | **−0.0530055** | 4.21× | +0.0133784 | −0.0663839 | **5.27×** |
| `degradation_regressor_p50` | pinball | 1.1144292 | 1.0335762 | **−0.0808530** | 8.98× | −0.0019026 | −0.0789505 | **8.77×** |
| `degradation_regressor_p90` | pinball | 0.5918152 | 0.5747936 | **−0.0170216** | 1.07× | +0.0043156 | −0.0213373 | **1.35×** |
| `cliff_classifier` | macro F1 | 0.3567748 | 0.3709149 | **+0.0141401** | 2.41× | −0.0001629 | +0.0143030 | **2.43×** |
| `stint_life_regressor` | AFT nloglik | 2.0224465 | 1.9887504 | **−0.0336961** | 4.37× | −0.0033000 | −0.0302961 | **3.93×** |

**Family C** (`cliff_candidate_flag` — note: subsequently pruned by 08j):

| target | A | A+C | delta | ×floor | capacity | information | ×floor |
|:---|---:|---:|---:|---:|---:|---:|---:|
| `degradation_regressor_p10` | 0.5829013 | 0.5928065 | +0.0099053 | 0.79× | +0.0096350 | +0.0002702 | 0.02× |
| `degradation_regressor_p50` | 1.1144292 | 1.1116689 | −0.0027604 | 0.31× | −0.0027613 | +0.0000009 | **0.00×** |
| `degradation_regressor_p90` | 0.5918152 | 0.5933422 | +0.0015270 | 0.10× | −0.0003952 | +0.0019222 | 0.12× |
| `cliff_classifier` | 0.3567748 | 0.3576418 | +0.0008671 | 0.15× | +0.0008122 | +0.0000549 | 0.01× |
| `stint_life_regressor` | 2.0224465 | 2.0182955 | −0.0041510 | 0.54× | −0.0072889 | +0.0031380 | 0.41× |

---

## Re-read on v12/08m Substrate (2026-09-17)

**Family T re-measured** (32-column contract, cv_final_fold train 2018–2023 eval 2024):

| target | metric | A (28 cols) | A+T (32) | delta | ×floor | capacity | information | ×floor | E |
|:---|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `degradation_regressor_p10` | pinball | 0.5429193 | 0.4764641 | **+0.0664552** | 9.95× | −0.0031177 (−0.47×) | +0.0695730 | **10.42×** | 35.91 |
| `degradation_regressor_p50` | pinball | 1.0499831 | 0.9823587 | **+0.0676244** | 6.06× | −0.0028325 (−0.25×) | +0.0704569 | **6.32×** | 35.46 |
| `degradation_regressor_p90` | pinball | 0.5440975 | 0.5128462 | **+0.0312513** | 3.39× | −0.0036515 (−0.40×) | +0.0349028 | **3.79×** | 31.16 |
| `cliff_classifier` | macro F1 | 0.3357970 | 0.3524661 | **+0.0166691** | 3.84× | +0.0018800 (+0.43×) | +0.0147892 | **3.41×** | 30.03 |
| `stint_life_regressor` | AFT nloglik | 2.0186246 | 1.9913359 | **+0.0272887** | 4.46× | +0.0028524 (+0.47×) | +0.0244363 | **4.00×** | 33.36 |

**Negative controls** (shuffle vs shuffle, H0 true by construction):
- E = 0.493, 0.458, 1.220, 1.097 (four targets)
- p10 control E = 3.282 (largest in set, shares target with largest headline E of 35.91)

**Headline headline values** (instrument check, all five targets):
- p10 pinball: 0.4764640778
- p50 pinball: 0.9823587336
- p90 pinball: 0.5128462338
- cliff macro F1: 0.3524660979
- stint-life AFT nloglik: 1.9913358779

(Match published v12 to better than 1e-8)

---

## Key Qualitative Changes
- **p90:** was narrow (1.07× on original) → solid (3.39× on v12)
- **p10 capacity:** was anomaly (+1.06× on original) → inside floor (−0.47× on v12)
- **All five:** information term larger than total on v12 (−0.25× to −0.47× capacity, information 3.41× to 10.42×)

---

## Caveats
1. `stint_life_regressor` arm uses params `10d`/`10e` are expected to move — re-read after 10e
2. Row count moved from 121,193 to 119,822 via `is_training_eligible` gate (population, not disagreement)
3. Instrument check on rebuilt target (step 1) passed; steps 2–4 run on AFTER substrate only (no 08e/08f decomposition)
