"""AX-05: qv_* views and catalogue.json.

Synthetic tests (always run): deny-list (planted *_component_s column fails), schema/type mismatch,
size gate, catalogue_version.
Scratch-export tests (run when AX05_EXPORT points at an export root made with
`export_app_data.py --db <scratch>/dev.duckdb --out <dir>`; skipped otherwise): schema vs catalogue,
deny-list over the real views, size gate, determinism (two builds, sha256 per file), required filters.
Nothing in the Makefile runs these yet.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

import duckdb
import pytest

import assistant_query_views as aqv

EXPORT = os.environ.get("AX05_EXPORT")
needs_export = pytest.mark.skipif(not EXPORT or not Path(EXPORT, "_manifest.json").exists(),
                                  reason="set AX05_EXPORT to a scratch export root")


def _toy_source(root: Path) -> list[dict]:
    p = root / "facts" / "toy.parquet"
    p.parent.mkdir(parents=True)
    duckdb.execute(
        f"COPY (SELECT * FROM (VALUES (2024, 'VER', 81.2::DOUBLE, 0.4::DOUBLE), (2024, 'HAM', 81.9::DOUBLE, 0.1::DOUBLE)) "
        f"t(race_year, driver_id, lap_time_s, fuel_component_s)) TO '{p}' (FORMAT PARQUET)"
    )
    return [{"name": "toy", "path": "/data/facts/toy.parquet", "partitioned": False}]


def _toy_view(sql: str, columns: list[dict]) -> dict:
    return {"name": "qv_toy", "grain": "lap", "note": "", "sources": ["toy"], "partition": None,
            "count_name": "laps", "required_filters": ["season"], "group_by_requires": {},
            "default_filters": [], "max_seasons": None, "sql": sql, "columns": columns}


GOOD_COLS = [aqv.SEASON, aqv.DRIVER, aqv.meas("lap_time_s", "number", "lap time")]
GOOD_SQL = "SELECT race_year AS season, driver_id, lap_time_s FROM toy"


def test_toy_view_builds_and_catalogue_versions(tmp_path):
    entries = _toy_source(tmp_path)
    out = aqv.export_query_views(tmp_path, entries, [], views=[_toy_view(GOOD_SQL, GOOD_COLS)], progress=lambda m: None)
    assert out[0]["path"] == "/data/assistant/qv/qv_toy.parquet"
    cat = json.loads((tmp_path / "assistant" / "catalogue.json").read_text())
    version = cat.pop("catalogue_version")
    assert version == hashlib.sha256(aqv.canonical_bytes(cat)).hexdigest()
    assert cat["seasons"] == [2024]


def test_planted_component_column_fails_deny_list(tmp_path):
    entries = _toy_source(tmp_path)
    cols = GOOD_COLS + [aqv.meas("fuel_component_s", "number", "planted")]
    view = _toy_view(GOOD_SQL.replace("lap_time_s FROM", "lap_time_s, fuel_component_s FROM"), cols)
    with pytest.raises(ValueError, match="denied"):
        aqv.export_query_views(tmp_path, entries, [], views=[view], progress=lambda m: None)


@pytest.mark.parametrize("name", [
    "fuel_component_s", "driver_skill_residual_s", "rating_s", "predicted_finish_position", "dirty_air_tax_s",
    "dirty_air_tax_se_s", "cumulative_dirty_air_tax_race_s", "cumulative_dirty_air_tax_s", "sc_hazard_per_lap",
    "sc_hazard_per_lap_shrunk", "tyre_management_score", "cliff_lap_in_stint", "teammate_gap_s",
    "pit_lane_loss_s", "pit_decision_class", "strategy_verdict", "ci_low",
])
def test_deny_patterns_catch_modelled_names(name):
    assert aqv.denied_columns([name]) == [name]


def test_deny_patterns_pass_every_catalogue_column():
    names = [c["name"] for v in aqv.VIEWS for c in v["columns"]]
    assert aqv.denied_columns(names) == []


def test_catalogue_mismatch_fails(tmp_path):
    entries = _toy_source(tmp_path)
    cols = [aqv.SEASON, aqv.DRIVER, aqv.meas("lap_time_s", "integer", "wrong type")]
    with pytest.raises(ValueError, match="type"):
        aqv.export_query_views(tmp_path, entries, [], views=[_toy_view(GOOD_SQL, cols)], progress=lambda m: None)
    with pytest.raises(ValueError, match="catalogue columns"):
        aqv.export_query_views(tmp_path, entries, [], views=[_toy_view(GOOD_SQL, GOOD_COLS[:2])], progress=lambda m: None)


def test_size_gate(tmp_path, monkeypatch):
    entries = _toy_source(tmp_path)
    monkeypatch.setattr(aqv, "MAX_FILE_BYTES", 10)
    with pytest.raises(ValueError, match="SIZE GATE"):
        aqv.export_query_views(tmp_path, entries, [], views=[_toy_view(GOOD_SQL, GOOD_COLS)], progress=lambda m: None)


def test_every_view_declares_its_shape():
    for v in aqv.VIEWS:
        names = [c["name"] for c in v["columns"]]
        assert len(set(names)) == len(names), v["name"]
        assert v["count_name"] not in names, v["name"]
        for col in v["required_filters"] + list(v["group_by_requires"]) + [f["col"] for f in v["default_filters"]]:
            assert col in names, (v["name"], col)
        for c in v["columns"]:
            assert set(c["ops"]) <= set(aqv.OPS), (v["name"], c["name"])
            assert set(c["aggregates"]) <= set(aqv.AGGREGATES) - {"count"}, (v["name"], c["name"])
            if "sum" in c["aggregates"]:
                assert c["type"] == "integer", (v["name"], c["name"])
        if v["partition"]:  # lap-grain views
            assert "season" in v["required_filters"] and v["max_seasons"], v["name"]
        if v["partition"] == "season_race":
            assert "race_id" in v["required_filters"]
            assert next(c for c in v["columns"] if c["name"] == "race_id")["ops"] == ["eq"]


# ── scratch-export tests ────────────────────────────────────────────────────

def _files(entry: dict, root: Path) -> list[Path]:
    p = root / entry["path"].removeprefix("/data/")
    return sorted(p.rglob("*.parquet")) if p.is_dir() else [p]


@needs_export
def test_export_schema_matches_catalogue():
    root = Path(EXPORT)
    manifest = json.loads((root / "_manifest.json").read_text())
    cat = json.loads((root / "assistant" / "catalogue.json").read_text())
    by_name = {t["name"]: t for t in manifest["tables"]}
    assert {v["name"] for v in cat["views"]} == {v["name"] for v in aqv.VIEWS}
    for v in cat["views"]:
        entry = by_name[v["name"]]
        for f in _files(entry, root):
            desc = duckdb.execute(f"DESCRIBE SELECT * FROM read_parquet('{f}')").fetchall()
            assert [r[0] for r in desc] == [c["name"] for c in v["columns"]], f
            assert [aqv.PARQUET_TYPE[r[1]] for r in desc] == [c["type"] for c in v["columns"]], f
            assert aqv.denied_columns([r[0] for r in desc]) == []
            assert f.stat().st_size <= aqv.MAX_FILE_BYTES, f
        if v["partition_key"]:
            assert entry["partitioned"] and entry["partitionKey"] == "season"
            assert [p["value"] for p in entry["partitions"]] == cat["seasons"]


@needs_export
def test_export_views_are_deterministic(tmp_path):
    root = Path(EXPORT)
    manifest = json.loads((root / "_manifest.json").read_text())
    src = [t for t in manifest["tables"] if not t["name"].startswith("qv_")]
    digests = []
    for run in ("a", "b"):
        out = tmp_path / run
        aqv.export_query_views(out, copy.deepcopy(src), [], progress=lambda m: None, src_root=root)
        digests.append({str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in sorted((out / "assistant").rglob("*")) if p.is_file()})
    assert digests[0] == digests[1]
    published = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted((root / "assistant").rglob("*")) if p.is_file()}
    assert digests[0] == published


@needs_export
def test_export_null_actuals_are_not_zero_filled():
    root = Path(EXPORT)
    f = root / "assistant" / "qv" / "qv_driver_race.parquet"
    nulls, zeros = duckdb.execute(
        f"SELECT count(*) FILTER (WHERE actual_finish_position IS NULL), "
        f"count(*) FILTER (WHERE actual_finish_position = 0) FROM read_parquet('{f}')").fetchone()
    assert zeros == 0 and nulls > 0
