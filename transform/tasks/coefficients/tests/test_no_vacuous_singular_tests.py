"""
T26 (F34, WI-07): no singular dbt test body can pass regardless of the condition it is
named to check.

F34 found three literal dead-code stubs -- `SELECT 1 WHERE FALSE`, tagged
`placeholder` -- counted toward the green PASS total on every build regardless: nothing
in `transform-check`'s own `dbt test` invocation (Makefile, ml-ci.yml) passes
`--exclude tag:placeholder`, so a declared, documented placeholder inflated the count
exactly as silently as an undeclared one would have. `assert_sector_aggregates_to_lap`'s
own 25-line header derived the real tolerance-bounded identity it never ran, ending in a
self-documented "Gate: PASSIVE / INFORMATION ONLY" comment -- reverified as understated
at "Medium (process)": this is dead code that had been inflating the suite's PASS count
indefinitely, with a comment admitting it.

WI-07's fix is not "tag it correctly" (all three already were) -- it is that this exact
shape must never ship again: `assert_cliff_stints_have_falloff.sql` and
`assert_constructor_confidence_monotone.sql` are deleted outright, and
`assert_sector_aggregates_to_lap.sql` now runs the identity its header always described.
Zero `tags=['placeholder']` singular tests remain in this checkout as of this item.

This is the guard that keeps it that way: a test body reducing to `SELECT 1 WHERE
FALSE` (any whitespace/case, comments and the config() call stripped) is refused
outright, tagged placeholder or not. A test that genuinely cannot be implemented yet
should not exist in this directory at all (dbt's `enabled: false`, or simply not
writing the file) rather than shipping a stub that runs, passes, and counts.
"""
from __future__ import annotations

import re
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parents[3] / "tests"

_LINE_COMMENT = re.compile(r"--[^\n]*")
_JINJA_COMMENT = re.compile(r"\{#.*?#\}", re.DOTALL)
_CONFIG_CALL = re.compile(r"\{\{\s*config\(.*?\)\s*\}\}", re.DOTALL)
_VACUOUS = re.compile(r"^select\s+1\s+where\s+false;?$", re.IGNORECASE)


def _stripped_body(sql: str) -> str:
    """The test's executable body with comments and the config() call removed, so a
    vacuous body can't hide behind either. Collapsed to single spaces so the exact
    layout of the original stubs (each on its own line) does not matter."""
    sql = _JINJA_COMMENT.sub(" ", sql)
    sql = _LINE_COMMENT.sub(" ", sql)
    sql = _CONFIG_CALL.sub(" ", sql)
    return " ".join(sql.split())


def _singular_test_files() -> list[Path]:
    # Every .sql file directly under transform/tests/ is a singular test by dbt's own
    # convention (transform/tests/README.md's own scope statement); baselines and
    # fixtures live in their own sub-paths/extensions and are not tests.
    return sorted(p for p in TESTS_DIR.glob("*.sql"))


def test_no_singular_test_body_is_vacuous():
    offenders = [p.name for p in _singular_test_files() if _VACUOUS.match(_stripped_body(p.read_text()))]
    assert not offenders, (
        f"vacuous (SELECT 1 WHERE FALSE) singular test bod(y/ies): {offenders} -- "
        "these run and pass on every build regardless of tagging (nothing in "
        "transform-check's dbt invocations excludes tag:placeholder), silently "
        "inflating the PASS count. Either implement the real check or delete the file; "
        "do not ship a stub here (F34)."
    )


def test_the_scanner_would_have_caught_the_pre_fix_shape():
    """Proves the check above is real, not vacuous itself (the same standard F34 holds
    everything else to). All three F34 stubs shared this exact shape before this item:
    a `{{ config(tags=['placeholder']) }}` call followed by `SELECT 1 WHERE FALSE`, on
    its own or after descriptive `--` comments -- reconstructed here verbatim from
    transform/tests/README.md's pre-fix rows (assert_cliff_stints_have_falloff.sql,
    assert_constructor_confidence_monotone.sql) and this item's own diff
    (assert_sector_aggregates_to_lap.sql), rather than depended on as files this same
    item removed."""
    pre_fix_bodies = [
        # assert_cliff_stints_have_falloff.sql, verbatim before this item deleted it.
        "-- Placeholder: returns empty (passes) until this is wired up as an active "
        "warning/error check.\n{{ config(tags=['placeholder']) }}\n\nSELECT 1 WHERE FALSE\n",
        # assert_constructor_confidence_monotone.sql, verbatim before this item deleted it.
        "{{ config(tags=['placeholder']) }}\nSELECT 1 WHERE FALSE\n",
        # assert_sector_aggregates_to_lap.sql, verbatim before this item rewrote it.
        "-- Gate: PASSIVE / INFORMATION ONLY (Placeholder test)\n"
        "{{ config(tags=['placeholder']) }}\n\nSELECT 1 WHERE FALSE\n",
    ]
    for body in pre_fix_bodies:
        assert _VACUOUS.match(_stripped_body(body)), (
            f"scanner failed to recognise a pre-fix F34 stub shape: {body!r}"
        )
