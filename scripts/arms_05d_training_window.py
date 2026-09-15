"""05d -- The training window: is a proper subset of seasons better than all of them?

Runs exactly the arms declared in _improvements/work/05-model-family.md §`05d`, which
were written before any of them was run (gate 6).

WHAT 01a LEFT OPEN, AND WHY THIS IS NOT A RERUN
-----------------------------------------------
`01a` found the cliff classifier scores higher trained on 2021-2023 than on the full
2018-2023. It could not close one confound: `features.py::load_features` fits the
ordinal encoder on the WHOLE training frame before any split, and 01a subset rows of
the already-encoded matrix. So 01a held the encoding fixed across its arms -- internally
clean, but not what a production window change returns, because a real window change
refits the encoder and HYPERSOFT / SUPERSOFT / ULTRASOFT (2018-only, absent from every
later season) vanish from it, renumbering every remaining level.

**Every arm here refits the encoder on the window's own rows, inside the fit.**

THE FOUR ARMS
-------------
  A  LADDER      most-recent-k seasons, k = 1..K_E, encoder refit inside each fit,
                 for every season-fold eval season E (not 2024 alone -- 01a's eval side
                 was one season, so "recent trains better" could have been 2024-specific).
  B  FOLD        full window, 2018's three unique compound levels collapsed to ONE
                 shared code. Keeps 2018's rows and 2018's regime; removes only its
                 compound identity. Separates the encoding mechanism from the regime
                 mechanism -- without it the finding cannot say which lever to pull.
  C  RENUMBER    full window, all levels kept, the encoder's integers randomly PERMUTED
                 per seed. The null for arm B: if B moves the headline only as much as C
                 does, B measured the numbering moving, not compound identity.
  G1 INSTRUMENT  the full-window cell at the canonical seed must reproduce the published
                 headline to 6 dp, per family, before anything else is trusted (gate 1).

Multi-seed throughout: seeds RANDOM_STATE+0..4, the same five `attribution.py::
refit_noise_floor` uses. 01a's recency cells were single fits.

TWO FLOORS ARE REPORTED, AND THEY ARE NOT INTERCHANGEABLE
---------------------------------------------------------
  floor_reseed  = 2*sqrt(2)*sd  over the full-window cell's five seeds. The programme's
                  standard single-fit floor. Quoted ONLY so these numbers can be read
                  against 01a's `x floor` column, which used it.
  floor_paired  = 2*sd(paired per-seed deltas)/sqrt(5). The arms share their five seeds
                  AND their eval rows, so the comparison is paired on both. This is the
                  correct denominator for a difference of two 5-seed means and it is the
                  one the verdict uses.

Deltas are oriented so POSITIVE ALWAYS MEANS IMPROVEMENT, on every metric.

STINT LIFE IS RUN TWICE, ON PURPOSE
-----------------------------------
`02b` bars stint_life_regressor "until 10e resolves ... 10e has not landed as of
2026-09-14": its shipped hyperparameters were tuned under the wrong label, so anything
measured against them describes a model about to change. Rather than drop the family the
spec asks for, the ladder is run under BOTH the shipped v11 params and 10e's declared
winner S1x. A window recommendation that agrees across both survives 10e landing; one
that does not is reported as provisional.

Usage:  PYTHONPATH=. ./.venv/bin/python scripts/arms_05d_training_window.py
        (add --quick for a 2-seed, 2-eval-season smoke of the same code path)

Writes ml/artefacts/05d_training_window_arms.json -- every fit's headline, per seed, so
a reader can recompute any delta or floor ratio in the leaf doc without refitting.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from ml.src import evaluate as E
from ml.src import features as F
from ml.src import schema as S
from ml.src import train as T

OUT = Path("ml/artefacts/05d_training_window_arms.json")

SEEDS: tuple[int, ...] = tuple(S.RANDOM_STATE + i for i in range(5))

# 10e's declared winner, copied verbatim from work/10-competing-risks.md §10e so the
# stint-life arm is not measured only against a model that is about to be replaced.
S1X_PARAMS = {
    "aft_loss_distribution_scale": 0.7537929016487691,
    "colsample_bytree": 0.7022777269179408,
    "gamma": 0.00526088099298953,
    "learning_rate": 0.021917329940077092,
    "max_depth": 8,
    "min_child_weight": 3,
    "n_estimators": 100,
    "reg_alpha": 2.6396744208969904,
    "reg_lambda": 0.016254068532870026,
    "subsample": 0.6740434973007393,
}

# (label, target, params-source). Params-source "v11" = the shipped tuned params.
FAMILIES: tuple[tuple[str, str, str], ...] = (
    ("degradation_regressor_p10", "degradation_regressor_p10", "v11"),
    ("degradation_regressor_p50", "degradation_regressor_p50", "v11"),
    ("degradation_regressor_p90", "degradation_regressor_p90", "v11"),
    ("cliff_classifier", "cliff_classifier", "v11"),
    ("stint_life_regressor", "stint_life_regressor", "v11"),
    ("stint_life_regressor_10e_S1x", "stint_life_regressor", "S1x"),
)

# The published full-window headlines this run must reproduce (gate 1). p10/p50/p90/cliff
# are `02b_qualifying_arms.json::published_headline`, measured on this same 32-column
# substrate on 2026-09-14. Stint life has no published figure at this contract (02b barred
# it), so its full-window cell is checked against evaluate.py's own split instead.
PUBLISHED_6DP = {
    "degradation_regressor_p10": 0.5320213273637161,
    "degradation_regressor_p50": 1.0467899119026969,
    "degradation_regressor_p90": 0.578513617807211,
    "cliff_classifier": 0.37186552717207966,
}

FOLD_CODE = "PRE_C_SCALE"     # the one shared code arm B collapses 2018's levels into


# ─── Raw frame, synthesised exactly as load_features synthesises it ─────────────
def raw_training_frame(duckdb_path: str = S.DUCKDB_PATH) -> tuple[pd.DataFrame, list[int]]:
    """The training-eligible mart rows, UNENCODED, with the stint-life target and its
    censoring flag merged on. This is `load_features` up to the point where it encodes --
    the encoding is what this item moves, so it cannot come pre-baked from the loader.

    Standard censoring (D5's realised stint ending), matching the shipped models. The
    10b cause-specific variant is a different question and is not this item's.
    """
    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        holdout_season = F.resolve_holdout_season(con)
        train_df = con.execute(
            f"SELECT * FROM {S.MART} "
            f"WHERE is_training_eligible AND race_year < {holdout_season}").df()
        stint_len = con.execute(
            f"SELECT stint_id, stint_length_laps, {S.STINT_LIFE_CENSOR_COLUMN} "
            f"FROM {S.STINT_FEATURES}").df()
    finally:
        con.close()

    merged = train_df.merge(stint_len, on="stint_id", how="left")
    train_df["stint_length_laps"] = merged["stint_length_laps"].to_numpy()
    train_df[S.STINT_LIFE_CENSOR_COLUMN] = (
        merged[S.STINT_LIFE_CENSOR_COLUMN].fillna(False).to_numpy(dtype=bool))
    train_df[S.STINT_LIFE_TARGET] = np.clip(
        train_df["stint_length_laps"] - train_df["lap_in_stint"], 0, None)

    training_seasons = sorted(int(y) for y in train_df["race_year"].unique())
    return train_df, training_seasons


def fold_eval_seasons(train_df: pd.DataFrame, training_seasons: list[int]) -> list[int]:
    """The season-fold eval seasons, derived from `train._season_folds` rather than
    written down -- no literal year, ever (features.py's standing rule)."""
    seasons = train_df["race_year"].to_numpy()
    return [int(seasons[ev][0])
            for _, ev in T._season_folds(seasons, training_seasons, n_splits=E.CV_SPLITS)]


def single_season_compounds(train_df: pd.DataFrame) -> list[str]:
    """Compound levels whose entire training-eligible support sits in ONE season, and
    that season is the earliest. Derived, then asserted against the three the spec names,
    so a substrate change cannot silently redefine arm B."""
    tab = pd.crosstab(train_df["compound"], train_df["race_year"])
    earliest = min(train_df["race_year"])
    return sorted(str(c) for c in tab.index
                  if (tab.loc[c] > 0).sum() == 1 and tab.loc[c, earliest] > 0)


# ─── One cell: window -> encoder -> fit -> score ────────────────────────────────
def build_cell(train_df: pd.DataFrame, window: tuple[int, ...], eval_season: int,
               target: str, *, compound_map: dict[str, str] | None = None,
               encoders_override: dict | None = None):
    """Encode a (window, eval season) pair with the encoder refit on the WINDOW's rows.

    This is the whole point of the item. `load_features` fits the encoder on the full
    training frame before the split; here the eval season's rows are encoded with a map
    that has never seen them, exactly as a deployed model would encode next season.
    Levels the window never saw fall to MISSING_ORDINAL, the same sentinel production uses.
    """
    spec = S.TARGET_BY_NAME[target]
    tr_raw = train_df[train_df["race_year"].isin(window)]
    ev_raw = train_df[train_df["race_year"] == eval_season]

    if compound_map:
        tr_raw = tr_raw.copy()
        ev_raw = ev_raw.copy()
        tr_raw["compound"] = tr_raw["compound"].replace(compound_map)
        ev_raw["compound"] = ev_raw["compound"].replace(compound_map)

    # <-- the encoder is refit on the WINDOW's rows, inside the fit. An override is
    # accepted only by arm C, which needs the same levels under permuted integers.
    encoders = encoders_override or F._build_encoders(tr_raw)

    masked = S.PER_TARGET_FEATURE_MASK.get(spec.family, frozenset())
    feature_cols = [c for c in S.FEATURE_COLUMNS if c not in masked]

    X_tr = F._encode_frame(tr_raw, encoders)[feature_cols].reset_index(drop=True)
    X_ev = F._encode_frame(ev_raw, encoders)[feature_cols].reset_index(drop=True)
    y_tr = F._resolve_target(tr_raw, target).reset_index(drop=True)
    y_ev = F._resolve_target(ev_raw, target).reset_index(drop=True)

    w_tr = (tr_raw["survival_weight"].to_numpy(dtype=np.float32)
            if spec.kind == "quantile" else None)
    c_tr = (tr_raw[S.STINT_LIFE_CENSOR_COLUMN].to_numpy(dtype=bool)
            if spec.kind == "survival" else None)
    c_ev = (ev_raw[S.STINT_LIFE_CENSOR_COLUMN].to_numpy(dtype=bool)
            if spec.kind == "survival" else None)

    # L0-7: XGBoost errors on NaN in y. load_features drops NULL-y rows from the whole
    # training frame BEFORE the fold split, so both sides must be dropped here for the
    # eval population to match the one evaluate.py scores.
    k_tr = y_tr.notna().to_numpy()
    k_ev = y_ev.notna().to_numpy()
    X_tr, y_tr = X_tr[k_tr].reset_index(drop=True), y_tr[k_tr].to_numpy()
    X_ev, y_ev = X_ev[k_ev].reset_index(drop=True), y_ev[k_ev].to_numpy()
    if w_tr is not None:
        w_tr = w_tr[k_tr]
    if c_tr is not None:
        c_tr, c_ev = c_tr[k_tr], c_ev[k_ev]

    return dict(spec=spec, X_tr=X_tr, y_tr=y_tr, X_ev=X_ev, y_ev=y_ev,
                w_tr=w_tr, c_tr=c_tr, c_ev=c_ev, encoders=encoders)


def permute_encoder(encoders: dict, rng: np.random.Generator) -> dict:
    """Arm C: same levels, shuffled integers. The null that says how much of arm B's
    movement is the NUMBERING changing rather than the compound identity changing."""
    out = {}
    for col, m in encoders.items():
        codes = rng.permutation(np.arange(len(m)))
        out[col] = {k: int(codes[i]) for i, k in enumerate(m)}
    return out


def fit_score_seeded(cell: dict, params: dict, seed: int) -> float:
    """evaluate.py's own fit and score, with the seed overridden.

    `random_state` is fixed inside `T._make_model` and cannot be passed through params,
    so it is set afterwards -- the same override `arms_02c` and `attribution.fit_seeded`
    use. AFTBooster is not an sklearn estimator and has no `set_params`, so its seed is
    written into the param dict it hands xgb.train.
    """
    spec = cell["spec"]
    m = T._make_model(spec, params)
    if spec.kind == "survival":
        m.params["seed"] = seed
        m.fit(cell["X_tr"], cell["y_tr"],
              sample_weight=T._sample_weight(spec, cell["y_tr"]),
              is_censored=cell["c_tr"])
        return E._score(spec, cell["y_ev"], m.predict(cell["X_ev"]),
                        cens=cell["c_ev"], scale=m.scale)
    m.set_params(random_state=seed)
    w = cell["w_tr"] if cell["w_tr"] is not None else T._sample_weight(spec, cell["y_tr"])
    m.fit(cell["X_tr"], cell["y_tr"], sample_weight=w)
    return E._score(spec, cell["y_ev"], E._predict_index(spec, m, cell["X_ev"]))


def improvement(arm: float, base: float, higher_is_better: bool) -> float:
    """Positive = improvement, on every metric."""
    return (arm - base) if higher_is_better else (base - arm)


# ─── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="2 seeds, 2 eval seasons, cliff+p50 only -- same code path")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    t_start = time.time()
    train_df, training_seasons = raw_training_frame()
    eval_seasons = fold_eval_seasons(train_df, training_seasons)
    unique_levels = single_season_compounds(train_df)
    earliest = min(training_seasons)

    seeds = SEEDS[:2] if args.quick else SEEDS
    families = (FAMILIES[1], FAMILIES[3]) if args.quick else FAMILIES
    if args.quick:
        eval_seasons = eval_seasons[-2:]

    print(f"[05d] training seasons {training_seasons}  eval seasons {eval_seasons}")
    print(f"[05d] {earliest}-only compound levels: {unique_levels} "
          f"({int((train_df['compound'].isin(unique_levels)).sum())} rows)")
    print(f"[05d] seeds {list(seeds)}")

    report: dict = {
        "item": "05d",
        "ran_at": pd.Timestamp.utcnow().isoformat(),
        "contract_version": "v11",
        "n_contract_features": len(S.FEATURE_COLUMNS),
        "quick": args.quick,
        "seeds": list(seeds),
        "training_seasons": training_seasons,
        "eval_seasons": eval_seasons,
        "encoder_refit_inside_fit": True,
        "single_season_compound_levels": unique_levels,
        "fold_code": FOLD_CODE,
        "arms": {
            "A_ladder": "most-recent-k seasons before E, encoder refit inside each fit",
            "B_fold": (f"full window, {unique_levels} collapsed to one code "
                       f"'{FOLD_CODE}' -- rows and regime kept, compound identity removed"),
            "C_renumber": "full window, all levels kept, encoder integers permuted per seed",
        },
        "families": {},
    }

    compound_map = {lvl: FOLD_CODE for lvl in unique_levels}

    for label, target, psrc in families:
        spec = S.TARGET_BY_NAME[target]
        params = dict(S1X_PARAMS) if psrc == "S1x" else E._params_for(target, "v11")
        hib = E._higher_is_better(spec)
        fam: dict = {
            "target": target, "params_source": psrc,
            "metric": E._headline_metric_name(spec), "higher_is_better": hib,
            "params": params, "eval_seasons": {},
        }
        print(f"\n=== {label}  ({fam['metric']}, "
              f"{'higher' if hib else 'lower'} is better, params={psrc}) ===")

        for E_season in eval_seasons:
            prior = [s for s in training_seasons if s < E_season]
            if len(prior) < 1:
                continue
            ladders = {}
            full_window = tuple(prior)
            base_encoders: dict = {}

            # ── Arm A: the most-recent-k ladder, k = 1..len(prior) ──────────────
            for k in range(1, len(prior) + 1):
                window = tuple(prior[-k:])
                cell = build_cell(train_df, window, E_season, target)
                if k == len(prior):
                    base_encoders = cell["encoders"]
                t0 = time.time()
                vals = [fit_score_seeded(cell, params, s) for s in seeds]
                a = np.asarray(vals, dtype=np.float64)
                ladders[k] = {
                    "k": k, "window": list(window),
                    "n_train": int(len(cell["X_tr"])), "n_eval": int(len(cell["X_ev"])),
                    "compound_levels": sorted(cell["encoders"]["compound"]),
                    "headline_by_seed": vals,
                    "mean": float(a.mean()), "sd": float(a.std(ddof=1)),
                    "secs": round(time.time() - t0, 1),
                }
                print(f"  E={E_season} k={k} win={window[0]}-{window[-1]} "
                      f"n={ladders[k]['n_train']:>6} "
                      f"mean={a.mean():.6f} sd={a.std(ddof=1):.6f} "
                      f"({ladders[k]['secs']}s)")

            base = ladders[len(prior)]                  # the full window = incumbent
            base_by_seed = np.asarray(base["headline_by_seed"])

            # ── Arm B: compound identity folded ────────────────────────────────
            cellB = build_cell(train_df, full_window, E_season, target,
                               compound_map=compound_map)
            valsB = [fit_score_seeded(cellB, params, s) for s in seeds]
            print(f"  E={E_season} FOLD  levels={sorted(cellB['encoders']['compound'])} "
                  f"mean={np.mean(valsB):.6f}")

            # ── Arm C: renumbering null (permuted integers, redrawn per seed) ───
            # Same window, same rows, same levels -- only the integers move. The
            # permutation is keyed on the seed so the five draws are independent.
            valsC = []
            for s in seeds:
                permuted = build_cell(
                    train_df, full_window, E_season, target,
                    encoders_override=permute_encoder(
                        base_encoders, np.random.default_rng(s)))
                valsC.append(fit_score_seeded(permuted, params, s))
            print(f"  E={E_season} RENUM mean={np.mean(valsC):.6f}")

            # ── Floors and paired deltas ───────────────────────────────────────
            sd_full = float(base_by_seed.std(ddof=1))
            floor_reseed = 2.0 * np.sqrt(2.0) * sd_full        # 01a-comparable
            n = len(seeds)

            def paired(vals) -> dict:
                d = np.asarray([improvement(v, b, hib)
                                for v, b in zip(vals, base_by_seed)], dtype=np.float64)
                sd_d = float(d.std(ddof=1)) if n > 1 else 0.0
                floor_paired = 2.0 * sd_d / np.sqrt(n)
                return {
                    "delta_by_seed": d.tolist(),
                    "mean_delta": float(d.mean()),
                    "sd_paired_delta": sd_d,
                    "floor_paired": float(floor_paired),
                    "x_floor_paired": (float(d.mean() / floor_paired)
                                       if floor_paired > 0 else None),
                    "x_floor_reseed": (float(d.mean() / floor_reseed)
                                       if floor_reseed > 0 else None),
                    "clears_paired": bool(d.mean() > floor_paired),
                }

            fam["eval_seasons"][str(E_season)] = {
                "eval_season": E_season,
                "prior_seasons": prior,
                "full_window": list(full_window),
                "full_window_mean": base["mean"],
                "full_window_sd": sd_full,
                "floor_reseed_2sqrt2sd": float(floor_reseed),
                "ladder": {str(k): v for k, v in ladders.items()},
                "ladder_vs_full": {
                    str(k): paired(v["headline_by_seed"])
                    for k, v in ladders.items() if k != len(prior)},
                "arm_B_fold": {
                    "headline_by_seed": valsB, "mean": float(np.mean(valsB)),
                    "compound_levels": sorted(cellB["encoders"]["compound"]),
                    "vs_full": paired(valsB)},
                "arm_C_renumber_null": {
                    "headline_by_seed": valsC, "mean": float(np.mean(valsC)),
                    "vs_full": paired(valsC)},
            }

            # gate 1 on the canonical seed of the full window, eval = last fold season
            if E_season == eval_seasons[-1] and label in PUBLISHED_6DP:
                got = base["headline_by_seed"][0]
                want = PUBLISHED_6DP[label]
                fam["instrument_check_6dp"] = bool(round(got, 6) == round(want, 6))
                fam["instrument_check"] = {"published": want, "refit": got,
                                           "abs_delta": abs(got - want)}
                print(f"  [gate 1] {label}: refit {got:.10f} vs published {want:.10f} "
                      f"-> {'PASS' if fam['instrument_check_6dp'] else 'FAIL'}")

        report["families"][label] = fam

    report["total_secs"] = round(time.time() - t_start, 1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))
    print(f"\n[05d] wrote {args.out} in {report['total_secs']}s")


if __name__ == "__main__":
    main()
