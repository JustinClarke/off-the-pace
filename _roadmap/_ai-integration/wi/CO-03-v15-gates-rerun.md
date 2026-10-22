# CO-03 — v15 retrain on the final label, owed gates, export

**Status:** CLOSED 2026-10-22, superseded by `CO-18`. v15 was trained on the CO-02/CO-04 label, which CO-09 and CO-15 (`CD9`) now move again. The text below is the record. The retrain and gates move to CO-18, the `training_weight_f9` clean-up to CO-17, the D9/D14 re-measures to CO-18, and the promotion question to `CD10`.

**Group:** 1 data settled · **Depends on:** `CO-02`, `CO-04` · **Blocker:** dependencies only. `CD1` ruled A (2026-10-15): F9 is decided not wired.

**Sources:** `ml/models/manifest.json`, `ml/src/schema.py`, `ml/artefacts/15a_traffic_families_arms.log`, `ml/artefacts/08e_thermal_family_arms_v15.log`, `transform/models/intermediate/int_lap_anomaly_flags.sql`.

**Audit findings:** 3, 4.

---

## What exists today (checked 2026-10-15)

- The fixes log resolved W59 as "v15 gates passed" on 2026-09-30. The gate logs are dated 2026-09-29, before the 2026-10-03 seed re-estimate, and CO-02 and CO-04 move the label again.
- All five `ml/models/*_v15.bst` are byte-identical to `*_v15uni.bst` (W58's weighting comparison at v14 settings). There is no `*_v15.onnx`. Both manifests and `MODEL_VERSION_DEFAULT` (`ml/src/schema.py:487`) say v14. The live CDN also serves v14.
- **F9 (finding 4).** WI-02b is LANDED, but `training_weight_f9` exists only at `int_lap_anomaly_flags.sql:293`. `fct_cliff_prediction_features.sql:984` still drops every 'mistake' row and nothing in `ml/src` reads the weight. It also gives 1,234 event_driven rows a weight above 0, so it is not a drop-in.

## Method

1. `CD1` = A: keep dropping 'mistake' laps (no wiring). `training_weight_f9` (`int_lap_anomaly_flags.sql:293`) is unused (checked 2026-10-15: no reader in transform, ml, app, scripts or docs). Delete it in this rebuild if the dbt build stays green, or leave it with a note. Do not wire it.
2. Record one label version bump covering CO-02 and CO-04.
3. Retrain v15 on that label. Settled, not reopened here: uniform sample weights (W58), the stint-life gauge is the realised stint ending (D5), training is 2018–2025 and 2026 is the blind test.
4. Run W59's owed gates on a warehouse built from the working tree: WI-15a steps 1–4, 6, 7; WI-15b's 08e thermal ablation; gate step 5 (`ml.src.features --check`) only after confirming WI-07 is LANDED on the fixes board.
5. Export ONNX, update the manifest, run the parity check.

6. After v15 lands (`CD3`): re-measure D9 (pit-strategy cost curve reading ML predictions) and re-check the 01c attainable-block ceiling for D14 on v15, and report both to the user. They stay OPEN on the improvements board until then.

## Acceptance

- Every gate log is dated after CO-02 and CO-04 landed.
- `*_v15.bst` differs from `*_v15uni.bst`, and the difference is recorded.
- Manifest version and ONNX file names agree; parity passes.

## Output

One table: each gate, pass/fail, v15 against v14 per family.

## Definition of done

Either every gate passes, or the failing gate is on the board and "ready to ship" is withdrawn. Promoting v15 (default bump, CDN publish) is the user's call. Do not commit.
