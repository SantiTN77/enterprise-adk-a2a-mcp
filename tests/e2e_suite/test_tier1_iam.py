from __future__ import annotations

import os
import pytest

from lib.config import LiveTargets
from lib.oidc_client import OidcHttpClient, OidcTokenMinter

pytestmark = [pytest.mark.tier1, pytest.mark.live_e2e, pytest.mark.iam]


def test_t1_f1_01_orchestrator_unauth_healthz_rejected(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    resp = oidc_client.request_raw("GET", f"{live_targets.orchestrator_url}/healthz")
    assert resp.status_code in {401, 403}, (
        f"Expected 401/403 on unauthenticated orchestrator /healthz, got {resp.status_code}"
    )


def test_t1_f1_02_orchestrator_unauth_analyze_rejected(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    resp = oidc_client.request_raw(
        "POST",
        f"{live_targets.orchestrator_url}/api/analyze",
        json_body={
            "scenario_id": "q3_cloud_vendor_review",
            "doc_id": "samples/q3_cloud_vendor_review.json",
            "prompt": "Unauth IAM probe",
        },
    )
    assert resp.status_code in {401, 403}, (
        f"Expected 401/403 on unauthenticated POST /api/analyze, got {resp.status_code}"
    )


def test_t1_f1_03_financial_agent_unauth_rejected(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    for path in ("/healthz", "/.well-known/agent-card.json"):
        resp = oidc_client.request_raw("GET", f"{live_targets.financial_agent_url}{path}")
        assert resp.status_code in {401, 403}, (
            f"Expected 401/403 on unauthenticated financial_agent {path}, got {resp.status_code}"
        )


def test_t1_f1_04_compliance_agent_unauth_rejected(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    for path in ("/healthz", "/.well-known/agent-card.json"):
        resp = oidc_client.request_raw("GET", f"{live_targets.compliance_agent_url}{path}")
        assert resp.status_code in {401, 403}, (
            f"Expected 401/403 on unauthenticated compliance_agent {path}, got {resp.status_code}"
        )


def test_t1_f1_05_orchestrator_valid_oidc_healthz_succeeds(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    resp = oidc_client.request_authenticated("GET", live_targets.orchestrator_url, "/healthz")
    assert resp.status_code == 200, (
        f"Expected 200 with valid OIDC ID token on orchestrator /healthz, got {resp.status_code}: {resp.text[:300]}"
    )


def test_t1_f1_06_bff_sa_rejected_by_specialized_agents(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    bff_sa_json = os.environ.get("E2E_BFF_SA_KEY_JSON", "").strip()
    if not bff_sa_json:
        if live_targets.strict_live:
            pytest.fail("E2E_STRICT_LIVE=1 requires E2E_BFF_SA_KEY_JSON for cross-SA 403 verification.")
        pytest.skip("E2E_BFF_SA_KEY_JSON not set; skipping cross-SA least-privilege probe.")

    bff_minter = OidcTokenMinter(sa_key_json=bff_sa_json)
    for agent_url in (live_targets.financial_agent_url, live_targets.compliance_agent_url):
        token = bff_minter.mint_id_token(agent_url)
        resp = oidc_client.request_raw(
            "GET",
            f"{agent_url}/healthz",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403, (
            f"BFF SA should NOT hold roles/run.invoker on {agent_url}; expected 403, got {resp.status_code}"
        )
