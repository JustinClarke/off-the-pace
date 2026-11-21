# ════════════════════════════════════════════════════════════════════════════════
#  Off The Pace project Makefile
#
#  Targets organized by workflow stage in chronological order:
#
#     1. Setup       	- environment + dependencies (one-time)
#     2. Ingest      	- pull raw F1 data into Bronze
#     3. Coefficients 	- fit physics-model seeds
#     4. Transform   	- dbt warehouse (Bronze → warehouse, with quality gates)
#     5. ML          	- train + export scoring models
#     6. App         	- build web app, publish CDN
#     7. Docs        	- build reference docs + interactive graphs
#     8. Workflows   	- composite tasks (e.g., add a new season)
#     9. Security    	- supply-chain + secret scans (mirror the CI gates)
#    10. Housekeeping 	- cleanup
#
#  New here? Just run `make` (or `make help`) to see all targets grouped by stage.
# ════════════════════════════════════════════════════════════════════════════════

.DEFAULT_GOAL := help

# Interpreter for all Python targets (override: make PYTHON=... <target>)
PYTHON ?= ./.venv/bin/python

.PHONY: \
	help \
	setup setup-check ml-setup app-install \
	ingest-all ingest-recent ingest-jolpica verify-bronze monitor-ingest manifest-report ingest-plan season-seeds-check simulate \
	test test-integration cov-python \
	coefficients-fit coefficients-promote coefficients-status coefficients-check deg-iso-fit \
	dbt-dev dbt-dev-full dbt-prod dbt-test dbt-docs query \
	lint lint-fix lint-oracle-snapshot lint-oracle-check \
	test-all test-fast transform-check data-profile-snapshot data-profile-check dq-test \
	ml-features ml-tune ml-train ml-retrain ml-evaluate ml-attribution ml-predict ml-onnx ml-card ml-reference ml-all ml-test ml-clean ml-docs-images \
	app-data app-cards-check app-data-wave0 app-data-check app-models app-dev app-dev-local app-build app-parity app-coverage app-bundle app-bundle-budget-update app-e2e app-e2e-install app-lighthouse app-publish app-publish-staging app-publish-dry app-smoke app-promote app-rollback verify-published bucket-lifecycle app-deploy \
	tf-init tf-validate tf-plan tf-apply tf-import \
	docs-reference docs-coverage docs-coverage-check project-graph watch-graph docs-audit docs-facts docs-app-audit lint-comments docs-site docs-install \
	add-season \
	audit sbom secret-scan security \
	clean-logs clean-ds clean-dev

help:  ## Show this help, grouped by pipeline stage
	@awk 'BEGIN {FS = ":.*##"} \
		/^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0, 5); next} \
		/^[a-zA-Z0-9_.-]+:.*?##/ {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""


##@ 1. Setup
VENV ?= .venv

setup:  ## Build venv + install all deps (ingestion pins first, then root, then ml), scaffold data/ (run first)
	@if [ ! -d "$(VENV)" ]; then \
		echo "Creating virtual environment..."; \
		uv venv -p 3.14 $(VENV); \
	fi
	uv pip install -p $(VENV) -r ingestion/requirements.txt -r requirements.txt -r ml/requirements.txt
	mkdir -p data/bronze data/silver data/gold data/cache data/marts
	touch data/bronze/.gitkeep data/silver/.gitkeep data/gold/.gitkeep data/cache/.gitkeep data/marts/.gitkeep
	cd transform && ../.venv/bin/dbt deps

setup-check:  ## Offline env check: Python 3.14.x, fastf1==3.9.2, pip check clean
	@set -e; \
	$(VENV)/bin/python -c "import sys; assert sys.version_info[:2]==(3,14), 'Python 3.14.x required, got '+sys.version" ; \
	$(VENV)/bin/python -c "import fastf1; assert fastf1.__version__=='3.9.2', 'fastf1 3.9.2 required, got '+fastf1.__version__"; \
	uv pip check -p $(VENV); \
	echo "setup-check OK"

ml-setup:  ## Install ML deps (ml/requirements.txt) into the shared venv
	./.venv/bin/pip install -r ml/requirements.txt

app-install:  ## Install web-app dependencies (pnpm)
	cd app && pnpm install


