"""TX-29 / HD17: no fit reads the holdout season (2025) or anything after it (2026).

The holdout is the dbt var ``holdout_season`` (transform/dbt_project.yml), which must match
ml/src/holdout_config.HOLDOUT_SEASON. A fit may produce a parameter for a season S only from
data before the holdout. Point-in-time fits (fit_compound_cliff: a cell for season S reads
seasons < S; 2018 reads 2018 in-sample) may therefore fit cells up to and including the
holdout season itself (the 2025 cell reads 2018-2024), and must refuse any later season.
"""

from __future__ import annotations

import re
from pathlib import Path

DBT_PROJECT = Path(__file__).resolve().parents[2] / "dbt_project.yml"


def holdout_season(path: Path = DBT_PROJECT) -> int:
    """The dbt var holdout_season, read from dbt_project.yml."""
    m = re.search(r"^\s*holdout_season:\s*(\d{4})\s*$", path.read_text(), re.MULTILINE)
    if not m:
        raise ValueError(f"holdout_season not found in {path}")
    return int(m.group(1))


def data_window_end(data_window: str) -> int:
    """Last season a seed row was fitted on: '2018_to_2024' -> 2024,
    '2018_to_2018_in_sample' -> 2018."""
    m = re.match(r"^(\d{4})_to_(\d{4})", str(data_window))
    if not m:
        raise ValueError(f"unparseable data_window: {data_window!r}")
    return int(m.group(2))


def check_point_in_time_seasons(seasons, holdout: int | None = None) -> None:
    """Raise if a point-in-time fit is asked for a season whose history reaches the holdout
    (any season after it: a 2026 cell would read 2025)."""
    holdout = holdout_season() if holdout is None else holdout
    bad = sorted(int(s) for s in seasons if int(s) > holdout)
    if bad:
        raise ValueError(
            f"seasons {bad} would be fitted on data from the holdout season {holdout} "
            f"(HD17: train on seasons before {holdout} only)")


def rows_reading_holdout(seed_rows, holdout: int | None = None) -> list[str]:
    """Seed rows (dicts or a DataFrame) whose data_window ends in or after the holdout."""
    holdout = holdout_season() if holdout is None else holdout
    if hasattr(seed_rows, "to_dict"):
        seed_rows = seed_rows.to_dict("records")
    return [f"{r.get('circuit_key')}/{r.get('compound_code')}/{r.get('season')}: {r['data_window']}"
            for r in seed_rows if data_window_end(r["data_window"]) >= holdout]
