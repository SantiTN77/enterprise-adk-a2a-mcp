from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from lib.config import LiveTargets
from lib.oidc_client import OidcHttpClient
from lib.schemas import AnalyzeResponse, assert_no_leaked_secrets
from lib.ui_runner import run_ui_analyze_workflow

pytestmark = [pytest.mark.tier4, pytest.mark.live_e2e]


def test_t4_sc_01_q3_cloud_vendor_spend_review_browser_e2e(live_targets: LiveTargets) -> None:
    obs, payload = run_ui_analyze_workflow(
        live_targets.web_url,
        scenario_id="q3_cloud_vendor_review",
        extra_headers=live_targets.vercel_headers(),
    )
    obs.assert_clean_telemetry()
    obs.assert_zero_credential_leakage()
    assert payload is not None
    parsed = AnalyzeResponse.model_validate(payload)
    assert parsed.gcp_provenance.report_gcs_uri is not None
    assert parsed.gcp_provenance.vertex_ai_location == "global"


def test_t4_sc_02_series_b_revenue_audit_bff_and_provenance(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    resp = oidc_client.request_raw(
        "POST",
        f"{live_targets.web_url}/api/analyze",
        headers=live_targets.vercel_headers(),
        json_body={
            "scenario_id": "series_b_revenue_audit",
            "doc_id": "samples/series_b_revenue_audit.json",
            "prompt": "Audit Series B ARR recognition, gross margin ratios, and Secret Manager policy compliance.",
            "persist_report": True,
        },
        timeout=oidc_client.analyze_timeout,
    )
    assert resp.status_code == 200, resp.text
    assert_no_leaked_secrets(resp.text, context="Series B audit response")
    parsed = AnalyzeResponse.model_validate(resp.json())
    assert any("series_b_revenue_audit" in s for s in parsed.financial_analysis.sources)
    assert parsed.gcp_provenance.secret_manager_policy == "adk-compliance-policy-rules"


def test_t4_sc_03_treasury_controls_memo_violation_in_chrome(live_targets: LiveTargets) -> None:
    obs, payload = run_ui_analyze_workflow(
        live_targets.web_url,
        scenario_id="treasury_controls_memo",
        extra_headers=live_targets.vercel_headers(),
    )
    obs.assert_clean_telemetry()
    assert payload is not None
    parsed = AnalyzeResponse.model_validate(payload)
    assert len(parsed.recommendations) > 0
    assert len(parsed.a2a_trace) >= 2


def test_t4_sc_04_adhoc_clean_enterprise_procurement_memo(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    resp = oidc_client.request_raw(
        "POST",
        f"{live_targets.web_url}/api/analyze",
        headers=live_targets.vercel_headers(),
        json_body={
            "scenario_id": "adhoc",
            "prompt": "Evaluate compliant enterprise procurement memo.",
            "document_text": (
                "Q4 Security Tooling Renewal: Approved budget $80,000; actual contract $79,200 (-1.0% variance). "
                "Three competitive vendor bids evaluated. Dual written sign-off by VP Security and CFO."
            ),
            "persist_report": False,
        },
        timeout=oidc_client.analyze_timeout,
    )
    assert resp.status_code == 200, resp.text
    parsed = AnalyzeResponse.model_validate(resp.json())
    assert parsed.compliance_audit.compliant is True
    assert parsed.compliance_audit.violations == []
    assert parsed.overall_risk_rating in {"LOW", "MEDIUM"}


def test_t4_sc_05_concurrent_bff_requests_and_high_risk_expenditure(
    live_targets: LiveTargets,
) -> None:
    payloads = [
        {
            "scenario_id": "adhoc",
            "prompt": "Audit high-risk sole-source expenditure.",
            "document_text": (
                "Unapproved $480,000 sole-source AI cluster invoice with +62% budget variance, "
                "zero competitive bids, and missing CFO dual approval."
            ),
            "persist_report": False,
        },
        {
            "scenario_id": "q3_cloud_vendor_review",
            "doc_id": "samples/q3_cloud_vendor_review.json",
            "prompt": "Audit Q3 vendor spend concurrently.",
            "persist_report": False,
        },
    ]

    def _call(body: dict) -> AnalyzeResponse:
        client = OidcHttpClient()
        try:
            resp = client.request_raw(
                "POST",
                f"{live_targets.web_url}/api/analyze",
                headers=live_targets.vercel_headers(),
                json_body=body,
                timeout=client.analyze_timeout,
            )
            assert resp.status_code == 200, f"Concurrent BFF failed: {resp.status_code} {resp.text[:300]}"
            return AnalyzeResponse.model_validate(resp.json())
        finally:
            client.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_call, payloads))

    high_risk, q3_res = results[0], results[1]
    assert high_risk.run_id != q3_res.run_id
    assert high_risk.compliance_audit.compliant is False
    assert high_risk.overall_risk_rating in {"HIGH", "CRITICAL"}
    assert len(high_risk.recommendations) > 0


def test_t4_sc_06_security_auditor_lockdown_and_zero_leakage(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    for svc_url, path in (
        (live_targets.orchestrator_url, "/api/scenarios"),
        (live_targets.financial_agent_url, "/.well-known/agent-card.json"),
        (live_targets.compliance_agent_url, "/.well-known/agent-card.json"),
    ):
        probe = oidc_client.request_raw("GET", f"{svc_url}{path}")
        assert probe.status_code in {401, 403}, (
            f"Lockdown breach: unauth {svc_url}{path} returned {probe.status_code}"
        )

    obs, payload = run_ui_analyze_workflow(
        live_targets.web_url,
        scenario_id="q3_cloud_vendor_review",
        extra_headers=live_targets.vercel_headers(),
    )
    obs.assert_clean_telemetry()
    obs.assert_zero_credential_leakage()
    assert payload is not None
    AnalyzeResponse.model_validate(payload)
