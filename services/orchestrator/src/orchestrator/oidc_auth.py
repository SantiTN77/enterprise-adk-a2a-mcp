"""Refreshing Google Cloud Run OIDC ID token auth flow for httpx and A2A clients."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable, Generator
from urllib.parse import urlparse

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token as google_id_token

DEFAULT_TOKEN_TTL_SECONDS = 2700.0  # 45 minutes (Google OIDC ID tokens last 60 minutes)


def normalize_audience(base_url: str) -> str:
    """Normalize a Cloud Run service URL to an exact base origin without trailing slash."""
    cleaned = (base_url or "").strip().rstrip("/")
    if not cleaned:
        raise ValueError("Target audience URL cannot be empty.")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise ValueError(f"Invalid audience URL: {base_url!r}")
    return f"{parsed.scheme}://{parsed.netloc}"


def is_cloud_run_oidc_enabled(explicit: bool | None = None) -> bool:
    """Return True when Cloud Run OIDC authentication is enabled."""
    if explicit is not None:
        return explicit
    raw = os.environ.get("ENABLE_CLOUD_RUN_OIDC", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


class CloudRunOidcAuth(httpx.Auth):
    """httpx.Auth implementation that mints and caches Google OIDC ID tokens per target audience."""

    def __init__(
        self,
        target_audience: str,
        *,
        enabled: bool | None = None,
        ttl_seconds: float = DEFAULT_TOKEN_TTL_SECONDS,
        token_fetcher: Callable[[str], str] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.audience = normalize_audience(target_audience)
        self.enabled = is_cloud_run_oidc_enabled(enabled)
        self.ttl_seconds = ttl_seconds
        self._token_fetcher = token_fetcher
        self._clock = clock
        self._lock = threading.Lock()
        self._cached_token: str | None = None
        self._expires_at: float = 0.0

    def _mint_token(self) -> str:
        if self._token_fetcher is not None:
            token = self._token_fetcher(self.audience)
        else:
            token = google_id_token.fetch_id_token(GoogleAuthRequest(), self.audience)
        if not token or not isinstance(token, str):
            raise RuntimeError(f"Failed to mint OIDC ID token for audience {self.audience!r}")
        return token

    def get_id_token(self, *, force_refresh: bool = False) -> str:
        """Return a valid cached OIDC ID token or mint a fresh one."""
        with self._lock:
            now = self._clock()
            if (
                not force_refresh
                and self._cached_token is not None
                and now < self._expires_at
            ):
                return self._cached_token

            token = self._mint_token()
            self._cached_token = token
            self._expires_at = now + self.ttl_seconds
            return token

    def invalidate(self) -> None:
        """Clear cached OIDC token so the next request mints a fresh token."""
        with self._lock:
            self._cached_token = None
            self._expires_at = 0.0

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        if not self.enabled:
            yield request
            return

        token = self.get_id_token()
        request.headers["Authorization"] = f"Bearer {token}"
        response = yield request

        if response.status_code == 401:
            fresh_token = self.get_id_token(force_refresh=True)
            request.headers["Authorization"] = f"Bearer {fresh_token}"
            yield request
