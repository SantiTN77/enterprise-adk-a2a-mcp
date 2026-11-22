from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from _harness.mock_stack import FaultConfig, MockStack, make_fake_jwt
from lib.config import LiveTargets, normalize_base_url
from lib.oidc_client import OidcHttpClient, OidcTokenMinter
from lib.repo_hygiene import (
    check_e2e_ast_opaque_box,
    check_gitignore,
    check_no_next_public_secrets,
    check_no_retired_models_or_fastmcp,
    check_pnpm_exclusively,
    check_synthetic_data,
    check_video_and_walkthrough_assets,
    scan_secrets,
)
from lib.schemas import (
    AgentCard,
    AgentHealthzResponse,
    AnalyzeResponse,
    OrchestratorHealthzResponse,
    ScenariosResponse,
    assert_no_leaked_secrets,
    validate_agent_card_url,
)
from lib.tf_policy import check_terraform_defaults, evaluate_terraform_directory
from lib.ui_runner import run_ui_analyze_workflow, run_ui_page_load

pytestmark = [pytest.mark.self_verify]


def test_sv_01_collection_zero_errors_and_tier_minimums(e2e_suite_dir: Path, tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-o",
            f"cache_dir={tmp_path / 'pytest_cache'}",
        ],
        cwd=str(e2e_suite_dir),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, f"pytest --collect-only failed:\n{proc.stdout}\n{proc.stderr}"
    lines = [ln.strip() for ln in proc.stdout.splitlines() if "::test_" in ln]

    t1 = [ln for ln in lines if "test_tier1_" in ln]
    t2 = [ln for ln in lines if "test_tier2_boundaries.py::" in ln]
    t3 = [ln for ln in lines if "test_tier3_pairwise.py::" in ln]
    t4 = [ln for ln in lines if "test_tier4_scenarios.py::" in ln]

    assert len(t1) >= 45, f"Expected >= 45 Tier 1 tests, found {len(t1)}"
    assert len(t2) >= 45, f"Expected >= 45 Tier 2 tests, found {len(t2)}"
    assert len(t3) >= 9, f"Expected >= 9 Tier 3 tests, found {len(t3)}"
    assert len(t4) >= 5, f"Expected >= 5 Tier 4 tests, found {len(t4)}"

    # Verify >= 5 tests per feature in Tier 1 and Tier 2
    for feat_idx in range(1, 10):
        t2_feat = [ln for ln in t2 if f"test_t2_f{feat_idx}_" in ln]
        assert len(t2_feat) >= 5, f"Expected >= 5 Tier 2 tests for F{feat_idx}, found {len(t2_feat)}"


def test_sv_02_config_url_validation_anti_cheat_guards() -> None:
    with pytest.raises(ValueError):
        normalize_base_url("", name="ORCHESTRATOR_URL")
    with pytest.raises(ValueError):
        normalize_base_url("https://svc.a.run.app/", name="ORCHESTRATOR_URL")
    with pytest.raises(ValueError):
        normalize_base_url("http://127.0.0.1:8000", name="ORCHESTRATOR_URL", allow_localhost=False)
    assert (
        normalize_base_url("http://127.0.0.1:8000", name="ORCHESTRATOR_URL", allow_localhost=True)
        == "http://127.0.0.1:8000"
    )

    old = {k: os.environ.get(k) for k in ("ORCHESTRATOR_URL", "FINANCIAL_AGENT_URL", "COMPLIANCE_AGENT_URL", "WEB_URL")}
    try:
        for k in old:
            os.environ.pop(k, None)
        with pytest.raises(ValueError):
            LiveTargets.from_env()
    finally:
        for k, v in old.items():
            if v is not None:
                os.environ[k] = v


