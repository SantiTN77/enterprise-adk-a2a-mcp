from __future__ import annotations

import pytest

from lib.config import LiveTargets
from lib.oidc_client import OidcHttpClient
from lib.schemas import AnalyzeResponse

pytestmark = [pytest.mark.tier1, pytest.mark.live_e2e, pytest.mark.financial]


@pytest.fixture(scope="module")
def q3_analysis(live_targets: LiveTargets, oidc_client: OidcHttpClient) -> AnalyzeResponse:
    resp = oidc_client.request_authenticated(
        "POST",
        live_targets.orchestrator_url,
        "/api/analyze",
        json_body={
            "scenario_id": "q3_cloud_vendor_review",
            "doc_id": "samples/q3_cloud_vendor_review.json",
            "prompt": "Analyze financial variance, unit ratios, and anomalies for Q3 cloud vendor spend.",
            "persist_report": True,
        },
        timeout=oidc_client.analyze_timeout,
    )
    assert resp.status_code == 200, f"/api/analyze failed: {resp.status_code} {resp.text[:400]}"
    return AnalyzeResponse.model_validate(resp.json())


def test_t1_f3_01_a2a_trace_contains_financial_delegation(q3_analysis: AnalyzeResponse) -> None:
    fin_steps = [s for s in q3_analysis.a2a_trace if "financial" in s.target.lower()]
    assert fin_steps, f"No financial agent step in a2a_trace: {q3_analysis.a2a_trace}"
    assert any(s.status.upper() == "SUCCESS" for s in fin_steps)
    assert all(s.protocol == "A2A" and s.auth == "CloudRun-OIDC-IAM" for s in fin_steps)


def test_t1_f3_02_financial_mcp_tools_recorded_in_trace(q3_analysis: AnalyzeResponse) -> None:
    fin_steps = [s for s in q3_analysis.a2a_trace if "financial" in s.target.lower()]
    tools = {t.lower() for t in fin_steps[0].mcp_tools}
    assert tools, "Financial A2A step reported zero mcp_tools"
    assert any("document" in t or "read" in t or "list" in t for t in tools), (
        f"Expected GCS document MCP tool in {tools}"
    )
    assert any("ratio" in t or "metric" in t or "variance" in t or "financial" in t for t in tools), (
        f"Expected financial ratio/metric MCP tool in {tools}"
    )


def test_t1_f3_03_financial_analysis_structured_output(q3_analysis: AnalyzeResponse) -> None:
    fa = q3_analysis.financial_analysis
    assert len(fa.summary.strip()) > 10
    assert isinstance(fa.key_metrics, dict) and len(fa.key_metrics) > 0
    assert any("q3_cloud_vendor_review" in src for src in fa.sources), (
        f"Expected GCS source reference to q3_cloud_vendor_review in {fa.sources}"
    )


def test_t1_f3_04_distinct_gcs_document_produces_distinct_metrics(
    live_targets: LiveTargets, oidc_client: OidcHttpClient, q3_analysis: AnalyzeResponse
) -> None:
    resp = oidc_client.request_authenticated(
        "POST",
        live_targets.orchestrator_url,
        "/api/analyze",
        json_body={
            "scenario_id": "series_b_revenue_audit",
            "doc_id": "samples/series_b_revenue_audit.json",
            "prompt": "Compute Series B revenue growth ratios and verify GCS source evidence.",
            "persist_report": False,
        },
        timeout=oidc_client.analyze_timeout,
    )
    assert resp.status_code == 200, resp.text
    rev = AnalyzeResponse.model_validate(resp.json())
    assert any("series_b_revenue_audit" in src for src in rev.financial_analysis.sources), (
        f"Expected series_b_revenue_audit in sources: {rev.financial_analysis.sources}"
    )
    assert rev.financial_analysis.key_metrics != q3_analysis.financial_analysis.key_metrics or (
        rev.financial_analysis.summary != q3_analysis.financial_analysis.summary
    )


def test_t1_f3_05_deterministic_variance_computation(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    # Ad-hoc numeric input with exact 50% overrun ($100,000 budget vs $150,000 actual)
    resp = oidc_client.request_authenticated(
        "POST",
        live_targets.orchestrator_url,
        "/api/analyze",
        json_body={
            "scenario_id": "adhoc",
            "prompt": "Compute exact budget variance and financial ratios from the provided memo.",
            "document_text": (
                "Q4 Infrastructure Memo: Approved budget = $100,000. Actual spend = $150,000. "
                "Variance = +$50,000 (+50.0%). Dual CFO sign-off obtained."
            ),
            "persist_report": False,
        },
        timeout=oidc_client.analyze_timeout,
    )
    assert resp.status_code == 200, resp.text
    parsed = AnalyzeResponse.model_validate(resp.json())
    assert len(parsed.financial_analysis.key_metrics) > 0
    combined = f"{parsed.financial_analysis.summary} {parsed.financial_analysis.key_metrics}".lower()
    assert "50" in combined or "150" in combined, (
        f"Expected deterministic variance/spend numbers reflected in financial output: {combined[:300]}"
    )
