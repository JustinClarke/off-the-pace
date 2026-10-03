{% macro driver_isolation_identity_terms() %}
  {#-
  The cumulative-identity split of tier 3, aggregated over any group of
  fct_driver_isolation_pair_lap rows (WI-16a). Use inside a GROUP BY over that model.

  Per pair row, relative = pace_gap + car_advantage + traffic_advantage + tyre-age bias,
  where relative is the raw gap (W63 design 2, 2026-10-03: no tyre-age adjustment, peers
  matched within var('isolation_peer_age_tolerance') laps of tyre age instead) and the
  bias is the compound seed's pricing of that age gap, (C(peer) - C(driver)), which
  pace_gap carries and the raw gap does not. It is 0 between cars on the same tyre age
  and is not published. Every term is a CONTRIBUTION: its sum over the group's closed
  rows (both cars have a car term, so pace_gap is non-NULL) divided by
  identity_n_pair_laps. Then

    identity_relative_pace_gain_s = identity_pace_gap_gain_s
                                  + identity_car_advantage_gain_s
                                  + identity_traffic_advantage_gain_s
                                  + (the group's mean tyre-age bias)

  The three published contributions therefore close identity_relative_pace_gain_s only
  up to that bias. T42 asserts the three-term identity exactly on same-age pair rows,
  where the bias is 0. A contribution over zero rows is 0, not a measurement. All columns
  are NULL when the group has no closed row. Seconds per lap, positive = in the focal
  driver's favour.

  Emits: n_pair_laps, identity_n_pair_laps,
  identity_relative_pace_gain_s, identity_pace_gap_gain_s,
  identity_car_advantage_gain_s, identity_traffic_advantage_gain_s.

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
    END AS identity_traffic_advantage_gain_s
{%- endmacro %}
