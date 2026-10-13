# docs/ — the Mintlify site

Source for [offthepace.mintlify.app](https://offthepace.mintlify.app). Pages are MDX with YAML
frontmatter; navigation, theme and tabs live in [`docs.json`](docs.json). Writing conventions
(terminology, sign convention, the app feature-page contract) are in [`AGENTS.md`](AGENTS.md).

## Preview locally

```bash
make docs-site        # runs `npx mintlify dev` in docs/ → http://localhost:3000
```

Needs Node.js 18+. Nothing to install globally; `npx` fetches the Mintlify CLI.

## Layout

Five tabs, one per pipeline layer plus a front door:

| Tab | Folders |
|---|---|
| Start Here | `index`, `about`, `engineering-highlights`, `system-design`, `data-engineering`, `key-concepts`, `findings/`, `platform/` |
| Data | `data/`, `ingestion/`, `reference/schemas/`, `reference/cli/` |
| Transform | `transform/`, `decomposition/`, `reference/models/`, `reference/macros/` |
| Machine Learning | `ml/`, `reference/ml/` |
| App | `app/` (one page per shipped feature, plus `app/families/`) |

Shared fragments live in `snippets/`, images in `images/`, and the interactive dependency graph
is `project-graph.html` (built by `make project-graph`).

## Generated, never hand-edited

| Path | Regenerate with | Source |
|---|---|---|
| `reference/**` | `make docs-reference` | dbt manifest, Bronze schemas, CLI `--help`, `ml/model_card.yml` |
| `snippets/bronze-coverage.mdx`, `overview-numbers.mdx`, `transform-inventory*.mdx`, `ml-inventory*.mdx` | `make docs-coverage` | Bronze data, `README.md` headline counts, dbt manifest, `ml/src/schema.py` + pytest collection |

A new dbt model needs a `schema.yml` entry with `meta.family` before `make docs-reference` will
run. After regenerating, add any new reference page to the matching group in `docs.json`.

## CI gates

`.github/workflows/docs-ci.yml` runs these on every pull request that touches docs or source:

| Gate | Local command |
|---|---|
| Mintlify config + broken links | `cd docs && npx mintlify validate && npx mintlify broken-links` |
| Reference pages match a fresh build | `make docs-reference`, then `git diff docs/reference/` |
| Snippets match a fresh build | `make docs-coverage-check` |
| Headline counts agree across README and docs | `make docs-facts` |
| Every shipped app feature has a page | `make docs-app-audit` |
| Required READMEs, tour footers, file headers | `make docs-audit` |

## Publishing

The Mintlify GitHub app deploys the default branch automatically; there is no manual publish step.

---

← Previous in tour: [app/](../app/README.md) · **Next in tour: [scripts/](../scripts/README.md) →**
