import assert from 'node:assert/strict';
import { generateKeyPairSync } from 'node:crypto';
import test from 'node:test';
import { GoogleAuth } from 'google-auth-library';
import {
  BffConfigError,
  normalizeBaseUrl,
  normalizePrivateKey,
  resolveTarget,
  sanitizeErrorText,
} from '../../src/lib/bff-config.ts';

const { privateKey: TEST_PEM } = generateKeyPairSync('rsa', {
  modulusLength: 2048,
  privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
  publicKeyEncoding: { type: 'spki', format: 'pem' },
});

test('normalizeBaseUrl strips trailing slashes and enforces origin-only URLs', () => {
  assert.equal(
    normalizeBaseUrl('https://adk-orchestrator-xyz-uc.a.run.app///'),
    'https://adk-orchestrator-xyz-uc.a.run.app',
  );
  assert.throws(
    () => normalizeBaseUrl('http://adk-orchestrator-xyz-uc.a.run.app'),
    BffConfigError,
  );
  assert.throws(
    () => normalizeBaseUrl('https://adk-orchestrator-xyz-uc.a.run.app/v1'),
    BffConfigError,
  );
});

test('normalizePrivateKey unescapes literal \\n and strips surrounding quotes', () => {
  const escaped = `"${TEST_PEM.replace(/\n/g, '\\n')}"`;
  const normalized = normalizePrivateKey(escaped);
  assert.equal(normalized, TEST_PEM.trim());
  assert.throws(() => normalizePrivateKey('not-a-pem-key'), BffConfigError);
});

test('resolveTarget blocks LOCAL_DEV_ORCHESTRATOR_URL in production and Vercel', () => {
  const prodEnv = {
    NODE_ENV: 'production',
    LOCAL_DEV_ORCHESTRATOR_URL: 'http://127.0.0.1:8080',
  };
  assert.throws(() => resolveTarget(prodEnv), /CLOUD_RUN_ORCHESTRATOR_URL/);

  const vercelEnv = {
    NODE_ENV: 'development',
    VERCEL: '1',
    LOCAL_DEV_ORCHESTRATOR_URL: 'http://127.0.0.1:8080',
  };
  assert.throws(() => resolveTarget(vercelEnv), /CLOUD_RUN_ORCHESTRATOR_URL/);

  const nonLocalDevEnv = {
    NODE_ENV: 'development',
    LOCAL_DEV_ORCHESTRATOR_URL: 'http://example.com:8080',
  };
  assert.throws(() => resolveTarget(nonLocalDevEnv), /restricted to localhost/);

  const validLocalEnv = {
    NODE_ENV: 'development',
    LOCAL_DEV_ORCHESTRATOR_URL: 'http://127.0.0.1:18080/',
  };
  assert.deepEqual(resolveTarget(validLocalEnv), {
    mode: 'local-dev',
    baseUrl: 'http://127.0.0.1:18080',
  });
});

test('resolveTarget resolves oidc-sa from split env vars and JSON fallback', () => {
  const splitTarget = resolveTarget({
    NODE_ENV: 'production',
    CLOUD_RUN_ORCHESTRATOR_URL: 'https://adk-orchestrator-test.a.run.app/',
    GCP_CLIENT_EMAIL: 'vercel-bff-invoker@gen-lang-client-0527325883.iam.gserviceaccount.com',
    GCP_PRIVATE_KEY: TEST_PEM.replace(/\n/g, '\\n'),
  });
  assert.equal(splitTarget.mode, 'oidc-sa');
  assert.equal(splitTarget.baseUrl, 'https://adk-orchestrator-test.a.run.app');

  const jsonTarget = resolveTarget({
    NODE_ENV: 'production',
    CLOUD_RUN_ORCHESTRATOR_URL: 'https://adk-orchestrator-test.a.run.app',
    GCP_SERVICE_ACCOUNT_KEY: JSON.stringify({
      client_email: 'vercel-bff-invoker@gen-lang-client-0527325883.iam.gserviceaccount.com',
      private_key: TEST_PEM,
    }),
  });
  assert.equal(jsonTarget.mode, 'oidc-sa');
  assert.equal(jsonTarget.credentials.private_key, TEST_PEM.trim());
});

test('sanitizeErrorText redacts JWTs, Bearer tokens, and full PEM keys', () => {
  const dirty = `Auth failed Bearer eyJhbGciOiJSUzI1NiJ9.eyJhdWQiOiJodHRwcyJ9.sig123 raw=Bearer opaque-secret-token key=${TEST_PEM}`;
  const clean = sanitizeErrorText(dirty);
  assert.ok(!clean.includes('eyJhbGci'));
  assert.ok(!clean.includes('opaque-secret-token'));
  assert.ok(!clean.includes('BEGIN PRIVATE KEY'));
  assert.ok(!clean.includes('END PRIVATE KEY'));
  assert.ok(!clean.includes(TEST_PEM.split('\n')[1]));
  assert.ok(clean.includes('[REDACTED_JWT]'));
  assert.ok(clean.includes('Bearer [REDACTED]'));
  assert.ok(clean.includes('[REDACTED_PRIVATE_KEY]'));
});

test('google-auth-library getIdTokenClient initializes with normalized target audience and wraps Headers cleanly', async () => {
  const auth = new GoogleAuth({
    credentials: {
      client_email: 'vercel-bff-invoker@gen-lang-client-0527325883.iam.gserviceaccount.com',
      private_key: TEST_PEM,
    },
  });
  const client = await auth.getIdTokenClient('https://adk-orchestrator-test.a.run.app');
  assert.equal(client.targetAudience, 'https://adk-orchestrator-test.a.run.app');

  // Verify Web Fetch Headers wrapper preserves entries (unlike object spread `{ ...headers }`)
  const sample = new Headers({ Authorization: 'Bearer test-token' });
  assert.deepEqual({ ...sample }, {});
  const wrapped = new Headers(sample);
  assert.equal(wrapped.get('authorization'), 'Bearer test-token');
});
