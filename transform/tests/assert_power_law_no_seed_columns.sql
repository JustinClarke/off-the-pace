-- T51 (WI-17): the F2/FD3 guard. Nothing the power-law build trains on may carry the compound
-- seed or anything priced from it -- FD3 is still open on whether that seed may be fitted on the
-- race it scores.
--
-- Checked on every model the build writes (the lap set, both fits, the training frame):
--   1. No column matches the guarded patterns: the compound_cliff_params parameters
--      (compound_grip_peak, compound_wear_gradient, compound_optimal_temp_*,
--      compound_cliff_onset_laps, compound_cliff_severity, compound_wear_s) and
--      compound_component_s; every expected_* column; cliff_onset_passed / laps_past_cliff /
--      cliff_candidate_flag; everything net of compound_component_s (driver_skill_residual_s,
--      pace_delta_s, total_explained_s, the v14 labels); ambient_temp_delta (track temperature
--      minus compound_optimal_temp_low); and int_field_pace_curve's base and the rubber /
--      ambient split fitted from it (the field pace subtracts expected_compound_pace_s).
--      Identity columns are allowed: compound_label, compound_code, compound_hardness_rank.
--   2. No model reads compound_cliff_params, dim_compounds_season or
--      int_compound_cliff_predicted directly.
--   3. Non-vacuous: every model has columns, and the training frame carries the eight
--      allowlisted features (ml/src/powerlaw.py FEATURES_DEG20 / FEATURES_BETA). The same
--      denylist is asserted on the Python side by ml/tests/test_powerlaw_export.py.

{%- set guarded_models = [
    'int_power_law_lap', 'int_stint_power_law_fit', 'int_cell_power_law_fit', 'fct_power_law_training'
] -%}
{%- set patterns = [
    '^compound_(grip|wear|optimal|cliff|component)',
    '^expected_',
    '^cliff_onset_passed$', '^laps_past_cliff$', '^cliff_candidate_flag$',
    '^driver_skill_residual', '^pace_delta_s$', '^total_explained_s$',
    '^ambient_temp_delta$',
    '^base_track_pace_s$', '^field_pace', '^rubber_component_s$', '^ambient_component_s$',
    '^track_unexplained_s$',
    '^next_.*jump', '^laps_until_cliff_class$'
] -%}
{%- set forbidden_parents = [
    'seed.off_the_pace.compound_cliff_params',
    'model.off_the_pace.dim_compounds_season',
    'model.off_the_pace.int_compound_cliff_predicted'
] -%}
{%- set allowlist = [
    'compound_hardness_rank', 'era_code', 'track_energy_index', 'circuit_abrasiveness_index',
    'track_temp_c', 'stint_start_fuel_kg', 'dirty_air_share', 'constructor_pace_s'
] -%}
{%- set relations = {
    'int_power_law_lap': ref('int_power_law_lap'),
    'int_stint_power_law_fit': ref('int_stint_power_law_fit'),
    'int_cell_power_law_fit': ref('int_cell_power_law_fit'),
    'fct_power_law_training': ref('fct_power_law_training')
} -%}
{%- set violations = [] -%}
{%- if execute -%}
    {%- for m in guarded_models -%}
        {%- set cols = adapter.get_columns_in_relation(relations[m]) | map(attribute='name') | map('lower') | list -%}
        {%- if cols | length == 0 -%}
            {%- do violations.append((m, '-', 'no columns: relation missing')) -%}
        {%- endif -%}
        {%- for c in cols -%}
            {%- for p in patterns -%}
                {%- if modules.re.search(p, c) -%}
                    {%- do violations.append((m, c, 'guarded column')) -%}
                {%- endif -%}
            {%- endfor -%}
        {%- endfor -%}
        {%- if m == 'fct_power_law_training' -%}
            {%- for f in allowlist if f not in cols -%}
                {%- do violations.append((m, f, 'allowlisted feature missing')) -%}
            {%- endfor -%}
        {%- endif -%}
    {%- endfor -%}
    {%- for node in graph.nodes.values() if node.resource_type == 'model' and node.name in guarded_models -%}
        {%- for parent in node.depends_on.nodes if parent in forbidden_parents -%}
            {%- do violations.append((node.name, parent, 'reads the compound seed directly')) -%}
        {%- endfor -%}
    {%- endfor -%}
{%- endif %}

{% if violations | length > 0 -%}
{%- for v in violations %}
SELECT '{{ v[0] }}' AS model_name, '{{ v[1] }}' AS column_or_parent, '{{ v[2] }}' AS failure
{% if not loop.last %}UNION ALL{% endif %}
{%- endfor %}
{%- else -%}
SELECT
    CAST(NULL AS VARCHAR) AS model_name,
    CAST(NULL AS VARCHAR) AS column_or_parent,
    CAST(NULL AS VARCHAR) AS failure
WHERE FALSE
{%- endif %}
