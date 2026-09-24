"""Replicates ml.src.features._check exactly, except persist_encoders=False.
The production CLI (`python -m ml.src.features --check`) calls
load_features(..., persist_encoders=True), which rewrites ml/models/encoders.json --
a tracked, shipped artefact. The audit is read-only, so the write is removed."""
import sys, json, hashlib
sys.path.insert(0, "/Users/justin/github/off-the-pace")
from ml.src import features as F
from ml.src import schema as S
man = F.MANIFEST_PATH
fw = F.audit_forward_window(man)
print("[forward-window audit]", "CLEAN" if not fw else fw)
agg = F.audit_aggregation_scope(man)
print("[aggregation-scope audit]", "CLEAN" if not agg else "VIOLATIONS")
for v in agg: print("  -", v)
leaks = F._declared_known_leaks(man)
print(f"[known_leaks] {len(leaks)}")
for l in leaks: print("  !", l)
survey = F.survey_aggregation_scope(man)
print(f"[survey] {len(survey)} off-lineage non-pinning aggregations")
for s in survey: print("   ~", s)
b = F.load_features(S.DUCKDB_PATH, target="degradation_regressor_p50", persist_encoders=False)
leaked = sorted(set(b.X_train.columns) & S.EXCLUDED_LEAKAGE_COLUMNS)
print("[leakage guard]", "CLEAN" if not leaked else leaked, f"({len(b.feature_columns)} features)")
print(f"[season split] train={b.training_seasons} holdout={b.holdout_season} rows train={len(b.X_train)} holdout={len(b.X_holdout)}")
print("[fingerprint]", b.fingerprint)
enc_disk = json.loads(open("/Users/justin/github/off-the-pace/ml/models/encoders.json").read())
print("[encoders equal to ml/models/encoders.json?]", enc_disk == b.encoders)
print("encoders:", b.encoders)
