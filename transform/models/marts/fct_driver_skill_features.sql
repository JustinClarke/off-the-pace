-- Gold layer: driver-race skill feature table for driver skill extraction model.
-- Grain: (race_year, race_id, driver_id) one row per driver per race.
-- Aggregates lap-level residuals, synthetic teammate deltas, constructor pace indices,
-- and circuit characteristics into a single race-grain feature vector.
--
-- Clean-lap filter (applied to residual + skill aggregates):
--   correction_weight = 1.0 AND anomaly_class NOT IN ('mistake','conditions') AND is_rain_lap = FALSE
--
-- driver_skill_residual_s sign convention: negative = faster than field (after physics removal).
-- driver_skill_proxy_s sign convention: positive = ego faster than synthetic teammate.
{{ config(materialized='table') }}

WITH residuals AS (
    SELECT
        lap_id,
        race_year,
        race_id,
        driver_id,
        constructor_id,
        lap_number,
        driver_skill_residual_s,
        correction_weight,
        rainfall_flag
    FROM {{ ref('int_lap_residual_decomposed') }}
),

anomaly AS (
    SELECT
        lap_id,
        anomaly_class,
        usable_for_modelling,
        is_rain_lap
    FROM {{ ref('int_lap_anomaly_flags') }}
),

-- Lap-grain join before aggregation
laps_with_flags AS (
    SELECT
        r.lap_id,
        r.race_year,
        r.race_id,
        r.driver_id,
        r.constructor_id,
        r.lap_number,
        r.driver_skill_residual_s,
        r.correction_weight,
        r.rainfall_flag,
        a.anomaly_class,
        a.usable_for_modelling,
        a.is_rain_lap
    FROM residuals r
    LEFT JOIN anomaly a USING (lap_id)
),

-- Residual aggregates at race grain (clean laps only)
residual_agg AS (
    SELECT
        race_year,
        race_id,
        driver_id,
        constructor_id,
        AVG(CASE
            WHEN correction_weight = 1.0
              AND anomaly_class NOT IN ('mistake', 'conditions')
              AND is_rain_lap = FALSE
            THEN driver_skill_residual_s
        END)                                                AS driver_residual_mean_s,
        STDDEV(CASE
            WHEN correction_weight = 1.0
              AND anomaly_class NOT IN ('mistake', 'conditions')
              AND is_rain_lap = FALSE
            THEN driver_skill_residual_s
        END)                                                AS driver_residual_stddev_s,
        PERCENTILE_CONT(0.5) WITHIN GROUP (
            ORDER BY CASE
                WHEN correction_weight = 1.0
                  AND anomaly_class NOT IN ('mistake', 'conditions')
                  AND is_rain_lap = FALSE
                THEN driver_skill_residual_s
            END
        )                                                   AS driver_residual_median_s,
        COUNT(CASE
            WHEN correction_weight = 1.0
              AND anomaly_class NOT IN ('mistake', 'conditions')
              AND is_rain_lap = FALSE
            THEN 1
        END)                                                AS clean_lap_count,
        COUNT(*)                                            AS total_race_laps,
        -- Race-level wet flag: any rainfall detected during the race
        BOOL_OR(COALESCE(rainfall_flag, FALSE))             AS race_wet_flag,
        -- ML eligible share: fraction of laps flagged usable_for_modelling
        ROUND(
            CAST(COUNT(CASE WHEN usable_for_modelling THEN 1 END) AS DOUBLE)
            / NULLIF(COUNT(*), 0),
        4)                                                  AS ml_eligible_lap_share
    FROM laps_with_flags
    GROUP BY race_year, race_id, driver_id, constructor_id
),

