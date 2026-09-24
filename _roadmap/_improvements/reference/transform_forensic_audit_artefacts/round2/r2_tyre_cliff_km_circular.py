"""R2-J: the Tyre-Cliff Survival page's "live validation" validates the seed against itself.

queries.ts (queryStintSummaries): cliffed = BOOL_OR(cliff_onset_passed); stint_length = MAX(lap_in_stint).
int_compound_cliff_predicted.sql:124: cliff_onset_passed = age_in_stint > COALESCE(compound_cliff_onset_laps, 999).
So a KM "event" is "this stint's tyre got older than the seed's onset", placed at the stint's END,
and the page tells readers the fit is calibrated if the KM median lands near that same seed onset
(methodology.tsx). No observed degradation enters the event; "degradation_s" is a sum of the seed's
expected rate. For 2018-2024 the seed onset is itself fitted on the same race (round-1 F2).

Part 1: cliffed is identical to (max age > seed onset) on every stint (definitional).
Part 2: agreement between the page's event and the label's OBSERVED cliff (laps_until_cliff_class
reaching a >1 s detrended jump within the stint), on the same stints.

DEFECT PRESENT while: mismatch_vs_seed_rule = 0 (the event is the seed rule).
"""
from _db import con, show

c = con()
c.execute(r"""
create temp table st as
select stint_id, race_year, compound,
  max(lap_in_stint) stint_length, bool_or(cliff_onset_passed) cliffed,
  max(age_in_stint) max_age, max(compound_cliff_onset_laps) onset,
  bool_or(laps_until_cliff_class in ('0_to_2','3_to_5','6_plus')) observed_cliff_ahead_somewhere
from fct_cliff_prediction_features
where compound not in ('INTERMEDIATE','WET') and anomaly_class in ('normal','clean_cliff') and is_rain_lap = false
group by all""")
show(c, r"""
select count(*) stints, count(*) filter (where cliffed) page_events,
  count(*) filter (where cliffed is distinct from (max_age > coalesce(onset, 999))) mismatch_vs_seed_rule
from st""", "Part 1: page event == seed rule")
show(c, r"""
select cliffed page_event, observed_cliff_ahead_somewhere observed_jump_in_stint, count(*) stints
from st group by all order by 1, 2""", "Part 2: page event vs an observed >1 s detrended jump anywhere in the stint")
