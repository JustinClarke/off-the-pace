import { CANONICAL_DOCS_BASE } from '../../config'

export const methodologyHref = `${CANONICAL_DOCS_BASE}/app/blind-test-scoreboard`

export const methodologyContent = `
The Blind Test Scoreboard puts the shipped degradation models' predictions next to what actually
happened, lap by lap, for the selected season. 2026 is the blind test: it is the designated holdout,
ingested as its races complete, and its laps are scored by models that never saw them.

The shipped models were refit on every ingested season (2018–2025), so any season before 2026 is
in-sample fit, which flatters both the scatter and the coverage. The honest out-of-sample numbers are
the final cross-validation fold (2025, scored by a model trained on 2018–2024) on Model Metrics.
That fold also helped decide which features to admit, so it is a validation fold, not a clean holdout.

**Predicted vs actual scatter:** Each point is one lap. X-axis = actual next-5-lap cumulative degradation
jump observed in the race; Y-axis = model p50 prediction. Points on the 45-degree diagonal are
perfect calls. The p10 / p90 band defines the 80% conformal envelope.

**Interval coverage rug:** Empirical coverage = fraction of laps where the actual jump falls
inside [p10, p90]. Target is 80% (conformal calibration from the training fold). Green bars hit;
red bars miss.

**Cliff class confusion matrix:** Predicted laps-until-cliff class (rows) vs actual class
(columns). Row-normalised so the intensity of each cell reflects the fraction of that predicted
class that lands in each actual bucket. Teal diagonal = correct; red off-diagonal = error.

All numbers are read from mart_degradation_predictions.parquet, joined to fct_cliff_prediction_features
for actuals. No values are hand-typed.
`.trim()
