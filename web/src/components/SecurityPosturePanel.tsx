'use client';

import { Lock, Server, Shield, DollarSign, ArrowRight, CheckCircle2 } from 'lucide-react';
import type { HealthResponse, SecurityPosture } from '@/lib/types';

interface SecurityPosturePanelProps {
  expanded: boolean;
  health: HealthResponse | null;
  posture: SecurityPosture | null;
}

const ARCHITECTURE_HOPS = [
  {
    id: 'browser',
    title: '1. Browser (Chrome)',
    subtitle: 'Next.js App Router UI',
    detail: 'Zero GCP credentials · Zero client-side env vars',
  },
  {
    id: 'bff',
    title: '2. Vercel OIDC BFF',
    subtitle: 'Node.js Fluid Compute (/api/analyze)',
    detail: 'google-auth-library getIdTokenClient(aud)',
  },
  {
    id: 'orchestrator',
    title: '3. Private Cloud Run IAM',
    subtitle: 'adk-orchestrator (NO allUsers)',
    detail: 'min_instances=0 · max_instances=2 ($0 Idle Cost)',
  },
  {
    id: 'a2a',
    title: '4. A2A v1.0 + OIDC',
    subtitle: 'adk-financial-agent & adk-compliance-agent',
    detail: 'CloudRunOidcAuth per-agent audience verification',
  },
  {
    id: 'mcp',
    title: '5. Stdio MCPServer',
    subtitle: 'GCS · Secret Manager · Vertex AI',
    detail: 'gemini-3.8-flash (global) · adk-compliance-policy-rules',
  },
] as const;

export function SecurityPosturePanel({
  expanded,
  health,
  posture,
}: SecurityPosturePanelProps) {
  const minInstances = posture?.min_instances ?? 0;
  const maxInstances = posture?.max_instances ?? 2;
  const iamMode = posture?.cloud_run_iam ?? 'private-oidc-enforced';

  return (
    <section
      id="security-posture-drawer"
      aria-labelledby="security-posture-heading"
      className="rounded-2xl border border-slate-800 bg-[#111827] p-5 shadow-lg"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2.5">
          <Shield className="h-5 w-5 text-emerald-300" aria-hidden="true" />
          <h2 id="security-posture-heading" className="text-lg font-semibold text-slate-50">
            Zero-Trust Architecture &amp; Security Posture
          </h2>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-950/60 px-3 py-1 text-xs font-semibold text-emerald-200">
            <Lock className="h-3.5 w-3.5" aria-hidden="true" />
            <span>IAM: {iamMode}</span>
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-500/40 bg-sky-950/60 px-3 py-1 text-xs font-semibold text-sky-200">
            <DollarSign className="h-3.5 w-3.5" aria-hidden="true" />
            <span>
              min_instances={minInstances}, max_instances={maxInstances} ($0 Idle Cost)
            </span>
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs font-medium text-slate-200">
            <Server className="h-3.5 w-3.5 text-slate-300" aria-hidden="true" />
            <span>
              Orchestrator: {health?.orchestrator?.status === 'ok' ? 'Reachable via BFF' : 'Private Cloud Run'}
            </span>
          </span>
        </div>
      </div>

      {expanded ? (
        <div className="mt-5 space-y-4">
          <p className="text-sm text-slate-300">
            Every browser request hits the server-side Vercel Node.js Fluid Compute BFF, which mints a short-lived
            Google-signed OIDC ID token scoped strictly to the private Cloud Run orchestrator audience. Unauthenticated
            direct calls to any Cloud Run service fail closed with <code className="font-mono text-amber-300">401/403</code>.
          </p>

          <div className="grid gap-3 md:grid-cols-5">
            {ARCHITECTURE_HOPS.map((hop, index) => (
              <div
                key={hop.id}
                className="relative flex flex-col justify-between rounded-xl border border-slate-800 bg-[#0B101B] p-3.5"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="text-sm font-semibold text-slate-100">{hop.title}</h3>
                    {index < ARCHITECTURE_HOPS.length - 1 ? (
                      <ArrowRight className="hidden h-4 w-4 text-sky-400 md:block" aria-hidden="true" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4 text-emerald-400" aria-hidden="true" />
                    )}
                  </div>
                  <p className="mt-1 font-mono text-xs text-sky-300">{hop.subtitle}</p>
                </div>
                <p className="mt-2.5 text-xs leading-relaxed text-slate-300">{hop.detail}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
