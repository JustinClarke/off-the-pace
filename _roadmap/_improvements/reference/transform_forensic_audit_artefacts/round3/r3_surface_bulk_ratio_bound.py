"""R3 F49: the surface/bulk split can never say "surface-driven", and the Tyre Recovery page
quotes a recovery rate its table does not hold.

Defect. surface_bulk_ratio = surface / (surface + bulk)
(int_tyre_surface_vs_bulk_decoupling.sql:85-90, classes at :118-119; the same arithmetic is contract
feature #19 at fct_cliff_prediction_features.sql:544-550). Both loads are finite sums of
the same positive push residuals (int_lap_thermal_proxy.sql:122-142): surface weights
1, .717, .514, .369, .264 over lags 0-4; bulk weights 1, .819, .670, .549, .449, .368,
.301, .247 over lags 0-7. Every surface weight is <= the bulk weight at the same lag and
bulk has three more lags, so surface <= bulk on every lap and the ratio is <= 0.5. The
model's 'surface_driven' class needs ratio > 0.65 -- unreachable -- and the ratio mostly
measures how RECENT the pushing was (0.5 = only this lap; 0.394 = steady push).
app/src/features/tyre-recovery-forecast/methodology.tsx:15-21 describes a
"surface-driven (thermal, can partially recover)" regime and says the recovery rate is
"~86-89%" across compounds.

Oracle: the weights in the SQL, and the table itself.

DEFECT PRESENT while: no row can reach the 'surface_driven' threshold (max ratio <= 0.5).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'round2'))
from _db import con, show  # noqa: E402

c = con()
show(c, """select count(*) laps_with_loads, count(*) filter (where cumulative_push_load_surface > cumulative_push_load_bulk + 1e-9) surface_exceeds_bulk
 from int_lap_thermal_proxy where cumulative_push_load_bulk is not null""", "surface load never exceeds bulk load")
show(c, """select degradation_source, count(*) n, round(min(surface_bulk_ratio), 3) min_ratio, round(max(surface_bulk_ratio), 3) max_ratio
 from int_tyre_surface_vs_bulk_decoupling group by 1 order by 1""", "classes produced (threshold for 'surface_driven' is > 0.65)")
show(c, """select round(max(surface_bulk_ratio), 3) max_contract_feature from fct_cliff_prediction_features""", "contract feature #19 range")
show(c, """select compound, count(*) post_cliff_laps, round(100 * avg(case when recovery_flag then 1.0 else 0 end), 1) recovery_rate_pct
 from int_tyre_surface_vs_bulk_decoupling where laps_past_cliff > 0 and compound not in ('INTERMEDIATE', 'WET')
 group by 1 order by 1""", "the page's own query (queries.ts:22-33): methodology says ~86-89%")