##@ 2. Ingest
ingest-all:  ## Pull all 2018–2025 races → Bronze (~7 GB, mostly telemetry; 35–50 min)
	$(PYTHON) ingestion/src/ingest.py --start-season 2018 --end-season 2025 --session both

ingest-full:  ## Full FastF1 pull 2018–2026 → Bronze, then lock + verify. Interactive terminal view; resumable (Ctrl+C, re-run)
	PYTHON="$(PYTHON)" $(PYTHON) ingestion/scripts/ingest_full_tui.py

bronze-lock:  ## Write data/bronze/MANIFEST.json (SHA-256 per file) and set the immutable flag on data/bronze
	$(PYTHON) ingestion/src/bronze_lock.py lock data/bronze

bronze-verify:  ## Re-hash data/bronze against MANIFEST.json; exit 1 on any added, missing or changed file
	$(PYTHON) ingestion/src/bronze_lock.py verify data/bronze

bronze-unlock:  ## Clear the immutable flag on data/bronze (deliberate rebuild only)
	$(PYTHON) ingestion/src/bronze_lock.py unlock data/bronze

ingest-recent:  ## Pull 2023–2024 only → Bronze (~15 min, ~200 MB)
	$(PYTHON) ingestion/src/ingest.py --start-season 2023 --end-season 2024 --session both

ingest-jolpica:  ## Pull standings + pit stops (2018–2025) via Jolpica API (~2–3 min)
	$(PYTHON) ingestion/src/jolpica_client.py --start-season 2018 --end-season 2025

verify-bronze:  ## Verify Bronze integrity (counts, nulls, schema)
	$(PYTHON) ingestion/verify_bronze.py

monitor-ingest:  ## Watch a running ingest log for failures/completion (LOG=path)
	@test -n "$(LOG)" || { echo "Usage: make monitor-ingest LOG=path/to/ingest.log"; exit 1; }
	$(PYTHON) ingestion/scripts/monitor_ingest.py $(LOG)

simulate:  ## Replay a Bronze race lap-by-lap (demo of the data)
	$(PYTHON) ingestion/src/replay_simulator.py --parquet_path data/bronze/laps/season=2024/race=bahrain_grand_prix/2024_bahrain_grand_prix_laps.parquet --race_id 2024_1 --speed 10

manifest-report:  ## Report ingestion run status + schema-drift from manifests
	$(PYTHON) ingestion/manifest_report.py

ingest-plan:  ## Dry run: which rounds of SEASON would be pulled / skipped / are not run yet
	@test -n "$(SEASON)" || { echo "Usage: make ingest-plan SEASON=YYYY"; exit 1; }
	$(PYTHON) ingestion/src/ingest.py --season $(SEASON) --session both --dry-run

season-seeds-check:  ## List the seed rows SEASON still needs (race_to_track, scheduled laps, ...)
	@test -n "$(SEASON)" || { echo "Usage: make season-seeds-check SEASON=YYYY"; exit 1; }
	$(PYTHON) ingestion/scripts/check_season_seeds.py --season $(SEASON)

test:  ## Offline ingestion unit tests (no network, <5 s)
	./.venv/bin/pytest ingestion/tests/test_ingestion.py ingestion/tests/test_jolpica.py \
		ingestion/tests/test_ingest_hardening.py ingestion/tests/test_bronze_verification.py \
		ingestion/tests/test_ingest_full_tui.py

test-integration:  ## Live FastF1 ingestion test (needs network)
	./.venv/bin/pytest ingestion/tests/test_integration_fastf1.py -m integration

cov-python:  ## Coverage-threshold gate for the self-contained Python suites
	PYTHONPATH=. ./.venv/bin/pytest ingestion/tests/test_ingestion.py ingestion/tests/test_jolpica.py \
		ingestion/tests/test_ingest_hardening.py ingestion/tests/test_bronze_verification.py \
		--cov=ingestion --cov-report=term-missing --cov-fail-under=55
	PYTHONPATH=transform ./.venv/bin/pytest transform/tasks/coefficients/tests/ \
		--cov=transform/tasks/coefficients --cov-report=term-missing --cov-fail-under=60
	$(PYTHON) -m pytest ml/tests \
		--cov=ml/src --cov-report=term-missing --cov-fail-under=25


