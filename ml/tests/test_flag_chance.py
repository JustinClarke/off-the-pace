"""CO-08 (draft): the laps-to-flag cap and the flag-chance lookup, Python side.

The browser mirror (app/src/ml/flagChance.ts) is checked against the SAME fixture by
app/src/ml/flagChance.test.ts, so the two implementations agree by transitivity. The
fixture is regenerated with `python -m ml.src.flag_chance parity-fixture`."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from ml.src import flag_chance as FC
from ml.src import schema as S
from ml.src.export_onnx import ATOL

FIXTURE = Path("app/src/ml/__fixtures__/flag_chance_parity.json")


@pytest.fixture(scope="module")
def fixture():
    if not FIXTURE.exists():
        pytest.skip("parity fixture absent (python -m ml.src.flag_chance parity-fixture)")
    return json.loads(FIXTURE.read_text())


def test_fixture_matches_python_within_onnx_tolerance(fixture):
    lk, rows = fixture["lookup"], fixture["rows"]
    col = lambda k: np.array([r[k] for r in rows], dtype=np.float64)
    raw = FC.raw_flag_chance(col("median"), col("laps_to_flag"), lk["aft_scale"], lk["label_shift"])
    assert np.max(np.abs(raw - col("raw"))) < ATOL
    assert np.max(np.abs(FC.apply_lookup(raw, lk) - col("calibrated"))) < ATOL
    assert np.max(np.abs(FC.cap_to_flag(col("median"), col("laps_to_flag")) - col("capped_median"))) < ATOL
    assert np.max(np.abs(FC.laps_to_flag_from_fuel(col("fuel_kg"), col("burn"))
                         - col("laps_to_flag_from_fuel"))) < ATOL


def test_lookup_is_a_monotone_probability_map(fixture):
    x, y = np.asarray(fixture["lookup"]["x"]), np.asarray(fixture["lookup"]["y"])
    assert np.all(np.diff(x) > 0), "breakpoints must be strictly increasing for interpolation"
    assert np.all(np.diff(y) >= -1e-12), "the recalibration must be monotone"
    assert y.min() >= 0.0 and y.max() <= 1.0


def test_cap_is_min_and_nan_flag_means_no_cap():
    assert FC.cap_to_flag([21.3, 5.0, 8.0], [12.0, 12.0, np.nan]).tolist() == [12.0, 5.0, 8.0]


def test_laps_to_flag_from_fuel_matches_the_fuel_model():
    """int_lap_fuel_state: fuel = initial - rate * (lap - 1), rate = initial / scheduled.
    So fuel / rate - 1 = scheduled - lap: the laps still to run after this one."""
    initial, scheduled = 110.0, 57
    rate = initial / scheduled
    for lap in (1, 20, 56, 57):
        fuel = initial - rate * (lap - 1)
        assert FC.laps_to_flag_from_fuel(fuel, rate) == pytest.approx(scheduled - lap)


def test_raw_chance_is_one_half_at_the_median_and_falls_as_the_flag_recedes():
    scale = 0.75
    assert FC.raw_flag_chance(12.0, 12.0, scale) == pytest.approx(0.5)
    p = FC.raw_flag_chance(np.full(4, 12.0), [3.0, 12.0, 25.0, 60.0], scale)
    assert np.all(np.diff(p) < 0)


def test_apply_lookup_clamps_outside_the_fitted_range():
    lk = {"x": [0.2, 0.8], "y": [0.1, 0.9]}
    assert FC.apply_lookup([0.0, 0.5, 1.0], lk).tolist() == pytest.approx([0.1, 0.5, 0.9])


def test_isotonic_table_reproduces_sklearn_predict():
    from sklearn.isotonic import IsotonicRegression
    rng = np.random.default_rng(0)
    raw = rng.uniform(0, 1, 2000)
    ev = (rng.uniform(0, 1, 2000) < raw ** 0.6).astype(float)
    xs, ys = FC._fit_table(raw, ev, "isotonic")
    ir = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(raw, ev)
    probe = np.linspace(-0.1, 1.1, 301)
    assert np.allclose(FC.apply_lookup(probe, {"x": xs, "y": ys}), ir.predict(probe))


def test_ece_and_reliability_on_a_perfectly_calibrated_toy():
    rng = np.random.default_rng(1)
    p = rng.uniform(0, 1, 200_000)
    e = (rng.uniform(0, 1, p.size) < p).astype(float)
    assert FC.ece(p, e) < 0.01
    assert sum(r["n"] for r in FC.reliability(p, e, np.linspace(0, 1, 11))) == p.size


def test_predict_refuses_a_lookup_fitted_for_another_booster(tmp_path):
    from ml.src import predict as P
    bst = tmp_path / "stint_life_regressor_vX.bst"
    bst.write_bytes(b"not the booster the lookup was fitted on")
    lk = {"model_version": "vX", "booster_sha256": "0" * 64, "aft_scale": 0.75,
          "label_shift": S.AFT_LABEL_SHIFT, "x": [0.0, 1.0], "y": [0.0, 1.0]}
    path = tmp_path / "lookup.json"
    path.write_text(json.dumps(lk))
    with pytest.raises(ValueError, match="does not match"):
        P._flag_chance_columns(str(path), "vX", bst, 0.75, np.zeros(3), np.array(["a", "b", "c"]))
    lk["booster_sha256"] = hashlib.sha256(bst.read_bytes()).hexdigest()
    lk["model_version"] = "vY"
    path.write_text(json.dumps(lk))
    with pytest.raises(ValueError, match="model_version"):
        P._flag_chance_columns(str(path), "vX", bst, 0.75, np.zeros(3), np.array(["a", "b", "c"]))


def test_flag_schema_is_the_19_column_contract_plus_two():
    assert len(S.PREDICTIONS_ARROW_SCHEMA) == 19
    assert S.PREDICTIONS_ARROW_SCHEMA_WITH_FLAG.names == (
        S.PREDICTIONS_ARROW_SCHEMA.names + list(S.FLAG_CHANCE_COLUMNS))
