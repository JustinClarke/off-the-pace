"""AX-08: --finalize hashing, tamper detection, deterministic parquet, 5 MB gate, cwd for the stg_* views."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

import assistant_finalize as af
import export_app_data as ead
from assistant_query_views import canonical_bytes


def _card(i: int, value=1.5, season=2024):
    return {
        "id": f"race.result:2024_1:D{i:02d}", "kind": "race.result", "metric": "finish", "label": "measured",
        "value": value, "unit": "pos", "display": str(value), "unavailable_reason": None,
        "n": {"count": 1, "unit": "races"}, "interval": None,
        "scope": {"season": season, "race_id": "2024_1", "driver_id": f"D{i:02d}", "constructor_id": None,
                  "circuit_id": None, "compound": None, "stint_id": None, "lap": None},
        "source": {"mart": "stg_results", "columns": ["position"], "feature": None, "query": None, "transform": None},
        "versions": {"data_version": "x", "label_version": "v1", "model_version": None, "card_schema": "1", "registry": "r"},
        "page": {"route": "/", "params": {}, "docs_slug": None}, "caveats": [], "sample": "na", "grade": "A",
        "status": "active", "held_reason": None, "policy_fields": {},
    }


def _out(tmp_path: Path, value=1.5, n=5) -> Path:
    out = tmp_path / "out"
    (out / "assistant" / "_staging").mkdir(parents=True)
    (out / "marts").mkdir()
    (out / "marts" / "t.parquet").write_bytes(b"x" * 10)
    cat = {"views": [], "limits": {}}
    cat["catalogue_version"] = hashlib.sha256(canonical_bytes(cat)).hexdigest()
    (out / "assistant" / "catalogue.json").write_text(json.dumps(cat))
    (out / "assistant" / "_staging" / "cards.json").write_text(json.dumps([_card(i, value) for i in range(n)]))
    (out / "assistant" / "_staging" / "build.json").write_text(json.dumps(
        {"versions": {"registry": "r", "label_version": "v1", "model_version": None}, "classes_live": ["T"], "classes_held": ["DA"]}))
    (out / "_manifest.json").write_text(json.dumps({"version": "old", "tables": []}))
    return out


def _restage(out: Path, value):
    (out / "assistant" / "_staging").mkdir()
    (out / "assistant" / "_staging" / "cards.json").write_text(json.dumps([_card(i, value) for i in range(5)]))
    (out / "assistant" / "_staging" / "build.json").write_text(json.dumps(
        {"versions": {"registry": "r", "label_version": "v1", "model_version": None}, "classes_live": ["T"], "classes_held": ["DA"]}))


def _manifest(out):
    return json.loads((out / "_manifest.json").read_text())


def test_changed_card_same_size_changes_version_and_check_fails_until_refinalized(tmp_path):
    out = _out(tmp_path, value=1.5)
    assert af.finalize(out) == 0
    v1 = _manifest(out)["version"]
    assert af.finalize(out, check=True) == 0
    _restage(out, 2.5)  # same byte length
    # cards on disk are still the old ones, the staged ones are not finalized yet
    assert af.finalize(out, check=True) == 0
    assert af.finalize(out) == 0
    assert _manifest(out)["version"] != v1
    # now tamper with the manifest version only: --finalize --check must fail
    m = _manifest(out); m["version"] = v1; (out / "_manifest.json").write_text(json.dumps(m))
    assert af.finalize(out, check=True) == 1


def test_check_fails_on_tampered_card_file(tmp_path):
    out = _out(tmp_path)
    af.finalize(out)
    f = out / "assistant" / "cards" / "2024.parquet"
    f.write_bytes(f.read_bytes() + b"\0")
    problems = af.verify_assistant(out, _manifest(out))
    assert any("2024.parquet" in p for p in problems)
    assert af.finalize(out, check=True) == 1


def test_parquet_is_deterministic_and_block_is_complete(tmp_path):
    a, b = _out(tmp_path / "a"), _out(tmp_path / "b")
    af.finalize(a); af.finalize(b)
    ma, mb = _manifest(a), _manifest(b)
    assert ma["assistant"]["cards"] == mb["assistant"]["cards"] and ma["version"] == mb["version"]
    blk = ma["assistant"]
    assert blk["card_schema"] == "1" and blk["model_version"] is None and blk["classes_live"] == ["T"]
    assert blk["catalogue_version"] == json.loads((a / "assistant" / "catalogue.json").read_text())["catalogue_version"]
    assert not (a / "assistant" / "_staging").exists()


def test_five_mb_gate(tmp_path, monkeypatch):
    out = _out(tmp_path)
    monkeypatch.setattr(af, "MAX_FILE_BYTES", 100)
    with pytest.raises(ValueError, match="SIZE GATE"):
        af.finalize(out)


def test_run_export_runs_from_transform_and_restores_cwd(tmp_path, monkeypatch):
    seen = {}
    db = tmp_path / "w.duckdb"; db.write_bytes(b"")
    monkeypatch.setattr(ead, "_run_export_dispatch", lambda *a: seen.setdefault("cwd", Path(os.getcwd()).resolve()))
    for start in (ead.ROOT, ead.ROOT / "transform"):
        monkeypatch.chdir(start)
        seen.clear()
        ead.run_export(db_path=db, out_root=tmp_path / "o")
        assert seen["cwd"] == (ead.ROOT / "transform").resolve()
        assert Path(os.getcwd()).resolve() == start.resolve()