##@ 3. Coefficients
coefficients-fit:  ## Fit cliff + weight-penalty seeds → seeds/_pending/ (no promote)
	cd transform && ../.venv/bin/python -m tasks.coefficients.fit_compound_cliff
	cd transform && ../.venv/bin/python -m tasks.coefficients.fit_weight_penalty
	@echo ""
	@echo "Pending seeds written to transform/seeds/_pending/"
	@echo "Review, then run: make coefficients-promote"

coefficients-promote:  ## Promote _pending/ seeds → live (archives previous)
	cd transform && ../.venv/bin/python -m tasks.coefficients.seed_writer promote --all --confirm

coefficients-status:  ## Show current seed state
	cd transform && ../.venv/bin/python -m tasks.coefficients.seed_writer status

coefficients-check:  ## Warn (non-fatal) if seeds are stale vs the data window
	cd transform && ../.venv/bin/python -m tasks.coefficients.check_freshness || true

deg-iso-fit:  ## Fit isotonic tyre-deg curves + modulation coefs → data/fits/degradation_isotonic.parquet
	cd transform && ../.venv/bin/python -m tasks.coefficients.fit_degradation_isotonic


##@ 4. Transform

##   Build targets
dbt-dev:  ## Build all dbt models + run their tests → data/dev.duckdb
	cd transform && ../.venv/bin/dbt build --profiles-dir profiles --target dev

dbt-dev-full: coefficients-check  ## Seed check → full dbt build (models + tests)
	cd transform && ../.venv/bin/dbt build --profiles-dir profiles --target dev

dbt-prod:  ## Prod build (Fabric deferred runs against dev for now)
	cd transform && ../.venv/bin/dbt build --profiles-dir profiles --target dev

dbt-docs:  ## Generate + serve the dbt docs site (port 8080)
	cd transform && ../.venv/bin/dbt docs generate --profiles-dir profiles && ../.venv/bin/dbt docs serve

query:  ## Open the warehouse in the Harlequin SQL IDE
	./.venv/bin/harlequin data/dev.duckdb

##   Test targets
dbt-test:  ## Run all dbt tests (schema + singular + assert_* invariants)
	cd transform && ../.venv/bin/dbt test --profiles-dir profiles --target dev

test-all:  ## CI-equivalent: full dbt build on fixtures + coefficient tests
	cd transform && ../.venv/bin/dbt build --profiles-dir profiles --target ci --vars '{"bronze_base": "../transform/tests/fixtures/bronze", "fits_base": "../transform/tests/fixtures/fits"}'
	PYTHONPATH=transform ./.venv/bin/pytest transform/tasks/coefficients/tests/

test-fast:  ## CI fast path: fast_build selector on fixtures
	cd transform && ../.venv/bin/dbt build --profiles-dir profiles --target ci --selector fast_build --vars '{"bronze_base": "../transform/tests/fixtures/bronze", "fits_base": "../transform/tests/fixtures/fits"}'

##   Lint targets
lint:  ## SQLFluff lint all models
	cd transform && ../.venv/bin/sqlfluff lint models/ --dialect duckdb --disable-progress-bar

lint-fix:  ## SQLFluff auto-fix all models
	cd transform && ../.venv/bin/sqlfluff fix models/ --dialect duckdb --disable-progress-bar

##   Oracle gates (byte-stability for fct_* models)
lint-oracle-snapshot:  ## Record byte-stable baseline of all model outputs (run on a known-good ci.duckdb)
	cd transform && ../.venv/bin/python scripts/snapshot_model_hashes.py

lint-oracle-check:  ## Fail if any fct_* model output drifted vs the recorded baseline (gates lint fixes)
	cd transform && ../.venv/bin/python scripts/snapshot_model_hashes.py --check

##   Composite gate (all CI checks in sequence)
transform-check:  ## Reproduce the CI transform gates in order (parse → lint → build → singular tests → oracle → pytest)
	cd transform && ../.venv/bin/dbt parse --profiles-dir profiles --target ci
	cd transform && ../.venv/bin/sqlfluff lint models/ --dialect duckdb --disable-progress-bar
	cd transform && ../.venv/bin/dbt build --profiles-dir profiles --target ci --vars '{"bronze_base": "../transform/tests/fixtures/bronze", "fits_base": "../transform/tests/fixtures/fits"}'
	cd transform && ../.venv/bin/dbt test --profiles-dir profiles --target ci --select test_type:singular --vars '{"bronze_base": "../transform/tests/fixtures/bronze", "fits_base": "../transform/tests/fixtures/fits"}'
	cd transform && ../.venv/bin/python scripts/snapshot_model_hashes.py --check
	PYTHONPATH=transform ./.venv/bin/pytest transform/tasks/coefficients/tests/

