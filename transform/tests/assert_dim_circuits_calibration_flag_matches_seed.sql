-- TX-13: dim_circuits.calibration_flag must equal circuit_reference.calibration_flag on every row.
-- A failing row is a circuit whose flag was dropped, changed or mistyped on the way to the dimension.
SELECT
    s.circuit_key,
    s.calibration_flag AS seed_flag,
    d.calibration_flag AS dim_flag
FROM {{ ref('circuit_reference') }} AS s
LEFT JOIN {{ ref('dim_circuits') }} AS d ON d.circuit_key = s.circuit_key
WHERE d.circuit_key IS NULL
   OR d.calibration_flag IS DISTINCT FROM CAST(s.calibration_flag AS VARCHAR)
