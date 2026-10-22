# CO-18 — Retrain on the new label version, owed gates, export

**Group:** 1 data settled · **Depends on:** `CO-17` · **Blocker:** none. Promotion is `CD10`.

**Sources:** `ml/src/schema.py`, `ml/models/manifest.json`, `ml/src/evaluate.py`, `ml/README.md` (label-version record), `ml/artefacts/`.

Replaces CO-03 (closed 2026-10-22). v15 was trained on the CO-02/CO-04 label. CO-09 and CO-15 move that label again, as one new label version, so v15's gates are not the launch model's.

---

## Method

1. Retrain the five models with the v15 configuration, unchanged, on CO-17's warehouse. Settled, not reopened here: uniform sample weights (W58), 2018–2025 training window, 'mistake' laps dropped (CD1).
2. Give it its own model version (v16 unless the label-version record says otherwise). Do not reuse the v15 name or artefacts.
3. Run every gate CO-03 ran: WI-15a, the 08e thermal ablation, `ml.src.features --check`, seed gate, beats-baseline for every family (stint life included), ONNX export and parity.
4. Write the manifest for the new version. Leave `MODEL_VERSION_DEFAULT` and the CDN on v14.
5. Re-measure D9 and re-check D14 on this model (`CD3`, watch W7). Report both.

## Acceptance

- Every gate log is dated after CO-17.
- One table: each gate, pass or fail, new version against v14 and v15 per family.
- Manifest version and ONNX file names agree; parity passes.

## Definition of done

Gate table recorded in the log and put to the owner with CO-14's result for `CD10`. Nothing promoted, published or committed.
