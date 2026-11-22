from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


def get_repo_root() -> Path:
    """Return the enterprise-adk-a2a-mcp repository root without assuming cwd."""
    env_override = os.environ.get("E2E_REPO_ROOT", "").strip()
    if env_override:
        return Path(env_override).resolve()
    return Path(__file__).resolve().parents[3]


def normalize_base_url(raw: str, *, name: str, allow_localhost: bool = False) -> str:
    value = (raw or "").strip()
    if not value:
        raise ValueError(f"{name} is required and cannot be empty.")
    if value.endswith("/"):
        raise ValueError(f"{name} must NOT have a trailing slash: {value!r}")

    parsed = urlparse(value)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise ValueError(f"{name} must be a valid URL (got {value!r}).")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError(f"{name} must be an exact base origin without path/query/fragment: {value!r}")

    host = (parsed.hostname or "").lower()
    if parsed.scheme == "http":
        if not (allow_localhost and host in {"localhost", "127.0.0.1"}):
            raise ValueError(
                f"{name} uses insecure http:// ({value!r}); use https:// or set E2E_ALLOW_LOCALHOST=1 for local dev."
            )
    return value


@dataclass(frozen=True)
class LiveTargets:
    orchestrator_url: str
    financial_agent_url: str
    compliance_agent_url: str
    web_url: str
    allow_localhost: bool = False
    strict_live: bool = False
    vercel_bypass_secret: str | None = None

    @classmethod
    def from_env(cls) -> "LiveTargets":
        allow_localhost = os.environ.get("E2E_ALLOW_LOCALHOST", "").strip() in {"1", "true", "TRUE", "yes"}
        strict_live = os.environ.get("E2E_STRICT_LIVE", "").strip() in {"1", "true", "TRUE", "yes"}
        bypass = os.environ.get("VERCEL_AUTOMATION_BYPASS_SECRET", "").strip() or None
        return cls(
            orchestrator_url=normalize_base_url(
                os.environ.get("ORCHESTRATOR_URL", ""),
                name="ORCHESTRATOR_URL",
                allow_localhost=allow_localhost,
            ),
            financial_agent_url=normalize_base_url(
                os.environ.get("FINANCIAL_AGENT_URL", ""),
                name="FINANCIAL_AGENT_URL",
                allow_localhost=allow_localhost,
            ),
            compliance_agent_url=normalize_base_url(
                os.environ.get("COMPLIANCE_AGENT_URL", ""),
                name="COMPLIANCE_AGENT_URL",
                allow_localhost=allow_localhost,
            ),
            web_url=normalize_base_url(
                os.environ.get("WEB_URL", ""),
                name="WEB_URL",
                allow_localhost=allow_localhost,
            ),
            allow_localhost=allow_localhost,
            strict_live=strict_live,
            vercel_bypass_secret=bypass,
        )

    def vercel_headers(self) -> dict[str, str]:
        if not self.vercel_bypass_secret:
            return {}
        return {
            "x-vercel-protection-bypass": self.vercel_bypass_secret,
            "x-vercel-set-bypass-cookie": "true",
        }
