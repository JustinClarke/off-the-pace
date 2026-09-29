"""W58: v15 retrain, corrected IPW survival_weight vs uniform, degradation quantile trio.

The question (user, 2026-09-29): 08o dropped IPW from the trio in v13 on evidence the W9
re-run reversed for p10/p50. Retrain v15 with IPW and compare it against uniform on the same
evaluation; use IPW for v15 only if it improves real metrics.

What is compared, and why not against published v14.
  * Published v14 was fitted on the pre-WI-01 label and on 2018-2025, so its 2025 numbers
    are (a) a different target and (b) in-sample if the shipped booster is re-scored.
    ml/README.md: a new-label headline is compared only against a v14 CONFIGURATION rebuilt
    on the new label. That configuration is the uniform arm (w=None, v14 best_params).
  * Arms, all at the v14 `*_best_params.json` (no re-tune, so the weight is the only mover):
      uniform       sample_weight=None (production since 08o; NOT w=ones, see W9 harness note)
      ipw           the corrected, season-lagged survival_weight column (post-WI-13)
      ipw_w10tail4  ipw, but W10's unreached tail cells (compound seen in a prior season, no
                    prior stint reached this lap_in_stint) at the 4.0 cap instead of 1.0
      mixed         ipw p10/p50 + uniform p90 (trio-level metrics only; heads fit separately)
  * Evaluations: the five season folds train.py and evaluate.py use (validate 2021..2025,
    expanding window), 3 seeds per fold per arm, plus the canonical-seed predictions for the
    trio-level metrics (coverage, per-quantile hit rates, crossing, CRPS).

Stages (ML_DUCKDB_PATH must point at the warehouse; ML_QUANTILE_WEIGHT is set per arm here):
    PYTHONPATH=. python w58_v15_compare.py OUT SCRATCH eval      # evaluate.run per arm
    PYTHONPATH=. python w58_v15_compare.py OUT SCRATCH arms      # fold x seed x arm refits
    PYTHONPATH=. python w58_v15_compare.py OUT SCRATCH boosters  # v15ipw / v15uni artefacts
    PYTHONPATH=. python w58_v15_compare.py OUT SCRATCH report    # tables
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import xgboost as xgb

from ml.src import crps as CR
from ml.src import evaluate as E
from ml.src import features as F
from ml.src import intervals as IV
from ml.src import schema as S
from ml.src import survival as SV
from ml.src import train as T

OUT = Path(sys.argv[1])
SCRATCH = Path(sys.argv[2])
STAGE = sys.argv[3]
OUT.mkdir(parents=True, exist_ok=True)
SCRATCH.mkdir(parents=True, exist_ok=True)

TRIO = ("degradation_regressor_p10", "degradation_regressor_p50", "degradation_regressor_p90")
ALL5 = tuple(t.name for t in S.PRODUCTION_TARGETS)
FOLD_SEEDS = (S.RANDOM_STATE, S.RANDOM_STATE + 1, S.RANDOM_STATE + 2)
ARMS = ("uniform", "ipw", "ipw_w10tail4")
VERSIONS = {"ipw": "v15ipw", "uniform": "v15uni"}
LIS_BUCKETS = [(4, 10), (11, 20), (21, 30), (31, 999)]

# F.ENCODERS_PATH is only written with persist_encoders=True (train.py); nothing here
# persists, but pin it off the tracked file anyway.
F.ENCODERS_PATH = SCRATCH / "encoders.harness.json"


def jdump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=E._json_default))


def pinball(y, q, a) -> float:
    return T.pinball_loss(y, q, a)


# ─── W10 tail flag: rebuild the mart's season-lagged survival curve ────────────────
W10_SQL = """
WITH season_compound_totals AS (
    SELECT race_year, compound, COUNT(DISTINCT stint_id) AS n_total_season
    FROM main.int_lap_residual_decomposed GROUP BY race_year, compound),
season_stints_reaching AS (
    SELECT race_year, compound, lap_in_stint, COUNT(DISTINCT stint_id) AS n_reaching_season
    FROM main.int_lap_residual_decomposed GROUP BY race_year, compound, lap_in_stint),
