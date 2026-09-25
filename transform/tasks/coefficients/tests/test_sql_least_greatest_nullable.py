"""
T29, lint half (WI-02, F39): no LEAST/GREATEST over a nullable expression in model SQL
goes unreviewed.

DuckDB's LEAST and GREATEST SKIP NULL arguments: LEAST(NULL, 10.0) is 10.0 and
GREATEST(NULL, 0.0) is 0.0. So a bound over an expression that can be NULL silently turns
"unknown" into the bound. That is F39 -- a NULL tyre age came out as exactly 10 s of wear
on 4,107 laps -- and the label clips had the same latent shape (a NULL residual would
have become +50 s). Range tests cannot see it, because the bound is always in range.

The rule, over every LEAST(...)/GREATEST(...) in transform/models and transform/macros:

  * accepted if every argument is NULL-proof by syntax: a numeric literal, a dbt var or a
    zero-argument macro call, COALESCE(..., <NULL-proof>), or arithmetic / CAST / ABS /
    SQRT / EXP / ROUND / nested LEAST-GREATEST built only from those (a division needs a
    non-zero literal divisor: DuckDB returns NULL for x / 0);
  * accepted if the call sits inside CASE blocks whose WHENs, before the call, test
    IS [NOT] NULL on every column its non-NULL-proof operands read -- the guard
    int_lap_thermal_proxy and the F39 fix use (a macro call inside the operands is not
    expanded: the macro's own body is linted in macros/);
  * otherwise it must be reviewed in transform/tests/least_greatest_nullable.allowlist.json
    with a verdict and a reason. A new unreviewed call fails; so does an allowlist entry
    that no longer matches a call (a stale review is not a review).

For a two-sided bound, clamp_or_null() (macros/clamp_or_null.sql) propagates NULL by
construction and needs no review.

What the lint cannot see: a WHERE clause or join that rules the NULL out (those sites are
reviewed as not_null, with the reason), and whether a guard's THEN branch is right.
assert_no_cap_valued_wear is the data-level check for the wear curve itself.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

TRANSFORM = Path(__file__).resolve().parents[3]
ALLOWLIST_PATH = TRANSFORM / "tests" / "least_greatest_nullable.allowlist.json"
SCANNED = ("models", "macros")
VERDICTS = {"not_null", "intended", "open"}

_CALL = re.compile(r"\b(LEAST|GREATEST)\s*\(", re.IGNORECASE)
_COMMENT = re.compile(r"--[^\n]*|\{#.*?#\}", re.DOTALL)
_NUMBER = re.compile(r"^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$")
_JINJA_CONST = re.compile(r"^\{\{\s*(var\([^{}]*\)|\w+\(\s*\))\s*\}\}$")
_UNARY_FUNCS = {"CAST", "ABS", "SQRT", "EXP", "ROUND", "LN", "LOG", "POWER"}


def _strip_comments(sql: str) -> str:
    """Blank out comments, keeping every offset (and newline) in place."""
    return _COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), sql)


def _close_paren(s: str, i: int) -> int:
    """Index of the parenthesis closing the one at s[i]."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "(":
            depth += 1
        elif s[j] == ")":
            depth -= 1
            if depth == 0:
                return j
    raise ValueError(f"unbalanced parenthesis at {i}")


def _split_top(s: str, seps: str) -> list[str]:
    """Split s on any character in seps at parenthesis depth 0 (and outside {{ }})."""
    parts, depth, start, i = [], 0, 0, 0
    while i < len(s):
        if s.startswith("{{", i):
            i = s.index("}}", i) + 2
            continue
        ch = s[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch in seps and depth == 0:
            parts.append(s[start:i])
            start = i + 1
        i += 1
    parts.append(s[start:])
    return parts


def _split_args(inner: str) -> list[str]:
    return [a.strip() for a in _split_top(inner, ",")]


def _strip_outer_parens(x: str) -> str:
    while x.startswith("(") and _close_paren(x, 0) == len(x) - 1:
        x = x[1:-1].strip()
    return x


def _split_arith(x: str) -> tuple[list[str], list[str]]:
    """Operands and binary operators (+ - * /) of x at parenthesis depth 0. A sign with
    no operand before it (unary minus) or inside a number's exponent (1e-6) is not a
    binary operator and stays with its operand."""
    pieces, ops, depth, start, i = [], [], 0, 0, 0
    while i < len(x):
        if x.startswith("{{", i):
            i = x.index("}}", i) + 2
            continue
        ch = x[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch in "+-*/" and depth == 0:
            before = x[start:i].rstrip()
            if before and not re.search(r"(?<![\w.])\d+(\.\d*)?[eE]$", before):
                pieces.append(x[start:i])
                ops.append(ch)
                start = i + 1
        i += 1
    pieces.append(x[start:])
    return pieces, ops


def _nonzero_constant(x: str) -> bool:
    x = _strip_outer_parens(x.strip())
    if _NUMBER.match(x):
        return float(x) != 0.0
    return bool(_JINJA_CONST.match(x))


def null_proof(expr: str) -> bool:
    """True if expr cannot be NULL, judged from its syntax alone (conservative)."""
    x = _strip_outer_parens(expr.strip())
    if not x:
        return False
    if _NUMBER.match(x) or _JINJA_CONST.match(x):
        return True
    pieces, ops = _split_arith(x)
    if ops:
        # every operand NULL-proof; a divisor must be a non-zero constant (x / 0 is NULL)
        if any(op == "/" and not _nonzero_constant(rhs) for op, rhs in zip(ops, pieces[1:])):
            return False
        return all(null_proof(p) for p in pieces)
    if x[0] in "+-":
        return null_proof(x[1:])
    m = re.match(r"^(\w+)\s*\(", x)
    if m and _close_paren(x, m.end() - 1) == len(x) - 1:
        name, args = m.group(1).upper(), _split_args(x[m.end():-1])
        if name == "COALESCE":
            return null_proof(args[-1])
        if name in ("LEAST", "GREATEST"):
            return all(null_proof(a) for a in args)
        if name == "CAST":
            return null_proof(re.split(r"\s+AS\s+", args[0], flags=re.IGNORECASE)[0])
        if name in _UNARY_FUNCS:
            return all(null_proof(a) for a in args)
    return False


_SQL_WORDS = {
    "AS", "AND", "OR", "NOT", "IS", "NULL", "CASE", "WHEN", "THEN", "ELSE", "END", "TRUE",
    "FALSE", "OVER", "PARTITION", "BY", "ORDER", "ROWS", "RANGE", "BETWEEN", "PRECEDING",
    "FOLLOWING", "CURRENT", "ROW", "UNBOUNDED", "IN", "DISTINCT", "FILTER", "WHERE",
    "DOUBLE", "INTEGER", "BIGINT", "VARCHAR", "DECIMAL", "FLOAT", "INT", "HUGEINT", "DATE",
}
_JINJA_CALL = re.compile(r"\{\{\s*\w+\s*\((?:[^{}]|\{\{[^{}]*\}\})*\)\s*\}\}")
_JINJA_VAR = re.compile(r"\{\{\s*(\w+)\s*\}\}")
_IDENT = re.compile(r"(?<![\w.'])([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)(?!\s*\()")
_NULL_TEST = re.compile(r"(\{\{\s*\w+\s*\}\}|[A-Za-z_][\w.]*)\s+IS\s+(?:NOT\s+)?NULL\b", re.IGNORECASE)


def _nullable_leaves(expr: str) -> list[str]:
    """The operands of expr that are not NULL-proof, descending through arithmetic,
    CAST / ABS / SQRT-style wrappers and nested LEAST/GREATEST."""
    x = _strip_outer_parens(expr.strip())
    if not x or null_proof(x):
        return []
    pieces, ops = _split_arith(x)
    if ops:
        return [leaf for p in pieces for leaf in _nullable_leaves(p)]
    if x[0] in "+-":
        return _nullable_leaves(x[1:])
    m = re.match(r"^(\w+)\s*\(", x)
    if m and _close_paren(x, m.end() - 1) == len(x) - 1:
        name, args = m.group(1).upper(), _split_args(x[m.end():-1])
        if name == "CAST":
            args = [re.split(r"\s+AS\s+", args[0], flags=re.IGNORECASE)[0]]
        if name in ("LEAST", "GREATEST", "CAST") or name in _UNARY_FUNCS:
            return [leaf for a in args for leaf in _nullable_leaves(a)]
    return [x]


def _nullable_identifiers(args: list[str]) -> set[str]:
    """Column references (and plain {{ jinja }} variables) the non-NULL-proof operands
    read. A macro call inside them is not expanded: its own body is linted where the
    macro is defined (macros/ is scanned too)."""
    names: set[str] = set()
    for a in (leaf for arg in args for leaf in _nullable_leaves(arg)):
        x = _JINJA_CALL.sub(" ", a)
        x = _JINJA_VAR.sub(lambda m: " __jinja_" + m.group(1) + " ", x)
        x = re.sub(r"'[^']*'", " ", x)
        x = re.sub(r"\bOVER\s+\w+", " ", x, flags=re.IGNORECASE)
        for m in _IDENT.finditer(x):
            ident = m.group(1)
            if ident.upper() in _SQL_WORDS or _NUMBER.match(ident):
                continue
            names.add(ident.lower())
    return names


def _guarded(s: str, pos: int, args: list[str]) -> bool:
    """True if pos sits inside CASE ... END blocks whose text before pos tests IS [NOT]
    NULL on every column the call's nullable arguments read."""
    stack = []
    for m in re.finditer(r"\bCASE\b|\bEND\b", s[:pos], re.IGNORECASE):
        if m.group(0).upper() == "CASE":
            stack.append(m.start())
        elif stack:
            stack.pop()
    if not stack:
        return False
    tested = set()
    for start in stack:
        for m in _NULL_TEST.finditer(s[start:pos]):
            t = m.group(1)
            jv = _JINJA_VAR.match(t)
            tested.add(("__jinja_" + jv.group(1)) if jv else t.lower())
    needed = _nullable_identifiers(args)
    return bool(needed) and needed <= tested


def scan_sql(sql: str) -> list[tuple[int, str]]:
    """(line, normalized call text) for every LEAST/GREATEST call that is neither
    NULL-proof by syntax nor inside a CASE that NULL-tests every column it reads."""
    s = _strip_comments(sql)
    flagged = []
    for m in _CALL.finditer(s):
        open_at = m.end() - 1
        close_at = _close_paren(s, open_at)
        args = _split_args(s[open_at + 1:close_at])
        if all(null_proof(a) for a in args):
            continue
        if _guarded(s, m.start(), args):
            continue
        text = m.group(1).upper() + "(" + re.sub(r"\s+", " ", s[open_at + 1:close_at]).strip() + ")"
        flagged.append((s.count("\n", 0, m.start()) + 1, text))
    return flagged


def scan_tree() -> Counter:
    """Counter of (relative path, normalized call) over the scanned directories."""
    found: Counter = Counter()
    for sub in SCANNED:
        for path in sorted((TRANSFORM / sub).rglob("*.sql")):
            for _line, text in scan_sql(path.read_text()):
                found[(path.relative_to(TRANSFORM).as_posix(), text)] += 1
    return found


def _allowlist() -> list[dict]:
    return json.loads(ALLOWLIST_PATH.read_text())["entries"]


# ---------------------------------------------------------------------------
# The lint
# ---------------------------------------------------------------------------

def test_no_unreviewed_least_greatest_over_a_nullable_expression():
    reviewed = Counter({(e["file"], e["call"]): e.get("count", 1) for e in _allowlist()})
    found = scan_tree()
    unreviewed = sorted(k for k in found if found[k] > reviewed.get(k, 0))
    assert not unreviewed, (
        "LEAST/GREATEST over a possibly-NULL expression (DuckDB skips the NULL and returns "
        "the other argument). Guard it with CASE WHEN x IS NULL THEN NULL ..., use "
        "clamp_or_null(), or review it in least_greatest_nullable.allowlist.json:\n  "
        + "\n  ".join(f"{f}: {c[:140]}" for f, c in unreviewed)
    )


def test_allowlist_entries_are_live_and_reasoned():
    found = scan_tree()
    for e in _allowlist():
        key = (e["file"], e["call"])
        assert found.get(key, 0) == e.get("count", 1), f"stale or miscounted allowlist entry: {key}"
        assert e["verdict"] in VERDICTS, e
        assert len(e.get("reason", "").strip()) > 20, f"allowlist entry needs a reason: {key}"


def test_the_f39_sites_are_guarded_not_waived():
    """The wear curve's bounds must pass by their own NULL guard. A waiver here would
    let the guard be deleted with the lint still green."""
    waived = [e for e in _allowlist()
              if e["file"] in ("models/intermediate/int_compound_cliff_predicted.sql",
                               "macros/compound_cliff_wear.sql",
                               "models/marts/fct_cliff_prediction_features.sql")
              and ("laps_past_cliff" in e["call"] or "age" in e["call"]
                   or "driver_skill_residual_s" in e["call"])]
    assert not waived, waived


# ---------------------------------------------------------------------------
# The checker catches what it is for (and does not cry wolf on the fixes)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sql", [
    # F39 as it was
    "SELECT LEAST(COALESCE(g, 0.0) * age_in_stint + x, {{ var('cap', 10.0) }}) FROM t",
    "SELECT GREATEST(CAST(age_in_stint AS DOUBLE) - COALESCE(onset, 999.0), 0.0) FROM t",
    # the label clip as it was
    "SELECT GREATEST(LEAST(LEAD(r, 1) OVER w - r, 10.0), -10.0) FROM t",
    # a division that can hit zero
    "SELECT LEAST(x / NULLIF(y, 0), 3.0) FROM t",
    "SELECT GREATEST(COALESCE(a, 0) / COALESCE(b, 0), 0) FROM t",
    # a guard that belongs to a different, already-closed CASE does not count
    "SELECT CASE WHEN a IS NULL THEN 0 END, LEAST(b, 1.0) FROM t",
    # a guard that tests only one of the columns the bound reads does not count
    "SELECT CASE WHEN a IS NULL THEN 0.0 ELSE GREATEST(a - b, 0.0) END FROM t",
])
def test_flags_a_bound_over_a_nullable_expression(sql):
    assert scan_sql(sql), sql


@pytest.mark.parametrize("sql", [
    "SELECT CASE WHEN age IS NULL THEN NULL ELSE LEAST(COALESCE(g, 0.0) * age, 10.0) END FROM t",
    "SELECT CASE WHEN a IS NULL OR b IS NULL THEN NULL ELSE GREATEST(a - b, 0.0) END FROM t",
    "SELECT CASE WHEN x IS NOT NULL THEN GREATEST(x, 0) END FROM t",
    "SELECT LEAST(GREATEST(COALESCE(t, 30.0) - COALESCE(lo, 20.0), 0.0), 30.0) FROM t",
    "SELECT GREATEST(COALESCE(a, 0) * 2 / 5.0, {{ cliff_severity_span() }}) FROM t",
    "SELECT LEAST(1, 2) -- LEAST(x, 1) in a comment is not code\nFROM t",
])
def test_accepts_null_proof_or_guarded_bounds(sql):
    assert not scan_sql(sql), scan_sql(sql)
