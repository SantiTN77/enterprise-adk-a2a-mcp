import json
import re
from pathlib import Path

import hcl2
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TF_DIR = REPO_ROOT / "infra" / "terraform"
SYNTHETIC_DIR = REPO_ROOT / "data" / "synthetic"


def _normalize_hcl(obj):
    if isinstance(obj, str):
        if len(obj) >= 2 and obj[0] == '"' and obj[-1] == '"':
            return obj[1:-1]
        return obj
    if isinstance(obj, list):
        return [_normalize_hcl(item) for item in obj]
    if isinstance(obj, dict):
        return {_normalize_hcl(k): _normalize_hcl(v) for k, v in obj.items() if k != "__is_block__"}
    return obj


def load_terraform_ast() -> dict:
    merged: dict = {}
    tf_files = sorted(TF_DIR.glob("*.tf"))
    assert tf_files, f"No .tf files found in {TF_DIR}"
    for tf_file in tf_files:
        with tf_file.open("r", encoding="utf-8") as fh:
            parsed = _normalize_hcl(hcl2.load(fh))
        for key, value in parsed.items():
            if isinstance(value, list):
                merged.setdefault(key, []).extend(value)
            else:
                merged[key] = value
    return merged


def _resource_map(ast: dict, resource_type: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for block in ast.get("resource", []):
        if resource_type in block:
            for name, attrs in block[resource_type].items():
                result[name] = attrs
    return result


def _contains_public_principal(obj) -> bool:
    if isinstance(obj, str):
        return "allUsers" in obj or "allAuthenticatedUsers" in obj
    if isinstance(obj, list):
        return any(_contains_public_principal(item) for item in obj)
    if isinstance(obj, dict):
        return any(_contains_public_principal(v) for v in obj.values())
    return False


def test_terraform_provider_pins():
    ast = load_terraform_ast()
    tf_blocks = ast.get("terraform", [])
    assert tf_blocks, "Missing terraform {} configuration block"
    providers = tf_blocks[0].get("required_providers", [])
    assert providers and "google" in providers[0], "Missing google required_provider"
    assert "~> 6.0" in providers[0]["google"]["version"]


def test_service_accounts_and_no_static_keys():
    ast = load_terraform_ast()
    sas = _resource_map(ast, "google_service_account")
    expected_account_ids = {
        "adk-orchestrator",
        "adk-financial-agent",
        "adk-compliance-agent",
        "vercel-bff-invoker",
    }
    actual_account_ids = {attrs["account_id"] for attrs in sas.values()}
    assert actual_account_ids == expected_account_ids

    sa_keys = _resource_map(ast, "google_service_account_key")
    assert len(sa_keys) == 0, "google_service_account_key must NEVER exist in Terraform"


def test_cloud_run_zero_idle_cost_and_required_env():
    ast = load_terraform_ast()
    services = _resource_map(ast, "google_cloud_run_v2_service")
    assert set(services.keys()) == {"financial_agent", "compliance_agent", "orchestrator"}

    expected_names = {
        "financial_agent": "adk-financial-agent",
        "compliance_agent": "adk-compliance-agent",
        "orchestrator": "adk-orchestrator",
    }

    for res_key, attrs in services.items():
        assert attrs["name"] == expected_names[res_key]
        assert attrs["deletion_protection"] is False
        assert attrs["ingress"] == "INGRESS_TRAFFIC_ALL"
        assert attrs.get("invoker_iam_disabled", False) is False

        tmpl = attrs["template"][0]
        scaling = tmpl["scaling"][0]
        assert scaling["min_instance_count"] == 0
        assert 1 <= scaling["max_instance_count"] <= 2

        container = tmpl["containers"][0]
        resources = container["resources"][0]
        assert resources["cpu_idle"] is True
        assert resources["startup_cpu_boost"] is True

        probe = container["startup_probe"][0]["http_get"][0]
        assert probe["path"] == "/healthz"
        assert probe["port"] == 8080

        env_map = {e["name"]: e["value"] for e in container["env"]}
        assert env_map["GOOGLE_GENAI_USE_VERTEXAI"] == "TRUE"
        assert "GOOGLE_CLOUD_PROJECT" in env_map
        assert "GOOGLE_CLOUD_LOCATION" in env_map
        assert "GEMINI_MODEL" in env_map
        assert "GCS_BUCKET_NAME" in env_map

        if res_key in {"financial_agent", "compliance_agent"}:
            assert "PUBLIC_HOST" in env_map
            assert env_map["PUBLIC_PORT"] == "443"
            assert env_map["PUBLIC_PROTOCOL"] == "https"
        if res_key == "compliance_agent":
            assert "COMPLIANCE_SECRET_ID" in env_map
        if res_key == "orchestrator":
            assert "FINANCIAL_AGENT_URL" in env_map
            assert "COMPLIANCE_AGENT_URL" in env_map
            assert "COMPLIANCE_SECRET_ID" in env_map
            assert env_map["ENABLE_CLOUD_RUN_OIDC"] == "true"


def test_zero_public_iam_exposure_and_exact_invoker_graph():
    ast = load_terraform_ast()
    iam_resource_types = [
        "google_cloud_run_v2_service_iam_member",
        "google_cloud_run_v2_service_iam_binding",
        "google_cloud_run_v2_service_iam_policy",
        "google_cloud_run_service_iam_member",
        "google_cloud_run_service_iam_binding",
        "google_cloud_run_service_iam_policy",
        "google_storage_bucket_iam_member",
        "google_storage_bucket_iam_binding",
        "google_storage_bucket_iam_policy",
        "google_secret_manager_secret_iam_member",
        "google_secret_manager_secret_iam_binding",
        "google_secret_manager_secret_iam_policy",
        "google_project_iam_member",
        "google_project_iam_binding",
        "google_project_iam_policy",
    ]
    for rtype in iam_resource_types:
        resources = _resource_map(ast, rtype)
        assert not _contains_public_principal(resources), f"Public principal found in {rtype}"

    run_invokers = _resource_map(ast, "google_cloud_run_v2_service_iam_member")
    edges = {
        (attrs["member"], attrs["name"], attrs["role"])
        for attrs in run_invokers.values()
    }
    expected_edges = {
        (
            "serviceAccount:${google_service_account.vercel_bff.email}",
            "${google_cloud_run_v2_service.orchestrator.name}",
            "roles/run.invoker",
        ),
        (
            "serviceAccount:${google_service_account.orchestrator.email}",
            "${google_cloud_run_v2_service.financial_agent.name}",
            "roles/run.invoker",
        ),
        (
            "serviceAccount:${google_service_account.orchestrator.email}",
            "${google_cloud_run_v2_service.compliance_agent.name}",
            "roles/run.invoker",
        ),
    }
    assert edges == expected_edges

    secret_iam = _resource_map(ast, "google_secret_manager_secret_iam_member")
    assert len(secret_iam) == 1
    only_secret_binding = next(iter(secret_iam.values()))
    assert only_secret_binding["role"] == "roles/secretmanager.secretAccessor"
    assert only_secret_binding["member"] == "serviceAccount:${google_service_account.compliance_agent.email}"

    proj_iam = _resource_map(ast, "google_project_iam_member")
    for attrs in proj_iam.values():
        assert attrs["role"] in {"roles/aiplatform.user", "roles/logging.logWriter"}
        assert "vercel_bff" not in attrs["member"]


def test_bucket_hardening_and_sample_seeding_filter():
    ast = load_terraform_ast()
    buckets = _resource_map(ast, "google_storage_bucket")
    assert "docs" in buckets
    docs_bucket = buckets["docs"]
    assert docs_bucket["uniform_bucket_level_access"] is True
    assert docs_bucket["public_access_prevention"] == "enforced"

    objects = _resource_map(ast, "google_storage_bucket_object")
    assert "samples" in objects
    assert "compliance_policy_rules.json" not in objects["samples"]["name"]
    locals_merged = {}
    for loc in ast.get("locals", []):
        locals_merged.update(loc)
    assert "compliance_policy_rules.json" in str(locals_merged.get("sample_files", ""))

    # Ensure Secret Manager seeds compliance_policy_rules.json
    secret_versions = _resource_map(ast, "google_secret_manager_secret_version")
    assert "compliance_policy_rules_v1" in secret_versions
    assert "compliance_policy_rules.json" in secret_versions["compliance_policy_rules_v1"]["secret_data"]


def test_synthetic_data_schemas_and_arithmetic_reconciliation():
    policy_path = SYNTHETIC_DIR / "compliance_policy_rules.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    assert policy["policy_id"] == "ENT-COMP-POLICY-2026.3"
    control_ids = {c["control_id"] for c in policy["controls"]}
    assert control_ids == {"FIN-VAR-01", "SOX-APPR-02", "SOC2-VEND-03", "TRES-SOD-04", "SOX-REV-05"}

    scenario_files = [
        "series_b_revenue_audit.json",
        "q3_cloud_vendor_review.json",
        "treasury_controls_memo.json",
    ]
    for fname in scenario_files:
        raw = (SYNTHETIC_DIR / fname).read_text(encoding="utf-8")
        assert not re.search(r"BEGIN .*PRIVATE KEY|AIza[0-9A-Za-z\-_]{35}|ghp_|github_pat_|@gmail\.com|\b\d{3}-\d{2}-\d{4}\b", raw)
        doc = json.loads(raw)
        fs = doc["financial_summary"]

        assert doc["doc_id"] == f"samples/{fname}"
        assert round(sum(x["budgeted_usd"] for x in doc["line_items"]), 2) == fs["budgeted_spend_usd"]
        assert round(sum(x["actual_usd"] for x in doc["line_items"]), 2) == fs["actual_spend_usd"]
        assert round(fs["actual_spend_usd"] + fs["other_operating_expenses_usd"], 2) == fs["operating_expenses_usd"]
        assert round(sum(x["recognized_usd"] for x in doc["revenue_recognition_items"]), 2) == fs["revenue_usd"]
        expected_var_pct = round((fs["actual_spend_usd"] - fs["budgeted_spend_usd"]) / fs["budgeted_spend_usd"] * 100.0, 2)
        assert expected_var_pct == fs["budget_variance_pct"]
