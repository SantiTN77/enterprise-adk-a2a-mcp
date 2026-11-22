from __future__ import annotations

import pytest

from lib.config import LiveTargets
from lib.oidc_client import OidcHttpClient
from lib.schemas import (
    AgentCard,
    AgentHealthzResponse,
    OrchestratorHealthzResponse,
    validate_agent_card_url,
)

pytestmark = [pytest.mark.tier1, pytest.mark.live_e2e, pytest.mark.a2a]


def _require_agent_oidc(live_targets: LiveTargets, agent_oidc_available: bool) -> None:
    if not agent_oidc_available:
        msg = (
            "Direct specialized-agent OIDC token unavailable (least-privilege IAM grants "
            "roles/run.invoker only to adk-orchestrator SA; set E2E_AGENT_IMPERSONATE_SA)."
        )
        if live_targets.strict_live:
            pytest.fail(msg)
        pytest.skip(msg)


def test_t1_f2_01_orchestrator_healthz_contract(
    live_targets: LiveTargets, oidc_client: OidcHttpClient
) -> None:
    resp = oidc_client.request_authenticated("GET", live_targets.orchestrator_url, "/healthz")
    assert resp.status_code == 200, resp.text
    parsed = OrchestratorHealthzResponse.model_validate(resp.json())
    assert parsed.agents["financial"].rstrip("/") == live_targets.financial_agent_url
    assert parsed.agents["compliance"].rstrip("/") == live_targets.compliance_agent_url


def test_t1_f2_02_financial_agent_healthz(
    live_targets: LiveTargets, oidc_client: OidcHttpClient, agent_oidc_available: bool
) -> None:
    _require_agent_oidc(live_targets, agent_oidc_available)
    resp = oidc_client.request_authenticated(
        "GET", live_targets.financial_agent_url, "/healthz", for_specialized_agent=True
    )
    assert resp.status_code == 200, resp.text
    parsed = AgentHealthzResponse.model_validate(resp.json())
    assert parsed.agent == "financial_analysis_agent"


def test_t1_f2_03_compliance_agent_healthz(
    live_targets: LiveTargets, oidc_client: OidcHttpClient, agent_oidc_available: bool
) -> None:
    _require_agent_oidc(live_targets, agent_oidc_available)
    resp = oidc_client.request_authenticated(
        "GET", live_targets.compliance_agent_url, "/healthz", for_specialized_agent=True
    )
    assert resp.status_code == 200, resp.text
    parsed = AgentHealthzResponse.model_validate(resp.json())
    assert parsed.agent == "audit_compliance_agent"


def test_t1_f2_04_financial_agent_card_discovery(
    live_targets: LiveTargets, oidc_client: OidcHttpClient, agent_oidc_available: bool
) -> None:
    _require_agent_oidc(live_targets, agent_oidc_available)
    resp = oidc_client.request_authenticated(
        "GET",
        live_targets.financial_agent_url,
        "/.well-known/agent-card.json",
        for_specialized_agent=True,
    )
    assert resp.status_code == 200, resp.text
    card = AgentCard.model_validate(resp.json())
    validate_agent_card_url(card, live_targets.financial_agent_url)
    assert card.supportedInterfaces[0].protocolBinding.upper() == "JSONRPC"


def test_t1_f2_05_compliance_agent_card_discovery(
    live_targets: LiveTargets, oidc_client: OidcHttpClient, agent_oidc_available: bool
) -> None:
    _require_agent_oidc(live_targets, agent_oidc_available)
    resp = oidc_client.request_authenticated(
        "GET",
        live_targets.compliance_agent_url,
        "/.well-known/agent-card.json",
        for_specialized_agent=True,
    )
    assert resp.status_code == 200, resp.text
    card = AgentCard.model_validate(resp.json())
    validate_agent_card_url(card, live_targets.compliance_agent_url)
    assert card.supportedInterfaces[0].protocolBinding.upper() == "JSONRPC"


def test_t1_f2_06_a2a_jsonrpc_message_send_both_agents(
    live_targets: LiveTargets, oidc_client: OidcHttpClient, agent_oidc_available: bool
) -> None:
    _require_agent_oidc(live_targets, agent_oidc_available)
    rpc_payload = {
        "jsonrpc": "2.0",
        "id": "e2e-a2a-probe",
        "method": "message/send",
        "params": {
            "message": {
                "messageId": "msg-e2e-1",
                "role": "user",
                "parts": [{"text": "List available enterprise documents and summarize capabilities."}],
            }
        },
    }
    for agent_url in (live_targets.financial_agent_url, live_targets.compliance_agent_url):
        resp = oidc_client.request_authenticated(
            "POST",
            agent_url,
            "/",
            for_specialized_agent=True,
            json_body=rpc_payload,
            timeout=90.0,
        )
        assert resp.status_code == 200, f"JSON-RPC POST / failed on {agent_url}: {resp.status_code} {resp.text[:300]}"
        body = resp.json()
        assert body.get("jsonrpc") == "2.0"
        assert "result" in body or "error" not in body, f"Unexpected JSON-RPC error: {body}"
