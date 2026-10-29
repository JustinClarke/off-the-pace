"""Tests for the WC-10 input data gate. Temporary files only; no real data."""

import unicodedata
from pathlib import Path

from tasks.wake_calibration import data_gate as G


def _make(root: Path, name: str, data: bytes) -> Path:
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def test_nfc_and_nfd_names_give_the_same_digest(tmp_path):
    name = "são_paulo.parquet"
    a, b = tmp_path / "a", tmp_path / "b"
    pa = _make(a, unicodedata.normalize("NFC", name), b"x")
    pb = _make(b, unicodedata.normalize("NFD", name), b"x")
    assert G.digest_lines(a, [pa]) == G.digest_lines(b, [pb])


def test_content_change_changes_digest_and_order_does_not(tmp_path):
    f1, f2 = _make(tmp_path, "a.parquet", b"1"), _make(tmp_path, "b.parquet", b"2")
    d = G.digest_lines(tmp_path, [f1, f2])
    assert d == G.digest_lines(tmp_path, [f2, f1])
    f2.write_bytes(b"3")
    assert G.digest_lines(tmp_path, [f1, f2]) != d


def test_pass_table_digest_counts_files(tmp_path):
    _make(tmp_path, "pass_table_2022.parquet", b"p")
    _make(tmp_path, "other.csv", b"c")
    n, _, per = G.pass_table_digest(tmp_path)
    assert n == 1 and list(per) == ["pass_table_2022.parquet"]


def test_restart_rule():
    assert G.run_state(False, False) == G.RESTARTABLE and G.is_restartable(False, False)
    assert G.run_state(True, False) == G.RUNNING
    assert G.run_state(True, True) == G.COMPLETED
    assert G.run_state(False, True) == G.BURNED and not G.is_restartable(False, True)


def test_dry_run_decodes_no_parquet_column(tmp_path, monkeypatch, capsys):
    import duckdb
    import pyarrow.parquet as pq

    def boom(*a, **k):
        raise AssertionError("a parquet/duckdb read was attempted")

    for obj, names in ((pq, ("read_table", "ParquetFile", "read_metadata", "ParquetDataset")), (duckdb, ("connect", "sql", "query"))):
        for n in names:
            monkeypatch.setattr(obj, n, boom)
    import pandas as pd
    monkeypatch.setattr(pd, "read_parquet", boom)
    b = tmp_path / "bronze"
    for t in ("laps", "telemetry", "weather", "results"):
        _make(b, f"{t}/season=2022/race=x/{t}.parquet", t.encode())
    pdir = tmp_path / "pt"
    _make(pdir, "pass_table_2022.parquet", b"p")
    import hashlib
    (pdir / "SHA256SUMS").write_text(hashlib.sha256(b"p").hexdigest() + "  pass_table_2022.parquet\n")
    sdir = tmp_path / "sc"
    _make(sdir, "sidecar_2022.parquet", b"s")
    (sdir / "SHA256SUMS").write_text(hashlib.sha256(b"s").hexdigest() + "  sidecar_2022.parquet\n")
    exp = _expected(b, pdir, sdir)
    assert G.main(["--bronze", str(b), "--pass-table-dir", str(pdir), "--sidecar-dir", str(sdir)], exp) == 0
    out = capsys.readouterr().out
    assert "check 2 scoped bronze (laps+telemetry+weather): PASS  files 3" in out and "outcome columns read: none" in out
    assert out.count("PASS") == 5 and "FAIL" not in out


def test_scope_excludes_other_tables_and_sums_check(tmp_path):
    for t in ("laps", "results"):
        _make(tmp_path, f"{t}/season=2022/race=x/{t}.parquet", b"1")
    assert G.scoped_bronze_digest(tmp_path)[0] == 1
    _make(tmp_path, "pass_table_2022.parquet", b"p")
    (tmp_path / "SHA256SUMS").write_text("0" * 64 + "  pass_table_2022.parquet\n")
    _, _, per = G.pass_table_digest(tmp_path)
    assert G.sha256sums_mismatches(tmp_path, per) == ["pass_table_2022.parquet"]


def _expected(b, pdir, sdir):
    """Registered digests for the temporary fixture, computed with the gate's own functions."""
    from tasks.wake_calibration import run_wc03 as R
    return {
        "pass_table": G.pass_table_digest(pdir)[:2],
        "scoped_bronze": G.scoped_bronze_digest(b),
        "sidecar": G.sidecar_digest(sdir)[:2],
        "full_bronze": R.bronze_digest(b),
    }


