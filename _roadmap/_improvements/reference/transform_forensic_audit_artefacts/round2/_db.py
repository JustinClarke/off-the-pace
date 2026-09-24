"""Shared read-only connection for round-2 probes.

Every probe imports `con()` from here. It opens data/dev.duckdb read_only and
chdirs to transform/ so the stg_* views (external globs with relative paths,
charter §2.4a) resolve. Override the warehouse with OTP_DB=/path/to.duckdb.
"""
import os
import pathlib

import duckdb

REPO = pathlib.Path(__file__).resolve().parents[4]
DB = pathlib.Path(os.environ.get("OTP_DB", REPO / "data" / "dev.duckdb"))


def con() -> duckdb.DuckDBPyConnection:
    os.chdir(REPO / "transform")
    return duckdb.connect(str(DB), read_only=True)


def show(c, sql: str, title: str | None = None, n: int = 60) -> None:
    if title:
        print(f"\n## {title}")
    print(c.sql(sql).df().head(n).to_string(index=False))
