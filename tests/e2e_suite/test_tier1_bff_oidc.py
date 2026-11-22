from __future__ import annotations

import re

import pytest

from lib.config import LiveTargets
from lib.oidc_client import OidcHttpClient
from lib.schemas import AnalyzeResponse, ScenariosResponse, assert_no_leaked_secrets

pytestmark = [pytest.mark.tier1, pytest.mark.live_e2e, pytest.mark.bff]


def test_t1_f6_01_bff_health_succeeds_without_browser_creds(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    resp = oidc_client.request_raw(
        "GET",
        f"{live_targets.web_url}/api/health",
        headers=live_targets.vercel_headers(),
    )
    assert resp.status_code == 200, f"BFF /api/health failed: {resp.status_code} {resp.text[:300]}"
    assert_no_leaked_secrets(resp.text, context="BFF /api/health")


def test_t1_f6_02_bff_scenarios_matches_orchestrator(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    bff_resp = oidc_client.request_raw(
        "GET",
        f"{live_targets.web_url}/api/scenarios",
        headers=live_targets.vercel_headers(),
    )
    assert bff_resp.status_code == 200, bff_resp.text
    bff_scenarios = ScenariosResponse.model_validate(bff_resp.json())

    orch_resp = oidc_client.request_authenticated("GET", live_targets.orchestrator_url, "/api/scenarios")
    assert orch_resp.status_code == 200, orch_resp.text
    orch_scenarios = ScenariosResponse.model_validate(orch_resp.json())

    assert {s.id for s in bff_scenarios.scenarios} == {s.id for s in orch_scenarios.scenarios}


def test_t1_f6_03_bff_analyze_proxies_via_server_oidc(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    resp = oidc_client.request_raw(
        "POST",
        f"{live_targets.web_url}/api/analyze",
        headers=live_targets.vercel_headers(),
        json_body={
            "scenario_id": "q3_cloud_vendor_review",
            "doc_id": "samples/q3_cloud_vendor_review.json",
            "prompt": "Analyze financial variance and audit compliance controls for Q3 vendor spend.",
            "persist_report": True,
        },
        timeout=oidc_client.analyze_timeout,
    )
    assert resp.status_code == 200, f"BFF /api/analyze failed: {resp.status_code} {resp.text[:400]}"
    AnalyzeResponse.model_validate(resp.json())


def test_t1_f6_04_bff_responses_leak_zero_secrets_or_tokens(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    for path in ("/api/health", "/api/scenarios"):
        resp = oidc_client.request_raw(
            "GET",
            f"{live_targets.web_url}{path}",
            headers=live_targets.vercel_headers(),
        )
        assert_no_leaked_secrets(resp.text, context=f"BFF {path} body")
        headers_dump = "\n".join(f"{k}: {v}" for k, v in resp.headers.items())
        assert_no_leaked_secrets(headers_dump, context=f"BFF {path} headers")
        assert "authorization" not in {k.lower() for k in resp.headers}


def test_t1_f6_05_html_and_static_bundles_contain_zero_gcp_secrets(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    html_resp = oidc_client.request_raw(
        "GET",
        live_targets.web_url,
        headers=live_targets.vercel_headers(),
    )
    assert html_resp.status_code == 200
    assert_no_leaked_secrets(html_resp.text, context="BFF root HTML")
    assert ".iam.gserviceaccount.com" not in html_resp.text

    script_srcs = re.findall(r'src=["\']([^"\']*?/_next/static/[^"\']+\.js)["\']', html_resp.text)
    for src in script_srcs[:10]:
        full_url = src if src.startswith("http") else f"{live_targets.web_url}{src}"
        js_resp = oidc_client.request_raw("GET", full_url, headers=live_targets.vercel_headers())
        if js_resp.status_code == 200:
            assert_no_leaked_secrets(js_resp.text, context=f"Client JS bundle {src}")
            assert ".iam.gserviceaccount.com" not in js_resp.text
