{% macro driver_isolation_identity_terms() %}
  {#-
  The cumulative-identity split of tier 3, aggregated over any group of
  fct_driver_isolation_pair_lap rows (WI-16a). Use inside a GROUP BY over that model.

  Per pair row, relative = pace_gap + car_advantage + traffic_advantage + age_pricing
  (age_pricing since WI-16b, 2026-09-30: the seed's tyre-age pricing minus the fitted
  curve's, because relative is age-adjusted by the curve and pace_gap by the seed). The aggregate
  keeps the identity exact by expressing every term as a CONTRIBUTION: its sum over
  the group's closed rows (both cars have a car term, so pace_gap is non-NULL) divided
  by identity_n_pair_laps. Then

    identity_relative_pace_gain_s = identity_pace_gap_gain_s
                                  + identity_car_advantage_gain_s
                                  + identity_traffic_advantage_gain_s
                                  + identity_age_pricing_gain_s

  holds to float precision (T42 checks it). A contribution over zero rows is 0, not a
  measurement. All columns are NULL when the group has no closed row. Seconds per lap,
  positive = in the focal driver's favour.

  Emits: n_pair_laps, identity_n_pair_laps,
  identity_relative_pace_gain_s, identity_pace_gap_gain_s,
  identity_car_advantage_gain_s,
  identity_traffic_advantage_gain_s, identity_age_pricing_gain_s.

  Usage:
    SELECT stint_id, {{ driver_isolation_identity_terms() }}
    FROM {{ ref('fct_driver_isolation_pair_lap') }}
    GROUP BY stint_id
  -#}
  {%- set n = 'COUNT(pace_gap_gain_s)' %}
    COUNT(*) AS n_pair_laps,
    {{ n }} AS identity_n_pair_laps,
    CASE WHEN {{ n }} > 0 THEN
        SUM(CASE WHEN pace_gap_gain_s IS NOT NULL THEN relative_pace_gain_s END) / {{ n }}
    END AS identity_relative_pace_gain_s,
    CASE WHEN {{ n }} > 0 THEN
        COALESCE(SUM(pace_gap_gain_s), 0.0) / {{ n }}
    END AS identity_pace_gap_gain_s,
    CASE WHEN {{ n }} > 0 THEN
        SUM(CASE WHEN pace_gap_gain_s IS NOT NULL THEN car_advantage_gain_s END) / {{ n }}
    END AS identity_car_advantage_gain_s,
    CASE WHEN {{ n }} > 0 THEN
        SUM(CASE WHEN pace_gap_gain_s IS NOT NULL THEN traffic_advantage_gain_s END) / {{ n }}
    END AS identity_traffic_advantage_gain_s,
    CASE WHEN {{ n }} > 0 THEN
        SUM(CASE WHEN pace_gap_gain_s IS NOT NULL THEN age_pricing_gain_s END) / {{ n }}
    END AS identity_age_pricing_gain_s
{%- endmacro %}
