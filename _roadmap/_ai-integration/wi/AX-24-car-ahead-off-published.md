# AX-24 — No published number depends on DriverAhead or DistanceToDriverAhead (D2)

**Decision:** no published figure may read FastF1's `DriverAhead` or `DistanceToDriverAhead`. `int_lap_proximity` stays, because it derives the car ahead from its own crossing times. `int_lap_air_state` keeps reading the field only as an internal filter for held outputs, until it is rebuilt on proximity.
**Why:** Probe 4 found the field is track order limited to cars on the same lap count, not physical proximity, and it mismatches on lapped and overlapping cars.
**Record:** experiments/13-app-reliability-decisions/decisions.md (in the f1-chat repo: /Users/justin/github/_misc/_chat/f1-chat/experiments/13-app-reliability-decisions/decisions.md)
**Status:** decided. Needs a reader list check (every reader is listed in the record) before any change.
**Done when:** every reader of the field is either removed from published outputs or marked internal, and a test fails if a published mart reads the field.
