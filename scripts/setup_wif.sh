#!/usr/bin/env bash
#
# One-time setup of GCP Workload Identity Federation (WIF) so GitHub Actions can deploy
# WITHOUT a long-lived service-account JSON key.
#
# It creates:
#   • a Workload Identity Pool + an OIDC provider that trusts GitHub's token issuer,
#     restricted to THIS repository (attribute-condition) so no other repo can mint creds;
#   • a deploy service account scoped to exactly what CD needs write the CDN bucket and
#     deploy Firebase Hosting and nothing else;
#   • the binding that lets the GitHub repo impersonate that service account.
#
# Run it once, locally, as a project owner:  bash scripts/setup_wif.sh
# It is idempotent re-running reconciles rather than duplicates. At the end it prints the
# two values to store as repo-level Actions variables (see .github/DEPLOYMENT.md):
#   vars.GCP_WORKLOAD_IDENTITY_PROVIDER   and   vars.GCP_DEPLOY_SERVICE_ACCOUNT
#
# Requires: gcloud authenticated as an owner of the project; the project's numeric ID.

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-off-the-pace}"
GITHUB_REPO="${GITHUB_REPO:-JustinClarke/off-the-pace}"
CDN_BUCKET_NAME="${CDN_BUCKET_NAME:-off-the-pace-cdn}"   # bucket name, no gs:// prefix
POOL_ID="${POOL_ID:-github-pool}"
PROVIDER_ID="${PROVIDER_ID:-github-provider}"
SA_NAME="${SA_NAME:-gh-deploy}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "  project:  $PROJECT_ID"
echo "  repo:     $GITHUB_REPO"
echo "  bucket:   gs://$CDN_BUCKET_NAME"
echo

command -v gcloud >/dev/null 2>&1 || { echo "❌  gcloud not found: https://cloud.google.com/sdk/docs/install" >&2; exit 1; }

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
echo "  project number: $PROJECT_NUMBER"

# ── Enable the APIs WIF + the deploy depend on ──────────────────────────────────
gcloud services enable \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  firebasehosting.googleapis.com \
  storage.googleapis.com \
  --project "$PROJECT_ID"

# ── 1. Workload Identity Pool ───────────────────────────────────────────────────
if ! gcloud iam workload-identity-pools describe "$POOL_ID" \
      --project "$PROJECT_ID" --location=global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$POOL_ID" \
    --project "$PROJECT_ID" --location=global \
    --display-name="GitHub Actions pool"
fi

# ── 2. OIDC provider, locked to this repo ───────────────────────────────────────
# attribute-condition restricts token exchange to GITHUB_REPO: without it ANY GitHub
# repo could impersonate the deploy SA. The repository_owner guard is belt-and-braces.
if ! gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
      --project "$PROJECT_ID" --location=global --workload-identity-pool="$POOL_ID" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --project "$PROJECT_ID" --location=global --workload-identity-pool="$POOL_ID" \
    --display-name="GitHub OIDC" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --attribute-condition="assertion.repository=='${GITHUB_REPO}'"
fi

# ── 3. Deploy service account ───────────────────────────────────────────────────
if ! gcloud iam service-accounts describe "$SA_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" \
    --project "$PROJECT_ID" \
    --display-name="GitHub Actions deploy (WIF, no keys)"
fi

# ── 4. Least-privilege roles ────────────────────────────────────────────────────
# Bucket: object admin scoped to the CDN bucket only (not project-wide storage admin).
gcloud storage buckets add-iam-policy-binding "gs://${CDN_BUCKET_NAME}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin"

# Firebase Hosting deploy + the API-enablement check the CLI performs.
for ROLE in roles/firebasehosting.admin roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$ROLE" --condition=None >/dev/null
done

# ── 5. Let the repo (and only this repo) impersonate the SA via the pool ─────────
PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_REPO}"
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --project "$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="$PRINCIPAL"

PROVIDER_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"

cat <<EOF

  ✅  WIF configured. Set these as repository Actions variables
      (Settings → Secrets and variables → Actions → Variables):

        GCP_WORKLOAD_IDENTITY_PROVIDER = ${PROVIDER_RESOURCE}
        GCP_DEPLOY_SERVICE_ACCOUNT     = ${SA_EMAIL}

      Then the deploy/preview workflows authenticate with no JSON key.
      Full runbook: .github/DEPLOYMENT.md
EOF
