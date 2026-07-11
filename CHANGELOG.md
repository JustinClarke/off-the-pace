# Changelog

## [0.2.0](https://github.com/JustinClarke/off-the-pace/compare/v0.1.0...v0.2.0) (2026-07-11)


### Features

* add ingestion monitoring script for long-running backfills ([1e2ede1](https://github.com/JustinClarke/off-the-pace/commit/1e2ede13a3852c12f4ff4b360c58966b481cdb72))
* add Jolpica client for standings and pit stops (ingestion-v0.2 step 9) ([2ffe294](https://github.com/JustinClarke/off-the-pace/commit/2ffe2945e81a33c6f1b541d1ec35c28a8a6147c2))
* **app:** add app shell, state management, and UI primitives ([1c64506](https://github.com/JustinClarke/off-the-pace/commit/1c6450679a5a2474bae2a9e81fb9977dd3e28628))
* **app:** implement feature pages and client-side routing ([955502b](https://github.com/JustinClarke/off-the-pace/commit/955502badbe16886172464f379e6f56d287d730d))
* **app:** scaffold Vite React application and Tailwind config ([e1ae1ae](https://github.com/JustinClarke/off-the-pace/commit/e1ae1ae5cd8e9c8a24f5991949a3f62f18268025))
* **app:** wire DuckDB-WASM data layer and ONNX inference client ([a086d5f](https://github.com/JustinClarke/off-the-pace/commit/a086d5fce3500412582a3d9cdaddf8b9e5b6fe4f))
* enhance documentation structure ([6d90599](https://github.com/JustinClarke/off-the-pace/commit/6d90599db7dc3cfeb713bfe906d50aff0fa01b26))
* expand analytics suite with new performance features, model marts, and comprehensive documentation updates ([27e09fb](https://github.com/JustinClarke/off-the-pace/commit/27e09fbf28bf9d64cecdcf0219564d43c04d5bf5))
* implement infrastructure as code, enhance app observability, and expand documentation across the application, transformation, and ML pipelines. ([e454134](https://github.com/JustinClarke/off-the-pace/commit/e454134a58be4de5ee1ece4934d80d63cf5ef149))
* **ingestion:** add FastF1/OpenF1 api client and environment config ([7d542f7](https://github.com/JustinClarke/off-the-pace/commit/7d542f738bf4683e387574441d2806181ffe5743))
* **ingestion:** define JSON schemas and ingestion config ([d949e25](https://github.com/JustinClarke/off-the-pace/commit/d949e25a67fb66d44a929e41d08d9b6f06f4584b))
* **ingestion:** implement ingest CLI, replay simulator, and offline tests ([67041fd](https://github.com/JustinClarke/off-the-pace/commit/67041fda6f5b4f555a1b25a1813d7a2c68c74c48))
* **ml:** add Optuna hyperparameter tuning and trial inspection ([f62936b](https://github.com/JustinClarke/off-the-pace/commit/f62936b92ecb049fbb70c0cd9228c4ab6986b4d1))
* **ml:** add prediction, ONNX export with parity tests, and evaluation ([07cc5f6](https://github.com/JustinClarke/off-the-pace/commit/07cc5f690f8fe827df7df4122e56fdf96a45235b))
* **ml:** implement XGBoost quantile + classifier training ([bd6607f](https://github.com/JustinClarke/off-the-pace/commit/bd6607f5f84822fa22850dca65ca227a41fdca30))
* **ml:** setup environment and feature engineering pipeline ([e74ed22](https://github.com/JustinClarke/off-the-pace/commit/e74ed2244d70e185a836fce1c94e20dd84bd8848))
* redesign home page and hide unshipped features ([f954d2b](https://github.com/JustinClarke/off-the-pace/commit/f954d2b5bd34230b59b763ffd8dc89d4a90da220))
* **transform:** add prediction-feature marts and data tests ([13d972c](https://github.com/JustinClarke/off-the-pace/commit/13d972c751b876506ff738a0b44d423449294514))
* **transform:** add static seeds and source definitions ([a19e563](https://github.com/JustinClarke/off-the-pace/commit/a19e56351848f3f64dddec4fa9532a06600dbf75))
* **transform:** build seven-term lap-residual and stint marts ([122498b](https://github.com/JustinClarke/off-the-pace/commit/122498b06a5533b2364f879244d9a1010dfa32a8))
* **transform:** build staging models for laps, weather, pits, telemetry ([e643ff4](https://github.com/JustinClarke/off-the-pace/commit/e643ff4625ae2be9a53caff830cbddf568500d9c))
* **transform:** implement intermediate transformations and bayesian macros ([632725e](https://github.com/JustinClarke/off-the-pace/commit/632725e23abefb429625221d48d5b1ae36426f90))
* upgrade to v4 tyre degradation models with updated ONNX inference and CI scanner integration ([b7c91db](https://github.com/JustinClarke/off-the-pace/commit/b7c91db3582e713d9596f7164fde285ffbdc9951))


### Refactors

* resolve join ambiguities, fix workspace build configuration, and add app roadmap documentation ([b8d6bc7](https://github.com/JustinClarke/off-the-pace/commit/b8d6bc7c98b7091015f8ba0ef61130212b01ce81))


### Documentation

* add narrative content and generated reference pages ([a4f4272](https://github.com/JustinClarke/off-the-pace/commit/a4f4272b2b70e5564c8ff2b0caa1ecbd3cd1e5a1))
* add reference-generation and app-data export scripts ([abfdddd](https://github.com/JustinClarke/off-the-pace/commit/abfdddd9abdafd279b8418c793ad667b7494d024))
* add repository tour, top-level README, and Makefile entry points ([5fc55d8](https://github.com/JustinClarke/off-the-pace/commit/5fc55d81e7088a7e5070f49e835960c565467d5c))
* initialize Docusaurus site and theme ([19c59f3](https://github.com/JustinClarke/off-the-pace/commit/19c59f3edd1a1c17b4f08fa86512ccd0ccf011bd))
* project documentation structure and expand public data assets while refining transformation macros and validation scripts ([3a3b34b](https://github.com/JustinClarke/off-the-pace/commit/3a3b34b78dba6671cd3571cad11ea951b98a25e3))


### Build & CI

* add GitHub Actions workflows for automated testing and deployment ([2418a18](https://github.com/JustinClarke/off-the-pace/commit/2418a18c5960330572dad6e8b785e05737a5cfac))
