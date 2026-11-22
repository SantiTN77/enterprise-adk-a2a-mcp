import { expect, test } from '@playwright/test';

const LEAK_PATTERNS = [
  /-----BEGIN [A-Z ]*PRIVATE KEY-----/i,
  /GCP_PRIVATE_KEY/,
  /NEXT_PUBLIC_[A-Z0-9_]*(GCP|KEY|SECRET|TOKEN|PRIVATE)/i,
  /\.iam\.gserviceaccount\.com/,
  /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/,
];

test.describe('Enterprise Multi-Agent BFF & Console E2E Smoke', () => {
  test('API routes enforce health, scenarios, and Zod 400 validation', async ({ request }) => {
    const healthRes = await request.get('/api/health');
    expect(healthRes.status()).toBe(200);
    const healthJson = await healthRes.json();
    expect(healthJson.status).toBe('ok');
    expect(healthJson.bff.runtime).toBe('nodejs');
    expect(healthJson.orchestrator.service).toBe('adk-orchestrator');

    const scenariosRes = await request.get('/api/scenarios');
    expect(scenariosRes.status()).toBe(200);
    const scenariosJson = await scenariosRes.json();
    expect(scenariosJson.scenarios).toHaveLength(3);
    expect(scenariosJson.scenarios.map((s: { id: string }) => s.id)).toEqual([
      'q3_cloud_vendor_review',
      'series_b_revenue_audit',
      'treasury_controls_memo',
    ]);

    const badAnalyzeRes = await request.post('/api/analyze', {
      data: { scenario_id: 'invalid id with spaces!', prompt: 'hi' },
    });
    expect(badAnalyzeRes.status()).toBe(400);
    const badJson = await badAnalyzeRes.json();
    expect(badJson.code).toBe('VALIDATION_ERROR');
  });

  test('UI renders with WCAG semantics, runs 1-click scenario, displays A2A/MCP trace, and leaks zero secrets', async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    const consoleErrors: string[] = [];
    const failedRequests: string[] = [];
    const httpErrorResponses: string[] = [];
    const apiResponseBodies: string[] = [];

    page.on('pageerror', (err) => pageErrors.push(err.message));
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    page.on('requestfailed', (req) => {
      failedRequests.push(`${req.method()} ${req.url()} (${req.failure()?.errorText ?? 'failed'})`);
    });
    page.on('response', async (res) => {
      if (res.status() >= 400) {
        httpErrorResponses.push(`${res.status()} ${res.url()}`);
      }
      if (res.url().includes('/api/')) {
        try {
          apiResponseBodies.push(await res.text());
        } catch {
          // ignore body read errors on redirected/closed streams
        }
      }
    });

    await page.goto('/', { waitUntil: 'networkidle' });

    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    await expect(
      page.getByRole('heading', {
        level: 1,
        name: /Enterprise Multi-Agent Risk & Compliance Console/i,
      }),
    ).toBeVisible();

    await expect(page.getByText(/BFF: Connected/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/min_instances=0, max_instances=2 \(\$0 Idle Cost\)/i)).toBeVisible();
    await expect(page.getByTestId('scenario-card-q3_cloud_vendor_review')).toBeVisible();
    await expect(page.getByTestId('scenario-card-series_b_revenue_audit')).toBeVisible();
    await expect(page.getByTestId('scenario-card-treasury_controls_memo')).toBeVisible();

    // Run 1-Click Scenario #1
    const analyzePromise = page.waitForResponse(
      (res) => res.url().includes('/api/analyze') && res.request().method() === 'POST',
    );
    await page.getByTestId('run-scenario-q3_cloud_vendor_review').click();
    const analyzeRes = await analyzePromise;
    expect(analyzeRes.status()).toBe(200);

    // Assert Executive Report & Risk Badge
    const reportSection = page.getByRole('region', {
      name: /Executive Risk & Compliance Report/i,
    });
    await expect(page.getByTestId('risk-rating-badge')).toContainText('HIGH RISK');
    await expect(reportSection.getByText(/Meridian Retail Analytics Corp\./i)).toBeVisible();
    await expect(reportSection.getByText(/ENT-COMP-POLICY-2026\.3/i)).toBeVisible();

    // Assert A2A Trace & MCP Tools & GCP Provenance
    const traceSection = page.getByRole('region', {
      name: /Multi-Agent A2A & MCP Execution Trace/i,
    });
    await expect(traceSection.getByText('financial_analysis_agent')).toBeVisible();
    await expect(traceSection.getByText('audit_compliance_agent')).toBeVisible();
    await expect(traceSection.getByText('compute_financial_ratios')).toBeVisible();
    await expect(traceSection.getByText('evaluate_control_matrix')).toBeVisible();
    await expect(traceSection.getByText(/gemini-3\.8-flash \(global\)/i)).toBeVisible();
    await expect(traceSection.getByText('adk-compliance-policy-rules', { exact: true })).toBeVisible();

    // Toggle Raw JSON panel
    await page.getByRole('button', { name: /Show Raw JSON/i }).click();
    await expect(page.locator('#raw-json-panel')).toBeVisible();

    // Zero console, page, or network errors
    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
    expect(httpErrorResponses).toEqual([]);

    // Zero leaked credentials/tokens in DOM or API payloads
    const domHtml = await page.content();
    for (const pattern of LEAK_PATTERNS) {
      expect(domHtml).not.toMatch(pattern);
      for (const body of apiResponseBodies) {
        expect(body).not.toMatch(pattern);
      }
    }
  });
});
