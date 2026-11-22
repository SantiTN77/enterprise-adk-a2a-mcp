from __future__ import annotations

import pytest

from lib.config import LiveTargets
from lib.oidc_client import OidcHttpClient
from lib.schemas import AnalyzeResponse

pytestmark = [pytest.mark.tier1, pytest.mark.live_e2e, pytest.mark.compliance]


@pytest.fixture(scope="module")
def treasury_analysis(live_targets: LiveTargets, oidc_client: OidcHttpClient) -> AnalyzeResponse:
    resp = oidc_client.request_authenticated(
        "POST",
        live_targets.orchestrator_url,
        "/api/analyze",
        json_body={
            "scenario_id": "treasury_controls_memo",
            "doc_id": "samples/treasury_controls_memo.json",
            "prompt": "Evaluate treasury dual-approval controls and policy violations against Secret Manager rules.",
            "persist_report": True,
        },
        timeout=oidc_client.analyze_timeout,
    )
    assert resp.status_code == 200, f"/api/analyze failed: {resp.status_code} {resp.text[:400]}"
    return AnalyzeResponse.model_validate(resp.json())


def test_t1_f4_01_a2a_trace_contains_compliance_delegation(treasury_analysis: AnalyzeResponse) -> None:
    comp_steps = [s for s in treasury_analysis.a2a_trace if "compliance" in s.target.lower()]
    assert comp_steps, f"No compliance agent step in a2a_trace: {treasury_analysis.a2a_trace}"
    assert any(s.status.upper() == "SUCCESS" for s in comp_steps)
    assert all(s.protocol == "A2A" and s.auth == "CloudRun-OIDC-IAM" for s in comp_steps)


def test_t1_f4_02_compliance_mcp_tools_recorded_in_trace(treasury_analysis: AnalyzeResponse) -> None:
    comp_steps = [s for s in treasury_analysis.a2a_trace if "compliance" in s.target.lower()]
    tools = {t.lower() for t in comp_steps[0].mcp_tools}
    assert tools, "Compliance A2A step reported zero mcp_tools"
    assert any("policy" in t or "secret" in t or "control" in t or "matrix" in t for t in tools), (
        f"Expected Secret Manager policy / control matrix MCP tools in {tools}"
    )


def test_t1_f4_03_compliance_audit_schema_populated(treasury_analysis: AnalyzeResponse) -> None:
    ca = treasury_analysis.compliance_audit
    assert len(ca.summary.strip()) > 10
    assert ca.policy_id == "adk-compliance-policy-rules"
    assert len(ca.controls_evaluated) > 0, "controls_evaluated must be non-empty"


def test_t1_f4_04_secret_manager_policy_provenance(treasury_analysis: AnalyzeResponse) -> None:
    assert treasury_analysis.gcp_provenance.secret_manager_policy == "adk-compliance-policy-rules"


def test_t1_f4_05_policy_violation_detected_on_breach_input(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    resp = oidc_client.request_authenticated(
        "POST",
        live_targets.orchestrator_url,
        "/api/analyze",
        json_body={
            "scenario_id": "adhoc",
            "prompt": "Audit this unapproved expenditure against corporate compliance controls.",
            "document_text": (
                "EMERGENCY WIRE TRANSFER: $480,000 sole-source vendor payment executed without "
                "competitive bids, without VP approval, and without CFO dual sign-off. "
                "Budget variance is +62% over approved threshold."
            ),
            "persist_report": False,
        },
        timeout=oidc_client.analyze_timeout,
    )
    assert resp.status_code == 200, resp.text
    parsed = AnalyzeResponse.model_validate(resp.json())
    assert parsed.compliance_audit.compliant is False
    assert len(parsed.compliance_audit.violations) > 0
    assert parsed.overall_risk_rating in {"HIGH", "CRITICAL"}
