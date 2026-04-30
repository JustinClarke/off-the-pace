"""Provenance metadata attached to every fitted seed."""

import subprocess
from datetime import date, datetime, timezone
from pathlib import Path


def get_git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except FileNotFoundError:
        return "unknown"


def build_provenance(
    fit_method: str,
    season_min: int,
    season_max: int,
) -> dict:
    """Return a dict of provenance columns to merge into output DataFrames."""
    return {
        "fit_date": date.today().isoformat(),
        "data_window": f"{season_min}_to_{season_max}",
        "fit_method": fit_method,
        "git_sha": get_git_sha(),
        "fit_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
