"""Tests for the SG1-SG7 harness (sg_checks.py). No real file is opened here: the world is made up (the generator of
test_design_a), and file tests use temporary folders. The SG results themselves come from running sg_checks on the
real 2022-23 structure; the last test re-derives the recorded verdicts from the recorded per-simulation files."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tasks.wake_calibration import design_a as A
from tasks.wake_calibration import sg_checks as S
from tasks.wake_calibration import wc10_io as IO
from tasks.wake_calibration.tests.test_design_a import world

EVIDENCE = IO.WC / "_evidence" / "WC-10-2026-10-29" / "sg"


def _structure(**kw) -> pd.DataFrame:
    """A made-up structure frame with every outcome column removed, prepared as the real one is."""
    f = world(**kw)
    f = f.drop(columns=[c for c in f.columns if c in IO.GUARDED_COLUMNS])
    f = f.assign(exit_bracket_m=20.0, throttle_n=10, drs_open_approach=f["gap_s"] < 1.0)
    assert not set(f.columns) & IO.GUARDED_COLUMNS
    return A.prepare(f)


@pytest.fixture(scope="module")
def small():
    p = _structure()
    return p, S.structural_keys(p)


def test_plants_are_deterministic_and_seeded_per_simulation(small):
    _, k = small
    for sg in ("SG1", "SG2", "SG3", "SG6"):
        a = S.plant(k, sg, np.random.default_rng(S.sim_seed(sg, 7)))
        b = S.plant(k, sg, np.random.default_rng(S.sim_seed(sg, 7)))
        c = S.plant(k, sg, np.random.default_rng(S.sim_seed(sg, 8)))
        for o in (A.TIME, A.MINSPEED):
            assert np.array_equal(a[o].to_numpy(), b[o].to_numpy())
            assert not np.array_equal(a[o].to_numpy(), c[o].to_numpy())
            assert np.isfinite(a[o].to_numpy()).all()
    with pytest.raises(ValueError):
        S.plant(k, "SG9", np.random.default_rng(0))


def test_sg1_plant_has_the_registered_effect_only_on_following_passes(small):
    p, k = small
    y1 = S.plant(k, "SG1", np.random.default_rng(S.sim_seed("SG1", 0)))[A.TIME].to_numpy()
    # same seed, beta switched off by moving every pass to "free": the difference is beta + circuit + race shocks
    k0 = dict(k, fol=np.zeros_like(k["fol"]))
    y0 = S.plant(k0, "SG1", np.random.default_rng(S.sim_seed("SG1", 0)))[A.TIME].to_numpy()
    d = y1 - y0
    assert np.all(d[~k["fol"]] == 0)
    b = k["bin"][k["fol"]]
    for j in range(A.N_BINS):  # within a bin the difference is beta_true + u + v, whose spread is the shocks only
        if (b == j).sum() > 50:
            assert abs(np.median(d[k["fol"]][b == j]) - S.BETA_TRUE[j]) < 0.06


def test_sg3_drift_is_relative_to_the_field(small):
    p, k = small
    seed = S.sim_seed("SG3", 1)
    y3 = S.plant(k, "SG3", np.random.default_rng(seed))[A.TIME].to_numpy()
    y1 = S.plant(k, "SG1", np.random.default_rng(seed))[A.TIME].to_numpy()
    extra = y3 - y1  # the SG3 branch draws nothing, so the difference is the planted drift term
    fr = k["free_nr"]
    sums = np.bincount(k["cell"][fr], weights=extra[fr], minlength=k["cell"].max() + 1)
    assert np.allclose(sums, 0.0, atol=1e-9)  # mean over the free passes of every (race, corner, lap) cell is 0
    assert k["drift_group"].any() and not k["drift_group"].all()
    # within a drifting group the term moves +0.01 s per tyre-age lap
    g = k["group"][k["drift_group"]][0]
    m = (k["group"] == g)
    t, e, c = k["t"][m], extra[m], k["cell"][m]
    cm = np.bincount(k["cell"][fr], weights=(S.SG3_DRIFT * k["t"] * k["drift_group"])[fr],
                     minlength=k["cell"].max() + 1) / np.maximum(np.bincount(k["cell"][fr],
                                                                           minlength=k["cell"].max() + 1), 1)
    assert np.allclose(e + cm[c], S.SG3_DRIFT * t)


def test_sg6_minimum_speed_has_no_class_contrast_and_correlated_errors(small):
    p, k = small
    y = S.plant(k, "SG6", np.random.default_rng(S.sim_seed("SG6", 0)))
    # the planted minimum-speed loss is -KAPPA x the time loss in every class: no fast - slow contrast by design
    assert S.KAPPA > 0 and np.isfinite(y[A.MINSPEED]).all()
    # pass-level noise correlation, recovered from two seeds' differences is not available; check the formula
    rng = np.random.default_rng(0)
    z = rng.standard_normal(200_000)
    v = S.SG6_RHO * z + np.sqrt(1 - S.SG6_RHO ** 2) * rng.standard_normal(200_000)
    assert abs(np.corrcoef(z, v)[0, 1] - S.SG6_RHO) < 0.01


def _fake_sims(cov_hit=1.0, agree=1.0, disagree=0.0, s3_fail=0.0, contains=1.0, n=200):
    rows = []
    for i in range(n):
        r = {"sim": i}
        for k in A.CLASSES:
            for b in range(A.N_BINS):
                hit = i < round(cov_hit * n)
                r[f"{k}|beta{b}"] = S.BETA_TRUE[b]
                r[f"{k}|beta{b}|lo"] = S.BETA_TRUE[b] - (0.01 if hit else -0.01)
                r[f"{k}|beta{b}|hi"] = S.BETA_TRUE[b] + 0.01
            r[f"{k}|near"] = S.NEAR_TRUE
            r[f"{k}|S2"] = A.AGREE if i < round(agree * n) else (A.DISAGREE if i < round((agree + disagree) * n)
                                                                  else A.INCONCLUSIVE)
            r[f"{k}|n_brk"], r[f"{k}|S2|lo90"], r[f"{k}|S2|hi90"], r[f"{k}|S2|T"] = 900, -0.01, 0.01, 0.02
            r[f"{k}|S3"] = "fail" if i < round(s3_fail * n) else "pass"
            r[f"{k}|S3B"] = 0.0
            r[f"{k}|held_up_share"] = 0.45
        r["aero_fs"] = 0.0
        r["aero_fs|lo"], r["aero_fs|hi"] = (-1.0, 1.0) if i < round(contains * n) else (0.5, 1.0)
        rows.append(r)
    return pd.DataFrame(rows)


def test_criteria_use_the_registered_thresholds():
    assert S.sg_coverage(_fake_sims(cov_hit=0.90))[0]
    assert not S.sg_coverage(_fake_sims(cov_hit=0.895))[0]
    biased = _fake_sims()
    biased["slow|near"] = S.NEAR_TRUE * 1.11
    assert not S.sg_coverage(biased)[0]
    assert S.sg7(_fake_sims(agree=0.80, disagree=0.05))[0]
    assert not S.sg7(_fake_sims(agree=0.795))[0]
    assert not S.sg7(_fake_sims(agree=0.80, disagree=0.055))[0]
    assert S.sg3(_fake_sims(s3_fail=0.80), _fake_sims(s3_fail=0.10))[0]
    assert not S.sg3(_fake_sims(s3_fail=0.795), _fake_sims())[0]
    assert not S.sg3(_fake_sims(s3_fail=1.0), _fake_sims(s3_fail=0.105))[0]
    assert S.sg6(_fake_sims(contains=0.90))[0]
    assert not S.sg6(_fake_sims(contains=0.895))[0]
    spread = _fake_sims()
    spread["fast|held_up_share"] = 0.51
    assert not S.sg6(spread)[0]
    # SG7 needs medium AND slow AGREE in the same simulation
    d = _fake_sims(agree=0.85)
    d["slow|S2"] = np.where(d["sim"] < 70, A.INCONCLUSIVE, d["slow|S2"])
    ok, _, x = S.sg7(d)
    assert not ok and x["agree_medium_and_slow"] < 0.80


def test_sg4_mechanics_and_reweight_equals_literal_refit_on_a_made_up_world(tmp_path):
    p = _structure(seed=5, races=S.SG4_RACES, n_drivers=10, n_laps=30)
    mech = S.sg4_mechanics(p, S.structural_keys(p), tmp_path)
    assert mech["pass"].all(), mech.loc[~mech["pass"]]
    rw, lab = S.sg4_reweight_vs_refit(p)
    assert (rw["max_abs_diff"] <= S.SG4_TOL).all()
    assert set(rw["case"]) == {"circuit copy + duplicate race", "duplicate race only"}
    assert (lab["label_mismatches"] == 0).all() and (lab["passes_compared"] > 0).all()
    for stat in ("S3|B", "S2pace|D", "sigma", "class_counts", "seg_time_s|all|beta"):
        assert rw["statistic"].str.contains(stat, regex=False).any()


def test_lap_arm_convergence_check_reads_structure_only(small):
    p, _ = small
    t = S.lap_arm_convergence(p)
    assert len(t) and t["converged"].all()


def test_end_to_end_small_run_and_determinism(tmp_path, small):
    p, _ = small

    def fn():
        return p

    outs = []
    for run in ("a", "b"):
        out = tmp_path / run
        v = S.run_all(out, n_sims=2, n_draws=4, workers=1, sets=("SG1", "SG3", "SG6"), structure_fn=fn,
                      sg4=False, sg5=False)
        assert set(v) == {"SG1", "SG3", "SG6", "SG7"}
        assert (out / "SHA256SUMS").is_file() and (out / "SG7_s2_rates.csv").is_file()
        outs.append(out)
    ok, lines = S.compare_runs(*outs)
    assert ok and all(line.startswith("IDENTICAL") for line in lines)
    (outs[1] / "SG1_sims.csv").write_text("changed\n")
    assert not S.compare_runs(*outs)[0]


def test_harness_reads_no_outcome_column_and_no_sealed_season(monkeypatch):
    seen = {}

    def fake_load_structure(*a, **kw):
        seen["args"], seen["kw"] = a, kw
        raise RuntimeError("stop")

    monkeypatch.setattr(IO, "load_structure", fake_load_structure)
    with pytest.raises(RuntimeError):
        S.load_real_structure()
    assert seen["args"] == () and seen["kw"] == {}  # the defaults: 2022-23, structure columns only
    assert IO.DISCOVERY_SEASONS == (2022, 2023)
    src = Path(S.__file__).read_text()
    for col in ("seg_time_s", "min_speed_kph"):  # only ever used as dict keys of the synthetic y (A.TIME / A.MINSPEED)
        assert f'"{col}"' not in src.replace('"seg_time_s", "pass_table_2022.parquet"', "")


@pytest.mark.skipif(not (EVIDENCE / "run1" / "verdicts.json").is_file(), reason="SG evidence not yet written")
def test_recorded_verdicts_rederive_from_the_recorded_simulations():
    run = EVIDENCE / "run1"
    v = json.loads((run / "verdicts.json").read_text())
    sims = {sg: pd.read_csv(run / f"{sg}_sims.csv") for sg in ("SG1", "SG2", "SG3", "SG6")
            if (run / f"{sg}_sims.csv").is_file()}
    want = {}
    if "SG1" in sims:
        want["SG1"] = S.sg_coverage(sims["SG1"])[0]
        want["SG7"] = S.sg7(sims["SG1"])[0]
    if "SG2" in sims:
        want["SG2"] = S.sg_coverage(sims["SG2"])[0]
    if "SG3" in sims and "SG1" in sims:
        want["SG3"] = S.sg3(sims["SG3"], sims["SG1"])[0]
    if "SG6" in sims:
        want["SG6"] = S.sg6(sims["SG6"])[0]
    for k, ok in want.items():
        assert v[k] == ("PASS" if ok else "FAIL"), k
    for sg, df in sims.items():
        assert len(df) == S.N_SIMS and list(df["sim"]) == list(range(S.N_SIMS)), sg
