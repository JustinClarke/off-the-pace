"""The stint-life AFT contract, in one place.

Remaining stint life is right-censored on 46.2% of training rows: a driver's last
stint of a race ends at the flag or at retirement, so the observed life is a LOWER
bound on the life the tyre had. `survival:aft` fits log(life + SHIFT) ~ Normal(mu,
scale) over an interval label, which is the only framing that can say "at least
this long" without pretending it means "exactly this long".

Everything that turns a booster margin into laps lives here -- training, batch
scoring, ONNX export and the parity checker all import it. The alternative, which
this module exists to prevent, is the failure ml_execution_plan.md flags as the
phase's headline risk: the post-transform copied into three files, applied to two
of them, passing every gate that only reads one.

The mirror of this file in the browser is app/src/ml/survival.ts. The two are held
together by verifyParity, not by hope.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import xgboost as xgb
from lifelines.utils import concordance_index
from scipy.stats import norm

from ml.src import schema as S


# ─── Label bounds ───────────────────────────────────────────────────────────────
def aft_bounds(y, is_censored) -> tuple[np.ndarray, np.ndarray]:
    """Right-censored interval labels for remaining stint life, in laps.

    Uncensored (the stint ended in a tyre change, so the life was observed):
        [y + SHIFT, y + SHIFT]   -- a point.
    Censored (the driver's last stint of the race; it ended at the flag or at
    retirement, so all we know is the tyre lasted AT LEAST this long):
        [y + SHIFT, +inf)        -- a half-line.

    SHIFT keeps the lower bound off log(0). 2,264 training rows have zero remaining
    life and 2,236 of them (98.8%) are censored -- final laps of final stints --
    so dropping them instead of shifting would delete precisely the population the
    survival framing exists to model.
    """
    lower = np.asarray(y, dtype=np.float64) + S.AFT_LABEL_SHIFT
    upper = np.where(np.asarray(is_censored, dtype=bool), np.inf, lower)
    return lower, upper


# ─── Booster → laps ─────────────────────────────────────────────────────────────
def load_booster(path: str | Path) -> xgb.Booster:
    b = xgb.Booster()
    b.load_model(str(path))
    b.feature_names = None  # positional scoring, FEATURE_COLUMNS order
    return b


def aft_params(booster: xgb.Booster) -> dict:
    """Distribution and scale, read back out of the artefact rather than out of a
    config file beside it. The scale is a term in every quantile this model emits;
    a copy of it that can drift from the booster is a defect waiting to happen."""
    cfg = json.loads(booster.save_config())
    obj = cfg["learner"]["objective"]
    if obj["name"] != "survival:aft":
        raise ValueError(f"not an AFT booster: objective={obj['name']!r}")
    p = obj["aft_loss_param"]
    return {"distribution": p["aft_loss_distribution"],
            "scale": float(p["aft_loss_distribution_scale"])}


def margin(booster: xgb.Booster, X) -> np.ndarray:
    d = xgb.DMatrix(X, missing=np.nan)
    return booster.predict(d, output_margin=True).astype(np.float64)


def laps_from_margin(m, scale: float, q: float | None = None) -> np.ndarray:
    """Margin → laps. q=None gives the median (exp(m), the log-normal's 50th
    percentile); otherwise the q-th percentile, exp(m + scale * Phi^-1(q)).
    Clipped at 0: a negative remaining life is not a thing."""
    m = np.asarray(m, dtype=np.float64)
    if q is not None:
        m = m + scale * norm.ppf(q)
    return np.clip(np.exp(m) - S.AFT_LABEL_SHIFT, 0.0, None)


def predict_laps(booster: xgb.Booster, X, scale: float,
                 q: float | None = None) -> np.ndarray:
    return laps_from_margin(margin(booster, X), scale, q)


# ─── Metrics ────────────────────────────────────────────────────────────────────
def aft_nloglik(y, pred_median, is_censored, scale: float) -> float:
    """Mean negative log-likelihood of the log-normal AFT fit, censoring included.

    Uncensored rows contribute the density at the observed life; censored rows
    contribute the survival function -log(1 - Phi(z)). That split is the whole
    point: a censored row says "at least this long" and must not be scored as if
    the tyre died on the lap the race happened to end.

    Pooled RMSE is deliberately absent. ml_headroom_ii.md #3 shows
    RMSE-on-uncensored crowns the worst model on the page, because scoring only the
    stints that ended in a tyre change scores the pit wall's selection, not the fit.
    """
    t = np.asarray(y, dtype=np.float64) + S.AFT_LABEL_SHIFT
    mu = np.log(np.maximum(np.asarray(pred_median, dtype=np.float64)
                           + S.AFT_LABEL_SHIFT, 1e-12))
    c = np.asarray(is_censored, dtype=bool)
    z = (np.log(t) - mu) / scale
    ll = np.empty_like(z)
    ll[~c] = -np.log(t[~c] * scale * np.sqrt(2.0 * np.pi)) - 0.5 * z[~c] ** 2
    ll[c] = norm.logsf(z[c])          # log P(T > t); stable in the far tail
    return float(-np.mean(ll))


def c_index(y, pred_median, is_censored) -> float:
    """Harrell's C over remaining stint life. event_observed is the negation of the
    censoring flag; a longer predicted life must rank as longer survival."""
    return float(concordance_index(np.asarray(y, dtype=np.float64),
                                   np.asarray(pred_median, dtype=np.float64),
                                   event_observed=~np.asarray(is_censored, dtype=bool)))


# ─── 10c: Cause-specific evaluation metrics ──────────────────────────────────────
def ipcw_brier(y, pred_median, is_censored, scale: float, times: np.ndarray | None = None) -> tuple[float, np.ndarray]:
    """IPCW-Brier score for censored survival data.

    Computes Brier score (mean squared error of predicted vs observed indicator)
    weighted by inverse probabilities of being censored (IPCW) at specified times.

    Args:
        y: observed times (laps)
        pred_median: predicted median remaining life (laps)
        is_censored: boolean censoring flags
        scale: AFT scale parameter
        times: time points at which to compute Brier. If None, uses deciles of y.

    Returns:
        (mean_brier, per_time_brier) where mean_brier is the IPCW-weighted mean
        and per_time_brier is a vector of Brier scores at each time.
    """
    from lifelines import KaplanMeierFitter

    y_arr = np.asarray(y, dtype=np.float64)
    pred_arr = np.asarray(pred_median, dtype=np.float64)
    cens_arr = np.asarray(is_censored, dtype=bool)

    if times is None:
        times = np.percentile(y_arr[~cens_arr], np.linspace(10, 90, 9))

    # Fit KM on censoring times to get G(t) = P(C > t)
    kmf = KaplanMeierFitter()
    kmf.fit(y_arr, event_observed=cens_arr, label="censoring")

    # Graf et al. IPCW weighting. The weight depends on the horizon t, not only on
    # the row's own time: rows with an event before t are weighted 1/G(T_i), rows
    # still at risk at t are weighted 1/G(t), and rows censored before t drop out
    # (their status at t is unknown and must not be scored as an event).
    G_MIN = 0.01  # clamp: caps any single row's weight at 100x
    g_at_own_time = np.array([max(float(kmf.predict(ti)), G_MIN) for ti in y_arr])

    mu_log = np.log(np.maximum(pred_arr + S.AFT_LABEL_SHIFT, 1e-12))

    brier_scores = []
    for t in times:
        # Predicted survival probability at time t
        z_t = (np.log(t + S.AFT_LABEL_SHIFT) - mu_log) / scale
        pred_surv = norm.sf(z_t)

        g_at_t = max(float(kmf.predict(t)), G_MIN)

        at_risk = y_arr > t                      # survived past t -> indicator 1
        event_by_t = (~cens_arr) & (y_arr <= t)   # observed event by t -> indicator 0
        # censored & y <= t: unknown at t, contributes nothing

        w = np.zeros(len(y_arr))
        w[event_by_t] = 1.0 / g_at_own_time[event_by_t]
        w[at_risk] = 1.0 / g_at_t

        contrib = np.zeros(len(y_arr))
        contrib[event_by_t] = (0.0 - pred_surv[event_by_t]) ** 2
        contrib[at_risk] = (1.0 - pred_surv[at_risk]) ** 2

        # Plain mean over all rows: dropped rows contribute 0, which is what makes
        # this consistent for the uncensored Brier score.
        brier_scores.append(float(np.mean(w * contrib)))

    return float(np.mean(brier_scores)), np.array(brier_scores)


def time_dependent_auc(y, pred_median, is_censored, scale: float, times: np.ndarray | None = None) -> tuple[float, np.ndarray]:
    """Time-dependent AUC for censored survival data.

    Computes the C-index-like AUC at specific time horizons, accounting for censoring.
    At time t, AUC measures discrimination: among pairs where one observed event by t,
    and one is still at risk at t, the model should rank the event as shorter survival.

    Args:
        y: observed times (laps)
        pred_median: predicted median remaining life (laps)
        is_censored: boolean censoring flags
        scale: AFT scale parameter
        times: time points at which to compute AUC. If None, uses deciles of y.

    Returns:
        (mean_auc, per_time_auc) where mean_auc is the mean across times
        and per_time_auc is a vector of AUC values at each time.
    """
    y_arr = np.asarray(y, dtype=np.float64)
    pred_arr = np.asarray(pred_median, dtype=np.float64)
    cens_arr = np.asarray(is_censored, dtype=bool)

    if times is None:
        times = np.percentile(y_arr[~cens_arr], np.linspace(10, 90, 9))

    auc_scores = []
    for t in times:
        # At-risk set: strictly past t, so a row sitting exactly at t cannot land in
        # both sets. The two sets are then disjoint by construction.
        at_risk = y_arr > t

        # Events by time t: uncensored and y <= t
        event_by_t = (~cens_arr) & (y_arr <= t)

        if np.sum(event_by_t) < 2 or np.sum(at_risk) < 2:
            auc_scores.append(np.nan)
            continue

        ev = pred_arr[event_by_t]
        ar = np.sort(pred_arr[at_risk])

        # Concordant when the event's predicted life is shorter than the at-risk
        # row's; ties take half credit rather than counting as discordant.
        lo = np.searchsorted(ar, ev, side="left")
        hi = np.searchsorted(ar, ev, side="right")
        n_greater = len(ar) - hi
        n_equal = hi - lo

        concordant = float(np.sum(n_greater) + 0.5 * np.sum(n_equal))
        total_pairs = float(len(ev) * len(ar))

        auc_scores.append(concordant / total_pairs if total_pairs > 0 else np.nan)

    valid_aucs = np.array([a for a in auc_scores if not np.isnan(a)])
    if len(valid_aucs) > 0:
        return float(np.mean(valid_aucs)), np.array(auc_scores)
    else:
        return np.nan, np.array(auc_scores)


def d_calibration(y, pred_median, is_censored, scale: float, n_bins: int = 5) -> dict:
    """D-calibration: expected vs observed event rates by predicted risk.

    Groups observations by predicted quantile and compares expected vs observed
    event rates (KM estimate on uncensored), accounting for censoring.

    Args:
        y: observed times (laps)
        pred_median: predicted median remaining life (laps)
        is_censored: boolean censoring flags
        scale: AFT scale parameter
        n_bins: number of risk groups

    Returns:
        dict with keys: pred_quantiles, obs_event_rates, exp_event_rates, calibration_slope
    """
    from lifelines import KaplanMeierFitter

    y_arr = np.asarray(y, dtype=np.float64)
    pred_arr = np.asarray(pred_median, dtype=np.float64)
    cens_arr = np.asarray(is_censored, dtype=bool)

    # Predicted risk at a COMMON horizon. Evaluating each row's survival curve at
    # its own predicted median gives 0.5 identically - a tautology, not a risk score.
    # The horizon has to be shared for the score to vary across rows.
    t0 = float(np.median(y_arr))
    mu_log = np.log(np.maximum(pred_arr + S.AFT_LABEL_SHIFT, 1e-12))
    z_t0 = (np.log(t0 + S.AFT_LABEL_SHIFT) - mu_log) / scale
    pred_risk = 1.0 - norm.sf(z_t0)

    # Bin by predicted risk
    bins = np.percentile(pred_risk, np.linspace(0, 100, n_bins + 1))
    bin_indices = np.digitize(pred_risk, bins) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)

    pred_quantiles = []
    obs_rates = []
    exp_rates = []

    for bin_idx in range(n_bins):
        mask = bin_indices == bin_idx
        if np.sum(mask) < 2:
            continue

        pred_quantiles.append(np.mean(pred_risk[mask]))
        exp_rates.append(np.mean(pred_risk[mask]))

        # Observed rate via KM at the SAME shared horizon t0. Using each bin's own
        # median puts every bin near KM(median)~0.5 by construction, which flattens
        # the observed axis and drags the slope toward zero.
        y_bin = y_arr[mask]
        cens_bin = cens_arr[mask]

        kmf = KaplanMeierFitter()
        kmf.fit(y_bin, event_observed=~cens_bin)
        obs_rates.append(1.0 - float(kmf.predict(t0)))

    # Calibration slope: regression of observed on expected. With no uncensored rows
    # the KM curve never drops, so every observed rate is 0 and the regression returns
    # a degenerate slope of exactly 0. That is unassessable, not calibrated - so say so.
    n_events = int(np.sum(~cens_arr))
    if n_events < 2:
        slope = np.nan
    elif len(pred_quantiles) > 2:
        from scipy.stats import linregress
        slope, intercept, r_value, p_value, std_err = linregress(exp_rates, obs_rates)
    else:
        slope = np.nan

    return {
        "pred_quantiles": np.array(pred_quantiles),
        "exp_event_rates": np.array(exp_rates),
        "obs_event_rates": np.array(obs_rates),
        "calibration_slope": slope,
    }
