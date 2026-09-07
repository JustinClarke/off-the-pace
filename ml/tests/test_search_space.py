"""The search space is declared once, and a search that stops on its edge says so.

`tune._suggest` used to hardcode its ranges inline, which made a boundary invisible
twice over: nothing outside the function knew what the bounds were, and a search that
ended on one printed a best value like any other. Both happened. The classifier pinned
`max_depth` and `n_estimators` at their ceilings from Phase 2 to Phase 8 (checkpoint
2026-08-25) and the quantile trio pinned `max_depth` and `min_child_weight` at theirs in
Phase 7 -- five searches, four years of seasons, and the fact reached a checkpoint only
when someone read three JSON files side by side.

So the space is data (`SEARCH_SPACE`), `_suggest` builds its suggestions from it, and
`boundary_params` reads the same dict to name what came back on an edge. The tests here
hold the two properties that makes worth having: suggestions never leave the declared
space, and the detector actually fires -- a detector that cannot fire is the silent gate
Corrections §5-§8 are about.

`boundary_params` reports; it does not fail. A pin means the optimum of the trials run
sits where the space ran out, which happens both when the learner wants more capacity
and when the optimum genuinely lives at the edge -- and only a probe past the bound
tells those apart (open item 21, measured in the 2026-08-26 checkpoint: on all five
production targets it was the second one).
"""
from __future__ import annotations

import optuna
import pytest

from ml.src import schema as S
from ml.src import tune as TU

optuna.logging.set_verbosity(optuna.logging.WARNING)

QUANTILE = S.TARGET_BY_NAME["degradation_regressor_p50"]
SURVIVAL = S.TARGET_BY_NAME["stint_life_regressor"]


def _sampled(spec, n_trials: int = 30) -> list[dict]:
    """Params from a real sampler, not a hand-built dict -- the space as searched."""
    seen: list[dict] = []
    study = optuna.create_study(sampler=optuna.samplers.RandomSampler(seed=S.RANDOM_STATE))

    def objective(trial: optuna.Trial) -> float:
        params = TU._suggest(trial, spec)
        seen.append(params)
        return float(params["max_depth"])

    study.optimize(objective, n_trials=n_trials)
    return seen


# ─── The space is what _suggest searches ────────────────────────────────────────
@pytest.mark.parametrize("spec", [QUANTILE, SURVIVAL], ids=["quantile", "survival"])
def test_suggest_returns_exactly_the_declared_keys(spec):
    assert set(TU._space_for(spec)) == set(_sampled(spec, n_trials=1)[0])


def test_the_aft_scale_is_offered_to_survival_only():
    assert "aft_loss_distribution_scale" in _sampled(SURVIVAL, n_trials=1)[0]
    assert "aft_loss_distribution_scale" not in _sampled(QUANTILE, n_trials=1)[0]


@pytest.mark.parametrize("spec", [QUANTILE, SURVIVAL], ids=["quantile", "survival"])
def test_no_suggestion_ever_leaves_the_declared_space(spec):
    space = TU._space_for(spec)
    for params in _sampled(spec):
        for name, value in params.items():
            assert space[name]["low"] <= value <= space[name]["high"], f"{name}={value}"


def test_stepped_and_log_integers_stay_integral():
    for params in _sampled(QUANTILE):
        assert isinstance(params["n_estimators"], int) and params["n_estimators"] % 100 == 0
        assert isinstance(params["min_child_weight"], int)


# ─── The detector fires, and only where it should ───────────────────────────────
def test_a_param_set_at_every_ceiling_is_named_at_every_ceiling():
    space = TU._space_for(QUANTILE)
    at_high = {name: d["high"] for name, d in space.items()}
    assert TU.boundary_params(at_high, QUANTILE) == {name: "high" for name in space}


def test_a_param_set_at_every_floor_is_named_at_every_floor():
    space = TU._space_for(QUANTILE)
    at_low = {name: d["low"] for name, d in space.items()}
    assert TU.boundary_params(at_low, QUANTILE) == {name: "low" for name in space}


def test_an_interior_param_set_is_silent():
    space = TU._space_for(QUANTILE)
    interior = {name: (d["low"] + d["high"]) / 2 for name, d in space.items()}
    interior["max_depth"], interior["n_estimators"] = 7, 500
    assert TU.boundary_params(interior, QUANTILE) == {}


def test_one_pinned_parameter_is_named_and_the_rest_are_not():
    """The shape the real searches hit: one knob on its edge, eight interior."""
    best = {"n_estimators": 500, "max_depth": TU.SEARCH_SPACE["max_depth"]["high"],
            "learning_rate": 0.05, "subsample": 0.8, "colsample_bytree": 0.8,
            "min_child_weight": 20, "reg_alpha": 0.1, "reg_lambda": 0.1, "gamma": 0.1}
    assert TU.boundary_params(best, QUANTILE) == {"max_depth": "high"}


def test_a_float_a_hair_inside_its_bound_still_counts_as_pinned():
    """A continuous suggestion never returns its bound exactly; 1e-12 inside is pinned."""
    high = TU.SEARCH_SPACE["subsample"]["high"]
    assert TU.boundary_params({"subsample": high - 1e-12}, QUANTILE) == {"subsample": "high"}
    assert TU.boundary_params({"subsample": high - 0.05}, QUANTILE) == {}


def test_the_aft_scale_is_checked_for_survival_and_ignored_elsewhere():
    scale = TU.SURVIVAL_SPACE["aft_loss_distribution_scale"]
    assert TU.boundary_params({"aft_loss_distribution_scale": scale["high"]}, SURVIVAL) \
        == {"aft_loss_distribution_scale": "high"}
    assert TU.boundary_params({"aft_loss_distribution_scale": scale["high"]}, QUANTILE) == {}


def test_params_the_space_does_not_declare_are_ignored():
    assert TU.boundary_params({"not_a_hyperparameter": 999.0}, QUANTILE) == {}


# ─── The bounds the widening moved ──────────────────────────────────────────────
def test_the_widened_bounds_are_past_every_pin_the_series_recorded():
    """Open item 21's whole subject: the five best_params that stopped on an edge.

    max_depth 8 (p50, classifier, stint-life), min_child_weight 20 (p50, p90) and
    n_estimators 700 (classifier) were the ceilings from Phase 2 to Phase 7. Each is
    now interior, which is what makes the 2026-08-26 probe's null a measurement rather
    than a restatement of the bound.
    """
    assert TU.SEARCH_SPACE["max_depth"]["high"] > 8
    assert TU.SEARCH_SPACE["min_child_weight"]["high"] > 20
    assert TU.SEARCH_SPACE["n_estimators"]["high"] > 700