##   Data quality
data-profile-snapshot:  ## Record the data-profile baseline (row counts, null-rates, means) from data/dev.duckdb
	$(PYTHON) transform/scripts/snapshot_data_profile.py --db data/dev.duckdb

data-profile-check:  ## Fail on data-profile drift vs the committed baseline (volume / null-rate / mean)
	$(PYTHON) transform/scripts/snapshot_data_profile.py --db data/dev.duckdb --check

dq-test:  ## Data-quality suite: build-over-build profile diff + source freshness (MIN_SEASON=YYYY)
	$(PYTHON) transform/scripts/snapshot_data_profile.py --db data/dev.duckdb --check
	$(PYTHON) transform/scripts/check_source_freshness.py --db data/dev.duckdb --min-season $(or $(MIN_SEASON),2024)


##@ 5. ML
ml-features:  ## Validate the ML feature contract against the warehouse
	$(PYTHON) -m ml.src.features --check

ml-tune:  ## Hyperparameter search (Optuna, 50 trials) → chains production-version refit
	$(PYTHON) -m ml.src.tune --target all --trials 50

ml-train:  ## Train all five at SMOKE_DEFAULTS as version v1 (experiments only - NOT a production retrain, use ml-retrain)
	$(PYTHON) -m ml.src.train --all

ml-retrain:  ## Production retrain: all five at their own *_best_params.json, at MODEL_VERSION_DEFAULT (no new search)
	$(PYTHON) -m ml.src.train --all --tuned

ml-evaluate:  ## Evaluate models (metrics + leakage checks)
	$(PYTHON) -m ml.src.evaluate --all

ml-attribution:  ## Evaluate + within-stint attribution, drop/flatten/causal. Slow: ~50 refits/target
	$(PYTHON) -m ml.src.evaluate --all --attribution

ml-predict:  ## Score → data/marts/mart_degradation_predictions.parquet
	$(PYTHON) -m ml.src.predict --out data/marts/mart_degradation_predictions.parquet

ml-onnx:  ## Export ONNX + parity + ml/models/manifest.json (no copy to app/)
	$(PYTHON) -m ml.src.export_onnx --all

ml-card:  ## Write the model card (ml/models/model_card.json)
	$(PYTHON) -m ml.src.card --write

ml-reference:  ## Regenerate the ML reference docs
	$(PYTHON) scripts/gen_ml_reference.py

# ml-tune already chains a production-version refit at the params it just found, so the
# chain does not call ml-train (which would write untuned v1 artefacts nothing reads).
ml-all: ml-features ml-tune ml-evaluate ml-predict ml-onnx ml-card ml-reference  ## Full ML pipeline end-to-end

ml-test:  ## ML unit tests (leakage, parity, schema)
	$(PYTHON) -m pytest ml/tests -q

