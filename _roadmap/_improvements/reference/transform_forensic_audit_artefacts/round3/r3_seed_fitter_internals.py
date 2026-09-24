"""R3 F41: compound seed fitter internals -- (a) cells labelled "fitted via cox_km_survival"
silently carry class-default parameters; (b) the wear gradient is fitted on lap times that
still contain the fuel burn.

Defect (a). transform/tasks/coefficients/fit_compound_cliff.py:250-258 sets
source = "cox_km_survival" as soon as the group has >= 8 stints, and :293-302 then
replaces any parameter that came back None (KM never crossed 0.5 and <= 3 cliffs,
survival.py:184-190; no positive slope with R^2 > 0.1, survival.py:311-316; no cliff with
two pre and two post laps, survival.py:228-229) or out of range with the compound class
default -- without changing fit_source or notes ("fitted from N stints via
cox_km_survival", :316). The seed therefore cannot say which of its numbers are
measured. Oracle: COMPOUND_DEFAULTS itself; the modal "fitted" onsets are exactly the
defaults (MEDIUM 33, SOFT 22, HARD 50).

Defect (b). load_stint_data (:130) feeds normalized_pace_s = lap_time_s - theta *
time_in_dirty_air_s (int_lap_normalized_pace.sql), which still contains the fuel burn
(~0.05 s/lap faster every lap), into estimate_wear_gradient (survival.py:262-320), which
also keeps only positive slopes. So the gradient estimates (wear - fuel gain) on a
positively-truncated sample, while int_lap_residual_decomposed subtracts fuel separately.
Its docstring (survival.py:274-275) says it "uses uncensored stints only"; the code uses
every fresh-tyre stint. Oracle: the same production estimator re-run on
fuel-corrected pace (normalized pace - fuel_mass_kg * weight_penalty_factor from
int_lap_fuel_state/dim_circuits), with the SEED's own onset per cell.

Note on reproduction: the seed was fitted on 2026-09-08 (c7de693) against an earlier
warehouse; re-running the unchanged estimator on today's warehouse reproduces 107/337
cells to 4 dp (means agree). The fuel counterfactual is therefore reported against
BOTH the seed and the same-warehouse rebuild.

DEFECT PRESENT while: (a) any cox_km_survival cell equals its class default on a
parameter while notes say "fitted"; (b) estimate_wear_gradient's pace column contains
the fuel burn.
"""
import sys
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'round2'))
from _db import con, show, REPO  # noqa: E402

sys.path.insert(0, str(REPO / 'transform'))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from tasks.coefficients import fit_compound_cliff as F  # noqa: E402
from tasks.coefficients.survival import estimate_wear_gradient  # noqa: E402

c = con()
D = F.COMPOUND_DEFAULTS
vals = ",".join(f"('{k}',{v['cliff_onset_laps']},{v['cliff_severity']},{v['wear_gradient']})" for k, v in D.items())
c.execute(f"create temp table defs as select * from (values {vals}) t(compound_code, d_onset, d_sev, d_grad)")
show(c, """
select count(*) cox_km_cells,
  count(*) filter (where abs(s.compound_cliff_onset_laps - d.d_onset) < 1e-9) onset_is_default,
  count(*) filter (where abs(s.compound_wear_gradient - d.d_grad) < 1e-9) gradient_is_default,
  count(*) filter (where abs(s.compound_cliff_severity - d.d_sev) < 1e-9) severity_is_default,
  count(*) filter (where abs(s.compound_cliff_onset_laps - d.d_onset) < 1e-9 or abs(s.compound_wear_gradient - d.d_grad) < 1e-9
                   or abs(s.compound_cliff_severity - d.d_sev) < 1e-9) any_default
from dim_compounds_season s join defs d using (compound_code) where s.notes like 'fitted from % via cox_km_survival'""",
     "(a) cells whose notes say 'fitted ... via cox_km_survival': parameters exactly equal to the class default")
