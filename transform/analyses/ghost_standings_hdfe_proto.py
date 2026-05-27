import duckdb, pandas as pd, numpy as np
import pyfixest as pf
from scipy.stats import spearmanr

con = duckdb.connect('../data/dev.duckdb', read_only=True)

# ---- 1. clean lap panel (mirrors int_driver_race_skill_loro clean_panel) ----
panel = con.execute("""
WITH fuel AS (SELECT lap_id,race_year,race_id,driver_id,lap_number,lap_time_s FROM int_lap_fuel_state),
field_pace AS (SELECT race_year,race_id,lap_number,field_pace_smoothed_s FROM int_field_pace_curve),
laps_meta AS (SELECT lap_id,constructor_id FROM stg_laps),
corr AS (SELECT lap_id,correction_weight FROM int_event_corrections),
evo AS (SELECT race_year,race_id,lap_number,rainfall_flag FROM int_track_evolution)
SELECT f.race_year, f.race_id, f.driver_id, lm.constructor_id,
       f.lap_time_s - COALESCE(fp.field_pace_smoothed_s, f.lap_time_s) AS pace_delta_s
FROM fuel f
JOIN laps_meta lm USING(lap_id)
LEFT JOIN field_pace fp ON f.race_year=fp.race_year AND f.race_id=fp.race_id AND f.lap_number=fp.lap_number
LEFT JOIN corr cor USING(lap_id)
LEFT JOIN evo e ON f.race_year=e.race_year AND f.race_id=e.race_id AND f.lap_number=e.lap_number
WHERE f.lap_time_s IS NOT NULL AND COALESCE(cor.correction_weight,1.0)=1.0 AND COALESCE(e.rainfall_flag,FALSE)=FALSE
""").fetchdf()
panel['constructor_race'] = (panel.race_year.astype(str)+'_'+panel.race_id.astype(str)+'_'+panel.constructor_id.astype(str))

# ---- 2. two-way FE: pace_delta ~ driver_FE + constructor_race_FE ----
m = pf.feols("pace_delta_s ~ 1 | driver_id + constructor_race", data=panel)
fe = m.fixef()
car_fe = pd.Series(fe['C(constructor_race)']); car_fe.index = car_fe.index.astype(str)
drv_fe = pd.Series(fe['C(driver_id)']); drv_fe.index = drv_fe.index.astype(str)

print("=== Global driver FE (neg=faster) top10 / bottom5 ===")
s = drv_fe.sort_values()
for did,v in list(s.items())[:10]: print(f"  {did:16s} {v:+.3f}")
print("  ...")
for did,v in list(s.items())[-5:]: print(f"  {did:16s} {v:+.3f}")

# ---- 3. per (race,driver) own_median and new signal ----
own = (panel.groupby(['race_year','race_id','driver_id','constructor_id'])
       .agg(own_median=('pace_delta_s','median'), nlaps=('pace_delta_s','size')).reset_index())
own['constructor_race'] = (own.race_year.astype(str)+'_'+own.race_id.astype(str)+'_'+own.constructor_id.astype(str))
own['car_fe'] = own.constructor_race.map(car_fe)
own['drv_fe'] = own.driver_id.map(drv_fe)
own = own.dropna(subset=['car_fe'])
# new field-anchored equal-car signal
own['field_new'] = own.own_median - own.car_fe   # neg=faster

# ---- circuit mapping (slug of circuit_name, per the model) ----
cmap = con.execute("""
SELECT cr.circuit_key, regexp_replace(lower(trim(cr.circuit_name)),'[^a-z0-9]+','-','g') AS circuit_id
FROM circuit_reference cr
""").fetchdf()
rtt = con.execute("SELECT CAST(race_id AS VARCHAR) AS rk, track_id AS circuit_key FROM race_to_track").fetchdf()
own['race_id'] = own.race_id.astype(str)
own['rk'] = own.race_id.str.replace('_','',regex=False)
own = own.merge(rtt, on='rk', how='left').merge(cmap, on='circuit_key', how='left')
own['circuit_id'] = own.circuit_id.fillna(own.circuit_key)
own['era'] = np.where(own.race_year < 2022, 'pre2022','post2022')

# ---- 4. believability gate ----
def leaders(df, label):
    g = (df.groupby(['era','circuit_id','driver_id']).field_new.mean().reset_index())
    # require >=2 races per cell like model default? keep simple: raw mean
    lead = g.loc[g.groupby(['era','circuit_id']).field_new.idxmin()]
    print(f"\n--- {label}: circuit leaders by era ---")
    for era in ['post2022','pre2022']:
        vc = lead[lead.era==era].driver_id.value_counts()
        print(f"  {era}: " + ", ".join(f"{d}:{n}" for d,n in vc.head(8).items()))

