"""02d — Tier 3 SC/VSC hazard: the pre-registered arms.

Runs exactly the arms declared in _improvements/work/02-feature-expansion.md's `02d`
section before any of them was run:

    stint_life_regressor                    PRIMARY   (survival, lower better)
    cliff_classifier                        secondary (macro-F1, higher better)
    degradation_regressor p10 / p50 / p90   secondary (pinball, lower better)

WHY stint_life IS THE PRIMARY FAMILY HERE, and not a follow-on as it was in 02b. The
leaf doc's §1 caps a circuit-constant feature at the between-stint share of the
degradation target. Stint life is the one target not shaped like that column: it is
right-censored on 46.2% of training rows, stint ends are pit-wall decisions, and 00b
measured that 26.87% of UNCENSORED stint ends fall on an SC/VSC lap against 6.49% of
censored ones, in every season. That is the mechanism this item exists to test.

10d's bar on this family (the shipped booster was tuned under the wrong label, on the
mixture NLL, with 2024 in the validation folds) was discharged when 10e LANDED
2026-09-19, so the floor is measured against the model that is actually shipping.

THE CONFOUND THIS SCRIPT IS SHAPED AROUND. The NaN mask of the three rate columns is
EXACTLY race_year == 2018 -- 14,982 of 119,822 training-eligible rows, 100% of 2018 and
0% of every other season -- because 2018 is the earliest season in the warehouse and has
neither a prior season nor a prior-season pooled prior. race_year is NOT in
FEATURE_COLUMNS, so the hazard block hands the model a free season indicator through its
missingness, and the permutation null CANNOT destroy it because a row shuffle moves the
NaNs with the values. 02c hit the identical shape in corner_input_coverage. Arms C and D
exist to price it: C is venue tenure with no NULLs at all, D is the mask alone.

The marginal correlations say this is not a hypothetical. Against the 5-lap degradation
label, the confound columns OUT-CORRELATE the mechanism columns: prior_seasons_n 0.0301
and prior_racing_laps 0.0246, against 0.0159 / 0.0094 / 0.0029 for the sc / any / vsc
rates. A naive arm A that cleared would most likely be clearing on tenure.

Protocol, in the order gates.md numbers it (identical to 02b's and 02c's):

  1. instrument check  -- the 32-column refit must reproduce the published v12 headline
                          to six decimals, per family, before anything else is trusted.
  2. add-ablation      -- cv_final_fold, train 2018-2023, eval 2024, evaluate.py's own
                          _fit/_score.
  3. floor             -- attribution.refit_noise_floor over seeds RANDOM_STATE+0..4,
                          delta measured against 2*sqrt(2)*sd of THAT family. Measured
                          FRESH: 02b's 2026-09-19 re-score found the floors moved by up
                          to 3.2x across the 08m rebuild, so no borrowed floor is valid.
  4. permutation null  -- the arm's own columns row-shuffled in train AND eval, so
                          capacity is preserved and signal destroyed. Capacity and
                          information reported separately.
  7. e-value           -- Construction B (paired safe-t) at n=10, g=1, as 09c ruled it
                          and as pre-registered, with the Monte Carlo validity check the
                          reference requires. NOT n=5: E_max(5,1) = 36 sits below the
                          campaign's lone-rejection bar of 20*(m+1), so a construction
                          that size cannot reject whatever the data show. E_max(10,1) =
                          11^4.5 = 48,558.70. See the seed block below for the floor-vs-
                          e-value n decision 09c left open and 02d closes.

Deltas are oriented so POSITIVE ALWAYS MEANS IMPROVEMENT, on every metric.

Usage:  PYTHONPATH=. ./.venv/bin/python scripts/arms_02d_sc_hazard.py

Writes ml/artefacts/02d_sc_hazard_arms.json -- every fit's headline, per seed, so a
reader can recompute any delta, floor ratio or e-value in the leaf doc without refitting.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from ml.src import attribution as AT
from ml.src import evaluate as E
from ml.src import features as F
from ml.src import schema as S
from ml.src import train as T

# ─── The five mart columns, plus the one derived control ────────────────────────
HAZARD_COLS = (
    "circuit_sc_hazard_per_lap",
    "circuit_vsc_hazard_per_lap",
    "circuit_any_hazard_per_lap",
)
EXPOSURE_COLS = (
    "circuit_hazard_prior_racing_laps",
    "circuit_hazard_prior_seasons_n",
)
MART_COLS = HAZARD_COLS + EXPOSURE_COLS

# Derived in hazard_frame(), not read from the mart: 1.0 exactly where the hazard is
# unknowable. This is the channel arm B gets for free through its own missingness, and
# the only way to price it is to hand it to the model on its own.
MASK_COL = "hazard_unknowable_flag"

ARMS: dict[str, tuple[str, ...]] = {
    "A_full": MART_COLS,                    # 5 — the group as it would ship
    "B_hazard": HAZARD_COLS,                # 3 — the mechanism arm
    "C_exposure": EXPOSURE_COLS,            # 2 — the confound arm: venue tenure
    "D_unknowable_mask": (MASK_COL,),       # 1 — the season channel, isolated
}

# ─── Seeds: two studies, two n, and the reason they differ ──────────────────────
# gates.md step 3 defines the reseed floor as 2*sqrt(2)*sd over FIVE reseeds. 09c
# (LANDED 2026-09-19) separately ruled Construction B to n=10, g=1, because at n=5 the
# ceiling is E_max(5,1) = 36 and the campaign's lone-rejection bar is 20*(m+1) with
# m = 103 declared hypotheses -- i.e. ~2,080. A construction whose ceiling sits below
# that bar cannot produce a lone rejection whatever the data show; that is arithmetic,
# not evidence, and it is why 02d depends_on 09c.
#
# 09c left one operational choice open in writing, to "whoever runs the next arm at
# n = 10": reuse ten seeds for both studies, or pay the extra five. 02d is that arm and
# the decision is recorded here.
#
# DECIDED: pay the extra five. The floor stays at FIVE reseeds, exactly as gates.md
# step 3 words it, so 02d's floor is measured on the same instrument as 02a's, 02b's,
# 02c's and every prior item's -- widening it to ten would tighten this item's floor
# while making its ratios incomparable to the ones they will be read beside, which is
# the mistake 02b's re-score exists to undo. The paired e-value study runs at ten, and
# its first five seeds ARE the floor's five, so the two remain nested rather than
# disjoint. Cost is 5 (floor) + 20 (paired, per arm) refits rather than 20.
FLOOR_SEEDS: tuple[int, ...] = tuple(S.RANDOM_STATE + i for i in range(5))
E_SEEDS: tuple[int, ...] = tuple(S.RANDOM_STATE + i for i in range(10))
assert E_SEEDS[:len(FLOOR_SEEDS)] == FLOOR_SEEDS, "the e-value seeds must nest the floor's"
E_VALUE_G = 1.0          # pre-registered: a one-sd effect

# The family size this construction was sized against, recorded beside the
# pre-registration as gates.md step 7 requires. 09c enumerated 103 declared hypotheses
# campaign-wide as of 2026-09-19; 02d declares 4 arms x 5 families = 20 more, giving
# m = 123 and a lone-rejection bar of 20*(123+1) = 2,480. E_max(10, 1) = 11^4.5 =
# 48,558.70 clears that ~19.6x.
FAMILY_SIZE_SIZED_AGAINST = 123
LONE_REJECTION_BAR = 20 * (FAMILY_SIZE_SIZED_AGAINST + 1)
PRIMARY_FAMILY = "stint_life_regressor"
FAMILIES = (PRIMARY_FAMILY, "cliff_classifier", "degradation_regressor_p10",
            "degradation_regressor_p50", "degradation_regressor_p90")
OUT = Path("ml/artefacts/02d_sc_hazard_arms.json")


# ─── Column plumbing ────────────────────────────────────────────────────────────
def hazard_frame(duckdb_path: str = S.DUCKDB_PATH) -> pd.DataFrame:
    """The five mart columns plus the derived mask, indexed by lap_id, float32.

    Read straight off `fct_cliff_prediction_features` rather than through features.py:
    the columns are deliberately NOT in FEATURE_COLUMNS yet (the contract moves only if
    these arms say it should), so the loader does not carry them. The mart has already
    resolved the (circuit_key, race_year) join and broadcast the circuit x season values
    onto every lap, so a lap_id read here needs no further join. Encoding matches
    `_encode_frame`'s continuous branch exactly -- to_numeric then float32, native NaN
    left as NaN.

    The mask is taken from circuit_sc_hazard_per_lap's own NaN pattern rather than from
    `race_year == 2018`. The two are identical today (verified: 14,982 rows, both
    directions), but deriving it from the column ties the control to the thing it is
    controlling for -- if the NULL rule ever changes, the arm follows it instead of
    silently testing a season dummy that no longer matches.
    """
    cols = ", ".join(MART_COLS)
    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        df = con.execute(f"SELECT lap_id, {cols} FROM {S.MART}").df()
    finally:
        con.close()
    df = df.set_index("lap_id")
    for c in MART_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float32")
    df[MASK_COL] = df["circuit_sc_hazard_per_lap"].isna().astype("float32")
    return df


def attach(X: pd.DataFrame, lap_ids: np.ndarray, extra: pd.DataFrame,
           cols: tuple[str, ...]) -> pd.DataFrame:
    """X with `cols` appended, aligned row-for-row on lap_id."""
    block = extra.reindex(pd.Index(lap_ids))[list(cols)]
    if block.isna().all(axis=1).all():
        raise RuntimeError("no sc-hazard rows matched the split's lap_ids")
    out = X.copy()
    for c in cols:
        out[c] = block[c].to_numpy(dtype=np.float32)
    return out


def shuffled(X: pd.DataFrame, cols: tuple[str, ...], rng: np.random.Generator) -> pd.DataFrame:
    """Row-shuffle the block of new columns JOINTLY.

    Jointly, not column-by-column: the arm's internal correlation structure is part of
    its capacity, and the null this scores is "these columns carry no information about
    the label", not "these columns are unrelated to each other". Capacity is preserved
    exactly -- same matrix shape, same marginal distributions, same NaN count.

    THE CAVEAT THAT MATTERS MORE HERE THAN IT DID IN 02b. NaNs move with their values,
    so for arm B this shuffle preserves the NUMBER of NaNs but destroys their alignment
    with season -- which means the permutation null does price part of the mask channel
    for B, but only the part that is alignment rather than count. It cannot be relied on
    to price the mask, and that is precisely why arm D exists as a separate arm rather
    than as a footnote on P. Arm D's own column has no NaNs at all, so its shuffle is
    clean.
    """
    out = X.copy()
    perm = rng.permutation(len(X))
    block = out[list(cols)].to_numpy()[perm]
    for i, c in enumerate(cols):
        out[c] = block[:, i]
    return out


# ─── Fit / score ────────────────────────────────────────────────────────────────
def fit_seeded(spec: S.TargetSpec, params: dict, X, y, w, seed: int, cens=None):
    """evaluate.py's fit with the seed overridden -- the same override
    `arms_02b_qualifying.fit_seeded` and `arms_02c_corner_inputs.fit_seeded` use, for
    the same reason: random_state is fixed inside T._make_model and cannot be passed
    through `params`.

    The survival branch takes a different route because `AFTBooster` is not an sklearn
    estimator and has no `set_params`: it carries `seed` inside its own params dict,
    where `**p` merges AFTER the default, so injecting it there is the supported route.
    This is exactly `arms_10d_calibration_arms.fit_seeded`, reused rather than
    re-derived -- varying the seed redraws `subsample` and `colsample_bytree`, which is
    what makes the five refits genuinely differ. It carries the whole weight of this
    run, since stint_life_regressor is the PRIMARY family here.
    """
    if spec.kind == "survival":
        if cens is None:
            raise ValueError("fit_seeded on a survival target needs the censoring flags")
        m = T._make_model(spec, {**params, "seed": int(seed)})
        weights = w if w is not None else T._sample_weight(spec, y)
        return m.fit(X, y, sample_weight=weights,
                     is_censored=np.asarray(cens, dtype=bool))
    m = T._make_model(spec, params)
    weights = w if w is not None else T._sample_weight(spec, y)
    m.set_params(random_state=seed)
    return m.fit(X, y, sample_weight=weights)


def score(spec: S.TargetSpec, model, X_ev, y_ev, cens_ev=None) -> float:
    """Headline on the eval rows.

    The survival branch must hand `_score` both the censoring flags and the scale the
    model was ACTUALLY fitted at -- `_score` raises without the former, and the AFT
    scale is a term in the likelihood, so scoring at the module default when the fit
    used a tuned scale silently compares two different likelihoods. This mirrors
    evaluate.py's own `scale = getattr(model, "scale", None)` line.
    """
    if spec.kind == "survival":
        return E._score(spec, y_ev, E._predict_index(spec, model, X_ev),
                        cens=cens_ev, scale=getattr(model, "scale", None))
    return E._score(spec, y_ev, E._predict_index(spec, model, X_ev))


def delta(arm_value: float, base_value: float, higher_is_better: bool) -> float:
    """Positive = improvement, on every metric."""
    return (arm_value - base_value) if higher_is_better else (base_value - arm_value)


# ─── E-value, Construction B (paired safe-t) -- identical to 02b's and 02c's ─────
def safe_t_e_value(d: np.ndarray, g: float = E_VALUE_G) -> dict:
    """E = (1+ng)^(-1/2) * [(1+t^2/(n-1)) / (1+t^2/((1+ng)(n-1)))]^(n/2).

    The one-sample Bayes factor under a right-Haar prior on sigma and N(0,g) on the
    effect size -- Grunwald, de Heide & Koolen's safe t-test. Exact for any unknown
    sigma, which is why the pre-registration chose it over Construction A.
    """
    d = np.asarray(d, dtype=np.float64)
    n = len(d)
    d_bar = float(d.mean())
    s_d = float(d.std(ddof=1))
    cap = (1.0 + n * g) ** ((n - 1) / 2.0)   # the t -> inf limit; 36 at n=5, g=1
    if s_d == 0.0:
        t = 0.0 if d_bar == 0.0 else float(np.copysign(np.inf, d_bar))
    else:
        t = float(np.sqrt(n) * d_bar / s_d)
    if np.isfinite(t):
        num = 1.0 + t * t / (n - 1)
        den = 1.0 + t * t / ((1.0 + n * g) * (n - 1))
        e = (1.0 + n * g) ** -0.5 * (num / den) ** (n / 2.0)
    else:
        e = cap
    # The DECLARED formula is reported exactly as pre-registered, and it is symmetric
    # in t. A consistently negative delta therefore also returns a large E -- evidence
    # against "these columns are exchangeable with their own shuffle", in the wrong
    # direction. Reading that as support for the arm would be a misreading, so the
    # direction is carried beside the number rather than folded into it: applying a
    # one-sided transform now would be changing the construction after seeing the data,
    # which is the one thing that voids an e-value.
    return {"n": n, "g": g, "d_bar": d_bar, "s_d": s_d, "t": t, "E": float(e),
            "direction_is_improvement": bool(d_bar > 0),
            "max_attainable_E": float(cap)}


def e_value_validity_check(n_draws: int = 100_000, seed: int = S.RANDOM_STATE) -> dict:
    """Push i.i.d. N(0, sigma) deltas through the implementation and confirm mean(E)=1.

    Required by e_value_construction.md §4: "A construction whose null mean is not 1 is
    not an e-value." Run at several sigma because the whole point of Construction B is
    that validity does not depend on sigma.
    """
    rng = np.random.default_rng(seed)
    out = {}
    for sigma in (0.001, 0.01, 0.1, 1.0):
        d = rng.normal(0.0, sigma, size=(n_draws, len(E_SEEDS)))
        d_bar = d.mean(axis=1)
        s_d = d.std(axis=1, ddof=1)
        t = np.sqrt(len(E_SEEDS)) * d_bar / s_d
        n, g = len(E_SEEDS), E_VALUE_G
        num = 1.0 + t ** 2 / (n - 1)
        den = 1.0 + t ** 2 / ((1.0 + n * g) * (n - 1))
        e = (1.0 + n * g) ** -0.5 * (num / den) ** (n / 2.0)
        out[f"sigma={sigma}"] = {
            "mean_E": float(e.mean()),
            "mc_se": float(e.std(ddof=1) / np.sqrt(n_draws)),
            "p_E_gt_20": float((e > 20).mean()),
        }
    return out


# ─── One family ─────────────────────────────────────────────────────────────────
def run_family(target: str, split, extra: pd.DataFrame, published: float,
               log) -> dict:
    spec = S.TARGET_BY_NAME[target]
    params = E._params_for(target, S.MODEL_VERSION_DEFAULT)
    hib = E._higher_is_better(spec)
    w_tr = split.w_tr
    X_tr, X_ev = split.X_tr, split.X_ev
    y_tr, y_ev = split.y_tr, split.y_ev
    # None for every family except stint_life_regressor; the survival fit and score
    # both raise rather than silently proceed without them.
    c_tr, c_ev = split.cens_tr, split.cens_ev

    def _fit_canon(Xm):
        return E._fit(spec, params, Xm, y_tr, cens=c_tr, w=w_tr)

    def _fit_seed(Xm, s):
        return fit_seeded(spec, params, Xm, y_tr, w_tr, s, cens=c_tr)

    def _sc(model, Xe):
        return score(spec, model, Xe, y_ev, cens_ev=c_ev)

    res: dict = {
        "target": target,
        "is_primary": target == PRIMARY_FAMILY,
        "metric": E._headline_metric_name(spec),
        "higher_is_better": hib,
        "n_train": int(len(X_tr)), "n_eval": int(len(X_ev)),
        "n_baseline_features": int(X_tr.shape[1]),
        "floor_seeds": list(FLOOR_SEEDS),
        "e_value_seeds": list(E_SEEDS),
    }

    # ── Step 1: instrument check ────────────────────────────────────────────────
    t0 = time.time()
    base_model = _fit_canon(X_tr)
    baseline = _sc(base_model, X_ev)
    res["baseline_headline"] = baseline
    res["published_headline"] = published
    res["instrument_check_6dp"] = bool(abs(baseline - published) < 5e-7)
    log(f"  [{target}] baseline={baseline:.10f} published={published:.10f} "
        f"instrument_check={res['instrument_check_6dp']} ({time.time()-t0:.0f}s)")
    if not res["instrument_check_6dp"]:
        res["aborted"] = ("instrument check failed: the 32-column refit does not "
                          "reproduce the published headline, so no delta below it "
                          "would mean anything")
        return res

    # ── Step 3: this family's own reseed floor, measured fresh ──────────────────
    t0 = time.time()
    floor = AT.refit_noise_floor(
        lambda s: _fit_seed(X_tr, s),
        lambda yt, m, X: score(spec, m, X, yt, cens_ev=c_ev),
        X_ev, y_ev, FLOOR_SEEDS)
    res["refit_noise"] = floor
    F2 = floor["delta_noise_2sd"]
    log(f"  [{target}] floor 2*sqrt(2)*sd = {F2:.8f}  (sd={floor['headline_sd']:.8f}, "
        f"{time.time()-t0:.0f}s)")

    # ── Steps 2 + 4 + 7, per arm ────────────────────────────────────────────────
    arm_rows: dict[str, dict] = {}
    for arm, cols in ARMS.items():
        t0 = time.time()
        Xa_tr = attach(X_tr, split.lap_ids_tr, extra, cols)
        Xa_ev = attach(X_ev, split.lap_ids_ev, extra, cols)

        # Canonical-seed add-ablation (the delta the floor judges).
        real_c = _sc(_fit_canon(Xa_tr), Xa_ev)
        d_real = delta(real_c, baseline, hib)

        # Permutation null at the canonical seed: capacity and information, separately.
        rng_tr = np.random.default_rng([S.RANDOM_STATE, 0])
        rng_ev = np.random.default_rng([S.RANDOM_STATE, 1])
        Xs_tr = shuffled(Xa_tr, cols, rng_tr)
        Xs_ev = shuffled(Xa_ev, cols, rng_ev)
        shuf_c = _sc(_fit_canon(Xs_tr), Xs_ev)
        capacity = delta(shuf_c, baseline, hib)
        information = delta(real_c, shuf_c, hib)

        # Paired five-seed arms for the e-value. The shuffle is redrawn per seed from a
        # stream keyed on that seed, so the five deltas are i.i.d. under H0 rather than
        # sharing one permutation draw.
        reals, shufs = [], []
        for s in E_SEEDS:
            reals.append(_sc(_fit_seed(Xa_tr, s), Xa_ev))
            r_tr = np.random.default_rng([int(s), 0])
            r_ev = np.random.default_rng([int(s), 1])
            shufs.append(_sc(_fit_seed(shuffled(Xa_tr, cols, r_tr), s),
                             shuffled(Xa_ev, cols, r_ev)))
        reals, shufs = np.asarray(reals), np.asarray(shufs)
        d_paired = np.asarray([delta(r, sh, hib) for r, sh in zip(reals, shufs)])
        ev = safe_t_e_value(d_paired)

        arm_rows[arm] = {
            "columns": list(cols), "n_columns": len(cols),
            "headline_real": real_c, "headline_shuffled": shuf_c,
            "delta_vs_baseline": d_real,
            "floor_ratio": (d_real / F2) if F2 else None,
            "clears_floor": bool(d_real > F2) if F2 else None,
            "capacity_delta": capacity,
            "capacity_floor_ratio": (capacity / F2) if F2 else None,
            "information_delta": information,
            "information_floor_ratio": (information / F2) if F2 else None,
            "information_clears_floor": bool(information > F2) if F2 else None,
            "paired_real_by_seed": reals.tolist(),
            "paired_shuffled_by_seed": shufs.tolist(),
            "paired_information_deltas": d_paired.tolist(),
            "e_value": ev,
            "seconds": round(time.time() - t0, 1),
        }
        log(f"  [{target}] {arm:<19} delta={d_real:+.8f} ({d_real/F2:+.2f}x floor) "
            f"cap={capacity:+.8f} info={information:+.8f} ({information/F2:+.2f}x) "
            f"E={ev['E']:.3g}  [{arm_rows[arm]['seconds']:.0f}s]")

    # ── Negative control: shuffle vs shuffle, on arm A's columns ────────────────
    # P's own null. Under H0 the real arm is exchangeable with a shuffle; under the
    # control BOTH sides are shuffles, so the delta is mean-zero by construction and
    # its E is an empirical check that the whole pipeline returns ~1 when nothing is
    # there. Cheap insurance against a plumbing bug reading as evidence.
    t0 = time.time()
    colsA = ARMS["A_full"]
    XA_tr = attach(X_tr, split.lap_ids_tr, extra, colsA)
    XA_ev = attach(X_ev, split.lap_ids_ev, extra, colsA)
    d_ctrl = []
    for s in E_SEEDS:
        a = _sc(_fit_seed(shuffled(XA_tr, colsA, np.random.default_rng([int(s), 0])), s),
                shuffled(XA_ev, colsA, np.random.default_rng([int(s), 1])))
        b = _sc(_fit_seed(shuffled(XA_tr, colsA, np.random.default_rng([int(s), 2])), s),
                shuffled(XA_ev, colsA, np.random.default_rng([int(s), 3])))
        d_ctrl.append(delta(a, b, hib))
    res["negative_control_shuffle_vs_shuffle"] = {
        "paired_deltas": d_ctrl,
        "e_value": safe_t_e_value(np.asarray(d_ctrl)),
        "note": ("both arms are shuffles of the same five columns, so H0 is true by "
                 "construction. A large E here would mean the harness, not the data."),
        "seconds": round(time.time() - t0, 1),
    }
    log(f"  [{target}] control(shuffle vs shuffle) "
        f"E={res['negative_control_shuffle_vs_shuffle']['e_value']['E']:.3g}")

    res["arms"] = arm_rows
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--families", nargs="*", default=list(FAMILIES))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    lines: list[str] = []

    def log(msg: str) -> None:
        print(msg, flush=True)
        lines.append(msg)

    published = json.loads(Path("ml/artefacts/evaluation_metrics.json").read_text())
    extra = hazard_frame()
    n_mask = int(extra[MASK_COL].sum())
    log(f"sc-hazard columns loaded: {extra.shape[0]} lap_ids x {extra.shape[1]} columns "
        f"({len(MART_COLS)} from the mart + the derived {MASK_COL})")
    log(f"unknowable mask: {n_mask:,} of {len(extra):,} mart rows "
        f"({100*n_mask/len(extra):.3f}%) -- expected to be exactly season 2018")

    out: dict = {
        "item": "02d",
        "ran_at": pd.Timestamp.utcnow().isoformat(),
        "contract_version": S.MODEL_VERSION_DEFAULT,
        "n_contract_features": len(S.FEATURE_COLUMNS),
        "floor_seeds": list(FLOOR_SEEDS),
        "e_value_seeds": list(E_SEEDS),
        "primary_family": PRIMARY_FAMILY,
        "secondary_families": [f for f in FAMILIES if f != PRIMARY_FAMILY],
        "e_value_construction": {
            "name": "B (paired safe-t)", "n": len(E_SEEDS), "g": E_VALUE_G,
            "family_size_sized_against": FAMILY_SIZE_SIZED_AGAINST,
            "lone_rejection_bar": LONE_REJECTION_BAR,
            "ruled_by": "09c, LANDED 2026-09-19",
        },
        "e_value_validity_check": e_value_validity_check(),
        "mask_rows": n_mask,
        "stint_life_status": ("PRIMARY family. 10d's bar discharged by 10e landing "
                              "2026-09-19; production stint_life_regressor_best_params "
                              "is S1x's, so the floor is measured against the shipping "
                              "model."),
        "floor_note": ("every floor in this run is measured FRESH. 02b's 2026-09-19 "
                       "re-score found the reseed floors moved by up to 3.2x across the "
                       "08m rebuild, so no borrowed floor is valid."),
        "confound_note": ("the NaN mask of the three rate columns is exactly "
                          "race_year == 2018. race_year is not in FEATURE_COLUMNS, so "
                          "arm B carries a free season indicator through its "
                          "missingness that the permutation null cannot fully destroy. "
                          "Arms C and D price it; see the leaf doc's decision rule."),
        "families": {},
    }
    log("e-value validity check (mean E under H0 must be 1.00):")
    for k, v in out["e_value_validity_check"].items():
        log(f"  {k:<14} mean_E={v['mean_E']:.4f} +/- {2*v['mc_se']:.4f}  "
            f"P(E>20)={v['p_E_gt_20']:.4f}")
    cap = (1.0 + len(E_SEEDS) * E_VALUE_G) ** ((len(E_SEEDS) - 1) / 2.0)
    out["e_value_construction"]["max_attainable_E"] = cap
    log(f"  max attainable E at n={len(E_SEEDS)}, g={E_VALUE_G}: {cap:.1f} "
        f"(t -> inf limit; a lone e-BH rejection at alpha=0.05 needs E >= 20*family_size)")

    # One bundle serves the whole degradation trio -- same rows, same target column,
    # same per-family mask; only the quantile alpha and the tuned params differ.
    bundles: dict[str, object] = {}
    for target in args.families:
        fam = S.TARGET_BY_NAME[target].family
        if fam not in bundles:
            bundles[fam] = E._evaluation_split(F.load_features(target=target))
        split = bundles[fam]
        log(f"\n=== {target} ({fam}){'  [PRIMARY]' if target == PRIMARY_FAMILY else ''} ===")
        out["families"][target] = run_family(
            target, split, extra, published["models"][target]["headline"], log)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, default=float))
    Path(args.out).with_suffix(".log").write_text("\n".join(lines) + "\n")
    log(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
