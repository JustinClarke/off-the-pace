# ML layer reset plan (branch ml-fresh-start)

## 1. Verified current state
- **v14 is served, not v6.** `app/public/models/manifest.json` has `model_version: "v14"` and lists only the five `*_v14.onnx` files. `app/src/ml/flagChance.test.ts:69-70` pins the lookup to that version. The comment at `ml/src/export_onnx.py:39` ("Production serves v6") is out of date (it was written during v13). Caveat: the app fetches from `${DATA_CDN_BASE}/models` (`app/src/ml/manifest.ts:134,140`), so the CDN copy still needs a check.
- v14 was trained on 2018-2025 with 2026 as the holdout (manifest provenance). `ml/models/manifest.json` is the same v14 file.
- v15, v15ipw and v15uni exist. **v16 is the next free name.**
- The holdout is pinned to 2026 (`ml/src/holdout_config.py:13`). CV is expanding-window only (`ml/src/train.py:208-225`). `ml/src/flag_chance.py:240` reuses that fold code. There is no leave-one-season-out (LOSO) code.
- CO-17 also depends on **CO-16** (`wi/CO-17-trusted-dev-rebuild.md:3`).
- The CO-15 fix is in `_evidence/co-15-2026-10-22/proposed_fix_wear_hold.diff`. It does not apply cleanly. There is a third call site at `int_pit_strategy_cost_curve.sql:202`.

## 2. Ordered build steps
| # | Step | Files | Gate | Owner? |
|---|---|---|---|---|
| 0 | Owner rulings | - | Written answers | **Yes** |
| 1 | CO-09 stint label (D5/D6 censoring, D4 key) | `int_stint_end_regime.sql`, stint features, `ml/src/schema.py`, `ml/README.md` | dbt tests on touched models; row change per season and affected races listed | D4 |
| 2 | Re-apply CO-15 by hand, including the third call site | `compound_cliff_wear.sql`, `dbt_project.yml`, `int_pit_strategy_cost_curve.sql`, 2 tests | Matches the evidence diff; pit-cost curve still equals `int_compound_cliff_predicted` | No |
| 3 | CO-16 | per WI | `assert_sector_aggregates_to_lap` | Scope |
| 4 | CO-17 rebuild in its own scratch folder (copy named `dev.duckdb`) | `Makefile dbt-dev-full` | Full build green; honest-range test passes for Monaco 2024 | Run approval |
| 5 | LOSO fold scheme added beside `_season_folds` (expanding stays the default) | `train.py`, `flag_chance.py`, `ml/tests/` | Test: one held-out season per fold, never 2018, never 2026 for stint life | CD6, D3 |
| 6 | CO-14 stint-life test on LOSO | `evaluate.py`, `survival.py` | Per-fold metric table | No |
| 7 | CO-18 retrain as **v16**, with a guard against existing names; fix the `export_onnx.py:39` comment | `ml/src/*`, `ml/models/*_v16*` | Refuses an existing name; ONNX parity at 1e-5; manifest says v16 | D1 |
| 8 | Tests: `pytest ml/tests`, plus app vitest against a scratch copy of v16 | - | Green | No |
| 9 | Compare v16 with served v14 on the same folds | new files in `ml/artefacts/` | D2 rule | **Verdict** |
| 10 | Promote to `app/public/models` and the CDN in a **separate final commit** | `app/public/models/*` | Owner yes; CO-19 if stint life stays on v14 | **Yes** |

No step commits without owner approval (rule 4).

## 3. Decisions
**(a) Owner must decide. These are my recommendations, not rulings.**
1. **D4:** re-key `stint_id` everywhere, or add `tyre_run_id`. *Rec: `tyre_run_id`*, because it keeps the downstream and app keys stable. Blocks step 1.
2. **D2:** pass margin and fold rule. *Rec: v16 wins at least 4 of 6 folds, and no metric is worse than its fold standard deviation.* Blocks step 9.
3. **2025:** it has already steered model selection. Report it as "validation, not blind" (rec), or treat it as blind. Use 2026 as a drift check only. Blocks how step 9 is reported.
4. **D1:** refit both the v14 and v15 configs as v16a and v16b (rec), or only v15. Blocks step 7.
5. **D3/CD8:** *Rec: 2018 is never held out*, which follows CD2=C, so LOSO runs over 2019-2024. Confirm. Blocks step 5.
6. **Retrain the shipped model on 2018-2025 after the test?** *Rec: yes*, the same as v14. Blocks step 7.
7. **Same holdout rule for the other four models?** *Rec: yes.* Blocks steps 5 and 9.
8. **CD6:** *Rec: A, expanding window.* Blocks step 5.
9. **CO-16 on this branch?** *Rec: yes*, because CO-17 needs it. Blocks step 4.

**(b) Settled by reading the code. This is the only set I can close.**
- **v14 is served, not v6** (section 1).
- **No cliff-seed leakage:** `fit_compound_cliff.py:708-711` fits each season only on earlier seasons and never fits 2026. 2018 is in-sample (`:77`, CD2).
- **Next version is v16.**
- **LOSO is added alongside the old fold code, not swapped in,** so v14 and the flag-chance results stay reproducible.
- **The comparison runs on local files only,** and `app/public/models` stays unchanged until step 10.
- **Not settled:** which seasons the pooled `theta_air` (0.331, `transform/seeds/schema.yml:360`) was fitted on. This is a read-only check at the start of step 1, not an owner question.

## 4. Risks and what would change the plan
- If `theta_air` includes 2025, add a refit before step 4.
- If the CDN serves something other than v14, step 9 compares against what it actually serves.
- The per-model feature order (`export_onnx.py:35-38`) may need app code changes at step 10.
- If v16 fails D2, stint life may stay on v14 (CO-19), or nothing is promoted.
- If the CO-15 hand re-apply drifts from the evidence diff, the honest-range numbers will not reproduce.

## 5. Smallest next action after the owner answers
Do the `theta_air` read. Then write CO-09 with the D4 key the owner chose, run dbt tests on the touched models in a separate scratch folder, and report row changes per season. Do not commit.
