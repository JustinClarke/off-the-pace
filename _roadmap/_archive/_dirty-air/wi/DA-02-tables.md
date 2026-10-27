# DA-02 - Tables and descriptives

**Build.** Two dbt models: a sample-level proximity table (about 68M rows on dev) and a micro-sector table (10-20 micro-sectors per lap, about 1.6-3.3M rows). Per design note section 1: each sample gets a gap, a time step capped at 1 s, and a validity reason code. Unknown car ahead gives a NULL cost, never 0 (the CO-04 rule). A lap with more than 20% unknown gets a NULL lap cost.

**Tests.** Total order on samples (byte-stability needs ROUND and total ordering at this size), pit-lane exclusion, agreement with blue-flag data, and the lap-total identity.

**Descriptives.** Loss-versus-gap curve by gap band. Expected: loss rises as the gap shrinks and is flat above 3 s.

**Gate to continue.** Build runs in minutes. Loss rises as the gap shrinks.

**Stop if.** No gap gradient.

**Owner decision at this gate.** Micro-sector grain, and seconds or metres as the unit.