def test_sv_03_mock_stack_iam_a2a_orchestrator_bff_positive() -> None:
    with MockStack() as stack:
        minter = OidcTokenMinter(custom_minter=lambda aud: make_fake_jwt(aud))
        client = OidcHttpClient(minter=minter)
        try:
            # 1. Unauth rejected (401) across all 3 private services
            for url in (stack.orchestrator_url, stack.financial_url, stack.compliance_url):
                assert client.request_raw("GET", f"{url}/healthz").status_code == 401

            # 2. Wrong audience rejected (403)
            orch_tok = minter.mint_id_token(stack.orchestrator_url)
            assert (
                client.request_raw(
                    "GET",
                    f"{stack.financial_url}/healthz",
                    headers={"Authorization": f"Bearer {orch_tok}"},
                ).status_code
                == 403
            )

            # 3. Valid OIDC healthz + AgentCard + JSON-RPC
            orch_h = client.request_authenticated("GET", stack.orchestrator_url, "/healthz")
            assert orch_h.status_code == 200
            OrchestratorHealthzResponse.model_validate(orch_h.json())

            for url, expected_agent in (
                (stack.financial_url, "financial_analysis_agent"),
                (stack.compliance_url, "audit_compliance_agent"),
            ):
                ah = client.request_authenticated("GET", url, "/healthz")
                assert ah.status_code == 200
                parsed_ah = AgentHealthzResponse.model_validate(ah.json())
                assert parsed_ah.agent == expected_agent

                card_resp = client.request_authenticated("GET", url, "/.well-known/agent-card.json")
                card = AgentCard.model_validate(card_resp.json())
                validate_agent_card_url(card, url)

                for method in ("SendMessage", "message/send"):
                    rpc = client.request_authenticated(
                        "POST",
                        url,
                        "/",
                        json_body={"jsonrpc": "2.0", "id": "1", "method": method, "params": {}},
                    )
                    assert rpc.status_code == 200
                    assert "result" in rpc.json()

            # 4. Scenarios & Analyze
            sc_resp = client.request_authenticated("GET", stack.orchestrator_url, "/api/scenarios")
            ScenariosResponse.model_validate(sc_resp.json())

            an_resp = client.request_authenticated(
                "POST",
                stack.orchestrator_url,
                "/api/analyze",
                json_body={
                    "scenario_id": "q3_cloud_vendor_review",
                    "doc_id": "samples/q3_cloud_vendor_review.json",
                    "prompt": "Analyze spend.",
                    "persist_report": True,
                },
            )
            assert an_resp.status_code == 200
            AnalyzeResponse.model_validate(an_resp.json())

            # 5. BFF proxy
            assert client.request_raw("GET", f"{stack.web_url}/api/health").status_code == 200
            assert client.request_raw("GET", f"{stack.web_url}/api/scenarios").status_code == 200
            assert client.request_raw("POST", f"{stack.web_url}/api/analyze", json_body={}).status_code == 400
            bff_ok = client.request_raw(
                "POST",
                f"{stack.web_url}/api/analyze",
                json_body={
                    "scenario_id": "treasury_controls_memo",
                    "doc_id": "samples/treasury_controls_memo.json",
                    "prompt": "Audit controls.",
                },
            )
            assert bff_ok.status_code == 200
            AnalyzeResponse.model_validate(bff_ok.json())
        finally:
            client.close()


def test_sv_04_mock_stack_fault_injection_negative_detection() -> None:
    minter = OidcTokenMinter(custom_minter=lambda aud: make_fake_jwt(aud))
    client = OidcHttpClient(minter=minter)
    try:
        # Fault A: retired Gemini model rejected by schema
        with MockStack(FaultConfig(retired_model=True)) as s1:
            r = client.request_authenticated(
                "POST",
                s1.orchestrator_url,
                "/api/analyze",
                json_body={"scenario_id": "adhoc", "document_text": "Test", "prompt": "Test"},
            )
            with pytest.raises(Exception):
                AnalyzeResponse.model_validate(r.json())

        # Fault B: missing compliance delegation trace rejected
        with MockStack(FaultConfig(missing_compliance_trace=True)) as s2:
            r = client.request_authenticated(
                "POST",
                s2.orchestrator_url,
                "/api/analyze",
                json_body={"scenario_id": "adhoc", "document_text": "Test", "prompt": "Test"},
            )
            with pytest.raises(Exception):
                AnalyzeResponse.model_validate(r.json())

        # Fault C: leaked private key in API caught
        with MockStack(FaultConfig(leak_secret_in_api=True)) as s3:
            r = client.request_authenticated(
                "POST",
                s3.orchestrator_url,
                "/api/analyze",
                json_body={"scenario_id": "adhoc", "document_text": "Test", "prompt": "Test"},
            )
            with pytest.raises(AssertionError):
                assert_no_leaked_secrets(r.text, context="fault API")

        # Fault D: unauth allowed caught as IAM failure
        with MockStack(FaultConfig(allow_unauth=True)) as s4:
            unauth = client.request_raw("GET", f"{s4.orchestrator_url}/healthz")
            assert unauth.status_code == 200  # proving harness fault fired so IAM test would fail
    finally:
        client.close()


