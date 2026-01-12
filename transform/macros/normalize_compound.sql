{#
  normalize_compound(compound_col)

  Maps Pirelli's 2018-era legacy compound names onto the modern SOFT/MEDIUM/HARD
  taxonomy so that compound-parameter joins (dim_compounds_season) land for 2018.

  Pirelli ran a 7-compound range in 2018 (HYPERSOFT/ULTRASOFT/SUPERSOFT/SOFT/
  MEDIUM/HARD/SUPERHARD); the cliff-parameter seed only fits the modern 5-name set
  ({SOFT, MEDIUM, HARD, INTERMEDIATE, WET}). Without normalisation the three
  legacy soft variants (8,836 laps, all 2018) get a 100%-NULL compound-param join.

  Scope: use this ONLY on ML-facing feature joins (e.g. fct_cliff_prediction_features'
  compound_params join). DO NOT normalise inside int_compound_cliff_predicted-its
  expected_compound_pace_s feeds int_lap_residual_decomposed.compound_component_s and
  therefore driver_skill_residual_s (the project's core metric). Normalising there
  would silently re-attribute compound vs. driver skill for 2018 legacy laps.

  Residual nulls (legacy laps at circuits with no slug-keyed 2018 SOFT fit) are
  intentional and carried by XGBoost's native missing-value handling. See ml/BUILD_LOG.md (L0-2).
#}
{% macro normalize_compound(compound_col) %}
    CASE {{ compound_col }}
        WHEN 'HYPERSOFT' THEN 'SOFT'
        WHEN 'ULTRASOFT' THEN 'SOFT'
        WHEN 'SUPERSOFT' THEN 'SOFT'
        ELSE {{ compound_col }}
    END
{% endmacro %}
