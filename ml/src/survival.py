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
