"""WC-11 / WC-12 / WC-13: interim placeholder wake values -- config, rule, labels and isolation checks.

No warehouse is read. These are file checks on the seed, the dbt model and the
app feature that displays it:

  * the seed is well formed, covers every circuit in race_to_track, and every
    value is labelled `placeholder`;
  * no number from the archived dirty-air method (DA-03, BUILD-ORDER rule 6)
    appears in the seed, and no DA-03 identifier appears in any WC-11 file;
  * the DD-WC2 disclaimer is carried word for word (rule 7);
  * nothing in the ML code or the rest of the dbt graph reads the placeholder,
    so it can never become an ML feature or training target;
  * WC-12: the per-race rule (seeds/wake_placeholder_rule.csv x
    seeds/wake_placeholder_race_structure.csv) is mirrored here from the seeds alone,
    so every race gets a bounded value, fallbacks are flagged, the values move in the
    expected direction across circuits and eras, and no rule constant or per-race value
    equals a DA-03 number at 3 dp. The seed builder reads no outcome column.
  * WC-13: the tyre (compound) and car (constructor) multipliers are bounded, the tyre
    factor is monotone SOFT >= MEDIUM >= HARD, the car table is complete and neutral
    unless a row cites a public, non-outcome source, a missing key falls back to a
    flagged neutral, every race x tyre x car value stays in bounds and off the DA-03
    numbers, and the lap model reads only identity columns from stg_laps.
  * WC-16: the C-number tyre factor. The verified allocation seed has every race, each
    trio in hardness order (C-codes 2019 on, Pirelli names in 2018); the constants table
    is complete; every race x compound factor is bounded and monotone; 2018 falls back
    to the relative class; the DD-WC2 line is the owner's 2026-10-31 wording everywhere.
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SEED = ROOT / "transform/seeds/wake_placeholder_values.csv"
MODEL = ROOT / "transform/models/intermediate/int_lap_wake_placeholder_cost.sql"
RACE_MODEL = ROOT / "transform/models/intermediate/int_wake_placeholder_race_loss.sql"
RULE = ROOT / "transform/seeds/wake_placeholder_rule.csv"
STRUCTURE = ROOT / "transform/seeds/wake_placeholder_race_structure.csv"
BUILDER = ROOT / "transform/tasks/wake_calibration/wc12_structure.py"
COMPOUND = ROOT / "transform/seeds/wake_placeholder_compound_factor.csv"
CONSTRUCTOR = ROOT / "transform/seeds/wake_placeholder_constructor_factor.csv"
FACTORS_TEST = ROOT / "transform/tests/assert_wake_placeholder_factors.sql"
DIM_CONSTRUCTORS = ROOT / "transform/models/reference/dim_constructors.sql"
LABELS_TEST = ROOT / "transform/tests/assert_wake_placeholder_labels.sql"
ALLOCATION = ROOT / "transform/seeds/wake_placeholder_tyre_allocation.csv"
C_FACTOR = ROOT / "transform/seeds/wake_placeholder_c_number_factor.csv"
ALLOCATION_TEST = ROOT / "transform/tests/assert_wake_placeholder_tyre_allocation.sql"
USER_TYRE_ALLOCATIONS = ROOT / "transform/seeds/tyre_allocations.csv"
INT_SCHEMA = ROOT / "transform/models/intermediate/schema.yml"
PAGE_SUMMARIES = ROOT / "app/src/nav/pageSummaries.generated.json"
DOCS_PAGE = ROOT / "docs/app/dirty-air-cost.mdx"
ML_SCHEMA = ROOT / "ml/src/schema.py"
RACE_TO_TRACK = ROOT / "transform/seeds/race_to_track.csv"
LOG = ROOT / "_roadmap/_wake-calibration/status/build-log.json"
DA03_FIT = ROOT / "_roadmap/_archive/_dirty-air/_evidence/DA-03-2026-10-27/fit.json"
APP_FEATURE = ROOT / "app/src/features/dirty-air-cost"

MODEL_NAME = "int_lap_wake_placeholder_cost"
RACE_MODEL_NAME = "int_wake_placeholder_race_loss"
PLACEHOLDER_SEEDS = ("wake_placeholder_values", "wake_placeholder_rule", "wake_placeholder_race_structure",
                     "wake_placeholder_compound_factor", "wake_placeholder_constructor_factor",
                     "wake_placeholder_tyre_allocation", "wake_placeholder_c_number_factor")
PLACEHOLDER_COLUMNS = ("wake_cost_placeholder_s", "wake_exposure", "loss_basis", "loss_source",
                       "compound_factor", "constructor_factor", "lap_loss_basis", "lap_loss_bounded",
                       "factor_flag", "race_loss_s_per_lap_within_1s", "compound_factor_scale",
                       "tyre_c_number", "race_medium_c") + PLACEHOLDER_SEEDS
# The owner kept this second line beside DD-WC2 (2026-10-30, DD-WC18 precedent). Word for word.
# WC-13 (DD-WC26): "on this tyre and car" added now the value varies by tyre and car.
# DD-WC30 (2026-11-01, delegated ruling): reworded so it no longer repeats DD-WC2.
PLACEHOLDER_LINE = "Placeholder = an interim value set by a fixed rule, not a measurement of this lap."
OLD_PLACEHOLDER_LINES = ("at this type of circuit",
                         "at this circuit and season, not a measurement of this lap.",
                         "Placeholder = an assumed typical cost for a car this close at this circuit and season, "
                         "on this tyre and car, not a measurement of this lap.")
# Races with no corner structure in the WC-03 pass table (no telemetry in bronze; no FastF1 corner table).
EXPECTED_FALLBACK_RACES = {"2018_1", "2018_2", "2020_9", "2020_16"}
# DD-WC2 as reworded by the owner 2026-10-31 (WC-16), word for word; the build log holds the same text.
DD_WC2_LINE = ("Modelled: an assumed typical loss for this circuit, season, tyre and car, applied to the measured "
               "time spent close behind another car. Not calibrated on this driver's own stints.")
OLD_DD_WC2_LINE = ("Normalised from other compounds, based on stints from other drivers or the general performance "
                   "of the tyres after removing other factors.")
DA03_IDENTIFIERS = ("DA-03", "DA03", "da_03", "fit_dirty_air_microsector", "microsector")


def _seed_rows() -> list[dict]:
    with SEED.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _wc11_files() -> list[Path]:
    return [SEED, MODEL] + sorted(p for p in APP_FEATURE.glob("*") if p.is_file())


def _wc12_files() -> list[Path]:
    return [RULE, STRUCTURE, RACE_MODEL, BUILDER, COMPOUND, CONSTRUCTOR, FACTORS_TEST,
            ALLOCATION, C_FACTOR, ALLOCATION_TEST]


def _floats(obj) -> list[float]:
    if isinstance(obj, bool):
        return []
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, dict):
        return [x for v in obj.values() for x in _floats(v)]
    if isinstance(obj, list):
        return [x for v in obj for x in _floats(v)]
    return []


def _squash(text: str) -> str:
    """SQL with all whitespace removed, so a lint reflow does not break a text check."""
    return re.sub(r"\s+", "", text)


def _dd_wc2_text() -> str:
    log = json.loads(LOG.read_text(encoding="utf-8"))
    dd = next(d for d in log["decisions"] if d["id"] == "DD-WC2")
    m = re.search(r'"([^"]+)"', dd["resolution"])
    assert m, "DD-WC2 resolution has no quoted disclaimer"
    return m.group(1)


# --- the seed ---------------------------------------------------------------

def test_seed_has_one_default_per_class_and_values_are_placeholders():
    rows = _seed_rows()
    assert rows and set(rows[0]) == {
        "row_kind", "key", "corner_class", "loss_s_per_lap_within_1s", "value_kind", "basis"}
    defaults = {r["key"]: float(r["loss_s_per_lap_within_1s"])
                for r in rows if r["row_kind"] == "class_default"}
    assert set(defaults) == {"fast", "medium", "slow"}
    assert all(0.0 < v <= 1.0 for v in defaults.values())
    assert defaults["fast"] >= defaults["medium"] >= defaults["slow"]
    assert all(r["value_kind"] == "placeholder" for r in rows)
    assert all(r["basis"].strip() for r in rows)
    assert all(r["corner_class"] in defaults for r in rows)
    assert sum(r["row_kind"] == "unlisted_default" for r in rows) == 1
    keys = [r["key"] for r in rows]
    assert len(keys) == len(set(keys))


def test_seed_covers_every_circuit_in_race_to_track():
    with RACE_TO_TRACK.open(encoding="utf-8", newline="") as f:
        tracks = {unicodedata.normalize("NFC", r["track_id"]) for r in csv.DictReader(f)}
    circuits = {r["key"] for r in _seed_rows() if r["row_kind"] == "circuit"}
    assert all(k == unicodedata.normalize("NFC", k) for k in circuits)
    assert tracks - circuits == set(), "circuits with no placeholder row"


def test_circuit_overrides_are_in_range():
    for r in _seed_rows():
        if r["row_kind"] == "circuit" and r["loss_s_per_lap_within_1s"].strip():
            assert 0.0 <= float(r["loss_s_per_lap_within_1s"]) <= 1.0, r["key"]


# --- rule 6: nothing from the archived method --------------------------------

def _da03_numbers() -> set[float]:
    da03 = {round(x, 3) for x in _floats(json.loads(DA03_FIT.read_text()))
            if abs(x) >= 0.005}
    assert da03, "DA-03 fit.json parsed to no numbers"
    return da03


def test_no_da03_number_in_the_seed():
    da03 = _da03_numbers()
    seed_values = [float(r["loss_s_per_lap_within_1s"]) for r in _seed_rows()
                   if r["loss_s_per_lap_within_1s"].strip()]
    clashes = {v for v in seed_values if round(v, 3) in da03}
    assert not clashes, f"seed value(s) equal a DA-03 number at 3 dp: {clashes}"


def test_no_da03_identifier_in_wc11_files():
    for path in _wc11_files() + _wc12_files():
        text = path.read_text(encoding="utf-8")
        for ident in DA03_IDENTIFIERS:
            assert ident not in text, f"{ident!r} in {path.relative_to(ROOT)}"


# --- rule 7: disclaimer word for word -----------------------------------------

def _sql_literal(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def test_model_carries_dd_wc2_disclaimer_verbatim():
    assert _sql_literal(_dd_wc2_text()) in MODEL.read_text(encoding="utf-8")


def test_dd_wc2_is_the_owner_rewording_everywhere():
    """Owner 2026-10-31: DD-WC2 replaced word for word in every placeholder file; the old line is gone."""
    assert _dd_wc2_text() == DD_WC2_LINE
    for path in (MODEL, LABELS_TEST, INT_SCHEMA):        # SQL / YAML: apostrophe doubled
        assert DD_WC2_LINE.replace("'", "''") in path.read_text(encoding="utf-8"), path.relative_to(ROOT)
    for path in (APP_FEATURE / "transform.ts", DOCS_PAGE):
        assert DD_WC2_LINE in path.read_text(encoding="utf-8"), path.relative_to(ROOT)
    assert DD_WC2_LINE.replace('"', '\\"') in PAGE_SUMMARIES.read_text(encoding="utf-8")
    for path in _wc11_files() + _wc12_files() + [LABELS_TEST, DOCS_PAGE, INT_SCHEMA, PAGE_SUMMARIES]:
        assert OLD_DD_WC2_LINE not in path.read_text(encoding="utf-8"), path.relative_to(ROOT)
    log = json.loads(LOG.read_text(encoding="utf-8"))
    dd = next(d for d in log["decisions"] if d["id"] == "DD-WC2")
    assert any(OLD_DD_WC2_LINE in h["resolution"] for h in dd.get("history", [])), "old wording dropped from history"


def test_model_never_fills_unavailable_with_zero():
    sql = MODEL.read_text(encoding="utf-8")
    assert "COALESCE(share_lap_within" not in sql
    assert "unavailable_reason" in sql and "'unavailable'" in sql


def test_app_feature_carries_dd_wc2_disclaimer_verbatim():
    text = "".join(p.read_text(encoding="utf-8") for p in _wc11_files()[2:])
    assert _dd_wc2_text() in text


# --- isolation: never an ML feature or target ---------------------------------

def test_ml_code_does_not_read_the_placeholder():
    for path in sorted((ROOT / "ml").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for name in (MODEL_NAME, RACE_MODEL_NAME) + PLACEHOLDER_COLUMNS:
            assert name not in text, f"{name} in {path.relative_to(ROOT)}"


def test_no_dbt_model_refs_the_placeholder():
    names = "|".join((MODEL_NAME, RACE_MODEL_NAME) + PLACEHOLDER_SEEDS)
    pattern = re.compile(r"ref\(\s*['\"](" + names + r")['\"]\s*\)")
    for path in sorted((ROOT / "transform/models").rglob("*.sql")):
        if path in (MODEL, RACE_MODEL):
            continue
        assert not pattern.search(path.read_text(encoding="utf-8")), \
            f"{path.relative_to(ROOT)} reads the placeholder; it must stay display-only"


def test_ml_feature_contract_names_no_placeholder():
    text = ML_SCHEMA.read_text(encoding="utf-8")
    for name in (MODEL_NAME, RACE_MODEL_NAME, "placeholder", "wake_cost", "loss_s_per_lap_within_1s"):
        assert name not in text, f"{name} in ml/src/schema.py"


# --- the placeholder line (owner ruling 2026-10-30) ------------------------------

def test_placeholder_line_verbatim_everywhere():
    for path in (MODEL, LABELS_TEST, APP_FEATURE / "transform.ts", DOCS_PAGE,
                 ROOT / "transform/models/intermediate/schema.yml",
                 ROOT / "app/src/nav/pageSummaries.generated.json"):
        assert PLACEHOLDER_LINE in path.read_text(encoding="utf-8"), path.relative_to(ROOT)
    for path in _wc11_files() + _wc12_files() + [LABELS_TEST, DOCS_PAGE,
                                                 ROOT / "transform/models/intermediate/schema.yml",
                                                 ROOT / "app/src/nav/pageSummaries.generated.json"]:
        text = path.read_text(encoding="utf-8")
        for old in OLD_PLACEHOLDER_LINES:
            assert old not in text, f"old wording {old!r} in {path.relative_to(ROOT)}"


# --- WC-12: the per-race rule, mirrored from the seeds ---------------------------

def _rule() -> tuple[dict, list[dict]]:
    with RULE.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    params = {r["param"]: float(r["value"]) for r in rows if r["param_kind"] != "era"}
    eras = [r for r in rows if r["param_kind"] == "era"]
    return params, eras


def _era(season: int, eras: list[dict]) -> dict:
    hit = [e for e in eras if int(e["season_from"]) <= season <= int(e["season_to"])]
    assert len(hit) == 1, f"season {season} matches {len(hit)} era rows"
    return hit[0]


def _per_race() -> dict[str, dict]:
    """The rule of int_wake_placeholder_race_loss, recomputed from the seeds alone."""
    params, eras = _rule()
    with STRUCTURE.open(encoding="utf-8", newline="") as f:
        structure = {r["race_id"]: r for r in csv.DictReader(f)}
    classes = {r["key"]: r for r in _seed_rows()}
    unlisted = next(r["corner_class"] for r in _seed_rows() if r["row_kind"] == "unlisted_default")
    with RACE_TO_TRACK.open(encoding="utf-8", newline="") as f:
        races = {r["race_id"]: unicodedata.normalize("NFC", r["track_id"]) for r in csv.DictReader(f)}
    out = {}
    for race_id, track in races.items():
        season = int(race_id.split("_")[0])
        era = _era(season, eras)
        factor = float(era["value"])
        s = structure.get(race_id)
        if s:
            index = sum(params[k] * float(s[f"n_{k}"]) for k in ("fast", "medium", "slow", "flat"))
            raw = factor * params["loss_at_reference_s"] * index / params["reference_index"]
            source = "race_structure"
        else:
            row = classes.get(track)
            cls = row["corner_class"] if row else unlisted
            raw = factor * float(classes[cls]["loss_s_per_lap_within_1s"])
            source = "class_fallback"
        loss = round(min(max(raw, params["min_s"]), params["max_s"]), 2)
        out[race_id] = {"season": season, "track": track, "loss": loss, "raw": raw, "source": source,
                        "era": era["param"]}
    return out


def test_rule_seed_is_complete_and_in_range():
    params, eras = _rule()
    assert set(params) == {"fast", "medium", "slow", "flat", "loss_at_reference_s", "reference_index",
                           "min_s", "max_s", "neutral_default"}
    assert params["neutral_default"] == 1.0
    assert params["fast"] >= params["medium"] >= params["slow"] > 0
    assert 0 < params["flat"] <= params["medium"]
    assert 0 < params["min_s"] < params["max_s"] <= 1.0
    with RULE.open(encoding="utf-8", newline="") as f:
        assert all(r["basis"].strip() for r in csv.DictReader(f))
    for season in range(2017, 2031):
        assert 0.5 <= float(_era(season, eras)["value"]) <= 1.0
    assert [e["param"] for e in eras if "unassessed" in e["param"]] == ["2026_on_unassessed"]


def test_every_race_has_a_bounded_value():
    params, _ = _rule()
    per_race = _per_race()
    with RACE_TO_TRACK.open(encoding="utf-8", newline="") as f:
        assert set(per_race) == {r["race_id"] for r in csv.DictReader(f)}
    for race_id, r in per_race.items():
        assert params["min_s"] <= r["loss"] <= params["max_s"], race_id


def test_fallbacks_are_exactly_the_races_without_structure():
    per_race = _per_race()
    assert {k for k, r in per_race.items() if r["source"] == "class_fallback"} == EXPECTED_FALLBACK_RACES
    sql = RACE_MODEL.read_text(encoding="utf-8")
    assert "'class_fallback'" in sql and "Fallback:" in sql and "era_assessed" in sql


def test_values_move_in_the_expected_direction():
    per_race = _per_race()
    by = {(r["track"], r["season"]): r["loss"] for r in per_race.values()}
    for season in (2018, 2022, 2025):
        assert by[("british_grand_prix", season)] > by[("italian_grand_prix", season)]
        assert by[("british_grand_prix", season)] > by[("monaco_grand_prix", season)]
        assert by[("hungarian_grand_prix", season)] > by[("italian_grand_prix", season)]
    for track in ("british_grand_prix", "monaco_grand_prix", "belgian_grand_prix", "hungarian_grand_prix"):
        assert by[(track, 2021)] > by[(track, 2022)], track       # ground effect: easier to follow
        assert by[(track, 2022)] < by[(track, 2023)] <= by[(track, 2024)], track  # outwash regained
        assert by[(track, 2018)] > by[(track, 2025)], track
    assert len({r["loss"] for r in per_race.values()}) >= 20, "rule collapsed to a few values"


def test_no_da03_number_in_the_rule_or_the_per_race_values():
    da03 = _da03_numbers()
    params, eras = _rule()
    consts = list(params.values()) + [float(e["value"]) for e in eras]
    assert not {v for v in consts if round(v, 3) in da03}, "rule constant equals a DA-03 number"
    clashes = {k: r["loss"] for k, r in _per_race().items() if round(r["loss"], 3) in da03}
    assert not clashes, f"per-race value(s) equal a DA-03 number at 3 dp: {clashes}"


def test_race_model_rounds_like_the_mirror_and_reads_no_outcome():
    sql = RACE_MODEL.read_text(encoding="utf-8")
    assert _squash("ROUND(LEAST(GREATEST(loss_raw_s, min_s), max_s), 2)") in _squash(sql)
    for col in ("seg_time_s", "lap_time_s", "LapTime", "speed_kph", "apex_kph", "seg_start_t", "seg_end_t"):
        assert col not in sql, col


BUILT_ARCHIVE_TEST = ROOT / "transform/tests/assert_wake_placeholder_off_archived_numbers.sql"


def test_built_tables_are_checked_against_the_archive_in_dbt():
    """Review R5: the mirror above can round differently from DuckDB (2020_9 sits at 0.405, halfway
    to the archived 0.40), so a dbt singular test checks the BUILT values against the same archive set."""
    sql = BUILT_ARCHIVE_TEST.read_text(encoding="utf-8")
    assert "../" + str(DA03_FIT.relative_to(ROOT)) in sql, "dbt test must read the same archived fit.json"
    assert ">= 0.005" in sql and "ROUND(CAST(v AS DOUBLE), 3)" in sql, "same archive set as _da03_numbers()"
    for ref in (RACE_MODEL_NAME, MODEL_NAME):
        assert f"ref('{ref}')" in sql, ref
    assert "< 0.0005 + 1e-9" in sql, "match at 3 dp must not be looser than round()"
    readme = (ROOT / "transform/tests/README.md").read_text(encoding="utf-8")
    assert f"`{BUILT_ARCHIVE_TEST.name}`" in readme, "register the test in transform/tests/README.md"


def test_structure_builder_reads_no_outcome_column():
    import importlib.util
    import sys
    sys.path.insert(0, str(ROOT / "transform"))
    spec = importlib.util.spec_from_file_location("wc12_structure", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from tasks.wake_calibration.wc10_io import GUARDED_COLUMNS
    assert not set(mod.READ_COLUMNS + mod.LAYOUT_COLUMNS) & GUARDED_COLUMNS
    assert "apex_kph" not in mod.READ_COLUMNS and "min_speed_kph" not in mod.READ_COLUMNS


# --- WC-13: tyre (compound) and car (constructor) multipliers ---------------------

COMPOUND_BOUNDS = (0.90, 1.15)
CONSTRUCTOR_BOUNDS = (0.95, 1.05)
NEUTRAL_BASIS = "neutral default, no public evidence used"
OUTCOME_COLUMNS = ("seg_time_s", "lap_time_s", "lap_time", "LapTime", "sector", "speed", "kph",
                   "apex", "min_speed", "exit_speed", "seg_start_t", "seg_end_t", "position",
                   "points", "pace", "residual")


def _compound_rows() -> dict[str, dict]:
    with COMPOUND.open(encoding="utf-8", newline="") as f:
        return {r["compound_class"]: r for r in csv.DictReader(f)}


def _constructor_rows() -> list[dict]:
    with CONSTRUCTOR.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_compound_factor_bounded_and_monotone():
    rows = _compound_rows()
    assert set(rows) == {"SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"}
    f = {k: float(r["factor"]) for k, r in rows.items()}
    lo, hi = COMPOUND_BOUNDS
    assert all(lo <= v <= hi for v in f.values()), f
    assert f["SOFT"] >= f["MEDIUM"] >= f["HARD"]
    assert f["SOFT"] > f["HARD"], "tyre factor collapsed to neutral"
    assert f["MEDIUM"] == 1.0, "MEDIUM is the reference"
    for k in ("INTERMEDIATE", "WET"):
        assert f[k] == 1.0 and rows[k]["source_type"] == "neutral_by_rule", k
    for k in ("SOFT", "MEDIUM", "HARD"):
        assert rows[k]["source_type"] == "assumed", k
    assert all(r["basis"].strip() for r in rows.values())
    assert "wear" in rows["SOFT"]["basis"], "the SOFT basis must say this is not tyre wear"


def _dim_constructors() -> dict[str, str]:
    sql = DIM_CONSTRUCTORS.read_text(encoding="utf-8")
    return {m.group(1): m.group(3) for m in re.finditer(r"\('([^']+)', '([^']+)', '([^']+)'\)", sql)}


def test_constructor_table_complete_neutral_unless_sourced():
    rows = _constructor_rows()
    assert rows and set(rows[0]) == {"season", "constructor_id", "constructor_lineage_id", "factor",
                                     "source_type", "basis"}
    keys = [(r["season"], r["constructor_id"]) for r in rows]
    assert len(keys) == len(set(keys)), "duplicate (season, constructor_id)"
    dim = _dim_constructors()
    assert len(dim) >= 19
    seasons = {}
    for r in rows:
        assert r["constructor_id"] in dim, r["constructor_id"]
        assert r["constructor_lineage_id"] == dim[r["constructor_id"]], r
        seasons.setdefault(int(r["season"]), set()).add(r["constructor_id"])
        f = float(r["factor"])
        lo, hi = CONSTRUCTOR_BOUNDS
        assert lo <= f <= hi, r
        if r["source_type"] == "neutral_default":
            assert f == 1.0 and r["basis"] == NEUTRAL_BASIS, r
        else:
            assert r["source_type"] == "public_concept", r
            assert f != 1.0, r
            # a cited, checkable public source: a URL or a named document, never an outcome
            assert re.search(r"https?://|regulation|technical directive|team statement", r["basis"], re.I), r
            assert not re.search(r"lap time|pace|faster|slower|result", r["basis"], re.I), r
    # every season 2018-2025 has a full grid (10 teams; 11 names in 2018: Force India -> Racing Point)
    assert set(seasons) == set(range(2018, 2026))
    for season, teams in seasons.items():
        assert len(teams) == (11 if season == 2018 else 10), (season, sorted(teams))
    # renames are their own rows and share a lineage
    lineage = {(int(r["season"]), r["constructor_id"]): r["constructor_lineage_id"] for r in rows}
    assert lineage[(2018, "Force India")] == lineage[(2021, "Aston Martin")] == "force_india"
    assert lineage[(2019, "Toro Rosso")] == lineage[(2020, "AlphaTauri")] == lineage[(2024, "RB")] \
        == lineage[(2025, "Racing Bulls")] == "toro_rosso"


def test_missing_keys_fall_back_to_a_flagged_neutral():
    sql = MODEL.read_text(encoding="utf-8")
    for source in ("neutral_missing_compound", "neutral_unresolved_compound",
                   "neutral_missing_constructor", "neutral_no_constructor_row", "neutral_wet_or_intermediate"):
        assert f"'{source}'" in sql, source
    assert "COALESCE(cf.factor, rule.neutral_factor)" in sql
    assert "COALESCE(kf.factor, rule.neutral_factor)" in sql
    assert "AS factor_flag" in sql
    test_sql = FACTORS_TEST.read_text(encoding="utf-8")
    assert "neutral fallback without a flag" in test_sql and "no constructor row" in test_sql


def _lap_values() -> dict[tuple, float]:
    """Every (race, tyre class, constructor) per-lap loss the model can produce, from the seeds alone.
    WC-16: a race with a C-number trio has its three C-number factors (plus wet / missing neutral);
    any other race has the relative factors."""
    params, _ = _rule()
    relative = {k: float(r["factor"]) for k, r in _compound_rows().items()}
    relative["neutral"] = params["neutral_default"]
    per_race_tyre = _race_tyre_factors()
    by_season: dict[int, list[tuple[str, float]]] = {}
    for r in _constructor_rows():
        by_season.setdefault(int(r["season"]), []).append((r["constructor_id"], float(r["factor"])))
    out = {}
    for race_id, r in _per_race().items():
        cars = by_season.get(r["season"], []) + [("neutral", params["neutral_default"])]
        cf = relative
        if race_id in per_race_tyre:
            cf = {**{k: v for k, v in relative.items() if k not in ("SOFT", "MEDIUM", "HARD")},
                  **per_race_tyre[race_id]}
        for tyre, f_t in cf.items():
            for car, f_c in cars:
                raw = r["loss"] * f_t * f_c
                out[(race_id, tyre, car)] = round(min(max(raw, params["min_s"]), params["max_s"]), 4)
    return out


def test_combined_value_bounded_and_off_da03():
    params, _ = _rule()
    values = _lap_values()
    assert all(params["min_s"] <= v <= params["max_s"] for v in values.values())
    da03 = _da03_numbers()
    clashes = {k: v for k, v in values.items() if round(v, 3) in da03}
    assert not clashes, f"race x tyre x car value(s) equal a DA-03 number at 3 dp: {dict(list(clashes.items())[:5])}"
    consts = [float(r["factor"]) for r in _compound_rows().values()] + \
             [float(r["factor"]) for r in _constructor_rows()] + \
             [float(r["value"]) for r in _c_factor_rows()] + \
             [v for f in _race_tyre_factors().values() for v in f.values()]
    assert not {v for v in consts if round(v, 3) in da03}, "a factor equals a DA-03 number"
    assert _squash("ROUND(LEAST(GREATEST(race_loss_s * compound_factor * constructor_factor, min_s), max_s), 4)") \
        in _squash(MODEL.read_text(encoding="utf-8"))


def test_lap_model_reads_identity_columns_only():
    sql = MODEL.read_text(encoding="utf-8")
    m = re.search(r"lap_identity AS \((.*?)\n\),", sql, re.S)
    assert m, "lap_identity CTE not found"
    selected = re.search(r"SELECT(.*?)FROM", m.group(1), re.S).group(1)
    cols = {c.strip().split(" AS ")[-1].strip() for c in selected.split(",") if c.strip()}
    assert cols == {"lap_id", "race_id", "race_year", "compound", "constructor_id"}, cols
    code = "\n".join(line.split("--")[0] for line in sql.splitlines())
    for col in OUTCOME_COLUMNS:
        assert col not in code.lower() if col.islower() else col not in code, col
    assert "ref('stg_laps')" in sql and sql.count("ref('stg_laps')") == 1


# --- WC-16: the C-number tyre factor -------------------------------------------------

C_FACTOR_BOUNDS = (0.90, 1.17)


def _c_number(code: str) -> int:
    assert re.fullmatch(r"C[1-6]", code), code
    return int(code[1:])


def _allocation_rows() -> list[dict]:
    with ALLOCATION.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _c_factor_rows() -> list[dict]:
    with C_FACTOR.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _c_rule() -> tuple[dict[int, float], dict[str, float], tuple[float, float]]:
    rows = _c_factor_rows()
    step = {int(r["param"]): float(r["value"]) for r in rows if r["param_kind"] == "step"}
    shift = {r["param"]: float(r["value"]) for r in rows if r["param_kind"] == "medium_shift"}
    bound = {r["param"]: float(r["value"]) for r in rows if r["param_kind"] == "bound"}
    return step, shift, (bound["min"], bound["max"])


def _race_tyre_factors() -> dict[str, dict[str, float]]:
    """The model's c_number factor for each race's HARD / MEDIUM / SOFT, from the seeds alone."""
    step, shift, (lo, hi) = _c_rule()
    out = {}
    for r in _allocation_rows():
        if r["compound_scale"] != "c_number":
            continue
        med = _c_number(r["medium_c"])
        assert r["medium_c"] in shift, f"{r['race_id']}: medium {r['medium_c']} has no shift row"
        out[r["race_id"]] = {
            label: round(min(max(step[max(-2, min(2, _c_number(r[col]) - med))] * shift[r["medium_c"]], lo), hi), 4)
            for label, col in (("HARD", "hard_c"), ("MEDIUM", "medium_c"), ("SOFT", "soft_c"))}
    return out


def test_allocation_seed_has_every_race_in_hardness_order():
    rows = _allocation_rows()
    assert set(rows[0]) == {"race_id", "season", "round", "circuit", "compound_scale", "hard_c", "medium_c",
                            "soft_c", "hard_name", "medium_name", "soft_name", "source_url", "source_type", "notes"}
    with RACE_TO_TRACK.open(encoding="utf-8", newline="") as f:
        races = {r["race_id"]: unicodedata.normalize("NFC", r["track_id"]) for r in csv.DictReader(f)}
    ids = [r["race_id"] for r in rows]
    assert len(ids) == len(set(ids)) == 173 and set(ids) == set(races)
    with (ROOT / "transform/seeds/compound_hardness_scale.csv").open(encoding="utf-8", newline="") as f:
        rank_2018 = {r["compound_code"]: int(r["hardness_rank"]) for r in csv.DictReader(f) if r["era"] == "2018"}
    for r in rows:
        season = int(r["season"])
        assert r["race_id"].startswith(f"{season}_") and r["circuit"] == races[r["race_id"]], r["race_id"]
        assert r["source_url"].startswith("https://") and r["source_type"] in ("primary_pirelli", "secondary")
        if season == 2018:
            assert r["compound_scale"] == "named_2018" and not (r["hard_c"] or r["medium_c"] or r["soft_c"])
            names = [r["hard_name"], r["medium_name"], r["soft_name"]]
            assert all(n in rank_2018 for n in names), r["race_id"]
            assert rank_2018[names[0]] < rank_2018[names[1]] < rank_2018[names[2]], r["race_id"]
        else:
            assert r["compound_scale"] == "c_number" and not (r["hard_name"] or r["medium_name"] or r["soft_name"])
            assert _c_number(r["hard_c"]) < _c_number(r["medium_c"]) < _c_number(r["soft_c"]), r["race_id"]
    by = {r["race_id"]: (r["hard_c"], r["medium_c"], r["soft_c"]) for r in rows}
    # spot values from the research: skip races, C6 races, and the corrections to the user-supplied file
    assert by["2022_3"] == ("C2", "C3", "C5") and by["2025_13"] == by["2025_19"] == ("C1", "C3", "C4")
    assert by["2025_20"] == ("C2", "C4", "C5") and by["2025_8"] == ("C4", "C5", "C6")
    assert by["2025_5"] == by["2024_16"] == ("C3", "C4", "C5")
    assert sum("C6" in v for v in by.values()) == 4


def test_c_factor_table_complete_and_bounded():
    rows = _c_factor_rows()
    assert set(rows[0]) == {"param_kind", "param", "value", "source_type", "basis"}
    step, shift, (lo, hi) = _c_rule()
    assert step == {-2: 0.93, -1: 0.96, 0: 1.00, 1: 1.10, 2: 1.17}
    # DD-WC29 (owner 2026-10-31): the medium shift is dropped (all 1.00); rows kept for a calibrated shift later
    assert shift == {"C2": 1.00, "C3": 1.00, "C4": 1.00, "C5": 1.00}
    assert all("DD-WC29" in r["basis"] for r in rows if r["param_kind"] == "medium_shift")
    assert (lo, hi) == C_FACTOR_BOUNDS
    assert all(r["source_type"] == "assumed" and "c_numbers_report.md" in r["basis"] for r in rows)
    assert all(step[k] < step[k + 1] for k in range(-2, 2)), "step not monotone in softness"
    assert [shift[c] for c in ("C2", "C3", "C4", "C5")] == sorted(shift.values()), "shift not monotone"
    assert all(0.90 <= v <= 1.17 for v in shift.values())
    # every medium that occurs has a shift row (C1 / C6 as medium would fail the dbt test loudly)
    assert {r["medium_c"] for r in _allocation_rows() if r["compound_scale"] == "c_number"} <= set(shift)
    test_sql = ALLOCATION_TEST.read_text(encoding="utf-8")
    assert "no medium_shift row" in test_sql and "hardness order" in test_sql


def test_every_race_tyre_factor_complete_monotone_bounded():
    per_race = _race_tyre_factors()
    assert len(per_race) == 152 and all(r.split("_")[0] != "2018" for r in per_race)
    lo, hi = C_FACTOR_BOUNDS
    for race_id, f in per_race.items():
        assert set(f) == {"HARD", "MEDIUM", "SOFT"}, race_id
        assert all(lo <= v <= hi for v in f.values()), (race_id, f)
        assert f["SOFT"] > f["MEDIUM"] > f["HARD"], (race_id, f)
    # a consecutive C2/C3/C4 race keeps the WC-13 relative factors exactly
    rel = {k: float(r["factor"]) for k, r in _compound_rows().items()}
    c3 = [k for k, r in zip(per_race, [x for x in _allocation_rows() if x["compound_scale"] == "c_number"])
          if (r["hard_c"], r["medium_c"], r["soft_c"]) == ("C2", "C3", "C4")]
    assert c3 and all(per_race[k] == {c: rel[c] for c in ("HARD", "MEDIUM", "SOFT")} for k in c3)
    # skip races follow the actual C-number gap
    assert per_race["2022_3"]["SOFT"] == 1.17 and per_race["2025_13"]["HARD"] == 0.93
    assert per_race["2025_20"]["HARD"] == 0.93 and per_race["2025_19"]["HARD"] == 0.93
    assert per_race["2025_8"]["SOFT"] == 1.10 and per_race["2025_8"]["MEDIUM"] == 1.00
    # DD-WC29: every race's factors are the step values alone
    assert {v for f in per_race.values() for v in f.values()} == {0.93, 0.96, 1.00, 1.10, 1.17}


def test_model_uses_c_number_rule_and_2018_fallback():
    sql = MODEL.read_text(encoding="utf-8")
    code = "\n".join(line.split("--")[0] for line in sql.splitlines())
    assert "ref('wake_placeholder_tyre_allocation')" in code and "ref('wake_placeholder_c_number_factor')" in code
    assert "ref('tyre_allocations')" not in sql, "the user-supplied tyre_allocations seed must not be read"
    for literal in ("'assumed_c_number'", "'c_number'", "'relative_class'", "'neutral'", "AS compound_factor_scale",
                    "AS tyre_c_number", "compound_scale = 'c_number'", "li.race_year > 2018"):
        assert literal in code, literal
    assert _squash("LEAST(GREATEST(t.c_step_factor * t.medium_shift, cb.c_min), cb.c_max)") in _squash(code)
    # no C-number constant hard-coded in the SQL: they live in the seed
    for const in ("0.93", "0.97", "1.03", "1.06", "1.10", "1.17"):
        assert const not in code, const
    # 2018 keeps the relative race-order class; wet / intermediate / missing stay neutral and flagged
    for literal in ("'assumed_race_order_2018'", "'neutral_wet_or_intermediate'", "'neutral_missing_compound'"):
        assert literal in code, literal
    test_sql = FACTORS_TEST.read_text(encoding="utf-8")
    for problem in ("not clamp(step x medium shift)", "relative_class tyre factor differs",
                    "not on the c_number scale", "not neutral", "in this race"):
        assert problem in test_sql, problem


def test_user_supplied_tyre_allocations_untouched_and_not_read():
    """The new seed corrects tyre_allocations for this model only; the original file is not edited or read."""
    for path in [MODEL, RACE_MODEL, FACTORS_TEST, ALLOCATION_TEST, LABELS_TEST]:
        assert "ref('tyre_allocations')" not in path.read_text(encoding="utf-8"), path.relative_to(ROOT)
    with USER_TYRE_ALLOCATIONS.open(encoding="utf-8", newline="") as f:
        user = {(r["race_year"], r["circuit_key"]): (r["hard_code"], r["medium_code"], r["soft_code"])
                for r in csv.DictReader(f)}
    ours = {(r["season"], r["circuit"]): (r["hard_c"], r["medium_c"], r["soft_c"], r["race_id"], r["notes"])
            for r in _allocation_rows() if r["compound_scale"] == "c_number"}
    differ = {v[3] for k, v in ours.items() if k in user and user[k] != v[:3]}
    assert differ == {"2024_16", "2025_5", "2025_7", "2025_8", "2025_10", "2025_12", "2025_13", "2025_15",
                      "2025_16", "2025_17", "2025_19", "2025_20"}, sorted(differ)
    assert all("corrects tyre_allocations.csv" in v[4] for v in ours.values() if v[3] in differ)
    assert {v[3] for k, v in ours.items() if k not in user} == {"2025_6"}
