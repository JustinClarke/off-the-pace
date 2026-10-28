"""Synthetic tests for the §12b sensitivity runs (sensitivity.py, decision record L4). No bronze file, warehouse
or pass table on disk is read."""

import numpy as np
import pandas as pd
import pytest

from tasks.wake_calibration import build_pass_table as bpt
from tasks.wake_calibration import contest as C
from tasks.wake_calibration import estimator as E
from tasks.wake_calibration import sensitivity as S
from tasks.wake_calibration.tests.test_contest import world
from tasks.wake_calibration.tests.test_estimator import _race_passes


def _raw(seed=1):
    rng = np.random.default_rng(seed)
    return pd.concat([_race_passes(2023, "r1", rng, n_drivers=4, laps=range(2, 20)),
                      _race_passes(2024, "las_vegas_grand_prix", rng, n_drivers=4, laps=range(2, 20))],
                     ignore_index=True)


def test_rereference_at_4_laps_reproduces_the_builder_exactly():
    raw = _raw()
    again = S.rereference(raw.drop(columns=S.REF_COLUMNS), bpt.REF_HALF_WINDOW_LAPS)
    pd.testing.assert_frame_equal(again[S.REF_COLUMNS], raw[S.REF_COLUMNS])


def test_rereference_window_bounds_the_donors():
    raw = _raw(2)
    for w in (2, 6):
        t = S.rereference(raw, w)
        g = t[(t["race_id"] == "2023_r1") & (t["driver"] == "D0") & (t["corner_id"] == "1")]
        for _, row in g.iterrows():
            same = g[(g["stint"] == row["stint"]) & (g["compound"] == row["compound"])]
            donors = same[same["clean"] & ((same["lap"] - row["lap"]).abs().between(1, w))]
            n = len(donors) if row["reason"] is None else 0
            assert row["ref_n"] == n
            if n >= bpt.REF_MIN_N:
                assert row["ref_time_s"] == pytest.approx(np.median(donors["seg_time_s"]))
    n2, n6 = S.rereference(raw, 2)["ref_n"].sum(), S.rereference(raw, 6)["ref_n"].sum()
    assert n2 < raw["ref_n"].sum() < n6


def test_rereferenced_table_passes_the_estimators_donor_identity_at_its_window():
    raw = _raw(3)
    cal = {(2023, "r1"): ("R1", pd.Timestamp("2023-06-01")),
           (2024, "las_vegas_grand_prix"): ("Las Vegas", pd.Timestamp("2024-11-23"))}
    p2 = E.prepare_passes(S.rereference(raw, 2), cal, half_window=2)
    assert np.isfinite(p2.loc[p2["ref_status"] == "measured", "ref_spread_s"]).all()
    with pytest.raises(E.EstimatorError):  # the ±2 table checked against ±4 donors is refused, not patched
        E.prepare_passes(S.rereference(raw, 2), cal)


def test_without_las_vegas_removes_it_from_the_fit_and_from_theta_only():
    raw = _raw(4)
    cal = {(2023, "r1"): ("R1", pd.Timestamp("2023-06-01")),
           (2024, "las_vegas_grand_prix"): ("Las Vegas", pd.Timestamp("2024-11-23"))}
    prepared = E.prepare_passes(raw, cal)
    panel = pd.DataFrame({"race_id": ["2023_r1", "2024_las_vegas_grand_prix", "2025_x"],
                          "race_year": [2023, 2024, 2025]})
    p, pan = S.variant_inputs(raw, prepared, panel, cal, S.NO_LV2024)
    assert S.lv2024_race_ids(raw) == ["2024_las_vegas_grand_prix"]
    assert "2024_las_vegas_grand_prix" not in set(p["race_key"]) and set(pan["race_id"]) == {"2023_r1", "2025_x"}
    with pytest.raises(E.EstimatorError):
        S.variant_inputs(raw, prepared, panel, cal, "reference_pm3")


def test_run_variants_end_to_end_and_report_figures_never_pass_or_fail():
    prepared, panel, cal, races = world(seed=31, races_per_season=2, n_drivers=4)
    raw = prepared[[c for c in prepared.columns if c not in
                    {"reason_wc03", "yielding", "circuit", "corner_key", "ref_spread_s", "leader_time_s",
                     "racecraft", "pass_class", "under_attack", "gap_bin", "race_key"}]]
    held = sorted(panel.loc[panel["race_year"] == 2025, "race_id"].unique())
    outs = S.run_variants(raw, prepared, panel, cal, held, n_draws=3)
    assert [o.variant for o in outs] == list(S.VARIANTS)
    for o in outs:
        assert o.result is not None or o.error
    text = " ".join(r["value"] for r in S.table2_rows(outs)).lower()
    assert " pass " not in f" {text} " and " fail " not in f" {text} "


def _fake(w1_passed):
    chk = [C.Check("W1", w1_passed, "r", "v")]
    return C.EraResult("main", None, None, None, None, None, chk, "x", "y")


def test_first_lines_only_when_w1_holds_in_the_main_run_and_not_in_a_sensitivity_run():
    outs = [S.VariantOutcome(S.REF_PM2, _fake(True)), S.VariantOutcome(S.REF_PM6, _fake(False)),
            S.VariantOutcome(S.NO_LV2024, None, "EstimatorError: x")]
    lines = S.first_lines(_fake(True), outs)
    assert len(lines) == 2 and "±6" in lines[0] and "could not be assessed" in lines[1]
    assert S.first_lines(_fake(False), outs) == []
    rows = S.table2_rows(outs)
    assert any(r["value"].startswith("— (not computed") for r in rows)
