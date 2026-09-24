"""11b · s2 — the stochastic DP over pit timing, and the three cost surfaces.

State  : (valid-lap offset within the horizon, tyre age, caution indicator).
Actions: stay / stop.  Compound-on-stop is NOT an action -- see the RESULT
         section: int_pit_strategy_cost_curve fixes next_compound to the
         realised choice, so the branch does not exist in the substrate.
Costs  : seed compound wear (int_pit_strategy_cost_curve, verbatim) + the
         unmodelled-degradation path delta + pit loss (int_pit_loss_circuit,
         already folded into the cost curve).
Stoch. : per-lap interruption hazard from int_sc_hazard_history's shrunk
         any_hazard_per_lap, carried on the cost-curve row.

Backward induction, exactly the yellow-flag extension of Carrasco Heine &
Thraves (CEJOR 2022):

    V(l, c) = min( stop_cost(l, c),  h V(l+1, 1) + (1-h) V(l+1, 0) )
    stop_cost(l, c) = A_old[l] + B_new[H-l] + bd (H-l)
                      + D_old[l] + D_new[H-l] + P (m if c else 1)

Four arms, differing ONLY in D:
    seed     D == 0                      (== the incumbent production argmin)
    model    D from the v11 p50 forecast (telescoped)
    oracle   D from the realised rho path (direct)
    clairvoyant  oracle D *and* the realised caution path known in advance

Every arm's policy is executed against the REALISED caution path and scored on
the ORACLE surface, so the regret is in seconds of race time.

Read-only.  Writes s2_stints.parquet + s2_results.json alongside.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DB = ROOT / "data" / "dev.duckdb"

TRI_K = 15                  # sum_{j=1..5} j, the detrend constant in the target
SC_PIT_MULTIPLIER = 0.5     # dbt var pit_sc_loss_multiplier
TAIL_SLOPE_LAPS = 3         # laps averaged for the persistence extrapolation


# ----------------------------------------------------------------- delta paths
def _delta_from_rho(rho: np.ndarray) -> np.ndarray:
    """Realised unmodelled degradation, delta*(u) = rho(u) - rho(1)."""
    return rho - rho[0]


def _delta_from_rho_parity(rho: np.ndarray, odd: bool) -> np.ndarray:
    """Half-sample delta: keep every other lap, interpolate onto the full grid.

    The raw realised surface is the object every arm is scored on, but an
    ORACLE chosen by minimising that same surface mines its lap-to-lap noise --
    the minimum of ~50 noisy candidates is biased low, so "regret against the
    oracle" is inflated by an amount that has nothing to do with strategy.
    Splitting the stint's laps by parity gives two surfaces with the SAME
    systematic degradation and INDEPENDENT noise: fit the oracle on one, score
    every arm on the other, and the bias is gone.
    """
    n = len(rho)
    idx = np.arange(n)
    keep = idx[(idx % 2 == 0)] if odd else idx[(idx % 2 == 1)]
    if len(keep) < 2:
        return rho - rho[0]
    v = np.interp(idx, keep, rho[keep])
    return v - v[0]


def _delta_from_forecast(j: np.ndarray, drift: float) -> np.ndarray:
    """Telescope the 5-lap cumulative-jump forecast into a level path.

    J(t) = sum_{j=1..5} (rho(t+j) - rho(t)) - 15 d, so the model's local slope
    at t is J(t)/15 + d.  delta_hat(1) = 0 by construction.
    """
    slope = j / TRI_K + drift
    out = np.zeros(len(j), dtype=float)
    out[1:] = np.cumsum(slope[:-1])
    return out


def _extend(delta: np.ndarray, n_to: int, policy: str) -> np.ndarray:
    """Extend delta past the age the tyre actually reached.

    'flat'    -- no further unmodelled degradation; the seed curve is assumed
                 correct beyond the observed age.  The conservative default:
                 it lets delta move the argmin only over ages that were run.
    'persist' -- hold the last observed slope.  Reported as a sensitivity
                 because it compounds a noisy 3-lap slope over ~20 laps.
    """
    n = len(delta)
    if n_to <= n:
        return delta[:n_to]
    if policy == "flat":
        tail = 0.0
    elif n >= TAIL_SLOPE_LAPS + 1:
        tail = float(np.mean(np.diff(delta[-(TAIL_SLOPE_LAPS + 1):])))
    elif n >= 2:
        tail = float(delta[-1] - delta[-2])
    else:
        tail = 0.0
    ext = delta[-1] + tail * np.arange(1, n_to - n + 1)
    return np.concatenate([delta, ext])


def _cum(delta: np.ndarray, n_to: int, policy: str = "flat") -> np.ndarray:
    """Cumulative sum of delta over 0..n_to laps; index k = k laps run."""
    d = _extend(delta, n_to, policy)
    return np.concatenate([[0.0], np.cumsum(d)])


# ------------------------------------------------------------------- the DP
def solve(stop_cost_green: np.ndarray, stop_cost_caution: np.ndarray,
          h: float) -> tuple[np.ndarray, np.ndarray]:
    """Backward induction over the candidate window.

    stop_cost_*[i] is the total horizon cost of stopping at candidate i.
    Returns boolean stop-policies for the green and caution states.
    """
    n = len(stop_cost_green)
    V = np.empty((n, 2))
    pol = np.zeros((n, 2), dtype=bool)
    V[n - 1, 0] = stop_cost_green[n - 1]
    V[n - 1, 1] = stop_cost_caution[n - 1]
    pol[n - 1, :] = True
    for i in range(n - 2, -1, -1):
        cont = h * V[i + 1, 1] + (1.0 - h) * V[i + 1, 0]
        for c, sc in ((0, stop_cost_green[i]), (1, stop_cost_caution[i])):
            if sc <= cont:
                V[i, c] = sc
                pol[i, c] = True
            else:
                V[i, c] = cont
    return pol[:, 0], pol[:, 1]


def execute(pol_green: np.ndarray, pol_caution: np.ndarray,
            caution: np.ndarray) -> int:
    """Walk the policy forward against the realised caution path."""
    n = len(pol_green)
    for i in range(n):
        if (pol_caution[i] if caution[i] else pol_green[i]):
            return i
    return n - 1


# ----------------------------------------------------------------- the panel
SHADOW = HERE.parent / "11a" / "panel_shadow.parquet"


def load(seasons: tuple[int, ...] | None) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    laps = pd.read_parquet(HERE / "panel_laps.parquet")
    # 11a's shadow fit (train 2018-2020) scores 2021-2024 OUT OF SAMPLE. The
    # production v11 boosters train on every season, so the `model` arm below is
    # in-sample on every row; `shadow` is the honest out-of-sample counterpart.
    if SHADOW.exists():
        sh = pd.read_parquet(SHADOW)[["lap_id", "q50", "split"]].rename(
            columns={"q50": "j_shadow", "split": "shadow_split"})
        laps = laps.merge(sh, on="lap_id", how="left")
    else:
        laps["j_shadow"] = np.nan
        laps["shadow_split"] = None
    seed = pd.read_parquet(HERE / "panel_seed_surface.parquet")
    meta = pd.read_parquet(HERE / "panel_meta.parquet")
    if seasons is not None:
        meta = meta[meta.race_year.isin(seasons)]
    lap_by_stint = {k: v for k, v in laps.groupby("stint_id", sort=False)}
    return lap_by_stint, seed, meta


def caution_windows() -> dict:
    """Per driver-race, the chronological laps that ran under SC or VSC.

    A stop between valid lap L and valid lap L+1 is discounted iff a caution
    lap falls in that gap.  Valid laps exclude SC laps by construction
    (int_stint_geometry.is_valid_lap), so the caution never lands ON a
    candidate lap -- it lands in the gap after it, which is exactly where a
    real SC stop happens.
    """
    # NOT fct_lap_residuals: that mart is already filtered to green racing laps,
    # so its is_safety_car_lap / is_vsc_lap / is_red_flag_lap columns are all
    # FALSE on all 137,447 rows. int_stint_geometry carries the full lap set
    # (162,729 rows, 8,927 SC / 2,980 VSC / 426 red-flag laps).
    con = duckdb.connect(str(DB), read_only=True)
    df = con.execute("""
        select race_year, race_id, driver_id, lap_number
        from int_stint_geometry
        where is_safety_car_lap or is_vsc_lap or is_red_flag_lap
    """).df()
    out: dict = {}
    for key, g in df.groupby(["race_year", "race_id", "driver_id"], sort=False):
        out[key] = np.sort(g.lap_number.to_numpy())
    return out


# ------------------------------------------------------------------- driver
def run(seasons: tuple[int, ...] | None, radius: int, tag: str,
        extrap: str = "flat") -> pd.DataFrame:
    lap_by_stint, seed, meta = load(seasons)
    cautions = caution_windows()
    seed_by_stint = {k: v for k, v in seed.groupby("stint_id", sort=False)}

    rows = []
    for r in meta.itertuples(index=False):
        s = seed_by_stint.get(r.stint_id)
        if s is None or r.next_stint_id not in lap_by_stint:
            continue
        old = lap_by_stint.get(r.stint_id)
        new = lap_by_stint.get(r.next_stint_id)
        if old is None or new is None:
            continue
        s = s.sort_values("L")
        H = int(s.horizon_laps.iloc[0])
        n_old = int(s.stint_valid_laps.iloc[0])
        P = float(s.pit_lane_loss_s.iloc[0])
        h = float(s.sc_hazard_per_lap.iloc[0])
        n_new = H - n_old
        if n_new < 1 or n_old < 2 or len(old) < 2 or len(new) < 2:
            continue

        # seed surface, verbatim from the production table, indexed by L
        Ls = s.L.to_numpy()
        A_old = np.full(H + 1, np.nan)
        B_new = np.full(H + 1, np.nan)
        base = np.full(H + 1, np.nan)
        A_old[Ls] = s.old_wear_cost_s.to_numpy()
        B_new[Ls] = s.new_wear_cost_s.to_numpy()
        base[Ls] = s.baseline_cost_s.to_numpy()
        cand_lap = np.full(H + 1, -1)
        cl = s.candidate_lap_number.to_numpy()
        cand_lap[Ls] = np.where(pd.isna(cl), -1, np.nan_to_num(cl, nan=-1)).astype(int)

        rho_o = old.rho.to_numpy(dtype=float)
        rho_n = new.rho.to_numpy(dtype=float)
        drift_o = float(np.nan_to_num(old.drift.iloc[0], nan=0.0))
        drift_n = float(np.nan_to_num(new.drift.iloc[0], nan=0.0))
        jo = np.nan_to_num(old.j_hat.to_numpy(dtype=float), nan=0.0)
        jn = np.nan_to_num(new.j_hat.to_numpy(dtype=float), nan=0.0)
        so = old.j_shadow.to_numpy(dtype=float)
        sn = new.j_shadow.to_numpy(dtype=float)
        has_shadow = bool(np.isfinite(so).all() and np.isfinite(sn).all())

        D = {}
        D["seed"] = (np.zeros(H + 1), np.zeros(H + 1))
        D["oracle"] = (_cum(_delta_from_rho(rho_o), H, extrap),
                       _cum(_delta_from_rho(rho_n), H, extrap))
        D["oracle_fit"] = (_cum(_delta_from_rho_parity(rho_o, True), H, extrap),
                           _cum(_delta_from_rho_parity(rho_n, True), H, extrap))
        D["oracle_eval"] = (_cum(_delta_from_rho_parity(rho_o, False), H, extrap),
                            _cum(_delta_from_rho_parity(rho_n, False), H, extrap))
        D["model"] = (_cum(_delta_from_forecast(jo, drift_o), H, extrap),
                      _cum(_delta_from_forecast(jn, drift_n), H, extrap))
        D["model_nodrift"] = (_cum(_delta_from_forecast(jo, 0.0), H, extrap),
                              _cum(_delta_from_forecast(jn, 0.0), H, extrap))
        if has_shadow:
            D["shadow_nodrift"] = (_cum(_delta_from_forecast(so, 0.0), H, extrap),
                                   _cum(_delta_from_forecast(sn, 0.0), H, extrap))

        if radius <= 0:
            lo, hi = 1, H - 1
        else:
            lo = max(1, n_old - radius)
            hi = min(H - 1, n_old + radius)
        if hi <= lo:
            continue
        cands = np.arange(lo, hi + 1)
        if np.isnan(A_old[cands]).any() or np.isnan(B_new[cands]).any():
            continue

        # realised caution availability in the gap after each candidate lap
        key = (r.race_year, r.race_id, r.driver_id)
        cl_flags = cautions.get(key, np.array([], dtype=int))
        caution = np.zeros(len(cands), dtype=bool)
        for i, L in enumerate(cands):
            a = cand_lap[L]
            b = cand_lap[L + 1] if L + 1 <= H and cand_lap[L + 1] > 0 else a + 2
            if a > 0:
                caution[i] = bool(((cl_flags > a) & (cl_flags < b)).any())

        def surface(name, cflag):
            Do, Dn = D[name]
            # B_new and base are indexed BY L (the cost curve emits them per
            # candidate row); Dn is indexed by laps run on the new set, H - L.
            fixed = A_old[cands] + B_new[cands] + base[cands] \
                + Do[cands] + Dn[H - cands]
            pit = P * np.where(cflag, SC_PIT_MULTIPLIER, 1.0)
            return fixed + pit

        # Instrument check: the production argmin, verbatim off total_cost_s.
        prod_argmin = int(s.L.to_numpy()[int(np.argmin(s.total_cost_s.to_numpy()))])

        truth = surface("oracle", caution)               # realised caution path
        truth_x = surface("oracle_eval", caution)        # held-out half-sample
        best = int(np.argmin(truth))
        best_x = int(np.argmin(truth_x))
        out = {
            "stint_id": r.stint_id, "race_year": r.race_year, "race_id": r.race_id,
            "driver_id": r.driver_id, "circuit_key": r.circuit_key,
            "end_regime": r.end_regime, "final_position": r.final_position,
            "H": H, "n_old": n_old, "n_new": n_new, "P": P, "h": h,
            "L_min": lo, "L_max": hi, "n_cand": len(cands),
            "caution_available": int(caution.sum()),
            "extrap": extrap, "radius": radius,
            "L_actual": n_old,
            "L_production_argmin": prod_argmin,
            "optimal_pit_lap_in_stint": (int(r.optimal_pit_lap_in_stint)
                                         if not pd.isna(r.optimal_pit_lap_in_stint) else -1),
            "L_clairvoyant": int(cands[best]),
            "best_cost": float(truth[best]),
            "best_cost_x": float(truth_x[best_x]),
            "cost_actual": float(truth[list(cands).index(n_old)]) if lo <= n_old <= hi else np.nan,
            "cost_actual_x": float(truth_x[list(cands).index(n_old)]) if lo <= n_old <= hi else np.nan,
        }
        arms = ["seed", "model", "model_nodrift", "oracle", "oracle_fit"]
        if has_shadow:
            arms.append("shadow_nodrift")
        out["has_shadow"] = has_shadow
        for name in arms:
            g = surface(name, np.zeros(len(cands), dtype=bool))
            c = surface(name, np.ones(len(cands), dtype=bool))
            pg, pc = solve(g, c, h)
            i = execute(pg, pc, caution)
            out[f"L_{name}"] = int(cands[i])
            out[f"regret_{name}"] = float(truth[i] - truth[best])
            out[f"regret_{name}_x"] = float(truth_x[i] - truth_x[best_x])
            # deterministic variant: hazard switched off
            pg0, pc0 = solve(g, c, 0.0)
            i0 = execute(pg0, pc0, caution)
            out[f"L_{name}_det"] = int(cands[i0])
            out[f"regret_{name}_det"] = float(truth[i0] - truth[best])
            out[f"regret_{name}_det_x"] = float(truth_x[i0] - truth_x[best_x])
        out["regret_actual"] = float(out["cost_actual"] - out["best_cost"])
        out["regret_actual_x"] = float(out["cost_actual_x"] - out["best_cost_x"])
        rows.append(out)

    df = pd.DataFrame(rows)
    df.to_parquet(HERE / f"s2_stints_{tag}.parquet", index=False)
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default="2018-2022")
    ap.add_argument("--radius", type=int, default=5)
    ap.add_argument("--tag", default="dev")
    ap.add_argument("--extrap", default="flat", choices=("flat", "persist"))
    a = ap.parse_args()
    if a.seasons == "all":
        seasons = None
    else:
        lo, hi = (int(x) for x in a.seasons.split("-"))
        seasons = tuple(range(lo, hi + 1))
    df = run(seasons, a.radius, a.tag, a.extrap)
    print(f"{a.tag}: {len(df)} stints, radius {a.radius}, extrap {a.extrap}")
    cols = [c for c in df.columns if c.startswith("regret_")]
    print(df[cols].mean().round(4).to_string())
    print("\nreproduction of the realised call (oracle DP):")
    for k in (0, 1, 2):
        print(f"  within +/-{k}: {np.mean(np.abs(df.L_oracle - df.L_actual) <= k):.4f}")


if __name__ == "__main__":
    main()
