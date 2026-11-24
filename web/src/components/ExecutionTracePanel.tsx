'use client';

import { useEffect, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { ArrowRight, Check, X } from 'lucide-react';
import type { A2ATraceStep, GcpProvenance } from '@/lib/types';
import { STRINGS, useLang } from '@/lib/i18n';

const EASE = [0.16, 1, 0.3, 1] as const;


interface ExecutionTracePanelProps {
  trace: A2ATraceStep[];
  provenance: GcpProvenance | null;
  isPending: boolean;
}

function Working() {
  const [lang] = useLang();
  const WORKING = STRINGS[lang].working;
  const eyebrow = STRINGS[lang].workingEyebrow;
  const [i, setI] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setI((v) => (v + 1) % WORKING.length), 2600);
    return () => clearInterval(id);
  }, [WORKING.length]);
  return (
    <div className="card mt-6 overflow-hidden">
      <div className="shimmer h-1 w-full bg-paper-deep" />
      <div className="grid gap-4 p-6 md:grid-cols-[1fr_auto] md:items-center">
        <div className="min-h-[52px]">
          <p className="eyebrow">{eyebrow}</p>
          <AnimatePresence mode="wait">
            <motion.p
              key={i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.5, ease: EASE }}
              className="mt-2 font-serif text-2xl"
            >
              {WORKING[i]}
            </motion.p>
          </AnimatePresence>
        </div>
        <div className="flex gap-1.5">
          {WORKING.map((_, k) => (
            <span key={k} className={`h-1.5 w-6 rounded-full transition-colors duration-500 ${k <= i ? 'bg-accent' : 'bg-line'}`} />
          ))}
        </div>
      </div>
    </div>
  );
}

export function ExecutionTracePanel({ trace, provenance, isPending }: ExecutionTracePanelProps) {
  const reduce = useReducedMotion();
  const [lang] = useLang();
  const t = STRINGS[lang];
  return (
    <section aria-labelledby="trace-panel-heading" data-demo="trace">
      <div className="flex flex-wrap items-end justify-between gap-3 border-t border-ink pt-5">
        <div>
          <p className="eyebrow">{t.liveDelegation}</p>
          <h2 id="trace-panel-heading" className="mt-2 text-2xl font-medium tracking-tight md:text-3xl">
            {t.traceTitle}
          </h2>
        </div>
        {isPending ? (
          <span className="inline-flex items-center gap-2 font-mono text-[11px] text-accent">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent motion-reduce:animate-none" />
            {t.executing}
          </span>
        ) : trace.length > 0 ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-ok-soft px-3 py-1 text-xs font-medium text-ok">
            <Check className="h-3.5 w-3.5" aria-hidden="true" /> {trace.length} {t.hopsRecorded}
          </span>
        ) : null}
      </div>

      {isPending ? <Working /> : null}

      {!isPending && trace.length > 0 ? (
        <ol className="relative mt-8 space-y-0" aria-label="A2A execution steps">
          <span className="absolute bottom-6 left-[15px] top-6 w-px bg-line-strong" aria-hidden="true" />
          {trace.map((step, idx) => {
            const ok = step.status.toUpperCase() === 'SUCCESS';
            return (
              <motion.li
                key={`${step.step}-${step.target}`}
                initial={reduce ? false : { opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.7, ease: EASE, delay: idx * 0.12 }}
                className="relative grid grid-cols-[32px_1fr] gap-4 pb-6"
              >
                <span className="relative z-10 flex h-[31px] w-[31px] items-center justify-center rounded-full border border-ink bg-card font-mono text-[11px]">
                  {step.step}
                </span>
                <div className="card p-4 sm:p-5">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div className="flex flex-wrap items-center gap-2 font-mono text-sm">
                      <span className="text-ink-muted">{step.caller}</span>
                      <ArrowRight className="h-3.5 w-3.5 text-ink-faint" aria-hidden="true" />
                      <span className="font-medium text-ink">{step.target}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] text-ink-muted">
                      <span>{step.protocol}</span>
                      <span>{step.auth}</span>
                      <span className="text-ink">{(step.latency_ms / 1000).toFixed(1)} s</span>
                      <span className={`inline-flex items-center gap-1 ${ok ? 'text-ok' : 'text-bad'}`}>
                        {ok ? <Check className="h-3 w-3" aria-hidden="true" /> : <X className="h-3 w-3" aria-hidden="true" />}
                        {step.status}
                      </span>
                    </div>
                  </div>
                  {step.mcp_tools.length > 0 ? (
                    <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-line pt-3">
                      <span className="eyebrow mr-1 !text-[10px]">{t.mcpTools}</span>
                      {step.mcp_tools.map((tool) => (
                        <code key={tool} className="rounded-full border border-line px-2.5 py-0.5 font-mono text-[11px] text-ink-soft">
                          {tool}
                        </code>
                      ))}
                    </div>
                  ) : null}
                </div>
              </motion.li>
            );
          })}
        </ol>
      ) : null}

      {!isPending && trace.length === 0 ? (
        <p className="mt-6 max-w-2xl text-[15px] leading-relaxed text-ink-muted">
          {t.traceEmpty}
        </p>
      ) : null}

      {provenance && !isPending ? (
        <motion.dl
          initial={reduce ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.3 }}
          className="mt-2 grid gap-px overflow-hidden rounded-[14px] border border-line bg-line sm:grid-cols-2 lg:grid-cols-4"
        >
          {[
            [t.prov[0], `${provenance.vertex_ai_model} (${provenance.vertex_ai_location})`],
            [t.prov[1], provenance.gcs_bucket],
            [t.prov[2], provenance.secret_manager_policy],
            [t.prov[3], provenance.report_gcs_uri ?? t.notPersisted],
          ].map(([k, v]) => (
            <div key={k} className="bg-card p-4">
              <dt className="eyebrow !text-[10px]">{k}</dt>
              <dd className="mt-1.5 break-all font-mono text-xs text-ink">{v}</dd>
            </div>
          ))}
        </motion.dl>
      ) : null}
    </section>
  );
}
