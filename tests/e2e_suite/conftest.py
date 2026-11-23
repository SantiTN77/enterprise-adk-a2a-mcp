from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterator

import pytest

from lib.config import LiveTargets, get_repo_root
from lib.oidc_client import OidcHttpClient, OidcTokenMinter

SUITE_DIR = Path(__file__).resolve().parent


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    if config.option.collectonly:
        return None
    markexpr = (config.option.markexpr or "").strip()
    if collection_path.name == "test_self_verify.py" and markexpr != "self_verify":
        return True
    return None


def _is_live_execution(config: pytest.Config, items: list[pytest.Item] | None = None) -> bool:
    if config.option.collectonly:
        return False
    markexpr = (config.option.markexpr or "").strip()
    if markexpr in {"self_verify", "static_repo"}:
        return False
    if items is not None:
        return any(item.get_closest_marker("live_e2e") is not None for item in items)
    return True


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.option.collectonly:
        return
    markexpr = (config.option.markexpr or "").strip()
    if markexpr in {"self_verify", "static_repo"}:
        return

    # Live mode or default run: verify anti-cheat invariants BEFORE executing any test
    if "_harness" in sys.modules or "_harness.mock_stack" in sys.modules:
        pytest.exit(
            "ANTI-CHEAT VIOLATION: _harness must NEVER be imported outside self_verify mode.",
            returncode=2,
        )
    if _is_live_execution(config, items):
        try:
            LiveTargets.from_env()
        except ValueError as exc:
            pytest.exit(
                f"LIVE E2E PREFLIGHT FAILED (fail-fast anti-cheat): {exc}\n"
                "Provide ORCHESTRATOR_URL, FINANCIAL_AGENT_URL, COMPLIANCE_AGENT_URL, WEB_URL "
                "or explicitly run `-m self_verify` / `-m static_repo`.",
                returncode=2,
            )


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("live_e2e") is not None:
        if "_harness" in sys.modules or "_harness.mock_stack" in sys.modules:
            pytest.exit(
                "ANTI-CHEAT VIOLATION: _harness imported while running live_e2e test.",
                returncode=2,
            )


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return get_repo_root()


@pytest.fixture(scope="session")
def e2e_suite_dir() -> Path:
    return SUITE_DIR


@pytest.fixture(scope="session")
def live_targets() -> LiveTargets:
    if "_harness" in sys.modules or "_harness.mock_stack" in sys.modules:
        pytest.exit("ANTI-CHEAT VIOLATION: _harness forbidden in live_targets.", returncode=2)
    try:
        return LiveTargets.from_env()
    except ValueError as exc:
        pytest.exit(f"Missing/invalid live target URLs: {exc}", returncode=2)


@pytest.fixture(scope="session")
def oidc_client() -> Iterator[OidcHttpClient]:
    client = OidcHttpClient(minter=OidcTokenMinter.from_env())
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="session")
def agent_oidc_available(live_targets: LiveTargets, oidc_client: OidcHttpClient) -> bool:
    """Check whether caller can mint an OIDC token accepted by specialized agents."""
    try:
        resp = oidc_client.request_authenticated(
            "GET",
            live_targets.financial_agent_url,
            "/healthz",
            for_specialized_agent=True,
        )
        return resp.status_code == 200
    except Exception:
        return False
