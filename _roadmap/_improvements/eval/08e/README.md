# 08e Evaluation — Thermal-proxy stint baseline reaches forward

## Status
**GATED** — all six gate steps complete, ready for human decision on landing.

## The Problem
`int_lap_thermal_proxy.stint_baseline_agg` scored 55.92% of training rows against laps that had not yet run. Two verified reaches:
1. **Forward reach:** Median pools laps 1..cutoff, mean reach 4.65 laps (max 45), 100% of lap_2 rows at mean 11.83 laps
2. **Label-derived window:** cutoff = CEIL(stint_length_actual × 0.60), and stint_length_actual ≡ remaining_stint_life_laps numerator (r=1.0 on 121,193 rows)

The feature's sign inverts under production: corr(push_residual, remaining_stint_life) is **−0.1231** (contaminated, BLOCK) vs **+0.0315** (contaminated, TRAILING); **−0.1191** vs **+0.1197** on next_5_lap_cumulative_jump_s at lap_in_stint≤4. Not noise—a fundamental sign flip.

## The Fix
Rebuild `stint_baseline_pace` as an expanding median over valid laps **strictly before** the scored lap, with min_observations=1 floor. Drop `stint_length_actual` from the cutoff entirely.

## Work Completed

### Materiality (2026-09-09)
Position-matched on lap_in_stint (21 strata, n=85,693), the BLOCK→TRAILING swing clears all three families:
- Degradation: −0.0350 [−0.0633, −0.0073], p=0.010
- Cliff P(0–2): −0.0357 [−0.0518, −0.0230], p=0.000
- Stint-life: +0.1055 [+0.0361, +0.1776], p=0.001

Unlike 02a, this is **not the cheap case** — the contamination inverts the feature, not merely adds noise.

### Rebuild (2026-09-09)
- `trailing_median('lap_time_s', ['stint_id'], ['lap_in_stint'], min_observations=1, valid_condition='is_valid_lap')`
- Coverage cost: 99.688% → 98.275% (−1.41pp)
- Correlations: deg +0.0867→+0.2031, life −0.1041→+0.0738, cliff −0.0239→+0.0354
- `baseline_observations_n` ships in mart contract, deliberately not in FEATURE_COLUMNS
- `assert_no_future_leakage` extended and verified to fire: 145,934 rows against old definition, 0 against rebuild

### Gates (Steps 1–7, 2026-09-09 + re-read 2026-09-17)

**Step 1 (instrument check):** Reproduce published v11 exactly on reversion. ✅ (all five headlines bit-identical to <1e-9)

**Steps 2–4 (add-ablation + permutation-null):** Family T clears on **all five targets** with information gains:
- p10 pinball: −0.0530055 (4.21× floor, info 5.27×)
- p50 pinball: −0.0808530 (8.98× floor, info 8.77×)
- p90 pinball: −0.0170216 (1.07× floor, info 1.35×)
- cliff macro F1: +0.0141401 (2.41× floor, info 2.43×)
- stint-life AFT nloglik: −0.0336961 (4.37× floor, info 3.93×)

**Step 5:** `features.py --check` CLEAN on all three audits (33 features, fingerprint 26345ce7)

**Steps 6–7:** Design pre-declared; e-values within-item: 35.91 / 35.46 / 33.36 / 31.16 / 30.03 (all reject e-BH at α=0.05, within 15% of ceiling).

**Re-read on v12/08m substrate (2026-09-17):** Steps 1–5 and 7 re-run on the rebuilt target where the label values moved (−1.8793s → −0.3946s). Family T **still clears all five**, information term larger than total every time:
- p10: +0.0664552 (9.95× floor, info 10.42×) — p90 went from narrow (1.07×) to solid (3.39×)
- p50: +0.0676244 (6.06× floor, info 6.32×)
- p90: +0.0312513 (3.39× floor, info 3.79×)
- cliff: +0.0166691 (3.84× floor, info 3.41×)
- life: +0.0272887 (4.46× floor, info 4.00×)

Negative controls recorded (including 3.282 on p10, which is the largest control in the set).

## Definition of Done
✅ `known_leak` entry gone from `transform/models/intermediate/schema.yml` (zero real entries anywhere; thermal proxy has no exemption block)
✅ Family T deltas reported on both substrates (2026-09-09 and v12/08m re-read)
✅ All six gate steps complete (plus step 7 e-values with MC validity)

## Artefacts
- `08e_thermal_family_arms.json` (23 KB, 2026-09-17 07:22 UTC) — all five targets with per-seed fits, e-value construction, Monte Carlo validity check, explicit `not_comparable_to` barring subtraction from 2026-09-09 table
- `08e_thermal_family_arms.log` — generation log from `scripts/arms_08e_thermal_family.py` (untracked)

## Open Question
**Decision D3:** "Land 08e + 08f?" This bundled them because "their deltas were measured against the target 08m superseded and must be re-read first."

**08e half:** Re-read is done. Family T clears on v12. Ready to land.

**08f half:** No re-read done. Moreover, `cliff_candidate_flag` (the only ablation target for family C) was pruned by 08j, so the 2026-09-09 family C measurement is no longer runnable on the current contract.

**Proposal:** Land 08e separately. For 08f, decide whether to:
- Re-scope to measure only 08f-1 (survival-weight change) without family C ablation
- Close 08f with a note that its ablation target vanished
- Re-read the landscape and measure differently

This lets you see the thermal contribution in isolation before taking on the circuit-interaction question.

## Next Steps (for new chat)
1. Decide D3 split: land 08e now, rule on 08f separately
2. Update `build-log.json`: mark 08e LANDED, advance pointer, note re-read completion, correct D3 context
3. If landing, update model card, docs snippets, export models (standard downstream)
4. Caveat: `stint_life_regressor` arm uses current params; re-read after 10e like all stint-life numbers

## Files in This Folder
- `README.md` — this file
- `08e_thermal_family_arms.json` — artefact with all fits and e-values
- `08e_thermal_family_arms.log` — generation log
- Full spec lives in `work/08-foundations-repair.md` (lines 162–879 cover 08e + 08f + re-read)