def _fixture(tmp_path):
    import hashlib
    b = tmp_path / "bronze"
    for t in ("laps", "telemetry", "weather"):
        _make(b, f"{t}/season=2022/race=são/{t}.parquet", t.encode())
    pdir, sdir = tmp_path / "pt", tmp_path / "sc"
    for d, pre in ((pdir, "pass_table_"), (sdir, "sidecar_")):
        sums = ""
        for y in (2022, 2023):
            _make(d, f"{pre}{y}.parquet", f"{pre}{y}".encode())
            sums += hashlib.sha256(f"{pre}{y}".encode()).hexdigest() + f"  {pre}{y}.parquet\n"
        (d / "SHA256SUMS").write_text(sums + "0" * 64 + "  races.csv\n")
    return b, pdir, sdir, _expected(b, pdir, sdir)


def _run(b, pdir, sdir, exp, capsys):
    rc = G.main(["--bronze", str(b), "--pass-table-dir", str(pdir), "--sidecar-dir", str(sdir)], exp)
    return rc, capsys.readouterr().out


def test_fixture_passes_all_four(tmp_path, capsys):
    rc, out = _run(*_fixture(tmp_path), capsys)
    assert rc == 0 and "GATE: PASS" in out and out.count("check") == 4 and out.count(": PASS") == 5


def test_wrong_byte_fails_each_check(tmp_path, capsys):
    cases = {
        "check 1": lambda b, p, s: (p / "pass_table_2022.parquet").write_bytes(b"X"),
        "check 2": lambda b, p, s: next((b / "laps").rglob("*.parquet")).write_bytes(b"X"),
        "check 3": lambda b, p, s: (s / "sidecar_2022.parquet").write_bytes(b"X"),
        "check 4": lambda b, p, s: next((b / "laps").rglob("*.parquet")).write_bytes(b"X"),
    }
    for name, mutate in cases.items():
        sub = tmp_path / name.replace(" ", "")
        sub.mkdir()
        b, p, s, exp = _fixture(sub)
        mutate(b, p, s)
        rc, out = _run(b, p, s, exp, capsys)
        assert rc == 1 and "GATE: FAIL" in out, name
        assert f"{name}" in out and any(l.startswith(name) and ": FAIL" in l for l in out.splitlines()), name


def test_missing_file_fails_checks_1_and_3(tmp_path, capsys):
    b, p, s, exp = _fixture(tmp_path)
    (p / "pass_table_2023.parquet").unlink()
    (s / "sidecar_2023.parquet").unlink()
    rc, out = _run(b, p, s, exp, capsys)
    lines = {l.split(":")[0]: l for l in out.splitlines() if l.startswith("check")}
    assert rc == 1 and ": FAIL" in lines["check 1 pass table"] and ": FAIL" in lines["check 3 sidecar"]


def test_missing_sha256sums_fails(tmp_path, capsys):
    b, p, s, exp = _fixture(tmp_path)
    (s / "SHA256SUMS").unlink()
    rc, out = _run(b, p, s, exp, capsys)
    assert rc == 1 and "check 3 sidecar: FAIL" in out and "SHA256SUMS" in out


def test_nfd_name_does_not_fail_but_wrong_name_does(tmp_path, capsys):
    b, p, s, exp = _fixture(tmp_path)
    nfc = next((b / "laps").rglob("*.parquet"))
    nfd_dir = nfc.parent.parent / unicodedata.normalize("NFD", nfc.parent.name)
    if nfd_dir != nfc.parent:
        nfc.parent.rename(nfd_dir)
    rc, out = _run(b, p, s, exp, capsys)
    assert rc == 0, out  # NFD on disk digests identically (NFC-normalised paths)
    # a genuinely different name changes the digest and fails checks 2 and 4
    (nfd_dir / nfc.name).rename(nfd_dir / "other.parquet")
    rc, out = _run(b, p, s, exp, capsys)
    assert rc == 1 and "check 2" in out and "check 4 full bronze (run_wc03 file set): FAIL" in out


def test_sums_prefix_argument(tmp_path):
    (tmp_path / "SHA256SUMS").write_text("1" * 64 + "  sidecar_2022.parquet\n" + "2" * 64 + "  pass_table_2022.parquet\n")
    assert G.sha256sums_mismatches(tmp_path, {"sidecar_2022.parquet": "1" * 64}, "sidecar_") == []
    assert G.sha256sums_mismatches(tmp_path, {"sidecar_2022.parquet": "1" * 64}) == ["pass_table_2022.parquet", "sidecar_2022.parquet"]
