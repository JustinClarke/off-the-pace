# AI-11 — Chart and lap-comparison tools

**Group:** 2 assistant build · **Depends on:** `AI-09` · **Blocker:** none.

**Sources:** `app/src/ui/feedback/`, `app/src/data/duckdb/queryLab.ts`. The working prototype is outside this repo, in `_misc/_chat/f1-chat`.

---

## Scope

1. **`make_chart(spec)`**: a fixed chart description: type, title, axes, and up to 6 series of up to 500 points each. The data comes from a previous tool result, referenced by id. The model never writes chart code.
2. **`compare_lap_times(driver_a, driver_b, race)`**: a lap-time comparison, built on the query builder (AI-09). Kept as its own tool because the prototype tests it and it charts well.

## Method

1. Port the prototype's chart and comparison logic into the app, using the app's own chart styling and the placeholder palette from the dataviz guidance.
2. Rows from a chart are kept out of the model's context. The model gets back only a short confirmation and the chart's sample size.
3. Each chart carries the sample size and the same "computed, not a fact card" label as the query builder (AD3).

## Acceptance

- A chart spec with more than 6 series or 500 points is rejected with a reason.
- A comparison of two drivers in one race renders, with n shown.
- No chart rows appear in the model's context (checked in the headless loop).

## Definition of done

Tests pass and the headless command produces a comparison chart for 3 sample questions. Do not commit.
