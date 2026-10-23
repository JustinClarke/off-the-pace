# DA-04 - Fit and validation

**Fit.** Estimate on earlier seasons, test on a held-out season. Run the existing honesty tests: `assert_lap_7term_identity`, `assert_no_future_leakage`, `assert_prior_season_labels_frozen`, `assert_proximity_agrees_with_blue_flags`, `assert_dirty_air_tax_null_only_when_unmeasured`.

**Gate to continue.** Out-of-sample gain over the current lag-based tax. Lap totals fall between 0.331 and the 0.881 lap-share fit.

**Stop if.** No out-of-sample gain.

**Owner decision at this gate.** Path A or path B (feeds DA-05).

**Not in this item.** Any change to the label. The label does not move until DA-05.
