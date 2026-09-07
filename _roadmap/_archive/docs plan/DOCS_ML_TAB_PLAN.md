# Implementation plan — the Machine Learning tab (XGBoost predictors, the pipeline, leakage spine, and the CI contract)

Internal planning doc. Lives in `_roadmap/` (gitignored) because it is *process*, not a
description of the committed tree — exactly the kind of artifact
[CONVENTIONS.md](../.github/CONVENTIONS.md) bans committed files from depending on. Nothing in
`docs/`, the layer READMEs, or code comments may cite this file. Every rule it applies to
the docs is restated inside the docs themselves.

The plan's own numbered steps are a genuine build procedure (a how-to), which CONVENTIONS
explicitly permits — the ban is on *describing what stage the project reached*, not on
ordered instructions.

This is the third layer pass, following the now-archived
[`_archive/DOCS_LAYER_TABS_PLAN.md`](_archive/DOCS_LAYER_TABS_PLAN.md) (the **Data** tab, the
template every later tab copies) and [`_archive/DOCS_TRANSFORM_TAB_PLAN.md`](_archive/DOCS_TRANSFORM_TAB_PLAN.md)
(the **Transform** tab, which set the "family narratives + enriched reference + grouped CI
contract" shape). This is the **ML** pass. It reuses the Transform tab's structure but trades
*breadth* for *depth*: ML has only 5 models and 28 tests, but it carries the project's hardest
methodology — leakage prevention on forward-looking targets, quantile calibration, conformal
intervals, the adversarial probe, and ONNX in-browser parity. The Transform tab earned the most
pages because it had the most models; the ML tab earns its keep by explaining the most *maths
per page*.

---

## 0. Progress checkpoint (resume here)

Execution is checkpointed in **7 parts** (§10) so a context reset never loses more than one
part's worth of work. Protocol: **pause after each part, report status, do not commit** unless
explicitly asked — each part is independently reviewable. Nothing in this plan authorizes a
commit. Standing instruction: each part needs its own go-ahead — don't chain into the next part
without one.

**STATUS: ALL 7 PARTS COMPLETE — 2026-06-24.**

All gates green (mintlify validate + broken-links 0/0, ml_docs_facts PASSED, gen_ml_reference --check clean, docs_facts PASSED, docs_audit 0 errors). Nothing committed yet — awaiting explicit go-ahead. Summary of what was built:

- §0.1 drift fixed: `make ml-reference` regenerated to v4/42-feat; `_roadmap/ml/ML.md` updated 41→42.
- **Part 1**: docs.json 5-group nav; `scripts/ml_docs_facts.py` + 6 snippets (`ml-inventory*.mdx`); `ml-inventory-drift` CI job in docs-ci.yml; `docs_facts.py` extended with "42 features" pattern + `docs-coverage`/`docs-coverage-check` Makefile targets updated.
- **Part 2**: `ml/overview.mdx` polished (MLInventory snippet, updated CardGroup to all 5 group fronts); `ml/feature-contract.mdx` NEW (42 features × 10 groups + read-only contract + MLFeatures/MLLeakage snippets).
- **Part 3**: `ml/pipeline.mdx` NEW (8-stage DAG mermaid + Steps); `ml/features-and-targets.mdx` NEW (3-target Tabs, encoder code, fingerprint/forward-window Accordions); `ml/models.mdx` polished (MLMetrics snippet, CardGroup nav, tuning folded out to link).
- **Part 4**: `ml/tuning.mdx` NEW (9-dim search table, Steps, learning-curve image); `ml/onnx.mdx` NEW (mermaid, parity Check, 3 Accordions).
- **Part 5**: `ml/validation.mdx` polished (calibration+cohorts split out, cross-links added); `ml/calibration.mdx` NEW (full LaTeX CQR derivation, MLCalibration snippet, calibration-degradation.png); `ml/cohorts.mdx` NEW (cohort table, cell-by-cell context).
- **Part 6**: `ml/ci/overview.mdx` NEW (MLTests snippet, mermaid pyramid, CardGroup); `ml/ci/leakage-spine.mdx` NEW (12 guards as Accordions, MLLeakage snippet); `ml/ci/parity-and-schema.mdx` NEW (9 tests in Tabs); `ml/ci/evaluation-gates.mdx` NEW (7 gates as Accordions).
- **Part 7**: `make ml-docs-images` target added + 3 PNGs copied to `docs/images/ml/`; `docs/AGENTS.md` + `ml/README.md` reconciled; Makefile `docs-coverage`/`docs-coverage-check` extended with `ml_docs_facts.py`.

When you resume: nothing to do — plan is complete. All 16 pages exist, all gates pass. Await commit go-ahead.

### 0.1 Must-verify-first: the v3 → v4 reference drift

The committed generated reference, [`docs/reference/ml/degradation-model-v1.mdx`](../docs/reference/ml/degradation-model-v1.mdx),
renders **`(v3)` / 41 features** in its title, headline table, and feature list. But
[`ml/model_card.yml`](../ml/model_card.yml) declares **`version: v4`**, and the three authored
narrative pages (`ml/overview`, `ml/models`, `ml/validation`) already state **v4 / 42 features**.
The roadmap note `_roadmap/ml/ML.md` also still says **41 features**. Three surfaces, two
different answers.

**This is a generated-file staleness, not a content decision.** `gen_ml_reference.py` reads
`model_card.yml` and emits the `.mdx`; if the committed `.mdx` says v3 while the card says v4,
either (a) `make ml-reference` was never re-run after the card went to v4, or (b) the v4 card
write never persisted. **Step 1 of Part 1 is to resolve which**, then bring all four surfaces
into agreement on a single version:

1. Run `python scripts/gen_ml_reference.py --check`. If it reports drift, the `.mdx` is simply
   stale → run `make ml-reference`, confirm it now renders v4/42-feat, and the `reference-drift`
   gate is satisfied. If `--check` passes (no drift), then the *card itself* is v3-shaped despite
   its `version: v4` label — investigate `ml/src/card.py` before touching docs.
2. Reconcile `_roadmap/ml/ML.md`'s "41 features" line (it is gitignored process notes, but it is
   the human-written companion to this plan; keep it honest).
3. Every count this plan's new pages cite (`42 features`, `10 groups`, `28 tests`, train spans)
   must come from the gated snippet (§7), never a prose literal — so this drift cannot recur.

Do **not** start authoring new pages on top of a layer whose own generated reference disagrees
with itself. Reconcile first.

