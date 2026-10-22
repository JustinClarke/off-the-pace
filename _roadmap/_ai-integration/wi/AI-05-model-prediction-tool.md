# AI-05 — Model prediction tool (closed for v1)

> **Cut from v1 on 2026-10-15.** `mart_degradation_predictions`, already on the CDN, carries p10/p50/p90, cliff-class probabilities, stint-life bands, `model_version` and `is_in_envelope` for every predicted lap. AI-01 turns those into fact cards, so questions about real stints need no live inference. Hypothetical questions link the Degradation Simulator page instead (AI-04). Reopen if AI-07 shows fans asking what-if tyre questions that the link does not serve. The spec below is kept for that.

**Group:** 2 assistant build · **Depends on:** `AI-02` · **Blocker:** none.

**Sources:** `app/src/ml/infer.ts`, `app/src/ml/index.ts`, `docs/ml/models.mdx`, `docs/ml/calibration.mdx`.

---

## What exists today

The app already runs the cliff classifier and the degradation and stint-life regressors in the browser through ONNX (`predictLap`, `predictLaps`, with a parity check against the Python models). The degradation models give p10, p50 and p90, which is the app's own expression of uncertainty.

## Method

1. Expose `predictLap` as a tool: input is compound, tyre age, fuel and conditions; output is the point estimate, the p10 to p90 band, and the cliff probability.
2. The tool result always includes the band and the model version. A point estimate without its band is not returned.
3. Inputs outside the training range (tyre age, fuel, circuit) return a "outside the range this model saw" warning, using the policy rules from AI-02.
4. Use the same fact-card shape from AI-01 for the output.

## Acceptance

- The tool never returns a bare number.
- Out-of-range input produces the warning.
- Output matches what the Degradation Simulator page shows for the same input.

## Tests to add

A parity test against the simulator for 5 fixed inputs; an out-of-range test.

## Definition of done

Tests pass and the tool's output for the 5 inputs matches the simulator page to display precision.
