export interface ServiceAccountCredentials {
  client_email: string;
  private_key: string;
}

export type BffTarget =
  | {
      mode: 'local-dev';
      baseUrl: string;
    }
  | {
      mode: 'oidc-sa';
      baseUrl: string;
      credentials: ServiceAccountCredentials;
    };

export class BffConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'BffConfigError';
  }
}

export class BffUpstreamError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'BffUpstreamError';
    this.status = status;
    this.code = code;
  }
}

const LOCALHOST_HOSTNAMES = new Set(['localhost', '127.0.0.1', '::1', '[::1]']);

export function sanitizeErrorText(input: string): string {
  return input
    .replace(
      /-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|$)/g,
      '[REDACTED_PRIVATE_KEY]',
    )
    .replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[REDACTED_JWT]')
    .replace(/"private_key"\s*:\s*"[^"]*"/g, '"private_key":"[REDACTED]"')
    .replace(/Bearer\s+(?!\[REDACTED)[A-Za-z0-9._-]+/gi, 'Bearer [REDACTED]')
    .slice(0, 600);
}

export function normalizePrivateKey(raw: string): string {
  let cleaned = raw.trim();
  if (
    (cleaned.startsWith('"') && cleaned.endsWith('"')) ||
    (cleaned.startsWith("'") && cleaned.endsWith("'"))
  ) {
    cleaned = cleaned.slice(1, -1);
  }
  const normalized = cleaned.replace(/\\n/g, '\n').trim();
  if (!normalized.includes('-----BEGIN') || !normalized.includes('PRIVATE KEY-----')) {
    throw new BffConfigError('GCP_PRIVATE_KEY is malformed (missing PEM boundaries)');
  }
  return normalized;
}

export function normalizeBaseUrl(rawUrl: string, allowHttpLocalhost = false): string {
  const trimmed = rawUrl.trim().replace(/\/+$/, '');
  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    throw new BffConfigError('Orchestrator URL is not a valid URL');
  }

  const isLocalHost = LOCALHOST_HOSTNAMES.has(parsed.hostname.toLowerCase());
  if (parsed.protocol !== 'https:' && !(allowHttpLocalhost && parsed.protocol === 'http:' && isLocalHost)) {
    throw new BffConfigError('Orchestrator URL must use https://');
  }

  if (parsed.pathname !== '/' && parsed.pathname !== '') {
    throw new BffConfigError('CLOUD_RUN_ORCHESTRATOR_URL must be an origin base URL without path segments');
  }

  return parsed.origin;
}

export function loadCredentialsFromEnv(env: NodeJS.ProcessEnv = process.env): ServiceAccountCredentials {
  const rawEmail = env.GCP_CLIENT_EMAIL?.trim();
  const rawKey = env.GCP_PRIVATE_KEY?.trim();

  if (rawEmail && rawKey) {
    return {
      client_email: rawEmail,
      private_key: normalizePrivateKey(rawKey),
    };
  }

  const rawJson = env.GCP_SERVICE_ACCOUNT_KEY?.trim();
  if (rawJson) {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(rawJson) as Record<string, unknown>;
    } catch {
      throw new BffConfigError('GCP_SERVICE_ACCOUNT_KEY is not valid JSON');
    }
    const email = typeof parsed.client_email === 'string' ? parsed.client_email.trim() : '';
    const key = typeof parsed.private_key === 'string' ? parsed.private_key.trim() : '';
    if (!email || !key) {
      throw new BffConfigError('GCP_SERVICE_ACCOUNT_KEY must contain client_email and private_key');
    }
    return {
      client_email: email,
      private_key: normalizePrivateKey(key),
    };
  }

  throw new BffConfigError(
    'BFF OIDC credentials are not configured (set GCP_CLIENT_EMAIL + GCP_PRIVATE_KEY or GCP_SERVICE_ACCOUNT_KEY)',
  );
}

export function resolveTarget(env: NodeJS.ProcessEnv = process.env): BffTarget {
  const isProdRuntime = env.NODE_ENV === 'production' || Boolean(env.VERCEL);
  const localDevRaw = env.LOCAL_DEV_ORCHESTRATOR_URL?.trim();

  if (!isProdRuntime && localDevRaw) {
    let parsed: URL;
    try {
      parsed = new URL(localDevRaw.replace(/\/+$/, ''));
    } catch {
      throw new BffConfigError('LOCAL_DEV_ORCHESTRATOR_URL is not a valid URL');
    }
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      throw new BffConfigError('LOCAL_DEV_ORCHESTRATOR_URL must use http:// or https://');
    }
    if (!LOCALHOST_HOSTNAMES.has(parsed.hostname.toLowerCase())) {
      throw new BffConfigError('LOCAL_DEV_ORCHESTRATOR_URL is restricted to localhost / 127.0.0.1 / ::1');
    }
    if (parsed.pathname !== '/' && parsed.pathname !== '') {
      throw new BffConfigError('LOCAL_DEV_ORCHESTRATOR_URL must be an origin base URL without path segments');
    }
    return {
      mode: 'local-dev',
      baseUrl: parsed.origin,
    };
  }

  const cloudRunRaw = env.CLOUD_RUN_ORCHESTRATOR_URL?.trim();
  if (!cloudRunRaw) {
    throw new BffConfigError('CLOUD_RUN_ORCHESTRATOR_URL is not configured');
  }

  const baseUrl = normalizeBaseUrl(cloudRunRaw, !isProdRuntime);
  const credentials = loadCredentialsFromEnv(env);

  return {
    mode: 'oidc-sa',
    baseUrl,
    credentials,
  };
}
