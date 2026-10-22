-- Constructor / team reference: power-unit family and team lineage.
--
-- Built from the fixed list below, not from whichever laps are loaded (CO-29),
-- so every build (the CI fixture included) has every team the frozen fits and
-- the marts can name. A team name FastF1 reports that is not listed here fails
-- the stg_laps.constructor_id relationships test, which is the prompt to add
-- its row.
--
-- pu_family is a reference attribute only: it is carried onto fct_lap_residuals
-- and fct_driver_skill_features, and no pace index or model reads it. (This
-- header used to say it conditions constructor_pace_index on similar-engine
-- teams in Layer 04; that was never built. F17.) One family per team NAME, not
-- per season.
--
-- constructor_lineage_id groups the names one team has raced under. F1 renames
-- its teams every year or two and each rename arrives as a new constructor_id;
-- the owner's ruling (2026-10-23) is that a rename is the same team. The id is
-- the snake-cased earliest name the team has in the data (2018 onward):
--   force_india: Force India -> Racing Point -> Aston Martin
--   toro_rosso:  Toro Rosso -> AlphaTauri -> RB -> Racing Bulls
--   sauber:      Sauber -> Alfa Romeo Racing -> Alfa Romeo -> Kick Sauber
--   renault:     Renault -> Alpine
-- Every other team is its own lineage.
{{ config(materialized='table') }}

WITH constructors AS (
    SELECT * FROM (
        VALUES
        ('Mercedes', 'mercedes_pu', 'mercedes'),
        ('Red Bull Racing', 'honda_pu', 'red_bull_racing'),
        ('Ferrari', 'ferrari_pu', 'ferrari'),
        ('McLaren', 'mercedes_pu', 'mclaren'),
        ('Haas F1 Team', 'ferrari_pu', 'haas_f1_team'),
        ('Williams', 'mercedes_pu', 'williams'),
        ('Force India', 'mercedes_pu', 'force_india'),
        ('Racing Point', 'mercedes_pu', 'force_india'),
        ('Aston Martin', 'mercedes_pu', 'force_india'),
        ('Toro Rosso', 'honda_pu', 'toro_rosso'),
        ('AlphaTauri', 'honda_pu', 'toro_rosso'),
        ('RB', 'honda_pu', 'toro_rosso'),
        ('Racing Bulls', 'honda_pu', 'toro_rosso'),
        ('Sauber', 'ferrari_pu', 'sauber'),
        ('Alfa Romeo Racing', 'ferrari_pu', 'sauber'),
        ('Alfa Romeo', 'ferrari_pu', 'sauber'),
        ('Kick Sauber', 'ferrari_pu', 'sauber'),
        ('Renault', 'renault_pu', 'renault'),
        ('Alpine', 'renault_pu', 'renault')
    -- the t(...) column-list alias names the VALUES columns; load-bearing
    ) AS t (constructor_id, pu_family, constructor_lineage_id)  -- noqa: AL05
)

SELECT
    constructor_id,
    pu_family,
    constructor_lineage_id
FROM constructors
ORDER BY constructor_id
