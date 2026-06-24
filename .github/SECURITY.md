# Security Policy

_Off The Pace_ is a static, serverless analytics site: all compute is either offline
(build time) or client-side (in the browser). There is no backend, no user accounts, and no
secrets served at runtime the attack surface is the supply chain and the build/deploy
pipeline. This policy covers how vulnerabilities are reported and what is automated to
prevent them.

## Reporting a vulnerability

**Do not open a public issue for a security vulnerability.** Instead, use GitHub's private
reporting:

1. Go to the repository's **Security** tab → **Report a vulnerability** (GitHub private
   vulnerability reporting).
2. Describe the issue, the affected component, and reproduction steps.

If private reporting is unavailable, contact the maintainer directly via GitHub. You will
get an acknowledgement within a few days; please allow reasonable time for a fix before any
public disclosure.

## What is automated

These run in CI (`.github/workflows/`) on every PR to `main`, plus a weekly schedule:

| Concern | Tooling | Workflow | Posture |
|---|---|---|---|
| SAST (Python + TS/JS) | CodeQL (`security-extended`) | `codeql.yml` | Blocking |
| Committed secrets | gitleaks | `security-scan.yml` | **Blocking** |
| Python dependency CVEs | `pip-audit` (root + `ml/`) | `security-scan.yml` | Non-blocking¹ |
| npm dependency CVEs | `pnpm audit --prod` | `security-scan.yml` | Non-blocking¹ |
| Cross-ecosystem CVEs | OSV-Scanner (SARIF → Security tab) | `osv-scanner.yml` | PR-diff: blocking on *new* vulns |
| Dependency updates | Dependabot (grouped, weekly) | `dependabot.yml` | PRs |
| Inventory | CycloneDX SBOM (syft) | `sbom.yml` | On release |

¹ Dependency audits start non-blocking (`continue-on-error: true`) so the existing advisory
backlog can be triaged without wedging PRs. Flip those steps to blocking once the backlog is
clean. See the comment at the top of `security-scan.yml`.

## Required one-time GitHub settings

Some controls live in **repo settings**, not in code, and must be enabled by an admin
(Settings → Code security). These complement the workflows above:

- [ ] **Secret scanning** on (catches secrets server-side, including in history).
- [ ] **Push protection** on (blocks secrets *before* they are committed; the gitleaks
      CI gate is the backstop, not the first line).
- [ ] **Dependabot alerts** + **Dependabot security updates** on (turns the
      `dependabot.yml` schedule into CVE-driven patch PRs).
- [ ] **Private vulnerability reporting** on (enables the reporting flow above).
- [ ] **CodeQL: switch "Default setup" → "Advanced"** required, otherwise the committed
      `codeql.yml` conflicts with default setup and errors.
- [ ] **Branch protection on `main`** require these status checks before merge:
      `App CI`, `dbt CI`, `ML CI`, `Docs CI`, CodeQL, and `Security Scan / Secret scan
      (gitleaks)`.

## Scope

In scope: this repository's code, CI/CD, and published artifacts (the app bundle, the GCS
CDN data/models). Out of scope: the upstream FastF1 / Jolpica data sources, and the
analytics/model *correctness* (covered by the dbt identity oracle and ML leakage guards,
not by this policy).
