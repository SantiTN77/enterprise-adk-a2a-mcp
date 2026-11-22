'use client';

import { Activity, ArrowRight, CheckCircle2, Clock, Database, KeyRound, Sparkles, XCircle } from 'lucide-react';
import type { A2ATraceStep, GcpProvenance } from '@/lib/types';

interface ExecutionTracePanelProps {
  trace: A2ATraceStep[];
  provenance: GcpProvenance | null;
  isPending: boolean;
}

export function ExecutionTracePanel({
  trace,
  provenance,
  isPending,
}: ExecutionTracePanelProps) {
  return (
    <section
      aria-labelledby="trace-panel-heading"
      className="rounded-2xl border border-slate-800 bg-[#111827] p-5 shadow-lg"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <Activity className="h-5 w-5 text-sky-300" aria-hidden="true" />
          <h2 id="trace-panel-heading" className="text-lg font-semibold text-slate-50">
            Multi-Agent A2A &amp; MCP Execution Trace
          </h2>
        </div>

        {isPending ? (
          <span className="inline-flex items-center gap-2 rounded-full border border-sky-500/40 bg-sky-950/60 px-3 py-1 text-xs font-semibold text-sky-200">
            <span className="h-2 w-2 animate-pulse rounded-full bg-sky-400 motion-reduce:animate-none" />
            <span>Executing A2A Delegation…</span>
          </span>
        ) : trace.length > 0 ? (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-950/60 px-3 py-1 text-xs font-semibold text-emerald-200">
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
            <span>{trace.length} A2A Hops Recorded</span>
          </span>
        ) : null}
      </div>

      {trace.length > 0 ? (
        <ol className="mt-4 space-y-3" aria-label="A2A execution steps">
          {trace.map((step) => {
            const isSuccess = step.status.toUpperCase() === 'SUCCESS';
            return (
              <li
                key={`${step.step}-${step.target}`}
                className="rounded-xl border border-slate-800 bg-[#0B101B] p-4"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="inline-flex h-7 min-w-7 items-center justify-center rounded-md bg-sky-500/15 px-2 font-mono text-xs font-bold text-sky-300">
                      #{step.step}
                    </span>
                    <span className="font-mono text-sm font-semibold text-slate-100">{step.caller}</span>
                    <ArrowRight className="h-4 w-4 text-slate-400" aria-hidden="true" />
                    <span className="font-mono text-sm font-semibold text-sky-300">{step.target}</span>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1 font-mono text-xs text-slate-200">
                      {step.protocol}
                    </span>
                    <span className="rounded-md border border-indigo-500/30 bg-indigo-950/60 px-2.5 py-1 font-mono text-xs text-indigo-200">
                      {step.auth}
                    </span>
                    <span className="inline-flex items-center gap-1 rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1 font-mono text-xs text-slate-200">
                      <Clock className="h-3 w-3 text-slate-400" aria-hidden="true" />
                      <span>{step.latency_ms} ms</span>
                    </span>
                    <span
                      className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-semibold ${
                        isSuccess
                          ? 'border-emerald-500/40 bg-emerald-950/60 text-emerald-200'
                          : 'border-red-500/40 bg-red-950/60 text-red-200'
                      }`}
                    >
                      {isSuccess ? (
                        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                      ) : (
                        <XCircle className="h-3.5 w-3.5" aria-hidden="true" />
                      )}
                      <span>{step.status}</span>
                    </span>
                  </div>
                </div>

                {step.mcp_tools.length > 0 ? (
                  <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-800/80 pt-3">
                    <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
                      MCP Tools:
                    </span>
                    {step.mcp_tools.map((tool) => (
                      <code
                        key={tool}
                        className="rounded-md border border-slate-700 bg-slate-900 px-2 py-0.5 font-mono text-xs text-emerald-300"
                      >
                        {tool}
                      </code>
                    ))}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ol>
      ) : (
        <div className="mt-4 rounded-xl border border-dashed border-slate-700 bg-[#0B101B] p-6 text-center">
          <p className="text-sm text-slate-300">
            Select a synthetic enterprise scenario and run an analysis to inspect live A2A delegation hops, OIDC
            token verification, and stdio MCP tool invocations.
          </p>
        </div>
      )}

      {provenance ? (
        <div className="mt-4 rounded-xl border border-slate-800 bg-[#0B101B] p-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            GCP Provenance &amp; Grounding
          </h3>
          <dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
              <dt className="flex items-center gap-1.5 text-xs text-slate-400">
                <Sparkles className="h-3.5 w-3.5 text-sky-300" aria-hidden="true" />
                <span>Vertex AI Model</span>
              </dt>
              <dd className="mt-1 font-mono text-xs font-semibold text-slate-100">
                {provenance.vertex_ai_model} ({provenance.vertex_ai_location})
              </dd>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
              <dt className="flex items-center gap-1.5 text-xs text-slate-400">
                <Database className="h-3.5 w-3.5 text-emerald-300" aria-hidden="true" />
                <span>GCS Bucket</span>
              </dt>
              <dd className="mt-1 break-all font-mono text-xs font-semibold text-slate-100">
                {provenance.gcs_bucket}
              </dd>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
              <dt className="flex items-center gap-1.5 text-xs text-slate-400">
                <KeyRound className="h-3.5 w-3.5 text-amber-300" aria-hidden="true" />
                <span>Secret Manager Policy</span>
              </dt>
              <dd className="mt-1 font-mono text-xs font-semibold text-slate-100">
                {provenance.secret_manager_policy}
              </dd>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
              <dt className="flex items-center gap-1.5 text-xs text-slate-400">
                <Database className="h-3.5 w-3.5 text-sky-300" aria-hidden="true" />
                <span>Persisted Report URI</span>
              </dt>
              <dd className="mt-1 break-all font-mono text-xs text-slate-200">
                {provenance.report_gcs_uri ?? 'Not persisted (dry run)'}
              </dd>
            </div>
          </dl>
        </div>
      ) : null}
    </section>
  );
}
