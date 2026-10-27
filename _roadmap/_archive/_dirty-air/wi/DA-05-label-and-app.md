# DA-05 - Label and app decision

**Path A: sit beside the label.** Add a `dirty_air_cost_dynamic_s` measure. The label, residuals, theta_air, `cumulative_dirty_air_tax_s` and the ML models are unchanged. Not a label-version change. An ML feature built on it would be a new arm and needs a retrain. App: a session replay on the dirty-air-cost page, shown as attribution from a same-lap model, not a causal label. About 3 weeks.

**Path B: replace the label's tax.** Roughly 3x higher on laps spent following. Label-version change: moves `dirty_air_tax_s`, `cumulative_dirty_air_tax_race_s`, `driver_skill_residual_s`, the lap and sector residuals, and `cumulative_dirty_air_tax_s` in `fct_stint_features`. Needs `label_stability_baseline` retaken and a retrain (same pattern as CO-18). App pages, page summaries and docs all update. About 6 weeks or more.

**Path B-lite.** Keep lap totals and split them across sectors by exposure. Sector labels only; still a label-version change.

**Gate.** Tests green. Label diff reviewed by the owner before any change lands.

**Stop if.** Unacceptable churn in downstream numbers.
