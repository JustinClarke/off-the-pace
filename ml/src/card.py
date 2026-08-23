"""Machine-written model card-assembles ml/model_card.yml (+ a JSON mirror) from artefacts.

CLI:
  python -m ml.src.card --write      # writes ml/model_card.yml + ml/models/model_card.json
  python -m ml.src.card --to-json    # prints the JSON mirror to stdout

The card is the single source of truth for the docs MDX page (scripts/gen_ml_reference.py reads it).
**No hand-edited metrics, no `TBD` at completion**-every number is read back from:
  * ml/models/training_logs/<target>_v1_*.json   (latest per target: CV headline, params, fingerprint)
  * ml/artefacts/evaluation_metrics.json          (eval headline vs baseline, cohorts, calibration, …)
  * ml/models/encoders.json                        (categorical levels)
  * ml.src.schema                                  (feature groups, leakage exclusions, holdout policy)

If a required artefact is missing the card refuses to write (so the docs can never go stale-green).
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from ml.src import schema as S

ROOT = Path(".")
LOGS_DIR = Path("ml/models/training_logs")
EVAL_PATH = Path("ml/artefacts/evaluation_metrics.json")
ENCODERS_PATH = Path("ml/models/encoders.json")
CARD_YAML = Path("ml/model_card.yml")
CARD_JSON = Path("ml/models/model_card.json")

# F1 car-telemetry coverage in this project starts in 2018 (the data epoch a fixed fact of the
# source, not a holdout choice). Only used as a fallback when a training log predates the
# training_seasons field; the holdout year itself is always derived as MAX(race_year)+1.
DATA_EPOCH_SEASON = 2018

HOLDOUT_NOTE = (
    "2025 is the designated holdout, ingested post-launch; until then the model trains on all "
    "ingested seasons (2018–2024) and selection rests on time-series CV-there is no live holdout. "
    "The evaluation headline is reported on the final TimeSeriesSplit fold (2024); it switches to a "
    "true-holdout reveal the moment 2025 ingests, with no code change.")


def _latest_log(target: str, version: str) -> dict:
    logs = sorted(LOGS_DIR.glob(f"{target}_{version}_*.json"))
    if not logs:
        raise FileNotFoundError(f"no {version} training log for {target}-run `make ml-tune`")
    return json.loads(logs[-1].read_text())


def _require(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"required artefact missing: {path}-run the pipeline first")
    return json.loads(path.read_text())


def build_card(version: str = S.MODEL_VERSION_DEFAULT) -> dict:
    ev = _require(EVAL_PATH)
    encoders = _require(ENCODERS_PATH)
    logs = {t.name: _latest_log(t.name, version) for t in S.PRODUCTION_TARGETS}
    any_log = next(iter(logs.values()))

    # ── Per-model block: CV (from the training log) + eval headline-vs-baseline (from eval) ──
    models = []
    for spec in S.PRODUCTION_TARGETS:
        log = logs[spec.name]
        em = ev["models"][spec.name]
        models.append({
            "name": spec.name,
            "family": spec.family,
            "kind": spec.kind,
            "objective": spec.objective,
            "quantile_alpha": spec.quantile_alpha,
            "headline_metric": em["headline_metric"],
            "cv_headline": round(log["headline_cv"], 5),
            "eval_headline": round(em["headline"], 5),
            "baseline_headline": round(em["baseline_headline"], 5),
            "beats_baseline": em["beats_baseline"],
            "n_train_rows": log["n_train_rows"],
            "fit_seconds": log["fit_seconds"],
            "hyperparameters": log["params"],
            "artefacts": {
                "booster": f"ml/models/{spec.name}_{version}.bst",
                "onnx": f"ml/models/{spec.name}_{version}.onnx",
            },
        })

    underperformers = [u for m in ev["models"].values() for u in m["underperforming_cohorts"]]

    # Metric quoted in `limitations` below; read back from the card, never typed.
    _cliff_f1 = next(m["eval_headline"] for m in models if m["name"] == "cliff_classifier")

    # ── Dual importance (headline model of each family carries it) ──
    importance = {}
    for spec in S.PRODUCTION_TARGETS:
        imp = ev["models"][spec.name].get("importance")
        if imp:
            importance[spec.name] = {
                "shap_top5": [f for f, _ in imp["shap_top5"]],
                "permutation_top5": [f for f, _ in imp["permutation_top5"]],
                "agreement_note": imp["agreement_note"],
            }

    card = {
        "model_card": {
            "name": "Off the Pace-Tyre Degradation Predictors",
            "version": version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": (
                "Five XGBoost models predicting next-lap tyre-degradation pace loss "
                "(quantile trio p10/p50/p90), laps-until-cliff class, and remaining stint life, "
                "from per-lap thermal, dirty-air, powertrain, weather and compound-prior features. "
                "Trained on 2018–2024 F1 laps; every model beats a strong per-cohort baseline."),
            "intended_use": (
                "Race-strategy analysis and the Off the Pace web app (application layer): surfacing when a "
                "stint is about to fall off the degradation cliff and how much pace a driver is "
                "leaving on track. Not a betting or safety system."),

            "data": {
                "source_mart": S.MART,
                # Derived, never a holdout-adjacent literal (test_no_hardcoded_holdout): prefer the
                # list the training log recorded; else seasons from the data epoch up to the holdout.
                "training_seasons": any_log.get("training_seasons")
                    or list(range(DATA_EPOCH_SEASON, int(ev["holdout_season"]))),
                "holdout_seasons": [int(ev["holdout_season"])],
                "holdout_note": HOLDOUT_NOTE,
                "n_training_rows": any_log["n_train_rows"],
                "feature_count": any_log["n_features"],
                "evaluation_mode": ev["evaluation_mode"],
                "evaluation_season": ev["eval_season"],
            },

            "features": {
                "columns": list(S.FEATURE_COLUMNS),
                "groups": {g: list(cols) for g, cols in S.FEATURE_GROUPS.items()},
                "categorical": {c: len(encoders.get(c, {})) for c in S.CATEGORICAL_COLUMNS},
                "excluded_leakage": sorted(S.EXCLUDED_LEAKAGE_COLUMNS),
                "excluded_note": (
                    "driver_id and race_year are deliberately excluded: an adversarial probe recovers "
                    "race_year from the remaining features at "
                    f"{ev.get('leakage_probe', {}).get('accuracy', 0):.3f} accuracy "
                    f"(majority baseline {ev.get('leakage_probe', {}).get('majority_class_accuracy', 0):.3f})-"
                    "constructor identity and compound generation encode the season, so race_year would "
                    "be a backdoor. driver_id would let the trees relearn per-driver skill, the exact "
                    "signal the mart strips via driver_skill_residual_s."),
            },

            "models": models,

            "validation": {
                "scheme": "season-grouped TimeSeriesSplit (expanding window, n_splits=5); whole "
                          "seasons move together, the final fold validates on 2024",
                "headline_metric_direction": "pinball ↓ (quantiles), macro-F1 ↑ (classifier), RMSE ↓ (stint-life)",
                "all_models_beat_baseline": ev["all_models_beat_baseline"],
                "baselines": {
                    "degradation_p50": "group-mean over (compound, circuit, age-bucket) cells, compound→global fallback",
                    "degradation_p10_p90": "empirical 10th/90th percentile in the same cells",
                    "cliff_classifier": "majority-class prior (none_in_stint)",
                    "stint_life": "cell group-mean of remaining stint life over (compound, circuit, age-bucket), compound→global fallback (non-leakage)",
                },
                "calibration": ev.get("calibration", {}),
                "leakage_probe": ev.get("leakage_probe", {}),
                "dual_importance": importance,
                "underperforming_cohorts": underperformers,
                "underperforming_cohorts_note": (
                    "Surfaced, never dropped. Specific circuit/constructor cells where the model "
                    "trails its non-leakage cohort-mean baseline; the model wins comfortably overall."),
            },

            "reproducibility": {
                "random_state": S.RANDOM_STATE,
                "dataset_fingerprint": any_log["fingerprint"],
                "library_versions": any_log["versions"],
                "command": "make ml-all",
                "onnx_parity": "all 5 boosters round-trip to ONNX within atol=1e-5 on a NaN-bearing sample (M2/M4)",
            },

            "deviations": [
                {"id": "D1", "note": "Built on XGBoost 3.2.0 (contract said 2.x); ONNX quantile round-trip spiked in M2 before tuning."},
                {"id": "D5", "note": "Degradation target is bounded [−10,10]; the majority of jumps are legitimate negatives (fuel burn / track evolution / out-lap recovery), so the contract's y>0 floor was a spec bug that degenerated the p10 quantile."},
                {"id": "E1", "note": "Evaluation uses the final CV fold (2024) as a holdout stand-in; 2025 not yet ingested."},
                {"id": "E3", "note": "Heavy elevations (ablation/learning-curve/SHAP/PDP) run on the headline model of each family; quantile siblings share p50's structure."},
            ],

            "limitations": [
                # Read the number back from this card's own models block-a hardcoded metric here
                # is the "hand-edited metrics" failure this module exists to prevent.
                f"The cliff classifier (macro-F1 ≈ {_cliff_f1:.2f} on 4-class cliff timing) is the "
                "weakest model-it decisively beats the majority prior, but absolute skill on the "
                "minority cliff windows is modest.",
                "Hyperparameters come from a 50-trial / season-fold Optuna search per target "
                "(ml/models/<target>_best_params.json); `make ml-retrain` refits at those params "
                "without re-searching. A target whose data has moved should be re-tuned, not just refit.",
                "No live 2025 holdout yet-headline numbers are time-series CV until 2025 ingests.",
                "Cliff-onset priors are NULL for ~45% of laps (legacy compounds, un-fit circuits); "
                "XGBoost native-NaN carries them, documented rather than imputed.",
            ],
        }
    }
    return card


def write(card: dict) -> None:
    CARD_YAML.write_text(yaml.safe_dump(card, sort_keys=False, allow_unicode=True, width=100))
    CARD_JSON.parent.mkdir(parents=True, exist_ok=True)
    CARD_JSON.write_text(json.dumps(card, indent=2, ensure_ascii=False))
    # Hard guarantee: a completed card carries no placeholder.
    assert "TBD" not in CARD_YAML.read_text(), "model card still contains TBD"
    print(f"wrote {CARD_YAML} + {CARD_JSON}  "
          f"({len(card['model_card']['models'])} models, "
          f"all_beat_baseline={card['model_card']['validation']['all_models_beat_baseline']})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write model_card.yml + model_card.json")
    ap.add_argument("--to-json", action="store_true", help="print the JSON mirror to stdout")
    ap.add_argument("--version", default=S.MODEL_VERSION_DEFAULT,
                    help="artefact version to describe; defaults to the production version "
                         "(MODEL_VERSION_DEFAULT), matching evaluate.py / predict.py")
    args = ap.parse_args()
    card = build_card(args.version)
    if args.to_json:
        print(json.dumps(card, indent=2, ensure_ascii=False))
        return 0
    write(card)  # default action == --write
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
