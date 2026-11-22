"""Subprocess stdio MCP test harness injecting fake Secret Manager & GCS for compliance_agent."""

from __future__ import annotations

import json
from types import SimpleNamespace

from google.api_core.exceptions import NotFound

from compliance_agent import mcp_server


class _FakeSecretClient:
    def __init__(self, secrets: dict[str, str]) -> None:
        self._secrets = secrets

    @staticmethod
    def secret_version_path(project: str, secret: str, version: str) -> str:
        return f"projects/{project}/secrets/{secret}/versions/{version}"

    def access_secret_version(self, request: dict[str, str]) -> SimpleNamespace:
        name = request["name"]
        if name not in self._secrets:
            raise NotFound(f"Secret version not found: {name}")
        return SimpleNamespace(payload=SimpleNamespace(data=self._secrets[name].encode("utf-8")))


class _FakeBlob:
    def __init__(self, name: str, body: str | None) -> None:
        self.name = name
        self._body = body

    def download_as_text(self, encoding: str = "utf-8") -> str:
        if self._body is None:
            raise NotFound(f"Blob not found: {self.name}")
        return self._body


class _FakeBucket:
    def __init__(self, objects: dict[str, str]) -> None:
        self._objects = objects

    def blob(self, blob_name: str) -> _FakeBlob:
        return _FakeBlob(blob_name, self._objects.get(blob_name))


class _FakeStorageClient:
    def __init__(self, buckets: dict[str, dict[str, str]]) -> None:
        self._buckets = buckets

    def bucket(self, bucket_name: str) -> _FakeBucket:
        if bucket_name not in self._buckets:
            raise NotFound(f"Bucket not found: {bucket_name}")
        return _FakeBucket(self._buckets[bucket_name])


def main() -> None:
    policy_payload = json.dumps(
        {
            "policy_id": "ENT-COMP-POLICY-TEST",
            "version": "2026.3.0",
            "thresholds": {"max_budget_variance_pct": 10.0, "dual_approval_threshold_usd": 50000.0},
            "controls": [
                {"control_id": "FIN-VAR-01", "name": "Variance", "severity": "HIGH"},
                {"control_id": "SOX-APPR-02", "name": "Dual Approval", "severity": "HIGH"},
            ],
        }
    )
    secrets = {
        "projects/test-project/secrets/adk-compliance-policy-rules/versions/latest": policy_payload,
    }
    buckets = {
        "test-enterprise-bucket": {
            "samples/q3_cloud_vendor_review.json": json.dumps(
                {
                    "doc_id": "samples/q3_cloud_vendor_review.json",
                    "financial_summary": {
                        "budgeted_spend_usd": 3200000.0,
                        "actual_spend_usd": 4096000.0,
                        "budget_variance_pct": 28.0,
                    },
                    "approvals": [
                        {
                            "record_id": "AMD-1",
                            "amount_usd": 660000.0,
                            "approvers": [{"employee_id": "emp-eng-1", "role": "VP_ENGINEERING"}],
                        }
                    ],
                }
            )
        }
    }
    mcp_server.set_secret_client_factory(lambda: _FakeSecretClient(secrets))
    mcp_server.set_storage_client_factory(lambda: _FakeStorageClient(buckets))
    mcp_server.mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
