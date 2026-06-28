# Changelog

## [0.2.0](https://github.com/JustinClarke/off-the-pace/compare/v0.1.0...v0.2.0) (2026-06-28)


### Features

* add ingestion monitoring script for long-running backfills ([5e3e9bf](https://github.com/JustinClarke/off-the-pace/commit/5e3e9bfa06acae34ce7353239eb5f151bdb71c30))
* add Jolpica client for standings and pit stops (ingestion-v0.2 step 9) ([640eee3](https://github.com/JustinClarke/off-the-pace/commit/640eee3f0c8d90751a0d85ecaab496caed1a3ad4))
* **app:** add app shell, state management, and UI primitives ([386265c](https://github.com/JustinClarke/off-the-pace/commit/386265cce9b9d758932d2bdefcb0b1ca722a66b2))
* **app:** implement feature pages and client-side routing ([d034da0](https://github.com/JustinClarke/off-the-pace/commit/d034da01f684201d26ebc24e3ee6871ba0362502))
* **app:** scaffold Vite React application and Tailwind config ([faf23c3](https://github.com/JustinClarke/off-the-pace/commit/faf23c34310fe4b1126a9dcc39575c62128f12fb))
* **app:** wire DuckDB-WASM data layer and ONNX inference client ([ba7a0b0](https://github.com/JustinClarke/off-the-pace/commit/ba7a0b05e8e1ebe2550096a0e3fe2518dea72830))
* enhance documentation structure ([07981a4](https://github.com/JustinClarke/off-the-pace/commit/07981a47c89fd3d9f08f74dddbb38ff4bd5634af))
* expand analytics suite with new performance features, model marts, and comprehensive documentation updates ([60bdf69](https://github.com/JustinClarke/off-the-pace/commit/60bdf69b570faaac5f12fb979ca526b33f20bfb4))
* implement infrastructure as code, enhance app observability, and expand documentation across the application, transformation, and ML pipelines. ([48c626e](https://github.com/JustinClarke/off-the-pace/commit/48c626e3b1cbdd5a988031917df3927752110a63))
* **ingestion:** add FastF1/OpenF1 api client and environment config ([1c57c86](https://github.com/JustinClarke/off-the-pace/commit/1c57c8665ae3d3d967cb76d95895896627c951b6))
* **ingestion:** define JSON schemas and ingestion config ([4a543cf](https://github.com/JustinClarke/off-the-pace/commit/4a543cf79d9eb25b92a5af18fefe06afc2d33d6d))
* **ingestion:** implement ingest CLI, replay simulator, and offline tests ([33469d4](https://github.com/JustinClarke/off-the-pace/commit/33469d4d3b63aac254cf56d0cbab801411895b98))
* **ml:** add Optuna hyperparameter tuning and trial inspection ([26d1006](https://github.com/JustinClarke/off-the-pace/commit/26d1006b7d347187ead3220bcf257f4f3f083166))
* **ml:** add prediction, ONNX export with parity tests, and evaluation ([cf3f67f](https://github.com/JustinClarke/off-the-pace/commit/cf3f67fe4bf921fdf5d0cbe22b864e647dbb5435))
* **ml:** implement XGBoost quantile + classifier training ([555fbf2](https://github.com/JustinClarke/off-the-pace/commit/555fbf2e4f9cefb0e5866b8e94cc6e94bcedb0e8))
* **ml:** setup environment and feature engineering pipeline ([1114eee](https://github.com/JustinClarke/off-the-pace/commit/1114eee3c3c9fcf8b433e87f222666ac68342601))
* redesign home page and hide unshipped features ([b609f77](https://github.com/JustinClarke/off-the-pace/commit/b609f77880049151eb8fc574f53326d9799aeee1))
* **transform:** add prediction-feature marts and data tests ([2676c51](https://github.com/JustinClarke/off-the-pace/commit/2676c51ccc8f9c1f806a30909fc36ed5b67ac645))
* **transform:** add static seeds and source definitions ([305460c](https://github.com/JustinClarke/off-the-pace/commit/305460ceedc5827a3daa5fa274f02e78bc483102))
* **transform:** build seven-term lap-residual and stint marts ([7553add](https://github.com/JustinClarke/off-the-pace/commit/7553add1d56990fbe5cb5e50b32fffa2c84ee21d))
* **transform:** build staging models for laps, weather, pits, telemetry ([a5061b7](https://github.com/JustinClarke/off-the-pace/commit/a5061b72bde4b7254587b1ebe72c972e2b4cb6eb))
* **transform:** implement intermediate transformations and bayesian macros ([28ec9eb](https://github.com/JustinClarke/off-the-pace/commit/28ec9eb607fd939d6af71f3d186b114dd4ae1cf7))
* upgrade to v4 tyre degradation models with updated ONNX inference and CI scanner integration ([8020e5a](https://github.com/JustinClarke/off-the-pace/commit/8020e5a68136c71f36d8e962d8f37a1d0bd80860))


### Refactors

* resolve join ambiguities, fix workspace build configuration, and add app roadmap documentation ([3f249ec](https://github.com/JustinClarke/off-the-pace/commit/3f249ece194d1aa6a73da748818eab141f26b2b9))


### Documentation

* add narrative content and generated reference pages ([ff4a191](https://github.com/JustinClarke/off-the-pace/commit/ff4a1910be31455bab511cf54f2187cc72bb8c73))
* add reference-generation and app-data export scripts ([4c537e3](https://github.com/JustinClarke/off-the-pace/commit/4c537e31b757cb6a66a7ca2fb29dcbdc1b15d1d8))
* add repository tour, top-level README, and Makefile entry points ([b7cd945](https://github.com/JustinClarke/off-the-pace/commit/b7cd945a0ca70cf64f91b62a1065de37c487ddff))
* initialize Docusaurus site and theme ([f379746](https://github.com/JustinClarke/off-the-pace/commit/f379746071740051572eb773292ef5c4db43f547))
* project documentation structure and expand public data assets while refining transformation macros and validation scripts ([f9ba40e](https://github.com/JustinClarke/off-the-pace/commit/f9ba40e245b3cbebef49eccaea663ff1d0d1088e))


### Build & CI

* add GitHub Actions workflows for automated testing and deployment ([674365e](https://github.com/JustinClarke/off-the-pace/commit/674365efd5f88f904390f4bcd8793d1a9bab0237))
