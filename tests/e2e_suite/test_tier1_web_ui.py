from __future__ import annotations

import pytest
from playwright.sync_api import sync_playwright

from lib.config import LiveTargets
from lib.ui_runner import (
    attach_telemetry_listeners,
    BrowserRunObservation,
    capture_page_artifacts,
    create_isolated_context,
    find_analyze_button,
    find_prompt_input,
    find_scenario_select,
    launch_chromium,
    run_ui_analyze_workflow,
    run_ui_page_load,
)

pytestmark = [pytest.mark.tier1, pytest.mark.live_e2e, pytest.mark.ui]


def test_t1_f7_01_ui_loads_with_controls(live_targets: LiveTargets) -> None:
    with sync_playwright() as pw:
        browser = launch_chromium(pw)
        try:
            ctx = create_isolated_context(browser, extra_headers=live_targets.vercel_headers())
            page = ctx.new_page()
            obs = BrowserRunObservation(status=None)
            attach_telemetry_listeners(page, obs)
            resp = page.goto(live_targets.web_url, wait_until="networkidle", timeout=45000)
            obs.status = resp.status if resp else None
            capture_page_artifacts(page, ctx, obs)

            assert obs.status == 200
            assert page.locator("h1, h2").count() > 0
            select_loc = find_scenario_select(page)
            assert select_loc.locator("option").count() >= 1
            find_prompt_input(page)
            find_analyze_button(page)
        finally:
            browser.close()


def test_t1_f7_02_ui_zero_console_and_network_errors_on_load(live_targets: LiveTargets) -> None:
    obs = run_ui_page_load(
        live_targets.web_url,
        extra_headers=live_targets.vercel_headers(),
    )
    obs.assert_clean_telemetry()


def test_t1_f7_03_ui_executes_analyze_and_renders_report(live_targets: LiveTargets) -> None:
    obs, payload = run_ui_analyze_workflow(
        live_targets.web_url,
        scenario_id="q3_cloud_vendor_review",
        extra_headers=live_targets.vercel_headers(),
    )
    obs.assert_clean_telemetry()
    assert payload is not None, "Expected 200 JSON payload from /api/analyze"
    lower_body = obs.body_text.lower()
    assert payload["overall_risk_rating"].lower() in lower_body
    assert payload["executive_summary"][:40].lower() in lower_body


def test_t1_f7_04_ui_renders_a2a_trace_and_security_posture(live_targets: LiveTargets) -> None:
    obs, _ = run_ui_analyze_workflow(
        live_targets.web_url,
        scenario_id="q3_cloud_vendor_review",
        extra_headers=live_targets.vercel_headers(),
    )
    obs.assert_clean_telemetry()
    lower_body = obs.body_text.lower()
    assert "financial" in lower_body and "compliance" in lower_body
    assert "oidc" in lower_body or "a2a" in lower_body
    assert "0" in lower_body


def test_t1_f7_05_browser_zero_direct_cloud_run_calls_and_zero_stored_creds(
    live_targets: LiveTargets,
) -> None:
    obs, _ = run_ui_analyze_workflow(
        live_targets.web_url,
        scenario_id="series_b_revenue_audit",
        extra_headers=live_targets.vercel_headers(),
    )
    obs.assert_clean_telemetry()
    obs.assert_zero_credential_leakage()
