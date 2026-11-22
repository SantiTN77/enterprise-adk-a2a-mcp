import 'server-only';
import { GoogleAuth, type IdTokenClient } from 'google-auth-library';
import {
  BffConfigError,
  BffUpstreamError,
  resolveTarget,
  sanitizeErrorText,
  type BffTarget,
  type ServiceAccountCredentials,
} from './bff-config';

export { BffConfigError, BffUpstreamError, sanitizeErrorText };

const clientCache = new Map<string, Promise<IdTokenClient>>();

async function getCachedIdTokenClient(
  targetAudience: string,
  credentials: ServiceAccountCredentials,
): Promise<IdTokenClient> {
  const cacheKey = `${targetAudience}|${credentials.client_email}`;
  const existing = clientCache.get(cacheKey);
  if (existing) {
    return existing;
  }

  const pending = (async () => {
    const auth = new GoogleAuth({
      credentials: {
        client_email: credentials.client_email,
        private_key: credentials.private_key,
      },
    });
    return auth.getIdTokenClient(targetAudience);
  })();

  clientCache.set(cacheKey, pending);

  try {
    return await pending;
  } catch (err) {
    clientCache.delete(cacheKey);
    throw err;
  }
}

export function inspectBffConfiguration(): {
  configured: boolean;
  authMode: 'oidc-sa' | 'local-dev' | 'unconfigured';
  error?: string;
} {
  try {
    const target = resolveTarget();
    return {
      configured: true,
      authMode: target.mode,
    };
  } catch (err) {
    return {
      configured: false,
      authMode: 'unconfigured',
      error: err instanceof Error ? sanitizeErrorText(err.message) : 'BFF configuration incomplete',
    };
  }
}

export interface CallOrchestratorOptions {
  method?: 'GET' | 'POST';
  body?: string;
  timeoutMs?: number;
}

export async function callOrchestrator<T>(
  path: `/${string}`,
  options: CallOrchestratorOptions = {},
): Promise<{ data: T; targetMode: BffTarget['mode'] }> {
  const target = resolveTarget();
  const targetUrl = `${target.baseUrl}${path}`;
  const method = options.method ?? 'GET';
  const timeoutMs = options.timeoutMs ?? 15_000;

  let headers: Headers;
  if (target.mode === 'oidc-sa') {
    let client: IdTokenClient;
    try {
      client = await getCachedIdTokenClient(target.baseUrl, target.credentials);
    } catch (err) {
      const detail = err instanceof Error ? sanitizeErrorText(err.message) : 'OIDC client init failed';
      throw new BffUpstreamError(502, 'OIDC_INIT_FAILED', `Failed to initialize OIDC client: ${detail}`);
    }

    try {
      // google-auth-library@11 returns a Web Fetch Headers instance (not a plain object)
      const authHeaders = await client.getRequestHeaders(targetUrl);
      headers = new Headers(authHeaders);
    } catch (err) {
      clientCache.delete(`${target.baseUrl}|${target.credentials.client_email}`);
      const detail = err instanceof Error ? sanitizeErrorText(err.message) : 'OIDC token minting failed';
      throw new BffUpstreamError(502, 'OIDC_TOKEN_FAILED', `Failed to mint Cloud Run OIDC token: ${detail}`);
    }
  } else {
    headers = new Headers();
  }

  headers.set('Accept', 'application/json');
  if (options.body !== undefined) {
    headers.set('Content-Type', 'application/json');
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(targetUrl, {
      method,
      headers,
      body: options.body,
      cache: 'no-store',
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if (err instanceof Error && err.name === 'AbortError') {
      throw new BffUpstreamError(
        504,
        'UPSTREAM_TIMEOUT',
        `Orchestrator timed out after ${Math.round(timeoutMs / 1000)}s`,
      );
    }
    const detail = err instanceof Error ? sanitizeErrorText(err.message) : 'Network failure';
    throw new BffUpstreamError(502, 'UPSTREAM_UNREACHABLE', `Orchestrator unreachable: ${detail}`);
  } finally {
    clearTimeout(timer);
  }

  const rawText = await response.text();
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      throw new BffUpstreamError(
        502,
        'UPSTREAM_IAM_REJECTED',
        'Upstream Cloud Run IAM rejected OIDC authentication',
      );
    }
    const safeDetail = sanitizeErrorText(rawText || `HTTP ${response.status}`);
    const mappedStatus = response.status >= 400 && response.status < 500 ? response.status : 502;
    throw new BffUpstreamError(
      mappedStatus,
      'UPSTREAM_ERROR',
      `Orchestrator returned HTTP ${response.status}: ${safeDetail}`,
    );
  }

  try {
    const data = JSON.parse(rawText) as T;
    return { data, targetMode: target.mode };
  } catch {
    throw new BffUpstreamError(502, 'UPSTREAM_INVALID_JSON', 'Orchestrator returned non-JSON payload');
  }
}
