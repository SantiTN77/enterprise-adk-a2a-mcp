'use client';

import { useEffect, useRef, useState, useTransition } from 'react';
import { AlertCircle, ChevronDown, ChevronUp, FileText, Play, Sparkles } from 'lucide-react';
import { DEFAULT_SCENARIOS, SCENARIO_UI_META } from '@/lib/scenarios';
import type { AnalyzeResponse, HealthResponse, ScenarioItem, ScenariosResponse } from '@/lib/types';
import { HeaderBar } from './HeaderBar';
import { SecurityPosturePanel } from './SecurityPosturePanel';
import { ExecutionTracePanel } from './ExecutionTracePanel';
import { ExecutiveReportPanel } from './ExecutiveReportPanel';

async function fetchStatusAndScenarios(): Promise<{
  health: HealthResponse | null;
  scenarios: ScenarioItem[] | null;
}> {
  const [healthRes, scenariosRes] = await Promise.allSettled([
    fetch('/api/health', { cache: 'no-store' }),
    fetch('/api/scenarios', { cache: 'no-store' }),
  ]);

  let nextHealth: HealthResponse | null = null;
  if (healthRes.status === 'fulfilled') {
    try {
      nextHealth = (await healthRes.value.json()) as HealthResponse;
    } catch {
      nextHealth = null;
    }
  }

  let nextScenarios: ScenarioItem[] | null = null;
  if (scenariosRes.status === 'fulfilled' && scenariosRes.value.ok) {
    try {
      const data = (await scenariosRes.value.json()) as ScenariosResponse;
      if (Array.isArray(data.scenarios) && data.scenarios.length > 0) {
        nextScenarios = data.scenarios;
      }
    } catch {
      nextScenarios = null;
    }
  }

  return { health: nextHealth, scenarios: nextScenarios };
}

