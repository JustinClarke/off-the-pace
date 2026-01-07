-- Constructor / team reference with power-unit family grouping.
-- pu_family is used in Layer 04 to condition constructor_pace_index
-- on similar-engine teams (e.g. Mercedes PU customers share base drag).
{{ config(materialized='table') }}

WITH laps AS (
    SELECT * FROM {{ ref('stg_laps') }}
),

teams AS (
    SELECT DISTINCT constructor_id AS team_name
    FROM laps
    WHERE constructor_id IS NOT NULL
),

-- PU family mapping: manually maintained until an external seed is built
pu_mapping AS (
    SELECT * FROM (VALUES
        ('Mercedes',          'mercedes_pu'),
        ('Red Bull Racing',   'honda_pu'),
        ('Ferrari',           'ferrari_pu'),
        ('McLaren',           'mercedes_pu'),
        ('Alpine',            'renault_pu'),
        ('Aston Martin',      'mercedes_pu'),
        ('AlphaTauri',        'honda_pu'),
        ('Alfa Romeo',        'ferrari_pu'),
        ('Haas F1 Team',      'ferrari_pu'),
        ('Williams',          'mercedes_pu'),
        ('Racing Point',      'mercedes_pu'),
        ('Renault',           'renault_pu'),
        ('Toro Rosso',        'honda_pu'),
        ('Force India',       'mercedes_pu'),
        ('Sauber',            'ferrari_pu'),
        ('RB',                'honda_pu')
    ) AS t(team_name, pu_family)
)

SELECT
    t.team_name                         AS constructor_id,
    COALESCE(p.pu_family, 'unknown_pu') AS pu_family
FROM teams t
LEFT JOIN pu_mapping p USING (team_name)
ORDER BY constructor_id
