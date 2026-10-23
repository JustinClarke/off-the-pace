# CO-09b evidence: before = CO-09 working tree build (scratch copy), after = + penalty join + cut-short fields.
import duckdb,sys,os
B=sys.argv[1]; OUT=sys.argv[2]
# connect to the after copy itself: its staging views name the catalog 'dev'
c=duckdb.connect(f'{B}/after/dev.duckdb', read_only=True)
c.execute(f"attach '{B}/before/dev.duckdb' as b (read_only)")  # only its TABLES are read
def show(title,q,csv=None):
    df=c.sql(q).df(); print('\n## '+title); print(df.to_string(index=False))
    if csv: df.to_csv(os.path.join(OUT,csv),index=False)
    return df
# pair list (green age+1 pairs) from the feed numbering, with penalty match, on the after copy
c.execute("""create temp table fb as select l.race_year,l.race_id,l.driver_id,q.stint_number,
 min(l.lap_number) first_lap,max(l.lap_number) last_lap, arg_min(q.compound,l.lap_number) c0, arg_max(q.compound,l.lap_number) c1,
 arg_min(q.tyre_life,l.lap_number) a0, arg_max(q.tyre_life,l.lap_number) a1,
 arg_max(not(l.is_red_flag_lap or l.is_safety_car_lap or l.is_vsc_lap),l.lap_number) endg
 from dev.main.stg_laps l join dev.main.stg_lap_tyre_qa q on l.lap_id=q.lap_id where q.stint_number is not null group by all""")
c.execute("""create temp table pr as select *, lag(c1) over w pc1, lag(a1) over w pa1, lag(endg) over w pendg, lag(last_lap) over w pl1, lag(stint_number) over w ps
 from fb window w as (partition by race_year,race_id,driver_id order by stint_number)""")
c.execute("""create temp table gp as select race_year,race_id,driver_id,ps::int s1,stint_number::int s2,pl1 l1,first_lap f2,c0 compound,pa1 last_age_s1,a0 first_age_s2 from pr where pc1=c0 and a0=pa1+1 and pendg""")
c.execute(r"""create temp table pen as select distinct rc.race_id, res.driver_id, rc.lap_number, rc.message_text from dev.main.stg_race_control rc join dev.main.stg_results res on rc.race_id=res.race_id
 and regexp_extract(upper(rc.message_text),'(DRIVE[ -]?THROUGH|STOP ?/ ?GO|STOP-GO|TIME) PENALTY FOR CAR ([0-9]+)',2)=res.driver_number where rc.lap_number is not null""")
c.execute("""create temp table gpm as select gp.*, string_agg(pen.lap_number||': '||pen.message_text,' || ') penalty_messages_in_window,
 (select count(distinct g.stint_id) from dev.main.int_stint_geometry g where g.race_id=gp.race_id and g.driver_id=gp.driver_id and g.lap_number in (gp.l1, gp.f2))=1 joined_in_after
 from gp left join pen on pen.race_id=gp.race_id and pen.driver_id=gp.driver_id and pen.lap_number between gp.l1-1 and gp.l1+1 group by all""")
show('All 36 green same-tyre (age + 1) pairs: penalty message in window and whether joined (after)',
     "select *, case when race_id='2023_20' and driver_id in ('PIA','RIC') and l1=2 or race_id='2020_14' and driver_id='OCO' and l1=1 then 'FLAG: looks like a neutralised stop the flags missed' end flag from gpm order by race_year, race_id, driver_id, s1", 'green_pairs_36.csv')
show('Pairs by season: joined vs left split', """select race_year, count(*) pairs, count(*) filter (where joined_in_after) joined, count(*) filter (where not joined_in_after) left_split,
 count(*) filter (where penalty_messages_in_window is not null) with_penalty_msg from gpm group by 1 order by 1""", 'pairs_by_season.csv')
