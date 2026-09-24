"""§5.5.2 magnitude: how much of an eval score depends on the eval season carrying IN-RACE seed params.

Fold = v13-shaped (train seasons <= 2023, eval 2024), built with the production season-fold generator.
One production-fitted model per target (evaluate._fit, v14 best params). Scored twice on the SAME eval rows:
  A  eval features as built (2024 cells fitted on the 2024 race itself)            -> the published-protocol number
  B  eval seed-derived features recomputed from LAGGED params (2023 cell carried to 2024,
     missing when the venue/compound had no 2023 cell -- exactly the 2025 carry-forward rule)
No refit between A and B, so the delta carries no reseed noise. Label untouched in both.
Seed-derived columns recomputed by re-running the COMPILED production SQL of int_compound_cliff_predicted
against a counterfactual dim_compounds_season (DuckDB in-memory, dev attached READ_ONLY). cwd = transform/.
Arm C (optional): train AND eval on lagged features (honest pipeline), one refit -> reseed noise applies."""
import sys, json, re
sys.path.insert(0, "/Users/justin/github/off-the-pace")
import duckdb, numpy as np, pandas as pd
from pathlib import Path
from ml.src import features as F, schema as S, train as T, evaluate as E

EVAL, PRIOR = 2024, 2023
SEED_COLS = ["compound_wear_gradient", "compound_cliff_onset_laps", "compound_cliff_severity",
             "compound_grip_peak", "compound_optimal_temp_low", "compound_optimal_temp_high"]
DERIVED = ["expected_compound_pace_s", "expected_degradation_rate_s_per_lap", "cliff_onset_passed", "laps_past_cliff"]

def counterfactual_features(lag_all_seasons: bool):
    con = duckdb.connect()
    con.execute("ATTACH '../data/dev.duckdb' AS dev (READ_ONLY)")
    seasons_to_lag = "season >= 2019" if lag_all_seasons else f"season = {EVAL}"
    # season S cell := season S-1 cell of the same (circuit_key, compound); other seasons untouched
    con.execute(f"""
      CREATE TEMP TABLE cf_dim AS
      SELECT * FROM dev.main.dim_compounds_season WHERE NOT ({seasons_to_lag})
      UNION ALL
      SELECT circuit_key, compound_code, season + 1 AS season, compound_grip_peak, compound_wear_gradient,
             compound_optimal_temp_low, compound_optimal_temp_high, compound_cliff_onset_laps,
             compound_cliff_severity, fit_date, data_window, notes
      FROM dev.main.dim_compounds_season WHERE ({seasons_to_lag.replace('season', '(season + 1)')})
    """)
    sql = Path("target/compiled/off_the_pace/models/intermediate/int_compound_cliff_predicted.sql").read_text()
    sql = sql.replace('"dev"."main"."dim_compounds_season"', "cf_dim")
    derived = con.execute(sql).df()[["lap_id"] + DERIVED]
    direct = con.execute("""
      SELECT r.lap_id, cp.compound_wear_gradient, cp.compound_cliff_onset_laps, cp.compound_cliff_severity,
             cp.compound_grip_peak, cp.compound_optimal_temp_low, cp.compound_optimal_temp_high
      FROM dev.main.int_lap_residual_decomposed r
      LEFT JOIN dev.main.race_to_track rtt ON r.race_id = rtt.race_id
      LEFT JOIN cf_dim cp ON rtt.track_id = cp.circuit_key AND r.compound = cp.compound_code AND r.race_year = cp.season
    """).df()
    return derived.merge(direct, on="lap_id", how="outer").set_index("lap_id")

def encode_patch(X: pd.DataFrame, lap_ids, cf: pd.DataFrame) -> pd.DataFrame:
    X = X.copy()
    sub = cf.reindex(lap_ids)
    for c in X.columns:
        if c in S.BOOLEAN_COLUMNS and c in sub.columns:
            X[c] = sub[c].map({True: 1.0, False: 0.0}).astype("float32").to_numpy()
        elif c in sub.columns:
            X[c] = pd.to_numeric(sub[c], errors="coerce").astype("float32").to_numpy()
    return X

cf_eval = counterfactual_features(lag_all_seasons=False)
cf_all = counterfactual_features(lag_all_seasons=True)