export function AgentConsole() {
  const [scenarios, setScenarios] = useState<ScenarioItem[]>(DEFAULT_SCENARIOS);
  const [selectedId, setSelectedId] = useState<string>(DEFAULT_SCENARIOS[0].id);
  const [prompt, setPrompt] = useState<string>(DEFAULT_SCENARIOS[0].default_prompt);
  const [documentText, setDocumentText] = useState<string>('');
  const [showCustomDoc, setShowCustomDoc] = useState<boolean>(false);
  const [persistReport, setPersistReport] = useState<boolean>(true);

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(false);
  const [postureExpanded, setPostureExpanded] = useState<boolean>(true);

  const [report, setReport] = useState<AnalyzeResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [isPending, startTransition] = useTransition();

  const abortRef = useRef<AbortController | null>(null);

  const activeScenario = scenarios.find((item) => item.id === selectedId) ?? scenarios[0];

  useEffect(() => {
    let active = true;
    void fetchStatusAndScenarios().then(({ health: nextHealth, scenarios: nextScenarios }) => {
      if (!active) return;
      if (nextHealth) {
        setHealth(nextHealth);
      }
      if (nextScenarios) {
        setScenarios(nextScenarios);
      }
    });
    return () => {
      active = false;
      abortRef.current?.abort();
    };
  }, []);

  async function handleRefreshHealth() {
    setHealthLoading(true);
    try {
      const { health: nextHealth, scenarios: nextScenarios } = await fetchStatusAndScenarios();
      if (nextHealth) {
        setHealth(nextHealth);
      }
      if (nextScenarios) {
        setScenarios(nextScenarios);
      }
    } finally {
      setHealthLoading(false);
    }
  }

  function handleSelectScenario(scenario: ScenarioItem) {
    startTransition(() => {
      setSelectedId(scenario.id);
      setPrompt(scenario.default_prompt);
      setErrorMessage(null);
    });
  }

  async function executeAnalysis(overrideScenario?: ScenarioItem) {
    const targetScenario = overrideScenario ?? activeScenario;
    const effectivePrompt = overrideScenario ? overrideScenario.default_prompt : prompt;

    if (effectivePrompt.trim().length < 5) {
      setErrorMessage('Prompt must be at least 5 characters.');
      return;
    }

    if (overrideScenario) {
      startTransition(() => {
        setSelectedId(overrideScenario.id);
        setPrompt(overrideScenario.default_prompt);
      });
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsRunning(true);
    setErrorMessage(null);

    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_id: targetScenario.id,
          doc_id: targetScenario.doc_id,
          prompt: effectivePrompt,
          persist_report: persistReport,
          ...(documentText.trim() ? { document_text: documentText.trim() } : {}),
        }),
        signal: controller.signal,
      });

      const payload = (await res.json()) as AnalyzeResponse | { error?: string };

      if (!res.ok) {
        const errText =
          'error' in payload && typeof payload.error === 'string'
            ? payload.error
            : `Analysis request failed (HTTP ${res.status})`;
        setErrorMessage(errText);
        return;
      }

      setReport(payload as AnalyzeResponse);
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      setErrorMessage('Unable to reach BFF /api/analyze endpoint. Check /api/health and try again.');
    } finally {
      setIsRunning(false);
    }
  }

  function handleFormSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void executeAnalysis();
  }

  const busy = isRunning || isPending;

  return (
    <div className="min-h-screen bg-[#090D16] text-slate-100">
      <HeaderBar
        health={health}
        healthLoading={healthLoading}
        onRefreshHealth={() => void handleRefreshHealth()}
        postureExpanded={postureExpanded}
        onTogglePosture={() => setPostureExpanded((prev) => !prev)}
      />

      <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <SecurityPosturePanel
          expanded={postureExpanded}
          health={health}
          posture={report?.security_posture ?? null}
        />

        {/* Scenario Selection & Prompt Workbench */}
        <section
          aria-labelledby="scenarios-heading"
          className="rounded-2xl border border-slate-800 bg-[#111827] p-5 shadow-lg"
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2.5">
              <Sparkles className="h-5 w-5 text-sky-300" aria-hidden="true" />
              <h2 id="scenarios-heading" className="text-lg font-semibold text-slate-50">
                1-Click Synthetic Enterprise Scenarios
              </h2>
            </div>
            <p className="text-xs text-slate-400">
              Backed by GCS samples &amp; Secret Manager policy{' '}
              <code className="font-mono text-slate-300">adk-compliance-policy-rules</code>
            </p>
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-3">
            {scenarios.map((scenario) => {
              const isSelected = scenario.id === activeScenario.id;
              const uiMeta = SCENARIO_UI_META[scenario.id];
              const toneClasses =
                uiMeta?.tone === 'success'
                  ? 'border-emerald-500/30 bg-emerald-950/50 text-emerald-200'
                  : uiMeta?.tone === 'critical'
                    ? 'border-red-500/30 bg-red-950/50 text-red-200'
                    : 'border-amber-500/30 bg-amber-950/50 text-amber-200';

              return (
                <div
                  key={scenario.id}
                  data-testid={`scenario-card-${scenario.id}`}
                  className={`flex flex-col justify-between rounded-xl border p-4 transition-colors motion-reduce:transition-none ${
                    isSelected
                      ? 'border-sky-400 bg-sky-950/25 shadow-md shadow-sky-950/40'
                      : 'border-slate-800 bg-[#0B101B] hover:border-slate-700'
                  }`}
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="text-base font-semibold text-slate-50">{scenario.title}</h3>
                    </div>

                    {uiMeta ? (
                      <p className="mt-1 text-xs font-medium text-slate-400">{uiMeta.company}</p>
                    ) : null}

                    {uiMeta ? (
                      <div className="mt-2">
                        <span
                          className={`inline-block rounded-full border px-2.5 py-0.5 text-xs font-semibold ${toneClasses}`}
                        >
                          {uiMeta.expectedSignal}
                        </span>
                      </div>
                    ) : null}

                    <p className="mt-3 text-sm leading-relaxed text-slate-300">{scenario.description}</p>
                    <p className="mt-2 font-mono text-xs text-slate-400">{scenario.doc_id}</p>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2 pt-2">
                    <button
                      type="button"
                      onClick={() => handleSelectScenario(scenario)}
                      aria-pressed={isSelected}
                      className={`min-h-[48px] flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0B101B] motion-reduce:transition-none ${
                        isSelected
                          ? 'border-sky-400 bg-sky-500/20 text-sky-100'
                          : 'border-slate-700 bg-slate-900 text-slate-200 hover:border-slate-500'
                      }`}
                    >
                      {isSelected ? 'Selected' : 'Select'}
                    </button>

                    <button
                      type="button"
                      onClick={() => void executeAnalysis(scenario)}
                      disabled={busy}
                      data-testid={`run-scenario-${scenario.id}`}
                      className="inline-flex min-h-[48px] items-center justify-center gap-1.5 rounded-lg bg-sky-500 px-3.5 py-2 text-sm font-semibold text-slate-950 transition-colors hover:bg-sky-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0B101B] disabled:cursor-not-allowed disabled:opacity-60 motion-reduce:transition-none"
                    >
                      <Play className="h-4 w-4" aria-hidden="true" />
                      <span>Run 1-Click</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          <form onSubmit={handleFormSubmit} noValidate className="mt-6 space-y-4 border-t border-slate-800 pt-5">
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <label htmlFor="scenario-selector" className="block text-sm font-medium text-slate-200">
                  Active Scenario
                </label>
                <select
                  id="scenario-selector"
                  name="scenario_id"
                  data-testid="scenario-select"
                  value={activeScenario.id}
                  onChange={(e) => {
                    const matched = scenarios.find((s) => s.id === e.target.value);
                    if (matched) {
                      handleSelectScenario(matched);
                    }
                  }}
                  className="mt-1.5 w-full min-h-[44px] rounded-xl border border-slate-700 bg-[#0B101B] px-3 py-2 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/50"
                >
                  {scenarios.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.title}
                    </option>
                  ))}
                </select>
              </div>
              <div className="sm:col-span-2">
                <label htmlFor="analysis-prompt" className="block text-sm font-medium text-slate-200">
                  Orchestrator Prompt ({activeScenario.id})
                </label>
                <textarea
                  id="analysis-prompt"
                  name="prompt"
                  data-testid="prompt-input"
                  rows={3}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  required
                  minLength={5}
                  maxLength={4000}
                  className="mt-1.5 w-full rounded-xl border border-slate-700 bg-[#0B101B] px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/50"
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex flex-wrap items-center gap-4">
                <button
                  type="button"
                  onClick={() => setShowCustomDoc((prev) => !prev)}
                  aria-expanded={showCustomDoc}
                  aria-controls="custom-document-panel"
                  className="inline-flex min-h-[48px] items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3.5 py-2 text-sm font-medium text-slate-200 hover:border-slate-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
                >
                  <FileText className="h-4 w-4 text-sky-300" aria-hidden="true" />
                  <span>Optional Ad-Hoc Document Text</span>
                  {showCustomDoc ? (
                    <ChevronUp className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <ChevronDown className="h-4 w-4" aria-hidden="true" />
                  )}
                </button>

                <label
                  htmlFor="persist-report-toggle"
                  className="inline-flex min-h-[48px] cursor-pointer items-center gap-2.5 rounded-lg border border-slate-800 bg-[#0B101B] px-3.5 py-2 text-sm text-slate-200"
                >
                  <input
                    id="persist-report-toggle"
                    type="checkbox"
                    checked={persistReport}
                    onChange={(e) => setPersistReport(e.target.checked)}
                    className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-sky-400 focus:ring-2 focus:ring-sky-400"
                  />
                  <span>Persist Report to GCS</span>
                </label>
              </div>

              <button
                type="submit"
                disabled={busy}
                data-testid="analyze-submit"
                className="inline-flex min-h-[48px] items-center gap-2 rounded-xl bg-emerald-400 px-5 py-2.5 text-sm font-bold text-slate-950 transition-colors hover:bg-emerald-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#111827] disabled:cursor-not-allowed disabled:opacity-60 motion-reduce:transition-none"
              >
                <Play className="h-4 w-4" aria-hidden="true" />
                <span>{busy ? 'Running A2A + MCP Agents…' : 'Run Multi-Agent Analysis'}</span>
              </button>
            </div>

            <div
              id="custom-document-panel"
              className={showCustomDoc ? 'rounded-xl border border-slate-800 bg-[#0B101B] p-4' : 'rounded-xl border border-slate-800/70 bg-[#0B101B] p-3'}
            >
              <label htmlFor="custom-document-text" className="block text-xs font-medium text-slate-300">
                Custom Document JSON / Memo Text (Optional override sent to orchestrator)
              </label>
              <textarea
                id="custom-document-text"
                name="document_text"
                data-testid="adhoc-doc-input"
                rows={showCustomDoc ? 5 : 2}
                value={documentText}
                onChange={(e) => setDocumentText(e.target.value)}
                placeholder="Paste custom financial statement JSON or compliance memo text for ad-hoc analysis..."
                className="mt-1.5 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-100 placeholder-slate-500 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/50"
              />
            </div>
          </form>

          {errorMessage ? (
            <div
              role="alert"
              className="mt-4 flex items-start gap-2.5 rounded-xl border border-red-500/40 bg-red-950/50 p-4 text-sm text-red-100"
            >
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-300" aria-hidden="true" />
              <div>
                <p className="font-semibold">Execution Error</p>
                <p className="mt-0.5 text-red-200">{errorMessage}</p>
              </div>
            </div>
          ) : null}
        </section>

        <ExecutionTracePanel
          trace={report?.a2a_trace ?? []}
          provenance={report?.gcp_provenance ?? null}
          isPending={busy}
        />

        {report ? <ExecutiveReportPanel report={report} /> : null}
      </main>
    </div>
  );
}