ml-clean:  ## Remove built models + predictions
	rm -rf ml/models/*.bst ml/models/*.onnx ml/artefacts/* data/marts/mart_degradation_predictions.parquet


##@ 6. App

##   Data export
app-data:  ## Export warehouse → app/public/data/ parquet + _manifest.json, then cards (AX-08: export, build-cards, --finalize)
	$(PYTHON) scripts/export_app_data.py
	cd app && node scripts/build-cards.mjs --data public/data --stage
	$(PYTHON) scripts/export_app_data.py --finalize

app-cards-check:  ## Rebuild cards into a temp copy of app/public/data and compare card sha256 with the manifest (no warehouse)
	$(PYTHON) scripts/check_cards.py

app-data-canary:  ## Export canary tables only (fast)
	$(PYTHON) scripts/export_app_data.py --canary

app-data-check:  ## CI drift gate: regenerate manifest and diff (no write)
	$(PYTHON) scripts/export_app_data.py --check

assistant-freeze-verify:  ## AX-19: recompute the assistant freeze from disk and diff against freeze.json (exit 1 names the field)
	$(PYTHON) scripts/assistant_freeze.py --verify

##   Models
app-models:  ## Copy ONNX models (version per manifest) + manifest/encoders → app/public/models/
	@mkdir -p app/public/models
	@if [ -d ml/models ]; then \
	  ver=$$($(PYTHON) -c "import json;print(json.load(open('ml/models/manifest.json'))['model_version'])"); \
	  rm -f app/public/models/*.onnx; \
	  cp ml/models/*_$$ver.onnx app/public/models/ 2>/dev/null || true; \
	  cp ml/models/manifest.json app/public/models/ 2>/dev/null || true; \
	  cp ml/models/encoders.json app/public/models/ 2>/dev/null || true; \
	  cp ml/models/model_card.json app/public/models/ 2>/dev/null || true; \
	  echo "  ✅  $$ver ONNX models copied to app/public/models/"; \
	  ls -lh app/public/models/; \
	else \
	  echo "  ⚠️   ml/models/ not found run: make ml-onnx"; \
	fi

##   Dev server
app-dev:  ## Start Vite dev server (reads live CDN data)
	cd app && pnpm dev

app-dev-local:  ## Start Vite dev server using local app/public/data/ (offline)
	cd app && VITE_DATA_BASE="" pnpm dev

##   Build + validation
app-build:  ## Type-check + build the React app → app/dist/ (prod reads data+models from the GCS CDN; use app-dev-local for the offline route)
	cd app && pnpm build

app-parity:  ## Prove in-browser ONNX == booster ground truth
	PYTHONPATH=. $(PYTHON) scripts/dump_parity_rows.py
	cd app && RUN_PARITY=1 ./node_modules/.bin/vitest run src/ml/parity.node.test.ts --environment node

app-coverage:  ## Vitest unit tests with coverage threshold
	cd app && pnpm test:coverage

app-bundle:  ## Check the built JS bundle against the size budget (run app-build first; for a VITE_ASSISTANT_ENABLED=true build use: cd app && pnpm build --manifest)
	cd app && pnpm run bundlesize

app-bundle-budget-update:  ## Rewrite app/perf-budget.json from the current build (+8% headroom)
	cd app && node scripts/check_bundle_size.mjs --update

app-e2e-install:  ## Install the Playwright Chromium browser (one-time, before app-e2e)
	cd app && pnpm exec playwright install --with-deps chromium

app-e2e:  ## Playwright E2E smoke (builds, serves prod bundle, drives DuckDB/ONNX/identity vs live CDN)
	cd app && pnpm build && pnpm exec playwright test

app-lighthouse:  ## Lighthouse CI on the shell routes (advisory CWV; needs a prior app-build)
	cd app && pnpm dlx @lhci/cli@0.14.x autorun --config=./lighthouserc.json

##   Publish to CDN
app-publish:  ## Sync app/public/data/ → live GCS CDN prod (no delete; manifest last)
	./scripts/publish_cdn.sh

app-publish-staging:  ## Publish app/public/data/ → CDN staging/ prefix (smoke before promote)
	./scripts/publish_cdn.sh --env staging

app-publish-dry:  ## Preview the CDN sync without uploading
	./scripts/publish_cdn.sh --dry-run

app-smoke:  ## Smoke the CDN data plane (ENV=prod|staging; manifest + sample parquet)
	./scripts/smoke_cdn.sh --env $(or $(ENV),prod)

app-promote:  ## Promote the staging CDN revision → prod (smokes staging, archives prod manifest)
	./scripts/promote_cdn.sh

app-rollback:  ## Roll prod back to the previous manifest (TO=<archive> | default --previous)
	./scripts/rollback_cdn.sh $(if $(TO),--to $(TO),--previous)

verify-published:  ## Post-publish gate: version + stats parity + ONNX (ENV=prod|staging; ROLLBACK=1 to undo)
	./scripts/verify_published.sh --env $(or $(ENV),prod) $(if $(ROLLBACK),--rollback-on-fail,) $(if $(SITE),--site $(SITE),)

bucket-lifecycle:  ## Apply the GCS lifecycle GC policy + enable versioning (infra/gcs_lifecycle.json)
	./scripts/apply_bucket_lifecycle.sh

app-deploy: app-data app-models app-build app-publish  ## Export warehouse, build app, publish CDN, then deploy to Firebase
	npx firebase deploy --only hosting:app


##@ Infra (IaC)
##   Operator-gated: apply needs a project owner. tf-validate is creds-free; run it before changes.
##   Runbook: infra/terraform/README.md

TF := terraform -chdir=infra/terraform
TFSTATE_BUCKET ?= off-the-pace-tfstate

tf-init:  ## Init Terraform with the GCS state backend (TFSTATE_BUCKET=, PREFIX=infra)
	$(TF) init -backend-config="bucket=$(TFSTATE_BUCKET)" -backend-config="prefix=$(or $(PREFIX),infra)"

tf-validate:  ## Creds-free gate: fmt -check + validate (no backend, no state)
	$(TF) fmt -recursive -check -diff
	$(TF) init -backend=false -input=false >/dev/null
	$(TF) validate

tf-plan:  ## Show the plan (near no-op after tf-import on existing infra)
	$(TF) plan -input=false

tf-apply:  ## Apply the infra (needs project-owner ADC)
	$(TF) apply -input=false

tf-import:  ## Adopt existing scripts-created resources into TF state (run once, after tf-init)
	bash infra/terraform/import.sh


##@ 7. Docs
##   Tip: for live editing, run `make docs-site` and `make watch-graph` in two terminals.
##   The graph regenerates on source change and Mintlify hot-reloads.

docs-reference:  ## Regenerate docs/reference/**/*.mdx from source
	$(PYTHON) scripts/build_reference.py

