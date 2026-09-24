# WI-03 — Holdout policy after 12a-1

**Group:** 12 season coverage · **Depends on:** nothing · **Blocker:** human decision — which season
is actually held out, if any.

**Findings folded in:** F4 (High, process).

**Reverification:** CONFIRMED-AS-STATED, and confirmed as the single top-priority process finding in
the whole audit — reconfirmed independently by reading `resolve_holdout_season` directly rather than
trusting the report's description.

---

## The defect, reconfirmed

`ml/src/features.py:54-57`, `resolve_holdout_season`:

```
SELECT MAX(race_year) + 1 FROM fct_cliff_prediction_features
```

This **always** names the first season that is absent by construction — a season that, by
definition, can never have rows. It is not "off by one in the current state," it is structurally
incapable of ever resolving to a populated season under any ingestion cadence: the moment a season
ingests, `MAX(race_year)` includes it, and the resolver's target moves one season further out.

**Confirmed today:** training = 2018–2025 inclusive (2025 included), `holdout_season` = 2026, 0 rows.
The intent recorded in `work/12-season-coverage.md` ("ingesting 2025 makes 2025 the holdout and folds
2024 into training with no code change") is false as implemented — 12a-1 landing made 2025 join
training, not become the holdout.

**Compounding: 2025 has already been spent once as a selection fold.**
`ml/artefacts/02c_corner_inputs_arms_v14.json` (2026-09-23) scored its admission gate with
`n_eval = 13,951`, exactly 2025's labelled row count. So even before this is fixed, 2025 has been
used for model selection, which means it can't retroactively become a clean holdout without either
re-selecting without it or accepting it's now a validation fold, not a holdout.

**Stale prose in four places, confirmed unchanged since the audit ran** (checked via `git log` on
each file — no commits since 2026-09-23): `ml/src/card.py:46-50,242,345,474`, `ml/model_card.yml:7,
24-26,963,1049`, `README.md:167`, `ml/tests/test_predict.py:36`. The test is tautological — it
asserts `not is_holdout.any()`, which passes *because* the resolver moved the goalposts, not because
the holdout mechanism works.

## Fix assessment (from reverification)

T8 (declared holdout season, or an explicit `holdout_populated: false` flag) is the right *test*, but
the **durable fix** is deeper than the original report's phrasing suggests: the resolver needs to
**pin a holdout season** — a literal value or a seed-controlled one — rather than perpetually
re-deriving `MAX+1`, which by definition can never be "spent" because it's always the season that
doesn't exist yet. A pinned season can actually be excluded from training and actually be evaluated
on later, which is the only way a re-derived-at-runtime holdout could ever function as intended.

## Method

1. **Decide the held-out season.** This is the blocking human decision. Options: pin the most
   recently completed season not yet used for any admission gate (currently none — 2025 is spent,
   per above); or accept there is currently no clean holdout and declare that explicitly rather than
   implicitly.
2. Change `resolve_holdout_season` to read a pinned value (config, seed, or explicit override) rather
   than `MAX(race_year)+1`.
3. Retire the tautological test (`test_predict.py:36`) and replace with T8: asserts the declared
   holdout season has rows, or the card/README explicitly state `holdout_populated: false`.
4. Correct the four stale-prose locations to describe the actual mechanism, not the aspirational one.
5. Note in `build-log.json`'s decisions that 02c v14's admission gate already consumed 2025 as a
   selection fold, so any claim about v14's "holdout" performance needs that caveat attached
   permanently, not just fixed going forward.

## Acceptance

- The holdout season is a value that can actually hold rows, is actually excluded from training, and
  is not simultaneously used for any admission/selection gate.
- The model card, README, and `HOLDOUT_NOTE` describe the real mechanism.
- `test_predict.py`'s holdout assertion is falsifiable (can actually fail) rather than passing by
  construction.
- 02c v14's use of 2025 in an admission gate is documented as a known confound on that artefact,
  not silently left as "unmeasured."

## Tests to add

T8.

## Definition of done

`resolve_holdout_season` cannot return a season that is absent by construction; T8 lands and can be
shown to fail on the pre-fix resolver; `verify_findings.py`'s F4 check flips to CLEARED (or is
retired with a note explaining the new mechanism it no longer applies to); the four stale-prose
locations are corrected.
