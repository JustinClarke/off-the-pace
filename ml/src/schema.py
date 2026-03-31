"""Single source of truth for the machine learning layer.

Pure constants + the predictions Arrow schema. Everything downstream
(features / train / tune / predict / export_onnx / tests) imports from here so
the feature contract, leakage guards and output schema have exactly one definition.

Column names are verified live against `data/dev.duckdb`
(fct_cliff_prediction_features) by tests/test_features.py::test_feature_contract_subset_of_mart.
"""
from __future__ import annotations

from dataclasses import dataclass

import pyarrow as pa

# ─── Reproducibility ──────────────────────────────────────────────────────────
RANDOM_STATE = 20260528  # imported everywhere; any other seed is a defect

# ─── Warehouse handles ──────────────────────────────────────────────────────────
DUCKDB_PATH = "data/dev.duckdb"
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
    # identifiers / keys
    "lap_id", "stint_id", "race_id", "race_year", "driver_id", "circuit_key",
    # the training gate
    "is_training_eligible",
    # targets: next-lap (modelled), alt-horizon (forward-looking, never features),
    # the classifier label, and the synthesised / join-time stint-life columns
    "next_lap_degradation_jump_s",            # legacy (undetrended)
    "next_lap_degradation_jump_detrended_s",  # C1 primary target
    "next_3_lap_cumulative_jump_s",
    "next_5_lap_cumulative_jump_s",
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

# ─── Feature set (42) verified members, grouped for ablation (§7.3) ───────────
# The `powertrain` (6) and `telemetry_cliff` (5) groups land with telemetry ingestion
# (ml-v0.2 §2): per-lap aggregates projected by int_lap_telemetry_aggregates →
# fct_cliff_prediction_features. They are gated by the pre-registered §2.3 ablation  
# kept here only because they beat the _v2 baseline (see ml/artefacts/ablation_*).
# The air-density weather features (air_density_kgm3 / density_ratio_to_ref) remain
# DEFERRED pending air-density enrichment (transform §5.6); the export-time guard
# (test_feature_contract) asserts contract ⊆ mart so nothing can be referenced before it lands.
# C3 (Route C): surface_bulk_ratio added as 42nd feature to the thermal group so the
# model can attribute early-stint surface vs bulk thermal loading (warm-up vs real deg).
FEATURE_GROUPS: dict[str, tuple[str, ...]] = {
    "stint_position": ("lap_number", "lap_in_stint", "age_in_stint", "fuel_mass_kg"),
    "compound": (
        "compound", "compound_grip_peak", "compound_wear_gradient",
        "compound_optimal_temp_low", "compound_optimal_temp_high",
        "compound_cliff_onset_laps", "compound_cliff_severity",
    ),
    "cliff_prior": (
        "expected_compound_pace_s", "expected_degradation_rate_s_per_lap",
        "cliff_onset_passed", "laps_past_cliff", "cliff_candidate_flag",
    ),
    "thermal": (
        "push_residual", "cumulative_push_load_surface", "cumulative_push_load_bulk",
        "surface_bulk_ratio",
    ),
    "dirty_air": (
        "dirty_air_share_lap", "dirty_air_thermal_load_surface",
        "dirty_air_thermal_load_bulk", "air_state_dominant",
    ),
    "powertrain": (
        "n_gear_changes", "mean_rpm", "max_rpm",
        "pct_full_throttle", "pct_drs_active", "short_shift_index",
    ),
    "telemetry_cliff": (
        "mid_corner_speed_loss_kph", "traction_wheelspin_proxy",
        "throttle_trace_decay", "braking_point_drift_m", "lift_coast_share",
    ),
    "weather_air": ("ambient_temp_delta", "is_rain_lap"),
    "track": ("track_energy_index", "circuit_abrasiveness_index"),
    "context": ("constructor_id", "event_flag_any", "anomaly_class"),
}

