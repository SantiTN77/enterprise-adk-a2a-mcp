from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import google.auth
import httpx
from google.auth import impersonated_credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token as google_id_token
from google.oauth2 import service_account


def _rewrite_gfe_reserved_healthz(url: str) -> str:
    """Google Frontend (GFE) on *.run.app intercepts `/healthz` directly at the edge with 404.
    For live *.run.app URLs, rewrite `/healthz` to `/health` so requests reach Cloud Run IAM and FastAPI.
    """
    parsed = urlparse(url)
    if (parsed.hostname or "").lower().endswith(".run.app") and parsed.path == "/healthz":
        return f"{parsed.scheme}://{parsed.netloc}/health"
    return url


def _audience_for_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Cannot derive OIDC audience from URL: {url!r}")
    return f"{parsed.scheme}://{parsed.netloc}"


def _load_sa_info(raw_or_path: str) -> dict[str, Any]:
    candidate = raw_or_path.strip()
    if candidate.startswith("{"):
        return json.loads(candidate)
    path = Path(candidate)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"Service account JSON path does not exist: {candidate!r}")


@dataclass
class OidcTokenMinter:
    """Mints Google Cloud Run OIDC ID tokens with exact base URL audience."""

    sa_key_json: str | None = None
    agent_sa_key_json: str | None = None
    impersonate_sa: str | None = None
    agent_impersonate_sa: str | None = None
    custom_minter: Callable[[str], str] | None = None
    _cache: dict[str, tuple[str, float]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._cache = {}

    @classmethod
    def from_env(cls) -> "OidcTokenMinter":
        sa_key = (
            os.environ.get("GCP_SA_KEY_JSON", "").strip()
            or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
            or None
        )
        agent_sa_key = (
            os.environ.get("E2E_AGENT_SA_KEY_JSON", "").strip()
            or None
        )
        impersonate_sa = os.environ.get("E2E_IMPERSONATE_SA", "").strip() or None
        agent_impersonate_sa = (
            os.environ.get("E2E_AGENT_IMPERSONATE_SA", "").strip()
            or impersonate_sa
        )
        return cls(
            sa_key_json=sa_key,
            agent_sa_key_json=agent_sa_key,
            impersonate_sa=impersonate_sa,
            agent_impersonate_sa=agent_impersonate_sa,
        )

    def mint_id_token(
        self,
        audience: str,
        *,
        for_specialized_agent: bool = False,
        force_refresh: bool = False,
        preserve_audience: bool = False,
    ) -> str:
        aud = audience if preserve_audience else audience.rstrip("/")
        if self.custom_minter is not None:
            return self.custom_minter(aud)

        target_sa = self.agent_impersonate_sa if for_specialized_agent else self.impersonate_sa
        active_key = (
            (self.agent_sa_key_json or self.sa_key_json)
            if for_specialized_agent
            else self.sa_key_json
        )
        cache_key = f"{aud}|{target_sa or active_key or 'default'}|{'agent' if for_specialized_agent else 'orch'}"
        now = time.monotonic()
        if not force_refresh and cache_key in self._cache:
            token, expires_at = self._cache[cache_key]
            if now < expires_at:
                return token

        token = self._mint_uncached(aud, target_sa=target_sa, sa_key=active_key)
        # Cloud Run OIDC ID tokens are valid for 1 hour; cache for 45 minutes.
        self._cache[cache_key] = (token, now + 2700.0)
        return token

    def _mint_uncached(self, audience: str, *, target_sa: str | None, sa_key: str | None = None) -> str:
        errors: list[str] = []

        # 1. Service Account JSON key (raw JSON or file path)
        effective_key = sa_key if sa_key is not None else self.sa_key_json
        if effective_key:
            try:
                info = _load_sa_info(effective_key)
                creds = service_account.IDTokenCredentials.from_service_account_info(
                    info, target_audience=audience
                )
                creds.refresh(GoogleAuthRequest())
                if creds.token:
                    return creds.token
            except Exception as exc:  # noqa: BLE001
                errors.append(f"SA key mint failed: {exc}")

        # 2. Service Account impersonation via ADC
        if target_sa:
            try:
                source_creds, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                target_creds = impersonated_credentials.Credentials(
                    source_credentials=source_creds,
                    target_principal=target_sa,
                    target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
                    lifetime=3600,
                )
                id_creds = impersonated_credentials.IDTokenCredentials(
                    target_credentials=target_creds,
                    target_audience=audience,
                    include_email=True,
                )
                id_creds.refresh(GoogleAuthRequest())
                if id_creds.token:
                    return id_creds.token
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Impersonated SA ({target_sa}) failed: {exc}")

        # 3. Standard google.oauth2.id_token.fetch_id_token (works on GCE/Cloud Run metadata or SA ADC)
        try:
            token = google_id_token.fetch_id_token(GoogleAuthRequest(), audience)
            if token:
                return token
        except Exception as exc:  # noqa: BLE001
            errors.append(f"fetch_id_token failed: {exc}")

        # 4. gcloud CLI fallback (Windows gcloud.ps1 / gcloud.cmd / gcloud)
        gcloud_bin = (
            shutil.which("gcloud.cmd")
            or shutil.which("gcloud.ps1")
            or shutil.which("gcloud")
        )
        if gcloud_bin:
            cmd: list[str]
            if gcloud_bin.lower().endswith(".ps1"):
                cmd = [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    gcloud_bin,
                ]
            else:
                cmd = [gcloud_bin]
            cmd.extend(["auth", "print-identity-token", f"--audiences={audience}"])
            if target_sa:
                cmd.append(f"--impersonate-service-account={target_sa}")
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
                stdout_tok = proc.stdout.strip()
                if proc.returncode == 0 and stdout_tok.count(".") == 2:
                    return stdout_tok
                errors.append(
                    f"gcloud exit={proc.returncode} stderr={proc.stderr.strip()[:200]}"
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"gcloud invocation failed: {exc}")

        raise RuntimeError(
            f"Unable to mint OIDC ID token for audience {audience!r}. Attempts: {'; '.join(errors)}"
        )


class OidcHttpClient:
    """Synchronous httpx wrapper supporting OIDC Bearer auth and unauthenticated probes."""

    def __init__(
        self,
        minter: OidcTokenMinter | None = None,
        *,
        default_timeout: float = 30.0,
        analyze_timeout: float = 120.0,
    ) -> None:
        self.minter = minter or OidcTokenMinter.from_env()
        self.default_timeout = default_timeout
        self.analyze_timeout = analyze_timeout
        self._client = httpx.Client(follow_redirects=False)

    def close(self) -> None:
        self._client.close()

    def request_raw(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: Any = None,
        content: bytes | str | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        effective_url = _rewrite_gfe_reserved_healthz(url)
        return self._client.request(
            method,
            effective_url,
            headers=headers,
            json=json_body,
            content=content,
            timeout=timeout or self.default_timeout,
        )

    def request_authenticated(
        self,
        method: str,
        base_url: str,
        path: str = "/",
        *,
        audience: str | None = None,
        for_specialized_agent: bool = False,
        headers: dict[str, str] | None = None,
        json_body: Any = None,
        content: bytes | str | None = None,
        timeout: float | None = None,
        retry_cold_start: bool = True,
    ) -> httpx.Response:
        aud = audience if audience is not None else _audience_for_url(base_url)
        token = self.minter.mint_id_token(aud, for_specialized_agent=for_specialized_agent)
        req_headers = dict(headers or {})
        req_headers["Authorization"] = f"Bearer {token}"

        target_url = _rewrite_gfe_reserved_healthz(f"{base_url.rstrip('/')}{path}")
        effective_timeout = timeout or self.default_timeout
        attempts = 2 if retry_cold_start else 1
        last_exc: Exception | None = None

        for attempt in range(attempts):
            try:
                resp = self._client.request(
                    method,
                    target_url,
                    headers=req_headers,
                    json=json_body,
                    content=content,
                    timeout=effective_timeout,
                )
                # Never retry 401/403 IAM errors; only retry transient 503/504 cold-start glitches.
                if resp.status_code in {503, 504} and attempt + 1 < attempts:
                    time.sleep(2.0)
                    continue
                return resp
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt + 1 < attempts:
                    time.sleep(2.0)
                    continue
                raise
        assert last_exc is not None
        raise last_exc
