// Curated starter queries for the Query Lab, surfaced as click-to-load chips. Each showcases
// a different mart/fact so a first-time visitor sees the warehouse's range immediately.
export interface QueryExample {
  label: string
  sql: string
}

export const EXAMPLES: QueryExample[] = [
  {
    label: 'Worst degraders by compound',
    sql: `SELECT compound,
       count(*)            AS stints,
       round(avg(end_of_stint_pace_falloff_s_per_lap), 4) AS avg_deg_per_lap
FROM fct_stint_features
WHERE compound IS NOT NULL
GROUP BY compound
ORDER BY avg_deg_per_lap DESC`,
  },
  {
    label: 'Ghost-car standings',
    sql: `SELECT ego_driver_id,
       round(avg(predicted_finish_position), 2) AS avg_ghost_finish,
       count(*) AS races
FROM fct_ghost_race_finish
GROUP BY ego_driver_id
HAVING count(*) >= 5
ORDER BY avg_ghost_finish ASC
LIMIT 20`,
  },
  {
    label: 'Driver skill leaderboard',
    sql: `SELECT driver_id,
       round(avg(driver_skill_proxy_mean_s), 3) AS avg_skill_s,
       count(*) AS races
FROM fct_driver_skill_features
GROUP BY driver_id
HAVING count(*) >= 20
ORDER BY avg_skill_s ASC
LIMIT 25`,
  },
  {
    label: 'Circuits covered',
    sql: `SELECT circuit_id, circuit_name, corner_count, lap_length_km
FROM dim_circuits
ORDER BY circuit_name`,
  },
  {
    label: 'Corner skill across seasons',
    sql: `SELECT race_year,
       driver_id,
       round(corner_skill_index, 3) AS corner_skill_index
FROM mart_corner_skill_driver
ORDER BY race_year DESC, corner_skill_index ASC
LIMIT 30`,
  },
  {
    label: 'List all tables',
    sql: `SHOW TABLES`,
  },
]