def test_sv_05_agent_card_url_accepts_443_and_bare_https() -> None:
    base = {
        "name": "financial_analysis_agent",
        "description": "Test",
        "version": "0.0.1",
        "capabilities": {"streaming": True},
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [{"id": "fin", "name": "model", "description": "Analyze"}],
    }
    c_443 = AgentCard.model_validate(
        {
            **base,
            "supportedInterfaces": [
                {
                    "url": "https://adk-financial-agent-xyz.a.run.app:443",
                    "protocolBinding": "JSONRPC",
                    "protocolVersion": "1.0",
                }
            ],
        }
    )
    validate_agent_card_url(c_443, "https://adk-financial-agent-xyz.a.run.app")

    c_bare = AgentCard.model_validate(
        {
            **base,
            "supportedInterfaces": [
                {
                    "url": "https://adk-financial-agent-xyz.a.run.app",
                    "protocolBinding": "JSONRPC",
                    "protocolVersion": "1.0",
                }
            ],
        }
    )
    validate_agent_card_url(c_bare, "https://adk-financial-agent-xyz.a.run.app")

    c_bad = AgentCard.model_validate(
        {
            **base,
            "supportedInterfaces": [
                {
                    "url": "http://localhost:8080",
                    "protocolBinding": "JSONRPC",
                    "protocolVersion": "1.0",
                }
            ],
        }
    )
    with pytest.raises(AssertionError):
        validate_agent_card_url(c_bad, "https://adk-financial-agent-xyz.a.run.app")


def test_sv_06_tf_policy_clean_and_violated_fixtures(tmp_path: Path) -> None:
    clean_dir = tmp_path / "clean_tf"
    clean_dir.mkdir()
    (clean_dir / "main.tf").write_text(
        """
resource "google_service_account" "sa1" { account_id = "vercel-bff" }
resource "google_service_account" "sa2" { account_id = "orch" }
resource "google_service_account" "sa3" { account_id = "fin" }
resource "google_service_account" "sa4" { account_id = "comp" }

resource "google_cloud_run_v2_service" "orch" {
  name = "adk-orchestrator"
  deletion_protection = false
  template { scaling { min_instance_count = 0 max_instance_count = 2 } }
}
resource "google_cloud_run_v2_service" "fin" {
  name = "adk-financial-agent"
  deletion_protection = false
  template { scaling { min_instance_count = 0 max_instance_count = 2 } }
}
resource "google_cloud_run_v2_service" "comp" {
  name = "adk-compliance-agent"
  deletion_protection = false
  template { scaling { min_instance_count = 0 max_instance_count = 2 } }
}
resource "google_cloud_run_v2_service_iam_member" "m1" {
  name = "adk-orchestrator"
  role = "roles/run.invoker"
  member = "serviceAccount:vercel-bff@proj.iam.gserviceaccount.com"
}
resource "google_cloud_run_v2_service_iam_member" "m2" {
  name = "adk-financial-agent"
  role = "roles/run.invoker"
  member = "serviceAccount:orch@proj.iam.gserviceaccount.com"
}
resource "google_cloud_run_v2_service_iam_member" "m3" {
  name = "adk-compliance-agent"
  role = "roles/run.invoker"
  member = "serviceAccount:orch@proj.iam.gserviceaccount.com"
}
""",
        encoding="utf-8",
    )
    (clean_dir / "variables.tf").write_text('variable "gemini_model" { default = "gemini-3.8-flash" }\n', encoding="utf-8")
    (clean_dir / "terraform.tfvars.example").write_text('gemini_model = "gemini-3.8-flash"\n', encoding="utf-8")

    clean_report = evaluate_terraform_directory(clean_dir)
    assert clean_report.passed, clean_report.violations
    assert check_terraform_defaults(clean_dir) == []

    # Dirty TF: min_instance_count = 1, missing deletion_protection, allAuthenticatedUsers, roles/run.admin
    dirty_dir = tmp_path / "dirty_tf"
    dirty_dir.mkdir()
    (dirty_dir / "main.tf").write_text(
        """
resource "google_cloud_run_v2_service" "orch" {
  name = "adk-orchestrator"
  template { scaling { min_instance_count = 1 max_instance_count = 5 } }
}
resource "google_cloud_run_v2_service_iam_member" "pub" {
  name = "adk-orchestrator"
  role = "roles/run.admin"
  member = "allAuthenticatedUsers"
}
""",
        encoding="utf-8",
    )
    dirty_report = evaluate_terraform_directory(dirty_dir)
    assert not dirty_report.passed
    assert len(dirty_report.violations) >= 4


