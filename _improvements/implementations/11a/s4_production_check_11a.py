"""11a stage 4 - cross-check on the real production artefact, and the data-volume answer.

Everything in s2/s3 rests on a shadow fit, which is weaker than production v11 (three
training seasons against seven). This stage removes that dependency for the one claim
that matters most - whether a circuit component exists at all - by reading the
PRODUCTION boosters on rows they were never trained on.

`load_features` trains on `is_training_eligible AND race_year < holdout_season`, but
`load_scoring_frame` scores EVERY lap. So the 12,876 rows with `is_training_eligible =
False` and a non-null target carry genuine out-of-sample production predictions, with no
refit anywhere. They are a different population - ineligible rows are ineligible for a
reason - so this is a corroborating read, not a replacement for s2.

Also computes the question s3's sweep raises: how many races per circuit would a
per-circuit offset actually need?
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.src import ceiling as C
from ml.src import schema as S

HERE = Path(__file__).resolve().parent
TARGET = S.DEGRADATION_TARGET
MIN_LAPS = 300


def decompose(f: pd.DataFrame, label: str) -> dict:
    cov = (f[TARGET] >= f["q10"]) & (f[TARGET] <= f["q90"])
    per_race = f.assign(c=cov).groupby(["circuit_key", "race_id"])["c"].mean().reset_index()
    vc = C.variance_components(per_race["c"].to_numpy(), per_race["circuit_key"].to_numpy())
    pc = f.assign(c=cov).groupby("circuit_key").agg(n=("c", "size"), m=("c", "mean"))
    pc = pc[pc["n"] >= MIN_LAPS]
    out = {
        "label": label, "n": int(len(f)), "races": int(f["race_id"].nunique()),
        "circuits": int(f["circuit_key"].nunique()),
        "pooled_coverage": float(cov.mean()),
        "below_p10": float((f[TARGET] < f["q10"]).mean()),
        "above_p90": float((f[TARGET] > f["q90"]).mean()),
        "mean_width": float((f["q90"] - f["q10"]).mean()),
        "circuits_n_ge_300": int(len(pc)),
        "per_circuit_spread_pts": float((pc["m"].max() - pc["m"].min()) * 100) if len(pc) else None,
    }
    if vc is not None:
        out |= {
            "n_race_units": vc.n, "n_circuits_vc": vc.n_groups,
            "mean_races_per_circuit": vc.mean_rows_per_group,
            "sigma_b2_circuit": vc.sigma_b2,
            "sigma_w2_race_within_circuit": vc.sigma_w2,
            "icc_circuit_share": vc.share,
            "icc_naive_biased_up": vc.share_naive,
            "sd_circuit_effect_pts": float(np.sqrt(vc.sigma_b2) * 100),
            "sd_race_noise_pts": float(np.sqrt(vc.sigma_w2) * 100),
        }
    return out


def races_needed(sigma_b2: float, sigma_w2: float) -> dict:
    """How many races per circuit before a per-circuit coverage estimate is worth using?

    The per-circuit estimate has standard error sigma_w / sqrt(n_races). A per-circuit
    correction is only informative when that error is small against the circuit effect
    it is trying to capture, sigma_b. Reported at three thresholds because there is no
    single canonical one.
    """
    sb, sw = float(np.sqrt(sigma_b2)), float(np.sqrt(sigma_w2))
    if sb <= 0:
        return {"sigma_b_pts": 0.0, "verdict": "no circuit component to estimate"}
    return {
        "sigma_b_circuit_effect_pts": sb * 100,
        "sigma_w_race_noise_pts": sw * 100,
        "noise_to_signal_ratio": sw / sb,
        "races_for_SE_equal_to_effect": (sw / sb) ** 2,
        "races_for_SE_half_the_effect": (sw / (0.5 * sb)) ** 2,
        "races_for_SE_third_the_effect": (sw / (sb / 3)) ** 2,
        "calendar_note": "a circuit hosts ~1 race per season, so races-per-circuit is "
                         "seasons-of-history-per-circuit",
    }


def rescore_production() -> pd.DataFrame:
    """Re-score the CURRENT v11 boosters on the CURRENT mart, in memory.

    `data/marts/mart_degradation_predictions.parquet` was written 2026-09-05 and the mart
    has been rebuilt since, so the stored predictions and the stored target no longer
    come from the same warehouse state. Reusing the production path
    (`features.load_scoring_frame` + `predict._load_model`) removes that skew. Nothing is
    written: this is the same computation predict.py does, minus the parquet write.
    """
    import duckdb
    from ml.src import features as F
    from ml.src import predict as P

    X_all, meta, _, _ = F.load_scoring_frame()
    Xv = X_all.to_numpy(dtype=np.float32)
    spec = {s.name: s for s in S.PRODUCTION_TARGETS}
    trio = np.vstack([
        P._load_model(spec["degradation_regressor_p10"], S.MODEL_VERSION_DEFAULT).predict(Xv),
        P._load_model(spec["degradation_regressor_p50"], S.MODEL_VERSION_DEFAULT).predict(Xv),
        P._load_model(spec["degradation_regressor_p90"], S.MODEL_VERSION_DEFAULT).predict(Xv),
    ]).T
    trio = np.sort(trio, axis=1)          # predict.py's crossing guard

    con = duckdb.connect(S.DUCKDB_PATH, read_only=True)
    try:
        extra = con.execute(
            f"SELECT lap_id, race_id, {TARGET} FROM {S.MART}").df()
    finally:
        con.close()
    out = meta.copy()
    out["q10"], out["q90"] = trio[:, 0], trio[:, 2]
    out = out.merge(extra, on="lap_id", how="left")
    out[TARGET] = pd.to_numeric(out[TARGET], errors="coerce")
    return out


def main() -> int:
    print("11a stage 4 - production cross-check and the data-volume answer")
    prod = rescore_production()
    prod = prod[prod[TARGET].notna()].copy()
    elig = prod[prod["is_training_eligible"].astype(bool)]
    inel = prod[~prod["is_training_eligible"].astype(bool)]

    res = {
        "production_in_sample_eligible": decompose(elig, "production v11, IN-SAMPLE (R4's rows)"),
        "production_out_of_sample_ineligible": decompose(
            inel, "production v11, OUT-OF-SAMPLE (never trained on these rows)"),
    }
    for k, v in res.items():
        print(f"  [{v['label']}]")
        print(f"     n={v['n']:,} races={v['races']} coverage={v['pooled_coverage']:.4%} "
              f"(below p10 {v['below_p10']:.3%} / above p90 {v['above_p90']:.3%})")
        print(f"     per-circuit spread (n>=300) = {v['per_circuit_spread_pts']:.1f} pts "
              f"over {v['circuits_n_ge_300']} circuits")
        print(f"     circuit ICC = {v['icc_circuit_share']:.3f}  "
              f"(naive, as a per-circuit table computes it: {v['icc_naive_biased_up']:.3f})")
        print(f"     sd(circuit effect) = {v['sd_circuit_effect_pts']:.2f} pts   "
              f"sd(race noise) = {v['sd_race_noise_pts']:.2f} pts")

    # The data-volume answer, computed from BOTH the shadow and the production reads so
    # it does not depend on which model produced the quantiles.
    shadow = json.loads((HERE / "s2_results.json").read_text())["schemes"]["raw"]["variance_decomposition"]
    res["races_needed_shadow"] = races_needed(shadow["sigma_b2_circuit"],
                                              shadow["sigma_w2_race_within_circuit"])
    res["races_needed_production_oos"] = races_needed(
        res["production_out_of_sample_ineligible"]["sigma_b2_circuit"],
        res["production_out_of_sample_ineligible"]["sigma_w2_race_within_circuit"])
    print("\n  races per circuit needed before a per-circuit offset is informative:")
    for k in ("races_needed_shadow", "races_needed_production_oos"):
        r = res[k]
        if "races_for_SE_half_the_effect" in r:
            print(f"    {k:32s} SE=effect {r['races_for_SE_equal_to_effect']:.1f}   "
                  f"SE=half {r['races_for_SE_half_the_effect']:.1f}   "
                  f"SE=third {r['races_for_SE_third_the_effect']:.1f}")
        else:
            print(f"    {k:32s} {r['verdict']}")

    (HERE / "s4_results.json").write_text(json.dumps(res, indent=2, default=str))
    print("  wrote s4_results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
