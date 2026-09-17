{#
  compound_cliff_wear -- THE single definition of the fitted compound wear curve's
  age-dependent terms. Work item 08m.

  Why this is a macro and not inline SQL, per macros/README.md's own rule ("a
  definition lives once here instead of being copy-pasted, and silently diverging,
  across models"): this exact expression had been copy-pasted into SIX sites, and it
  had silently diverged in the way that matters -- every one of them consumed
  compound_cliff_severity as a per-lap RATE when survival.py fits it as a level
  SHIFT. 08l measured that single term at 60.4% of the seed's contribution to the ML
  target. Fixing five sites and missing one would have re-created the split lineage,
  so the arithmetic now lives here and the sites call it.

  THE UNITS, which are the whole point:
  survival.py::estimate_cliff_severity returns post.mean() - pre.mean() over
     pre  = age in [onset-5, onset-1]   5 laps, centroid onset - 3.0
     post = age in [onset,   onset+5]   6 laps, centroid onset + 2.5
  so compound_cliff_severity is the TOTAL pace change in SECONDS across the onset,
  between two window centroids 5.5 laps apart. It is not s/lap and not s/lap^2.

  TWO corrections are applied to it here:

  (a) DE-DOUBLE-COUNT. The curve already carries wear_gradient*age, which rises by
      span*wear_gradient across the same centroid separation the severity windows
      straddle -- so ~48.7% of the measured severity (mean 0.4385 s of 0.8996 s
      across the 438-row seed) is ordinary wear the formula charges elsewhere. The
      cliff-attributable EXCESS is the remainder, floored at zero. It floors on 41 of
      438 cells (9.4%), where the measured "cliff" is no worse than linear wear.

  (b) MOMENT-MATCH, then SATURATE. The excess is delivered as a linear ramp over
      `span` laps past onset and held flat thereafter. The gain = span/post_centroid
      makes the corrected curve reproduce the fitter's own measurement exactly: the
      predicted pace change from onset-3.0 to onset+2.5 is
          span*wear_gradient + plateau*(post_centroid/span) == severity.
      Past onset+span the fitter measured NOTHING, so the curve holds its last
      measured level rather than extrapolating. That is a documented limitation of
      the seed, not a claim about tyres.

  A two-window mean difference cannot distinguish a step from a ramp inside its own
  window, so either is within the estimator's resolution; the ramp is used because it
  is continuous at onset and because it moment-matches without an occupancy
  correction for the age == onset lap, where laps_past_cliff = 0.

  The 0.002*age^2 quadratic that used to sit alongside these terms is GONE, at every
  site. It was a literal constant, identical across all 438 circuit x compound x
  season cells, never fitted against anything, and worth 1.8 s at age 30 -- and it is
  already absorbed by the linear term, since survival.py::_fit_wear_slope_with_wind
  fits pace ~ [1, age, wind] with no quadratic in its design matrix.
#}

{% macro cliff_severity_span() -%}
{{ var('cliff_severity_pre_centroid_laps', 3.0) + var('cliff_severity_post_centroid_laps', 2.5) }}
{%- endmacro %}

{% macro cliff_severity_gain() -%}
{{ (var('cliff_severity_pre_centroid_laps', 3.0) + var('cliff_severity_post_centroid_laps', 2.5)) / var('cliff_severity_post_centroid_laps', 2.5) }}
{%- endmacro %}


{# The saturated post-onset level, in seconds. Reached at onset + span. #}
{% macro cliff_plateau_s(severity, wear_gradient) -%}
({{ cliff_severity_gain() }} * GREATEST(
    COALESCE({{ severity }}, 0.0)
    - {{ cliff_severity_span() }} * COALESCE({{ wear_gradient }}, 0.0),
    0.0
))
{%- endmacro %}


{# Fraction of the plateau delivered at this depth past onset: 0 -> 1 over span. #}
{% macro cliff_ramp_frac(laps_past_cliff) -%}
(LEAST({{ laps_past_cliff }}, {{ cliff_severity_span() }}) / {{ cliff_severity_span() }})
{%- endmacro %}


{# The cliff's whole contribution to per-lap pace loss, in seconds. #}
{% macro cliff_severity_term(severity, wear_gradient, laps_past_cliff) -%}
{{ cliff_plateau_s(severity, wear_gradient) }} * {{ cliff_ramp_frac(laps_past_cliff) }}
{%- endmacro %}


{# The full age-dependent wear term, bounded. grip_peak and the temperature
   offset are per-lap constants and are deliberately NOT included: they do not
   run away with age, and the bound is defined on the age-dependent part only. #}
{% macro compound_cliff_wear_s(wear_gradient, severity, age, laps_past_cliff) -%}
LEAST(
    COALESCE({{ wear_gradient }}, 0.0) * {{ age }}
    + {{ cliff_severity_term(severity, wear_gradient, laps_past_cliff) }},
    {{ var('compound_wear_max_s_per_lap', 10.0) }}
)
{%- endmacro %}


{# Equivalent per-lap slope of the cliff term while the ramp is climbing (s/lap^2).
   This is what a consumer that needs a RATE should use -- never bare severity. #}
{% macro cliff_ramp_slope_s_per_lap(severity, wear_gradient) -%}
({{ cliff_plateau_s(severity, wear_gradient) }} / {{ cliff_severity_span() }})
{%- endmacro %}
