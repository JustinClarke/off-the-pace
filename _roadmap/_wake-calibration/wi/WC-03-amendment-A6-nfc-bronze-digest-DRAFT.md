# WC-03 pre-registration, amendment A6 (DRAFT): NFC path names in the G3 bronze digest

**Status: DRAFT, proposed. Owner ruling required.** Written by an agent on 2026-10-29; not decided, not signed, not committed, not hashed. It amends how `run_wc03.bronze_digest` (G3 check 4) writes path names. The pre-registration, A1-A5, RUN-PACKAGE.md and the build log are not edited. The registered values are unchanged.

---

## The failure

Run `WC-04-2026-10-29` stopped at G3 check 4:

    G3.4 FAIL (1214 files, aaaf711dcc0781819ec7103c6f36184d1ba63bdeb8b1828da0e2bfb6e9c45a94)

Registered: `G3_BRONZE_FILES = 1_214`, `G3_BRONZE_SHA256 = "aed1c27da1cc00fb80eea470bb0c5c4879ee09556c81ff35bc17ad4aff1690b4"`. The file count matched; the digest did not. The evidence of that attempt is kept as written under `_evidence/WC-04-2026-10-29/`.

## The cause

Five laps files, `race=são_paulo_grand_prix` for seasons 2021-2025, are returned by Python `glob.glob` with the name in NFD form (`a` + combining tilde U+0303). The registered digest was computed with the same names in NFC form (precomposed `ã`, U+00E3). The digest hashes the path text, so the five lines differ in bytes (and may sort differently), and the whole digest changes. No file content changed. Verified: 5 of the 1,214 paths from `glob` are not NFC.

## The change

One line in `transform/tasks/wake_calibration/run_wc03.py`, `bronze_digest` (plus `import unicodedata` and a docstring note): each relative path is NFC-normalised before the bytewise sort and before the line is written.

    lines = [(unicodedata.normalize("NFC", os.path.relpath(p, bronze)), sha256_file(Path(p))) for p in files]

## Registered constant unchanged

`G3_BRONZE_FILES` and `G3_BRONZE_SHA256` are not changed. With the change, `bronze_digest()` on `data/bronze` returns `1214 aed1c27da1cc00fb80eea470bb0c5c4879ee09556c81ff35bc17ad4aff1690b4`, the registered values.

## Test added

`tests/test_run_wc03.py::test_bronze_digest_hashes_an_nfd_name_as_its_nfc_form`: a synthetic bronze folder with one laps file under `race=são_paulo_grand_prix`, written once with an NFD name and once with an NFC name, must give the same digest, equal to a digest built by hand from the NFC path. A third case forces `glob` to return NFD paths, so the test holds whatever the file system stores. The existing shell-recipe test is unchanged.

## Ruling required

The owner decides whether A6 is adopted, and whether the next start of the run is allowed under §0 given that the failed attempt stopped at G3 before anything was fitted.