show(c, """select compound_code, compound_cliff_onset_laps onset, count(*) n_cells from dim_compounds_season
 where notes like 'fitted from % via cox_km_survival' and compound_code in ('SOFT','MEDIUM','HARD')
 group by 1, 2 qualify row_number() over (partition by compound_code order by count(*) desc) <= 2 order by 1, 3 desc""",
     "(a) the two most common 'fitted' onsets per slick (class defaults: SOFT 22, MEDIUM 33, HARD 50)")
show(c, """
with cells as (select s.*, abs(s.compound_cliff_onset_laps - d.d_onset) < 1e-9 def_onset,
    abs(s.compound_cliff_severity - d.d_sev) < 1e-9 def_sev, abs(s.compound_wear_gradient - d.d_grad) < 1e-9 def_grad
  from dim_compounds_season s join defs d using (compound_code) where s.notes like 'fitted from % via cox_km_survival'),
m as (select f.race_year, f.compound, rt.track_id from fct_cliff_prediction_features f join race_to_track rt using (race_id) where f.is_training_eligible)
select count(*) eligible_rows_on_cox_km_cells, count(*) filter (where def_onset) onset_default,
  count(*) filter (where def_grad) gradient_default, count(*) filter (where def_sev) severity_default,
  count(*) filter (where def_onset or def_grad or def_sev) any_default
from m join cells on cells.circuit_key = m.track_id and cells.season = m.race_year and cells.compound_code = m.compound""",
     "(a) training-eligible rows sitting on those cells")

# (b) wear gradient with and without the fuel burn, production estimator, seed onset per cell.
df = F.load_stint_data(c, list(range(2018, 2025)))
fuel = c.execute("""select f.lap_id, f.fuel_mass_kg * d.weight_penalty_factor fuel_s,
    d.fuel_consumption_rate_kg_per_lap * d.weight_penalty_factor fuel_gain_s_per_lap
  from int_lap_fuel_state f join race_to_track rt using (race_id) join dim_circuits d on d.circuit_key = rt.track_id""").df()
df = df.merge(fuel, on='lap_id', how='left')
seed = pd.read_csv(REPO / 'transform/seeds/compound_cliff_params.csv')
seed = seed[seed.fit_source == 'cox_km_survival']
g = df.groupby(['circuit_key', 'compound_code', 'race_year'])


def clamp(x, comp):
    d = D.get(comp, D['MEDIUM'])['wear_gradient']
    return d if (x is None or x < 0.005 or x > 0.3) else x


rows = []
for _, s in seed.iterrows():
    key = (s.circuit_key, s.compound_code, int(s.season))
    if key not in g.groups:
        continue
    fresh = F.fresh_tyre_only(g.get_group(key))
    sub = fresh[fresh.fuel_s.notna()]
    rebuilt = estimate_wear_gradient(fresh, s.compound_cliff_onset_laps, pace_col='normalized_pace_s')
    fuelcorr = estimate_wear_gradient(sub.assign(normalized_pace_s=sub.normalized_pace_s - sub.fuel_s),
                                      s.compound_cliff_onset_laps, pace_col='normalized_pace_s')
    rows.append(dict(seed=s.compound_wear_gradient, rebuilt=round(clamp(rebuilt, s.compound_code), 4),
                     fuelcorr=round(clamp(fuelcorr, s.compound_code), 4),
                     fuel_gain=sub.fuel_gain_s_per_lap.mean()))
r = pd.DataFrame(rows)
print("\n## (b) wear gradient (s/lap), production estimator, seed onset per cox_km cell")
print(f"cells: {len(r)}; rebuilt == seed to 4 dp: {(abs(r.rebuilt - r.seed) < 1e-4).sum()}")
print(r[['seed', 'rebuilt', 'fuelcorr', 'fuel_gain']].describe().round(4).to_string())
print(f"median ratio fuel-corrected / seed: {np.median(r.fuelcorr / r.seed):.3f}; "
      f"/ rebuilt: {np.median(r.fuelcorr / r.rebuilt):.3f}; "
      f"cells where the fuel-corrected gradient is higher: {(r.fuelcorr > r.rebuilt + 1e-6).sum()} / {len(r)}")
