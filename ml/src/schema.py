"""Single source of truth for the machine learning layer.

Pure constants + the predictions Arrow schema. Everything downstream
(features / train / tune / predict / export_onnx / tests) imports from here so
the feature contract, leakage guards and output schema have exactly one definition.

Column names are verified live against `data/dev.duckdb`
(fct_cliff_prediction_features) by tests/test_features.py::test_feature_contract_subset_of_mart.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import pyarrow as pa

# ─── Reproducibility ──────────────────────────────────────────────────────────
RANDOM_STATE = 20260528  # imported everywhere; any other seed is a defect

# ─── Warehouse handles ──────────────────────────────────────────────────────────
# ML_DUCKDB_PATH lets a caller point the layer at a warehouse other than the local
# dev build. CI needs this: it builds only `data/ci.duckdb` (dbt --target ci), so
# without the override every warehouse-backed step dies on a missing dev.duckdb.
DUCKDB_PATH = os.environ.get("ML_DUCKDB_PATH", "data/dev.duckdb")
MART = "fct_cliff_prediction_features"
STINT_FEATURES = "fct_stint_features"
RACE_TO_TRACK = "race_to_track"

# ─── Leakage / identity exclusions (asserted by tests/test_features.py) ─────────
# Nothing in this set may ever appear as a model feature. Three reasons:
#   * causal leakage  -driver_skill_* literally encode the label
#   * identifiers     -keys / cohort ids (some kept as metadata for eval, never in X)
#   * targets + gate  -current/alt-horizon targets, the classifier label, the eligibility flag
EXCLUDED_LEAKAGE_COLUMNS: frozenset[str] = frozenset({
    # causal leakage (absent from the mart by design; pinned anyway)
    "driver_skill_residual_s", "driver_skill_proxy_s", "driver_skill_residual_proxy_s",
    # D1 RULED 2026-09-07. int_driver_race_skill_loro's columns are barred too, and the
    # reason is the opposite of the one that was assumed. "LORO" in that model means
    # leave-one-DRIVER-out -- a driver is graded against the OTHER same-car drivers in the
    # SAME race (its header: "leave-one-driver-out (LORO) car baseline"). It is NOT
    # leave-one-race-out. The focal race is never excluded: driver_skill_loro_s is
    # `driver_p20_pace_delta_s - loro_car_baseline_s`, and that P20 is the focal driver's
    # own clean laps in the race being predicted. Every CTE in the model groups by
    # (race_year, race_id, ...); no cross-race window exists anywhere in it.
    #
    # Proof, not reading: a driver with exactly ONE race in the whole table still gets a
    # non-NULL value (DOO 2024_24 = 0.0468 off 45 clean laps; AIT 2020_16 = -1.3164 off 61).
    # Under leave-one-race-out there would be no other race to estimate from and the value
    # would have to be NULL. So the column is contemporaneous with the target by
    # construction -- textbook leakage for a model predicting that same race's degradation.
    #
    # Pinned here because the guard is a set intersection on NAMES
    # (tests/test_features.py: `set(X.columns) & EXCLUDED_LEAKAGE_COLUMNS`), so an
    # unlisted column passes straight through. These three were unlisted; the mart simply
    # does not carry them today, which made the safety accidental rather than designed.
    # This does NOT settle whether a genuine leave-one-race-out skill term would be
    # admissible -- no such column has been built. See _improvements/work/00-corrections.md 00c.
    "driver_skill_loro_s", "driver_skill_field_s", "driver_skill_loro_mean_s",
    # identifiers / keys
    "lap_id", "stint_id", "race_id", "race_year", "driver_id", "circuit_key",
    # the training gate
    "is_training_eligible",
    # targets: the modelled one, the alt-horizon ones (forward-looking, never
    # features), the classifier label, and the synthesised / join-time stint-life
    # columns. Every horizon stays barred whichever one DEGRADATION_TARGET names --
    # Phase 7 moved the modelled column from the 1-lap to the 5-lap one and this set
    # did not have to move with it, which is the property test_feature_contract keeps.
    "next_lap_degradation_jump_s",            # legacy (undetrended)
    "next_lap_degradation_jump_detrended_s",  # C1 target; alt-horizon since Phase 7
    "next_3_lap_cumulative_jump_s",
    "next_5_lap_cumulative_jump_s",           # Phase 7 primary target
    "laps_until_cliff_class",
    "remaining_stint_life_laps",   # synthesised target
    "stint_length_laps",           # join-time only → synthesises the target, never a feature
    # C1: per-stint drift slope carried in base; causally encodes the target
    "drift_s_per_lap",
    # C2: IPW weight carried as training metadata, never a predictor
    "survival_weight",
})

# Identifier / metadata columns carried through load_features for splitting & cohort
# eval, but stripped from X. (race_year drives the season split; circuit_key is the
# L0-1 cohort key; compound/constructor_id are also features but handy as cohorts.)
# survival_weight (C2) is carried here so train.py can use it as IPW without it
# entering the feature matrix.
IDENTIFIER_COLUMNS: tuple[str, ...] = (
    "lap_id", "stint_id", "race_year", "race_id", "circuit_key",
    "driver_id", "constructor_id", "is_training_eligible",
    "survival_weight",
)

# ─── Feature set (39) verified members, grouped for ablation ────────────────────
# 02b / D12 (2026-09-21): 32 -> 39. The seven `qualifying` columns join the contract
# GLOBALLY but are MASKED from every family except cliff_classifier -- see
# PER_TARGET_FEATURE_MASK below. The effective width is 39 for cliff_classifier and 32
# for the degradation trio and stint life, which is the shape D12 ruled.
# Phase 9 (2026-09-05): dropped `powertrain` (6), `telemetry_cliff` (5), `weather_air` (2),
# `track` (2) and `context` (3) -- 18 of the prior 42 columns -- on a noise-floor group
# ablation re-run against the v8 mart (5-lap target, repaired cliff label) across all three
# ablation-bearing families (degradation p50, cliff classifier, stint life). A group was kept
# only if its drop delta was positive and cleared that family's own seed-refit floor
# (2*sqrt(2)*sd over 5 reseeds) in at least one of the three; every dropped group cleared in
# none. `powertrain` and `telemetry_cliff` were the mart's entire consumption of
# int_lap_telemetry_aggregates -- dropping them removes every telemetry-aggregate feature
# from the contract, not the ingestion or model behind it (Phase 10 reads the same data for a
# different channel). See the plan's Phase 9 section for the full ablation table and the
# aggregation rule. Kept: `stint_position`, `compound`, `cliff_prior`, `thermal`, `dirty_air`.
# The air-density weather features (air_density_kgm3 / density_ratio_to_ref) were
# DEFERRED here pending enrichment. Closed 2026-08-23 as a measured negative result, not
# as unrealised value: built properly (Tetens, off the bronze pressure_hpa that
# stg_weather drops) they move degradation p50 RMSE -0.33% and cliff macro-F1 +0.70%,
# both inside harness noise, because air density is near a per-circuit constant and
# circuit identity already enters the set three times over. Do not re-open it as an ML
# win; see docs/ml/features-and-targets.mdx. The export-time guard (test_feature_contract)
# asserts contract ⊆ mart so nothing can be referenced before it lands.
# C3 (Route C): surface_bulk_ratio added to the thermal group so the model can attribute
# early-stint surface vs bulk thermal loading (warm-up vs real deg); survives Phase 9's prune.
# Foundations 08j (2026-09-09): dropped `cliff_candidate_flag` from `cliff_prior` (5 -> 4).
# Ruled dead on both substrates by 08g; gate steps 2-4 found it carries no information in any
# family. p10 capacity term measured at +0.0096350, so removing it may be a small gain rather
# than neutral. Contract: 33 -> 32. Three-arm prune verification (add-ablation, reseed floor,
# permutation-null) on AFTER substrate confirms the cost. See build-log.json 08j RESULT.
FEATURE_GROUPS: dict[str, tuple[str, ...]] = {
    "stint_position": ("lap_number", "lap_in_stint", "age_in_stint", "fuel_mass_kg"),
    "compound": (
        "compound", "compound_grip_peak", "compound_wear_gradient",
        "compound_optimal_temp_low", "compound_optimal_temp_high",
        "compound_cliff_onset_laps", "compound_cliff_severity",
    ),
    "cliff_prior": (
        "expected_compound_pace_s", "expected_degradation_rate_s_per_lap",
        "cliff_onset_passed", "laps_past_cliff",
    ),
    "thermal": (
        "push_residual", "cumulative_push_load_surface", "cumulative_push_load_bulk",
        "surface_bulk_ratio",
    ),
    "dirty_air": (
        "dirty_air_share_lap", "dirty_air_thermal_load_surface",
        "dirty_air_thermal_load_bulk", "air_state_dominant",
    ),
    # Phase 10a (2026-09-05). The first group in either series sourced from a
    # DIFFERENT SENSOR rather than from a further transform of the car channel or
    # of lap times -- which is the specific thing the plan's "Not recommended"
    # list says a 43rd feature has to be in order to add information rather than
    # variance. Built in int_lap_proximity from the position channel's ~369
    # samples/lap/driver: each lap is cut into 100 fractions of relative_distance,
    # the session clock at which a driver first enters a fraction is a crossing
    # time of a fixed point on track, and the gap to the car ahead is the
    # difference between two crossings of the same point. Every incumbent traffic
    # feature (the `dirty_air` group above) instead divides FastF1's
    # DistanceToDriverAhead by point speed, which assumes the car ahead is at the
    # same speed as the car behind -- false in exactly the situation the feature
    # describes.
    #
    # ADMITTED ON A MEASUREMENT, not on the argument. Add-ablation on the v10
    # split, same _fit/_score as the production headline, each delta against that
    # family's own 5-reseed floor (2*sqrt(2)*sd):
    #   p50   pinball  1.034661 -> 1.012128  (-0.022532, 1.54x floor)  CLEARS
    #   cliff macro-F1 0.372960 -> 0.380950  (+0.007990, 2.17x floor)  CLEARS
    #   life  AFT NLL  1.956152 -> 1.952005  (-0.004146, 0.59x floor)  inside
    # All nine are kept because reduced arms are strictly worse, not on taste: the
    # gain is monotone in group size on both families that clear -- p50 runs
    # 0.40x (3 cols) / 0.91x (5) / 1.54x (9), cliff 1.44x / 2.07x / 2.17x.
    #
    # And they are ADDITIVE, not a replacement. The plan's checklist called for
    # replacing the DistanceToDriverAhead inputs; the swap arm (drop `dirty_air`,
    # keep `proximity`) lands inside noise on all three families (0.15x / 0.67x /
    # 0.39x) and on the classifier is actually WORSE than the 24-feature baseline.
    # The two groups carry different things and both stay.
    #
    # AND THE GAIN IS INFORMATION, NOT NINE EXTRA SPLIT CANDIDATES -- checked,
    # because a tree model handed more columns can score better on an eval fold
    # without those columns knowing anything. Permutation-null arm: same 33-wide
    # matrix, same params, proximity columns row-shuffled in train and eval, so
    # capacity is preserved exactly and the signal is destroyed.
    #   cliff  capacity -0.000416 (0.11x, nil)  information +0.008406 (2.28x) CLEARS
    #   p50    capacity -0.011286 (0.77x)       information -0.011247 (0.77x)
    #   life   capacity +0.001218 (0.17x)       information -0.005365 (0.77x)
    # So the classifier's win is unambiguously the traffic signal. **p50's is
    # not cleanly attributable**: its total clears the floor but splits about
    # 50/50 between information and capacity, and neither half clears on its own.
    # Recorded rather than rounded up -- see the plan's Phase 10a checkpoint.
    "proximity": (
        "share_lap_within_1s", "share_lap_within_2s", "share_lap_in_train",
        "share_lap_behind_within_1s", "time_within_1s", "gap_ahead_min_s",
        "gap_ahead_median_s", "ahead_identity_stability",
        "n_distinct_cars_ahead_3s",
    ),
    # 02b, Tier 1 -- qualifying. ADMITTED 2026-09-21 by D12, for `cliff_classifier`
    # ONLY; the degradation trio and stint life are masked back to 32 below. Weekend
    # grain (race_year, race_id, driver_id) from int_qualifying_driver_summary,
    # broadcast onto every lap of that driver's race, so every member is
    # stint-invariant by construction (verified: zero stints and zero driver-weekends
    # in the 119,822 training-eligible rows carry more than one distinct value).
    #
    # Re-scored 2026-09-19 on the post-08m substrate (`scripts/arms_02b_qualifying.py`;
    # `ml/artefacts/02b_qualifying_arms.json`). Add-ablation on cv_final_fold, train
    # 2018-2023, eval 2024, each delta over that family's OWN in-run 5-reseed floor
    # (2*sqrt(2)*sd), "raw" = add-ablation, "info" = permutation-corrected (real -
    # shuffled). Clearing needs both, per gates.md:
    #   cliff  A full  raw +7.27x  info +7.47x  CLEARS   macro-F1 0.35247 -> 0.38404
    #          B car   raw +4.60x  info +4.67x  CLEARS            -> 0.37245
    #          C form  raw +6.80x  info +6.56x  CLEARS            -> 0.38196
    #   p90    B car   raw +1.90x  info +1.42x  clears   pinball  0.51285 -> 0.49693
    #          C form  raw +1.04x  info +1.20x  clears            -> 0.50415
    #          A full  raw +1.41x  info +0.95x  MISSES (dilution: the union pays more
    #                  capacity than the halves earn back -- Phase 10a's trap, mirrored)
    #   p10/p50/stint life -- nothing reaches its floor on any arm.
    # C beats B on cliff, so the carrying channel is the DRIVER's one-lap form, not the
    # car term. All 7 are admitted together (Arm A) rather than B or C alone: A is the
    # best cliff arm, and the pre-registration carries `quali_push_laps_n` in A only,
    # as the explicit coverage indicator for the other six.
    #
    # WHY p90 IS NOT ADMITTED THOUGH B AND C CLEARED IT. Not a reading of the evidence
    # -- a ruling (D12) taken against a machinery constraint. features.py:178 keys
    # PER_TARGET_FEATURE_MASK by TargetSpec.family, and p10/p50/p90 share the single
    # family `degradation_regressor`, so "p90 only" is INEXPRESSIBLE by masking: it
    # means all three quantile heads (p10 measurably worse, C at raw -2.93x) or a code
    # change keying the mask by target name. D12 chose neither and closed the trio at
    # 32. Re-opening p90 is a code change first, not an edit to this dict.
    #
    # Gate 7 (e-BH) rejects NOTHING here, and that is structural, not a weak result:
    # under the declared Construction B at n=5, g=1, E is capped at 36 while e-BH needs
    # E >= 20*m = 400 for this item's 20 declared hypotheses. Best measured E is 32.6.
    # The admission rests on gates 3 + 4 (floor + information split), which is what
    # D12 ruled on. See 02-feature-expansion.md sec.11 and 09c.
    #
    # Missingness is a measured 1.947% on six of the seven, NOT forward leakage (a
    # driver-weekend's qualifying record is settled before the race starts). It is
    # concentrated in 2018 (7.98%, an upstream ingestion gap -- LEC/OCO/PER/ALO/BOT all
    # qualified for 2018_1 and all lack rows) and it is not label-neutral: NULL rows are
    # 39% likelier to sit within 2 laps of a cliff crossing. `quali_push_laps_n` is
    # COALESCE-d to 0 at source and is a PERFECT indicator of that pattern (verified
    # both directions), so the channel is explicit rather than an implicit NaN pattern a
    # tree could split on. The other six stay NULL -> XGBoost native missing.
    #
    # `quali_vs_race_skill_delta_s` exists upstream and is deliberately NOT carried: it
    # is a same-race average of driver_skill_residual_s, unknowable until the race has
    # finished -- the forward-reach defect int_qualifying_decomposed's own
    # aggregation_scope_exemptions entry names.
    "qualifying": (
        "quali_push_laps_n",
        "quali_constructor_pace_mean_s", "quali_constructor_pace_se_mean_s",
        "quali_pace_delta_best_s", "quali_ratio_to_segment_best_min",
        "quali_skill_session_avg_s", "quali_segments_contested_n",
    ),
}

# Flat, ordered feature list (group order preserved → deterministic column order).
FEATURE_COLUMNS: tuple[str, ...] = tuple(
    col for group in FEATURE_GROUPS.values() for col in group
)
assert len(FEATURE_COLUMNS) == len(set(FEATURE_COLUMNS)), "duplicate feature column"

# ─── Categorical handling ─────────────────────────────────────────────────────────
# String categoricals → ordinal-encoded from the TRAINING map; NULL/unseen → MISSING_ORDINAL.
CATEGORICAL_COLUMNS: tuple[str, ...] = ("compound", "air_state_dominant")
# Booleans → float (True=1.0, False=0.0, NULL=NaN → native-NaN).
BOOLEAN_COLUMNS: tuple[str, ...] = ("cliff_onset_passed",)
# Continuous features keep NaN as NaN (XGBoost native missing). Reserved ordinal for missing categoricals:
MISSING_ORDINAL = -1.0

# Label-adjacent features that must clear the forward-window audit before they stay in.
# anomaly_class dropped by Phase 9 (2026-09-05): it left FEATURE_COLUMNS with the `context`
# group, and leaving it here would point the forward-window audit at a column no longer in
# the contract -- a gate asserting over nothing (Corrections §6's shape).
# cliff_candidate_flag pruned by 08j (2026-09-09): ruled dead on both substrates by 08g,
# p10 capacity term +0.0096350 suggests removing it is a small gain, contract 33 -> 32.
AUDIT_FEATURES: tuple[str, ...] = ()

# ─── Targets / model families ───────────────────────────────────────────────────
# Phase 7: the modelled degradation column is the 5-lap cumulative jump, not the
# next-lap one. Both are detrended at source; the 5-lap column subtracts 5x the current
# residual and 15x the per-stint drift from the sum of the next five leads, and Phase 4
# verified that closed form to max |diff| 3.2e-14. Three consequences live in this file:
# TARGET_HORIZON_LAPS (below) makes the ceiling arithmetic thin overlapping windows,
# TARGET_BOUND_BY_COLUMN carries the +/-50 s clip the SQL applies to it rather than the
# +/-10 s of the 1-lap column, and every horizon stays in EXCLUDED_LEAKAGE_COLUMNS.
# The cost is rows: the column is NULL unless five consecutive laps follow in the same
# stint, which drops 114,274 -> 82,315 training rows, and drops them from the END of
# stints (18.9% of laps 1-5 vs 50.4% of lap 31+). See the Phase 7 checkpoint.
DEGRADATION_TARGET = "next_5_lap_cumulative_jump_s"  # was next_lap_degradation_jump_detrended_s (C1)
CLIFF_TARGET = "laps_until_cliff_class"
STINT_LIFE_TARGET = "remaining_stint_life_laps"  # synthesised in features.py
STINT_LIFE_CENSOR_COLUMN = "is_censored_stint"  # from fct_stint_features; TRUE => right-censored

# Forward horizon of each target column, in laps. Phase 6 (attainable ceilings) needs it:
# a rolling-window target overlaps itself, so consecutive rows share `h - 1` of their `h`
# terms and any within-stint independence assumption is false by construction. Two things
# key off this and both are silently wrong without it -- the between-stint variance share
# (ml/src/ceiling.py thins to non-overlapping windows when h > 1) and the reading of the
# within-stint lag-1 autocorrelation (white-noise increments already give (h-1)/h).
# Phase 7 flips DEGRADATION_TARGET to the 5-lap column; this map is what makes that a
# one-line change rather than a silent regression in the ceiling arithmetic.
TARGET_HORIZON_LAPS: dict[str, int] = {
    "next_lap_degradation_jump_detrended_s": 1,
    "next_lap_degradation_jump_s": 1,
    "next_3_lap_cumulative_jump_s": 3,
    "next_5_lap_cumulative_jump_s": 5,
    CLIFF_TARGET: 1,
    STINT_LIFE_TARGET: 1,
}

# ─── Stint-life survival (AFT) contract ─────────────────────────────────────────
# Remaining stint life is right-censored on 46.2% of training rows (55,926 of
# 120,934): a driver's last
# stint of a race ends at the flag or at retirement, so the observed life is a LOWER
# bound on the life the tyre had. Squared error against that lower bound trains the
# model to predict the pit wall's decision, not the tyre's limit.
#
# survival:aft over the interval [y+1, y+1] (uncensored) / [y+1, +inf) (censored)
# fits log(life+1) ~ Normal(margin, scale), i.e. life+1 is log-normal. The +1 shift
# exists because log(0) is -inf and 2,264 training rows have zero remaining life --
# 2,236 of them (98.8%) censored, i.e. final laps of final stints. Subtract it back
# at predict time.
AFT_LABEL_SHIFT = 1.0             # log(0) guard; predict returns exp(margin) - SHIFT
AFT_DISTRIBUTION = "normal"       # normal on the log scale == log-normal in laps
# Swept at the production params, season-grouped CV, 5 folds: NLL runs 3.062 (0.30),
# 2.483 (0.40), 2.237 (0.50), 2.140 (0.60), 2.101 (0.70), 2.0905 (0.80), 2.094 (0.85),
# 2.115 (1.00) -- an interior optimum at 0.80, not a boundary. The plan carried ~0.5
# from a sweep at different params; against 0.5 the move is -6.54% NLL, 5/5 folds,
# paired t=10.254 p=0.0005. Production reads it from
# ml/models/stint_life_regressor_best_params.json; this is the smoke/fallback value.
AFT_SCALE_DEFAULT = 0.8
# Reported band. A log-normal median is exp(margin); quantile q is
# exp(margin + scale * Phi^-1(q)). One extra scalar buys the whole distribution.
STINT_LIFE_QUANTILES: tuple[float, ...] = (0.10, 0.50, 0.90)

# Fixed class order (matches accepted_values in marts/schema.yml). Index == XGBoost label.
CLIFF_CLASS_LABELS: tuple[str, ...] = ("0_to_2", "3_to_5", "6_plus", "none_in_stint")
# D5: the degradation target is clipped at source, and the clip is per-column -- the
# 1-lap columns at +/-10 s, the 3-lap at +/-30 s, the 5-lap at +/-50 s (see
# fct_cliff_prediction_features.sql). Phase 7's checklist called for reconciling the two
# deliberately rather than inheriting either: the bound follows the column, because it
# is the SQL that enforces it and a bound that disagreed with the SQL would be a claim
# about the data rather than a fact about it. TARGET_BOUND stays as the name every
# consumer already reads (test_features, export_onnx's manifest) and now resolves
# through the map, so flipping DEGRADATION_TARGET moves it automatically.
TARGET_BOUND_BY_COLUMN: dict[str, float] = {
    "next_lap_degradation_jump_s": 10.0,
    "next_lap_degradation_jump_detrended_s": 10.0,
    "next_3_lap_cumulative_jump_s": 30.0,
    "next_5_lap_cumulative_jump_s": 50.0,
}
TARGET_BOUND = TARGET_BOUND_BY_COLUMN[DEGRADATION_TARGET]


@dataclass(frozen=True)
class TargetSpec:
    name: str            # artefact base name, e.g. "degradation_regressor_p50"
    family: str          # degradation_regressor | cliff_classifier | stint_life_regressor
    source_column: str   # mart column or synthesised name
    kind: str            # "quantile" | "classification" | "survival"
    objective: str
    quantile_alpha: float | None = None
    num_class: int | None = None


PRODUCTION_TARGETS: tuple[TargetSpec, ...] = (
    TargetSpec("degradation_regressor_p10", "degradation_regressor", DEGRADATION_TARGET,
               "quantile", "reg:quantileerror", quantile_alpha=0.10),
    TargetSpec("degradation_regressor_p50", "degradation_regressor", DEGRADATION_TARGET,
               "quantile", "reg:quantileerror", quantile_alpha=0.50),
    TargetSpec("degradation_regressor_p90", "degradation_regressor", DEGRADATION_TARGET,
               "quantile", "reg:quantileerror", quantile_alpha=0.90),
    TargetSpec("cliff_classifier", "cliff_classifier", CLIFF_TARGET,
               "classification", "multi:softprob", num_class=len(CLIFF_CLASS_LABELS)),
    TargetSpec("stint_life_regressor", "stint_life_regressor", STINT_LIFE_TARGET,
               "survival", "survival:aft"),
)
TARGET_BY_NAME: dict[str, TargetSpec] = {t.name: t for t in PRODUCTION_TARGETS}

# Per-FAMILY feature mask, applied in features.py:176-179.
#
# READ THE KEY CAREFULLY: it is `TargetSpec.family`, NOT `TargetSpec.name`. features.py
# looks up `S.TARGET_BY_NAME[target].family`, so a key spelled `degradation_regressor_p10`
# would never be read and would mask NOTHING -- it would sit here looking like a guard
# while every quantile head kept seeing the columns. p10, p50 and p90 share the single
# family `degradation_regressor` (see PRODUCTION_TARGETS above), so they cannot be masked
# apart without keying this dict by target name instead, which is a code change in
# features.py and not an edit here.
#
# Two entries, two different reasons:
#
# 1. `stint_length_laps` is masked from stint life because it would memorise the answer
#    (the target is stint_length_laps - lap_in_stint). It is never in FEATURE_COLUMNS, so
#    that half is belt-and-braces.
#
# 2. The seven `qualifying` columns (02b) ARE in FEATURE_COLUMNS, so for them this mask is
#    load-bearing, not belt-and-braces -- it is the only thing implementing D12's
#    "cliff_classifier only". Removing either entry silently widens a family that did not
#    earn the columns. Measured on the post-08m substrate: the degradation trio clears
#    nothing at p10/p50 (p10 is actively worse, Arm C at raw -2.93x floor) and stint life
#    clears nothing on any arm (best raw +0.87x; Arm C's information term is +0.00003,
#    i.e. the driver-form columns do precisely nothing for remaining stint life once
#    capacity is accounted for). p90 DID clear on arms B and C individually but is masked
#    anyway, because it shares a family with p10 and p50 -- see the FEATURE_GROUPS
#    ["qualifying"] note.
#
# Effective contract width: cliff_classifier 39, everything else 32.
#
# NOTE FOR THE v13 EXPORT (not fixed here, no retrain in this change): this is the first
# mask that actually removes a FEATURE_COLUMNS member, so the feature vector is now
# per-model. export_onnx.py:298-300 still writes ONE global `input` block from
# len(S.FEATURE_COLUMNS), and tests/test_manifest_contract.py
# ::test_manifest_input_width_matches_the_actual_booster is parametrized over all five
# targets against that single declared width. Once v13 artefacts exist, four of those five
# boosters will be 32-wide against a 39-wide declaration. The manifest needs a per-model
# feature_order before the browser scores v13, or it will build the wrong vector.
PER_TARGET_FEATURE_MASK: dict[str, frozenset[str]] = {
    "stint_life_regressor": frozenset({"stint_length_laps"}) | frozenset(FEATURE_GROUPS["qualifying"]),
    "degradation_regressor": frozenset(FEATURE_GROUPS["qualifying"]),
}


def feature_columns_for(target: str) -> tuple[str, ...]:
    """The effective, ordered feature contract for one target, after PER_TARGET_FEATURE_MASK.

    Since 02b/D12 the contract is no longer one width: `cliff_classifier` takes 39 columns
    and every other family takes 32. Anything that builds a feature matrix or declares a
    feature order must go through here rather than through FEATURE_COLUMNS directly, or it
    will hand a 39-wide matrix to a 32-wide booster. Order is FEATURE_COLUMNS order with the
    masked members removed, which is the order features.py fits in and therefore the order
    positional scoring requires.
    """
    masked = PER_TARGET_FEATURE_MASK.get(TARGET_BY_NAME[target].family, frozenset())
    return tuple(c for c in FEATURE_COLUMNS if c not in masked)


def artefact_name(spec: TargetSpec, version: str) -> str:
    """version ∈ {"smoke", "v1"…"v5"} → e.g. degradation_regressor_p50_v5."""
    return f"{spec.name}_{version}"


def optuna_study_name(target: str, version: str) -> str:
    """Optuna study + sqlite DB stem for a target at a given model version,
    e.g. cliff_classifier_v3. Keying off the version (rather than a hardcoded
    'v1') means a fresh tuning run per version gets its own study namespace."""
    return f"{target}_{version}"


# ─── Predictions output schema (19 columns) ─────────────────────────────────────
# Validated at write time by predict.py and by tests/test_predict.py.
PROB_COLUMNS: tuple[str, ...] = tuple(f"prob_{c}" for c in CLIFF_CLASS_LABELS)

PREDICTIONS_ARROW_SCHEMA = pa.schema([
    ("lap_id", pa.string()),
    ("stint_id", pa.string()),
    ("race_year", pa.int32()),
    ("circuit_key", pa.string()),
    ("is_holdout", pa.bool_()),          # race_year == HOLDOUT_SEASON
    ("is_in_envelope", pa.bool_()),      # is_training_eligible
    ("predicted_degradation_jump_s", pa.float64()),       # p50
    ("predicted_degradation_jump_p10_s", pa.float64()),
    ("predicted_degradation_jump_p90_s", pa.float64()),
    ("predicted_cliff_class", pa.string()),               # argmax
    (PROB_COLUMNS[0], pa.float64()),
    (PROB_COLUMNS[1], pa.float64()),
    (PROB_COLUMNS[2], pa.float64()),
    (PROB_COLUMNS[3], pa.float64()),
    # AFT log-normal median, in laps, with the 10th/90th percentile of the same
    # fitted distribution. The median is the headline the gauge renders; the band
    # is what stops one decimal place claiming more than a 45.8%-censored fit can.
    ("predicted_remaining_stint_life_laps", pa.float64()),      # median
    ("predicted_remaining_stint_life_p10_laps", pa.float64()),
    ("predicted_remaining_stint_life_p90_laps", pa.float64()),
    ("model_version", pa.string()),
    ("predicted_at", pa.timestamp("us")),
])
assert len(PREDICTIONS_ARROW_SCHEMA) == 19, "predictions schema must be 19 columns"

MODEL_VERSION_DEFAULT = "v13"  # v13 = the four-item bundle (08i, 02b, 08o, 08q), landed as ONE
# version bump per D16. Four independent changes ride it; the union touches all five fits, which is
# why it is one bump and not four (D16's trace: a version EXISTS only when all five .bst files exist
# at it, since predict.py loads the set at one version and raises if any is missing).
#
#   08i (D10) - `int_lap_thermal_proxy` min_observations 2 -> 1. Reverts a floor nobody chose on
#     evidence: it was set on 2026-09-10 by a session that left no artefact and rode into git inside
#     a commit about something else. Measured through the full gate on the v12/08m substrate, floor 1
#     is better on all three degradation heads and uniformly better than floor 2 across families;
#     floors 3 and 5 lose coverage AND signal and are dead. Moves the four thermal columns, which are
#     unmasked, so it moves all five fits.
#   02b (D12) - the seven `qualifying` columns join FEATURE_COLUMNS for `cliff_classifier` ONLY
#     (clears at 4.6x-6.8x its floor on all three arms). The degradation trio and stint life stay at
#     32 columns. **This is the first version whose feature contract is not one width**: 39 for the
#     classifier, 32 for everything else, implemented by PER_TARGET_FEATURE_MASK above and readable
#     only through `feature_columns_for()`. p90 cleared on arms B and C individually but is masked
#     anyway, because the mask is family-level and p90 shares a family with p10 and p50.
#   08o - the IPW survival sample weight comes off the degradation quantile heads
#     (`train.py::_sample_weight` now returns None for kind == "quantile"). 08f-1 measured uniform as
#     better on all three heads, every delta inside its own reseed floor, with one floor-clearing
#     permutation-null information cost on p10. Touches three of five fits. Recorded as a null-shaped
#     result that tidies a mechanism, NOT as a headline win - see 08o's leaf doc before quoting it.
#   08q - `theta_air` stops being a COALESCE default. The hardcoded 0.5 s/lap was 3.8x the estimate
#     (+0.1310 s/lap, 95% CI [+0.1144, +0.1476]). Confined to `int_dirty_air_tax_component.sql`, so
#     it moves the label for the trio and the classifier (four of five on substance); stint life's
#     target is synthesised in features.py and does not carry it.
#
# **What is comparable across v12 -> v13.** Nothing, head-to-head, without care. 08q moves the LABEL
# for four of five families, so - exactly as at 08m - `next_5_lap_cumulative_jump_s` and
# `laps_until_cliff_class` are different quantities under unchanged column names, and
# `_guard_target_change` cannot catch it because it compares target column NAMES. A smaller v13
# pinball loss is not automatically skill. The admissible comparisons are the per-arm, fixed-target
# measurements already recorded in each item's leaf doc, not the v12/v13 eval headlines.
# **v12 is the rollback floor, with one caveat**: 08o's measurement session on 2026-09-21 refit and
# re-exported the three degradation v12 artefacts IN PLACE (14:13-14:14), so the trio's v12 files on
# disk are 08o's uniform-weight arm, not the published v12 fit. v11 is intact and is the clean floor.
#
# v12 = work item 08m's repair of the compound wear curve. NOT a
# feature-contract change and NOT a re-tune: the contract is v11's 32 columns unchanged and every
# target keeps its own `*_best_params.json`, i.e. v11's hyperparameters. What moved is what two of
# those columns MEAN. `int_compound_cliff_predicted.sql` was multiplying `compound_cliff_severity`
# -- fitted by `survival.py::estimate_cliff_severity` as a ~5.5-lap LEVEL SHIFT -- by
# `laps_past_cliff`, i.e. consuming a magnitude as a per-lap rate (48.7% of it was ordinary wear
# already charged by `wear_gradient*age`), and adding a hardcoded `0.002*age^2` that was never
# fitted against anything. 08m replaced both with a moment-matched saturating ramp defined once in
# `transform/macros/compound_cliff_wear.sql`.
#
# **Why this is a new version rather than a v11 rebuild.** `expected_compound_pace_s` is subtracted
# into `driver_skill_residual_s`, so the degradation trio's target
# (`next_5_lap_cumulative_jump_s`, mean -1.8793 -> -0.3946 s, training-eligible rows 82,470 ->
# 81,619) and `cliff_classifier`'s label (`laps_until_cliff_class`, 10.79% of rows changed class)
# are DIFFERENT QUANTITIES UNDER UNCHANGED COLUMN NAMES. That is the exact hazard
# `train.py::_guard_target_change` was written to refuse -- and note that the guard CANNOT catch
# this one, because it compares target column *names*, which did not change. It is caught here, by
# the version, or not at all.
#
# **v11's numbers are therefore not a baseline for v12's.** v11's eval headline
# (p10 0.53202 / p50 1.04679 / p90 0.57851) was measured against the superseded target; a smaller
# v12 pinball loss is a smaller target spread, not skill. The only admissible comparisons are at
# fixed target: each model against its own baseline on the rebuilt target. `stint_life_regressor`
# is the one exception -- its target (`remaining_stint_life_laps`, from `int_stint_geometry`) is
# untouched by 08m and only its INPUTS moved, so its v11/v12 headlines ARE comparable, as a
# feature-definition change on a fixed target. **v11 is the rollback floor** and is retained on
# disk in full. See `_improvements/work/08-foundations-repair.md` -> 08m and 08n.
#
# v11 = Phase 10a: the `proximity` group (9 columns) joins the
# contract, 24 -> 33. It is the first version in either series whose feature change comes from
# a DIFFERENT SENSOR -- the position channel of the telemetry stream, whose ~58.8M rows had no
# consumer at all before Phase 10 (stg_telemetry projected them and int_lap_telemetry_aggregates
# filtered them out). Everything else is held fixed: same targets, same labels, same
# hyperparameters, same split. Nothing was re-tuned, so v10 -> v11 is attributable to the nine
# columns and to nothing else, which is the property the group ablation above needs in order to
# mean anything. See the FEATURE_GROUPS["proximity"] note for the acceptance numbers and
# ml/src/schema.py's Phase 9 note for what the contract looked like before. **v10 is the
# rollback floor** and the last shipped set before this one. Prior version notes follow.
#
# v10 = Phase 9's pruned feature contract: FEATURE_GROUPS drops
# `powertrain`, `telemetry_cliff`, `weather_air`, `track` and `context` (18 of 42 columns),
# leaving 24. It is the first version fitted against the two target/label changes that were
# already live in the mart SQL and this file's constants but had never been shipped through a
# retrain -- DEGRADATION_TARGET is Phase 7's 5-lap cumulative jump
# (next_5_lap_cumulative_jump_s), and CLIFF_TARGET's underlying laps_until_cliff_class is
# scored against Phase 8's source-bounded driver_skill_residual_s (6,825 rows changed class).
# Both were already the code's truth under the stale "v6" label; v10 is the first artefact set
# that actually reflects them. v9 is not in this lineage -- it is an abandoned 42-feature
# search-space-widening probe (open item 21) run on only 2 of the 5 targets and explicitly
# "not worth shipping." **v6 is the rollback floor**: it is the last version actually exported
# to `app/public/models/` (v7/v8 never left `ml/models/` as shipped artefacts), so it is what
# v10 has to clear and what a revert falls back to. Prior version notes follow.
#
# v6 = v5's features and cliff label, unchanged, with the
# stint-life model moved from reg:squarederror to survival:aft over an interval label.
# The contract changed, not just the weights: the booster emits a log-scale margin, the
# predictions parquet gained p10/p90 life columns (17 -> 19), and the ONNX graph needs a
# post-transform the app reads from the manifest. v5 is kept for rollback and is the
# floor v6 has to clear. Prior version note follows.
#
# v5 = v4's 42 features, unchanged, against the repaired
# laps_until_cliff_class label (first threshold crossing scanned over the whole remaining
# stint at true lap offsets, so 6_plus is 6-or-more rather than exactly 6). The feature
# matrix is byte-identical to v4's; only the classifier's target moved. v4 kept for diff
# and rollback, and its metrics are the floor v5 has to clear.
