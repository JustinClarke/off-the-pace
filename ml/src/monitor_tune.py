"""Monitor a running tune job (poll for trial updates).

Usage:
  # In another terminal, watch progress (defaults to the production version):
  watch -n 5 "python -m ml.src.monitor_tune"
  watch -n 5 "python -m ml.src.monitor_tune --version v2"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import optuna

from ml.src import schema as S

STUDIES_DIR = Path("ml/models/optuna_studies")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=S.MODEL_VERSION_DEFAULT,
                    help="model version whose studies to monitor (default: production version)")
    args = ap.parse_args()

    for target in S.PRODUCTION_TARGETS:
        name = target.name
        study_name = S.optuna_study_name(name, args.version)
        db_path = STUDIES_DIR / f"{study_name}.db"
        if not db_path.exists():
            print(f"[{name}] no study")
            continue

        storage = f"sqlite:///{db_path}"
        study = optuna.create_study(
            direction="maximize" if target.kind == "classification" else "minimize",
            study_name=study_name,
            storage=storage,
            load_if_exists=True,
        )

        n = len(study.trials)
        complete = len([t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE])
        pruned = len([t for t in study.trials if t.state == optuna.trial.TrialState.PRUNED])
        metric_name = "F1" if target.kind == "classification" else ("pinball" if target.kind == "quantile" else "RMSE")

        print(f"{name:30} {complete:2}/{n:2} ({pruned:2} pruned) | best {metric_name}: {study.best_value:.6f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
