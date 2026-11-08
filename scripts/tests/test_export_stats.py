"""TX-07 part B (AP-04): the ML-models home tile count comes from the real card, no fallback."""

from __future__ import annotations

import json

import duckdb

import export_app_data as ead


def test_real_card_counts_five_of_five():
    assert ead.MODEL_CARD == ead.ROOT / "ml" / "models" / "model_card.json"
    assert ead.count_significant_models(ead.MODEL_CARD) == (5, 5)


def test_one_flag_false_gives_four_of_five(tmp_path):
    card = json.loads(ead.MODEL_CARD.read_text())
    card["model_card"]["models"][0]["beats_baseline_significant"] = False
    p = tmp_path / "model_card.json"
    p.write_text(json.dumps(card))
    assert ead.count_significant_models(p) == (4, 5)


def test_missing_file_gives_none(tmp_path):
    assert ead.count_significant_models(tmp_path / "nope.json") is None


def test_flat_shape_gives_none(tmp_path):
    p = tmp_path / "model_card.json"
    p.write_text(json.dumps({"models": [{"beats_baseline_significant": True}]}))
    assert ead.count_significant_models(p) is None


def test_unreadable_json_gives_none(tmp_path):
    p = tmp_path / "model_card.json"
    p.write_text("{not json")
    assert ead.count_significant_models(p) is None


def _tiny_conn():
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE fct_lap_residuals AS SELECT * FROM (VALUES (2023), (2024)) t(race_year)")
    conn.execute("CREATE TABLE dim_drivers AS SELECT * FROM (VALUES ('VER')) t(driver_code)")
    conn.execute("CREATE TABLE race_to_track AS SELECT * FROM (VALUES (1, 'monza')) t(race_id, track_id)")
    return conn


def test_stats_block_publishes_null_not_five_when_card_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ead, "MODEL_CARD", tmp_path / "missing.json")
    stats = ead.build_stats_block(_tiny_conn())
    assert stats["ml_models"] is None
    assert stats["ml_models_total"] is None
    assert "total_events" not in stats


def test_stats_block_real_card(monkeypatch):
    stats = ead.build_stats_block(_tiny_conn())
    assert (stats["ml_models"], stats["ml_models_total"]) == (5, 5)
    assert "total_events" not in stats
