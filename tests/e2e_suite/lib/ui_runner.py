from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import Browser, BrowserContext, Locator, Page, Playwright, sync_playwright

from lib.schemas import assert_no_leaked_secrets


@dataclass
class BrowserRunObservation:
    status: int | None
    console_errors: list[str] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    failed_responses: list[str] = field(default_factory=list)
    direct_cloud_run_requests: list[str] = field(default_factory=list)
    html: str = ""
    body_text: str = ""
    storage_dump: str = ""
    cookies_dump: str = ""
    bundle_texts: list[str] = field(default_factory=list)

    def assert_clean_telemetry(self) -> None:
        assert self.status == 200, f"Expected HTTP 200 page load, got {self.status}"
        assert not self.console_errors, f"Browser console errors detected: {self.console_errors}"
        assert not self.page_errors, f"Uncaught page errors detected: {self.page_errors}"
        assert not self.failed_responses, f"Failed network responses (>=400): {self.failed_responses}"
        assert not self.direct_cloud_run_requests, (
            f"Browser attempted direct *.run.app call(s) bypassing BFF: {self.direct_cloud_run_requests}"
        )

    def assert_zero_credential_leakage(self) -> None:
        assert_no_leaked_secrets(self.html, context="rendered HTML")
        assert_no_leaked_secrets(self.storage_dump, context="localStorage/sessionStorage")
        assert_no_leaked_secrets(self.cookies_dump, context="browser cookies")
        for idx, bundle in enumerate(self.bundle_texts):
            assert_no_leaked_secrets(bundle, context=f"JS bundle #{idx}")


def launch_chromium(pw: Playwright) -> Browser:
    """Launch Playwright Chromium, falling back to system Chrome channel if needed."""
    try:
        return pw.chromium.launch(headless=True)
    except Exception:
        return pw.chromium.launch(channel="chrome", headless=True)


def create_isolated_context(
    browser: Browser,
    *,
    extra_headers: dict[str, str] | None = None,
    viewport: dict[str, int] | None = None,
) -> BrowserContext:
    return browser.new_context(
        extra_http_headers=extra_headers or {},
        viewport=viewport or {"width": 1440, "height": 900},
    )


def attach_telemetry_listeners(page: Page, obs: BrowserRunObservation) -> None:
    def _on_console(msg: Any) -> None:
        if msg.type == "error":
            obs.console_errors.append(msg.text)

    def _on_pageerror(err: Any) -> None:
        obs.page_errors.append(str(err))

    def _on_response(resp: Any) -> None:
        if resp.status >= 400:
            obs.failed_responses.append(f"{resp.status} {resp.request.method} {resp.url}")
        if resp.url.endswith(".js") or "/_next/static/" in resp.url:
            try:
                if resp.status == 200:
                    obs.bundle_texts.append(resp.text())
            except Exception:
                pass

    def _on_request(req: Any) -> None:
        host = (urlparse(req.url).hostname or "").lower()
        if host.endswith(".run.app"):
            obs.direct_cloud_run_requests.append(f"{req.method} {req.url}")

    page.on("console", _on_console)
    page.on("pageerror", _on_pageerror)
    page.on("response", _on_response)
    page.on("request", _on_request)


def first_visible(page: Page, selectors: list[Locator]) -> Locator | None:
    for loc in selectors:
        try:
            if loc.count() > 0 and loc.first.is_visible():
                return loc.first
        except Exception:
            continue
    return None


def find_scenario_select(page: Page) -> Locator:
    loc = first_visible(
        page,
        [
            page.get_by_test_id("scenario-select"),
            page.get_by_label("Scenario", exact=False),
            page.locator("select"),
        ],
    )
    assert loc is not None, "Could not locate scenario selector in UI"
    return loc


def find_prompt_input(page: Page) -> Locator:
    loc = first_visible(
        page,
        [
            page.get_by_test_id("prompt-input"),
            page.get_by_label("Prompt", exact=False),
            page.locator("textarea"),
            page.get_by_role("textbox"),
        ],
    )
    assert loc is not None, "Could not locate prompt input in UI"
    return loc


def find_adhoc_input(page: Page) -> Locator | None:
    return first_visible(
        page,
        [
            page.get_by_test_id("adhoc-doc-input"),
            page.get_by_label("Document", exact=False),
        ],
    )


def find_analyze_button(page: Page) -> Locator:
    loc = first_visible(
        page,
        [
            page.get_by_test_id("analyze-submit"),
            page.get_by_role("button", name="Analyze"),
            page.get_by_role("button", name="Run"),
            page.locator("button[type='submit']"),
            page.locator("button"),
        ],
    )
    assert loc is not None, "Could not locate Analyze submit button in UI"
    return loc


def capture_page_artifacts(page: Page, context: BrowserContext, obs: BrowserRunObservation) -> None:
    obs.html = page.content()
    obs.body_text = page.locator("body").inner_text()
    storage = page.evaluate(
        "() => JSON.stringify({ls: {...localStorage}, ss: {...sessionStorage}})"
    )
    obs.storage_dump = str(storage)
    obs.cookies_dump = str(context.cookies())


def run_ui_page_load(
    url: str,
    *,
    extra_headers: dict[str, str] | None = None,
    viewport: dict[str, int] | None = None,
    timeout_ms: int = 45000,
) -> BrowserRunObservation:
    obs = BrowserRunObservation(status=None)
    with sync_playwright() as pw:
        browser = launch_chromium(pw)
        try:
            ctx = create_isolated_context(browser, extra_headers=extra_headers, viewport=viewport)
            page = ctx.new_page()
            attach_telemetry_listeners(page, obs)
            resp = page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            obs.status = resp.status if resp is not None else None
            capture_page_artifacts(page, ctx, obs)
        finally:
            browser.close()
    return obs


def run_ui_analyze_workflow(
    url: str,
    *,
    scenario_id: str | None = None,
    prompt: str | None = None,
    adhoc_document: str | None = None,
    extra_headers: dict[str, str] | None = None,
    timeout_ms: int = 120000,
) -> tuple[BrowserRunObservation, dict[str, Any] | None]:
    obs = BrowserRunObservation(status=None)
    api_payload: dict[str, Any] | None = None

    with sync_playwright() as pw:
        browser = launch_chromium(pw)
        try:
            ctx = create_isolated_context(browser, extra_headers=extra_headers)
            page = ctx.new_page()
            attach_telemetry_listeners(page, obs)

            resp = page.goto(url, wait_until="networkidle", timeout=45000)
            obs.status = resp.status if resp is not None else None

            if scenario_id:
                select_loc = find_scenario_select(page)
                try:
                    select_loc.select_option(scenario_id)
                except Exception:
                    select_loc.select_option(index=0)

            if prompt is not None:
                prompt_loc = find_prompt_input(page)
                prompt_loc.fill(prompt)

            if adhoc_document is not None:
                adhoc_loc = find_adhoc_input(page)
                if adhoc_loc is not None:
                    adhoc_loc.fill(adhoc_document)

            submit_btn = find_analyze_button(page)
            with page.expect_response(
                lambda r: "/api/analyze" in r.url and r.request.method == "POST",
                timeout=timeout_ms,
            ) as api_info:
                submit_btn.click()

            api_resp = api_info.value
            if api_resp.status == 200:
                try:
                    api_payload = api_resp.json()
                except Exception:
                    api_payload = None

            page.wait_for_load_state("networkidle", timeout=15000)
            capture_page_artifacts(page, ctx, obs)
        finally:
            browser.close()

    return obs, api_payload
