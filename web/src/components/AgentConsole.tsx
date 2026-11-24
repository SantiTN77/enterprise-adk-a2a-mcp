'use client';

import { useEffect, useRef, useState, useTransition } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import { AlertCircle, ArrowRight, ChevronDown, CornerDownLeft } from 'lucide-react';
import { DEFAULT_SCENARIOS, SCENARIO_UI_META } from '@/lib/scenarios';
import type { AnalyzeResponse, HealthResponse, ScenarioItem, ScenariosResponse } from '@/lib/types';
import { ES_PROMPT_SUFFIX, SCENARIO_ES, STRINGS, useLang } from '@/lib/i18n';
import { HeaderBar } from './HeaderBar';
import { SecurityPosturePanel } from './SecurityPosturePanel';
import { ExecutionTracePanel } from './ExecutionTracePanel';
import { ExecutiveReportPanel } from './ExecutiveReportPanel';

const EASE = [0.16, 1, 0.3, 1] as const;

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
  const [lang] = useLang();
  const t = STRINGS[lang];
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
    const basePrompt = overrideScenario ? overrideScenario.default_prompt : prompt;
    const effectivePrompt = lang === 'es' && !basePrompt.includes('in Spanish') ? basePrompt + ES_PROMPT_SUFFIX : basePrompt;

    if (effectivePrompt.trim().length < 5) {
      setErrorMessage(t.promptShort);
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
      setErrorMessage(t.unreachable);
    } finally {
      setIsRunning(false);
    }
  }

  function handleFormSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void executeAnalysis();
  }

  const busy = isRunning || isPending;
  const reduce = useReducedMotion();
  const rise = (d = 0) =>
    reduce
      ? {}
      : { initial: { opacity: 0, y: 18 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.9, ease: EASE, delay: d } };

  return (
    <div className="min-h-screen">
      <HeaderBar
        health={health}
        healthLoading={healthLoading}
        onRefreshHealth={() => void handleRefreshHealth()}
        postureExpanded={postureExpanded}
        onTogglePosture={() => setPostureExpanded((prev) => !prev)}
      />

      <main className="mx-auto max-w-[1280px] space-y-20 px-5 pb-24 sm:px-8">
        {/* intro */}
        <section className="grid grid-cols-12 gap-6 pt-12 md:pt-16">
          <motion.div {...rise()} className="col-span-12 lg:col-span-8">
            <p className="eyebrow">{t.eyebrow}</p>
            <h2 className="mt-4 text-balance text-4xl font-medium leading-[1.02] tracking-[-0.035em] md:text-6xl">
              {t.h1a} <span className="font-serif italic text-accent">{t.h1b}</span>
            </h2>
          </motion.div>
          <motion.p {...rise(0.1)} className="col-span-12 self-end text-pretty text-[15px] leading-relaxed text-ink-muted lg:col-span-4">
            {t.lede}
          </motion.p>
        </section>

        <SecurityPosturePanel expanded={postureExpanded} health={health} posture={report?.security_posture ?? null} />

        {/* scenarios */}
        <section aria-labelledby="scenarios-heading" data-demo="scenarios">
          <div className="flex flex-wrap items-end justify-between gap-3 border-t border-ink pt-5">
            <div>
              <p className="eyebrow">{t.casesEyebrow}</p>
              <h2 id="scenarios-heading" className="mt-2 text-2xl font-medium tracking-tight md:text-3xl">
                {t.casesTitle}
              </h2>
            </div>
            <p className="text-xs text-ink-muted">
              {t.evidence}{' '}
              <code className="font-mono text-ink">adk-compliance-policy-rules</code>
            </p>
          </div>

          <div className="mt-8 grid gap-4 lg:grid-cols-3">
            {scenarios.map((scenario, idx) => {
              const isSelected = scenario.id === activeScenario.id;
              const uiMeta = SCENARIO_UI_META[scenario.id];
              const dot = uiMeta?.tone === 'success' ? 'bg-ok' : uiMeta?.tone === 'critical' ? 'bg-bad' : 'bg-warn';
              const es = lang === 'es' ? SCENARIO_ES[scenario.id] : undefined;
              const signal = es?.signal ?? uiMeta?.expectedSignal ?? '';
              const txt = uiMeta?.tone === 'success' ? 'text-ok' : uiMeta?.tone === 'critical' ? 'text-bad' : 'text-warn';
              return (
                <motion.div
                  key={scenario.id}
                  {...rise(0.05 + idx * 0.07)}
                  data-testid={`scenario-card-${scenario.id}`}
                  className={`relative flex flex-col justify-between rounded-[18px] border bg-card p-5 transition-all duration-500 ${
                    isSelected
                      ? 'border-ink shadow-[0_24px_48px_-32px_rgba(21,20,18,0.5)]'
                      : 'border-line hover:-translate-y-0.5 hover:border-line-strong'
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[11px] text-ink-faint">{String(idx + 1).padStart(2, '0')}</span>
                      {uiMeta ? (
                        <span className={`inline-flex items-center gap-1.5 font-mono text-[10.5px] ${txt}`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
                          {signal.split(' · ')[0]}
                        </span>
                      ) : null}
                    </div>
                    <h3 className="mt-4 text-lg font-medium leading-snug tracking-tight">{es?.title ?? scenario.title}</h3>
                    {uiMeta ? <p className="mt-1 text-xs text-ink-muted">{uiMeta.company}</p> : null}
                    {uiMeta ? (
                      <p className={`mt-3 text-xs ${txt}`}>{signal.split(' · ').slice(1).join(' · ')}</p>
                    ) : null}
                    <p className="mt-3 text-sm leading-relaxed text-ink-soft">{es?.description ?? scenario.description}</p>
                    <p className="mt-3 font-mono text-[11px] text-ink-faint">{scenario.doc_id}</p>
                  </div>

                  <div className="mt-5 flex gap-2 border-t border-line pt-4">
                    <button
                      type="button"
                      onClick={() => handleSelectScenario(scenario)}
                      aria-pressed={isSelected}
                      className={`flex-1 rounded-full border px-3 py-2 text-sm transition-colors ${
                        isSelected ? 'border-ink bg-paper-deep text-ink' : 'border-line-strong text-ink-soft hover:border-ink'
                      }`}
                    >
                      {isSelected ? t.selected : t.select}
                    </button>
                    <button
                      type="button"
                      onClick={() => void executeAnalysis(scenario)}
                      disabled={busy}
                      data-testid={`run-scenario-${scenario.id}`}
                      className="group inline-flex items-center justify-center gap-1.5 rounded-full bg-ink px-4 py-2 text-sm font-medium text-paper transition-transform duration-300 hover:-translate-y-px disabled:cursor-wait disabled:opacity-60"
                    >
                      {t.run1}
                      <ArrowRight
                        className="h-3.5 w-3.5 transition-transform duration-500 group-hover:translate-x-0.5"
                        aria-hidden="true"
                      />
                    </button>
                  </div>
                </motion.div>
              );
            })}
          </div>

          <form onSubmit={handleFormSubmit} noValidate className="card mt-6 p-5 sm:p-6">
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <label htmlFor="scenario-selector" className="eyebrow block">
                  {t.activeScenario}
                </label>
                <div className="relative mt-2">
                  <select
                    id="scenario-selector"
                    name="scenario_id"
                    data-testid="scenario-select"
                    value={activeScenario.id}
                    onChange={(e) => {
                      const matched = scenarios.find((s) => s.id === e.target.value);
                      if (matched) handleSelectScenario(matched);
                    }}
                    className="w-full appearance-none rounded-xl border border-line bg-paper/60 px-3.5 py-2.5 pr-9 text-sm focus:border-ink focus:outline-none"
                  >
                    {scenarios.map((s) => (
                      <option key={s.id} value={s.id}>
                        {(lang === 'es' && SCENARIO_ES[s.id]?.title) || s.title}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
                </div>
              </div>
              <div className="sm:col-span-2">
                <label htmlFor="analysis-prompt" className="eyebrow block">
                  {t.prompt} · {activeScenario.id}
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
                  className="mt-2 w-full resize-none rounded-xl border border-line bg-paper/60 px-3.5 py-2.5 text-[15px] leading-relaxed focus:border-ink focus:outline-none"
                />
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-4 border-t border-line pt-4">
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <button
                  type="button"
                  onClick={() => setShowCustomDoc((prev) => !prev)}
                  aria-expanded={showCustomDoc}
                  aria-controls="custom-document-panel"
                  className="inline-flex items-center gap-2 rounded-full border border-line-strong px-3.5 py-2 transition-colors hover:border-ink"
                >
                  {t.adhoc}
                  <ChevronDown
                    className={`h-4 w-4 transition-transform duration-500 ${showCustomDoc ? 'rotate-180' : ''}`}
                    aria-hidden="true"
                  />
                </button>
                <label htmlFor="persist-report-toggle" className="inline-flex cursor-pointer items-center gap-2.5 text-ink-soft">
                  <input
                    id="persist-report-toggle"
                    type="checkbox"
                    checked={persistReport}
                    onChange={(e) => setPersistReport(e.target.checked)}
                    className="h-4 w-4 rounded accent-[#151412]"
                  />
                  {t.persist}
                </label>
              </div>

              <button
                type="submit"
                disabled={busy}
                data-testid="analyze-submit"
                className="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-paper transition-transform duration-300 hover:-translate-y-px disabled:cursor-wait disabled:opacity-70"
              >
                {busy ? t.running : t.runAll}
                <CornerDownLeft className="h-3.5 w-3.5 opacity-80" aria-hidden="true" />
              </button>
            </div>

            <div id="custom-document-panel" className={showCustomDoc ? 'mt-4' : 'hidden'}>
              <label htmlFor="custom-document-text" className="eyebrow block">
                {t.adhocLabel}
              </label>
              <textarea
                id="custom-document-text"
                name="document_text"
                data-testid="adhoc-doc-input"
                rows={5}
                value={documentText}
                onChange={(e) => setDocumentText(e.target.value)}
                placeholder={t.adhocPh}
                className="mt-2 w-full rounded-xl border border-line bg-paper/60 px-3.5 py-2.5 font-mono text-xs focus:border-ink focus:outline-none"
              />
            </div>
          </form>

          {errorMessage ? (
            <div role="alert" className="mt-4 flex items-start gap-2.5 rounded-xl border border-bad/30 bg-bad-soft p-4 text-sm text-bad">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
              <div>
                <p className="font-medium">{t.execError}</p>
                <p className="mt-0.5">{errorMessage}</p>
              </div>
            </div>
          ) : null}
        </section>

        <ExecutionTracePanel trace={report?.a2a_trace ?? []} provenance={report?.gcp_provenance ?? null} isPending={busy} />

        {report && !busy ? <ExecutiveReportPanel report={report} /> : null}

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-6 font-mono text-[11px] text-ink-muted">
          <span>{t.built}</span>
          <a href="https://danieltafur.vercel.app" target="_blank" rel="noopener noreferrer" className="hover:text-ink">
            danieltafur.vercel.app ↗
          </a>
        </footer>
      </main>
    </div>
  );
}
