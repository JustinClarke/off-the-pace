"""Feature loading, splitting, encoding, fingerprinting, and the forward-window leakage audit.

The spine of the ML layer: every leakage guard lives here or is enforced against the
FeatureBundle this module returns. Reads the warehouse READ-ONLY.

Public API:
    resolve_holdout_season(con) -> int
    load_features(duckdb_path, target=None, *, persist_encoders=False) -> FeatureBundle
    audit_forward_window(manifest_path) -> list[str]      # [] == clean

CLI (`python -m ml.src.features --check`): audit-only mode for CI-runs the
forward-window audit, asserts the leakage guards, prints the season split, and
exits non-zero on any violation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from ml.src import schema as S

ENCODERS_PATH = Path("ml/models/encoders.json")
MANIFEST_PATH = "transform/target/manifest.json"


@dataclass
class FeatureBundle:
    target_name: str | None
    X_train: pd.DataFrame
    y_train: pd.Series | None
    X_holdout: pd.DataFrame
    y_holdout: pd.Series | None
    groups_train: pd.Series            # race_year, for season-grouped TimeSeriesSplit
    meta_train: pd.DataFrame           # IDENTIFIER_COLUMNS (+ remaining_stint_life_laps if synthesised)
    meta_holdout: pd.DataFrame
    encoders: dict[str, dict[str, int]]
    fingerprint: str
    feature_columns: list[str]
    holdout_season: int
    training_seasons: list[int] = field(default_factory=list)


# ─── Holdout resolution (data-derived; no literal year, ever) ───────────────────
def resolve_holdout_season(con: duckdb.DuckDBPyConnection) -> int:
    """Holdout = next (not-yet-ingested) season = latest ingested + 1.
    2025 today (absent from the mart); becomes live the moment 2025 ingests."""
    return int(con.execute(f"SELECT MAX(race_year) + 1 FROM {S.MART}").fetchone()[0])


# ─── Encoding helpers ───────────────────────────────────────────────────────────
def _build_encoders(train_df: pd.DataFrame) -> dict[str, dict[str, int]]:
    """Deterministic ordinal maps from TRAINING data only: sorted unique non-null
    values → 0..k-1. NULL / unseen-at-scoring map to MISSING_ORDINAL downstream."""
    encoders: dict[str, dict[str, int]] = {}
    for col in S.CATEGORICAL_COLUMNS:
        values = sorted(v for v in train_df[col].dropna().unique())
        encoders[col] = {str(v): i for i, v in enumerate(values)}
    return encoders


def _encode_frame(df: pd.DataFrame, encoders: dict[str, dict[str, int]]) -> pd.DataFrame:
    """Return a float32 feature frame (FEATURE_COLUMNS order). Continuous keep NaN
    (native-NaN); categoricals map to ordinal with MISSING_ORDINAL sentinel for
    NULL/unseen; booleans → 1.0/0.0 with NULL → NaN."""
    out = pd.DataFrame(index=df.index)
    for col in S.FEATURE_COLUMNS:
        if col in S.CATEGORICAL_COLUMNS:
            mapped = df[col].astype("object").map(encoders[col])
            out[col] = mapped.fillna(S.MISSING_ORDINAL).astype("float32")
        elif col in S.BOOLEAN_COLUMNS:
            out[col] = df[col].map({True: 1.0, False: 0.0}).astype("float32")
        else:
            out[col] = pd.to_numeric(df[col], errors="coerce").astype("float32")
    return out


def _fingerprint(X: pd.DataFrame, training_seasons: list[int], feature_cols: list[str]) -> str:
    """SHA256 over the row-sorted encoded matrix + season split + feature list.
    Deterministic across runs/machines → gates the twice-run determinism proof."""
    ordered = X.reindex(columns=feature_cols).to_numpy(dtype=np.float32)
    ordered = ordered[np.lexsort(ordered.T[::-1])]  # canonical row order, NaN-stable
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(ordered).tobytes())
    h.update(json.dumps({"seasons": training_seasons, "features": feature_cols}).encode())
    return h.hexdigest()


def _resolve_target(df: pd.DataFrame, target: str | None) -> pd.Series | None:
    if target is None:
        return None
    spec = S.TARGET_BY_NAME[target]
    if spec.family == "cliff_classifier":
        label_to_int = {lab: i for i, lab in enumerate(S.CLIFF_CLASS_LABELS)}
        return df[spec.source_column].map(label_to_int)            # NaN where label NULL
    return pd.to_numeric(df[spec.source_column], errors="coerce")  # degradation / stint-life


# ─── Main loader ─────────────────────────────────────────────────────────────────
def load_features(
    duckdb_path: str = S.DUCKDB_PATH,
    target: str | None = None,
    *,
    persist_encoders: bool = False,
) -> FeatureBundle:
    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        holdout_season = resolve_holdout_season(con)
        all_seasons = [int(r[0]) for r in con.execute(
            f"SELECT DISTINCT race_year FROM {S.MART} ORDER BY 1").fetchall()]
        training_seasons = [y for y in all_seasons if y < holdout_season]

        train_df = con.execute(
            f"SELECT * FROM {S.MART} WHERE is_training_eligible AND race_year < {holdout_season}"
        ).df()
        holdout_df = con.execute(
            f"SELECT * FROM {S.MART} WHERE race_year = {holdout_season}"
        ).df()
        stint_len = con.execute(
            f"SELECT stint_id, stint_length_laps FROM {S.STINT_FEATURES}"
        ).df()
    finally:
        con.close()

    # Synthesise the stint-life target (full coverage verified: 0 unmatched).
    for d in (train_df, holdout_df):
        merged = d.merge(stint_len, on="stint_id", how="left")
        d["stint_length_laps"] = merged["stint_length_laps"].to_numpy()
        d[S.STINT_LIFE_TARGET] = np.clip(
            d["stint_length_laps"]-d["lap_in_stint"], 0, None)

    encoders = _build_encoders(train_df)
    if persist_encoders:
        ENCODERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        ENCODERS_PATH.write_text(json.dumps(encoders, indent=2, sort_keys=True))

    X_train_full = _encode_frame(train_df, encoders)
    X_holdout_full = _encode_frame(holdout_df, encoders)

    # PER_TARGET_FEATURE_MASK (belt & braces masked cols are not in FEATURE_COLUMNS).
    feature_cols = list(S.FEATURE_COLUMNS)
    if target is not None:
        masked = S.PER_TARGET_FEATURE_MASK.get(S.TARGET_BY_NAME[target].family, frozenset())
        feature_cols = [c for c in feature_cols if c not in masked]
    X_train = X_train_full[feature_cols].copy()
    X_holdout = X_holdout_full[feature_cols].copy()

    y_train = _resolve_target(train_df, target)
    y_holdout = _resolve_target(holdout_df, target)

    meta_cols = list(S.IDENTIFIER_COLUMNS) + [S.STINT_LIFE_TARGET, "stint_length_laps"]
    meta_train = train_df[meta_cols].reset_index(drop=True)
    meta_holdout = holdout_df[meta_cols].reset_index(drop=True)
    groups_train = train_df["race_year"].reset_index(drop=True)

    X_train = X_train.reset_index(drop=True)
    X_holdout = X_holdout.reset_index(drop=True)
    if y_train is not None:
        y_train = y_train.reset_index(drop=True)
    if y_holdout is not None:
        y_holdout = y_holdout.reset_index(drop=True)

    # L0-7: drop training rows whose (per-target) y is NULL XGBoost errors on NaN in y.
    if target is not None and y_train is not None:
        keep = y_train.notna().to_numpy()
        X_train, y_train = X_train[keep].reset_index(drop=True), y_train[keep].reset_index(drop=True)
        groups_train = groups_train[keep].reset_index(drop=True)
        meta_train = meta_train[keep].reset_index(drop=True)

    fingerprint = _fingerprint(X_train, training_seasons, feature_cols)

    return FeatureBundle(
        target_name=target, X_train=X_train, y_train=y_train,
        X_holdout=X_holdout, y_holdout=y_holdout, groups_train=groups_train,
        meta_train=meta_train, meta_holdout=meta_holdout, encoders=encoders,
        fingerprint=fingerprint, feature_columns=feature_cols,
        holdout_season=holdout_season, training_seasons=training_seasons,
    )


def load_scoring_frame(duckdb_path: str = S.DUCKDB_PATH):
    """Encode EVERY lap (training + holdout, eligible + ineligible) for full-dataset
    scoring by predict.py. Encoders are rebuilt from the training subset (identical to
    load_features, deterministic). Returns (X_all, meta, encoders, holdout_season)."""
    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        holdout_season = resolve_holdout_season(con)
        train_df = con.execute(
            f"SELECT * FROM {S.MART} WHERE is_training_eligible AND race_year < {holdout_season}"
        ).df()
        all_df = con.execute(f"SELECT * FROM {S.MART}").df()
    finally:
        con.close()

    encoders = _build_encoders(train_df)
    X_all = _encode_frame(all_df, encoders)[list(S.FEATURE_COLUMNS)].reset_index(drop=True)
    meta = all_df[["lap_id", "stint_id", "race_year", "circuit_key",
                   "is_training_eligible"]].reset_index(drop=True)
    return X_all, meta, encoders, holdout_season


# ─── Forward-window audit (the test that earns its keep §5.2 item 8) ───────────
import sqlglot  # noqa: E402
from sqlglot import exp  # noqa: E402


def _expr_is_forward_looking(node: exp.Expression) -> bool:
    """True if the expression subtree peeks forward: a LEAD(), or a window frame
    bound of FOLLOWING (LAG / PRECEDING / CURRENT ROW are backward → fine)."""
    if list(node.find_all(exp.Lead)):
        return True
    for spec in node.find_all(exp.WindowSpec):
        if spec.args.get("start_side") == "FOLLOWING" or spec.args.get("end_side") == "FOLLOWING":
            return True
    return False


def _alias_definitions(compiled_sql_by_model: dict[str, str]) -> dict[str, list[exp.Expression]]:
    """Map every output alias → list of defining expressions across all lineage models."""
    defs: dict[str, list[exp.Expression]] = {}
    for sql in compiled_sql_by_model.values():
        try:
            tree = sqlglot.parse_one(sql, dialect="duckdb")
        except Exception:
            continue
        for select in tree.find_all(exp.Select):
            for proj in select.expressions:
                alias = proj.alias_or_name
                inner = proj.this if isinstance(proj, exp.Alias) else proj
                if alias:
                    defs.setdefault(alias, []).append(inner)
    return defs


def audit_forward_window(manifest_path: str = MANIFEST_PATH) -> list[str]:
    """For each FEATURE_COLUMNS member, resolve its defining expression(s) by
    walking the compiled mart + all ancestor int_*/stg_* models (following bare
    column passthroughs/renames), and reject any forward-looking window.
    Returns a list of violation strings ([] == clean)."""
    manifest = json.loads(Path(manifest_path).read_text())
    nodes = manifest["nodes"]
    mart_uid = next(uid for uid, n in nodes.items()
                    if n.get("name") == S.MART and n.get("resource_type") == "model")

    # BFS the mart's model ancestors via parent_map; collect compiled SQL.
    parent_map = manifest.get("parent_map", {})
    lineage, frontier = set(), [mart_uid]
    while frontier:
        uid = frontier.pop()
        if uid in lineage or uid not in nodes:
            continue
        lineage.add(uid)
        frontier.extend(parent_map.get(uid, []))
    compiled = {
        uid: nodes[uid].get("compiled_code") or nodes[uid].get("raw_code") or ""
        for uid in lineage if nodes[uid].get("resource_type") == "model"
    }

    defs = _alias_definitions(compiled)
    violations: list[str] = []
    for col in S.FEATURE_COLUMNS:
        seen: set[str] = set()
        frontier = [col]
        forward_hit = False
        while frontier:
            name = frontier.pop()
            if name in seen:
                continue
            seen.add(name)
            for expr in defs.get(name, []):
                if _expr_is_forward_looking(expr):
                    forward_hit = True
                    break
                # follow bare column ref / rename chains one hop at a time
                if isinstance(expr, exp.Column) and expr.name and expr.name != name:
                    frontier.append(expr.name)
            if forward_hit:
                break
        if forward_hit:
            violations.append(f"forward-looking definition for feature '{col}'")
    return violations


# ─── CLI: --check (CI audit mode) ────────────────────────────────────────────────
def _check(duckdb_path: str, manifest_path: str) -> int:
    problems: list[str] = []

    fw = audit_forward_window(manifest_path)
    problems += fw
    print(f"[forward-window audit] {'CLEAN' if not fw else 'VIOLATIONS: ' + '; '.join(fw)}")

    bundle = load_features(duckdb_path, target="degradation_regressor_p50", persist_encoders=True)
    leaked = sorted(set(bundle.X_train.columns) & S.EXCLUDED_LEAKAGE_COLUMNS)
    if leaked:
        problems.append(f"leaked columns in X: {leaked}")
    print(f"[leakage guard] {'CLEAN' if not leaked else 'LEAKED: ' + str(leaked)} "
          f"({len(bundle.feature_columns)} features)")

    # Unseen holdout categoricals (hard error per R4) only meaningful once holdout populated.
    unseen: list[str] = []
    for col in S.CATEGORICAL_COLUMNS:
        if len(bundle.X_holdout):
            train_vals = set(bundle.encoders[col].values())
            holdout_vals = set(bundle.X_holdout[col].dropna().unique())-{S.MISSING_ORDINAL}
            if holdout_vals-train_vals:
                unseen.append(col)
    if unseen:
        problems.append(f"unseen holdout categorical levels: {unseen}")

    print(f"[season split] train={bundle.training_seasons}  holdout={bundle.holdout_season} "
          f"(rows: train={len(bundle.X_train)}, holdout={len(bundle.X_holdout)})")
    print(f"[fingerprint] {bundle.fingerprint}")

    if problems:
        print("\nFAIL:\n -" + "\n -".join(problems), file=sys.stderr)
        return 1
    print("\nOK-features audit clean.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Feature audit / loader for the degradation models.")
    ap.add_argument("--check", action="store_true", help="CI audit mode (leakage + forward-window + split).")
    ap.add_argument("--duckdb", default=S.DUCKDB_PATH)
    ap.add_argument("--manifest", default=MANIFEST_PATH)
    args = ap.parse_args()
    if args.check:
        return _check(args.duckdb, args.manifest)
    bundle = load_features(args.duckdb)
    print(f"Loaded {len(bundle.X_train)} training rows, {len(bundle.feature_columns)} features.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