-- Synthetic teammate: aggregate to race grain with same clean-lap filter
teammate_agg AS (
    SELECT
        st.race_year,
        st.race_id,
        st.ego_driver_id                                    AS driver_id,
        -- Weighted mean: AVG(proxy * weight) / AVG(weight)
        AVG(st.driver_skill_proxy_s * st.pair_quality_weight)
            / NULLIF(AVG(st.pair_quality_weight), 0)        AS driver_skill_proxy_mean_s,
        AVG(st.pair_quality_weight)                         AS pair_quality_weight_mean,
        BOOL_OR(st.teammate_available_flag)                 AS teammate_available_flag,
        ROUND(
            CAST(COUNT(CASE WHEN st.strategic_divergence_flag THEN 1 END) AS DOUBLE)
            / NULLIF(COUNT(*), 0),
        4)                                                  AS strategic_divergence_share
    FROM {{ ref('int_synthetic_teammate') }} st
    -- Same clean-lap filter applied via join back to anomaly flags
    JOIN laps_with_flags lf
        ON st.race_year  = lf.race_year
        AND st.race_id   = lf.race_id
        AND st.lap_number = lf.lap_number
        AND st.ego_driver_id = lf.driver_id
        AND lf.correction_weight = 1.0
        AND lf.anomaly_class NOT IN ('mistake', 'conditions')
        AND lf.is_rain_lap = FALSE
    GROUP BY st.race_year, st.race_id, st.ego_driver_id
),

-- Constructor structural pace (#6): one row per constructor-race, no lap grain needed.
-- Initial transform release: replaces the legacy EW rolling index.
-- Power/aero split not yet available at race grain (subsequent sector decomposition).
constructor_final AS (
    SELECT
        race_year,
        race_id,
        constructor_id,
        constructor_structural_pace_s       AS constructor_power_pace_index_final,
        constructor_structural_pace_s       AS constructor_aero_pace_index_final,
        -- Confidence proxy from sample size: saturates at 1.0 above 500 laps
        LEAST(panel_observations_n / 500.0, 1.0) AS constructor_index_confidence_final
    FROM {{ ref('int_constructor_structural_pace') }}
),

-- Resolve race_id → circuit_key via race_to_track seed
race_to_track AS (
    SELECT
        race_id,
        track_id    AS circuit_key
    FROM {{ ref('race_to_track') }}
),

dim_circuits AS (
    SELECT
        circuit_key,
        track_energy_index,
        abrasiveness_index
    FROM {{ ref('dim_circuits') }}
),

dim_drivers AS (
    SELECT
        driver_id,
        debut_year
    FROM {{ ref('dim_drivers') }}
),

dim_constructors AS (
    SELECT
        constructor_id,
        pu_family
    FROM {{ ref('dim_constructors') }}
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['ra.race_year', 'ra.race_id', 'ra.driver_id']) }}
                                                            AS driver_race_id,
    ra.driver_id,
    ra.race_year,
    ra.race_id,
    ra.constructor_id,
    rtt.circuit_key,
    dc_con.pu_family,
    dd.debut_year                                           AS driver_debut_year,

    -- Residual aggregates (clean laps only)
    ra.driver_residual_mean_s,
    ra.driver_residual_stddev_s,
    ra.driver_residual_median_s,
    ra.clean_lap_count,

    -- Synthetic teammate (weighted, clean laps only)
    ta.driver_skill_proxy_mean_s,
    ta.pair_quality_weight_mean,
    COALESCE(ta.teammate_available_flag, FALSE)             AS teammate_available_flag,
    COALESCE(ta.strategic_divergence_share, 0.0)            AS strategic_divergence_share,

    -- Constructor pace index at race end
    cf.constructor_power_pace_index_final,
    cf.constructor_aero_pace_index_final,
    cf.constructor_index_confidence_final,

    -- Race context
    ra.race_wet_flag,
    dc_cir.track_energy_index                               AS circuit_energy_index,
    dc_cir.abrasiveness_index                               AS circuit_abrasiveness_index,
    ra.total_race_laps,

    -- Quality flag
    ra.ml_eligible_lap_share

FROM residual_agg ra
LEFT JOIN teammate_agg ta           USING (race_year, race_id, driver_id)
LEFT JOIN constructor_final cf      USING (race_year, race_id, constructor_id)
LEFT JOIN race_to_track rtt         USING (race_id)
LEFT JOIN dim_circuits dc_cir       USING (circuit_key)
LEFT JOIN dim_drivers dd            USING (driver_id)
LEFT JOIN dim_constructors dc_con   ON ra.constructor_id = dc_con.constructor_id
ORDER BY ra.race_year, ra.race_id, ra.driver_id
