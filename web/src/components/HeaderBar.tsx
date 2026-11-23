'use client';

import { RefreshCw } from 'lucide-react';

function GithubMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" className={className} aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}
import type { HealthResponse } from '@/lib/types';

interface HeaderBarProps {
  health: HealthResponse | null;
  healthLoading: boolean;
  onRefreshHealth: () => void;
  postureExpanded: boolean;
  onTogglePosture: () => void;
}

export function HeaderBar({ health, healthLoading, onRefreshHealth, postureExpanded, onTogglePosture }: HeaderBarProps) {
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
    <header className="sticky top-0 z-30 border-b border-line bg-paper/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1280px] items-center justify-between gap-4 px-5 sm:px-8">
        <h1 className="truncate text-[15px] font-medium tracking-tight">
          Multi-Agent Risk <span className="font-serif text-lg italic text-accent">&amp;</span> Compliance Console
        </h1>

        <div className="flex items-center gap-2 text-xs sm:gap-3">
          <div role="status" aria-live="polite" className="hidden items-center gap-2 text-ink-muted md:inline-flex">
            <span className="relative flex h-2 w-2">
              {isOk ? <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ok/50" /> : null}
              <span className={`relative inline-flex h-2 w-2 rounded-full ${isOk ? 'bg-ok' : 'bg-warn'}`} />
            </span>
            <span>
              BFF: {isOk ? 'Connected' : health ? 'Degraded' : 'Checking'} · {authModeLabel}
            </span>
          </div>

          <button
            type="button"
            onClick={onRefreshHealth}
            disabled={healthLoading}
            aria-label="Refresh BFF and Cloud Run orchestrator health status"
            className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-line-strong text-ink transition-colors hover:border-ink disabled:opacity-60"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${healthLoading ? 'animate-spin motion-reduce:animate-none' : ''}`} aria-hidden="true" />
          </button>

          <button
            type="button"
            onClick={onTogglePosture}
            aria-expanded={postureExpanded}
            aria-controls="security-posture-drawer"
            className="hidden rounded-full border border-line-strong px-3 py-1.5 text-ink transition-colors hover:border-ink sm:inline-flex"
          >
            {postureExpanded ? 'Hide Security Posture' : 'Architecture & Security Posture'}
          </button>

          <a
            href="https://github.com/SantiTN77/enterprise-adk-a2a-mcp"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-full bg-ink px-3 py-1.5 text-paper"
          >
            <GithubMark className="h-3.5 w-3.5" /> Source
          </a>
        </div>
      </div>
    </header>
  );
}
