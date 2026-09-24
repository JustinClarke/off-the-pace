# WI-13 — Pit-strategy stop matching

**Group:** 07 causal pit timing · **Depends on:** nothing · **Blocker:** none.

**Findings folded in:** F31 (Medium).

**Reverification:** CONFIRMED-AS-STATED.

---

## The defect, reconfirmed

`int_pit_strategy_value.sql`'s `stint_meta` CTE filters `WHERE sg.is_valid_lap = TRUE`, and a stop is
matched only within `stint_start_lap` to `stint_end_lap + 1` (confirmed at the join clause). Any
SC/VSC/red-flag run-in, or an invalid lap immediately before the stop, puts the real in-lap outside
that window. Confirmed live: pit-ended stints with `actual_pit_lap` NULL — green 105/4,061 (2.6%), SC
191/644 (**29.7%**), VSC 38/230, red **96/115 (83.5%)**. Each gets `verdict = NULL` and
`opportunity_cost_s = 0.0` via an explicit `CASE WHEN r.actual_pit_lap IS NULL THEN 0.0`, as if the
stop never happened. In the app, `pit-strategy/queries.ts:101,115-116` then does
`ORDER BY actual_pit_lap NULLS LAST` and `COALESCE(actual_pit_lap, tl.n)`, which draws those stints'
bars all the way to the chequered flag — a visibly wrong Gantt for a large majority of red-flag
stops.

## Fix assessment (from reverification)

Genuinely minimal: `int_stint_end_regime.end_lap_number` **already exists** as the correct join key
— this isn't a new-data requirement, it's a JOIN-clause swap.

## Method

1. Replace the `stint_end_lap + 1` match window with a match against
   `int_stint_end_regime.end_lap_number`, which already accounts for stints ending under SC/VSC/red
   conditions.
2. Remove the app's `NULLS LAST`/`COALESCE(..., tl.n)` fallback once the underlying join reliably
   resolves `actual_pit_lap` for these stints — that fallback exists specifically to paper over the
   current gap and should go away with it, not be left as a second layer of masking.

## Acceptance

- No pit-ended stint (`stint_end_cause LIKE '%pit'` or `'red'`) has a NULL `actual_pit_lap`.
- The Gantt draws every stop at its real lap, including SC/VSC/red-flag run-ins.

## Tests to add

T23.

## Definition of done

`verify_findings.py`'s F31 check flips to CLEARED; T23 is wired in and would fail against the
pre-fix join.