docs-coverage:  ## Regenerate docs/snippets/{bronze-coverage,overview-numbers,transform-inventory*,ml-inventory*}.mdx from source
	$(PYTHON) scripts/ingestion_docs_facts.py --write
	$(PYTHON) scripts/overview_docs_facts.py --write
	cd transform && ../.venv/bin/dbt parse --profiles-dir profiles --target ci
	$(PYTHON) scripts/transform_docs_facts.py --write
	$(PYTHON) scripts/ml_docs_facts.py --write

ml-docs-images:  ## Copy curated ML artefact plots into docs/images/ml/ (calibration, PDP, learning curve)
	mkdir -p docs/images/ml
	cp ml/artefacts/calibration_degradation.png docs/images/ml/calibration-degradation.png
	cp ml/artefacts/pdp_degradation_regressor_p50.png docs/images/ml/pdp-degradation-regressor-p50.png
	cp ml/artefacts/learning_curve_degradation_regressor_p50.png docs/images/ml/learning-curve-degradation-regressor-p50.png

project-graph:  ## Regenerate the interactive project dependency graph HTML
	$(PYTHON) scripts/gen_project_graph.py -o docs/project-graph.html

watch-graph:  ## Watch source files and run project-graph on change
	$(PYTHON) scripts/watch_project_graph.py

docs-audit:  ## CI gate: README-presence + tour-footer + file-header checks
	$(PYTHON) scripts/docs_audit.py --headers

docs-facts:  ## CI gate: reconcile headline counts across README + docs
	$(PYTHON) scripts/docs_facts.py

docs-coverage-check:  ## CI gate: snippet mdx files match a fresh regeneration
	$(PYTHON) scripts/ingestion_docs_facts.py
	$(PYTHON) scripts/overview_docs_facts.py
	cd transform && ../.venv/bin/dbt parse --profiles-dir profiles --target ci
	$(PYTHON) scripts/transform_docs_facts.py
	$(PYTHON) scripts/ml_docs_facts.py

docs-app-audit:  ## CI gate: every shipped app feature has an /app/<slug> docs page
	$(PYTHON) scripts/app_docs_audit.py --strict

lint-comments:  ## CI gate: fail if banned planning/history language reaches committed source
	@! grep -rn \
	  --include="*.ts" --include="*.tsx" --include="*.py" --include="*.sh" \
	  --include="*.sql" --include="*.yml" --include="*.yaml" --include="*.tf" \
	  -E -f .github/lint-comments-patterns.txt \
	  --exclude-dir=".git" --exclude-dir="_roadmap" --exclude-dir="node_modules" \
	  --exclude-dir=".venv" --exclude-dir=".agents" --exclude-dir="target" . \
	  || { echo "Banned planning/history language in source. See CLEANUP_PLAN.md for the rule."; exit 1; }

