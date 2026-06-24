{% macro circuit_id_from_name(name_col) %}
  {#-
  Derive a stable physical-circuit identifier from a circuit's display name.

  The seed key (circuit_key) is really a grand-prix/event slug, so a single physical
  venue can carry several keys: renamed events (mexican_grand_prix → mexico_city_grand_prix),
  and double-headers at one track (british_grand_prix + 70th_anniversary_grand_prix at
  Silverstone; austrian_grand_prix + styrian_grand_prix at the Red Bull Ring). Slugifying
  the circuit_name collapses those into one circuit_id so "equal-car track record at a
  circuit" pools all races run at the same venue.
  -#}
    trim(both '_' from regexp_replace(lower({{ name_col }}), '[^a-z0-9]+', '_', 'g'))
{% endmacro %}
