-- Deterministic tripwire on the compound_cliff_params seed: fitted severities
-- must stay <= 1.6 s/lap (physical plausibility is ~0.1-0.5; unbounded, the
-- ghost cliff term can dwarf real car pace) and the cross-season fallback must
-- never fire from fewer than 8 real stints (fewer invents parameters from too
-- little data). Nothing else in the suite anchors this seed's plausibility, so
-- a bad regenerate of the seed could otherwise ship green even past the
-- byte-drift gate.
--
-- fit_compound_cliff.py now winsorises severity to 1.5 and gates the fallback on
-- >= 8 cross-season STINTS; 1.6 and the n_stints check below give a hair of margin.

SELECT
    circuit_key,
    compound_code,
    season,
    compound_cliff_severity,
    fit_source,
    n_stints
FROM {{ ref('compound_cliff_params') }}
WHERE compound_cliff_severity > 1.6
   OR (fit_source = 'cross_season_fallback' AND n_stints < 8)
