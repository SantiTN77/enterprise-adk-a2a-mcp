from __future__ import annotations

import pytest

from lib.config import LiveTargets
from lib.oidc_client import OidcHttpClient
from lib.schemas import AgentCard, AnalyzeResponse, assert_no_leaked_secrets
from lib.tf_policy import evaluate_terraform_directory
from lib.ui_runner import run_ui_analyze_workflow

pytestmark = [pytest.mark.tier3, pytest.mark.live_e2e]


def test_t3_pw_01_iam_x_a2a_discovery_unauth_vs_auth(
    live_targets: LiveTargets, oidc_client: OidcHttpClient, agent_oidc_available: bool
) -> None:
    unauth = oidc_client.request_raw("GET", f"{live_targets.financial_agent_url}/.well-known/agent-card.json")
    assert unauth.status_code in {401, 403}
    if not agent_oidc_available:
        pytest.skip("Set E2E_AGENT_IMPERSONATE_SA to verify authenticated agent-card discovery alongside 401/403.")
    auth_resp = oidc_client.request_authenticated(
        "GET", live_targets.financial_agent_url, "/.well-known/agent-card.json", for_specialized_agent=True
    )
    assert auth_resp.status_code == 200
    AgentCard.model_validate(auth_resp.json())


def test_t3_pw_02_iam_x_bff_direct_401_vs_bff_200(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    direct = oidc_client.request_raw("GET", f"{live_targets.orchestrator_url}/api/scenarios")
    assert direct.status_code in {401, 403}

    bff = oidc_client.request_raw(
        "GET", f"{live_targets.web_url}/api/scenarios", headers=live_targets.vercel_headers()
    )
    assert bff.status_code == 200
    assert_no_leaked_secrets(bff.text, context="BFF /api/scenarios pairwise check")


def test_t3_pw_03_a2a_x_financial_mcp_trace_alignment(
    live_targets: LiveTargets, oidc_client: OidcHttpClient, agent_oidc_available: bool
) -> None:
    resp = oidc_client.request_authenticated(
        "POST",
        live_targets.orchestrator_url,
        "/api/analyze",
        json_body={
            "scenario_id": "q3_cloud_vendor_review",
            "doc_id": "samples/q3_cloud_vendor_review.json",
            "prompt": "Analyze financial metrics.",
            "persist_report": False,
        },
        timeout=oidc_client.analyze_timeout,
    )
    assert resp.status_code == 200
    parsed = AnalyzeResponse.model_validate(resp.json())
    fin_steps = [s for s in parsed.a2a_trace if "financial" in s.target.lower()]
    assert fin_steps and len(fin_steps[0].mcp_tools) >= 1

    if agent_oidc_available:
        card = AgentCard.model_validate(
            oidc_client.request_authenticated(
                "GET", live_targets.financial_agent_url, "/.well-known/agent-card.json", for_specialized_agent=True
            ).json()
        )
        assert len(card.skills) >= 1


def test_t3_pw_04_a2a_x_compliance_mcp_trace_alignment(
    live_targets: LiveTargets, oidc_client: OidcHttpClient, agent_oidc_available: bool
) -> None:
    resp = oidc_client.request_authenticated(
        "POST",
        live_targets.orchestrator_url,
        "/api/analyze",
        json_body={
            "scenario_id": "treasury_controls_memo",
            "doc_id": "samples/treasury_controls_memo.json",
            "prompt": "Audit compliance controls.",
            "persist_report": False,
        },
        timeout=oidc_client.analyze_timeout,
    )
    assert resp.status_code == 200
    parsed = AnalyzeResponse.model_validate(resp.json())
    comp_steps = [s for s in parsed.a2a_trace if "compliance" in s.target.lower()]
    assert comp_steps and len(comp_steps[0].mcp_tools) >= 1

    if agent_oidc_available:
        card = AgentCard.model_validate(
            oidc_client.request_authenticated(
                "GET", live_targets.compliance_agent_url, "/.well-known/agent-card.json", for_specialized_agent=True
            ).json()
        )
        assert len(card.skills) >= 1


def test_t3_pw_05_financial_anomalies_correlate_with_compliance_violations(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    resp = oidc_client.request_authenticated(
        "POST",
        live_targets.orchestrator_url,
        "/api/analyze",
        json_body={
            "scenario_id": "q3_cloud_vendor_review",
            "doc_id": "samples/q3_cloud_vendor_review.json",
            "prompt": "Identify financial anomalies and corresponding compliance control breaches.",
            "persist_report": False,
        },
        timeout=oidc_client.analyze_timeout,
    )
    assert resp.status_code == 200
    parsed = AnalyzeResponse.model_validate(resp.json())
    assert len(parsed.financial_analysis.anomalies) > 0 or parsed.compliance_audit.compliant is False
    assert len(parsed.recommendations) > 0


def test_t3_pw_06_orchestrator_vertex_synthesizes_both_agents_and_gcs_report(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    resp = oidc_client.request_authenticated(
        "POST",
        live_targets.orchestrator_url,
        "/api/analyze",
        json_body={
            "scenario_id": "series_b_revenue_audit",
            "doc_id": "samples/series_b_revenue_audit.json",
            "prompt": "Synthesize financial and compliance findings and persist report.",
            "persist_report": True,
        },
        timeout=oidc_client.analyze_timeout,
    )
    assert resp.status_code == 200
    parsed = AnalyzeResponse.model_validate(resp.json())
    assert parsed.gcp_provenance.report_gcs_uri is not None
    assert parsed.gcp_provenance.report_gcs_uri.startswith("gs://")


def test_t3_pw_07_bff_x_web_ui_zero_direct_cloud_run_calls(live_targets: LiveTargets) -> None:
    obs, payload = run_ui_analyze_workflow(
        live_targets.web_url,
        scenario_id="q3_cloud_vendor_review",
        extra_headers=live_targets.vercel_headers(),
    )
    obs.assert_clean_telemetry()
    obs.assert_zero_credential_leakage()
    assert payload is not None
    AnalyzeResponse.model_validate(payload)


def test_t3_pw_08_terraform_zero_idle_matches_live_security_posture(
    live_targets: LiveTargets, oidc_client: OidcHttpClient, repo_root
) -> None:
    tf_report = evaluate_terraform_directory(repo_root / "infra" / "terraform")
    assert tf_report.passed, f"Terraform policy violations: {tf_report.violations}"

    resp = oidc_client.request_authenticated(
        "POST",
        live_targets.orchestrator_url,
        "/api/analyze",
        json_body={
            "scenario_id": "q3_cloud_vendor_review",
            "doc_id": "samples/q3_cloud_vendor_review.json",
            "prompt": "Confirm runtime security posture.",
            "persist_report": False,
        },
        timeout=oidc_client.analyze_timeout,
    )
    assert resp.status_code == 200
    parsed = AnalyzeResponse.model_validate(resp.json())
    assert parsed.security_posture.min_instances == 0
    assert parsed.security_posture.max_instances == 2
    assert parsed.security_posture.cloud_run_iam == "private-oidc-enforced"


def test_t3_pw_09_web_ui_adhoc_document_traverses_bff_to_agents(live_targets: LiveTargets) -> None:
    obs, payload = run_ui_analyze_workflow(
        live_targets.web_url,
        prompt="Audit ad-hoc invoice via Playwright UI.",
        adhoc_document="Emergency hardware purchase $240,000 without dual CFO approval (+40% variance).",
        extra_headers=live_targets.vercel_headers(),
    )
    obs.assert_clean_telemetry()
    assert payload is not None
    parsed = AnalyzeResponse.model_validate(payload)
    assert parsed.compliance_audit.compliant is False