### Parts

| Part | Scope (one-liner) |
|---|---|
| **1** | Reconcile v3→v4 drift (§0.1); docs.json five-group nav; `ml_docs_facts.py` + `ml-inventory.mdx` snippet + `ml-inventory-drift` CI job; regenerate + enrich `gen_ml_reference.py` |
| **2** | Concepts group: `ml/overview` front-door polish + `ml/feature-contract` (NEW) |
| **3** | The Pipeline group: `ml/pipeline` (NEW) + `ml/features-and-targets` (NEW) + `ml/models` polish |
| **4** | The Pipeline group cont.: `ml/tuning` (NEW) + `ml/onnx` (NEW) |
| **5** | Validation & Trust group: `ml/validation` polish + `ml/calibration` (NEW) + `ml/cohorts` (NEW) |
| **6** | The CI Contract group: `ml/ci/{overview,leakage-spine,parity-and-schema,evaluation-gates}` (NEW) |
| **7** | Visual payload (artefact plots → `docs/images/ml/`); CONVENTIONS sweep; reconcile README/Makefile-help/AGENTS/`docs_facts`; full gate run |

---

## 1. Goal and the bar

Build the **Machine Learning** tab so a reader who has never seen the repo can, at their chosen
depth, understand **why** the machine layer exists on top of the physics decomposition, **how**
each of the five models is trained and tuned, **how** the pipeline guarantees it never leaks the
future, and **what** every model produces — without opening the Python.

The ML layer's intellectual content is not "many models" (there are five) but "hard guarantees":

1. **Forward-looking targets make leakage the defining risk.** The tab must make the *leakage
   spine* — five guards plus an adversarial probe that recovers `race_year` at 0.987 accuracy —
   legible as the load-bearing structure it is, the same way the Transform tab made the 443-test
   CI contract legible.

2. **Quantile calibration and conformal intervals are real maths, not a metric table.** The
   `[p10, p90]` interval claims 80% coverage and delivers 0.814; the split-conformal (CQR)
   correction has a finite-sample guarantee. These earn full LaTeX derivations — the
   decomposition pages set that standard and the ML pages match it.

3. **The pipeline is one command (`make ml-all`) and eight honest stages.** Each stage
   (`features → tune → train → evaluate → predict → onnx → card → reference`) is a narrative beat:
   what it reads, what it writes, what it guarantees.

The bar: a contributor lands on the tab and comes away understanding the design *and its
alternatives* — why gradient-boosted trees and not one regression, why pinball loss gives the
interval, why IPW survival weights, why `driver_id` and `race_year` are non-negotiable
exclusions — well enough to arrive with v2 ideas already forming.

Scope:
- **Full**: the ML tab IA (§5) and the generation/gating spine (§7).
- **Deep**: every page — Concepts (§6A), the pipeline-stage narratives (§6B), Validation & Trust
  (§6C), the grouped CI contract (§6D), the enriched generated reference (§6E).
- **Out of scope**: Transform and App tabs (separate passes — App is the only remaining one);
  changing any `ml/src/*.py` behaviour, retraining a model, or moving a number. Documentation
  only. The single exception is **regenerating** the stale reference (§0.1) and **copying**
  artefact plots into `docs/images/ml/` (§7d) — neither changes model output.

---

## 2. Source-of-truth map (what backs every page)

Every ML page is backed by committed source. No page invents behaviour. Counts are *never*
hand-typed in prose — they come from a gate (§7).

| Concern | Source of truth | Surfaced on |
|---|---|---|
| Why ML on top of physics | `ml/overview.mdx` (exists), `decomposition/tyre-cliff.mdx` | Concepts |
| The 42 features × 10 groups | `ml/src/schema.py` (`FEATURE_COLUMNS`, group map), `model_card.yml` `features` | `ml/feature-contract`, gated snippet |
| The read-only contract with Transform | `fct_cliff_prediction_features` (`reference/models/fct/*`), `ml/src/features.py` (load) | `ml/feature-contract` |
| The three targets | `ml/src/schema.py` (target cols), `ml/src/features.py`, `test_targets.py` | `ml/features-and-targets` |
| The 5 models & objectives | `ml/src/train.py`, `ml/src/schema.py` (model registry), `model_card.yml` `models` | `ml/models` |
| The pipeline DAG (8 stages) | `Makefile` (`ml-all` target), `ml/README.md` | `ml/pipeline` |
| Feature loading / encoding / fingerprint / leakage audit | `ml/src/features.py` (docstring: "loading, splitting, encoding, fingerprinting, and the forward-window leakage audit") | `ml/features-and-targets` |
| Hyperparameter search | `ml/src/tune.py` (Optuna `TPESampler`+`MedianPruner`), `*_best_params.json` | `ml/tuning` |
| Training engine (IPW + class weights) | `ml/src/train.py`, `model_card.yml` per-model | `ml/training` (folded into `ml/models`) |
| ONNX export + parity | `ml/src/export_onnx.py` (docstring: "the D1/R1 gate"), `test_onnx_parity.py`, `ml/models/manifest.json` | `ml/onnx` |
| Season-grouped CV | `ml/src/evaluate.py`, `model_card.yml` `validation.scheme` | `ml/validation` |
| Leakage spine (5 guards) | `test_features.py`, `ml/src/schema.py` `EXCLUDED_LEAKAGE_COLUMNS`, `ml/src/features.py` audit | `ml/validation`, `ml/ci/leakage-spine` |
| Adversarial probe | `ml/src/evaluate.py`, `model_card.yml` `validation.leakage_probe` | `ml/validation` |
| Calibration / conformal (CQR) | `ml/src/evaluate.py`, `model_card.yml` `validation.calibration` | `ml/calibration` |
| Underperforming cohorts | `ml/src/evaluate.py`, `model_card.yml` `validation.underperforming_cohorts` | `ml/cohorts` |
| The 28 tests | `ml/tests/*.py` (pytest collection: 16 functions → 28 parametrized), `ml/tests/README.md` | `ml/ci/*` |
| The model card (all metrics) | `model_card.yml` (machine-written by `ml/src/card.py`) | `reference/ml/degradation-model-v1` (generated) |
| Headline counts (5 models / 28 tests / 42 features) | `scripts/docs_facts.py` (gate), new `scripts/ml_docs_facts.py` | gated snippets only, never prose literals |
| Visual artefacts (calibration / PDP / learning curves) | `ml/artefacts/*.png` (**gitignored** — see §7d), regenerated by `ml-evaluate` | `docs/images/ml/*` (curated, committed) |