# sanity: as-built reproduction -- recompute with the UNMODIFIED dim and compare to the mart
con = duckdb.connect("../data/dev.duckdb", read_only=True)
mart = con.execute(f"select lap_id, {', '.join(SEED_COLS + DERIVED)} from fct_cliff_prediction_features where race_year in ({PRIOR},{EVAL})").df().set_index("lap_id")
pre = cf_eval.reindex(mart.index)
same_2023 = mart.index.str.startswith(f"{PRIOR}")
diffs = {c: float(np.nanmax(np.abs(pd.to_numeric(mart.loc[same_2023, c]).astype(float) - pd.to_numeric(pre.loc[same_2023, c]).astype(float)))) for c in SEED_COLS + ["expected_compound_pace_s", "expected_degradation_rate_s_per_lap", "laps_past_cliff"]}
print("reproduction check on untouched season 2023 (max |diff| vs mart):", json.dumps(diffs))
chg = mart.index.str.startswith(f"{EVAL}")
moved = {c: float(np.mean(~np.isclose(pd.to_numeric(mart.loc[chg, c]).astype(float), pd.to_numeric(pre.loc[chg, c]).astype(float), equal_nan=True))) for c in SEED_COLS + DERIVED if c != "cliff_onset_passed"}
print("share of 2024 rows whose value moves under the lag:", json.dumps({k: round(v, 3) for k, v in moved.items()}))
print("2024 rows with NO lagged cell:", int(pre.loc[chg, "compound_cliff_onset_laps"].isna().sum()), "of", int(chg.sum()))

out = {}
for target in sys.argv[1:]:
    spec = S.TARGET_BY_NAME[target]
    b = F.load_features(S.DUCKDB_PATH, target=target, persist_encoders=False)
    seasons = b.groups_train.to_numpy()
    folds = list(T._season_folds(seasons, b.training_seasons, n_splits=5))
    tr, ev = next((t, e) for t, e in folds if int(seasons[e][0]) == EVAL)
    assert int(seasons[tr].max()) == PRIOR
    y = b.y_train.to_numpy(); lap = b.meta_train["lap_id"].to_numpy()
    cens = b.meta_train[S.STINT_LIFE_CENSOR_COLUMN].to_numpy(dtype=bool) if spec.kind == "survival" else None
    params = E._params_for(target, S.MODEL_VERSION_DEFAULT)
    X_tr, X_ev = b.X_train.iloc[tr].reset_index(drop=True), b.X_train.iloc[ev].reset_index(drop=True)
    model = E._fit(spec, params, X_tr, y[tr], cens=None if cens is None else cens[tr])
    scale = params.get("aft_loss_distribution_scale") if spec.kind == "survival" else None
    def score(m, X):
        pred = E._predict_index(spec, m, X)
        return E._score(spec, y[ev], pred, cens=None if cens is None else cens[ev], scale=scale)
    X_ev_B = encode_patch(X_ev, lap[ev], cf_eval)
    sA, sB = score(model, X_ev), score(model, X_ev_B)
    has_cell = cf_eval.reindex(lap[ev])["compound_cliff_onset_laps"].notna().to_numpy()
    def score_mask(m, X, mask):
        pred = E._predict_index(spec, m, X)[mask]
        return E._score(spec, y[ev][mask], pred, cens=None if cens is None else cens[ev][mask], scale=scale)
    sA_cell, sB_cell = score_mask(model, X_ev, has_cell), score_mask(model, X_ev_B, has_cell)
    X_tr_C = encode_patch(X_tr, lap[tr], cf_all); X_ev_C = encode_patch(X_ev, lap[ev], cf_all)
    model_C = E._fit(spec, params, X_tr_C, y[tr], cens=None if cens is None else cens[tr])
    sC = score(model_C, X_ev_C)
    hib = E._higher_is_better(spec)
    out[target] = dict(metric=E._headline_metric_name(spec), higher_is_better=hib, n_train=int(len(tr)), n_eval=int(len(ev)),
                       A_inrace_eval=sA, B_lagged_eval_same_model=sB, C_lagged_train_and_eval=sC,
                       A_minus_B=sA - sB, A_minus_C=sA - sC,
                       share_eval_with_lagged_cell=float(has_cell.mean()), A_on_cell_rows=sA_cell, B_on_cell_rows=sB_cell,
                       A_minus_B_on_cell_rows=sA_cell - sB_cell)
    print(target, json.dumps(out[target]))
Path("/private/tmp/claude-501/-Users-justin-github-off-the-pace/a20b3a7b-0089-474d-8e4a-d20ca67bbc81/scratchpad/transform_audit/phaseC_seed_magnitude_v2.json").write_text(json.dumps(out, indent=2))