total_per_compound AS (
    SELECT race_year, compound, SUM(n_total_season) OVER (
        PARTITION BY compound ORDER BY race_year
        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS n_total
    FROM season_compound_totals),
stints_reaching AS (
    SELECT race_year, compound, lap_in_stint, SUM(n_reaching_season) OVER (
        PARTITION BY compound, lap_in_stint ORDER BY race_year
        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS n_reaching
    FROM season_stints_reaching)
SELECT f.lap_id, f.survival_weight, tp.n_total, sr.n_reaching
FROM main.fct_cliff_prediction_features AS f
JOIN main.int_lap_residual_decomposed AS d ON f.lap_id = d.lap_id
LEFT JOIN total_per_compound AS tp ON d.compound = tp.compound AND d.race_year = tp.race_year
LEFT JOIN stints_reaching AS sr
    ON d.compound = sr.compound AND d.lap_in_stint = sr.lap_in_stint AND d.race_year = sr.race_year
WHERE f.is_training_eligible AND f.race_year < 2026
"""


def w10_table() -> pd.DataFrame:
    con = duckdb.connect(S.DUCKDB_PATH, read_only=True)
    try:
        df = con.execute(W10_SQL).df()
    finally:
        con.close()
    p = df["n_reaching"] / df["n_total"]
    recomputed = np.where(p.notna(), np.clip(1.0 / p, 0.25, 4.0), 1.0)
    df["recomputed_weight"] = recomputed
    df["is_w10_tail"] = df["n_total"].notna() & df["n_reaching"].isna()
    return df.set_index("lap_id")


# ─── Stage: evaluate.run per arm (the v14 evaluation protocol, on the new label) ────
def stage_eval() -> None:
    # The heavy elevations (ablation / learning curve / SHAP) stay on p50 only: the cliff
    # classifier and stint life do not read the switch, so theirs would repeat v15's
    # weight-invariant fits for nothing (their .bst are checked identical in `boosters`).
    E.ELEVATION_TARGETS = frozenset({"degradation_regressor_p50"})
    for scheme, targets in (("ipw", ALL5), ("none", TRIO)):
        S.QUANTILE_SAMPLE_WEIGHT = scheme
        arm = "ipw" if scheme == "ipw" else "uniform"
        E.ARTEFACTS_DIR = SCRATCH / f"eval_{arm}"
        E.ARTEFACTS_DIR.mkdir(parents=True, exist_ok=True)
        E.EVAL_METRICS_PATH = OUT / f"eval_{arm}.json"
        t0 = time.time()
        E.run(list(targets), version=VERSIONS[arm])
        print(f"[eval {arm}] {time.time()-t0:.0f}s", flush=True)
    S.QUANTILE_SAMPLE_WEIGHT = "none"


# ─── Stage: fold x seed x arm refits ────────────────────────────────────────────────
def _fit(spec, params, X, y, w, seed):
    m = T._make_model(spec, {**params, "seed": int(seed)})
    m.set_params(random_state=int(seed))
    m.fit(X, y, sample_weight=None if w is None else np.asarray(w, dtype=np.float32))
    return m


def stage_arms() -> None:
    w10 = w10_table()
    res: dict = {"fold_seeds": list(FOLD_SEEDS), "arms": list(ARMS), "heads": {},
                 "w10": {}}
    preds: dict = {}   # (arm, fold) -> {head: pred}, canonical seed
    ys: dict = {}      # fold -> (y, lap_in_stint, compound, weight)
    for head in TRIO:
        spec = S.TARGET_BY_NAME[head]
        params = E._params_for(head, "v15")
        b = F.load_features(target=head)
        X, y = b.X_train, b.y_train.to_numpy()
        seasons = b.groups_train.to_numpy()
        meta = b.meta_train
        w_ipw = meta["survival_weight"].to_numpy(dtype=np.float32)
        wt = w10.reindex(meta["lap_id"])
        if wt["survival_weight"].isna().any():
            raise SystemExit("W10 table does not cover every training row")
        mism = float(np.max(np.abs(wt["recomputed_weight"].to_numpy() - w_ipw)))
        tail = wt["is_w10_tail"].to_numpy(dtype=bool)
        w_w10 = np.where(tail, 4.0, w_ipw).astype(np.float32)
        res["w10"][head] = {
            "recomputed_vs_mart_max_abs_diff": mism,
            "n_rows": int(len(y)), "n_tail_rows": int(tail.sum()),
            "tail_rows_by_season": {int(k): int(v) for k, v in
                                    pd.Series(tail).groupby(seasons).sum().items()},
            "tail_rows_at_1.0_in_mart": int((w_ipw[tail] == 1.0).sum()),
        }
        if mism > 1e-5:
            raise SystemExit(f"recomputed survival_weight does not match the mart ({mism})")
        weights = {"uniform": None, "ipw": w_ipw, "ipw_w10tail4": w_w10}
        hr: dict = {"n_rows": int(len(y)),
                    "w_ipw": {"mean": float(w_ipw.mean()), "sd": float(w_ipw.std()),
                              "share_at_1": float((w_ipw == 1).mean()),
                              "share_at_4": float((w_ipw == 4).mean())},
                    "folds": []}
        for k, (tr, va) in enumerate(T._season_folds(seasons, b.training_seasons, 5)):
            vs = int(seasons[va][0])
            fold = {"fold": k, "val_season": vs, "n_train": int(tr.size), "n_val": int(va.size),
                    "arms": {}}
            for arm in ARMS:
                w = weights[arm]
                scores = []
                for s in FOLD_SEEDS:
                    t0 = time.time()
                    m = _fit(spec, params, X.iloc[tr], y[tr], None if w is None else w[tr], s)
                    p = m.predict(X.iloc[va])
                    scores.append(pinball(y[va], p, spec.quantile_alpha))
                    if s == S.RANDOM_STATE:
                        preds.setdefault((arm, k), {})[head] = p
                fold["arms"][arm] = {"pinball_by_seed": scores,
                                     "pinball_mean": float(np.mean(scores)),
                                     "seed_sd": float(np.std(scores, ddof=1))}
                print(f"[{head}] fold {k} ({vs}) {arm:13s} "
                      f"{np.mean(scores):.5f} sd={np.std(scores, ddof=1):.5f}", flush=True)
            hr["folds"].append(fold)
            lap_va = meta["lap_id"].to_numpy()[va]
            if k in ys:  # the trio shares one target and one feature mask: same rows, same y
                if not (np.array_equal(ys[k]["lap_ids"], lap_va) and np.array_equal(ys[k]["y"], y[va])):
                    raise SystemExit(f"{head} fold {k}: rows differ from the other heads")
            else:
                ys[k] = {"y": y[va], "season": vs, "lap_ids": lap_va}
        # Paired over folds: seed-averaged, canonical seed, IPW (and W10) vs uniform.
        for arm in ("ipw", "ipw_w10tail4"):
            d_mean = [f["arms"]["uniform"]["pinball_mean"] - f["arms"][arm]["pinball_mean"]
                      for f in hr["folds"]]
            d_can = [f["arms"]["uniform"]["pinball_by_seed"][0] - f["arms"][arm]["pinball_by_seed"][0]
                     for f in hr["folds"]]
            d_rel = [f["arms"]["uniform"]["pinball_mean"] and
                     (f["arms"]["uniform"]["pinball_mean"] - f["arms"][arm]["pinball_mean"])
                     / f["arms"]["uniform"]["pinball_mean"] for f in hr["folds"]]
            hr[f"{arm}_vs_uniform"] = {
                "positive_means": f"{arm} has the lower pinball",
                "seed_averaged": IV.paired_t(d_mean),
                "canonical_seed": IV.paired_t(d_can),
                "relative_by_fold": d_rel,
                "mean_relative": float(np.mean(d_rel)),
                "per_fold_seed_floor_2sqrt2sd": [
                    2 * np.sqrt(2) * max(f["arms"]["uniform"]["seed_sd"], f["arms"][arm]["seed_sd"])
                    for f in hr["folds"]],
            }
        d = [f["arms"]["ipw"]["pinball_mean"] - f["arms"]["ipw_w10tail4"]["pinball_mean"]
             for f in hr["folds"]]
        hr["w10tail4_vs_ipw"] = {"positive_means": "tail at 4.0 has the lower pinball",
                                 "seed_averaged": IV.paired_t(d)}
        res["heads"][head] = hr
        jdump(OUT / "arms.json", res)

    import pickle
    (SCRATCH / "arms_preds.pkl").write_bytes(pickle.dumps({"preds": preds, "ys": ys}))
    post_arms(res, preds, ys)


def post_arms(res: dict | None = None, preds: dict | None = None, ys: dict | None = None) -> None:
    """Trio-level metrics and the 2025 breakdown from the canonical-seed predictions.
    Re-runnable on its own from arms_preds.pkl (stage `post`)."""
    import pickle
    if res is None:
        res = json.loads((OUT / "arms.json").read_text())
        blob = pickle.loads((SCRATCH / "arms_preds.pkl").read_bytes())
        preds, ys = blob["preds"], blob["ys"]
    # Trio-level, per fold, canonical seed.
    trio_rows = []
    arms_trio = {"uniform": ("uniform", "uniform", "uniform"),
                 "ipw": ("ipw", "ipw", "ipw"),
                 "ipw_w10tail4": ("ipw_w10tail4",) * 3,
                 "mixed_ipw_p10p50_uniform_p90": ("ipw", "ipw", "uniform")}
    for k, fy in ys.items():
        y = fy["y"]
        for name, (a10, a50, a90) in arms_trio.items():
            p10 = preds[(a10, k)]["degradation_regressor_p10"]
            p50 = preds[(a50, k)]["degradation_regressor_p50"]
            p90 = preds[(a90, k)]["degradation_regressor_p90"]
            lo, hi = np.minimum(p10, p90), np.maximum(p10, p90)
            cr = CR.crps_report(y, {0.10: p10, 0.50: p50, 0.90: p90})
            trio_rows.append({
                "fold": k, "val_season": fy["season"], "arm": name, "n": int(len(y)),
                "pinball_p10": pinball(y, p10, 0.10), "pinball_p50": pinball(y, p50, 0.50),
                "pinball_p90": pinball(y, p90, 0.90),
                "mae_p50": float(np.mean(np.abs(y - p50))),
                "hit_below_p10": float(np.mean(y < p10)),
                "hit_below_p50": float(np.mean(y < p50)),
                "hit_below_p90": float(np.mean(y < p90)),
                "coverage_p10_p90": float(np.mean((y >= lo) & (y <= hi))),
                "mean_width_p10_p90": float(np.mean(p90 - p10)),
                "crossing_p10_gt_p50": float(np.mean(p10 > p50)),
                "crossing_p50_gt_p90": float(np.mean(p50 > p90)),
                "crossing_p10_gt_p90": float(np.mean(p10 > p90)),
                "crps": cr["crps"], "crps_mcb": cr["decomposition"]["mcb"],
                "crps_dsc": cr["decomposition"]["dsc"], "crps_unc": cr["decomposition"]["unc"],
            })
    res["trio_by_fold"] = trio_rows

    # 2025 fold breakdown by lap_in_stint bucket and compound (canonical seed).
    k_last = max(ys)
    lap_ids = ys[k_last]["lap_ids"]
    dims = E.load_cohort_dims().loc[lap_ids]  # already indexed by lap_id
    y = ys[k_last]["y"]
    lis = dims["lap_in_stint"].to_numpy()
    comp = dims["compound"].astype(str).to_numpy()
    bd = []
    for head in TRIO:
        a = S.TARGET_BY_NAME[head].quantile_alpha
        for lo_, hi_ in LIS_BUCKETS:
            m = (lis >= lo_) & (lis <= hi_)
            row = {"head": head, "cohort": f"lap_in_stint {lo_}-{hi_ if hi_ < 999 else '+'}",
                   "n": int(m.sum())}
            for arm in ARMS:
                row[arm] = pinball(y[m], preds[(arm, k_last)][head][m], a)
            bd.append(row)
        for c in sorted(set(comp)):
            m = comp == c
            if m.sum() < 200:
                continue
            row = {"head": head, "cohort": f"compound {c}", "n": int(m.sum())}
            for arm in ARMS:
                row[arm] = pinball(y[m], preds[(arm, k_last)][head][m], a)
            bd.append(row)
    res["breakdown_2025"] = bd
    jdump(OUT / "arms.json", res)
    print("wrote", OUT / "arms.json")


# ─── Stage: the v15 artefacts themselves ─────────────────────────────────────────────
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _time(fn, reps: int) -> dict:
    fn()  # warm
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t0)
    return {"median_ms": float(np.median(ts) * 1e3), "p90_ms": float(np.percentile(ts, 90) * 1e3),
            "reps": reps}


def stage_boosters() -> None:
    import onnxruntime as ort
    from ml.src import export_onnx as X

    out: dict = {"models": {}}
    samples: dict = {}
    for target in ALL5:
        spec = S.TARGET_BY_NAME[target]
        b = F.load_features(target=target)
        X_tr, y_tr = b.X_train, b.y_train.to_numpy()
        seasons = b.groups_train.to_numpy()
        X_25 = X_tr[seasons == 2025]
        key = tuple(S.feature_columns_for(target))
        if key not in samples:
            samples[key] = X.nan_bearing_sample(target=target)
        for arm, version in VERSIONS.items():
            bst = T.MODELS_DIR / f"{S.artefact_name(spec, version)}.bst"
            logs = sorted(T.LOGS_DIR.glob(f"{target}_{version}_*.json"))
            log = json.loads(logs[-1].read_text())
            booster = SV.load_booster(bst) if spec.kind == "survival" else xgb.Booster(model_file=str(bst))
            df = booster.trees_to_dataframe()
            r: dict = {
                "version": version, "bst_path": str(bst), "bst_bytes": bst.stat().st_size,
                "bst_sha256": _sha(bst),
                "sample_weight_scheme": log.get("sample_weight_scheme"),
                "headline_metric": log["headline_metric"], "headline_cv": log["headline_cv"],
                "fold_metrics": log["fold_metrics"], "fit_seconds": log["fit_seconds"],
                "n_train_rows": log["n_train_rows"], "fingerprint": log["fingerprint"],
                "n_trees": int(df["Tree"].nunique()), "n_nodes": int(len(df)),
                "n_leaves": int((df["Feature"] == "Leaf").sum()),
            }
            gain = booster.get_score(importance_type="total_gain")
            tot = sum(gain.values()) or 1.0
            r["gain_share_top10"] = sorted(((f, v / tot) for f, v in gain.items()),
                                           key=lambda t: t[1], reverse=True)[:10]
            # In-sample training loss on the full training set (unweighted).
            if spec.kind == "quantile":
                m = xgb.XGBRegressor()
                m.load_model(str(bst))
                p = m.predict(X_tr)
                r["train_pinball_unweighted"] = pinball(y_tr, p, spec.quantile_alpha)
                w = b.meta_train["survival_weight"].to_numpy(dtype=np.float64)
                e = y_tr - p
                a = spec.quantile_alpha
                r["train_pinball_ipw_weighted"] = float(
                    np.sum(w * np.maximum(a * e, (a - 1) * e)) / w.sum())
                pred_batch = lambda: m.predict(X_25)  # noqa: E731
                row1 = X_25.iloc[[0]]
                pred_one = lambda: m.predict(row1)  # noqa: E731
            elif spec.kind == "classification":
                m = xgb.XGBClassifier()
                m.load_model(str(bst))
                from sklearn.metrics import accuracy_score, f1_score
                p = m.predict(X_tr)
                r["train_macro_f1"] = float(f1_score(y_tr, p, average="macro"))
                r["train_accuracy"] = float(accuracy_score(y_tr, p))
                pred_batch = lambda: m.predict_proba(X_25)  # noqa: E731
                row1 = X_25.iloc[[0]]
                pred_one = lambda: m.predict_proba(row1)  # noqa: E731
            else:
                dm25 = xgb.DMatrix(X_25, missing=np.nan)
                dm1 = xgb.DMatrix(X_25.iloc[[0]], missing=np.nan)
                pred_batch = lambda: booster.predict(dm25)  # noqa: E731
                pred_one = lambda: booster.predict(dm1)  # noqa: E731
            r["xgb_batch_2025"] = {"rows": int(len(X_25)), **_time(pred_batch, 7)}
            r["xgb_single_row"] = _time(pred_one, 200)
            # ONNX: convert next to the .bst (gitignored), parity-gate, time it.
            onnx_path = X.convert(target, version)
            par = X.parity(target, version, samples[key])
            sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
            a25 = X_25.to_numpy(dtype=np.float32)
            a1 = a25[:1]
            r["onnx_bytes"] = onnx_path.stat().st_size
            r["onnx_parity"] = par
            r["onnx_batch_2025"] = {"rows": int(len(a25)),
                                    **_time(lambda: sess.run(None, {"input": a25}), 7)}
            r["onnx_single_row"] = _time(lambda: sess.run(None, {"input": a1}), 500)
            out["models"].setdefault(target, {})[arm] = r
            print(f"[{target}] {version} bst={r['bst_bytes']/1e6:.2f}MB onnx={r['onnx_bytes']/1e6:.2f}MB "
                  f"trees={r['n_trees']} leaves={r['n_leaves']} parity={par['pass']} "
                  f"onnx1={r['onnx_single_row']['median_ms']:.3f}ms "
                  f"onnx_batch={r['onnx_batch_2025']['median_ms']:.1f}ms", flush=True)
        both = out["models"][target]
        both["bst_identical_across_arms"] = both["ipw"]["bst_sha256"] == both["uniform"]["bst_sha256"]
        jdump(OUT / "boosters.json", out)
    print("wrote", OUT / "boosters.json")


# ─── Stage: tables ───────────────────────────────────────────────────────────────────
def stage_report() -> None:
    ev = {a: json.loads((OUT / f"eval_{a}.json").read_text()) for a in ("uniform", "ipw")}
    arms = json.loads((OUT / "arms.json").read_text())
    boo = json.loads((OUT / "boosters.json").read_text())
    pub = json.loads((SCRATCH / "evaluation_metrics.v14.backup.json").read_text())
    o8 = json.loads(Path("_roadmap/_improvements/implementations/08o/08o_gate_arms.json").read_text())
    sp = json.loads(Path("_roadmap/_fixes/_evidence/w9-2026-09-29/supp_production_vs_ipw.json").read_text())
    lines: list[str] = []
    summ: dict = {"heads": {}, "trio": {}, "invariant": {}, "artefacts": {}}

    lines.append("## A. 2025 (v14 evaluation protocol: refit 2018-2024, score 2025, canonical seed)")
    lines.append("| Head | published v14 (old label, not comparable) | uniform = v14 config rebuilt | IPW (v15ipw) "
                 "| IPW - uniform | % | seed floor (n=10) | x floor | seeds IPW better | E |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for h in TRIO:
        u, i = ev["uniform"]["models"][h], ev["ipw"]["models"][h]
        d = u["headline"] - i["headline"]  # positive = IPW lower pinball
        s = sp["targets"][h]
        fl = s["floor_quoted"]
        e = s["e_value_B_beats_production"]["E"]
        row = {"published_v14_old_label": pub["models"][h]["headline"],
               "uniform": u["headline"], "ipw": i["headline"],
               "baseline": u["baseline_headline"],
               "ipw_minus_uniform_improvement": d, "pct": d / u["headline"],
               "seed_floor": fl, "floor_ratio": d / fl,
               "paired_seed_mean_delta": s["mean_delta_B_vs_production"],
               "seeds_ipw_better": s["seeds_B_better"], "e_value_t2": e,
               "ipw_vs_08o_armB": i["headline"] - o8["targets"][h]["arm_B_ipw"]["headline"],
               "uniform_vs_08o_prod": u["headline"] - o8["targets"][h]["gate1_headline_production"],
               "fold_paired_vs_baseline": {a: ev[a]["models"][h]["interval"]["fold_paired"].get("p_value")
                                           for a in ev}}
        summ["heads"][h] = {"2025": row}
        lines.append(f"| {h[-3:]} | {row['published_v14_old_label']:.4f} | {u['headline']:.4f} | "
                     f"{i['headline']:.4f} | {d:+.4f} | {100*d/u['headline']:+.2f}% | {fl:.4f} | "
                     f"{d/fl:+.2f}x | {s['seeds_B_better']}/10 | {e:.3g} |")

    lines.append("\n## B. Five season folds (validate 2021..2025), 3 seeds per fold, seed-averaged")
    lines.append("| Head | uniform mean | IPW mean | mean improvement | mean % | folds IPW won | paired t p | 95% CI |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for h in TRIO:
        hr = arms["heads"][h]
        um = np.mean([f["arms"]["uniform"]["pinball_mean"] for f in hr["folds"]])
        im = np.mean([f["arms"]["ipw"]["pinball_mean"] for f in hr["folds"]])
        pt = hr["ipw_vs_uniform"]["seed_averaged"]
        summ["heads"][h]["folds"] = {
            "uniform_mean": float(um), "ipw_mean": float(im),
            "by_fold": [{"val_season": f["val_season"],
                         "uniform": f["arms"]["uniform"]["pinball_mean"],
                         "ipw": f["arms"]["ipw"]["pinball_mean"],
                         "w10tail4": f["arms"]["ipw_w10tail4"]["pinball_mean"],
                         "seed_sd_uniform": f["arms"]["uniform"]["seed_sd"],
                         "seed_sd_ipw": f["arms"]["ipw"]["seed_sd"]} for f in hr["folds"]],
            "paired_t": pt, "mean_relative": hr["ipw_vs_uniform"]["mean_relative"],
            "w10tail4_vs_ipw": hr["w10tail4_vs_ipw"]["seed_averaged"]}
        lines.append(f"| {h[-3:]} | {um:.4f} | {im:.4f} | {pt['mean_delta']:+.4f} | "
                     f"{100*hr['ipw_vs_uniform']['mean_relative']:+.2f}% | {pt['folds_won']}/{pt['n_folds']} | "
                     f"{pt['p_value']:.3f} | [{pt['ci_low']:+.4f}, {pt['ci_high']:+.4f}] |")
        lines.append("|  | by fold (uniform -> IPW): " + "; ".join(
            f"{f['val_season']} {f['arms']['uniform']['pinball_mean']:.4f}->{f['arms']['ipw']['pinball_mean']:.4f}"
            for f in hr["folds"]) + " | | | | | | |")

    lines.append("\n## C. Trio as a distribution (canonical seed)")
    tb = pd.DataFrame(arms["trio_by_fold"])
    cols = ["coverage_p10_p90", "hit_below_p10", "hit_below_p50", "hit_below_p90",
            "mean_width_p10_p90", "crossing_p10_gt_p50", "crossing_p50_gt_p90", "crps", "mae_p50"]
    for label, sub in (("2025", tb[tb["val_season"] == 2025]), ("mean of 5 folds", tb)):
        g = sub.groupby("arm")[cols].mean()
        summ["trio"][label] = g.to_dict(orient="index")
        lines.append(f"\n{label} (nominal: coverage 0.80; hits 0.10 / 0.50 / 0.90)")
        lines.append("| arm | " + " | ".join(cols) + " |")
        lines.append("|---" * (len(cols) + 1) + "|")
        for arm, r in g.iterrows():
            lines.append(f"| {arm} | " + " | ".join(f"{v:.4f}" for v in r.to_numpy()) + " |")

    lines.append("\n## D. W10 (tail cells at 4.0 instead of 1.0), seed-averaged over 5 folds")
    for h in TRIO:
        w = arms["w10"][h]
        pt = arms["heads"][h]["w10tail4_vs_ipw"]["seed_averaged"]
        lines.append(f"- {h[-3:]}: {w['n_tail_rows']} tail rows ({w['tail_rows_by_season']}); "
                     f"4.0 vs 1.0 mean improvement {pt['mean_delta']:+.4f}, folds won {pt['folds_won']}/5, "
                     f"p={pt['p_value']:.3f}; recomputed weight max |diff| vs mart {w['recomputed_vs_mart_max_abs_diff']:.1e}")

    lines.append("\n## E. 2025 breakdown by lap_in_stint and compound (pinball, canonical seed)")
    lines.append("| head | cohort | n | uniform | IPW | W10 tail 4.0 | IPW - uniform |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in arms["breakdown_2025"]:
        lines.append(f"| {r['head'][-3:]} | {r['cohort']} | {r['n']} | {r['uniform']:.4f} | {r['ipw']:.4f} | "
                     f"{r['ipw_w10tail4']:.4f} | {r['uniform']-r['ipw']:+.4f} |")

    lines.append("\n## F. Artefacts (final boosters, fit on 2018-2025)")
    lines.append("| model | arm | CV headline (train.py, 5 folds) | train loss (unweighted) | .bst MB | .onnx MB | trees | leaves "
                 "| fit s | ONNX 1 row ms | ONNX 2025 batch ms | xgb batch ms | parity |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for t, both in boo["models"].items():
        for arm in ("uniform", "ipw"):
            r = both[arm]
            tl = r.get("train_pinball_unweighted", r.get("train_macro_f1"))
            lines.append(f"| {t} | {arm} | {r['headline_metric']} {r['headline_cv']:.4f} | "
                         f"{'' if tl is None else f'{tl:.4f}'} | {r['bst_bytes']/1e6:.2f} | "
                         f"{r['onnx_bytes']/1e6:.2f} | {r['n_trees']} | {r['n_leaves']} | {r['fit_seconds']} | "
                         f"{r['onnx_single_row']['median_ms']:.3f} | {r['onnx_batch_2025']['median_ms']:.1f} | "
                         f"{r['xgb_batch_2025']['median_ms']:.1f} | {r['onnx_parity']['pass']} |")
        summ["artefacts"][t] = {a: {k: both[a][k] for k in (
            "version", "bst_bytes", "onnx_bytes", "n_trees", "n_leaves", "fit_seconds", "headline_cv",
            "sample_weight_scheme")} for a in ("uniform", "ipw")}
        summ["artefacts"][t]["bst_identical_across_arms"] = both["bst_identical_across_arms"]

    lines.append("\n## G. Weight-invariant models (same .bst under both arms)")
    for t in ("cliff_classifier", "stint_life_regressor"):
        m = ev["ipw"]["models"][t]
        same = boo["models"][t]["bst_identical_across_arms"]
        summ["invariant"][t] = {"bst_identical_across_arms": same, "headline": m["headline"],
                                "baseline": m["baseline_headline"], "metric": m["headline_metric"],
                                "published_v14_old_label": pub["models"][t]["headline"]}
        lines.append(f"- {t}: bst identical across arms = {same}; 2025 {m['headline_metric']} "
                     f"{m['headline']:.4f} (baseline {m['baseline_headline']:.4f}; published v14 on old label "
                     f"{pub['models'][t]['headline']:.4f})")

    lines.append("\n## H. p50 top-5 gain share")
    for arm in ("uniform", "ipw"):
        top = boo["models"]["degradation_regressor_p50"][arm]["gain_share_top10"][:5]
        lines.append(f"- {arm}: " + ", ".join(f"{f} {v:.3f}" for f, v in top))
    for arm in ("uniform", "ipw"):
        imp = ev[arm]["models"]["degradation_regressor_p50"].get("importance", {})
        if imp:
            lines.append(f"- {arm} SHAP top-5 (eval refit): " + ", ".join(f for f, _ in imp["shap_top5"]))

    text = "\n".join(lines)
    (OUT / "w58_v15_report.log").write_text(text + "\n")
    jdump(OUT / "w58_v15_summary.json", summ)
    print(text)


if __name__ == "__main__":
    {"eval": stage_eval, "arms": stage_arms, "post": post_arms, "boosters": stage_boosters,
     "report": stage_report}[STAGE]()