**Three design decisions are pre-made and must be honoured everywhere:**

- **`driver_skill_residual_s` and the targets are read from Transform, never re-derived in ML.**
  The machine layer reads `fct_cliff_prediction_features` **read-only** and writes nothing back
  to the warehouse or app. Every page that touches a feature says it comes from the mart, not the
  ML code. (Mirrors the Transform tab's "`driver_skill` is a closure" ruling — here, ML is a
  *consumer* of that closure.)

- **The holdout season is derived, never literal.** `HOLDOUT_SEASON = MAX(race_year) + 1`,
  today 2025 (no rows yet). The eval headline is the final TimeSeriesSplit fold (2024) standing
  in as a holdout, switching to a true reveal with **zero code change** when 2025 ingests. No
  page may hard-code 2025 as "the holdout" in a way that implies it already exists.

- **The version is whatever the gated card says (v4 today), stated once.** After §0.1, every
  page that names a version reads it from the card/snippet. No page hard-codes "v4" — when v5
  trains, the pages follow the card.

---

## 3. The pipeline-stage taxonomy (the "smart grouping")

The Transform tab grouped 60 models into 8 *families*. The ML layer has only 5 models, so its
natural unit of narrative is not the model but the **pipeline stage** and the **question family**.
Two orthogonal groupings, both encoded in source:

**(a) Three question families (the models).** Encoded in `ml/src/schema.py`'s model registry
(`family` per model) and surfaced in the card's `models[].family`:

| Question | Models | Output | Loss |
|---|---|---|---|
| How much pace will the tyre lose? | `degradation_regressor_p10/p50/p90` | `next_lap_degradation_jump_s` quantiles | pinball (`reg:quantileerror`) |
| How close is the cliff? | `cliff_classifier` | `laps_until_cliff_class` (4-class) | softprob + balanced weights |
| How many usable laps remain? | `stint_life_regressor` | `remaining_stint_life_laps` | squared error |

**(b) Eight pipeline stages (the `make ml-all` DAG).** Encoded in the `Makefile` `ml-all` target.
This is the reading order down the "Pipeline" sidebar group — a reader walking top to bottom
walks the data the same direction it flows:

```
features → tune → train → evaluate → predict → onnx → card → reference
   │         │       │        │          │        │       │       │
 contract  Optuna  XGBoost  metrics   score    parity  card   docs
 (read)    search  refit    +leakage  marts    ≤1e-5   (yml)  (mdx)
```

The two groupings meet on the `ml/models` page: it explains the *three question families* (the
*what*) and links into the *training stage* (the *how*). The `ml/pipeline` page owns the
*eight-stage DAG* as its front door.

**Why not one page per model (the Transform "one page per model" rule)?** The five models share
one feature matrix, one training engine, one tuning loop, one ONNX export, and one validation
spine. Spreading them across five near-identical pages would duplicate 80% of the content. The
*differences* are exactly four things — objective function, target, baseline, and weighting —
which fit in one comparison table on `ml/models`. The generated reference (§6E) is where each
model's individual hyperparameters and metrics live, one section each. So: **shared methodology
in the narrative, per-model specifics in the generated card** — the same split the Transform tab
used (family narrative vs enriched reference), applied to a layer whose "family" is the whole set.

---

## 4. The CI-block taxonomy (the 28 tests, grouped)

The ML suite is **28 tests** (the pytest *collection* count — 16 test functions, several
parametrized across the five models, expand to 28). The number is small but the guarantees are
load-bearing, so the grouping mirrors what `ml/tests/` and `validation.mdx` already state:
**12 spine + 5 ONNX parity + 3 predict + 7 evaluate + 1 targets**.

```
                          28 ML tests
        ┌──────────────┬────────────┬───────────┬───────────┬─────────┐
   LEAKAGE SPINE   ONNX PARITY    PREDICT    EVALUATE     TARGETS
       (12)            (5)          (3)         (7)          (1)
   no leaked cols   booster==onnx  schema    beats-base   bounded /
   no LEAD/FOLLOW   ≤ atol 1e-5    of preds  calibration  non-null
   holdout purity   NaN-bearing    written   cohorts      target
   no hardcoded yr  (5 models)               surfaced
   bounded targets
   (test_features)  (test_onnx_    (test_     (test_       (test_
                     parity)        predict)   evaluate)    targets)
```

| Group | Source file | Count | What it guarantees | Page (§6D) |
|---|---|---|---|---|
| **Leakage spine** | `test_features.py` | 12 | Targets/skill/season never enter `X`; a `sqlglot` audit rejects any `LEAD`/`FOLLOWING`; no holdout row in any train fold; split is `MAX+1`-derived not literal; targets bounded & non-null. | `ml/ci/leakage-spine` (one idea each) |
| **ONNX parity** | `test_onnx_parity.py` | 5 | Each of the five boosters round-trips to ONNX within `atol=1e-5`, including a NaN-bearing sample (the ~47% null-prior laps). | `ml/ci/parity-and-schema` |
| **Predict schema** | `test_predict.py` | 3 | The scored predictions parquet carries the declared columns/grain; Arrow-validated. | `ml/ci/parity-and-schema` |
| **Targets** | `test_targets.py` | 1 | Degradation target ∈ [−10, 10]; no NULL-target row enters training. | `ml/ci/parity-and-schema` (clubbed) |
| **Evaluation gates** | `test_evaluate.py` | 7 | Every model beats its per-cohort baseline; calibration coverage computed; cohorts surfaced not dropped; metrics match the card. | `ml/ci/evaluation-gates` |

The **exact** counts must **not** be hand-typed onto the pages — every count renders from the
gated `ml-inventory.mdx` snippet (§7b), which reads the live pytest collection. The day someone
adds a guard, the page updates itself and CI fails if it wasn't regenerated.

The clubbing rule (from the Transform tab): the 12 spine guards each carry a *unique idea*
(no-leak, no-lead, holdout-purity, no-hardcode, bounds) → they get one explained block each on
`ml/ci/leakage-spine`. The 5+3+1 parity/schema/targets tests are *mechanical contracts* → one
pattern page (`ml/ci/parity-and-schema`). The 7 evaluation gates each assert a headline property
→ `ml/ci/evaluation-gates`. That is the whole 28, grouped, heavy explanation spent only where
there's a unique idea.

