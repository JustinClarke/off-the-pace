"""What the within-stint signal actually is — open item 15, opened by Phase 6.

Phase 6 proved the degradation family reaches *past* everything stint identity can
supply: `fraction_of_attainable_in_sample` is 2.84 for p50 against the exact in-sample
optimum over stint-constant predictors, so the models are provably using within-stint
variation. It did not show **what** that variation is. `push_residual` — the top SHAP
feature for p50 — is 12.9% between-stint, i.e. almost entirely a per-lap quantity, and
nothing in the series establishes whether it is carrying tyre degradation, traffic,
driver push or fuel phase. That is the difference between a tyre model and a traffic
model wearing a tyre model's name, and it is answerable with the artefacts already on
disk.

**The measurement this module adds, and why the existing one cannot answer it.**
`evaluate.ablation` *drops* a feature group and re-scores. A drop removes the group's
between-stint information and its within-stint information together, so the delta it
reports is a sum of two things the question needs separated: `dirty_air` at 0.0079 could
be the model learning that some stints run in traffic (a stint-level fact, reachable
inside the 2.9% ICC) or learning which *laps* were spent behind a car (a per-lap fact,
which is the 97.1%). The delta is identical either way.

Flattening separates them. Replace every feature in a group with its **per-stint
summary** — mean for continuous, mode for the ordinal-encoded categoricals and booleans —
and refit. The group keeps all of its between-stint information and loses exactly its
within-stint variation, so

    drop_delta(g)     = everything group g contributes
    flatten_delta(g)  = the part of it that is within-stint    <- item 15's quantity
    drop - flatten    = the part that is stint-level

Flattening is applied to train and eval alike: a model fitted on flattened columns cannot
learn to use within-stint variation it was never shown, which is what makes the delta an
information measurement rather than a distribution-shift artefact.

**Feature granularity, chosen by the data rather than by hand.** A group is the wrong unit
for the ambiguous cases — `thermal` holds `push_residual` (driver input) beside
`cumulative_push_load_*` (tyre thermal state), and those are the two hypotheses item 15
exists to tell apart. So every feature whose own between-stint share falls below
`PER_LAP_ICC_MAX` is additionally flattened alone. That set is self-selecting: a feature
that is constant within a stint has no within-stint variation to remove and flattening it
is a no-op by construction, so the threshold costs nothing but the fits it avoids.

**What a flatten result is not.** `flatten_delta` measures what the *model* uses. It does
not measure what a *feature* could supply, and on a forward-looking target the two come
apart: the per-stint mean is taken over laps 1..N, so at row t it averages laps that had
not run. A negative delta then has two readings -- "within-stint variation hurts the
model" and "knowing the rest of the stint helps" -- and nothing in the delta separates
them. `causal_stint_mean` (laps 1..t) and `future_stint_mean` (laps t..N) do, and
`flatten_causality` runs both arms for any result anyone proposes to act on. Corrections
§22 is what happens when that check is skipped: the classifier's -0.01775 thermal flatten,
recorded as a free win, is +0.00150 causally -- inside the noise floor -- while the
future-only arm is *larger* than the full-stint one. The ingredient was the future.

**The channel roll-up is interpretation, not measurement.** `CHANNELS` maps features onto
the four hypotheses in item 15's wording. It crosses the ablation groups deliberately —
that crossing is the point — but which channel a feature belongs to is a judgement about
what the sensor means, and it is recorded here so it can be argued with rather than
buried. Every number it is built from is a refit-and-rescore; only the grouping is a
claim.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from ml.src import ceiling as CE
from ml.src import schema as S

# Above this rank correlation between a column and its causal summary, a tree sees the same
# feature: XGBoost splits on global thresholds, so any globally-monotone relabelling induces
# the same partitions. The prefix mean of a counter is exactly that -- mean(1..t) = (t+1)/2 --
# so `causal_delta` for such a column is ~0 whatever its information content. Measured
# boundary: on the 2024 eval split the tyre-age channel's changed columns sit at rho
# 0.991-0.999 and every other channel's median is below 0.81, so 0.99 separates the
# counter-like channel from the rest rather than being chosen a priori.
RANK_DEGENERATE_RHO = 0.99

# A feature at or above this between-stint share is stint-constant for practical
# purposes and flattening it individually cannot move anything. Set at the boundary the
# 2026-08-24 measurement block used to call 14 of 34 features "genuinely per-lap".
PER_LAP_ICC_MAX = 0.50

# Item 15's four hypotheses, at feature granularity. A feature appears at most once;
# anything unmapped rolls up as "other" rather than being silently dropped.
#
# Phase 9 (2026-09-05) dropped 18 of the 42 feature columns (`powertrain`,
# `telemetry_cliff`, `weather_air`, `track`, `context`). This is a different taxonomy
# from `FEATURE_GROUPS` -- it regroups by physics hypothesis, not by ablation group --
# so the prune lands unevenly here: `tyre_thermal` and `driver_push` each lose members
# rather than disappearing, and `environment` loses all of them. It stays as an empty
# channel rather than being deleted, so the hypothesis it tested (conditions/identity
# carrying signal) stays visible in the taxonomy; `within_stint_ablation` skips any unit
# whose columns are empty after filtering to `X.columns`, so an empty channel is a no-op
# in the rollup, not an error.
CHANNELS: dict[str, tuple[str, ...]] = {
    # Where the stint is in its own life. Tyre-intrinsic, and the thing a degradation
    # model is *supposed* to be reading.
    "tyre_age": (
        "lap_in_stint", "age_in_stint", "laps_past_cliff", "cliff_onset_passed",
        "cliff_candidate_flag", "expected_degradation_rate_s_per_lap",
        "expected_compound_pace_s", "compound", "compound_grip_peak",
        "compound_wear_gradient", "compound_optimal_temp_low",
        "compound_optimal_temp_high", "compound_cliff_onset_laps",
        "compound_cliff_severity",
    ),
    # Accumulated thermal state of the rubber. Tyre-intrinsic, but *driven* by how the
    # car is being used -- the reason it is kept apart from tyre_age rather than merged.
    # `traction_wheelspin_proxy` and `throttle_trace_decay` (telemetry_cliff) dropped.
    "tyre_thermal": (
        "cumulative_push_load_surface", "cumulative_push_load_bulk",
        "surface_bulk_ratio",
    ),
    # What the driver did on this lap. Not tyre state: a per-lap input to it.
    # `lift_coast_share`, `mid_corner_speed_loss_kph`, `braking_point_drift_m`
    # (telemetry_cliff) and all six `powertrain` members dropped; only the thermal
    # group's `push_residual` remains.
    "driver_push": ("push_residual",),
    # Another car's wake. The competing explanation item 15 was opened to test, and
    # the channel item 15 found carries 19.7% of the within-stint signal.
    #
    # Phase 10a (2026-09-05) more than triples it: the nine `proximity` columns are
    # the same physical hypothesis (another car's wake) measured from the position
    # channel instead of from FastF1's DistanceToDriverAhead, so they belong in THIS
    # channel and not in a new one. That is a deliberate call with a consequence
    # worth naming: item 15's "traffic = 19.7%" was measured over four columns, and
    # any re-run of the attribution pass will now be measuring thirteen. The two
    # numbers are not comparable, and a future session reading a bigger traffic share
    # off a re-run should attribute it to this taxonomy change before attributing it
    # to the physics.
    "traffic": (
        "dirty_air_share_lap", "dirty_air_thermal_load_surface",
        "dirty_air_thermal_load_bulk", "air_state_dominant",
        "share_lap_within_1s", "share_lap_within_2s", "share_lap_in_train",
        "share_lap_behind_within_1s", "time_within_1s", "gap_ahead_min_s",
        "gap_ahead_median_s", "ahead_identity_stability",
        "n_distinct_cars_ahead_3s",
    ),
    # Mass burning off. A per-lap ramp that is not degradation and is trivially
    # predictable from lap number -- the classic confound for a pace-based target.
    "fuel": ("fuel_mass_kg", "lap_number"),
    # Conditions and identity. Was almost entirely stint-level; carried so the roll-up
    # was exhaustive rather than for what it showed. Phase 9 dropped every member
    # (`weather_air`, `track`, `context`) -- kept empty rather than removed, see above.
    "environment": (),
}


def channel_of(feature: str) -> str:
    for name, cols in CHANNELS.items():
        if feature in cols:
            return name
    return "other"


def unmapped_features() -> tuple[str, ...]:
    """Features in the contract that no channel claims. Expected empty; asserted by
    `ml/tests/test_attribution.py` so a 43rd feature cannot land unclassified."""
    return tuple(f for f in S.FEATURE_COLUMNS if channel_of(f) == "other")


# ─── The flatten operation ──────────────────────────────────────────────────────
def _stint_mode(s: pd.Series, stint_ids: np.ndarray) -> pd.Series:
    """Per-stint most-common value, broadcast back to rows.

    Ordinal-encoded categoricals and 0/1 booleans have no meaningful mean -- averaging
    the codes for SOFT and HARD produces MEDIUM, which is a different claim about the
    stint rather than a summary of it. The mode is the stint-constant summary that
    stays inside the column's own value set.
    """
    df = pd.DataFrame({"v": s.to_numpy(), "g": stint_ids})
    # value_counts sorts by count desc; the value-ordered tiebreak keeps this
    # deterministic across pandas versions and row orderings.
    modes = (df.dropna(subset=["v"]).groupby(["g", "v"], observed=True).size()
             .reset_index(name="n").sort_values(["g", "n", "v"], ascending=[True, False, True])
             .groupby("g", observed=True)["v"].first())
    return pd.Series(df["g"].map(modes).to_numpy(), index=s.index)


def stint_flatten(X: pd.DataFrame, stint_ids: np.ndarray,
                  cols: tuple[str, ...] | list[str]) -> pd.DataFrame:
    """Copy of `X` with `cols` replaced by their per-stint summary.

    Between-stint information is preserved exactly; within-stint variation is removed
    exactly. A column already constant within a stint comes back unchanged, which is
    what makes `flatten_delta` interpretable as a pure within-stint quantity: the
    operation has no effect at all on the part of the feature set that lives between
    stints.

    NaN is preserved as NaN where a whole stint is missing -- XGBoost's native missing
    handling is the same on both sides of the comparison, so the ablation stays like-
    for-like rather than quietly imputing on the flattened arm.
    """
    out = X.copy()
    stint_ids = np.asarray(stint_ids)
    if len(stint_ids) != len(X):
        raise ValueError(f"stint_ids ({len(stint_ids)}) must align with X ({len(X)})")
    discrete = set(S.CATEGORICAL_COLUMNS) | set(S.BOOLEAN_COLUMNS)
    for c in cols:
        if c not in out.columns:
            continue
        if c in discrete:
            out[c] = _stint_mode(out[c], stint_ids).astype(out[c].dtype)
        else:
            out[c] = (pd.Series(out[c].to_numpy(dtype=np.float64), index=out.index)
                      .groupby(stint_ids).transform("mean").to_numpy())
    return out


def flatten_is_noop(X: pd.DataFrame, Xf: pd.DataFrame, cols,
                    tol: float = 1e-9) -> bool:
    """True when flattening changed nothing -- the columns were already stint-constant.

    Reported per row of the ablation so a zero delta can be read as "no within-stint
    variation existed" rather than "the model ignored it". Those are different findings
    and the number alone does not distinguish them.

    Compared within `tol` rather than exactly: the mean of `n` identical float64 values
    sums and divides, so a genuinely stint-constant column does not come back bit-for-bit
    identical. An exact test reports every constant feature as *changed*, which inverts
    the flag's meaning on precisely the features it exists to identify.
    """
    for c in cols:
        if c not in X.columns:
            continue
        a, b = X[c].to_numpy(), Xf[c].to_numpy()
        if not np.array_equal(np.isnan(a.astype(np.float64, copy=False)),
                              np.isnan(b.astype(np.float64, copy=False))):
            return False
        if not np.allclose(a.astype(np.float64), b.astype(np.float64),
                           rtol=0, atol=tol, equal_nan=True):
            return False
    return True


# ─── Causality of the flatten: what a summary knows that a scoring row cannot ────
def _causal_mode(v: pd.Series, stint_ids: np.ndarray, order: np.ndarray) -> np.ndarray:
    """Running per-stint mode over laps 1..t, matching `_stint_mode`'s tiebreak.

    One-hot counts accumulated per stint, then argmax with values in ascending order --
    `np.argmax` returns the first maximum, which is the lowest value among the tied,
    exactly as `_stint_mode` sorts. NaN rows contribute no count and a prefix with no
    observation yet stays NaN rather than picking an arbitrary level.
    """
    arr = pd.to_numeric(v, errors="coerce").to_numpy(dtype=np.float64)[order]
    g = np.asarray(stint_ids)[order]
    levels = np.unique(arr[np.isfinite(arr)])
    if levels.size == 0:
        return np.full(len(arr), np.nan)
    codes = np.searchsorted(levels, arr)
    onehot = np.zeros((len(arr), levels.size), dtype=np.int32)
    seen = np.isfinite(arr)
    onehot[np.flatnonzero(seen), codes[seen]] = 1
    counts = pd.DataFrame(onehot).groupby(g, sort=False).cumsum().to_numpy()
    out = levels[np.argmax(counts, axis=1)].astype(np.float64)
    out[counts.sum(axis=1) == 0] = np.nan
    return out


def causal_stint_mean(X: pd.DataFrame, stint_ids: np.ndarray, lap_order: np.ndarray,
                      cols: tuple[str, ...] | list[str],
                      window: int | None = None) -> pd.DataFrame:
    """`stint_flatten`'s causal twin: the summary over laps 1..t instead of 1..N.

    `stint_flatten` is the right operation for an *information* measurement -- it removes
    within-stint variation and nothing else. It is the wrong operation for a *feature*,
    because the per-stint mean of a lap-varying column is not computable when the row is
    scored: it averages laps that have not run. On a forward-looking label that is
    look-ahead, and a negative `flatten_delta` then reads as "flattening helps" when what
    it means is "knowing the rest of the stint helps".

    This computes the same summary over the laps available at each row -- expanding when
    `window` is None, trailing `window` laps otherwise. Row 1 of a stint keeps its raw
    value (a prefix of one) and the last row equals the full-stint summary, so the two
    operations agree exactly where the future is empty and diverge everywhere else.
    """
    return _windowed_summary(X, stint_ids, lap_order, cols, window, direction="past")


def future_stint_mean(X: pd.DataFrame, stint_ids: np.ndarray, lap_order: np.ndarray,
                      cols: tuple[str, ...] | list[str]) -> pd.DataFrame:
    """The summary over laps t..N -- every lap at or after the row being scored.

    The look-ahead probe, and the arm that distinguishes the two readings of a negative
    `flatten_delta`. If a flatten wins because averaging suppresses per-lap noise, an arm
    built only from laps the row cannot see should not win. If it wins anyway -- and by
    more than the full-stint mean, on fewer laps -- the ingredient is the future.
    """
    return _windowed_summary(X, stint_ids, lap_order, cols, None, direction="future")


def _windowed_summary(X: pd.DataFrame, stint_ids: np.ndarray, lap_order: np.ndarray,
                      cols, window: int | None, direction: str) -> pd.DataFrame:
    out = X.copy()
    stint_ids = np.asarray(stint_ids)
    if len(stint_ids) != len(X) or len(lap_order) != len(X):
        raise ValueError(f"stint_ids/lap_order must align with X ({len(X)})")
    order = np.lexsort((np.asarray(lap_order, dtype=np.float64), stint_ids))
    if direction == "future":
        order = order[::-1]          # reversed within stint => a prefix is a suffix
    inv = np.empty(len(order), dtype=np.int64)
    inv[order] = np.arange(len(order))
    g = pd.Series(stint_ids[order])
    discrete = set(S.CATEGORICAL_COLUMNS) | set(S.BOOLEAN_COLUMNS)
    for c in cols:
        if c not in out.columns:
            continue
        if c in discrete:
            if direction == "future":
                raise NotImplementedError("future-arm mode is not needed and not defined")
            vals = _causal_mode(out[c], stint_ids, order)
        else:
            v = pd.Series(out[c].to_numpy(dtype=np.float64)[order])
            gb = v.groupby(g, sort=False)
            sm = (gb.expanding().mean() if window is None
                  else gb.rolling(window, min_periods=1).mean())
            vals = sm.reset_index(level=0, drop=True).sort_index().to_numpy()
        out[c] = vals[inv].astype(out[c].dtype)
    return out


def rank_preservation(X: pd.DataFrame, Xt: pd.DataFrame,
                      cols: tuple[str, ...] | list[str]) -> dict:
    """How much of a column's ordering survives a transform -- the causal arm's own null check.

    A `causal_delta` of zero has two readings and they are not the same finding: "the past
    supplies what the model was using", or "the transform did not change the feature a tree
    can see". The second happens whenever the summary is a monotone relabelling, which is
    the normal case for counters and cumulative sums -- and `tyre_age` is made of those.

    Reported per column as Spearman(raw, transformed) over the rows where both are finite,
    with columns the transform left identical excluded: those are already flagged as
    `flatten_is_noop` and would drag the median to 1.0 for the wrong reason.
    """
    from scipy.stats import spearmanr

    rho: dict[str, float] = {}
    for c in cols:
        if c not in X.columns or c not in Xt.columns:
            continue
        a = pd.to_numeric(X[c], errors="coerce").to_numpy(dtype=np.float64)
        b = pd.to_numeric(Xt[c], errors="coerce").to_numpy(dtype=np.float64)
        m = np.isfinite(a) & np.isfinite(b)
        if m.sum() < 10 or np.std(a[m]) == 0 or np.std(b[m]) == 0:
            continue
        if np.allclose(a[m], b[m], rtol=0, atol=1e-9):
            continue                      # unchanged: a no-op, not a relabelling
        r = spearmanr(a[m], b[m]).statistic
        if np.isfinite(r):
            rho[c] = float(r)
    if not rho:
        return {"per_column": {}, "median": None, "max": None,
                "degenerate": None, "n_changed_columns": 0,
                "note": "the transform changed no column with usable variance"}
    vals = np.asarray(list(rho.values()))
    return {
        "per_column": dict(sorted(rho.items(), key=lambda kv: kv[1])),
        "median": float(np.median(vals)), "max": float(vals.max()),
        "n_changed_columns": len(rho),
        "degenerate": bool(np.median(vals) >= RANK_DEGENERATE_RHO),
        "note": ("Spearman(raw, causal) over the columns the transform actually changed. "
                 f"A median at or above {RANK_DEGENERATE_RHO} means the causal summary is a "
                 "near-monotone relabelling and a tree sees nearly the same feature, so a "
                 "null causal_delta is arithmetic rather than evidence."),
    }


def flatten_causality(fit: Callable, score: Callable,
                      X_tr: pd.DataFrame, y_tr: np.ndarray,
                      stint_tr: np.ndarray, lap_tr: np.ndarray,
                      X_ev: pd.DataFrame, y_ev: np.ndarray,
                      stint_ev: np.ndarray, lap_ev: np.ndarray,
                      higher_is_better: bool, cols: tuple[str, ...],
                      base: float, flatten_delta: float,
                      *, noise: float | None = None) -> dict:
    """Is a flatten result reachable by a feature, or does it need the stint's future?

    Three deltas against the same reference, oriented like every other delta here
    (positive = the model got worse without it):

        flatten_delta  -- laps 1..N   (measured upstream; passed in, not refitted)
        causal_delta   -- laps 1..t   the most a scoring-time feature could recover
        future_delta   -- laps t..N   the look-ahead probe

    `lookahead_share` is the part of the flatten effect that no feature can reach. A row
    with `causally_reachable: false` is a finding about the target, not an action: it
    says the summary carries information about laps that have not run, which for a
    forward-looking label is what the label is made of.
    """
    def _delta(val: float) -> float:
        return (base - val) if higher_is_better else (val - base)

    cont = tuple(c for c in cols if c not in set(S.CATEGORICAL_COLUMNS) | set(S.BOOLEAN_COLUMNS))
    Xc_tr = causal_stint_mean(X_tr, stint_tr, lap_tr, cols)
    Xc_ev = causal_stint_mean(X_ev, stint_ev, lap_ev, cols)
    rank = rank_preservation(X_ev, Xc_ev, cols)
    causal = _delta(score(y_ev, fit(Xc_tr, y_tr), Xc_ev))
    future = None
    if cont:
        future = _delta(score(y_ev, fit(future_stint_mean(X_tr, stint_tr, lap_tr, cont), y_tr),
                              future_stint_mean(X_ev, stint_ev, lap_ev, cont)))
    share = (None if abs(flatten_delta) < 1e-12
             else float((flatten_delta - causal) / flatten_delta))
    return {
        "flatten_delta": float(flatten_delta),
        "causal_delta": float(causal),
        "future_delta": None if future is None else float(future),
        "lookahead_share": share,
        "causal_inside_noise": (None if noise is None else bool(abs(causal) < noise)),
        # Withheld, not guessed, when the causal arm barely changed the feature a tree
        # sees: on a degenerate arm the delta is ~0 by construction and a verdict read off
        # it would be the artefact stated as a finding.
        "causally_reachable": (
            None if noise is None or rank.get("degenerate") else
            bool(abs(causal) > noise and np.sign(causal) == np.sign(flatten_delta))),
        "causal_rank_preservation": rank,
        "n_future_only_features": len(cont),
        "note": ("causal_delta repeats the flatten over laps 1..t only. A flatten that "
                 "clears the floor while its causal twin does not is not a feature "
                 "change that can be shipped: the summary is reading laps that had not "
                 "run. future_delta says which way -- if it exceeds flatten_delta on "
                 "strictly later laps, the ingredient is the future rather than the "
                 "larger sample. Read causal_rank_preservation first: on a degenerate "
                 "arm (a counter, whose prefix mean is a monotone relabelling) the causal "
                 "delta is ~0 by construction and carries no verdict."),
    }


# ─── Between/within decomposition by refit ──────────────────────────────────────
def within_stint_ablation(
    fit: Callable, score: Callable,
    X_tr: pd.DataFrame, y_tr: np.ndarray, stint_tr: np.ndarray,
    X_ev: pd.DataFrame, y_ev: np.ndarray, stint_ev: np.ndarray,
    higher_is_better: bool,
    units: dict[str, tuple[str, ...]],
    *, feature_icc: dict[str, float] | None = None,
    drop: bool = True,
) -> list[dict]:
    """Drop-vs-flatten for each unit of features. `units` is {name: columns}.

    `fit(X, y)` and `score(y, pred_from(X))` are passed in rather than a model, so the
    same arithmetic serves pinball, macro-F1 and censored AFT NLL -- the module never
    learns which metric it is holding. Deltas are oriented so **positive always means
    the model got worse without it**, i.e. positive = the unit was carrying something.

    `flatten_share` is the headline: the fraction of a unit's total contribution that is
    within-stint. It is only defined where the drop delta is meaningfully non-zero, and
    it is deliberately left null rather than reported as a ratio of two numbers that are
    both inside noise.

    `drop=False` runs the flatten arm only, halving the refits. Used for the per-feature
    pass, where the within-stint delta is the quantity item 15 asked for and a
    single-feature drop delta mostly re-reports what the group-level ablation already
    measured -- at 10 s a fit, that is the difference between a command someone runs and
    one they do not.
    """
    def _delta(val: float, base: float) -> float:
        return (base - val) if higher_is_better else (val - base)

    full = fit(X_tr, y_tr)
    base = score(y_ev, full, X_ev)
    rows: list[dict] = [{"unit": "<none>", "kind": "reference", "headline": base,
                         "drop_delta": 0.0, "flatten_delta": 0.0, "flatten_share": None,
                         "flatten_is_noop": False, "n_features": len(X_tr.columns)}]

    for name, cols in units.items():
        cols = tuple(c for c in cols if c in X_tr.columns)
        if not cols:
            continue
        keep = [c for c in X_tr.columns if c not in cols]
        drop_delta = None
        if drop and keep:  # dropping every column is not a model
            m = fit(X_tr[keep], y_tr)
            drop_delta = _delta(score(y_ev, m, X_ev[keep]), base)

        Xf_tr = stint_flatten(X_tr, stint_tr, cols)
        Xf_ev = stint_flatten(X_ev, stint_ev, cols)
        noop = flatten_is_noop(X_tr, Xf_tr, cols)
        mf = fit(Xf_tr, y_tr)
        flatten_delta = _delta(score(y_ev, mf, Xf_ev), base)

        share = None
        if drop_delta is not None and abs(drop_delta) > 1e-9 and drop_delta > 0:
            share = float(flatten_delta / drop_delta)
        rows.append({
            "unit": name,
            "kind": "group" if name in S.FEATURE_GROUPS else "feature",
            "headline": base + (flatten_delta if higher_is_better is False else -flatten_delta),
            "drop_delta": None if drop_delta is None else float(drop_delta),
            "flatten_delta": float(flatten_delta),
            "flatten_share": share,
            "flatten_is_noop": bool(noop),
            "n_features": len(cols),
            "between_stint_share": (None if feature_icc is None else
                                    feature_icc.get(name)),
        })
    return rows


def refit_noise_floor(fit_seeded: Callable[[int], object], score: Callable,
                      X_ev: pd.DataFrame, y_ev: np.ndarray,
                      seeds: tuple[int, ...]) -> dict:
    """How much the headline moves when only the seed changes. The denominator for
    every delta in this module.

    A `flatten_delta` is a difference between two independently-seeded fits, so the
    quantity it must clear is not the headline's own sd but the sd of a *difference* of
    two of them: `sqrt(2) * sd`. `delta_noise_2sd` is two of those, and any delta inside
    it is reported as inside noise rather than as a finding.

    This exists because the alternative is the exact failure Corrections §15 catalogues
    one level down: Phase 6 put intervals on every `beats_baseline` claim, and it would be
    absurd for the phase that reads *why* those models win to ship point estimates with
    nothing under them.
    """
    vals = [float(score(y_ev, fit_seeded(int(s)), X_ev)) for s in seeds]
    a = np.asarray(vals, dtype=np.float64)
    sd = float(a.std(ddof=1)) if len(a) > 1 else 0.0
    return {"n_seeds": len(vals), "headline_by_seed": vals,
            "headline_mean": float(a.mean()), "headline_sd": sd,
            "headline_min": float(a.min()), "headline_max": float(a.max()),
            "delta_noise_1sd": float(np.sqrt(2.0) * sd),
            "delta_noise_2sd": float(2.0 * np.sqrt(2.0) * sd),
            "note": ("seed-only refits of the unmodified feature set. A delta smaller "
                     "than delta_noise_2sd is not distinguishable from reseeding the "
                     "same model.")}


def annotate_noise(rows: list[dict], delta_noise_2sd: float | None) -> list[dict]:
    """Mark each ablation row against the refit noise floor, in place."""
    for r in rows:
        for k in ("drop_delta", "flatten_delta"):
            v = r.get(k)
            r[f"{k[:-len('delta')]}inside_noise"] = (
                None if v is None or delta_noise_2sd is None
                else bool(abs(v) < delta_noise_2sd))
    return rows


def per_lap_features(X: pd.DataFrame, stint_ids: np.ndarray,
                     icc_max: float = PER_LAP_ICC_MAX) -> dict[str, float]:
    """{feature: between-stint share} for features with genuine within-stint variation.

    Uses the same corrected ANOVA estimator Phase 6 put under the target, so a feature's
    share and the target's share are the same statistic and can be read side by side.
    Constant-within-stint features are excluded because flattening them is provably a
    no-op -- this is the cost control that keeps the feature-level pass to ~14 refits
    instead of 42.
    """
    out: dict[str, float] = {}
    for c in X.columns:
        v = pd.to_numeric(X[c], errors="coerce").to_numpy(dtype=np.float64)
        if not np.isfinite(v).any() or np.nanstd(v) == 0:
            continue
        vc = CE.variance_components(v, stint_ids)
        if vc is not None and vc.share < icc_max:
            out[c] = float(vc.share)
    return out


def prediction_variance_split(pred: np.ndarray, y: np.ndarray,
                              stint_ids: np.ndarray) -> dict:
    """ICC of the model's own output beside the ICC of what it is predicting.

    The single most direct read on item 15 and it needs no refit: if the predictions were
    stint-constant their share would be 1.0. Whatever it actually is, it is the share of
    the model's *output* variance that lives between stints, and comparing it to the
    target's share says whether the model is spending its variance where the target keeps
    its own.
    """
    vp = CE.variance_components(np.asarray(pred, dtype=np.float64), stint_ids)
    vy = CE.variance_components(np.asarray(y, dtype=np.float64), stint_ids)
    if vp is None or vy is None:
        return {"error": "insufficient groups for a variance decomposition"}
    return {
        "prediction_between_stint_share": vp.share,
        "target_between_stint_share": vy.share,
        "prediction_sd": vp.sd, "target_sd": vy.sd,
        "ratio": (float(vp.share / vy.share) if vy.share > 0 else None),
        "note": ("1.0 would mean the model never varies its answer inside a stint. The "
                 "target's share is the corrected ANOVA ICC, the same estimator, so the "
                 "two are directly comparable."),
    }


def channel_rollup(feature_rows: list[dict]) -> list[dict]:
    """Sum the feature-level within-stint deltas into item 15's four hypotheses.

    Additive on `flatten_delta` and it should be read as indicative: the features inside
    a channel are correlated, so the parts do not sum to what flattening the whole
    channel at once would give. `evaluate` runs the channels as units in their own right
    for exactly that reason -- this roll-up is the cheap view, the channel-as-unit row is
    the measured one.
    """
    agg: dict[str, dict] = {}
    for r in feature_rows:
        if r["kind"] != "feature":
            continue
        ch = channel_of(r["unit"])
        a = agg.setdefault(ch, {"channel": ch, "flatten_delta_sum": 0.0,
                                "features": [], "n_noop": 0})
        a["flatten_delta_sum"] += float(r["flatten_delta"])
        a["features"].append(r["unit"])
        a["n_noop"] += int(bool(r["flatten_is_noop"]))
    rows = sorted(agg.values(), key=lambda a: -a["flatten_delta_sum"])
    total = sum(max(a["flatten_delta_sum"], 0.0) for a in rows)
    for a in rows:
        a["share_of_within_stint"] = (
            float(max(a["flatten_delta_sum"], 0.0) / total) if total > 0 else None)
        a["features"] = sorted(a["features"])
    return rows
