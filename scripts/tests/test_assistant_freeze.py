"""AX-19: freeze write/verify, mutation, gates (synthetic data, no warehouse)."""
from __future__ import annotations

import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import assistant_freeze as af


def _pq(path, rows, source=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"id": [str(i) for i in range(rows)]}
    if source:
        data["source"] = [json.dumps({"mart": source})] * rows
    pq.write_table(pa.table(data), path)


def _data(tmp_path, generated="2026-11-09T00:00:00Z", **block_over):
    d = tmp_path / "data"
    _pq(d / "assistant/cards/2024.parquet", 3, "mart_x")
    _pq(d / "marts/mart_x.parquet", 5)
    (d / "assistant/catalogue.json").write_text('{"a":1}')
    (d / "assistant/index.json").write_text('{"b":2}')
    block = {"cards": [{"season": 2024, "path": "/data/assistant/cards/2024.parquet", "rows": 3, "sha256": "x"}],
             "catalogue_version": "cv", "registry": "r", "label_version": "v1", "model_version": None,
             "classes_live": ["T"], "classes_held": ["T*", "WC", "ML"]}
    block.update(block_over)
    m = {"version": "abc", "generatedAt": generated, "assistant": block,
         "tables": [{"name": "mart_x", "path": "/data/marts/mart_x.parquet", "partitioned": False}]}
    if block_over.get("_drop"):
        del m["assistant"]
    (d / "_manifest.json").write_text(json.dumps(m))
    return d


def _run(d, tmp_path, *args):
    return af.main(["--data", str(d), "--freeze", str(tmp_path / "f/freeze.json"), *args])


def test_write_then_verify(tmp_path):
    d = _data(tmp_path)
    assert _run(d, tmp_path, "--write", "--ax13-real-pass") == 0
    f = json.loads((tmp_path / "f/freeze.json").read_text())
    assert f["card_sources"][0]["rows"] == 5 and f["assistant"]["cards"][0]["rows"] == 3
    assert "Refused" in f["launch_summary"]
    assert _run(d, tmp_path, "--verify") == 0


def test_write_needs_attestation(tmp_path):
    assert _run(_data(tmp_path), tmp_path, "--write") == 2
    assert not (tmp_path / "f/freeze.json").exists()


def test_dry_run_writes_nothing(tmp_path):
    assert _run(_data(tmp_path), tmp_path, "--dry-run") == 0
    assert not (tmp_path / "f").exists()


def test_mutated_partition_fails_and_names_it(tmp_path, capsys):
    d = _data(tmp_path)
    _run(d, tmp_path, "--write", "--ax13-real-pass")
    p = d / "assistant/cards/2024.parquet"
    p.write_bytes(p.read_bytes() + b"\0")
    assert _run(d, tmp_path, "--verify") == 1
    assert "cards/2024.parquet" in capsys.readouterr().err


def test_missing_assistant_block_fails(tmp_path):
    d = _data(tmp_path, _drop=True)
    assert _run(d, tmp_path, "--dry-run") == 1


def test_generated_before_seal_fails(tmp_path):
    assert _run(_data(tmp_path, generated="2026-10-16T00:00:00Z"), tmp_path, "--dry-run") == 1


def test_model_null_needs_ml_held(tmp_path):
    assert af.gate(json.loads((_data(tmp_path) / "_manifest.json").read_text())) == []
    m = json.loads((_data(tmp_path / "b", classes_held=["T*", "WC"]) / "_manifest.json").read_text())
    probs = af.gate(m)
    assert any("model_version" in p for p in probs)


def test_class_lists_pinned(tmp_path):
    m = json.loads((_data(tmp_path, classes_live=["T", "ML"]) / "_manifest.json").read_text())
    assert any("classes_live" in p for p in af.gate(m))
