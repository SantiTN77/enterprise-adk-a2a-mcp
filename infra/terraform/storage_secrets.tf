locals {
  synthetic_dir = "${path.module}/../../data/synthetic"
  sample_files = toset([
    for f in fileset(local.synthetic_dir, "*.json") : f
    if f != "compliance_policy_rules.json"
  ])
}

resource "google_storage_bucket" "docs" {
  project                     = var.project_id
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.bucket_force_destroy

  # Reports written by the public demo are ephemeral: expire them after 30 days so
  # anonymous traffic can never grow storage cost unbounded.
  lifecycle_rule {
    condition {
      age            = 30
      matches_prefix = ["reports/"]
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_object" "samples" {
  for_each = local.sample_files

  name         = "samples/${each.value}"
  bucket       = google_storage_bucket.docs.name
  content      = file("${local.synthetic_dir}/${each.value}")
  content_type = "application/json"
}

resource "google_secret_manager_secret" "compliance_policy_rules" {
  project   = var.project_id
  secret_id = var.compliance_secret_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "compliance_policy_rules_v1" {
  secret      = google_secret_manager_secret.compliance_policy_rules.id
  secret_data = file("${local.synthetic_dir}/compliance_policy_rules.json")
}
