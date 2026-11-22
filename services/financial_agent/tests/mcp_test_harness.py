"""Subprocess stdio MCP test harness injecting fake GCS storage for financial_agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from google.api_core.exceptions import NotFound

from financial_agent import mcp_server


class _FakeBlob:
    def __init__(self, name: str, payload: str) -> None:
        self.name = name
        self._payload = payload
        self.size = len(payload.encode("utf-8"))
        self.updated = datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc)

    def download_as_text(self, encoding: str = "utf-8") -> str:
        return self._payload


class _FakeBucket:
    def __init__(self, objects: dict[str, str]) -> None:
        self._objects = objects

    def list_blobs(self, prefix: str = "") -> list[_FakeBlob]:
        return [
            _FakeBlob(name, body)
            for name, body in sorted(self._objects.items())
            if name.startswith(prefix)
        ]

    def blob(self, blob_name: str) -> _FakeBlob:
        if blob_name not in self._objects:
            return _MissingBlob(blob_name)
        return _FakeBlob(blob_name, self._objects[blob_name])


class _MissingBlob:
    def __init__(self, name: str) -> None:
        self.name = name

    def download_as_text(self, encoding: str = "utf-8") -> str:
        raise NotFound(f"Blob not found: {self.name}")


class _FakeStorageClient:
    def __init__(self, buckets: dict[str, dict[str, str]]) -> None:
        self._buckets = buckets

    def bucket(self, bucket_name: str) -> _FakeBucket:
        if bucket_name not in self._buckets:
            raise NotFound(f"Bucket not found: {bucket_name}")
        return _FakeBucket(self._buckets[bucket_name])


def main() -> None:
    fixtures = {
        "test-enterprise-bucket": {
            "samples/q3_cloud_vendor_review.json": json.dumps(
                {
                    "doc_id": "samples/q3_cloud_vendor_review.json",
                    "financial_summary": {
                        "revenue_usd": 12600000.0,
                        "operating_expenses_usd": 10950000.0,
                        "budgeted_spend_usd": 3200000.0,
                        "actual_spend_usd": 4096000.0,
                    },
                }
            ),
            "samples/series_b_revenue_audit.json": json.dumps(
                {
                    "doc_id": "samples/series_b_revenue_audit.json",
                    "financial_summary": {"revenue_usd": 18450000.0},
                }
            ),
        }
    }
    mcp_server.set_storage_client_factory(lambda: _FakeStorageClient(fixtures))
    mcp_server.mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