# Flat, ordered feature list (group order preserved → deterministic column order).
FEATURE_COLUMNS: tuple[str, ...] = tuple(
    col for group in FEATURE_GROUPS.values() for col in group
)
assert len(FEATURE_COLUMNS) == len(set(FEATURE_COLUMNS)), "duplicate feature column"

# ─── Categorical handling (§5.1, L0-3) ──────────────────────────────────────────
# String categoricals → ordinal-encoded from the TRAINING map; NULL/unseen → MISSING_ORDINAL.
CATEGORICAL_COLUMNS: tuple[str, ...] = ("compound", "air_state_dominant", "constructor_id", "anomaly_class")
# Booleans → float (True=1.0, False=0.0, NULL=NaN → native-NaN).
BOOLEAN_COLUMNS: tuple[str, ...] = ("cliff_onset_passed", "event_flag_any", "cliff_candidate_flag", "is_rain_lap")
# Continuous features keep NaN as NaN (XGBoost native missing). Reserved ordinal for missing categoricals:
MISSING_ORDINAL = -1.0

# Label-adjacent features that must clear the M1 forward-window audit before they stay in (§15-5).
AUDIT_FEATURES: tuple[str, ...] = ("cliff_candidate_flag", "anomaly_class")

# ─── Targets / model families (§5.3) ────────────────────────────────────────────
DEGRADATION_TARGET = "next_lap_degradation_jump_detrended_s"  # C1: detrended (was next_lap_degradation_jump_s)
CLIFF_TARGET = "laps_until_cliff_class"
STINT_LIFE_TARGET = "remaining_stint_life_laps"  # synthesised in features.py

# Fixed class order (matches accepted_values in marts/schema.yml). Index == XGBoost label.
CLIFF_CLASS_LABELS: tuple[str, ...] = ("0_to_2", "3_to_5", "6_plus", "none_in_stint")
TARGET_BOUND = 10.0  # next_lap_degradation_jump_s ∈ [-TARGET_BOUND, +TARGET_BOUND] (D5)


@dataclass(frozen=True)
class TargetSpec:
    name: str            # artefact base name, e.g. "degradation_regressor_p50"
    family: str          # degradation_regressor | cliff_classifier | stint_life_regressor
    source_column: str   # mart column or synthesised name
    kind: str            # "quantile" | "classification" | "regression"
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
               "regression", "reg:squarederror"),
)
TARGET_BY_NAME: dict[str, TargetSpec] = {t.name: t for t in PRODUCTION_TARGETS}

# stint_length_laps is masked from the stint-life model's X (would memorise the answer).
# It is never in FEATURE_COLUMNS; the mask is a belt-and-braces guard applied in features.py.
PER_TARGET_FEATURE_MASK: dict[str, frozenset[str]] = {
    "stint_life_regressor": frozenset({"stint_length_laps"}),
}


def artefact_name(spec: TargetSpec, version: str) -> str:
    """version ∈ {"smoke", "v1", "v2", "v3"} → e.g. degradation_regressor_p50_v3."""
    return f"{spec.name}_{version}"


def optuna_study_name(target: str, version: str) -> str:
    """Optuna study + sqlite DB stem for a target at a given model version,
    e.g. cliff_classifier_v3. Keying off the version (rather than a hardcoded
    'v1') means a fresh tuning run per version gets its own study namespace."""
    return f"{target}_{version}"


# ─── Predictions output schema (§5.6 / plan §6.5)-17 columns ──────────────────
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
    ("predicted_remaining_stint_life_laps", pa.float64()),
    ("model_version", pa.string()),
    ("predicted_at", pa.timestamp("us")),
])
assert len(PREDICTIONS_ARROW_SCHEMA) == 17, "predictions schema must be 17 columns"

MODEL_VERSION_DEFAULT = "v4"  # v4 = 42-feature (+ surface_bulk_ratio), detrended target (Route C); v3 kept for diff