---

## 5. Target information architecture (docs.json restructure)

The ML tab currently has two groups: *Machine Learning* (3 authored pages) and *ML Models* (1
generated reference). Restructure to **five groups**, in pipeline reading order, reusing the
Data/Transform tab vocabulary verbatim so the four layer tabs read identically:

```
Machine Learning  (icon: microchip)
├── Concepts                  (icon: lightbulb)    — why ML, what it consumes
│     ml/overview                                     (exists → front door, polish)
│     ml/feature-contract                             ← NEW (42 features, 10 groups, read-only mart contract)
│
├── The Pipeline              (icon: workflow)     — the 8 make ml-all stages, each a narrative
│     ml/pipeline                                     ← NEW (front door: the 8-stage DAG)
│     ml/features-and-targets                         ← NEW (features.py: load/encode/fingerprint/audit + 3 targets)
│     ml/models                                       (exists → 5 models, objectives, training engine; polish)
│     ml/tuning                                       ← NEW (Optuna search → select on CV → refit)
│     ml/onnx                                         ← NEW (export + parity + in-browser scoring)
│
├── Validation & Trust        (icon: shield-check) — leakage, CV, calibration, cohorts
│     ml/validation                                   (exists → CV + leakage spine, polish)
│     ml/calibration                                  ← NEW (the 80% interval, conformal CQR maths)
│     ml/cohorts                                      ← NEW (underperforming cells, surfaced never dropped)
│
├── The CI Contract           (icon: vial)         — the 28 tests, grouped + gated
│     ml/ci/overview                                  ← NEW (the test pyramid 12+5+3+7+1)
│     ml/ci/leakage-spine                             ← NEW (12, one idea each)
│     ml/ci/parity-and-schema                         ← NEW (5 onnx + 3 predict + 1 targets)
│     ml/ci/evaluation-gates                          ← NEW (7 evaluate)
│
└── Model Reference           (icon: database)     — the generated card, enriched
      reference/ml/degradation-model-v1               (exists, generated → REGENERATE to v4 + enrich)
```

**Why five groups, not two:** the two current groups conflate *concept* + *method* + *validation*
into one "Machine Learning" bucket and isolate the *lookup* (reference). The reader who wants the
idea, the reader who wants to reproduce the pipeline, the reader who wants to trust the numbers,
and the reader who wants one model's hyperparameters are four different readers; each gets a
group. The reading order is the pipeline order, so the sidebar itself teaches `make ml-all`.

**Vocabulary (reused from Data/Transform so the four tabs read identically):** "Concepts" mirrors
the conceptual framing; "The Pipeline" is the ML analogue of Transform's "How the Layer Works";
"Validation & Trust" mirrors Transform's "Quality"/"CI Contract" framing split into its
methodology half; "The CI Contract" is the literal Transform analogue; "Model Reference" mirrors
"Model Reference". Group icons reuse the shared set: `lightbulb`/`workflow`/`shield-check`/`vial`/
`database`.

Page slugs: new authored pages live under `ml/` (`ml/feature-contract`, `ml/pipeline`,
`ml/features-and-targets`, `ml/tuning`, `ml/onnx`, `ml/calibration`, `ml/cohorts`, `ml/ci/*`).
The generated reference stays at `reference/ml/degradation-model-v1` (no file move — same call
the Transform tab made for its generated pages).

**Page count:** 4 existing (polished/regenerated) + 12 new = 16 pages. Proportionate: the
Transform tab had ~30 for 60 models; ML has half the pages for a tenth of the models because its
value is depth-per-page, not breadth.

---

## 6. Page specs

Each spec gives **purpose**, **source of truth**, **Mintlify components**, **CONVENTIONS notes**.
Authored MDX unless marked *generated*. The three existing pages (`ml/overview`, `ml/models`,
`ml/validation`) are already strong — the specs below say what to *keep* and what to *add*, not
to rewrite.

### 6A. Concepts group

