"""AX-02: assistant_entities builds from a tiny warehouse + bronze fixture, and fails on an unnamed driver."""

from __future__ import annotations

import duckdb
import pytest

import assistant_entities as ae


def _fixture(tmp_path, with_zzz_name: bool):
    bronze = tmp_path / "bronze"
    for sub in ("reference/jolpica/driver_standings", "results", "schedule"):
        (bronze / sub).mkdir(parents=True)
    mem = duckdb.connect()
    mem.execute(f"""COPY (SELECT * FROM (VALUES ('PER','Sergio','Pérez',2024,1)) t(driver_code,given_name,family_name,season,round))
                    TO '{bronze}/reference/jolpica/driver_standings/a.parquet' (FORMAT PARQUET)""")
    rows = "('VER','Max','Verstappen','2024_1')" + (",('ZZZ','Zed','Zee','2024_1')" if with_zzz_name else "")
    mem.execute(f"""COPY (SELECT * FROM (VALUES {rows}) t(Abbreviation,FirstName,LastName,race_id))
                    TO '{bronze}/results/a.parquet' (FORMAT PARQUET)""")
    mem.execute(f"""COPY (SELECT * FROM (VALUES (1,'Bahrain Grand Prix','Sakhir','Bahrain',2024)) t(RoundNumber,EventName,Location,Country,season))
                    TO '{bronze}/schedule/a.parquet' (FORMAT PARQUET)""")
    w = duckdb.connect(str(tmp_path / "w.duckdb"))
    w.execute("CREATE TABLE dim_drivers AS SELECT * FROM (VALUES ('PER','11'),('VER','1'),('ZZZ','99')) t(driver_id, driver_number)")
    w.execute("CREATE TABLE fct_lap_residuals AS SELECT * FROM (VALUES ('PER','Red Bull Racing',2024),('VER','Red Bull Racing',2024),('ZZZ','Sauber',2024)) t(driver_id, constructor_id, race_year)")
    w.execute("CREATE TABLE dim_constructors AS SELECT * FROM (VALUES ('Red Bull Racing','red_bull_racing'),('Sauber','sauber')) t(constructor_id, constructor_lineage_id)")
    w.execute("CREATE TABLE dim_circuits AS SELECT * FROM (VALUES ('bahrain_grand_prix','bahrain_international_circuit','Bahrain International Circuit')) t(circuit_key, circuit_id, circuit_name)")
    w.execute("CREATE TABLE race_to_track AS SELECT * FROM (VALUES ('2024_1','bahrain_grand_prix')) t(race_id, track_id)")
    w.execute("CREATE TABLE dim_compounds_season AS SELECT * FROM (VALUES ('SOFT',2024)) t(compound_code, season)")
    w.execute("CREATE TABLE fct_stint_features AS SELECT * FROM (VALUES ('sc_pit'),(NULL)) t(stint_end_cause)")
    return w, bronze


ALIASES = {"driver": {"PER": ["Checo"]}, "constructor": {"sauber": ["Kick Sauber"]}}


def test_names_come_from_jolpica_then_fastf1(tmp_path):
    w, bronze = _fixture(tmp_path, with_zzz_name=True)
    rows, report = ae.build_rows(w, bronze=bronze, aliases=ALIASES)
    assert report["names_from_jolpica"] == 1 and report["names_from_fastf1_results"] == 2
    per = next(r for r in rows if r["domain"] == "driver" and r["code"] == "PER")
    assert per["display"] == "Sergio Pérez (PER)" and "Checo" in per["aliases"]
    race = next(r for r in rows if r["domain"] == "race")
    assert race["code"] == "2024_1" and race["extra"]["grand_prix"] == "Bahrain Grand Prix"


def test_fails_naming_a_driver_with_no_name(tmp_path):
    w, bronze = _fixture(tmp_path, with_zzz_name=False)
    with pytest.raises(ae.EntityBuildError, match="ZZZ"):
        ae.build_rows(w, bronze=bronze, aliases=ALIASES)


def test_unknown_alias_key_fails(tmp_path):
    w, bronze = _fixture(tmp_path, with_zzz_name=True)
    with pytest.raises(ae.EntityBuildError, match="driver:NOPE"):
        ae.build_rows(w, bronze=bronze, aliases={"driver": {"NOPE": ["x"]}})
