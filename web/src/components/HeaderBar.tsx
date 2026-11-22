'use client';

import { RefreshCw, ShieldCheck, ShieldAlert, Cpu } from 'lucide-react';
import type { HealthResponse } from '@/lib/types';

interface HeaderBarProps {
  health: HealthResponse | null;
  healthLoading: boolean;
  onRefreshHealth: () => void;
  postureExpanded: boolean;
  onTogglePosture: () => void;
}

export function HeaderBar({
  health,
  healthLoading,
  onRefreshHealth,
  postureExpanded,
  onTogglePosture,
}: HeaderBarProps) {
  const isOk = health?.status === 'ok';
  const authModeLabel =
    health?.bff.auth_mode === 'oidc-sa'
      ? 'OIDC Service Account'
      : health?.bff.auth_mode === 'local-dev'
        ? 'Local Dev Proxy'
        : health
          ? 'Unconfigured'
          : 'Checking…';

  return (
    <header className="border-b border-slate-800 bg-[#0D1320]/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
        <div className="flex items-start gap-3.5">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-sky-500/30 bg-sky-500/10 text-sky-300">
            <Cpu className="h-6 w-6" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-slate-50 sm:text-2xl">
              Enterprise Multi-Agent Risk &amp; Compliance Console
            </h1>
            <p className="mt-1 text-sm text-slate-300">
              Google ADK 2.15 · A2A v1.0 · Stdio MCP 2.3.0 · Vertex AI{' '}
              <span className="font-mono text-sky-300">gemini-3.8-flash</span>{' '}
              <span className="text-slate-400">(global)</span>
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div
            role="status"
            aria-live="polite"
            className={`inline-flex min-h-[48px] items-center gap-2.5 rounded-lg border px-3.5 py-2 text-sm font-medium ${
              isOk
                ? 'border-emerald-500/40 bg-emerald-950/60 text-emerald-200'
                : 'border-amber-500/40 bg-amber-950/60 text-amber-200'
            }`}
          >
            {isOk ? (
              <ShieldCheck className="h-4 w-4 shrink-0 text-emerald-300" aria-hidden="true" />
            ) : (
              <ShieldAlert className="h-4 w-4 shrink-0 text-amber-300" aria-hidden="true" />
            )}
            <span>
              BFF: {isOk ? 'Connected' : health ? 'Degraded' : 'Checking'} · {authModeLabel}
            </span>
          </div>

          <button
            type="button"
            onClick={onRefreshHealth}
            disabled={healthLoading}
            aria-label="Refresh BFF and Cloud Run orchestrator health status"
            className="inline-flex min-h-[48px] items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-100 transition-colors hover:border-slate-500 hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#090D16] disabled:cursor-not-allowed disabled:opacity-60 motion-reduce:transition-none"
          >
            <RefreshCw
              className={`h-4 w-4 ${healthLoading ? 'animate-spin motion-reduce:animate-none' : ''}`}
              aria-hidden="true"
            />
            <span>Refresh Health</span>
          </button>

          <button
            type="button"
            onClick={onTogglePosture}
            aria-expanded={postureExpanded}
            aria-controls="security-posture-drawer"
            className="inline-flex min-h-[48px] items-center gap-2 rounded-lg border border-sky-500/40 bg-sky-950/50 px-4 py-2 text-sm font-medium text-sky-100 transition-colors hover:border-sky-400 hover:bg-sky-900/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#090D16] motion-reduce:transition-none"
          >
            <ShieldCheck className="h-4 w-4 text-sky-300" aria-hidden="true" />
            <span>{postureExpanded ? 'Hide Security Posture' : 'Architecture & Security Posture'}</span>
          </button>
        </div>
      </div>
    </header>
  );
}