show('Consistency: joined iff penalty message', "select joined_in_after, penalty_messages_in_window is not null has_msg, count(*) from gpm group by all")
# stints and labels per season
lab="""select race_year, count(*) stints, count(*) filter (where stint_end_cause='green_pit') green_pit, count(*) filter (where stint_end_cause='sc_pit') sc_pit,
 count(*) filter (where stint_end_cause='vsc_pit') vsc_pit, count(*) filter (where stint_end_cause='red') red, count(*) filter (where stint_end_cause='race_end') race_end,
 count(*) filter (where stint_end_cause='retirement') retirement, count(*) filter (where is_stint_life_censored) life_censored, count(*) filter (where not is_stint_life_censored) life_observed,
 count(*) filter (where reached_flag) rf_true, count(*) filter (where not reached_flag) rf_false, count(*) filter (where reached_flag is null) rf_null from {s}.int_stint_end_regime group by 1"""
c.execute("create temp table lb as "+lab.format(s='b')); c.execute("create temp table la as "+lab.format(s='dev.main'))
show('Stint labels per season, before (CO-09) -> after (CO-09b)', """select b.race_year, b.stints||'->'||a.stints stints, b.green_pit||'->'||a.green_pit green_pit, b.sc_pit||'->'||a.sc_pit sc_pit, b.vsc_pit||'->'||a.vsc_pit vsc_pit,
 b.red||'->'||a.red red, b.race_end||'->'||a.race_end race_end, b.retirement||'->'||a.retirement retirement, b.life_observed||'->'||a.life_observed life_observed,
 b.life_censored||'->'||a.life_censored life_censored, b.rf_false||'->'||a.rf_false reached_flag_false, b.rf_true||'->'||a.rf_true reached_flag_true, b.rf_null||'->'||a.rf_null reached_flag_null
 from lb b join la a using(race_year) order by 1""", 'labels_per_season.csv')
# lap grain
c.execute("""create temp table lg as select g.race_year, g.lap_id, gb.stint_id sb, g.stint_id sa, eb.stint_end_cause cb, ea.stint_end_cause ca, eb.is_stint_life_censored lcb, ea.is_stint_life_censored lca,
 eb.reached_flag rfb, ea.reached_flag rfa from dev.main.int_stint_geometry g join b.int_stint_geometry gb using(lap_id)
 join b.int_stint_end_regime eb on eb.stint_id=gb.stint_id join dev.main.int_stint_end_regime ea on ea.stint_id=g.stint_id""")
show('Lap grain: laps per season whose run, cause, life censoring or reached_flag changed', """select race_year, count(*) laps, count(*) filter (where sb<>sa) stint_id_changed, count(*) filter (where cb is distinct from ca) cause_changed,
 count(*) filter (where lcb is distinct from lca) life_censor_changed, count(*) filter (where rfb is distinct from rfa) reached_flag_changed from lg group by 1 order by 1""", 'lap_grain_changes.csv')
show('Lap grain: cause transitions', "select cb before_cause, ca after_cause, count(*) laps from lg where cb is distinct from ca group by all order by 3 desc")
show('Unchanged-key check: stints present in after that did not exist before (expect 0)', "select count(*) from dev.main.int_stint_end_regime x where not exists (select 1 from b.int_stint_end_regime y where y.stint_id=x.stint_id)")
show('Cliff mart rows per season before/after and labelled next_5 rows', """select a.race_year, (select count(*) from b.fct_cliff_prediction_features x where x.race_year=a.race_year) rows_before, count(*) rows_after,
 (select count(next_5_lap_cumulative_jump_s) from b.fct_cliff_prediction_features x where x.race_year=a.race_year) n5_before, count(next_5_lap_cumulative_jump_s) n5_after,
 (select round(avg(next_5_lap_cumulative_jump_s),4) from b.fct_cliff_prediction_features x where x.race_year=a.race_year) mean_before, round(avg(next_5_lap_cumulative_jump_s),4) mean_after
 from dev.main.fct_cliff_prediction_features a group by 1 order by 1""", 'cliff_mart_per_season.csv')