docs-site:  ## Start the Mintlify docs dev server (http://localhost:3000)
	cd docs && npx -y mintlify dev

docs-install:  ## (no-op) npx fetches Mintlify automatically
	@echo "No global install needed. npx will be used automatically."


##@ 8. Workflows

add-season:  ## Onboard a new season end-to-end (stops before publish): make add-season SEASON=YYYY
	@test -n "$(SEASON)" || { echo "Usage: make add-season SEASON=YYYY"; exit 1; }
	@echo "── 1/7  Ingest finished rounds for $(SEASON) (unrun rounds skipped) ──"
	$(PYTHON) ingestion/src/ingest.py --season $(SEASON) --session both
	@echo "── 2/7  Ingest standings + pit stops for $(SEASON) ─────────────────"
	$(PYTHON) ingestion/src/jolpica_client.py --start-season $(SEASON) --end-season $(SEASON)
	@echo "── 3/7  Verify Bronze integrity ────────────────────────────────────"
	$(PYTHON) ingestion/verify_bronze.py
	@echo "── 4/7  Seed coverage for $(SEASON) (stops with a to-do list) ──────"
	$(PYTHON) ingestion/scripts/check_season_seeds.py --season $(SEASON)
	@echo "── 5/7  Re-fit isotonic tyre-deg curves ────────────────────────────"
	$(MAKE) deg-iso-fit
	@echo "── 6/7  Full dbt build + tests (car-FE refit + all models) ────────"
	$(MAKE) dbt-dev-full
	@echo "── 7/7  Export warehouse → app/public/data/ ────────────────────────"
	$(MAKE) app-data
	@echo "── ✔    Smoke test ─────────────────────────────────────────────────"
	$(PYTHON) scripts/smoke_test_season.py $(SEASON)
	@echo ""
	@echo "✔  Season $(SEASON) onboarded locally."
	@echo "   Review the simulator at: make app-dev-local"
	@echo "   When satisfied, publish: make app-publish"


##@ 9. Security

# Mirrors security-scan.yml. Locally these hard-fail on findings (you run them to *see*
# problems); in CI the dependency audits are non-blocking until the backlog is clean.
security: audit secret-scan  ## Run the full local security sweep (audit + secret-scan)

audit:  ## Dependency CVE scan: pip-audit (root + ml) + pnpm audit (app)
	@command -v pip-audit >/dev/null 2>&1 || { echo "pip-audit not found  →  pip install pip-audit  (or: pipx install pip-audit)"; exit 1; }
	pip-audit -r requirements.txt --desc
	pip-audit -r ml/requirements.txt --desc
	cd app && pnpm audit --prod

secret-scan:  ## Scan tree + git history for committed secrets (mirrors security-scan.yml; needs gitleaks)
	@command -v gitleaks >/dev/null 2>&1 || { echo "gitleaks not found  →  brew install gitleaks  (https://github.com/gitleaks/gitleaks)"; exit 1; }
	gitleaks detect --no-banner --redact

sbom:  ## Generate a CycloneDX SBOM → sbom.cyclonedx.json (mirrors sbom.yml; needs syft)
	@command -v syft >/dev/null 2>&1 || { echo "syft not found  →  brew install syft  (https://github.com/anchore/syft)"; exit 1; }
	syft scan dir:. -o cyclonedx-json=sbom.cyclonedx.json
	@echo "✔  Wrote sbom.cyclonedx.json"


##@ 10. Housekeeping

clean-logs:  ## Remove dbt + ingestion + root logs
	rm -rf transform/logs/*.log transform/logs/*.log.* ingestion/_archive/*.log ingestion/_archive/*.txt logs/*.log

clean-ds:  ## Remove stray .DS_Store files
	find . -name ".DS_Store" -depth -exec rm {} \;

clean-dev:  ## Kill all local Vite, Mintlify, and dbt docs dev servers
	@echo "Stopping local dev servers on ports 5173, 3000, 8080..."
	@pkill -f vite || true
	@pkill -f mintlify || true
	@lsof -ti :5173,3000,8080 | xargs kill -9 2>/dev/null || true
	@echo "✔  All local dev servers stopped."
