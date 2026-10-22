# CO-19 — Mixed model versions: can stint life stay on v14 while the other four move?

**Group:** 1 data settled · **Depends on:** `CO-18` (the retrained models on the new label version) · **Blocks:** `AI-03` (the data freeze) · **Feeds:** `CD10` (which model version serves at launch). Raised 2026-10-22 on the owner's instruction (an invasive probe). Method rewritten 2026-10-22 on the owner's correction: no scratch copies; the probe works in the real folders and records everything in the repo.

**Not runnable yet.** It waits for `CO-18` (and so for `CO-17`'s trusted rebuild). It does not wait for `CO-14`. Set up only; no scenario has run.

**Sources (real folders the probe reads and may write):**

- `ml/src/schema.py` (`MODEL_VERSION_DEFAULT = "v14"`, `MART = fct_cliff_prediction_features`, `STINT_FEATURES = fct_stint_features`, `DUCKDB_PATH`, overridable by `ML_DUCKDB_PATH`), `ml/src/predict.py` (`--version`, writes `model_version` per row to `data/marts/mart_degradation_predictions.parquet`), `ml/src/features.py` (`load_scoring_frame`, `persist_encoders`), `ml/src/export_onnx.py` (ONNX export, per-feature-contract parity, writes `ml/models/manifest.json`), `ml/src/flag_chance.py` (writes `flag_chance_lookup.json` with one `model_version`).
- `ml/models/` (`manifest.json` and `encoders.json`: one of each, not versioned by file name; `*_v14.bst/.onnx` and the `CO-18` files beside them; `*_best_params.json`).
- `ml/artefacts/` (evaluation outputs; the probe writes nothing here unless a step names it).
- `transform/models/marts/fct_cliff_prediction_features.sql` and `fct_stint_features` (the feature tables the models read), in `data/dev.duckdb`. `mart_degradation_predictions` is **not** a dbt model: it is the parquet `ml/src/predict.py` writes to `data/marts/`, exported by `scripts/export_app_data.py` (`export_predictions_mart`).
- `Makefile` targets `app-models` (copies `ml/models/*_<manifest model_version>.onnx`, `manifest.json`, `encoders.json`, `model_card.json` to `app/public/models/`; one version for all five) and `app-data`.
- `app/public/models/` (committed: `manifest.json`, `encoders.json`, `model_card.json`, `flag_chance_lookup.json`, five `*_v14.onnx`).
- `app/src/ml/` (`manifest.ts`: one `model_version` field; `infer.ts`, `session.ts`, `featureVector.ts`, `verifyParity.ts`, `flagChance.ts`: drops the lookup when its `model_version` differs; `__fixtures__/`).
- `app/src/data/` (`manifest.ts`: the data manifest and `VITE_DATA_BASE` for running offline; `duckdb/`).
- Pages that show a model version or prediction: `app/src/features/degradation-simulator/` (`page.tsx`, `transform.ts`, `powerLaw.ts`), `app/src/features/model-metrics/page.tsx`, `app/src/features/blind-test-scoreboard/page.tsx`, `app/src/ui/methodology/Provenance.tsx`, `app/src/ui/layout/FeaturePage.tsx`.

## Ground rules

1. **Real folders, documented in the repo.** The probe runs in `ml/`, `transform/`, `app/`, `scripts/` and `data/` as each scenario needs. No scratch copies of the app or model folders. Everything it produces goes in `_roadmap/_ai-integration/_evidence/co-19-<run date>/` (the folder made at set-up, `co-19-2026-10-22/`, holds the set-up `PROVENANCE.txt`; a run on a later date makes its own folder and links back).
2. **`PROVENANCE.txt` in the run folder** lists: every command run, in order; `git rev-parse HEAD` and `git status --short` before and after; the data snapshot (path, size, modified time and sha256 of `data/dev.duckdb` and of the baseline predictions parquet); sha256 of `ml/models/manifest.json`, `ml/models/encoders.json` and every file in `app/public/models/` before, during each scenario, and after.
3. **Nothing is promoted and nothing ships.** No commit. `MODEL_VERSION_DEFAULT` stays `v14` at the end. No upload to the CDN. Files the probe changes in the working tree (`ml/models/manifest.json`, `ml/models/encoders.json`, `app/public/models/*`, `data/marts/mart_degradation_predictions.parquet`, `app/public/data/`) are put back at the end: tracked files with `git restore`, untracked outputs from the copies saved in step 0 below. The diff of what each scenario changed is saved in the evidence folder before it is put back. Promotion is the owner's call (`CD10`); the freeze (`AI-03`) still waits for this probe, the clean test (`CO-14`) and the retrain (`CO-18`).
4. **Rules before the first run.** The go/no-go and pass rules below are **drafts for the owner to change**. Before the first scenario runs they are copied, as final, into this item's note in the log and into `rules.txt` in the run folder, and not changed afterwards.

## Why

`CD10` option A has a fail branch: if the stint-life clean test (`CO-14`) fails, promote the retrain (`CO-18`) for the four models that pass and keep v14 for stint life. Nobody has checked that the project can serve that. What the code already shows:

- `ml/models/manifest.json` (copied to `app/public/models/`) carries **one** top-level `model_version`; there is no per-model version field. `app/src/ml/manifest.ts` reads that one field. `make app-models` copies only `*_<that version>.onnx`.
- One `encoders.json` serves all five models, and `CO-18` overwrites `ml/models/encoders.json` and `ml/models/manifest.json` in place. After the retrain, the v14 copies survive only in git (`HEAD`) and in `app/public/models/`.
- `CO-15` moves features the models read (`expected_compound_pace_s`, `compound_wear_gradient`, the cliff columns are in the feature union), so a v14 stint-life model fed new-label features may not get what it was trained on.
- `ml/src/predict.py` stamps one `--version` on every row. `flag_chance_lookup.json` carries one `model_version` and `flagChance.ts` hides the chance line when it does not match.
- The fact cards (`AI-01`) carry one `model_version`, read at export time. Under `CD10` option B the cards would mix label versions and must say so.

## Dependency

Waits for **`CO-18`** (as the log records): it needs the retrained boosters, ONNX files, manifest and encoders to exist, and `CO-18` follows `CO-17`, so the warehouse is the trusted new-label build. It does **not** wait for `CO-14`: the probe tests every promotion outcome, so it does not need to know which one `CO-14` produces, and it runs alongside it. It is **not** blocked by `CD10`: it is evidence for that ruling. The freeze (`AI-03`) waits on it, with `CO-14`, `CO-18` and `CD10` (`CD13`).

**Baseline it needs (check before `CO-17` runs if possible).** S4 and S5 compare against the old-label world. Available today: `data/marts/mart_degradation_predictions.parquet` (v14 predictions, 2026-09-22) and the v14 files in `app/public/models/` and git. The old-label feature tables are not kept anywhere: `CO-17` overwrites `data/dev.duckdb`, and it keeps copies of label tables only. If an export of `fct_cliff_prediction_features` and `fct_stint_features` to parquet is taken before `CO-17` runs, the feature-shift measure (S4 step 3) can use it; otherwise the probe measures the prediction shift only and says so. Note: `data/dev.duckdb` is already partly rebuilt by an earlier probe (2026-10-22 01:42), so any pre-`CO-17` copy must be described as that, not as clean v14.

## Step 0 (once, before any scenario)

1. Write the final rules into the log note and `rules.txt` (ground rule 4).
2. Record the before state in `PROVENANCE.txt` (ground rule 2).
3. Copy the untracked outputs the probe will overwrite into the run folder's `baseline/`: `data/marts/mart_degradation_predictions.parquet`, and the `CO-18` `ml/models/manifest.json` and `encoders.json` as `manifest_<new>.json`, `encoders_<new>.json`. Take the v14 pair from git: `git show HEAD:ml/models/manifest.json > baseline/manifest_v14.json` (same for `encoders.json`).
4. Diff the two encoders (category lists, order) and the two manifests' `feature_order` per model; save as `encoders_diff.txt`, `feature_order_diff.txt`.

## Scenarios and exact steps

`<new>` is `CO-18`'s version name (v16 unless the label-version record says otherwise). All Python runs use `./.venv/bin/python` from the repo root against `data/dev.duckdb` (the `CO-17` build) unless a step says otherwise.

| # | Scenario | Stint life | Cliff + three pace quantiles | Warehouse |
| :-- | :-- | :-- | :-- | :-- |
| S1 | Promotion yes | `<new>` | `<new>` | new label |
| S2 | Promotion no | v14 | v14 | as served today (v14 files, committed app data) |
| S3 | Partial promotion (option A's fail branch) | v14 | `<new>` | new label, as the app serves it |
| S4 | v14 stint life fed features built on the new label | v14 | `<new>` | new label, measured against v14's own training features |
| S5 | v14 for every model on the new-label warehouse (option B) | v14 | v14 | new label |

**S1, promotion yes (control).**
1. Put the `<new>` manifest and encoders in `ml/models/`. Run `make app-models` (copies `*_<new>.onnx`).
2. `python -m ml.src.predict --version <new>`; save the row count, versions present and summary stats.
3. `make app-data` (writes `app/public/data/`).
4. In `app/`: `npx vitest run src/ml/parity.node.test.ts src/ml/infer.test.ts src/ml/flagChance.test.ts`; then `VITE_DATA_BASE="" npm run dev` and open the simulator, model metrics, blind-test scoreboard and methodology pages. Record console errors, `verifyParity` result per model, and every version string shown.
5. Save diffs and screenshots; restore.

**S2, promotion no (control for today).** Same as S1 with the v14 manifest and encoders from `baseline/`, `make app-models`, and `predict --version v14`. Expect no difference from `HEAD`; any difference is a finding.

**S3, partial promotion.**
1. Build a manifest by hand from the `<new>` manifest with the `stint_life_regressor` entry (its `onnx`, `onnx_sha256`, `booster_sha256`, `feature_order`, output block) replaced by v14's. Record whether the top-level `model_version` can say anything true (it cannot hold two values).
2. Copy the four `<new>` ONNX files and `stint_life_regressor_v14.onnx` into `app/public/models/` by hand (`make app-models` cannot do this: it copies one version). Pick one `encoders.json` and record which; then repeat with the other.
3. Score: `predict.py` takes one `--version` for all five models (plus `--out`, `--models-dir`, `--flag-lookup`; checked 2026-10-22), so score twice, `--version <new> --out <run folder>/s3_new.parquet` and `--version v14 --out <run folder>/s3_v14.parquet`, join stint life from the second onto the first, and record what the `model_version` column then says and what `scripts/export_app_data.py` would publish.
4. Load the app as in S1. Record whether the app fetches the v14 stint-life file at all (it names files from the manifest), whether `verifyParity` passes for each model against its own fixtures, and every version string shown.

**S4, v14 stint life on new-label features.** Uses S3's set-up.
1. Score v14 stint life on the new warehouse (`load_scoring_frame` on `data/dev.duckdb`).
2. Compare against the v14 baseline parquet per stint: median and p90 change in predicted laps, share of stints moving more than one lap, share outside v14's own published p10–p90 band.
3. If old-label feature tables were kept, per feature in stint life's `feature_order`: share of rows that change and the size of the change.

**S5, all v14 on the new-label warehouse.**
1. v14 manifest and encoders, `make app-models`, `predict --version v14` on the new `data/dev.duckdb`.
2. Same shift measures as S4, for all five models.
3. `make app-data`; load the app; list every page and card where a v14 prediction sits beside a new-label warehouse number.

## What to check for cards and pages beside mismatched versions

For S3, S4 and S5, record for each pair whether anything on the page or card says the versions differ, and whether the two numbers can disagree:

- **Simulator** (`degradation-simulator/page.tsx`, `transform.ts`, `powerLaw.ts`): stint-life band next to the cliff probability on the same stint; the laps-to-flag cap and the experimental chance line (`flagChance.ts` hides the line when the lookup's `model_version` differs: record whether it disappears silently) next to a stint-life number.
- **Model metrics** and **blind-test scoreboard**: whether the headline version and the per-model metrics name the version each model really is.
- **Methodology / provenance** (`Provenance.tsx`, `FeaturePage.tsx`): which `model_version` they print.
- **Assistant cards** (`AI-01`, not built yet): tyre-prediction cards next to rating cards built on the new label; record what the single `model_version` field would say, from the export.
- **Predictions mart**: whether `model_version` holds one value per row and can hold a mix, and what `scripts/export_app_data.py` writes.

## Questions per scenario

1. **Loads?** Manifest and five models load without error; ONNX parity passes per model against its own version's fixtures.
2. **Right files?** Can the manifest name a version per model? If not, the smallest change that would let it (a note for `CD10`, not made here).
3. **Right features?** Feature and prediction shift (S4, S5).
4. **Encoders?** One `encoders.json` for both versions without mismatch.
5. **Cards and pages beside mismatched versions** (section above).
6. **Predictions mart** (section above).
7. **Breakage in the plain sense.** Anything that errors, shows a wrong label, shows a number that disagrees with another on the same page, or silently mixes versions.

## Go/no-go — DRAFT for the owner to change before the first run

- **GO for mixed versions (S3)** only if all of: S3 loads with no error; every model passes its own parity check; the manifest and the cards can name each model's version separately (or the change to let them is named and small); the v14 stint-life predictions under S4 stay inside v14's own p10–p90 band for at least 95% of stints, or the shift is fully explained and the owner accepts it; and every mixed pair in the cards-and-pages check can carry a visible note.
- **NO-GO** otherwise. A NO-GO means `CD10` option A's fail branch is not available as written; the owner chooses between promoting all five, keeping v14 for all five, or funding the change from question 2 first.
- **Draft pass rule for S1 and S2 (controls):** both load with no error and parity passes; S2 differs from `HEAD` in nothing shipped. If a control fails, stop and report: the mixed scenarios cannot be read.
- **Draft rule for S5 (option B):** report only, no pass or fail; it lists what would need a visible "mixed label versions" note.

## Output (in the run folder)

1. `PROVENANCE.txt`, `rules.txt` (final, frozen before the run), `baseline/`.
2. `results.csv` (or `.md` table): one row per scenario, one column per question, measured values.
3. `go-no-go.txt`: the verdict against `rules.txt`.
4. `what-breaks.txt`: plain English, one line per break with its scenario, e.g. "the simulator shows a stint-life number from the old model next to a cliff chance from the new one, and nothing on the page says so".
5. Per-scenario diffs (`s1.diff` ... `s5.diff`), shift tables, screenshots.
6. A note for `CD10`'s context saying which options are safe to choose (written into the log by the log keeper).

## Definition of done

All five scenarios run and recorded in the run folder; go/no-go stated against the rules frozen before the run; the plain-English list of breaks written; `CD10`'s context updated. At the end the working tree is back to the before state for everything outside `_roadmap/` (checked against the `git status` and sha256 lists in `PROVENANCE.txt`), `MODEL_VERSION_DEFAULT` is `v14`, the CDN is untouched. Nothing committed.
