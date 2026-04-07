#!/usr/bin/env bash
#
# Adopt the EXISTING infra (created earlier by scripts/setup_wif.sh, the manual bucket
# create, and apply_bucket_lifecycle.sh) into Terraform state, so the first `terraform apply`
# reconciles in place instead of trying to re-create resources that already exist.
#
# Run ONCE, after `make tf-init`, as a project owner with ADC set. Idempotent: `terraform
# import` no-ops on resources already in state. Resources that don't exist yet (e.g. the
# Firebase site if you've never used Firebase) just error skip them.
#
# Usage:  bash infra/terraform/import.sh
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PROJECT_ID="${PROJECT_ID:-off-the-pace}"
BUCKET="${BUCKET:-off-the-pace-cdn}"
GITHUB_REPO="${GITHUB_REPO:-JustinClarke/off-the-pace}"
POOL_ID="${POOL_ID:-github-pool}"
PROVIDER_ID="${PROVIDER_ID:-github-provider}"
SA_NAME="${SA_NAME:-gh-deploy}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
PROJECT_NUMBER="${PROJECT_NUMBER:-$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')}"

PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_REPO}"

imp() {  # imp <address> <id> tolerate "already managed" / "not found" so the script is re-runnable
  echo "── import $1"
  terraform import -input=false "$1" "$2" || echo "   (skipped: already in state or resource absent)"
}

# Enabled APIs
for svc in iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
           storage.googleapis.com firebase.googleapis.com firebasehosting.googleapis.com \
           cloudresourcemanager.googleapis.com cloudbilling.googleapis.com \
           billingbudgets.googleapis.com monitoring.googleapis.com; do
  imp "google_project_service.enabled[\"${svc}\"]" "${PROJECT_ID}/${svc}"
done

# CDN bucket + IAM
imp google_storage_bucket.cdn                       "${PROJECT_ID}/${BUCKET}"
imp google_storage_bucket_iam_member.public_read    "b/${BUCKET} roles/storage.objectViewer allUsers"
imp google_storage_bucket_iam_member.deploy_object_admin "b/${BUCKET} roles/storage.objectAdmin serviceAccount:${SA_EMAIL}"

# WIF pool / provider / SA
imp google_iam_workload_identity_pool.github          "projects/${PROJECT_ID}/locations/global/workloadIdentityPools/${POOL_ID}"
imp google_iam_workload_identity_pool_provider.github "projects/${PROJECT_ID}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"
imp google_service_account.deploy                     "projects/${PROJECT_ID}/serviceAccounts/${SA_EMAIL}"

# IAM bindings
imp google_project_iam_member.deploy_firebase     "${PROJECT_ID} roles/firebasehosting.admin serviceAccount:${SA_EMAIL}"
imp google_project_iam_member.deploy_serviceusage "${PROJECT_ID} roles/serviceusage.serviceUsageConsumer serviceAccount:${SA_EMAIL}"
imp google_service_account_iam_member.deploy_wif_user "projects/${PROJECT_ID}/serviceAccounts/${SA_EMAIL} roles/iam.workloadIdentityUser ${PRINCIPAL}"

echo
echo "  ✅  Import pass done. Now: terraform plan expect it to be a near no-op."
echo "      Any planned *changes* are real drift between the scripts and this module review them."
