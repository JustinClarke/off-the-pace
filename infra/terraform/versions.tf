# Terraform + provider pins.
# Pinned major versions so a provider release can't silently change a plan; bump
# deliberately (Dependabot doesn't track Terraform providers).
terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    # google-beta is only needed for the Firebase resources (optional, see firebase.tf).
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
  }

  # Remote state in GCS. Partial config supply bucket + prefix at init time so the
  # state bucket isn't hard-coded here (it is itself infra). See README.md → "State".
  #   terraform init \
  #     -backend-config="bucket=off-the-pace-tfstate" \
  #     -backend-config="prefix=infra"
  backend "gcs" {}
}
