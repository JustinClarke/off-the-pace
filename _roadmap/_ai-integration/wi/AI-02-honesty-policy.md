# AI-02 — Honesty policy as data

**Group:** A grounding · **Depends on:** none · **Blocker:** none.

**Sources:** `docs/app/blind-test-scoreboard.mdx`, `docs/ml/ci/evaluation-gates.mdx`, `docs/app/model-metrics.mdx`, and the WI-16 validation findings in `_roadmap/_fixes/status/build-log.json`.

---

## What exists today

The docs already set honesty rules in prose. Examples read in the tree: the blind-test page says every season it can show was in the training set until the 2026 holdout ingests, so it is in-sample fit, not proof; the calibration work flags circuit priors as `REVIEW_REQUIRED` or `INSUFFICIENT_DATA`; the fixes log records WI-16 grades (tactical stability fail, car leakage marginal) and a docs contradiction for São Paulo 2021. None of this is in a form a program can check.

## Method

1. Read the docs and the fixes log and extract each rule as a row: `code`, `applies_to` (metric or page), `condition`, `required_wording` (what the answer must say), `forbidden_claim`.
2. Cover at least: in-sample versus out-of-sample, thin samples, low-confidence model outputs, predictions outside `is_in_envelope`, metrics graded below pass, known data gaps, and "the app has no data for that" (2026 races not ingested). Open rulings that limit a claim are rules too, until ruled: no campaign-level rejection is quoted (D13), and a pit-call verdict carries its measured reproduction rate (D9).
3. Add a checker: given a drafted answer and its fact cards, report which rules fired and whether the required wording is present.
4. Each rule cites the doc line it came from, so a docs change shows up as a policy change.

## Acceptance

- Every rule cites a source file; no rule is invented.
- The checker fails an answer that states an in-sample result as proof.
- The checker passes an answer that quotes the same number with the required wording.

## Tests to add

One failing and one passing example per rule.

## Output

The rule list (count by kind) and the list of doc claims that contradict each other.

## Definition of done

Policy file and checker exist, every rule has both examples passing, and a list of doc claims that contradict each other (such as the São Paulo item) is recorded rather than resolved silently.
