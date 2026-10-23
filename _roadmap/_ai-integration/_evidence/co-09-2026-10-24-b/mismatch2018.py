# Reproduce the investigation's SC/VSC cut-run count from raw bronze (its q3.py logic)
# and diff it against the warehouse's sc_pit / vsc_pit runs, to explain the 2018 gap (47 vs 85).
import duckdb,sys
db=sys.argv[1]; bronze=sys.argv[2]
c=duckdb.connect()
c.execute(f"attach '{db}' as w (read_only)")
c.execute(f"create view l as select * from read_parquet('{bronze}/laps/season=*/race=*/*_laps.parquet', hive_partitioning=false, union_by_name=true)")
c.execute("""create table lp as select season,race_id r,Driver d,Stint s,LapNumber ln,TyreLife age,Compound cmp,TrackStatus ts from l where Stint is not null""")
c.execute("""create table fr as select season,r,d,s, arg_min(age,ln) t0, arg_min(cmp,ln) c0, min(ln) l0, max(ln) l1, arg_max(age,ln) t1, arg_max(cmp,ln) c1, arg_max(ts,ln) tsend from lp group by all""")
c.execute("""create table fr2 as select *, lag(t1) over w pt1, lag(c1) over w pc1, lag(tsend) over w ptse from fr window w as (partition by season,r,d order by s)""")
c.execute("""create table fr3 as select *, sum((not coalesce(pc1=c0 and t0=pt1+1 and regexp_matches(coalesce(ptse,''),'[4567]'),false))::int) over (partition by season,r,d order by s) run from fr2""")
c.execute("""create table runs as select season,r,d,run,min(s) s0,max(s) smax,min(l0) l0,max(l1) l1,arg_max(tsend,l1) tsend from fr3 group by all""")
c.execute("""create table runs2 as select *, smax=(select max(s) from fr where fr.season=runs.season and fr.r=runs.r and fr.d=runs.d) is_last,
 case when regexp_matches(coalesce(tsend,''),'5') then 'red' when regexp_matches(tsend,'4') then 'sc' when regexp_matches(tsend,'[67]') then 'vsc' else 'green' end reg from runs""")
c.execute("create table inv as select season, r, d, l1 end_lap, reg, l0 from runs2 where not is_last and reg in ('sc','vsc')")
print('investigation SC/VSC cut runs by season:')
print(c.sql("select season, count(*) filter (where reg='sc') sc, count(*) filter (where reg='vsc') vsc, count(*) total from inv group by 1 order by 1"))
c.execute("""create table wh as select e.race_year season, e.race_id r, e.driver_id d, e.end_lap_number end_lap, e.stint_end_cause cause, f.stint_length_laps n,
 (select min(g.lap_number) from w.int_stint_geometry g where g.stint_id=e.stint_id) l0,
 (select string_agg(distinct g.stint_source, ',') from w.int_stint_geometry g where g.stint_id=e.stint_id) src
 from w.int_stint_end_regime e join w.fct_stint_features f using(stint_id) where e.stint_end_cause in ('sc_pit','vsc_pit')""")
print('warehouse sc_pit/vsc_pit by season:')
print(c.sql("select season, count(*) filter (where cause='sc_pit') sc, count(*) filter (where cause='vsc_pit') vsc, count(*) total from wh group by 1 order by 1"))
c.execute("""create table d as select wh.*, inv.reg inv_reg from wh left join inv on inv.season=wh.season and inv.r=wh.r and inv.d=wh.d and inv.end_lap=wh.end_lap""")
print('2018 warehouse sc_pit runs with no investigation SC run at the same end lap, by why:')
print(c.sql("""select case when l0=1 and n=1 then 'lap-1-only stint (WI-05 lap-1 repair; bronze Stint is NULL on 2018 lap 1)'
   when src like '%pit_record%' then 'quarantined unit (stint served from pit record)'
   when inv_reg is not null then 'investigation calls it '||inv_reg
   else 'other' end why, count(*) from d where season=2018 and cause='sc_pit' and inv_reg is distinct from 'sc' group by 1 order by 2 desc"""))
print(c.sql("""select r, d, end_lap, n, l0, src, inv_reg from d where season=2018 and cause='sc_pit' and inv_reg is distinct from 'sc' and not (l0=1 and n=1) order by 1,2"""))
print('lap-1-only sc/vsc stints per season (warehouse):')
print(c.sql("select season, count(*) filter (where l0=1 and n=1) lap1_only, count(*) filter (where src like '%bronze_lap1_repaired%') touches_lap1_repair from wh group by 1 order by 1"))
print('bronze laps with NULL Stint on lap 1 per season:')
print(c.sql("select season, count(*) filter (where Stint is null and LapNumber=1) lap1_null, count(*) filter (where Stint is null) all_null from l group by 1 order by 1"))
print('investigation 2018 SC runs with no warehouse sc_pit at the same end lap:')
print(c.sql("""select inv.*, (select string_agg(cause||':'||end_lap, ',') from wh where wh.season=inv.season and wh.r=inv.r and wh.d=inv.d) wh_causes from inv where season=2018 and reg='sc' and not exists (select 1 from wh where wh.season=inv.season and wh.r=inv.r and wh.d=inv.d and wh.end_lap=inv.end_lap and wh.cause='sc_pit')"""))
print('stg_pits in-laps on lap 1, per season, and the lap-1-only sc stints of 2018 per race:')
print(c.sql("select race_year, count(*) from w.stg_pits where pit_in_lap_number=1 group by 1 order by 1"))
print(c.sql("select r, count(*) from d where season=2018 and l0=1 and n=1 group by 1 order by 1"))
