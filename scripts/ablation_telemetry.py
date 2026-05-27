"""Pre-registered ablation for the ml-v0.2 §2 telemetry cliff features.

Decision question: do the 11 telemetry features (powertrain + telemetry_cliff groups,
landed in fct_cliff_prediction_features via int_lap_telemetry_aggregates) earn their place
in the cliff classifier, or do they only add an ONNX/parity/drift surface?

PRE-REGISTERED (stated before any model is fit no peeking):
  * Primary metric : macro-F1 of the 4-class cliff classifier on the evaluation split
                     (final TimeSeriesSplit fold = most-recent ingested season; the same
                     honest split evaluate.py uses until 2025 ingests).
  * Both arms      : identical tuned hyperparameters (cliff_classifier_best_params.json),
                     identical train/eval rows. The ONLY difference is the 11 telemetry columns.
  * Decision rule  : KEEP the telemetry features iff
                       Δmacro_f1 = macro_f1(full 41) − macro_f1(baseline 30) ≥ +0.005
                     AND no cliff-positive class (0_to_2, 3_to_5, 6_plus) loses > 0.01 recall.
                     Otherwise REVERT (drop both groups from schema.py, leave _v2 in place).

Usage:  python -m scripts.ablation_telemetry           (or  ./.venv/bin/python scripts/ablation_telemetry.py)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_recall_fscore_support

from ml.src import evaluate as E
from ml.src import features as F
from ml.src import schema as S

TARGET = "cliff_classifier"
TELEMETRY_GROUPS = ("powertrain", "telemetry_cliff")
PRIMARY_MARGIN = 0.005          # min Δmacro_f1 to keep
MAX_RECALL_DROP = 0.01          # max tolerated recall loss on any cliff-positive class
CLIFF_POSITIVE = ("0_to_2", "3_to_5", "6_plus")
OUT = Path("ml/artefacts/ablation_telemetry.json")


def _telemetry_columns() -> list[str]:
    return [c for g in TELEMETRY_GROUPS for c in S.FEATURE_GROUPS[g]]


def _per_class(y_true, y_pred) -> dict[str, dict[str, float]]:
    labels = list(range(len(S.CLIFF_CLASS_LABELS)))
    p, r, f, sup = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    return {
        S.CLIFF_CLASS_LABELS[i]: {"precision": float(p[i]), "recall": float(r[i]),
                                  "f1": float(f[i]), "support": int(sup[i])}
        for i in labels
    }


def main() -> int:
    spec = S.TARGET_BY_NAME[TARGET]
    params = json.loads(Path(f"ml/models/{TARGET}_best_params.json").read_text())
    tel_cols = _telemetry_columns()

    print("── Pre-registered telemetry ablation (ml-v0.2 §2.3) ──")
    print(f"  primary metric : macro_f1 (cliff classifier)")
    print(f"  decision rule  : KEEP iff Δmacro_f1 ≥ +{PRIMARY_MARGIN} "
          f"AND no cliff-positive class loses > {MAX_RECALL_DROP} recall")
    print(f"  telemetry cols ({len(tel_cols)}): {tel_cols}")

    bundle = F.load_features(target=TARGET)
    split = E._evaluation_split(bundle)
    print(f"  eval split     : mode={split.mode} eval_season={split.eval_season} "
          f"(train={len(split.X_tr)} rows, eval={len(split.X_ev)} rows)")

    keep_cols = [c for c in split.X_tr.columns if c not in tel_cols]
    assert len(split.X_tr.columns) - len(keep_cols) == len(tel_cols), "telemetry columns not all present"

    # Full arm (41 features)
    full = E._fit(spec, params, split.X_tr, split.y_tr)
    yhat_full = full.predict(split.X_ev)
    f1_full = f1_score(split.y_ev, yhat_full, average="macro")

    # Baseline arm (30 features telemetry dropped)
    base = E._fit(spec, params, split.X_tr[keep_cols], split.y_tr)
    yhat_base = base.predict(split.X_ev[keep_cols])
    f1_base = f1_score(split.y_ev, yhat_base, average="macro")

    delta = f1_full - f1_base
    pc_full, pc_base = _per_class(split.y_ev, yhat_full), _per_class(split.y_ev, yhat_base)

    recall_drops = {c: pc_base[c]["recall"] - pc_full[c]["recall"] for c in CLIFF_POSITIVE}
    worst_drop = max(recall_drops.values())

    keep = bool(delta >= PRIMARY_MARGIN and worst_drop <= MAX_RECALL_DROP)
    verdict = "KEEP" if keep else "REVERT"

    report = {
        "target": TARGET,
        "preregistered": {"primary_metric": "macro_f1", "margin": PRIMARY_MARGIN,
                          "max_recall_drop": MAX_RECALL_DROP, "cliff_positive": list(CLIFF_POSITIVE)},
        "eval_split": {"mode": split.mode, "eval_season": split.eval_season,
                       "n_train": int(len(split.X_tr)), "n_eval": int(len(split.X_ev))},
        "telemetry_columns": tel_cols,
        "macro_f1_full": f1_full, "macro_f1_baseline": f1_base, "delta_macro_f1": delta,
        "recall_drop_cliff_positive": recall_drops, "worst_recall_drop": worst_drop,
        "per_class_full": pc_full, "per_class_baseline": pc_base,
        "verdict": verdict,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2))

    print("\n── Result ──")
    print(f"  macro_f1  full(41)={f1_full:.4f}   baseline(30)={f1_base:.4f}   Δ={delta:+.4f}")
    print(f"  cliff-positive recall drop (baseline−full): "
          + ", ".join(f"{c}={recall_drops[c]:+.4f}" for c in CLIFF_POSITIVE))
    print(f"  worst recall drop = {worst_drop:+.4f}  (tolerance {MAX_RECALL_DROP})")
    print(f"\n  VERDICT: {verdict}  → {'telemetry features earn their place' if keep else 'telemetry features do NOT clear the bar'}")
    print(f"  wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
