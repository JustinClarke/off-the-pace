{#
  compound_cliff_wear -- THE single definition of the fitted compound wear curve's
  age-dependent terms. Work item 08m; the plateau was rewritten by CO-02 (2026-10-15).

  Why this is a macro and not inline SQL, per macros/README.md's own rule ("a
  definition lives once here instead of being copy-pasted, and silently diverging,
  across models"): this exact expression had been copy-pasted into SIX sites, and it
  had silently diverged in the way that matters -- every one of them consumed
  compound_cliff_severity as a per-lap RATE when survival.py fits it as a level
  SHIFT. 08l measured that single term at 60.4% of the seed's contribution to the ML
  target. Fixing five sites and missing one would have re-created the split lineage,
  so the arithmetic now lives here and the sites call it.

  THE UNITS, which are the whole point:
  survival.py::estimate_cliff_severity fits, per stint, one line (pace ~ age) through
  the pre-cliff laps and one through the post-cliff laps, and takes their vertical
  gap at onset + cliff_severity_span() (2.5 laps). Both lines carry the stint's wear
  slope and are read at the same age, so the slope cancels: compound_cliff_severity
  is the cliff STEP in SECONDS with ordinary wear already excluded. It is not s/lap
  and not s/lap^2. A negative estimate is stored as 0.0 in the seed (no cliff).

  So the plateau IS the fitted severity, added on top of wear_gradient * age as is.

  Until CO-02 this macro still corrected severity as if it were the older window-mean
  difference, post.mean() - pre.mean(), whose window centroids sit 5.5 laps apart and
  so carry 5.5 laps of wear: it subtracted 5.5 * wear_gradient (floored at zero) and
  scaled the rest by 5.5 / 2.5 = 2.2. The estimator had already moved to the
  regression gap, so wear came out twice (T1), and the 2.2 scaled a step up past its
  own height. On a stint with a 1.0 s step and 0.05 s/lap of wear the old plateau
  was 2.2 * (1.0 - 0.275) = 1.60 s; it is now 1.00 s.

  THE RAMP. The plateau is reached by a linear ramp over cliff_severity_span() laps
  past the cell's onset, then held flat. The onset is a population median (the
  Kaplan-Meier median of the cell's stints), and each stint's own cliff lands either
  side of it, so the ramp spreads the step over that scatter and keeps the curve
  continuous at onset. The span is the age offset at which the fitter measures the
  step (owner decision E, CO-02): ONE constant, var cliff_ramp_span_laps = 2.5 in
  dbt_project.yml, read by this macro and by survival.py. So the curve reaches the
  full fitted step at onset + 2.5, where it was measured. Until CO-02 the ramp ran
  over 5.5 laps (the old window-mean centroid spacing), so between onset + 2.5 and
  onset + 5.5 the curve charged less than the step the fitter had measured there.
  It is a modelling choice, not a fitted quantity. Past onset + 5 the fitter measured
  nothing, so the curve holds the plateau rather than extrapolating. That is a
  documented limitation of the seed, not a claim about tyres.

  The 0.002*age^2 quadratic that used to sit alongside these terms is GONE, at every
  site. It was a literal constant, identical across all 438 circuit x compound x
  season cells, never fitted against anything, and worth 1.8 s at age 30 -- and it is
  already absorbed by the linear term, since survival.py::_fit_wear_slope_with_wind
  fits pace ~ [1, age, wind] with no quadratic in its design matrix.
#}

{# Laps past onset over which the plateau is ramped in. See THE RAMP above. No
   default on purpose: dbt_project.yml's var is the one definition, shared with the
   fitter (survival.py::CLIFF_RAMP_SPAN_LAPS reads the same var). #}
{% macro cliff_severity_span() -%}
{{ var('cliff_ramp_span_laps') }}
{%- endmacro %}


{# The saturated post-onset level, in seconds: the fitted severity itself, floored
   at zero. wear_gradient is NOT read (the severity has no wear in it, see THE
   UNITS); the argument stays so that every call site keeps one signature. #}
{% macro cliff_plateau_s(severity, wear_gradient) -%}
GREATEST(COALESCE({{ severity }}, 0.0), 0.0)
{%- endmacro %}


{# Fraction of the plateau delivered at this depth past onset: 0 -> 1 over span.
   NULL in, NULL out: DuckDB's LEAST skips a NULL argument, so a bare
   LEAST(NULL, span) would read an unknown depth as a fully developed cliff. #}
{% macro cliff_ramp_frac(laps_past_cliff) -%}
(CASE WHEN {{ laps_past_cliff }} IS NULL THEN NULL
    ELSE LEAST({{ laps_past_cliff }}, {{ cliff_severity_span() }}) END
    / {{ cliff_severity_span() }})
{%- endmacro %}


{# The cliff's whole contribution to per-lap pace loss, in seconds. #}
{% macro cliff_severity_term(severity, wear_gradient, laps_past_cliff) -%}
{{ cliff_plateau_s(severity, wear_gradient) }} * {{ cliff_ramp_frac(laps_past_cliff) }}
{%- endmacro %}


{# The full age-dependent wear term, bounded. grip_peak and the temperature
   offset are per-lap constants and are deliberately NOT included: they do not
   run away with age, and the bound is defined on the age-dependent part only.

   NULL-SAFE (F39). DuckDB's LEAST skips NULL arguments, so with a NULL tyre age
   the bare LEAST(NULL, cap) returned the cap itself -- a valid-looking 10 s of
   wear on every lap whose age is unknown (stints quarantined by stg_lap_tyre_qa,
   and a few laps bronze never aged). An unknown age is an unknown wear term:
   the guard returns NULL, the same pattern int_lap_thermal_proxy uses for
   GREATEST. #}
{% macro compound_cliff_wear_s(wear_gradient, severity, age, laps_past_cliff) -%}
CASE
    WHEN {{ age }} IS NULL OR {{ laps_past_cliff }} IS NULL THEN NULL
    ELSE LEAST(
        COALESCE({{ wear_gradient }}, 0.0) * {{ age }}
        + {{ cliff_severity_term(severity, wear_gradient, laps_past_cliff) }},
        {{ var('compound_wear_max_s_per_lap', 10.0) }}
    )
END
{%- endmacro %}


{# Equivalent per-lap slope of the cliff term while the ramp is climbing (s/lap^2).
   This is what a consumer that needs a RATE should use -- never bare severity. #}
{% macro cliff_ramp_slope_s_per_lap(severity, wear_gradient) -%}
({{ cliff_plateau_s(severity, wear_gradient) }} / {{ cliff_severity_span() }})
{%- endmacro %}
