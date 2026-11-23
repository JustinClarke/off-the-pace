{% macro hazard_circuit_key(race_year, race_slug) %}
  {#-
  Venue key for int_sc_hazard_history: which races pool into one circuit's
  safety-car history. Shared by the model and assert_sc_hazard_no_forward_leakage
  so the two cannot drift.

  The race slug is the key, with two exceptions that split / merge by PHYSICAL
  circuit:
    * 2026 spanish_grand_prix is Madrid (Madring), a new venue -> madring_grand_prix.
    * 2026 barcelona_grand_prix is Barcelona-Catalunya, which hosted the
      2018-2025 spanish_grand_prix -> spanish_grand_prix (inherits that history).
  `spanish_grand_prix` therefore remains the legacy Barcelona/Catalunya key.
  -#}
    CASE
        WHEN {{ race_slug }} = 'barcelona_grand_prix' THEN 'spanish_grand_prix'
        WHEN {{ race_slug }} = 'spanish_grand_prix' AND {{ race_year }} >= 2026
            THEN 'madring_grand_prix'
        ELSE {{ race_slug }}
    END
{% endmacro %}
