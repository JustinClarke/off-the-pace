"""Feature loading, splitting, encoding, fingerprinting, and the forward-window leakage audit.

The spine of the ML layer: every leakage guard lives here or is enforced against the
FeatureBundle this module returns. Reads the warehouse READ-ONLY.

Public API:
    resolve_holdout_season(con) -> int
    load_features(duckdb_path, target=None, *, persist_encoders=False) -> FeatureBundle
    audit_forward_window(manifest_path) -> list[str]      # [] == clean
    audit_aggregation_scope(manifest_path) -> list[str]   # [] == clean
    survey_aggregation_scope(manifest_path) -> list[str]  # report-only, off-lineage

CLI (`python -m ml.src.features --check`): audit-only mode for CI-runs the
forward-window and aggregation-scope audits, asserts the leakage guards, prints
the season split, and exits non-zero on any violation.
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
    censoring_variant: str = "standard",
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
        # Load stint_end_cause if using 10b (cause-specific) censoring variant
        stint_cols = "stint_id, stint_length_laps, is_censored_stint"
        if censoring_variant == "10b":
            stint_cols += ", stint_end_cause"
        stint_len = con.execute(
            f"SELECT {stint_cols} FROM {S.STINT_FEATURES}"
        ).df()
    finally:
        con.close()

    # Synthesise the stint-life target (full coverage verified: 0 unmatched).
    # is_censored_stint rides along: the target alone cannot say whether a 0 means
    # "the tyre was done" or "the race was". It is meta, never a feature -- it is
    # not in FEATURE_COLUMNS and test_features.py asserts that it never becomes one.
    #
    # 10b variant (work/10-competing-risks.md): treat non-green endings as censored
    # to isolate the tyre-limit distribution from the deployment-timing distribution.
    for d in (train_df, holdout_df):
        merged = d.merge(stint_len, on="stint_id", how="left")
        d["stint_length_laps"] = merged["stint_length_laps"].to_numpy()

        if censoring_variant == "10b":
            # Treat only 'green_pit' as uncensored; everything else (sc_pit, vsc_pit, red,
            # race_end, retirement) is censored. NULL stint_end_cause: preserve original
            # is_censored_stint (2 stints have NULL cause but is_censored_stint=TRUE).
            d[S.STINT_LIFE_CENSOR_COLUMN] = (
                ((merged["stint_end_cause"] != "green_pit") &
                 merged["stint_end_cause"].notna())
                | merged[S.STINT_LIFE_CENSOR_COLUMN].fillna(False)
            ).to_numpy(dtype=bool)
        else:
            # Standard censoring: race_end and retirement (already marked in original)
            d[S.STINT_LIFE_CENSOR_COLUMN] = (
                merged[S.STINT_LIFE_CENSOR_COLUMN].fillna(False).to_numpy(dtype=bool))

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

    meta_cols = list(S.IDENTIFIER_COLUMNS) + [
        S.STINT_LIFE_TARGET, "stint_length_laps", S.STINT_LIFE_CENSOR_COLUMN]
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


# ─── Forward-window audit ───────────────────────────────────────────────────────
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


_INEQUALITIES = (exp.GT, exp.GTE, exp.LT, exp.LTE)


def _self_join_inequality(select: exp.Select) -> str | None:
    """Describe a row-ordering self-join in this SELECT's scope, else None.

    A window is not the only way to see another row. `FROM mart f JOIN mart a ON
    f.stint_id = a.stint_id AND f.lap_in_stint > a.lap_in_stint` scans a whole
    horizon with no LEAD() and no FOLLOWING frame anywhere in the projection — the
    forward reach lives in the join predicate, which the expression walker never
    reads. That is exactly how fct_cliff_prediction_features builds its cliff scan,
    and a *feature* built the same way would have passed this audit silently.

    Signature: an inequality between two columns of the SAME name under DIFFERENT
    qualifiers, in a JOIN ON or the WHERE clause. Direction is deliberately not
    inferred — which alias is "the current row" is a naming convention, not
    something the tree says — so both `f.x > a.x` and `f.x < a.x` are reported and
    a human decides. A backward self-join is not leakage, but it is a
    row-referencing definition that this audit exists to surface.
    """
    predicates = [j.args["on"] for j in select.args.get("joins") or [] if j.args.get("on")]
    where = select.args.get("where")
    if where is not None:
        predicates.append(where)
    for pred in predicates:
        for cmp_type in _INEQUALITIES:
            for node in pred.find_all(cmp_type):
                left, right = node.this, node.expression
                if not (isinstance(left, exp.Column) and isinstance(right, exp.Column)):
                    continue
                if left.name != right.name or not left.name:
                    continue
                lq, rq = left.table, right.table
                if lq and rq and lq != rq:
                    return f"self-join inequality {lq}.{left.name} {node.key.upper()} {rq}.{right.name}"
    return None


def _alias_definitions(
    compiled_sql_by_model: dict[str, str],
) -> tuple[dict[str, list[tuple[exp.Expression, str | None]]], list[str]]:
    """Map every output alias → list of (defining expression, enclosing-scope note),
    plus the models whose SQL would not parse.

    The note is a self-join description when the SELECT that produced the alias
    reaches across rows through its join predicate rather than through a window,
    and None otherwise. Unparsed models are returned rather than swallowed: a model
    this walker cannot read is a hole in the audit, and the caller turns it into a
    violation instead of letting it read as clean."""
    defs: dict[str, list[tuple[exp.Expression, str | None]]] = {}
    unparsed: list[str] = []
    for uid, sql in compiled_sql_by_model.items():
        try:
            tree = sqlglot.parse_one(sql, dialect="duckdb")
        except Exception:
            unparsed.append(uid.split(".")[-1])
            continue
        for select in tree.find_all(exp.Select):
            scope_note = _self_join_inequality(select)
            for proj in select.expressions:
                alias = proj.alias_or_name
                inner = proj.this if isinstance(proj, exp.Alias) else proj
                if alias:
                    defs.setdefault(alias, []).append((inner, scope_note))
    return defs, unparsed


def _model_sql(node: dict, target_dir: Path) -> str:
    """Compiled SQL for one dbt model node.

    `manifest.json` only carries `compiled_code` when it was written by a command
    that compiled (`dbt run` / `dbt build` / `dbt compile`); a `dbt parse` manifest
    leaves it null. Falling straight through to `raw_code` looks harmless and is
    not: raw_code is Jinja (`{{ config(...) }}`, `{{ ref(...) }}`), sqlglot cannot
    parse it, and every model then lands in the caller's `except: continue`. So the
    on-disk compiled file is tried before that fallback."""
    code = node.get("compiled_code")
    if code:
        return code
    for rel in (node.get("compiled_path"),
                f"compiled/{node.get('package_name')}/{node.get('original_file_path')}"):
        if rel:
            path = target_dir / rel
            if path.exists():
                return path.read_text()
    return node.get("raw_code") or ""


def audit_forward_window(manifest_path: str = MANIFEST_PATH) -> list[str]:
    """For each FEATURE_COLUMNS member, resolve its defining expression(s) by
    walking the compiled mart + all ancestor int_*/stg_* models (following bare
    column passthroughs/renames), and reject any forward-looking window.
    Returns a list of violation strings ([] == clean)."""
    manifest = json.loads(Path(manifest_path).read_text())
    target_dir = Path(manifest_path).parent
    nodes = manifest["nodes"]
    compiled = {uid: _model_sql(nodes[uid], target_dir)
                for uid in _mart_lineage(manifest)}

    defs, unparsed = _alias_definitions(compiled)

    # Coverage first. An audit that resolved nothing returns [] — indistinguishable
    # from an audit that resolved everything and found nothing wrong. That is not a
    # hypothetical: while `compiled_code` was null in a `dbt parse` manifest this
    # walker parsed zero of 21 lineage models, resolved 0 of 42 features, and
    # reported CLEAN on every run. Coverage is asserted before the finding is
    # trusted, so an unreadable lineage fails loudly instead of passing silently.
    violations: list[str] = []
    if unparsed:
        violations.append(
            f"audit could not parse {len(unparsed)} lineage model(s): {sorted(unparsed)} "
            f"— the audit is blind to them, so a CLEAN result would be meaningless")
    undefined = [c for c in S.FEATURE_COLUMNS if c not in defs]
    if undefined:
        violations.append(
            f"audit resolved no definition for {len(undefined)}/{len(S.FEATURE_COLUMNS)} "
            f"features: {undefined} — check that transform/target/ holds compiled SQL "
            f"(dbt run / dbt build / dbt compile), not just a parse manifest")

    for col in S.FEATURE_COLUMNS:
        seen: set[str] = set()
        frontier = [col]
        reason: str | None = None
        while frontier and reason is None:
            name = frontier.pop()
            if name in seen:
                continue
            seen.add(name)
            for expr, scope_note in defs.get(name, []):
                if _expr_is_forward_looking(expr):
                    reason = f"forward window in the definition of '{name}'"
                    break
                if scope_note is not None:
                    reason = f"'{name}' is defined in a scope with a {scope_note}"
                    break
                # follow bare column ref / rename chains one hop at a time
                if isinstance(expr, exp.Column) and expr.name and expr.name != name:
                    frontier.append(expr.name)
        if reason is not None:
            violations.append(f"forward-looking definition for feature '{col}': {reason}")
    return violations


# ─── Aggregation-scope audit ────────────────────────────────────────────────────
# A forward reach does not need a window function, and it does not need a join
# predicate either. It can live in the SCOPE OF A GROUP BY, where neither of the
# two checks above looks: `GROUP BY circuit_slug` over every ingested season pools
# 2024 into what a 2018 row sees, and `GROUP BY stint_id` hands a lap the median of
# laps that had not yet run. Neither construct has a LEAD, a FOLLOWING frame or a
# self-join inequality anywhere in it, so `audit_forward_window` read both as clean
# -- which it did, for as long as they existed.
#
# The rule: every GROUP BY in a model feeding FEATURE_COLUMNS must pin the time
# coordinate to at most one lap -- the label's grain, since the mart is one row per
# valid race lap -- or be declared in that model's `schema.yml`. Extra keys only
# ever shrink a group, so the test is monotone: adding keys never breaks pinning.
#
# The declaration is data, not a comment. The checker reads it, refuses a blank
# reason, refuses a `known_leak` with no item to fix it, and fails on an exemption
# that no longer matches any aggregation in the model -- so an exemption cannot rot
# quietly while the SQL moves under it.

# `race_id` pins a race on its own, with no season key alongside it. VERIFIED, not
# assumed: across the ingested 2018-2024 seasons it is globally unique -- 147 ids in
# fct_lap_residuals, 149 in int_stint_geometry and fct_stint_features, zero reused
# across seasons in any of the three. `circuit_id` / `circuit_key` / `circuit_slug` /
# `track_id` are deliberately NOT race keys even beside a season key: 2020 ran two
# races at the Red Bull Ring and two at Silverstone, so (season, venue) does not
# identify a race.
_LAP_ID_KEYS = frozenset({"lap_id"})
_RACE_KEYS = frozenset({"race_id", "race_key"})
_STINT_KEYS = frozenset({"stint_id"})
_LAP_ORDINAL_KEYS = frozenset({"lap_number", "lap_in_stint"})
_SEASON_KEYS = frozenset({"race_year", "season"})
_TIME_KEYS = _LAP_ID_KEYS | _RACE_KEYS | _STINT_KEYS | _LAP_ORDINAL_KEYS | _SEASON_KEYS

_EXEMPTION_META_KEY = "aggregation_scope_exemptions"
_EXEMPTION_STATUSES = ("accepted", "known_leak")


def _pins_one_lap(names: set[str]) -> bool:
    """True if this grouping key set confines a group to at most one lap."""
    if names & _LAP_ID_KEYS:
        return True
    if (names & _RACE_KEYS) and (names & _LAP_ORDINAL_KEYS):
        return True
    if (names & _STINT_KEYS) and (names & _LAP_ORDINAL_KEYS):
        return True
    return False


def _scope_width(names: set[str]) -> str:
    """How far a non-pinning group reaches, narrowest first. This is the severity:
    the last case crosses the season split itself and so contaminates the CV folds,
    while the first two are point-in-time defects inside one race."""
    if names & _STINT_KEYS:
        return "pools the laps of one stint"
    if names & _RACE_KEYS:
        return "pools the laps of one race"
    if names & _SEASON_KEYS:
        return "pools the races of one season"
    return "pools every ingested season — this crosses the train/eval split"


def _passthrough_column(node: exp.Expression) -> exp.Column | None:
    """The column a projection passes through, after stripping wrappers that do not
    change which rows share a value: parentheses and casts. `CAST(lap_number AS
    INTEGER) AS lap_number` is the same key; `FLOOR(lap_number / 5.0) * 5.0` is not.
    Returns None when the projection computes something. (A cast that genuinely
    coarsens -- a float lap index truncated to int -- would be missed here; no time
    key in this warehouse is stored as a float, so the case does not arise.)"""
    while isinstance(node, (exp.Paren, exp.Alias, exp.Cast, exp.TryCast)):
        node = node.this
    return node if isinstance(node, exp.Column) else None


def _derived_aliases(tree: exp.Expression) -> set[str]:
    """Aliases in this model that are computed, not passed through.

    `FLOOR(lap_number / 5.0) * 5.0 AS lap_window` is a *coarsened* lap key: the
    group it makes spans five laps, four of which are in the future at the first
    one. Grouping on it must not count as grouping on a lap. The set is used to
    disqualify vocabulary names too, so aliasing a bucket back onto the name
    `lap_number` does not buy a pass.

    Model-wide rather than resolved per CTE, deliberately: a coarsened key anywhere
    in a model disqualifies that name in every GROUP BY in it. That over-flags if
    one CTE buckets a name another CTE passes through cleanly -- an over-flag costs
    a declaration, an under-flag costs the guard."""
    derived: set[str] = set()
    for select in tree.find_all(exp.Select):
        for proj in select.expressions:
            if isinstance(proj, exp.Alias) and _passthrough_column(proj.this) is None:
                derived.add(proj.alias_or_name)
    return derived


def _group_key_names(select: exp.Select, group: exp.Group) -> tuple[set[str], list[str]]:
    """(key names, printable keys) for one GROUP BY, with positional references
    (`GROUP BY 1, 2, 3`) resolved back to the projections they stand for."""
    names: set[str] = set()
    printable: list[str] = []
    projections = select.expressions
    for key in group.expressions:
        node = key
        if isinstance(key, exp.Literal) and key.is_int:
            index = int(key.name) - 1
            if 0 <= index < len(projections):
                node = projections[index]
        name = node.alias_or_name
        if name:
            names.add(name)
            printable.append(name)
        else:
            printable.append(node.sql(dialect="duckdb"))
    return names, sorted(printable)


def _aggregation_findings(
    name: str, sql: str,
) -> tuple[list[tuple[frozenset[str], str]], str | None]:
    """Every non-pinning GROUP BY in one model, as (key set, description) pairs.
    Second element is a parse error message, or None."""
    try:
        tree = sqlglot.parse_one(sql, dialect="duckdb")
    except Exception:
        return [], (f"aggregation-scope audit could not parse '{name}' — the audit is "
                    f"blind to it, so a CLEAN result would be meaningless")
    derived = _derived_aliases(tree)
    findings: list[tuple[frozenset[str], str]] = []
    for select in tree.find_all(exp.Select):
        group = select.args.get("group")
        if group is None:
            continue
        names, printable = _group_key_names(select, group)
        effective = {n for n in names if n not in derived}
        if _pins_one_lap(effective):
            continue
        note = ""
        coarsened = sorted((names & _TIME_KEYS) & derived)
        if coarsened:
            note = (f"; {', '.join(coarsened)} is a derived key here, not a "
                    f"pass-through time column, so it does not pin a lap")
        findings.append((
            frozenset(names),
            f"{name}: GROUP BY ({', '.join(printable)}) {_scope_width(effective)}{note}",
        ))
    return findings, None


def _exemptions(node: dict, model: str) -> tuple[dict[frozenset[str], dict], list[str]]:
    """Declared aggregation-scope exemptions for one model, keyed by grouping key
    set, plus the malformed ones. A declaration that does not say what it is
    accepting, or claims a known leak with nothing scheduled to fix it, is itself a
    violation -- the point of putting these in `schema.yml` is that someone signed
    them."""
    meta = (node.get("config") or {}).get("meta") or node.get("meta") or {}
    declared = meta.get(_EXEMPTION_META_KEY) or []
    parsed: dict[frozenset[str], dict] = {}
    problems: list[str] = []
    for entry in declared:
        keys = frozenset(entry.get("keys") or [])
        where = f"{model} exemption for GROUP BY ({', '.join(sorted(keys)) or '<no keys>'})"
        if not keys:
            problems.append(f"{where}: names no grouping keys")
            continue
        status = entry.get("status")
        if status not in _EXEMPTION_STATUSES:
            problems.append(f"{where}: status must be one of {list(_EXEMPTION_STATUSES)}, "
                            f"got {status!r}")
        if not (entry.get("reason") or "").strip():
            problems.append(f"{where}: needs a written reason")
        if status == "known_leak" and not (entry.get("fixed_by") or "").strip():
            problems.append(f"{where}: status 'known_leak' needs `fixed_by` naming the "
                            f"work item that repairs it")
        parsed[keys] = entry
    return parsed, problems


def _mart_lineage(manifest: dict) -> set[str]:
    """Model uids the mart is built from, the mart included."""
    nodes = manifest["nodes"]
    mart_uid = next(uid for uid, n in nodes.items()
                    if n.get("name") == S.MART and n.get("resource_type") == "model")
    parent_map = manifest.get("parent_map", {})
    lineage, frontier = set(), [mart_uid]
    while frontier:
        uid = frontier.pop()
        if uid in lineage or uid not in nodes:
            continue
        lineage.add(uid)
        frontier.extend(parent_map.get(uid, []))
    return {uid for uid in lineage if nodes[uid].get("resource_type") == "model"}


def audit_aggregation_scope(manifest_path: str = MANIFEST_PATH) -> list[str]:
    """Every GROUP BY in the mart's lineage must pin the time coordinate to at most
    one lap, or be declared in the model's `schema.yml` under
    `meta.aggregation_scope_exemptions`. Returns a list of violation strings
    ([] == clean).

    Scope is the whole model lineage rather than the models that define a feature's
    expression, deliberately. Resolving a feature to the models that build it means
    following the definition chain, and that chain stops at the first computed
    expression -- so a model reached only through arithmetic (`int_field_pace_curve`
    feeds `push_residual` by subtraction) would drop out of scope. Over-approximating
    costs a few declarations; under-approximating costs the guard."""
    manifest = json.loads(Path(manifest_path).read_text())
    target_dir = Path(manifest_path).parent
    nodes = manifest["nodes"]

    violations: list[str] = []
    for uid in sorted(_mart_lineage(manifest), key=lambda u: nodes[u]["name"]):
        node = nodes[uid]
        model = node["name"]
        findings, unparsed = _aggregation_findings(model, _model_sql(node, target_dir))
        if unparsed:
            violations.append(unparsed)
            continue
        declared, problems = _exemptions(node, model)
        violations += problems
        found_keys = {keys for keys, _ in findings}
        for keys, description in findings:
            if keys in declared:
                continue
            violations.append(
                f"undeclared aggregation scope — {description}. Add a lap key, or "
                f"declare it in schema.yml under meta.{_EXEMPTION_META_KEY} with "
                f"keys/status/reason")
        for keys in declared:
            if keys not in found_keys:
                violations.append(
                    f"stale exemption — {model} declares GROUP BY "
                    f"({', '.join(sorted(keys))}), which no longer appears in the "
                    f"model or now pins a lap. Delete it rather than leaving it to rot")
    return violations


def survey_aggregation_scope(manifest_path: str = MANIFEST_PATH) -> list[str]:
    """The same walk over the int_/stg_ models the mart does NOT currently read.

    Report-only, and separate from the gate on purpose. These models feed no feature
    today, so failing the build on them would force ~56 declarations that assert
    nothing anyone has to honour, and an exemption file that is mostly noise is worse
    than no exemption file. What this list is for: `int_corner_skill_residuals` and
    `int_sc_hazard_history` are both in it, and both are scheduled to enter the
    feature contract (items 02c and 02d). When they do, they arrive in
    `audit_aggregation_scope`'s scope automatically and the build stops until someone
    rules on them -- this survey is the advance notice that the ruling is coming."""
    manifest = json.loads(Path(manifest_path).read_text())
    target_dir = Path(manifest_path).parent
    nodes = manifest["nodes"]
    lineage = _mart_lineage(manifest)

    outside = [uid for uid, n in nodes.items()
               if n.get("resource_type") == "model" and uid not in lineage
               and n["name"].startswith(("int_", "stg_"))]
    findings: list[str] = []
    for uid in sorted(outside, key=lambda u: nodes[u]["name"]):
        node = nodes[uid]
        model_findings, unparsed = _aggregation_findings(
            node["name"], _model_sql(node, target_dir))
        if unparsed:
            findings.append(unparsed)
            continue
        findings += [description for _, description in model_findings]
    return findings

def _declared_known_leaks(manifest_path: str = MANIFEST_PATH) -> list[str]:
    """Exemptions in the feature lineage whose status is `known_leak`, one line each."""
    manifest = json.loads(Path(manifest_path).read_text())
    nodes = manifest["nodes"]
    leaks: list[str] = []
    for uid in sorted(_mart_lineage(manifest), key=lambda u: nodes[u]["name"]):
        node = nodes[uid]
        declared, _ = _exemptions(node, node["name"])
        for keys, entry in declared.items():
            if entry.get("status") == "known_leak":
                leaks.append(f"{node['name']} GROUP BY ({', '.join(sorted(keys))}) "
                             f"— fixed_by {entry.get('fixed_by')}")
    return leaks


# ─── CLI: --check (CI audit mode) ────────────────────────────────────────────────
def _check(duckdb_path: str, manifest_path: str) -> int:
    problems: list[str] = []

    fw = audit_forward_window(manifest_path)
    problems += fw
    print(f"[forward-window audit] {'CLEAN' if not fw else 'VIOLATIONS: ' + '; '.join(fw)}")

    agg = audit_aggregation_scope(manifest_path)
    problems += agg
    print(f"[aggregation-scope audit] {'CLEAN' if not agg else 'VIOLATIONS:'}")
    for violation in agg:
        print(f"  - {violation}")

    # Declared, not clean. A `known_leak` is a reach someone has ruled real and
    # scheduled, and it should stay visible every run rather than resting quietly in
    # a YAML file -- the count is the number of leaks currently shipping.
    leaks = _declared_known_leaks(manifest_path)
    if leaks:
        print(f"[aggregation-scope audit] {len(leaks)} declared known_leak(s) still in "
              f"the feature lineage:")
        for leak in leaks:
            print(f"  ! {leak}")

    survey = survey_aggregation_scope(manifest_path)
    print(f"[aggregation-scope survey] {len(survey)} non-pinning aggregation(s) in "
          f"int_/stg_ models outside the mart lineage (report-only; they enter the "
          f"audit above if a feature ever reads them)")

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