def test_sv_07_repo_hygiene_clean_and_dirty_temp_repos(tmp_path: Path, e2e_suite_dir: Path) -> None:
    # Verify real tests/e2e_suite/ is clean for opaque-box AST & pnpm-only in runner/docs
    assert check_e2e_ast_opaque_box(e2e_suite_dir).passed
    assert check_pnpm_exclusively(e2e_suite_dir).passed

    # Build a clean synthetic repo
    clean = tmp_path / "clean_repo"
    (clean / "docs").mkdir(parents=True)
    (clean / "data" / "synthetic").mkdir(parents=True)
    (clean / "web" / "src").mkdir(parents=True)
    (clean / "services" / "orchestrator").mkdir(parents=True)
    (clean / "tests" / "e2e_suite").mkdir(parents=True)

    (clean / ".gitignore").write_text(".env*\n.terraform/\n*.tfstate*\n.venv/\n.vercel\n", encoding="utf-8")
    (clean / "README.md").write_text("# Enterprise ADK A2A MCP\n" + ("architecture details " * 15), encoding="utf-8")
    (clean / "docs" / "VIDEO_SCRIPT.md").write_text(
        "Walkthrough of A2A, MCP, Cloud Run, OIDC, Secret Manager, GCS, and Vercel BFF. " * 4,
        encoding="utf-8",
    )
    (clean / "docs" / "DEMO_WALKTHROUGH.md").write_text(
        "Scenarios: q3_cloud_vendor_review, series_b_revenue_audit, treasury_controls_memo. "
        "Covers A2A, MCP, Cloud Run, OIDC, Secret Manager, GCS, Vercel. " * 3,
        encoding="utf-8",
    )
    for fname in (
        "q3_cloud_vendor_review.json",
        "series_b_revenue_audit.json",
        "treasury_controls_memo.json",
        "compliance_policy_rules.json",
    ):
        (clean / "data" / "synthetic" / fname).write_text(json.dumps({"ok": True}), encoding="utf-8")
    (clean / "web" / "package.json").write_text('{"name":"web","scripts":{"build":"next build"}}', encoding="utf-8")
    (clean / "web" / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
    (clean / "web" / "src" / "page.tsx").write_text("export default function Page() { return null; }\n", encoding="utf-8")
    (clean / "services" / "orchestrator" / "app.py").write_text(
        "from mcp.server.mcpserver import MCPServer\nMODEL = 'gemini-3.8-flash'\n", encoding="utf-8"
    )
    (clean / "tests" / "e2e_suite" / "test_ok.py").write_text("import httpx\n", encoding="utf-8")

    assert scan_secrets(clean).passed
    assert check_gitignore(clean).passed
    assert check_no_next_public_secrets(clean).passed
    assert check_no_retired_models_or_fastmcp(clean).passed
    assert check_e2e_ast_opaque_box(clean / "tests" / "e2e_suite").passed
    assert check_pnpm_exclusively(clean).passed
    assert check_video_and_walkthrough_assets(clean).passed
    assert check_synthetic_data(clean).passed

    # Build a dirty synthetic repo
    dirty = tmp_path / "dirty_repo"
    (dirty / "web" / "src").mkdir(parents=True)
    (dirty / "services" / "agent").mkdir(parents=True)
    (dirty / "tests" / "e2e_suite").mkdir(parents=True)
    (dirty / "web" / ".env.local").write_text(
        'NEXT_PUBLIC_GCP_KEY="secret"\nKEY="-----BEGIN PRIVATE KEY----- MIIEvQIBADANBgkqhkiG9w0B"\n',
        encoding="utf-8",
    )
    (dirty / "web" / "package-lock.json").write_text("{}", encoding="utf-8")
    (dirty / "README.md").write_text("Run n" + "pm install in web/.\n", encoding="utf-8")
    (dirty / "services" / "agent" / "bad.py").write_text(
        "from mcp.server.fastmcp import FastMCP\nMODEL='gemini-2.0-flash'\n", encoding="utf-8"
    )
    (dirty / "tests" / "e2e_suite" / "bad_test.py").write_text(
        "from services.agent import bad\n", encoding="utf-8"
    )

    assert not scan_secrets(dirty).passed
    assert not check_no_next_public_secrets(dirty).passed
    assert not check_no_retired_models_or_fastmcp(dirty).passed
    assert not check_e2e_ast_opaque_box(dirty / "tests" / "e2e_suite").passed
    assert not check_pnpm_exclusively(dirty).passed


def test_sv_08_playwright_chromium_clean_workflow() -> None:
    with MockStack() as stack:
        obs_load = run_ui_page_load(stack.web_url)
        obs_load.assert_clean_telemetry()
        obs_load.assert_zero_credential_leakage()

        obs_run, payload = run_ui_analyze_workflow(
            stack.web_url,
            scenario_id="q3_cloud_vendor_review",
            prompt="Run offline Playwright Chromium verification.",
        )
        obs_run.assert_clean_telemetry()
        obs_run.assert_zero_credential_leakage()
        assert payload is not None
        AnalyzeResponse.model_validate(payload)
        assert "executive multi-agent assessment completed" in obs_run.body_text.lower()


def test_sv_09_playwright_chromium_detects_injected_faults() -> None:
    # 1. Console error detected
    with MockStack(FaultConfig(ui_console_error=True)) as s1:
        obs = run_ui_page_load(s1.web_url)
        assert len(obs.console_errors) >= 1
        with pytest.raises(AssertionError):
            obs.assert_clean_telemetry()

    # 2. Direct *.run.app browser request detected
    with MockStack(FaultConfig(ui_direct_run_app_call=True)) as s2:
        obs = run_ui_page_load(s2.web_url)
        assert len(obs.direct_cloud_run_requests) >= 1
        with pytest.raises(AssertionError):
            obs.assert_clean_telemetry()

    # 3. Private key leaked in static JS bundle detected
    with MockStack(FaultConfig(leak_secret_in_bundle=True)) as s3:
        obs = run_ui_page_load(s3.web_url)
        with pytest.raises(AssertionError):
            obs.assert_zero_credential_leakage()

    # 4. BFF 502 API response detected
    with MockStack(FaultConfig(bff_upstream_502=True)) as s4:
        obs, payload = run_ui_analyze_workflow(s4.web_url, scenario_id="q3_cloud_vendor_review")
        assert payload is None
        assert any("502 " in f for f in obs.failed_responses)
        with pytest.raises(AssertionError):
            obs.assert_clean_telemetry()


def test_sv_10_live_mode_fails_fast_exit_2_without_urls(e2e_suite_dir: Path, tmp_path: Path) -> None:
    env = dict(os.environ)
    for k in ("ORCHESTRATOR_URL", "FINANCIAL_AGENT_URL", "COMPLIANCE_AGENT_URL", "WEB_URL"):
        env.pop(k, None)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-m",
            "live_e2e",
            "-o",
            f"cache_dir={tmp_path / 'pytest_cache_live'}",
        ],
        cwd=str(e2e_suite_dir),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 2, f"Expected exit code 2, got {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
    assert "ANTI-CHEAT" in proc.stdout or "FAIL" in proc.stdout or "Missing" in proc.stdout or "ANTI-CHEAT" in proc.stderr