#### `ml/overview` — the tab's front door *(exists → polish)*
- **Purpose**: orient a cold reader — what the machine layer adds over the physics decomposition
  (the cliff is an *interaction* effect a linear model can't capture), the three question
  families, the one-mart feature source, the one-command reproduce. The existing page already
  nails this; the polish is structural.
- **Source**: existing page; `Makefile` `ml-all`; `model_card.yml`.
- **Polish**:
  - Replace the hand-typed "5 XGBoost models / 42 features / 113,309 laps" figures with the gated
    `ml-inventory.mdx` `import`s (§7b) — the only change of substance, and it kills the v3/v4
    drift class permanently.
  - Add a closing `<CardGroup cols={2}>` linking down to the four other group front doors
    (`ml/pipeline`, `ml/validation`, `ml/ci/overview`, `reference/ml/degradation-model-v1`) — the
    same navigable-both-directions card pattern the Transform tab used.
  - Keep the existing `flowchart TD` mermaid (physics → mart → 5 models → ONNX → browser).
- **CONVENTIONS**: present tense; no "v4" prose literal once the snippet lands; counts from gate.

#### `ml/feature-contract` — the 42 features and the read-only mart contract *(NEW)*
- **Purpose**: the page that makes "the physics lives in Transform; the machine layer reads it"
  concrete. The 42 features across 10 physics-grouped families, where each comes from, and the
  hard rule that ML reads `fct_cliff_prediction_features` read-only and writes nothing back.
- **Source**: `ml/src/schema.py` (`FEATURE_COLUMNS` + group map), `model_card.yml` `features`,
  `reference/models/fct/fct_cliff_prediction_features`.
- **Mintlify**:
  - The 10-group feature table rendered from `ml-inventory.mdx` (§7b) — never hand-typed (the
    reference page's stale 41-feature list is exactly the failure mode this prevents).
  - `<CardGroup>` — one card per group (stint-position, compound, cliff-prior, thermal, dirty-air,
    powertrain, telemetry-cliff, weather-air, track, context) with its one-line physics idea,
    each linking to the Transform model that produces it.
  - `<Note>` the two-target-span fact (113,309 deg+cliff / 119,876 stint-life rows — from the
    snippet) and *why* they differ.
  - A `<Warning>` "read-only contract": ML never writes the warehouse or app; it consumes the
    decomposition's `driver_skill_residual_s` closure as a *stripped* signal it must not relearn.
- **CONVENTIONS**: link to the live `fct_cliff_prediction_features` reference page, not to any
  ML-internal feature derivation (there is none — that's the point).

### 6B. The Pipeline group — the 8-stage narrative

#### `ml/pipeline` — the layer's reproduce-it front door *(NEW)*
- **Purpose**: one screen that shows the whole `make ml-all` DAG and what each stage reads/writes/
  guarantees. The "I want to run this myself" entry point.
- **Source**: `Makefile` (`ml-all`, `ml-features`, `ml-tune`, … targets), `ml/README.md`.
- **Mintlify**:
  - Opening full-width `mermaid` flowchart: the 8 stages with their inputs/outputs (features→
    `X` matrix; tune→`best_params.json`; train→`.bst`; evaluate→`evaluation_metrics.json`;
    predict→`mart_degradation_predictions.parquet`; onnx→`.onnx`+`manifest.json`; card→
    `model_card.yml`; reference→`.mdx`). Project red (`#e40404`) on the marts node.
  - `<Steps>` — one step per stage, each with its `make` target in a `<CodeGroup>` and a one-line
    "what it guarantees".
  - `<CodeGroup>` Build/Test: `make ml-all` and `make ml-test`.
  - `<Accordion>` "Smoke vs production" — the `_smoke` vs `_v{N}` artefact split (smoke = fast
    CI fixture, production = full refit), from the `ml/models/` naming.
- **CONVENTIONS**: present tense; the `ml-tune` note ("reduced budget v1 params; canonical 50/5/
  full only improves them") stated as present behaviour, not history.

#### `ml/features-and-targets` — load, encode, fingerprint, audit, and the three targets *(NEW)*
- **Purpose**: the `features.py` stage in full — how a row of the mart becomes a row of `X`
  (ordinal encoding from the training map, NULL/unseen → −1), the dataset fingerprint that makes
  runs reproducible, the forward-window leakage audit, and the three targets the models predict.
- **Source**: `ml/src/features.py` (docstring: "loading, splitting, encoding, fingerprinting, and
  the forward-window leakage audit"), `ml/src/schema.py` (targets), `test_features.py`,
  `test_targets.py`.
- **Mintlify**:
  - `<Tabs>` per target: `next_lap_degradation_jump_s` (legitimately negative ~44% of the time),
    `laps_until_cliff_class` (4 classes, ~58/15/15/12), `remaining_stint_life_laps` (synthesised,
    ≥0). Each tab: definition, distribution note, which model(s) consume it.
  - `<CodeGroup>` the *characteristic clause* of the encoder (5–15 lines, ordinal map + −1
    sentinel), never the whole module.
  - `<AccordionGroup>`: "The dataset fingerprint" (why `b8a37b7c…` makes a run reproducible and
    gates the card), "The forward-window audit" (the `sqlglot` walk that rejects `LEAD`/
    `FOLLOWING` — forward-linking to `ml/ci/leakage-spine`).
- **CONVENTIONS**: the fingerprint is stated as a mechanism, not "the value is X" (it changes per
  build — cite it from the snippet/card or describe it, don't pin a literal hash in prose).

#### `ml/models` — the five models, objectives, and the training engine *(exists → polish)*
- **Purpose**: already excellent — the additive-trees objective, the four loss functions (pinball/
  squared/softprob/IPW), per-model "what it tells you / when to rely / limits", the tuning Steps,
  and the worked p10/p50/p90 example. Keep all of it.
- **Source**: existing page; `ml/src/train.py`; `model_card.yml`.
- **Polish**:
  - Replace the hand-typed headline metrics table with a `<Note>` pointing at the generated
    reference for live numbers, **or** keep the table but gate its numbers via the snippet — pick
    one in Part 3 so the v3/v4 drift can't reappear here (recommend: keep the narrative table but
    add a "live numbers: see [reference]" line, since the prose around the numbers is the value).
  - Add a family banner `<CardGroup>` at top linking to `ml/features-and-targets` (the inputs) and
    `ml/tuning` (how the params were chosen) so the page sits in the pipeline flow.
  - Fold the existing "Tuning and refit" `<Steps>` *out* to the new `ml/tuning` page and replace
    with a one-line summary + link (avoid duplicating it across two pages).
- **CONVENTIONS**: the "v1 reduced budget" `<Note>` already present — keep, it's honest present
  behaviour.

#### `ml/tuning` — Optuna search, CV selection, full refit *(NEW)*
- **Purpose**: the `tune.py` stage. The 9-dimensional search space, `TPESampler`+`MedianPruner`
  (seeded, resumable), per-fold pruning, selection on the season-grouped CV headline, then refit
  on the full training set. Receives the `<Steps>` moved out of `ml/models`.
- **Source**: `ml/src/tune.py`, `ml/models/*_best_params.json`, `ml/models/optuna_studies/*.db`.
- **Mintlify**:
  - `<Steps>` Search → Select on CV → Refit on everything (the moved block, expanded).
  - A table of the 9 search dimensions (`max_depth`, `learning_rate`, `n_estimators`, `subsample`,
    `colsample_bytree`, `min_child_weight`, γ/λ/α) mapping each to the regularised objective term
    from `ml/models`.
  - `<Note>` the reduced-budget-v1 vs canonical-50/5/full distinction (the beats-baseline gate
    holds regardless).
  - `<Accordion>` "Reproducible & resumable studies" — the `.db` Optuna storage.
- **CONVENTIONS**: present tense; no phase labels.

#### `ml/onnx` — export, parity, in-browser scoring *(NEW)*
- **Purpose**: the `export_onnx.py` stage (its docstring calls it "the D1/R1 gate"). Why every
  booster is exported to ONNX, the `atol=1e-5` round-trip parity, the NaN-bearing sample that
  proves the ~47% null-prior laps round-trip, and how this enables server-free in-browser scoring
  in the React app.
- **Source**: `ml/src/export_onnx.py`, `test_onnx_parity.py`, `ml/models/manifest.json`,
  `ml/models/encoders.json`.
- **Mintlify**:
  - `mermaid`: `.bst booster → ONNX → manifest.json + encoders.json → app/public/models → browser`.
  - `<Check>` parity statement (5 models, NaN-bearing, ≤1e-5) — gated to the snippet's parity line.
  - `<Accordion>` "Why parity must be exact" (Python trains, browser scores; any divergence is a
    silent wrong number on screen) and "The manifest" (version pinning per `manifest.json`).
  - Forward-link to `ml/ci/parity-and-schema` (the test that enforces this).
- **CONVENTIONS**: the app-copy step (`make app-models`) is mentioned as the boundary, not
  re-documented (it belongs to the App tab).

### 6C. Validation & Trust group

#### `ml/validation` — season-grouped CV and the leakage spine *(exists → polish)*
- **Purpose**: already strong — the gantt CV diagram, the 5-guard spine table, the adversarial
  probe, the metric-definition `<Tabs>`, the holdout policy. Keep all of it. The polish is to
  *split off* the two topics that earn their own page (calibration → `ml/calibration`, cohorts →
  `ml/cohorts`) and leave this page as "the spine + CV + holdout".
- **Source**: existing page; `ml/src/evaluate.py`; `test_features.py`.
- **Polish**:
  - Move the "Calibration — does the 80% interval cover 80%?" section *out* to `ml/calibration`
    (it has unique maths — the CQR derivation — that deserves a page). Leave a one-paragraph
    summary + link.
  - Move "Cohorts surfaced, never dropped" *out* to `ml/cohorts`. Leave a summary + link.
  - Keep the leakage spine table and adversarial probe *here* (they are the page's spine) but
    cross-link the enforcing tests to `ml/ci/leakage-spine`.
  - Gate the "n = 19,067 laps" and "0.987 probe accuracy" figures to the snippet.
- **CONVENTIONS**: holdout stated as `MAX+1`-derived; no hard-coded 2025-as-existing.

#### `ml/calibration` — the 80% interval and the conformal correction *(NEW)*
- **Purpose**: the unique-maths page. Coverage as the fraction of held-out laps inside `[p10,p90]`;
  the split-conformal (CQR) conformity score, the empirical-quantile correction, the finite-sample
  guarantee, and the plain-English "right four times in five, ~1.24s wide".
- **Source**: `ml/src/evaluate.py` (calibration block), `model_card.yml` `validation.calibration`,
  the moved section from `ml/validation`.
- **Mintlify**:
  - The full LaTeX the existing validation page already has: coverage indicator sum, the
    conformity score $s_i = \max(p_{10}-y_i,\ y_i-p_{90})$, the $\lceil(n+1)(1-\alpha)\rceil/n$
    empirical quantile, the shifted band.
  - The coverage table (nominal 0.800 / raw 0.814 / conformal 0.805 / width 1.238s) — gated to the
    snippet, not hand-typed (these are the exact numbers that drifted v3→v4).
  - `<Accordion>` "Confirms, not rescues" — the q≈−0.014 offset means the raw quantiles were
    already calibrated.
  - The committed calibration plot (`docs/images/ml/calibration-degradation.png`, §7d).
- **CONVENTIONS**: numbers from the gate.

#### `ml/cohorts` — surfaced, never dropped *(NEW)*
- **Purpose**: the honesty page. The 18 cohort cells where a model trails its baseline (mostly the
  near-oracle stint-life baseline winning on specific circuits), recorded openly rather than hidden.
- **Source**: `ml/src/evaluate.py` (cohort loop), `model_card.yml` `validation.underperforming_cohorts`.
- **Mintlify**:
  - The cohort table rendered from the card/snippet (dimension/cohort/n/model/baseline) — never
    hand-typed (it's 18 rows that change every retrain).
  - `<Warning>` the contract: surface the losses, do not drop them; most are the stint-life
    baseline's near-oracle advantage on the Dutch/Japanese/Las Vegas GPs.
  - Cross-link to `ml/ci/evaluation-gates` (the test that asserts cohorts are surfaced).
- **CONVENTIONS**: the count ("18") from the gate, since it changes per retrain.

### 6D. The CI Contract group — the 28 tests, grouped + gated

#### `ml/ci/overview` — the test pyramid *(NEW)*
- **Purpose**: the §4 taxonomy as a page — the 28 tests as 12+5+3+7+1, what each group guarantees,
  and the one-command reproduce.
- **Source**: `ml/tests/README.md`, `ml/tests/*.py`, the gated snippet.
- **Mintlify**: the §4 ASCII pyramid as a `mermaid`; a `<CardGroup>` to the three sub-pages;
  `<Check>` "reproduce with `make ml-test`"; the 28 count from the snippet.
- **CONVENTIONS**: counts gated; present tense.

#### `ml/ci/leakage-spine` — the 12 guards, one idea each *(NEW)*
- **Purpose**: the heavy page. Each spine guard explained as its own block: no-leaked-columns,
  no-forward-window (`sqlglot` `LEAD`/`FOLLOWING` reject), holdout-purity, no-hardcoded-holdout
  (`MAX+1`), bounded/non-null targets.
- **Source**: `test_features.py`, `ml/src/schema.py` `EXCLUDED_LEAKAGE_COLUMNS`, `ml/src/features.py`.
- **Mintlify**: one `<Accordion>` per guard with its assertion + why it matters; a `<Warning>`
  on temporal leakage being silent (it never throws, it just inflates every offline number);
  cross-link to the adversarial probe on `ml/validation`. The excluded-columns list rendered from
  the snippet (it's the same list the reference page hand-renders today and got stale).
- **CONVENTIONS**: the excluded list from the gate.

#### `ml/ci/parity-and-schema` — ONNX parity + predict schema + targets *(NEW)*
- **Purpose**: the mechanical-contract page — 5 ONNX parity + 3 predict-schema + 1 targets,
  clubbed because each is one repeated pattern.
- **Source**: `test_onnx_parity.py`, `test_predict.py`, `test_targets.py`.
- **Mintlify**: a `<Tabs>` (Parity / Predict schema / Targets); status `<Check>` badges; the
  NaN-bearing-sample note; counts from the snippet.
- **CONVENTIONS**: present tense.

#### `ml/ci/evaluation-gates` — the 7 evaluation gates *(NEW)*
- **Purpose**: the beats-baseline / calibration-computed / cohorts-surfaced / metrics-match-card
  assertions in `test_evaluate.py`.
- **Source**: `test_evaluate.py`, `ml/src/evaluate.py`.
- **Mintlify**: one explained block per gate; cross-link beats-baseline → `ml/models`,
  calibration → `ml/calibration`, cohorts → `ml/cohorts`; counts from the snippet.
- **CONVENTIONS**: present tense.

### 6E. Model Reference — the generated card *(generated → regenerate + enrich)*

#### `reference/ml/degradation-model-v1` — every model's specifics *(generated)*
- **Purpose**: the autogenerated card: headline table, per-model hyperparameters, the feature
  table, baselines, calibration, probe, SHAP-vs-permutation importance, cohorts, reproducibility,
  limitations, holdout policy. It already exists and is generated by `gen_ml_reference.py`.
- **Source**: `model_card.yml` → `scripts/gen_ml_reference.py`.
- **Work**:
  1. **Regenerate to v4** (§0.1) — the single most important action in the whole plan. The
     committed `.mdx` is stale at v3/41-feat.
  2. **Enrich the generator** (optional, recommended): add a top `<Card>` banner linking up to
     `ml/models` (the narrative) so the reference and narrative cross-link both ways — mirroring
     the Transform tab's "every reference page begins with a family card" rule. Keep the generator
     idempotent and drift-gated (the existing `--check` + `reference-drift` job already cover it).
  3. Consider renaming the slug if the `-v1` suffix misleads (it renders "v4" content). **Defer** —
     a slug rename touches `docs.json` + every inbound link; the title already shows the live
     version, and the file is generated. Note it as a known cosmetic wart, don't fix it in this
     pass unless the user asks.
- **CONVENTIONS**: it's autogenerated with the `do not hand-edit` header — never hand-edit; all
  changes go through `card.py`/`gen_ml_reference.py`.

---

## 7. Generation & gating (how counts and families stay honest)

The whole tab obeys "counts live behind a gate." Four generation surfaces:

**(a) `scripts/gen_ml_reference.py` — the card MDX (existing, keep + lightly enrich).**
- Already has a real `--check` and is in `build_reference.py`'s `GENERATORS`, so the
  `reference-drift` CI job (`make docs-reference` → `git diff --exit-code`) covers it.
- Part 1 regenerates it to v4 (§0.1). Part 6E optionally adds the family-card banner — a template
  change, so regenerate + let the gate keep it current.

**(b) `scripts/ml_docs_facts.py` — the gated inventory snippet (NEW).**
- Mirrors `scripts/transform_docs_facts.py` / `scripts/ingestion_docs_facts.py`'s write/check
  shape. Reads `ml/src/schema.py` (`FEATURE_COLUMNS` + groups + `EXCLUDED_LEAKAGE_COLUMNS`),
  `ml/model_card.yml` (metrics, calibration, cohorts, train spans), and the live pytest collection
  count (`pytest ml/tests --collect-only -q`) and writes `docs/snippets/ml-inventory.mdx`: the
  feature table (42 features × 10 groups), the excluded-leakage list, the 28-test taxonomy
  (12+5+3+7+1), the headline metrics, the calibration coverage row, and the cohort count. Every
  count on every ML page `import`s from this snippet.
- Wire into `make docs-coverage` / `make docs-coverage-check` (extend, don't duplicate) and a new
  `ml-inventory-drift` job in `.github/workflows/docs-ci.yml`, alongside the existing
  `bronze-coverage-drift` / `transform-inventory-drift` / `overview-numbers-drift` jobs.
- **This snippet is the permanent fix for the v3/v4 drift class** — once the feature/metric tables
  render from it, a card bump that isn't re-snapped fails CI.

**(c) `scripts/docs_facts.py` — extend reconciliation (existing).**
- It already gate-checks `5 XGBoost models` and `28 tests` across `README.md` and
  `ml/overview.mdx`. Add the new ML pages that state these counts (`ml/feature-contract`,
  `ml/pipeline`, `ml/ci/overview`) to its reconcile set so the headline figures can't diverge
  between README and any ML front door. Add a `42 features` pattern if it isn't already covered.

**(d) Visual artefacts — the `docs/images/ml/` decision (NEW).**
- `ml/artefacts/*.png` (calibration, PDPs, learning curves) are **gitignored** — they are
  regenerated by `ml-evaluate` and not committed. To surface them in docs without committing the
  whole artefacts dir, **copy a curated subset into `docs/images/ml/`** (a committed dir, matching
  the existing `docs/images/hero-degradation-simulator.png` convention):
  - `calibration-degradation.png` → `ml/calibration`
  - `pdp-degradation-regressor-p50.png` → `ml/models` or `ml/features-and-targets` (feature effect)
  - one `learning-curve-*.png` → `ml/tuning` (over/underfit story)
- Add a `make ml-docs-images` target that copies the curated set from `ml/artefacts/` →
  `docs/images/ml/` so a regenerated plot can be refreshed deterministically. **Do not** add a
  drift gate on the PNGs (binary diffs are noisy; the plots are illustrative, not contractual) —
  this is the one place the tab is *not* gated, and that's correct (mirrors the Transform tab's
  "no screenshot pipeline" call, inverted: ML genuinely has model-quality plots worth showing).
- **Pre-made decision**: commit the curated subset. If the user prefers zero new binaries in
  `docs/`, fall back to Mermaid/described placeholders — but the real plots are the stronger
  payload and the convention already exists.

---

## 8. The visual system (the "go all out" payload)

Applied consistently, matching the Transform/Data tabs so the four read as one site:

- **One diagram language.** Mermaid everywhere, fenced ` ```mermaid ` blocks (not a `<Mermaid>`
  JSX tag — confirmed by the existing ML pages' usage). Three scales: the pipeline DAG
  (`ml/pipeline`), the system flowchart (`ml/overview`, exists), the CV gantt (`ml/validation`,
  exists) and the ONNX/test pyramids. Project red (`#e40404`) on the focus node.
- **Math gets LaTeX, always.** The existing pages already set the bar (pinball loss, the
  regularised objective, the CQR conformity score, macro-F1). The new pages match it — never an
  ASCII formula where a rendered one is possible. `ml/calibration` is the densest-maths page.
- **The "current vs alternative" pattern.** Design-notes blocks use `<Tabs>`/`<AccordionGroup>`
  with "how it works now" vs "other approaches" — e.g. "why GBT not one regression" (exists on
  `ml/models`, keep), "why IPW not raw counts", "why balanced weights not resampling". Consistent
  across pages so the reader learns the pattern once.
- **Light code, not whole modules.** SQL/Python snippets are the *characteristic clause* (the
  ordinal-encode map, the pinball loss, the conformity score) in `<CodeGroup>`, 5–15 lines, never
  a whole `.py`. The full module is in the repo, one `ml/src/*` reference away.
- **Badges for contracts.** `<Check>` for the parity/leakage gates; the beats-baseline ✅ in the
  headline table; the "read-only mart contract" `<Warning>` on `ml/feature-contract`.
- **CardGroup as connective tissue.** Every group front door is a card hub; every page links up,
  down, and sideways. `ml/overview` → group fronts; family/pipeline cards between stages;
  reference ↔ narrative.
- **The artefact plots (§7d)** are the one bitmap payload — calibration curve, a PDP, a learning
  curve — which a compute layer earns and a SQL layer (Transform) did not.

---

## 9. CONVENTIONS obligations (the sweep, restated for this tab)

- **No version/phase framing.** `ml/src/*` docstrings reference `D1/R1/§7 elevations`, `M2/M4`,
  `v0.2`-style labels; the model SQL/test files may carry `Fix N`. None of these may appear in
  committed docs. Authored pages never introduce them; lifted text is sanitised. The "v1 reduced
  budget" note is *allowed* — it describes present behaviour (the shipped params), not a project
  phase.
- **Counts behind a gate or not in prose.** All feature/model/test/cohort counts render from
  `ml-inventory.mdx` (§7b) or `docs_facts.py`. This is non-negotiable — the v3/v4 drift (§0.1) is
  exactly what hand-typed counts cause.
- **The version is the card's version.** No page hard-codes "v4"; it reads from the
  card/snippet. The generated reference's title already does this correctly.
- **Holdout is `MAX+1`-derived.** No page implies 2025 already exists as a populated holdout.
- **Read-only contract.** Every feature is sourced from `fct_cliff_prediction_features`; no page
  describes ML deriving physics. `driver_skill_residual_s` is a *stripped* signal ML must not
  relearn (the `driver_id` exclusion), not an ML output.
- **Every reference resolves in a clone.** No links to `_roadmap/**`, `SYSTEM_DESIGN_AUDIT.md`,
  `D1`/`R1`/`M2`, this plan. The leakage-probe and calibration *findings* are stated as present
  behaviour, never as debugging history.
- **One vocabulary.** Group/section names match the Data/Transform tabs (§5). "Leakage spine",
  "beats a per-cohort baseline", "season-grouped TimeSeriesSplit", "the cliff is an interaction
  effect" are the canonical phrasings already in use — keep them verbatim.
- **Reconcile outward-facing source in Part 7**: `ml/README.md` (its model/feature/test counts
  and any hosted-doc links), the Makefile `help` strings if any cite stale ML counts,
  `docs/AGENTS.md` if it still describes the ML tab's old two-group shape, and `_roadmap/ml/ML.md`'s
  "41 features" (§0.1).

---

## 10. Build sequence (the 7 parts, expanded)

| Part | Builds | Verify before pausing |
|---|---|---|
| **1** | §0.1 drift fix (`ml-reference` → v4); docs.json five-group nav; `ml_docs_facts.py` + `ml-inventory.mdx` + `ml-inventory-drift` CI job; `docs_facts.py` reconcile-set extension | `gen_ml_reference.py --check` clean (v4); snippet write→check round-trips; `mintlify validate` (new nav pages warn until authored — expected) |
| **2** | Concepts: `ml/overview` polish (gate its numbers) + `ml/feature-contract` (NEW) | `docs-coverage-check`; feature table renders from snippet; forward-refs into unbuilt pages expected |
| **3** | Pipeline: `ml/pipeline` (NEW) + `ml/features-and-targets` (NEW) + `ml/models` polish (move tuning Steps out) | pipeline DAG renders; target tabs resolve; `ml/models` no longer duplicates the tuning block |
| **4** | Pipeline cont.: `ml/tuning` (NEW) + `ml/onnx` (NEW) | tuning Steps land here (not on `ml/models`); ONNX mermaid + parity `<Check>` from snippet |
| **5** | Validation & Trust: `ml/validation` polish (split calibration/cohorts out) + `ml/calibration` (NEW) + `ml/cohorts` (NEW) | CQR LaTeX renders; coverage + cohort tables from snippet; `ml/validation` summarises-and-links, doesn't duplicate |
| **6** | CI Contract: `ml/ci/{overview,leakage-spine,parity-and-schema,evaluation-gates}` (NEW) | every count from the snippet; the 28 = 12+5+3+7+1 reconciles; status badges match `ml/tests/README.md` |
| **7** | Visual payload (`make ml-docs-images` → `docs/images/ml/`); CONVENTIONS sweep; reconcile `ml/README.md`/Makefile-help/AGENTS/`docs_facts`/`_roadmap/ml/ML.md`; full gate run | `docs-audit` + `docs-facts` + `docs-coverage-check` + `ml-inventory-drift` + `reference-drift` + `mintlify validate`/`broken-links` all green |

Pause after each part, report status, do not commit.

---

## 11. Definition of Done

- [ ] §0.1 resolved: the generated reference and all narrative pages agree on one version (v4);
      `gen_ml_reference.py --check` clean.
- [ ] ML tab has five groups in pipeline reading order (§5); every authored page exists and
      renders; `mintlify validate` + `broken-links` clean.
- [ ] **Concepts**: `ml/feature-contract` makes the 42-feature read-only mart contract concrete,
      every count from the gate.
- [ ] **The Pipeline**: the 8-stage `make ml-all` DAG is a navigable narrative —
      features-and-targets, models (objectives), tuning (Optuna), onnx (parity) — each stage's
      what-it-reads/writes/guarantees is legible without opening Python.
- [ ] **Validation & Trust**: the leakage spine, season-grouped CV, the adversarial probe, the
      conformal-interval maths (own page), and the surfaced cohorts (own page) are each first-class.
- [ ] **The CI Contract**: all 28 tests documented and grouped (12 spine one-idea-each + the
      5+3+1 parity/schema clubbed + 7 evaluation gates), every count from `ml-inventory.mdx`.
- [ ] **Model Reference**: regenerated to v4, optionally enriched with an up-link to `ml/models`;
      `reference-drift` gate green.
- [ ] **Gating spine**: `ml_docs_facts.py` + `ml-inventory-drift` CI job live; no ML count is a
      prose literal anywhere; the v3/v4 drift class cannot recur.
- [ ] **Visual payload**: curated artefact plots committed to `docs/images/ml/` via
      `make ml-docs-images`.
- [ ] **CONVENTIONS**: no version/phase framing; holdout `MAX+1`-derived; read-only contract held;
      all links resolve in a clone; `ml/README.md`/AGENTS/`docs_facts`/`_roadmap/ml/ML.md`
      reconciled.
- [ ] All gates green; nothing committed without an explicit go-ahead.
