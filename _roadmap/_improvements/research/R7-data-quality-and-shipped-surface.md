# R7 — Data quality, and what the app is actually serving

**Opened 2026-09-07**, out of a direct question rather than a literature track: *do the app's
models account for the competing-risks finding, and is the data clean?* Two answers, both
measured. All reads `read_only=True`; nothing fitted, nothing shipped.

---

## Part 1 — What the app serves

**Verified — the competing-risks framing is in no version.** `schema.py`'s
`survival:aft` over `[y+1, y+1]` / `[y+1, +inf)` is the single-event framing in every artefact
lineage from v6 to v11. [R3](R3-competing-risks.md)'s finding is unaddressed by the shipped
models, not merely unaddressed by the current one. There is no version to roll forward to.

**Verified — but there is also a version skew, and it is functional, not cosmetic.**

| location | `model_version` | built |
| :--- | :--- | :--- |
| `ml/models/manifest.json` | v11 | 2026-09-05T15:05:40Z |
| `app/public/models/manifest.json` | v11 | 2026-09-05 |
| `app/dist/models/manifest.json` | v11 | 2026-09-05 |
| **deployed production** | **v6**, per decision `D2` | — |

`D2` (raised 2026-09-06, **still OPEN**): *"CDN publish / app deploy — v11 is committed but
production still serves v6."* The `.onnx` files are gitignored (`app/.gitignore:16`); only
`manifest.json`, `model_card.json` and `encoders.json` are tracked.

**Assumed — that production is still on v6.** That is `D2`'s statement as of 2026-09-06 and it
has not been re-checked from this session; the live CDN was not fetched. Worth verifying before
acting on it.

**Why the skew matters more than a version number suggests.** Per `schema.py`'s own version
notes, v10 was *"the first artefact set that actually reflects"* two changes that were already
live in the mart SQL and the constants but had never been through a retrain:

- **The degradation target.** v6 was fitted on the **1-lap** column; Phase 7 moved
  `DEGRADATION_TARGET` to `next_5_lap_cumulative_jump_s`. A v6 artefact is answering a different
  question from the one the docs, the model card and this whole research round describe.
- **The cliff label.** v6 predates Phase 8's source-bounded `driver_skill_residual_s`, which
  **changed the class of 6,825 rows**.

So the live surface is not "slightly older weights". It is a different target and a different
label. Anyone reading the current model card against the deployed app is comparing two things
that were never the same.

---

## Part 2 — Is the data clean?

**Broadly yes, and the missingness is mostly deliberate.** 21 of the 33 contract features are
100% populated on training-eligible rows (n = 120,938). Continuous features keep native NaN for
XGBoost by design (`schema.py`), so a null is a value, not a hole — but only where the null is
*structural*. Two of the twelve are not.

### Structural, and fine

| feature | null rate | why |
| :--- | ---: | :--- |
| `ahead_identity_stability` | 31.0% | Stable at 28.6–32.2% in **every** season. Only 1,449 of 36,044 nulls are "no car ahead" — the rest are the statistic being undefined, not absent. Semantics are *undefined*, not *zero*; worth stating in `schema.yml`. |
| `surface_bulk_ratio` | 12.2% | 11.4–13.6% every season. A ratio guard early in a stint. |
| `gap_ahead_*`, `n_distinct_cars_ahead_3s` | 1.2% | Leader has no car ahead. |
| `push_residual` | 0.31% | — |

### Gap 1 — the 2018 compound dimension has no pre-2019 compounds

**Verified.** `dim_compounds_season` carries five `compound_code` values: HARD (117), MEDIUM
(131), SOFT (130), INTERMEDIATE (16), WET (9). It has **no rows** for SUPERSOFT, ULTRASOFT or
HYPERSOFT — the 2018 naming, before F1 moved to the C1–C5 system.

Consequence: **7,622 training rows (6.30%), every one of them 2018**, carry NULL for **all six**
compound physical parameters — `compound_grip_peak`, `compound_wear_gradient`,
`compound_optimal_temp_low`, `compound_optimal_temp_high`, `compound_cliff_onset_laps`,
`compound_cliff_severity`. Six of the seven columns in the `compound` feature group, gone.

**And `compound_cliff_onset_laps` is the #1 feature on `degradation_regressor_p50`** by both SHAP
and permutation (`model_card.yml`, `dual_importance`). The single most important feature in the
headline model is absent for an entire season's soft-compound running, and absent
**non-randomly** — by season and by compound together.

This is not fatal (XGBoost routes NaN), but it means 2018 is a systematically weaker training
season, and three live items lean on 2018 specifically: `01a`'s season arm starts at 2018–19,
`06b` asks a regulation-era question across the boundary, and `03`'s panel is anchored there.

### Gap 2 — the 2018 position channel is partial

**Verified.** `gap_ahead_min_s` null rate by season: **9.7% in 2018, 0.0% in 2019–2024.** The
entire non-structural proximity gap is one season. Same season as Gap 1.

> **Both gaps land on 2018.** The coherent statement is not "the data has nulls" — it is
> **2018 is a partially-degraded training season**, on two independent axes, and nothing in the
> programme currently accounts for that when 2018 is used as a learning-curve base or a
> regulation-era comparator.

### An open design question — wet-weather laps in a dry-degradation model

**Verified.** INTERMEDIATE (4,867 rows, 4.02%) and WET (212, 0.18%) together are **4.2% of the
degradation training set.** Wet-tyre degradation is a different physical process from dry, and
the nearest published comparator ([Frontiers 2025](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1673148/full),
see [R6](R6-causal-decision-and-the-field.md)) excludes wet and intermediate laps outright.

Not called a defect — the model may be extracting something from them, and `dim_compounds_season`
does parameterise both. But it has never been tested as an arm, and it is a one-line filter to
test under `gates.md`.

---

## Proposed promotions

1. **Backfill `dim_compounds_season` for SUPERSOFT / ULTRASOFT / HYPERSOFT**, or explicitly map
   them onto their C-number equivalents. Cheap, and it repairs the top feature on a whole season.
2. **Re-check `D2` against the live CDN** before any further reasoning about "what users see".
   If production is on v6, every headline in the model card describes a model nobody is running.
3. **Declare `ahead_identity_stability`'s null semantics** in `schema.yml` — undefined, not zero.
4. **A wet/intermediate exclusion arm**, tested under `gates.md` like anything else.
