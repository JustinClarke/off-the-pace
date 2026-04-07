# Provider config. project/region come from variables so the same module can target a
# throwaway project for a dry run. Credentials are ambient (ADC) a project owner runs
# this locally or via a CI job that has WIF-impersonated owner creds; no keys in the repo.
provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