# task B
show('Task B: cut-short fields coverage', """select count(*) stints, count(laps_completed) laps_completed, count(tyre_age_at_fit) tyre_age_at_fit, count(*) filter (where tyre_age_at_fit is distinct from starting_tyre_age_laps+1) age_ne_start_plus1,
 count(*) filter (where fresh_at_fit) fresh_at_fit_true, count(*) filter (where is_fresh_tyre_raw) raw_fresh_true, count(*) filter (where fresh_at_fit <> is_fresh_tyre_raw) fresh_disagree,
 count(cut_reason) cut_runs, count(clean_laps_to_cut) clean_laps_filled, count(slope_to_cut_s_per_lap) slope_filled, count(mean_clean_pace_s) mean_filled,
 count(*) filter (where slope_reliable) reliable, round(avg(slope_reliable::int),3) reliable_share,
 count(*) filter (where clean_laps_to_cut>=5) clean_ge5, count(*) filter (where cut_reason is null and (clean_laps_to_cut is not null or slope_to_cut_s_per_lap is not null or mean_clean_pace_s is not null or slope_reliable is not null)) leak_outside_cut
 from dev.main.fct_stint_features""", 'cut_fields_coverage.csv')
show('Task B: per season and reason', """select race_year, cut_reason, count(*) runs, count(*) filter (where slope_reliable) reliable, round(avg(slope_reliable::int),3) reliable_share, median(clean_laps_to_cut) median_clean,
 count(*) filter (where clean_laps_to_cut=0) zero_clean, round(median(slope_to_cut_s_per_lap),4) median_slope, round(quantile_cont(slope_to_cut_s_per_lap,0.1),3) p10_slope, round(quantile_cont(slope_to_cut_s_per_lap,0.9),3) p90_slope
 from dev.main.fct_stint_features where cut_reason is not null group by all order by 1,2""", 'cut_fields_by_season.csv')
show('Task B: sample rows', """select stint_id, compound, laps_completed, tyre_age_at_fit, fresh_at_fit, is_fresh_tyre_raw, cut_reason, clean_laps_to_cut, round(slope_to_cut_s_per_lap,4) slope, round(mean_clean_pace_s,3) mean_pace, slope_reliable
 from dev.main.fct_stint_features where stint_id in ('2025_2025_10_VER_2','2024_2024_23_NOR_4') or stint_id in (select stint_id from dev.main.fct_stint_features where cut_reason is not null order by hash(stint_id) limit 8) order by 1""", 'cut_fields_sample.csv')
show('Task B: same field on a non-cut run (pace fields NULL)', "select stint_id, stint_end_cause, laps_completed, tyre_age_at_fit, fresh_at_fit, cut_reason, clean_laps_to_cut, slope_to_cut_s_per_lap, slope_reliable from dev.main.fct_stint_features where stint_end_cause='green_pit' order by hash(stint_id) limit 3")
show('assert_tyre_run_key check 3 is not vacuous: green feed boundaries inside an after run (all should carry a penalty)', """
 with fb as (select g.stint_id, g.race_id, g.driver_id, g.lap_number, q.stint_number fs, lag(q.stint_number) over w pfs, lag(not(g.is_red_flag_lap or g.is_safety_car_lap or g.is_vsc_lap)) over w pg, lag(g.lap_number) over w pl
 from dev.main.int_stint_geometry g join dev.main.stg_lap_tyre_qa q using(lap_id) where g.stint_number is not null window w as (partition by g.stint_id order by g.lap_number))
 select count(*) green_boundaries_inside_runs, count(*) filter (where exists (select 1 from pen where pen.race_id=fb.race_id and pen.driver_id=fb.driver_id and pen.lap_number between fb.pl-1 and fb.pl+1)) with_penalty
 from fb where fs is distinct from pfs and pfs is not null and pg""")
