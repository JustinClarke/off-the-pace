"""Replay a scratch car term into the scratch dev copy, then compute V1 + coverage.
usage: run_struct.py <name> [--full]"""
import sys, json, time, subprocess
from pathlib import Path
import duckdb, numpy as np, pandas as pd
import os
S = Path(os.environ.get("ERAS_DIR", Path(__file__).parent))  # holds dev.duckdb (a scratch copy) and car_<name>.parquet
REPO = Path("/Users/justin/github/off-the-pace")
name = sys.argv[1]; full = "--full" in sys.argv
db = S / "dev.duckdb"
t0 = time.time()
subprocess.run([str(REPO / ".venv/bin/python"), str(REPO / "_roadmap/_fixes/_evidence/wi-16-2026-09-30/eras/replay_isolation_v2.py"),
                str(db), str(S / f"car_{name}.parquet")], check=True, capture_output=True)
sys.path.insert(0, str(REPO / "scripts"))
import validate_driver_isolation as V
v = V.DriverIsolationValidator(db_path=str(db))
if full:
    v.run_all_validations()
    od = S / name; od.mkdir(exist_ok=True)
    v.write_validation_json(str(od)); v.write_report(str(od))
    res = v.results
    v1 = res["V1"]; ms = res["method_scores"]
else:
    v1 = v._validate_v1(); ms = None
cov = v.q("SELECT race_year, AVG((pure_skill_gain_s IS NOT NULL)::INT) AS share FROM fct_driver_isolation_race GROUP BY 1 ORDER BY 1")
b = v1["V1b"]
print(f"== {name}  ({time.time()-t0:.0f}s)")
print("  pure coverage by season:", dict(zip(cov.race_year, cov.share.round(3))))
print(f"  V1a {v1['V1a_pure']['status']} {v1['V1a_pure']['median_spearman']}")
print(f"  V1b {b['status']} median {b['median_pearson']}; rule check {b['rule_change_check']}")
for k, d in b["per_pair"].items():
    print(f"     {k}: r={d['pearson'] if d['pearson'] is None else round(d['pearson'],3)} n={d['n_drivers']}")
print(f"  V1c {v1['V1c']['status']} ratio={v1['V1c'].get('ratio')}")
if ms:
    for r in ("pure", "relative"):
        m = ms[r]; print(f"  method {r}: strict {m['method_score']} {m['grade']}; before rule {m['weighted_score_before_critical_rule']:.3f}; test-level {m['test_level_reading']}")
json.dump({"V1": v1, "coverage": dict(zip(map(int, cov.race_year), map(float, cov.share)))}, open(S / f"v1_{name}.json", "w"), default=str, indent=1)
