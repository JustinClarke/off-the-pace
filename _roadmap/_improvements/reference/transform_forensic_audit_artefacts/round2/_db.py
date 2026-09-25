"""Shared read-only connection for round-2 probes.

Every probe imports `con()` from here. It opens data/dev.duckdb read_only and
chdirs to transform/ so the stg_* views (external globs with relative paths,
charter §2.4a) resolve. Override the warehouse with OTP_DB=/path/to.duckdb.
"""
import os
import pathlib

import duckdb


def _repo_root() -> pathlib.Path:
    """Walk up from this file to the nearest `.git`, rather than hardcoding a parent
    count (F53: a fixed `parents[N]` silently breaks the moment this artefact moves,
    the way `_roadmap/`'s consolidation already broke it once)."""
    here = pathlib.Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists():
            return candidate
    raise RuntimeError(f"no .git found walking up from {here}")


REPO = _repo_root()
DB = pathlib.Path(os.environ.get("OTP_DB", REPO / "data" / "dev.duckdb"))


def con() -> duckdb.DuckDBPyConnection:
    os.chdir(REPO / "transform")
    return duckdb.connect(str(DB), read_only=True)


def show(c, sql: str, title: str | None = None, n: int = 60) -> None:
    if title:
        print(f"\n## {title}")
    print(c.sql(sql).df().head(n).to_string(index=False))
