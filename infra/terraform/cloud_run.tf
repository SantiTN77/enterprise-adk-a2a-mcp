locals {
  financial_agent_host  = "adk-financial-agent-${data.google_project.current.number}.${var.region}.run.app"
  compliance_agent_host = "adk-compliance-agent-${data.google_project.current.number}.${var.region}.run.app"
  orchestrator_host     = "adk-orchestrator-${data.google_project.current.number}.${var.region}.run.app"
}

resource "google_cloud_run_v2_service" "financial_agent" {
  project             = var.project_id
  name                = "adk-financial-agent"
  location            = var.region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.financial_agent.email
    timeout         = "300s"

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.financial_agent_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      startup_probe {
        initial_delay_seconds = 5
        timeout_seconds       = 3
        period_seconds        = 5
        failure_threshold     = 6
        http_get {
          path = "/health"
          port = 8080
        }
      }

      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "TRUE"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.vertex_ai_location
      }
      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.docs.name
      }
      env {
        name  = "PUBLIC_HOST"
        value = local.financial_agent_host
      }
      env {
        name  = "PUBLIC_PORT"
        value = "443"
      }
      env {
        name  = "PUBLIC_PROTOCOL"
        value = "https"
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service" "compliance_agent" {
  project             = var.project_id
  name                = "adk-compliance-agent"
  location            = var.region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.compliance_agent.email
    timeout         = "300s"

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.compliance_agent_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      startup_probe {
        initial_delay_seconds = 5
        timeout_seconds       = 3
        period_seconds        = 5
        failure_threshold     = 6
        http_get {
          path = "/health"
          port = 8080
        }
      }

      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "TRUE"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.vertex_ai_location
      }
      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.docs.name
      }
      env {
        name  = "COMPLIANCE_SECRET_ID"
        value = google_secret_manager_secret.compliance_policy_rules.secret_id
      }
      env {
        name  = "PUBLIC_HOST"
        value = local.compliance_agent_host
      }
      env {
        name  = "PUBLIC_PORT"
        value = "443"
      }
      env {
        name  = "PUBLIC_PROTOCOL"
        value = "https"
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service" "orchestrator" {
  project             = var.project_id
  name                = "adk-orchestrator"
  location            = var.region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.orchestrator.email
    timeout         = "300s"

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.orchestrator_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      startup_probe {
        initial_delay_seconds = 5
        timeout_seconds       = 3
        period_seconds        = 5
        failure_threshold     = 6
        http_get {
          path = "/health"
          port = 8080
        }
      }

      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "TRUE"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.vertex_ai_location
      }
      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.docs.name
      }
      env {
        name  = "COMPLIANCE_SECRET_ID"
        value = google_secret_manager_secret.compliance_policy_rules.secret_id
      }
      env {
        name  = "FINANCIAL_AGENT_URL"
        value = "https://${local.financial_agent_host}"
      }
      env {
        name  = "COMPLIANCE_AGENT_URL"
        value = "https://${local.compliance_agent_host}"
      }
      env {
        name  = "ENABLE_CLOUD_RUN_OIDC"
        value = "true"
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_cloud_run_v2_service.financial_agent,
    google_cloud_run_v2_service.compliance_agent,
  ]
}
