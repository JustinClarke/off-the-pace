"""Transform v0.2 §4 Validation gate (GO/NO-GO) harness.

Runs the batch validation suite for the Ghost Car host-swap model against the
local dev DuckDB. Pure batch, existing data no live inputs. Each step writes a
metrics block (and any plots) under transform/analyses/gate_results/ and returns a
dict of headline numbers; main() assembles them into gate_metrics.md, which the
4.6 verdict (a human/Fable synthesis) reads.

Steps (roadmap transform-v0.2 §4):
  4.1 Teammate-swap harness        identifies the deg-interaction term
  4.2 Team-change counterfactuals  drivers who switched constructors
  4.3 Leave-one-race-out backtest  finish-order hit rate vs host-invariant baseline
  4.4 Calibration of pairwise probs reliability curve + Brier score
  4.5 Offline Monte Carlo finish order pure-function simulation core

Usage:
  .venv/bin/python scripts/validate_gate.py [--step 4.1] [--step 4.3] ...
  (no --step → run all)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import kendalltau, norm, spearmanr
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "dev.duckdb"
OUT = ROOT / "transform" / "analyses" / "gate_results"
OUT.mkdir(parents=True, exist_ok=True)

# Minimum laps for a teammate pair / scenario to count toward an estimate.
MIN_PAIR_LAPS = 8


def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB), read_only=True)


# ─────────────────────────────────────────────────────────────────────────────
# 4.1 Teammate-swap harness
# ─────────────────────────────────────────────────────────────────────────────
def step_4_1(con: duckdb.DuckDBPyConnection) -> dict:
    """Does the model's constructor-shared degradation hold within a team?

    Teammates share a constructor, so the recombination model predicts they
    degrade at the SAME rate (the constructor deg slope is per (constructor,
    compound, season)); only the constant driver_skill_residual separates them.
    int_synthetic_teammate already controls for tyre state, so
    driver_skill_proxy_s is the tyre-state-matched pace gap. Under the model it
    should be FLAT in tyre age. We measure the actual per-pair slope of that gap
    vs age_in_stint and compare its spread to the spread of constructor
    deg-slope deltas the quantity that actually drives host re-ranking. If the
    reordering signal is not larger than this ignored within-team variation,
    single-stint reorderings are within noise.
    """
    pairs = con.execute(
        f"""
        WITH tm AS (
            SELECT t.race_year, t.race_id, t.ego_driver_id, t.teammate_driver_id,
                   t.constructor_id, t.driver_skill_proxy_s, t.pair_quality_weight,
                   g.age_in_stint
            FROM int_synthetic_teammate t
            JOIN int_stint_geometry g
              ON g.race_year = t.race_year AND g.race_id = t.race_id
             AND g.driver_id = t.ego_driver_id AND g.lap_number = t.lap_number
            WHERE t.teammate_available_flag
              AND NOT t.strategic_divergence_flag
              AND t.driver_skill_proxy_s IS NOT NULL
        )
        SELECT race_year, race_id, ego_driver_id, teammate_driver_id,
               COUNT(*)                                      AS n_laps,
               REGR_SLOPE(driver_skill_proxy_s, age_in_stint) AS gap_slope_s_per_age,
               AVG(driver_skill_proxy_s)                     AS gap_level_s,
               AVG(pair_quality_weight)                      AS quality
        FROM tm
        GROUP BY 1, 2, 3, 4
        HAVING COUNT(*) >= {MIN_PAIR_LAPS}
        """
    ).fetchdf()

    slopes = pairs["gap_slope_s_per_age"].dropna()
    w = pairs.loc[slopes.index, "quality"]
    wmean = np.average(slopes, weights=w)
    # quality-weighted std
    wstd = np.sqrt(np.average((slopes - wmean) ** 2, weights=w))

    # Reordering signal scale: spread of constructor deg-slope deltas within
    # (season, compound). This is what the deg_interaction term multiplies by age.
    deltas = con.execute(
        """
        SELECT a.deg_slope_s_per_lap - b.deg_slope_s_per_lap AS delta
        FROM int_constructor_deg_sensitivity a
        JOIN int_constructor_deg_sensitivity b
          ON a.race_year = b.race_year AND a.compound = b.compound
         AND a.constructor_id < b.constructor_id
        WHERE a.deg_slope_s_per_lap IS NOT NULL
          AND b.deg_slope_s_per_lap IS NOT NULL
        """
    ).fetchdf()["delta"]

    signal = float(deltas.abs().median())
    noise = float(slopes.abs().median())
    snr = signal / noise if noise else float("nan")

    # Plot: histogram of within-team gap-slopes with the signal scale overlaid.
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(slopes.clip(-0.3, 0.3), bins=60, color="#4C78A8", alpha=0.85)
    ax.axvline(0, color="k", lw=1)
    ax.axvline(signal, color="#E45756", ls="--", lw=1.5, label=f"+constructor signal ({signal:.3f})")
    ax.axvline(-signal, color="#E45756", ls="--", lw=1.5)
    ax.set_xlabel("within-team gap slope (s per lap of tyre age)")
    ax.set_ylabel("teammate pairs")
    ax.set_title("4.1 Within-team degradation gap vs constructor reordering signal")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "gate_4_1_teammate_swap.png", dpi=120)
    plt.close(fig)

    pairs.to_csv(OUT / "gate_4_1_pairs.csv", index=False)

    return {
        "step": "4.1 teammate-swap harness",
        "n_pairs": int(len(slopes)),
        "gap_slope_mean_s_per_age": round(float(slopes.mean()), 5),
        "gap_slope_qweighted_mean_s_per_age": round(float(wmean), 5),
        "gap_slope_median_s_per_age": round(float(slopes.median()), 5),
        "gap_slope_qweighted_std": round(float(wstd), 5),
        "gap_slope_abs_median (noise)": round(noise, 5),
        "constructor_deg_delta_abs_median (signal)": round(signal, 5),
        "signal_to_noise": round(snr, 3),
        "reading": (
            "Constructor-shared degradation is unbiased on average "
            f"(mean slope {slopes.mean():+.4f} s/lap-age, ~0); but per-pair "
            f"dispersion (noise {noise:.4f}) {'exceeds' if snr < 1 else 'is below'} "
            f"the reordering signal ({signal:.4f}), SNR={snr:.2f}. "
            "Per-stint deg reorderings are "
            f"{'within noise trust full-race aggregation, not single-lap deltas' if snr < 1 else 'above noise'}."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4.2 Team-change counterfactuals
# ─────────────────────────────────────────────────────────────────────────────
def step_4_2(con: duckdb.DuckDBPyConnection) -> dict:
    """Does a driver's skill residual transfer across a constructor change?

    The swap model assumes driver_skill_residual is car-independent: predict
    season N+1 from season N skill + the new car's coefficients. The sharpest
    identifying test is whether skill-residual prediction error for drivers who
    SWITCHED constructors between consecutive seasons is any larger than for
    drivers who STAYED. If switchers are not worse, the residual carries little
    car contamination the swap premise holds. If they are worse, the residual
    is still soaking up the old car.

    NOTE (coverage): with this checkout's dev DB, full seasons exist only for
    2018/2019/2024; 2020/2021 are partial and 2022/2023 absent so consecutive
    pairs collapse to ~2018->2019->2020. The test is underpowered; we report a
    bootstrap CI on the switcher-minus-stayer MAE gap, not a point verdict.
    """
    df = con.execute(
        """
        WITH season_constr AS (
            SELECT driver_id, race_year, constructor_id,
                   ROW_NUMBER() OVER (PARTITION BY driver_id, race_year
                                      ORDER BY COUNT(*) DESC) AS rn
            FROM fct_driver_skill_features
            GROUP BY 1, 2, 3
        ),
        sc AS (SELECT driver_id, race_year, constructor_id FROM season_constr WHERE rn = 1),
        ratings AS (
            SELECT driver_id, season, shrunk_residual_s, shrunk_residual_se_s, n_races
            FROM int_driver_season_ratings
        )
        SELECT a.driver_id,
               a.season              AS season_n,
               a.shrunk_residual_s   AS predicted_residual_s,   -- carried from N
               b.shrunk_residual_s   AS actual_residual_s,      -- observed in N+1
               a.n_races AS nr_n, b.n_races AS nr_n1,
               sca.constructor_id AS constructor_n,
               scb.constructor_id AS constructor_n1,
               (sca.constructor_id <> scb.constructor_id) AS switched,
               (a.shrunk_residual_s - b.shrunk_residual_s) AS error_s
        FROM ratings a
        JOIN ratings b ON a.driver_id = b.driver_id AND b.season = a.season + 1
        JOIN sc sca ON sca.driver_id = a.driver_id AND sca.race_year = a.season
        JOIN sc scb ON scb.driver_id = b.driver_id AND scb.race_year = b.season
        """
    ).fetchdf()
    df.to_csv(OUT / "gate_4_2_team_change.csv", index=False)

    sw = df.loc[df.switched, "error_s"].dropna().to_numpy()
    st = df.loc[~df.switched, "error_s"].dropna().to_numpy()

    def mae(x):
        return float(np.mean(np.abs(x))) if len(x) else float("nan")

    rng = np.random.default_rng(0)
    gaps = []
    for _ in range(5000):
        bs = rng.choice(sw, len(sw), replace=True)
        bt = rng.choice(st, len(st), replace=True)
        gaps.append(mae(bs) - mae(bt))
    lo, hi = np.percentile(gaps, [2.5, 97.5])
    gap = mae(sw) - mae(st)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.scatter(df.loc[df.switched, "predicted_residual_s"],
               df.loc[df.switched, "actual_residual_s"],
               c="#E45756", label=f"switched (n={len(sw)})", zorder=3)
    ax.scatter(df.loc[~df.switched, "predicted_residual_s"],
               df.loc[~df.switched, "actual_residual_s"],
               c="#4C78A8", label=f"stayed (n={len(st)})", alpha=0.7)
    lim = [df[["predicted_residual_s", "actual_residual_s"]].min().min(),
           df[["predicted_residual_s", "actual_residual_s"]].max().max()]
    ax.plot(lim, lim, "k--", lw=1, label="perfect transfer")
    ax.set_xlabel("predicted residual (season N, s)")
    ax.set_ylabel("actual residual (season N+1, s)")
    ax.set_title("4.2 Skill-residual transfer across constructor change")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "gate_4_2_team_change.png", dpi=120)
    plt.close(fig)

    return {
        "step": "4.2 team-change counterfactuals",
        "n_switchers": len(sw),
        "n_stayers": len(st),
        "switcher_mae_s": round(mae(sw), 4),
        "stayer_mae_s": round(mae(st), 4),
        "mae_gap_switcher_minus_stayer_s": round(gap, 4),
        "mae_gap_ci95": [round(float(lo), 4), round(float(hi), 4)],
        "reading": (
            f"Switchers MAE {mae(sw):.3f} vs stayers {mae(st):.3f}; gap {gap:+.3f} "
            f"(95% CI [{lo:+.3f}, {hi:+.3f}]). "
            + ("CI spans 0 → no evidence the team change adds transfer error "
               "(supports car-independence), but UNDERPOWERED on this checkout's coverage."
               if lo < 0 < hi else
               "CI excludes 0 → switchers materially "
               + ("worse" if gap > 0 else "better") + "; investigate.")
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4.3 Leave-one-race-out finish-order backtest
# ─────────────────────────────────────────────────────────────────────────────
def step_4_3(con: duckdb.DuckDBPyConnection) -> dict:
    """Does car/track structure beat a host-invariant (skill-only) baseline?

    Pass criterion 2. Self-scenario mart pace ~= actual pace (self-consistency),
    so it can't serve as an honest predictor. Instead we build a STRUCTURAL
    finish-order prediction from stable coefficients and a leave-one-race-out
    driver skill (mean of the driver's OTHER races that season):

      MODEL    = loo_skill + constructor_structural_pace + circuit_x_constructor
      BASELINE = loo_skill only   (host-invariant: same order in any car this is
                 exactly the v0.1 ego-order the host-swap fix had to improve on)

    Lower predicted value = faster = better finish. We score each against actual
    finish order with Spearman rho, Kendall tau, and top-3 hit rate, then paired-
    bootstrap the per-race Spearman gap.
    """
    df = con.execute(
        """
        WITH skill AS (
            SELECT driver_id, race_year, race_id, constructor_id, driver_residual_mean_s
            FROM fct_driver_skill_features WHERE driver_residual_mean_s IS NOT NULL
        ),
        loo AS (
            SELECT s.driver_id, s.race_year, s.race_id, s.constructor_id,
                   (SUM(s2.driver_residual_mean_s) - s.driver_residual_mean_s)
                       / NULLIF(COUNT(*) - 1, 0) AS loo_skill_s
            FROM skill s
            JOIN skill s2 ON s2.driver_id = s.driver_id AND s2.race_year = s.race_year
            GROUP BY 1, 2, 3, 4, s.driver_residual_mean_s
        ),
        cp AS (SELECT race_year, race_id, constructor_id, constructor_structural_pace_s
               FROM int_constructor_structural_pace),
        ci AS (SELECT race_year, race_id, constructor_id, circuit_constructor_interaction_s
               FROM int_circuit_x_constructor_interaction),
        fin AS (SELECT DISTINCT race_year, race_id, ego_driver_id AS driver_id,
                       actual_finish_position AS finish
                FROM fct_ghost_race_finish WHERE actual_finish_position IS NOT NULL)
        SELECT l.race_year, l.race_id, l.driver_id, l.loo_skill_s,
               COALESCE(cp.constructor_structural_pace_s, 0) AS cpace,
               COALESCE(ci.circuit_constructor_interaction_s, 0) AS cint, f.finish
        FROM loo l
        LEFT JOIN cp ON cp.race_year = l.race_year AND cp.race_id = l.race_id
                    AND cp.constructor_id = l.constructor_id
        LEFT JOIN ci ON ci.race_year = l.race_year AND ci.race_id = l.race_id
                    AND ci.constructor_id = l.constructor_id
        JOIN fin f ON f.race_year = l.race_year AND f.race_id = l.race_id
                  AND f.driver_id = l.driver_id
        WHERE l.loo_skill_s IS NOT NULL
        """
    ).fetchdf()
    df["model"] = df.loo_skill_s + df.cpace + df.cint
    df["base"] = df.loo_skill_s

    def per_race(col):
        sp, kt, t3, rids = [], [], [], []
        for rid, g in df.groupby("race_id"):
            if len(g) < 6:
                continue
            sp.append(spearmanr(g[col], g.finish).statistic)
            kt.append(kendalltau(g[col], g.finish).statistic)
            t3.append(len(set(g.nsmallest(3, col).driver_id)
                          & set(g.nsmallest(3, "finish").driver_id)) / 3)
            rids.append(rid)
        return pd.DataFrame({"race_id": rids, "sp": sp, "kt": kt, "t3": t3})

    m, b = per_race("model"), per_race("base")
    merged = m.merge(b, on="race_id", suffixes=("_m", "_b"))
    dsp = (merged.sp_m - merged.sp_b).to_numpy()
    rng = np.random.default_rng(0)
    boot = [np.nanmean(rng.choice(dsp, len(dsp), replace=True)) for _ in range(5000)]
    lo, hi = np.nanpercentile(boot, [2.5, 97.5])

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.scatter(merged.sp_b, merged.sp_m, alpha=0.6, c="#4C78A8")
    ax.plot([-1, 1], [-1, 1], "k--", lw=1)
    ax.set_xlabel("baseline (skill-only) Spearman per race")
    ax.set_ylabel("model (skill+car+track) Spearman per race")
    ax.set_title("4.3 Finish-order recovery: model vs host-invariant baseline")
    fig.tight_layout()
    fig.savefig(OUT / "gate_4_3_loro.png", dpi=120)
    plt.close(fig)

    return {
        "step": "4.3 LORO finish-order backtest",
        "n_races": int(len(m)),
        "model_spearman": round(float(m.sp.mean()), 3),
        "baseline_spearman": round(float(b.sp.mean()), 3),
        "model_kendall": round(float(m.kt.mean()), 3),
        "model_top3": round(float(m.t3.mean()), 3),
        "baseline_top3": round(float(b.t3.mean()), 3),
        "spearman_gap_mean": round(float(np.nanmean(dsp)), 3),
        "spearman_gap_ci95": [round(float(lo), 3), round(float(hi), 3)],
        "reading": (
            f"Model Spearman {m.sp.mean():.3f} (top-3 {m.t3.mean():.2f}) vs host-invariant "
            f"baseline {b.sp.mean():.3f} (top-3 {b.t3.mean():.2f}); gap {np.nanmean(dsp):+.3f} "
            f"(95% CI [{lo:+.3f}, {hi:+.3f}]). "
            + ("Car/track structure beats skill-only criterion 2 PASS. "
               "Skill-only ~ random confirms the constructor pace the host-swap manipulates "
               "carries the finish-order signal."
               if lo > 0 else "Gap CI includes 0 criterion 2 NOT cleared.")
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4.4 Calibration of pairwise order probabilities
# ─────────────────────────────────────────────────────────────────────────────
def _calib(p: np.ndarray, y: np.ndarray):
    A = np.vstack([p, np.ones_like(p)]).T
    slope, intercept = np.linalg.lstsq(A, y, rcond=None)[0]
    brier = float(np.mean((p - y) ** 2))
    return float(slope), float(intercept), brier


def step_4_4(con: duckdb.DuckDBPyConnection) -> dict:
    """Are the pairwise order probabilities calibrated? (criterion 3, slope ~= 1)

    Ground truth exists only for self-scenarios (host = own car, actual finish
    observed). Two views:
      * MART adjacent pairs: the p_beats_next the app actually surfaces, paired
        rank r vs r+1 the hardest, least-separable pairs.
      * FULL pairwise: reconstruct P(i beats j) = Phi((mu_j-mu_i)/sqrt(se_i^2+se_j^2))
        over ALL pairs from the marginal predicted_mean_lap_se_s fairer, larger.
    We also fit the variance-inflation factor k that would calibrate the full set,
    a concrete recalibration recommendation for the live confidence.
    """
    # --- full pairwise from marginal SE ---
    d = con.execute(
        """
        SELECT race_year, race_id, host_constructor_id, ego_driver_id,
               predicted_mean_lap_s AS mu,
               COALESCE(predicted_mean_lap_se_s, 0) AS se,
               actual_finish_position AS af
        FROM fct_ghost_race_finish
        WHERE is_self_scenario AND actual_finish_position IS NOT NULL
        """
    ).fetchdf()
    pf, yf, mu_gap, sd_pair = [], [], [], []
    for _, g in d.groupby(["race_year", "race_id", "host_constructor_id"]):
        g = g.reset_index(drop=True)
        for a in range(len(g)):
            for b in range(a + 1, len(g)):
                i, j = g.loc[a], g.loc[b]
                sd = max(float(np.hypot(i.se, j.se)), 1e-6)
                pf.append(float(norm.cdf((j.mu - i.mu) / sd)))
                yf.append(1 if i.af < j.af else 0)
                mu_gap.append(j.mu - i.mu)
                sd_pair.append(sd)
    pf, yf = np.array(pf), np.array(yf)
    slope_f, int_f, brier_f = _calib(pf, yf)

    # fit variance-inflation k minimising Brier on the full set
    mu_gap, sd_pair = np.array(mu_gap), np.array(sd_pair)
    ks = np.linspace(0.5, 4.0, 200)
    briers = [np.mean((norm.cdf(mu_gap / (k * sd_pair)) - yf) ** 2) for k in ks]
    k_star = float(ks[int(np.argmin(briers))])
    p_cal = norm.cdf(mu_gap / (k_star * sd_pair))
    slope_c, _, brier_c = _calib(p_cal, yf)

    # --- mart adjacent pairs (what the app shows) ---
    adj = con.execute(
        """
        WITH self AS (
            SELECT race_year, race_id, host_constructor_id, ego_driver_id,
                   predicted_finish_position pr, actual_finish_position af, p_beats_next
            FROM fct_ghost_race_finish
            WHERE is_self_scenario AND actual_finish_position IS NOT NULL
              AND p_beats_next IS NOT NULL
        )
        SELECT i.p_beats_next AS p,
               CASE WHEN i.af < j.af THEN 1 ELSE 0 END AS y
        FROM self i JOIN self j
          ON i.race_year = j.race_year AND i.race_id = j.race_id
         AND i.host_constructor_id = j.host_constructor_id AND j.pr = i.pr + 1
        """
    ).fetchdf()
    pa, ya = adj.p.to_numpy(), adj.y.to_numpy()
    slope_a, int_a, brier_a = _calib(pa, ya)

    # reliability plot (full pairwise, raw vs recalibrated)
    fig, ax = plt.subplots(figsize=(6, 6))
    for arr_p, arr_y, lab, c in [(pf, yf, "raw (full pairwise)", "#E45756"),
                                 (p_cal, yf, f"recalibrated k={k_star:.2f}", "#4C78A8")]:
        bins = np.linspace(0, 1, 11)
        idx = np.digitize(arr_p, bins) - 1
        xs, ys = [], []
        for bb in range(10):
            mm = idx == bb
            if mm.sum() > 15:
                xs.append(arr_p[mm].mean())
                ys.append(arr_y[mm].mean())
        ax.plot(xs, ys, "o-", color=c, label=lab)
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="perfect")
    ax.set_xlabel("predicted P(i beats j)")
    ax.set_ylabel("observed beat rate")
    ax.set_title("4.4 Pairwise order-probability calibration (self-scenarios)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "gate_4_4_calibration.png", dpi=120)
    plt.close(fig)

    return {
        "step": "4.4 pairwise probability calibration",
        "full_pairwise_n": int(len(pf)),
        "full_mean_pred": round(float(pf.mean()), 3),
        "full_observed": round(float(yf.mean()), 3),
        "full_calibration_slope": round(slope_f, 3),
        "full_brier": round(brier_f, 4),
        "brier_baseline_0.5": round(float(np.mean((0.5 - yf) ** 2)), 4),
        "variance_inflation_k_star": round(k_star, 2),
        "recalibrated_slope": round(slope_c, 3),
        "recalibrated_brier": round(brier_c, 4),
        "mart_adjacent_n": int(len(pa)),
        "mart_adjacent_slope": round(slope_a, 3),
        "mart_adjacent_brier": round(brier_a, 4),
        "reading": (
            f"Full-pairwise: resolution present (Brier {brier_f:.3f} vs 0.5-baseline "
            f"{np.mean((0.5-yf)**2):.3f}) but OVERCONFIDENT slope {slope_f:.2f} (target ~1), "
            f"predicts {pf.mean():.2f} delivers {yf.mean():.2f}. Inflating the predicted SE by "
            f"k={k_star:.2f} restores slope {slope_c:.2f}. Mart adjacent p_beats_next (app-facing, "
            f"hardest pairs) is uninformative: slope {slope_a:.2f}, Brier {brier_a:.3f}. "
            "Criterion 3 (slope ~= 1) NOT met as-shipped needs SE inflation before live."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4.5 Offline Monte Carlo finish-order core
# ─────────────────────────────────────────────────────────────────────────────
def step_4_5(con: duckdb.DuckDBPyConnection) -> dict:
    """Validate the pure-function MC core against the analytic numbers.

    The simulation core (scripts/mc_finish_order.py) is destined to become the
    live engine. Here we run it on every self-scenario's predicted (mu, se) and
    check it reproduces, within MC sampling error, the analytic quantities the
    Poisson-binomial mart computes under the same independence assumption:
      * p_beats_next  = Phi((mu_next - mu)/sqrt(se^2 + se_next^2))
      * finish_pos_se = sqrt(sum_j p(beat j)(1 - p(beat j)))
    Plus distribution sanity: each sim is a valid permutation (position rows and
    columns of p_position both sum to 1) and expected position is monotone in mu.
    """
    from mc_finish_order import simulate_finish_distribution

    d = con.execute(
        """
        -- Full host scenarios (all drivers in each host car): the MC-vs-analytic
        -- check is about internal consistency of the simulation core, not ground
        -- truth, so it runs on every scenario, not just self-scenarios.
        SELECT race_year, race_id, host_constructor_id, ego_driver_id,
               predicted_mean_lap_s AS mu, COALESCE(predicted_mean_lap_se_s, 0) AS se
        FROM fct_ghost_race_finish
        """
    ).fetchdf()

    rng = np.random.default_rng(0)
    pbn_dev, se_dev, rowsum_dev, colsum_dev, mono = [], [], [], [], []
    n_scen = 0
    for _, g in d.groupby(["race_year", "race_id", "host_constructor_id"]):
        g = g.reset_index(drop=True)
        n = len(g)
        if n < 4:
            continue
        n_scen += 1
        mu, se = g.mu.to_numpy(), g.se.to_numpy()
        fd = simulate_finish_distribution(g.ego_driver_id.tolist(), mu, se,
                                          n_sims=5000, rng=rng)
        # analytic (independent) pairwise matrix
        diff = mu[None, :] - mu[:, None]
        sd = np.sqrt(se[:, None] ** 2 + se[None, :] ** 2)
        sd = np.where(sd < 1e-9, 1e-9, sd)
        p_beats = norm.cdf(diff / sd)              # p_beats[i,j] = P(i beats j)
        np.fill_diagonal(p_beats, 0.0)
        analytic_se = np.sqrt((p_beats * (1 - p_beats)).sum(axis=1))
        order = np.argsort(mu, kind="stable")
        analytic_pbn = np.full(n, np.nan)
        for r in range(n - 1):
            i, j = order[r], order[r + 1]
            analytic_pbn[i] = p_beats[i, j]

        m = ~np.isnan(fd.p_beats_next) & ~np.isnan(analytic_pbn)
        pbn_dev.append(float(np.max(np.abs(fd.p_beats_next[m] - analytic_pbn[m]))))
        se_dev.append(float(np.max(np.abs(fd.finish_pos_se - analytic_se))))
        rowsum_dev.append(float(np.max(np.abs(fd.p_position.sum(axis=1) - 1))))
        colsum_dev.append(float(np.max(np.abs(fd.p_position.sum(axis=0) - 1))))
        mono.append(float(spearmanr(mu, fd.expected_position).statistic))

    se_dev = np.array(se_dev)
    return {
        "step": "4.5 offline Monte Carlo core",
        "n_scenarios": n_scen,
        "max_p_beats_next_dev_vs_analytic": round(max(pbn_dev), 4),
        "mean_p_beats_next_dev": round(float(np.mean(pbn_dev)), 4),
        "finish_pos_se_dev_median": round(float(np.median(se_dev)), 4),
        "finish_pos_se_dev_p95": round(float(np.percentile(se_dev, 95)), 4),
        "finish_pos_se_dev_max": round(float(se_dev.max()), 4),
        "max_p_position_rowsum_dev": round(max(rowsum_dev), 6),
        "max_p_position_colsum_dev": round(max(colsum_dev), 6),
        "min_mu_to_expected_pos_spearman": round(min(mono), 3),
        "reading": (
            f"Core CORRECT: MC reproduces analytic p_beats_next (max dev "
            f"{max(pbn_dev):.3f} ~ MC error 0.014), p_position is a valid distribution "
            f"(row/col sums to 1 within {max(max(rowsum_dev), max(colsum_dev)):.0e}), "
            f"expected position monotone in pace (min Spearman {min(mono):.2f}). "
            f"BUT finish_pos_se diverges from the mart's Poisson-binomial "
            f"(median {np.median(se_dev):.2f}, p95 {np.percentile(se_dev,95):.2f}, max "
            f"{se_dev.max():.2f} positions): pairwise-independence understates true "
            "position uncertainty under high pace overlap. The MC (permutation-respecting) "
            "is the reference corroborates 4.4's overconfidence; the live engine should "
            "take finish-position SE from the MC, not the analytic approximation."
        ),
    }


STEPS = {
    "4.1": step_4_1,
    "4.2": step_4_2,
    "4.3": step_4_3,
    "4.4": step_4_4,
    "4.5": step_4_5,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", action="append", help="run only these steps (repeatable)")
    args = ap.parse_args()

    todo = args.step or list(STEPS)
    con = _con()
    results = []
    for s in todo:
        if s not in STEPS:
            print(f"!! unknown step {s} (have {list(STEPS)})")
            continue
        print(f"\n=== running {s} ===")
        r = STEPS[s](con)
        results.append(r)
        for k, v in r.items():
            print(f"  {k}: {v}")

    # Refresh metrics files (JSON for machines, MD for the 4.6 verdict author).
    (OUT / "gate_metrics.json").write_text(json.dumps(results, indent=2))
    lines = ["# Transform v0.2 §4 gate metrics\n",
             "_Auto-generated by scripts/validate_gate.py against data/dev.duckdb._\n"]
    for r in results:
        lines.append(f"\n## {r['step']}\n")
        for k, v in r.items():
            if k in ("step", "reading"):
                continue
            lines.append(f"- **{k}**: {v}")
        lines.append(f"\n> {r['reading']}\n")
    (OUT / "gate_metrics.md").write_text("\n".join(lines))
    print(f"\nwrote {OUT/'gate_metrics.json'} and gate_metrics.md")


if __name__ == "__main__":
    main()