leaders(own, "NEW (HDFE de-biased)")

# current board leaders for comparison
cur = con.execute("""
SELECT era_key, circuit_id, driver_id, shrunk_affinity_s, n_obs
FROM int_driver_circuit_era_affinity
""").fetchdf()
curlead = cur.loc[cur.groupby(['era_key','circuit_id']).shrunk_affinity_s.idxmin()]
print("\n--- CURRENT board: circuit leaders by era ---")
for era in ['post2022','pre2022']:
    vc = curlead[curlead.era_key==era].driver_id.value_counts()
    print(f"  {era}: " + ", ".join(f"{d}:{n}" for d,n in vc.head(8).items()))

# ---- Albon @ Zandvoort post2022 ranking ----
def rank_at(df, circ_sub, era):
    sub = df[(df.era==era) & (df.circuit_id.str.contains(circ_sub, case=False, na=False))]
    g = sub.groupby('driver_id').field_new.mean().sort_values()
    return g
print("\n=== Zandvoort post2022 NEW (field_new, neg=faster) ===")
z = rank_at(own,'zand','post2022')
for i,(d,v) in enumerate(z.items()): print(f"  {i+1:2d}. {d:16s} {v:+.3f}")

# ---- correlation: score vs own pace, score vs teammate laps (leak check) ----
# per (race,driver): own pace = own_median; teammate clean laps
own_sorted = own.copy()
# teammate laps per (race,constructor) excluding self
tot = own.groupby(['race_year','race_id','constructor_id']).nlaps.sum().rename('car_laps')
own_sorted = own_sorted.merge(tot, on=['race_year','race_id','constructor_id'])
own_sorted['teammate_laps'] = own_sorted.car_laps - own_sorted.nlaps
post = own_sorted[own_sorted.era=='post2022']
print("\n=== leak checks (post2022, per race-driver) ===")
print(f"  corr(field_new, own_median)   = {post.field_new.corr(post.own_median):+.3f}  (want POSITIVE: slow drivers score worse)")
print(f"  corr(field_new, teammate_laps)= {post.field_new.corr(post.teammate_laps):+.3f}  (want ~0: no teammate leak)")

# ---- cross-check vs sector decomposition (method user trusts) ----
sec = con.execute("""
SELECT driver_id, race_year, race_id, AVG(sector_driver_skill_residual_s) AS sec_skill
FROM int_sector_residual_decomposed
GROUP BY 1,2,3
""").fetchdf()
sec['race_id'] = sec.race_id.astype(str)
mrg = own.merge(sec, on=['driver_id','race_year','race_id'], how='inner')
# aggregate per driver-circuit-era
agg_new = mrg.groupby(['era','circuit_id','driver_id']).agg(new=('field_new','mean'), sec=('sec_skill','mean')).reset_index()
rho_new,_ = spearmanr(agg_new.new, agg_new.sec)
# current board vs sector
cur2 = cur.rename(columns={'era_key':'era'}).merge(
    sec.groupby('driver_id').sec_skill.mean().rename('sec_drv'), on='driver_id', how='left')
print(f"\n=== vs Sector Decomposition (per driver-circuit-era) ===")
print(f"  Spearman(NEW field, sector skill) = {rho_new:+.3f}  (n={len(agg_new)})")

# also compare to CURRENT board correlation with sector at same grain
sec['rk'] = sec.race_id.str.replace('_','',regex=False)
secg = sec.merge(rtt,on='rk',how='left').merge(cmap,on='circuit_key',how='left')
secg['circuit_id']=secg.circuit_id.fillna(secg.circuit_key)
secg['era']=np.where(secg.race_year<2022,'pre2022','post2022')
secagg = secg.groupby(['era','circuit_id','driver_id']).sec_skill.mean().reset_index()
curm = cur.rename(columns={'era_key':'era'}).merge(secagg,on=['era','circuit_id','driver_id'],how='inner')
rho_cur,_ = spearmanr(curm.shrunk_affinity_s, curm.sec_skill)
newm = agg_new.merge(secagg,on=['era','circuit_id','driver_id'],how='inner',suffixes=('','_s2'))
rho_new2,_ = spearmanr(newm.new, newm.sec_skill)
print(f"  Spearman matched grain: CURRENT={rho_cur:+.3f} (n={len(curm)})  NEW={rho_new2:+.3f} (n={len(newm)})")
