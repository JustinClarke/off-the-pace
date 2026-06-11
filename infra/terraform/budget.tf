# Cost monitoring. A GCP billing budget over the CDN's storage +
# egress, with email alerts the cost analogue of the SLO alerting in .github/OBSERVABILITY.md.
# All of this is gated on var.billing_account being set (it requires billing-account access the
# default plan/validate path doesn't have), so it's a clean no-op until an operator wires it.

locals {
  budget_enabled = var.billing_account != ""
}

# Email notification channels for the budget. all_updates_rule references these.
resource "google_monitoring_notification_channel" "budget_email" {
  for_each = local.budget_enabled ? toset(var.budget_alert_emails) : toset([])

  project      = var.project_id
  display_name = "Budget alert → ${each.value}"
  type         = "email"
  labels = {
    email_address = each.value
  }

  depends_on = [google_project_service.enabled]
}

resource "google_billing_budget" "cdn" {
  count = local.budget_enabled ? 1 : 0

  billing_account = var.billing_account
  display_name    = "off-the-pace CDN storage + egress"

  budget_filter {
    projects = ["projects/${var.project_number}"]
    # Scope to Cloud Storage (storage + egress SKUs). Empty list = whole project.
    services = var.budget_filter_services
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.budget_amount_usd)
    }
  }

  # Actual-spend alerts at 50% / 90% / 100%, plus an early forecast warning at 100%.
  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.9
  }
  threshold_rules {
    threshold_percent = 1.0
  }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  all_updates_rule {
    monitoring_notification_channels = [for c in google_monitoring_notification_channel.budget_email : c.id]
    # Keep notifying the billing admins too, even if no extra emails are configured.
    disable_default_iam_recipients = false
  }

  depends_on = [google_project_service.enabled]
}
