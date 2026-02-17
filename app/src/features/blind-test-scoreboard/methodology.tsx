export const methodologyHref = 'https://off-the-pace.onrender.com/machine-learning'

export const methodologyContent = `
The Blind Test Scoreboard shows the degradation models' out-of-sample performance on the 2024
season evaluation fold (the last TimeSeriesSplit fold, held out of training). Until the 2025
season ingests, 2024 is the proxy holdout the scoreboard promotes automatically the moment
the new season arrives.

**Predicted vs actual scatter:** Each point is one lap. X-axis = actual next-lap degradation
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
