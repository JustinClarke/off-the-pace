"""F9 measurement arm: what does keeping `mistake` rows in training cost or buy?

Status quo hard-excludes anomaly_class == 'mistake' from training (is_training_eligible).
`mistake` and `clean_cliff` differ only by cliff_onset_passed (the in-race seed), so the
exclusion selects training rows on a quantity adjacent to the label. This script refits
every production target on the production fit path with three training sets and the SAME
eval rows:

  A   shipped:   eligible rows, production weights (w=None for the trio / stint life).
  A1  control:   eligible rows, explicit weight 1.0. Separates "explicit ones" from "None"
                 (XGBoost quantile fits sample_weight=ones differently from None).
  B   mistake rows added to training at weight 0.5 (what int_lap_anomaly_flags.training_weight_f9 encodes).
  C   mistake rows added at weight 1.0 (no exclusion at all; the ceiling of the idea).

Eval rows are the baseline-eligible rows of the final CV fold in every arm, so scores are
comparable. Reseed noise (the floor) is the sd of A1 over the same seeds. Reports paired
deltas against A1 (positive = improvement), quoted against that floor.

Runs against a scratch COPY of the warehouse; dev.duckdb is not written.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

import duckdb
import numpy as np

from ml.src import evaluate as E
from ml.src import features as F
from ml.src import schema as S
from ml.src import train as T

TARGETS = ("degradation_regressor_p10", "degradation_regressor_p50", "degradation_regressor_p90",
           "cliff_classifier", "stint_life_regressor")


def build_scratch_warehouse(src: Path, dst: Path) -> set[str]:
    """Copy the warehouse and flip `mistake` rows eligible in the copy only.

    Returns the lap_ids of the added rows. A row is added iff it is a `mistake` that the
    other eligibility clauses (age_in_stint > 3, not the lap after a restart) would admit.
    `mistake` rows are never eligible in the shipped warehouse, so the selection does not
    depend on the flag and the function is safe to re-run against an existing scratch copy.
    """
    if not dst.exists():
        shutil.copyfile(src, dst)
    con = duckdb.connect(str(dst))
    try:
        ids = con.execute(f"""
            SELECT m.lap_id
            FROM {S.MART} m
            LEFT JOIN int_event_corrections c USING (lap_id)
            WHERE m.anomaly_class = 'mistake'
              AND m.age_in_stint > 3
              AND NOT COALESCE(c.is_lap_after_restart, FALSE)
        """).df()["lap_id"].tolist()
        con.execute(f"""
            UPDATE {S.MART} SET is_training_eligible = TRUE
            WHERE lap_id IN (SELECT UNNEST(?))""", [ids])
    finally:
        con.close()
    return set(ids)


def fit_seeded(spec, params, X, y, w, cens, seed):
    model = T._make_model(spec, {**params, "seed": int(seed)})
    if hasattr(model, "set_params"):
        try:
            model.set_params(random_state=int(seed))
        except Exception:  # noqa: BLE001 - AFTBooster takes its seed through params
            pass
    if spec.kind == "survival":
        model.fit(X, y, sample_weight=w, is_censored=np.asarray(cens, dtype=bool))
    else:
        model.fit(X, y, sample_weight=w)
    return model


def run_target(target, added, ship_path, scratch_path, seeds):
    spec = S.TARGET_BY_NAME[target]
    params = E._params_for(target, S.MODEL_VERSION_DEFAULT)
    hib = E._higher_is_better(spec)

    ship = F.load_features(duckdb_path=str(ship_path), target=target)
    scr = F.load_features(duckdb_path=str(scratch_path), target=target)
    s_ship, s_scr = E._evaluation_split(ship), E._evaluation_split(scr)

    is_added_tr = np.array([lid in added for lid in s_scr.lap_ids_tr])
    is_added_ev = np.array([lid in added for lid in s_scr.lap_ids_ev])
    keep_ev = ~is_added_ev
    base_tr = ~is_added_tr
    # Parity: the scratch split minus added rows must be the shipped split.
    assert int(base_tr.sum()) == len(s_ship.y_tr), (target, int(base_tr.sum()), len(s_ship.y_tr))
    assert int(keep_ev.sum()) == len(s_ship.y_ev), (target, int(keep_ev.sum()), len(s_ship.y_ev))

    X_ev = s_scr.X_ev[keep_ev].reset_index(drop=True)
    y_ev = s_scr.y_ev[keep_ev]
    cens_ev = None if s_scr.cens_ev is None else s_scr.cens_ev[keep_ev]
    X_tr, y_tr, cens_tr = s_scr.X_tr, s_scr.y_tr, s_scr.cens_tr

    def anomaly_w(w_added):
        w = np.ones(len(y_tr), dtype=np.float32)
        w[is_added_tr] = w_added
        return w

    def row_w(w_added, rows):
        """Training weight for a row subset: balanced class weights (classifier) times the arm weight."""
        base = anomaly_w(w_added)[rows]
        if spec.kind == "classification":
            return (T._sample_weight(spec, y_tr[rows]) * base).astype(np.float32)
        return base

    arms = {
        "A":  dict(rows=base_tr, w=None),
        "A1": dict(rows=base_tr, w=row_w(1.0, base_tr)),
        "B":  dict(rows=np.ones(len(y_tr), bool), w=row_w(0.5, np.ones(len(y_tr), bool))),
        "C":  dict(rows=np.ones(len(y_tr), bool), w=row_w(1.0, np.ones(len(y_tr), bool))),
    }
    scores = {k: [] for k in arms}
    t0 = time.time()
    for seed in seeds:
        for name, a in arms.items():
            rows = a["rows"]
            X, y = X_tr[rows].reset_index(drop=True), y_tr[rows]
            c = None if cens_tr is None else cens_tr[rows]
            w = a["w"]
            if name == "A":
                w = T._sample_weight(spec, y) if spec.kind == "classification" else None
            model = fit_seeded(spec, params, X, y, w, c, seed)
            scale = getattr(model, "scale", None) if spec.kind == "survival" else None
            scores[name].append(float(E._score(spec, y_ev, E._predict_index(spec, model, X_ev),
                                               cens=cens_ev, scale=scale)))
        print(f"  [{target}] seed {seed} done ({time.time() - t0:.0f}s)", flush=True)

    sgn = 1.0 if hib else -1.0
    a1 = np.array(scores["A1"])
    out = {"target": target, "metric": E._headline_metric_name(spec), "higher_is_better": hib,
           "n_train_base": int(base_tr.sum()), "n_added": int(is_added_tr.sum()),
           "n_eval": int(len(y_ev)), "eval_season": s_scr.eval_season, "seeds": list(seeds),
           "scores": scores, "floor_sd_A1": float(a1.std(ddof=1)) if len(a1) > 1 else None}
    for arm in ("A", "B", "C"):
        d = sgn * (np.array(scores[arm]) - a1)   # positive = improvement over control
        out[f"delta_{arm}_vs_A1"] = {"mean": float(d.mean()),
                                     "sd": float(d.std(ddof=1)) if len(d) > 1 else None,
                                     "per_seed": d.tolist()}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--targets", nargs="*", default=list(TARGETS))
    ap.add_argument("--scratch", required=True, help="path for the scratch warehouse copy")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ship = Path(S.DUCKDB_PATH)
    scratch = Path(args.scratch)
    added = build_scratch_warehouse(ship, scratch)
    print(f"added {len(added):,} mistake rows to the scratch warehouse", flush=True)
    seeds = [S.RANDOM_STATE + i for i in range(args.seeds)]
    results = [run_target(t, added, ship, scratch, seeds) for t in args.targets]
    Path(args.out).write_text(json.dumps(results, indent=2))
    print("\nSUMMARY (delta vs A1, positive = improvement; floor = sd of A1 over seeds)")
    for r in results:
        f = r["floor_sd_A1"]
        print(f"{r['target']:32s} {r['metric']:>14s} n_add={r['n_added']:>5d} floor={f if f is None else round(f, 5)}")
        for arm in ("A", "B", "C"):
            d = r[f"delta_{arm}_vs_A1"]
            print(f"    {arm:>2s} - A1: {d['mean']:+.5f}  ({d['mean']/f:+.2f}x floor)" if f else f"    {arm}: {d['mean']:+.5f}")


if __name__ == "__main__":
    main()
