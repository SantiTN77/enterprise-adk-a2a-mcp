from __future__ import annotations

import pytest

from lib.config import LiveTargets
from lib.oidc_client import OidcHttpClient
from lib.schemas import AnalyzeResponse, ScenariosResponse

pytestmark = [pytest.mark.tier1, pytest.mark.live_e2e, pytest.mark.orchestrator]


def test_t1_f5_01_scenarios_catalog_from_gcs(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    resp = oidc_client.request_authenticated("GET", live_targets.orchestrator_url, "/api/scenarios")
    assert resp.status_code == 200, resp.text
    parsed = ScenariosResponse.model_validate(resp.json())
    ids = {s.id for s in parsed.scenarios}
    expected = {"q3_cloud_vendor_review", "series_b_revenue_audit", "treasury_controls_memo"}
    assert expected.issubset(ids), f"Missing required scenarios {expected - ids} in {ids}"


def test_t1_f5_02_analyze_response_strict_schema(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    resp = oidc_client.request_authenticated(
        "POST",
        live_targets.orchestrator_url,
        "/api/analyze",
        json_body={
            "scenario_id": "q3_cloud_vendor_review",
            "doc_id": "samples/q3_cloud_vendor_review.json",
            "prompt": "Provide structured financial and compliance analysis.",
            "persist_report": True,
        },
        timeout=oidc_client.analyze_timeout,
    )
    assert resp.status_code == 200, resp.text
    AnalyzeResponse.model_validate(resp.json())


def test_t1_f5_03_vertex_ai_gemini_3_8_global_provenance(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    resp = oidc_client.request_authenticated(
        "POST",
        live_targets.orchestrator_url,
        "/api/analyze",
        json_body={
            "scenario_id": "series_b_revenue_audit",
            "doc_id": "samples/series_b_revenue_audit.json",
            "prompt": "Summarize Series B revenue audit.",
            "persist_report": False,
        },
        timeout=oidc_client.analyze_timeout,
    )
    assert resp.status_code == 200, resp.text
    parsed = AnalyzeResponse.model_validate(resp.json())
    assert parsed.gcp_provenance.vertex_ai_model in {"gemini-3.8-flash", "gemini-3.5-flash-lite"}
    assert parsed.gcp_provenance.vertex_ai_location == "global"


def test_t1_f5_04_security_posture_zero_idle_private_oidc(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    resp = oidc_client.request_authenticated(
        "POST",
        live_targets.orchestrator_url,
        "/api/analyze",
        json_body={
            "scenario_id": "q3_cloud_vendor_review",
            "doc_id": "samples/q3_cloud_vendor_review.json",
            "prompt": "Verify security posture metadata.",
            "persist_report": False,
        },
        timeout=oidc_client.analyze_timeout,
    )
    assert resp.status_code == 200, resp.text
    parsed = AnalyzeResponse.model_validate(resp.json())
    assert parsed.security_posture.cloud_run_iam == "private-oidc-enforced"
    assert parsed.security_posture.min_instances == 0
    assert parsed.security_posture.max_instances == 2


def test_t1_f5_05_persist_report_creates_gcs_uri(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    resp = oidc_client.request_authenticated(
        "POST",
        live_targets.orchestrator_url,
        "/api/analyze",
        json_body={
            "scenario_id": "q3_cloud_vendor_review",
            "doc_id": "samples/q3_cloud_vendor_review.json",
            "prompt": "Analyze Q3 vendor spend and persist report to GCS.",
            "persist_report": True,
        },
        timeout=oidc_client.analyze_timeout,
    )
    assert resp.status_code == 200, resp.text
    parsed = AnalyzeResponse.model_validate(resp.json())
    uri = parsed.gcp_provenance.report_gcs_uri
    assert uri is not None and uri.startswith("gs://") and "/reports/" in uri, (
        f"Expected gs://.../reports/... URI when persist_report=True, got {uri!r}"
    )


def test_t1_f5_06_unique_run_ids_and_positive_trace_latency(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    payload = {
        "scenario_id": "q3_cloud_vendor_review",
        "doc_id": "samples/q3_cloud_vendor_review.json",
        "prompt": "Run variance check.",
        "persist_report": False,
    }
    r1 = AnalyzeResponse.model_validate(
        oidc_client.request_authenticated(
            "POST", live_targets.orchestrator_url, "/api/analyze", json_body=payload, timeout=oidc_client.analyze_timeout
        ).json()
    )
    r2 = AnalyzeResponse.model_validate(
        oidc_client.request_authenticated(
            "POST", live_targets.orchestrator_url, "/api/analyze", json_body=payload, timeout=oidc_client.analyze_timeout
        ).json()
    )
    assert r1.run_id != r2.run_id
    assert all(step.latency_ms > 0 for step in r1.a2a_trace)
