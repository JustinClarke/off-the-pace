"""TX-29 / HD17 guard: the holdout is 2025; no fit reads 2025 or 2026.

Planted rows prove each check fails: a seed row fitted on a window ending in 2025, and a
point-in-time cliff fit asked for 2026 (whose history would include 2025).
"""

import pandas as pd
import pytest

from tasks.coefficients import fit_compound_cliff as F
from tasks.coefficients import holdout_guard as G
from tasks.coefficients.seed_writer import SEEDS_DIR


def test_holdout_is_2025_in_dbt_and_ml():
    from ml.src import holdout_config
    assert G.holdout_season() == 2025
    assert holdout_config.HOLDOUT_SEASON == G.holdout_season()


def test_data_window_end_parses_both_forms():
    assert G.data_window_end("2018_to_2024") == 2024
    assert G.data_window_end("2018_to_2018_in_sample") == 2018
    with pytest.raises(ValueError):
        G.data_window_end("all seasons")


def test_live_cliff_seed_reads_nothing_from_the_holdout():
    seed = pd.read_csv(SEEDS_DIR / "compound_cliff_params.csv")
    assert G.rows_reading_holdout(seed) == []


def test_planted_2025_window_row_is_caught():
    seed = pd.read_csv(SEEDS_DIR / "compound_cliff_params.csv").head(3).copy()
    seed.loc[seed.index[0], "data_window"] = "2018_to_2025"
    caught = G.rows_reading_holdout(seed)
    assert len(caught) == 1 and caught[0].endswith("2018_to_2025")


def test_cliff_fit_default_seasons_stay_inside_the_guard(monkeypatch):
    seen = {}
    monkeypatch.setattr(F, "run_fit", lambda seasons, circuits, dry_run: seen.setdefault("s", seasons))
    monkeypatch.setattr(F, "write_pending", lambda *a, **k: None)
    F.main([])
    assert max(seen["s"]) <= G.holdout_season()   # the 2025 cell reads 2018-2024 only


def test_cliff_fit_refuses_a_season_after_the_holdout(monkeypatch):
    called = []
    monkeypatch.setattr(F, "run_fit", lambda *a, **k: called.append(1))
    assert F.main(["--seasons", "2024", "2026"]) == 2
    assert not called
    with pytest.raises(ValueError):
        G.check_point_in_time_seasons([2025, 2026])
    G.check_point_in_time_seasons([2018, 2024, 2025])   # 2025 cell: history 2018-2024
