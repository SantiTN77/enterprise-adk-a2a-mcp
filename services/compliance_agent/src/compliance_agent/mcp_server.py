"""Embedded stdio MCP server for the Audit & Compliance Agent."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import date
from typing import Any

from google.api_core.exceptions import GoogleAPICallError, NotFound, PermissionDenied
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import secretmanager, storage
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("audit-compliance-mcp")

_secret_client_factory: Callable[[], secretmanager.SecretManagerServiceClient] = (
    secretmanager.SecretManagerServiceClient
)
_secret_client: secretmanager.SecretManagerServiceClient | None = None

_storage_client_factory: Callable[[], storage.Client] = storage.Client
_storage_client: storage.Client | None = None

_SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def set_secret_client_factory(
    factory: Callable[[], secretmanager.SecretManagerServiceClient],
) -> None:
    """Override Secret Manager client creation (used by subprocess stdio test harness)."""
    global _secret_client_factory, _secret_client
    _secret_client_factory = factory
    _secret_client = None


def get_secret_client() -> secretmanager.SecretManagerServiceClient:
    """Lazily instantiate the Google Cloud Secret Manager client."""
    global _secret_client
    if _secret_client is None:
        _secret_client = _secret_client_factory()
    return _secret_client


def set_storage_client_factory(factory: Callable[[], storage.Client]) -> None:
    """Override GCS storage client creation (used by subprocess stdio test harness)."""
    global _storage_client_factory, _storage_client
    _storage_client_factory = factory
    _storage_client = None


def get_storage_client() -> storage.Client:
    """Lazily instantiate the Google Cloud Storage client."""
    global _storage_client
    if _storage_client is None:
        _storage_client = _storage_client_factory()
    return _storage_client


def _require_bucket_name() -> str:
    bucket = os.environ.get("GCS_BUCKET_NAME", "").strip()
    if not bucket:
        raise ToolError("GCS_BUCKET_NAME environment variable is not configured.")
    return bucket


def _normalize_doc_candidates(doc_id: str, bucket_name: str) -> list[str]:
    raw = doc_id.strip()
    if raw.startswith(f"gs://{bucket_name}/"):
        clean = raw.removeprefix(f"gs://{bucket_name}/")
    elif raw.startswith("gs://"):
        _, _, clean = raw.removeprefix("gs://").partition("/")
    else:
        clean = raw
    clean = clean.lstrip("/")
    if not clean:
        raise ToolError("doc_id must be a non-empty GCS object path.")

    candidates = [clean]
    if "/" not in clean:
        candidates.append(f"samples/{clean}")
        if not clean.endswith(".json"):
            candidates.append(f"samples/{clean}.json")
    elif not clean.endswith(".json"):
        candidates.append(f"{clean}.json")
    return list(dict.fromkeys(candidates))


@mcp.tool()
def fetch_compliance_policy(secret_id: str = "") -> str:
    """Fetch compliance policy JSON rules from GCP Secret Manager."""
    target = (
        secret_id.strip()
        or os.environ.get("COMPLIANCE_SECRET_ID", "adk-compliance-policy-rules").strip()
        or "adk-compliance-policy-rules"
    )
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()

    try:
        client = get_secret_client()
        if target.startswith("projects/"):
            resource_name = target if "/versions/" in target else f"{target.rstrip('/')}/versions/latest"
            parts = resource_name.split("/")
            resolved_secret_id = parts[3] if len(parts) >= 4 else target
        else:
            if not project_id:
                raise ToolError("GOOGLE_CLOUD_PROJECT environment variable is not configured.")
            resource_name = client.secret_version_path(project_id, target, "latest")
            resolved_secret_id = target

        response = client.access_secret_version(request={"name": resource_name})
        payload_text = response.payload.data.decode("utf-8")
        try:
            policy_obj: Any = json.loads(payload_text)
        except json.JSONDecodeError:
            policy_obj = None

        return json.dumps(
            {
                "secret_id": resolved_secret_id,
                "resource_name": resource_name,
                "policy": policy_obj,
                "policy_raw": payload_text,
            }
        )
    except ToolError:
        raise
    except NotFound as exc:
        raise ToolError(f"Compliance policy secret not found: {target}") from exc
    except (PermissionDenied, DefaultCredentialsError, GoogleAPICallError) as exc:
        raise ToolError(f"Secret Manager access failed for {target}: {exc}") from exc


@mcp.tool()
def read_audit_evidence(doc_id: str) -> str:
    """Read audit evidence JSON or text document from GCS."""
    bucket_name = _require_bucket_name()
    candidates = _normalize_doc_candidates(doc_id, bucket_name)
    try:
        client = get_storage_client()
        bucket = client.bucket(bucket_name)
        last_not_found: NotFound | None = None
        for candidate in candidates:
            try:
                text = bucket.blob(candidate).download_as_text(encoding="utf-8")
                try:
                    parsed: Any = json.loads(text)
                except json.JSONDecodeError:
                    parsed = None
                return json.dumps(
                    {
                        "bucket": bucket_name,
                        "doc_id": candidate,
                        "gcs_uri": f"gs://{bucket_name}/{candidate}",
                        "evidence": parsed,
                        "content": text,
                    }
                )
            except NotFound as exc:
                last_not_found = exc
        raise ToolError(f"Audit evidence document not found: gs://{bucket_name}/{candidates[0]}") from last_not_found
    except ToolError:
        raise
    except (PermissionDenied, DefaultCredentialsError, GoogleAPICallError) as exc:
        raise ToolError(f"Failed to read audit evidence gs://{bucket_name}/{candidates[0]}: {exc}") from exc


def _unwrap_json_payload(raw_text: str, wrapper_keys: tuple[str, ...]) -> Any:
    parsed = json.loads(raw_text)
    if isinstance(parsed, dict):
        for key in wrapper_keys:
            if key in parsed and parsed[key] is not None:
                inner = parsed[key]
                if isinstance(inner, str):
                    try:
                        inner_parsed = json.loads(inner)
                        if isinstance(inner_parsed, (dict, list)):
                            return inner_parsed
                    except json.JSONDecodeError:
                        pass
                elif isinstance(inner, (dict, list)):
                    return inner
    return parsed


def _first_present(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _recursive_find(obj: Any, target_key: str) -> Any:
    if isinstance(obj, dict):
        if target_key in obj:
            return obj[target_key]
        for value in obj.values():
            found = _recursive_find(value, target_key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _recursive_find(item, target_key)
            if found is not None:
                return found
    return None


def _resolve_field(doc: dict[str, Any], field_path: str) -> Any:
    if not field_path:
        return None
    current: Any = doc
    for part in field_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            current = None
            break
    if current is not None:
        return current
    leaf_key = field_path.split(".")[-1]
    return _recursive_find(doc, leaf_key)


def _parse_iso_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _extract_approvers(raw_approvals: Any) -> list[tuple[str, str]]:
    """Normalize approver entries to a list of (employee_id, role) tuples."""
    if raw_approvals is None:
        return []
    entries = raw_approvals if isinstance(raw_approvals, list) else [raw_approvals]
    normalized: list[tuple[str, str]] = []
    for entry in entries:
        if isinstance(entry, str) and entry.strip():
            normalized.append((entry.strip(), ""))
        elif isinstance(entry, dict):
            emp_id = str(
                _first_present(entry, ("employee_id", "id", "user_id", "approver_id", "name", "email")) or ""
            ).strip()
            role = str(_first_present(entry, ("role", "title", "approver_role")) or "").strip().upper()
            if emp_id:
                normalized.append((emp_id, role))
    return normalized


def _normalize_document(doc: dict[str, Any]) -> dict[str, Any]:
    """Normalize diverse audit/financial document schemas into a canonical view."""
    doc_id = str(_first_present(doc, ("doc_id", "document_id", "scenario_id")) or "unknown")
    report_date = _parse_iso_date(doc.get("report_date")) or date.today()

    fs = (
        doc.get("financial_summary")
        or doc.get("financials")
        or doc.get("budget")
        or doc.get("summary")
        or {}
    )
    if not isinstance(fs, dict):
        fs = {}

    line_items = doc.get("line_items") if isinstance(doc.get("line_items"), list) else []

    budgeted = _first_present(
        fs,
        ("budgeted_spend_usd", "budgeted_spend", "budgeted_usd", "budget_usd", "approved_budget", "budget"),
    )
    if budgeted is None:
        budgeted = _first_present(
            doc,
            ("budgeted_spend_usd", "budgeted_spend", "budgeted_usd", "budget_usd", "approved_budget", "budget"),
        )
    if budgeted is None and line_items:
        vals = [float(item["budgeted_usd"]) for item in line_items if isinstance(item, dict) and item.get("budgeted_usd") is not None]
        if vals:
            budgeted = sum(vals)

    actual = _first_present(
        fs,
        ("actual_spend_usd", "actual_spend", "actual_usd", "total_spend", "actual_cost", "spend_usd", "actual", "amount_usd"),
    )
    if actual is None:
        actual = _first_present(
            doc,
            ("actual_spend_usd", "actual_spend", "actual_usd", "total_spend", "actual_cost", "spend_usd", "actual", "amount_usd"),
        )
    if actual is None and line_items:
        vals = [float(item["actual_usd"]) for item in line_items if isinstance(item, dict) and item.get("actual_usd") is not None]
        if vals:
            actual = sum(vals)

    variance_pct = _first_present(fs, ("budget_variance_pct", "variance_pct"))
    if variance_pct is None:
        variance_pct = _first_present(doc, ("budget_variance_pct", "variance_pct"))
    if variance_pct is None and budgeted is not None and actual is not None and float(budgeted) > 0.0:
        variance_pct = round(((float(actual) - float(budgeted)) / float(budgeted)) * 100.0, 2)

    waiver = bool(
        _first_present(fs, ("variance_waiver_approved", "waiver_approved"))
        or _first_present(doc, ("variance_waiver_approved", "waiver_approved"))
        or False
    )

    approvals_raw = _first_present(doc, ("approvals", "approval_chain", "approval_metadata"))
    approvals_list: list[dict[str, Any]] = []
    if isinstance(approvals_raw, list):
        approvals_list = [item for item in approvals_raw if isinstance(item, dict)]
    elif isinstance(approvals_raw, dict):
        approvals_list = [approvals_raw]
    else:
        top_approvers = _first_present(doc, ("approvers", "approved_by", "sign_offs"))
        if top_approvers is not None:
            approvals_list = [
                {
                    "record_id": doc_id,
                    "amount_usd": float(actual) if actual is not None else 0.0,
                    "approvers": top_approvers,
                }
            ]

    vendor_contracts_present = "vendor_contracts" in doc or "vendors" in doc
    vendor_contracts = doc.get("vendor_contracts") if "vendor_contracts" in doc else doc.get("vendors")
    if not isinstance(vendor_contracts, list):
        vendor_contracts = []

    treasury = doc.get("treasury_controls") if isinstance(doc.get("treasury_controls"), dict) else {}
    wire_transfers = treasury.get("wire_transfers") if isinstance(treasury.get("wire_transfers"), list) else None
    if wire_transfers is None:
        wire_transfers = doc.get("wire_transfers") if isinstance(doc.get("wire_transfers"), list) else []

    revenue_items = (
        doc.get("revenue_recognition_items")
        if isinstance(doc.get("revenue_recognition_items"), list)
        else (doc.get("revenue_items") if isinstance(doc.get("revenue_items"), list) else [])
    )

    control_evidence = doc.get("control_evidence") if isinstance(doc.get("control_evidence"), dict) else {}
    if not control_evidence and isinstance(doc.get("controls"), dict):
        control_evidence = doc["controls"]

    return {
        "document_id": doc_id,
        "report_date": report_date,
        "budgeted_spend": float(budgeted) if budgeted is not None else None,
        "actual_spend": float(actual) if actual is not None else None,
        "budget_variance_pct": float(variance_pct) if variance_pct is not None else None,
        "variance_waiver_approved": waiver,
        "approvals": approvals_list,
        "dual_approval_flag": _first_present(doc, ("dual_approval", "dual_approval_obtained", "dual_custody")),
        "preparer": _first_present(doc, ("preparer", "prepared_by", "requester", "initiator", "submitted_by")),
        "top_approvers": _extract_approvers(_first_present(doc, ("approvers", "approved_by", "sign_offs"))),
        "sod_violation_flag": doc.get("sod_violation"),
        "segregation_of_duties_flag": doc.get("segregation_of_duties"),
        "vendor_contracts_present": vendor_contracts_present,
        "vendor_contracts": vendor_contracts,
        "wire_transfers": wire_transfers,
        "revenue_recognition_items": revenue_items,
        "control_evidence": control_evidence,
    }


def _default_controls() -> list[dict[str, Any]]:
    return [
        {
            "control_id": "FIN-VAR-01",
            "name": "Budget Variance Threshold Control",
            "framework": "INTERNAL-FIN-CTRL",
            "severity": "HIGH",
            "threshold_key": "max_budget_variance_pct",
        },
        {
            "control_id": "SOX-APPR-02",
            "name": "High-Value Expenditure & Wire Dual Approval",
            "framework": "SOX-404",
            "severity": "HIGH",
            "threshold_key": "dual_approval_threshold_usd",
        },
        {
            "control_id": "SOC2-VEND-03",
            "name": "Third-Party Vendor SOC2 Type II & DPA Verification",
            "framework": "SOC2-CC6",
            "severity": "CRITICAL",
            "threshold_key": "vendor_soc2_required_above_usd",
        },
        {
            "control_id": "TRES-SOD-04",
            "name": "Treasury & Disbursement Segregation of Duties (SoD)",
            "framework": "SOX-404 / SOC2-CC6.1",
            "severity": "CRITICAL",
            "threshold_key": "segregation_of_duties_enforced",
        },
        {
            "control_id": "SOX-REV-05",
            "name": "ASC 606 Revenue Recognition & Period-Close Evidence",
            "framework": "SOX-404 / ASC-606",
            "severity": "MEDIUM",
            "threshold_key": "asc_606_verification_required",
        },
    ]


def _extract_controls(pol: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("controls", "rules", "policies"):
        val = pol.get(key)
        if isinstance(val, list) and val:
            return [c for c in val if isinstance(c, dict)]

    # Flatten dict-of-sections policies if present
    flattened: list[dict[str, Any]] = []
    for section_key in ("spending_controls", "sox_controls", "soc2_controls", "treasury_controls", "revenue_recognition_controls"):
        section = pol.get(section_key)
        if isinstance(section, list):
            flattened.extend(c for c in section if isinstance(c, dict))
        elif isinstance(section, dict):
            flattened.append({"control_id": section_key.upper(), "name": section_key, **section})
    return flattened if flattened else _default_controls()


def _eval_budget_variance(
    rule: dict[str, Any],
    norm: dict[str, Any],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    max_pct = float(thresholds.get(rule.get("threshold_key", "max_budget_variance_pct"), 10.0))
    crit_pct = float(thresholds.get("critical_budget_variance_pct", 25.0))
    variance = norm["budget_variance_pct"]
    waived = norm["variance_waiver_approved"]

    if variance is None:
        return {
            "status": "FAIL",
            "observed": None,
            "expected_or_threshold": f"<= {max_pct}%",
            "rationale": "Missing required budget variance evidence (budgeted/actual spend absent or zero budget).",
        }
    if variance <= max_pct:
        return {
            "status": "PASS",
            "observed": f"{variance}%",
            "expected_or_threshold": f"<= {max_pct}%",
            "rationale": f"Budget variance {variance:.2f}% is within {max_pct:.2f}% tolerance.",
        }
    if waived:
        return {
            "status": "PASS",
            "observed": f"{variance}% (waived)",
            "expected_or_threshold": f"<= {max_pct}% or CFO waiver",
            "rationale": f"Budget variance {variance:.2f}% exceeds {max_pct:.2f}% but has approved variance waiver.",
        }
    severity_note = " (CRITICAL overrun)" if variance > crit_pct else ""
    return {
        "status": "FAIL",
        "observed": f"{variance}%",
        "expected_or_threshold": f"<= {max_pct}%",
        "rationale": f"Budget variance {variance:.2f}% exceeds policy threshold of {max_pct:.2f}% without an approved waiver{severity_note}.",
    }


def _eval_dual_approval(
    rule: dict[str, Any],
    norm: dict[str, Any],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    amount_threshold = float(thresholds.get(rule.get("threshold_key", "dual_approval_threshold_usd"), 50_000.0))
    req_count = int(thresholds.get(rule.get("required_count_key", "required_approvals_above_threshold"), 2))
    req_roles = {str(r).upper() for r in thresholds.get(rule.get("required_roles_key", "required_finance_approver_roles"), ["CFO", "VP_FINANCE", "CONTROLLER"])}

    approvals = norm["approvals"]
    actual_spend = norm["actual_spend"]

    if norm["dual_approval_flag"] is False:
        return {
            "status": "FAIL",
            "observed": {"dual_approval": False},
            "expected_or_threshold": f">= {req_count} approvers above ${amount_threshold:,.0f}",
            "rationale": "Document explicitly indicates dual approval was not obtained.",
        }

    if not approvals:
        if actual_spend is not None and actual_spend >= amount_threshold:
            return {
                "status": "FAIL",
                "observed": {"approval_records": 0, "actual_spend_usd": actual_spend},
                "expected_or_threshold": f">= {req_count} distinct approvers with Finance leadership role",
                "rationale": f"Spend of ${actual_spend:,.2f} meets/exceeds ${amount_threshold:,.2f} threshold with zero approval records.",
            }
        return {
            "status": "FAIL",
            "observed": {"approval_records": 0},
            "expected_or_threshold": f">= {req_count} distinct approvers for >= ${amount_threshold:,.0f}",
            "rationale": "Missing approval chain evidence.",
        }

    failures: list[str] = []
    checked = 0
    for rec in approvals:
        amt = float(rec.get("amount_usd", actual_spend or 0.0) or 0.0)
        if amt < amount_threshold:
            continue
        checked += 1
        rec_id = str(rec.get("record_id") or rec.get("id") or "record")
        pairs = _extract_approvers(rec.get("approvers") or rec.get("approved_by"))
        distinct_ids = {emp for emp, _ in pairs}
        roles = {role for _, role in pairs if role}
        if len(distinct_ids) < req_count:
            failures.append(f"{rec_id} (${amt:,.0f}) has {len(distinct_ids)}/{req_count} distinct approver(s)")
        elif req_roles and roles and not (roles & req_roles):
            failures.append(f"{rec_id} (${amt:,.0f}) lacks required Finance role {sorted(req_roles)} (found {sorted(roles)})")
        elif req_roles and not roles:
            failures.append(f"{rec_id} (${amt:,.0f}) missing approver role metadata for Finance leadership verification")

    if failures:
        return {
            "status": "FAIL",
            "observed": failures,
            "expected_or_threshold": f">= {req_count} distinct approvers including {sorted(req_roles)} for >= ${amount_threshold:,.0f}",
            "rationale": "; ".join(failures),
        }
    return {
        "status": "PASS",
        "observed": f"{checked} high-value approval record(s) verified",
        "expected_or_threshold": f">= {req_count} distinct approvers including Finance leadership",
        "rationale": f"All {checked} high-value approval record(s) satisfy dual-approval and Finance role requirements.",
    }


def _eval_vendor_soc2(
    rule: dict[str, Any],
    norm: dict[str, Any],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    val_threshold = float(thresholds.get(rule.get("threshold_key", "vendor_soc2_required_above_usd"), 25_000.0))
    req_classes = {
        str(c).upper()
        for c in thresholds.get("vendor_soc2_required_classifications", ["CONFIDENTIAL", "RESTRICTED_FINANCIAL"])
    }
    report_date: date = norm["report_date"]
    vendors = norm["vendor_contracts"]

    if not norm["vendor_contracts_present"] and not vendors:
        return {
            "status": "NOT_APPLICABLE",
            "observed": "No vendor_contracts section in document",
            "expected_or_threshold": "SOC2 Type II + DPA for in-scope vendors",
            "rationale": "Document contains no third-party vendor contract disclosures.",
        }

    if norm["vendor_contracts_present"] and not vendors:
        return {
            "status": "FAIL",
            "observed": [],
            "expected_or_threshold": "Non-empty vendor verification records",
            "rationale": "vendor_contracts field is empty; vendor compliance cannot be attested.",
        }

    failures: list[str] = []
    in_scope = 0
    for vendor in vendors:
        if not isinstance(vendor, dict):
            continue
        vid = str(vendor.get("vendor_id") or vendor.get("vendor_name") or "vendor")
        annual_val = vendor.get("annual_value_usd")
        classification = str(vendor.get("data_classification") or "").upper()
        applies = (
            annual_val is None
            or float(annual_val) > val_threshold
            or classification in req_classes
        )
        if not applies:
            continue
        in_scope += 1
        if vendor.get("soc2_type2_verified") is not True:
            failures.append(f"{vid}: soc2_type2_verified is {vendor.get('soc2_type2_verified')}")
        if vendor.get("dpa_signed") is not True:
            failures.append(f"{vid}: dpa_signed is {vendor.get('dpa_signed')}")
        expiry = _parse_iso_date(vendor.get("soc2_report_expiry"))
        if expiry is None:
            failures.append(f"{vid}: missing or invalid soc2_report_expiry")
        elif expiry < report_date:
            failures.append(f"{vid}: SOC2 report expired on {expiry.isoformat()} (before {report_date.isoformat()})")
        if vendor.get("missing_po") is True or ("po_number" in vendor and not vendor.get("po_number")):
            failures.append(f"{vid}: missing purchase order number")

    if failures:
        return {
            "status": "FAIL",
            "observed": failures,
            "expected_or_threshold": f"Valid non-expired SOC2 Type II + signed DPA for vendors > ${val_threshold:,.0f} or sensitive data",
            "rationale": "; ".join(failures),
        }
    return {
        "status": "PASS",
        "observed": f"{in_scope} in-scope vendor(s) verified",
        "expected_or_threshold": "Valid SOC2 Type II + signed DPA",
        "rationale": f"All {in_scope} in-scope vendor(s) hold active SOC2 Type II reports and signed DPAs.",
    }


def _eval_segregation_of_duties(
    rule: dict[str, Any],
    norm: dict[str, Any],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    enforced = bool(thresholds.get(rule.get("threshold_key", "segregation_of_duties_enforced"), True))
    if not enforced:
        return {
            "status": "NOT_APPLICABLE",
            "observed": "segregation_of_duties_enforced=false",
            "expected_or_threshold": "SoD disabled in policy",
            "rationale": "Policy does not enforce segregation of duties.",
        }

    if norm["sod_violation_flag"] is True or norm["segregation_of_duties_flag"] is False:
        return {
            "status": "FAIL",
            "observed": {"sod_violation": norm["sod_violation_flag"], "segregation_of_duties": norm["segregation_of_duties_flag"]},
            "expected_or_threshold": "Distinct preparer, approver(s), and releaser",
            "rationale": "Explicit Segregation of Duties conflict flagged in document.",
        }

    wires = norm["wire_transfers"]
    failures: list[str] = []
    if wires:
        for wire in wires:
            if not isinstance(wire, dict):
                continue
            wid = str(wire.get("wire_id") or "wire")
            preparer = str(wire.get("preparer_id") or "").strip()
            releaser = str(wire.get("releaser_id") or "").strip()
            approvers = [str(a).strip() for a in (wire.get("approver_ids") or []) if str(a).strip()]
            if not preparer or not approvers or not releaser:
                failures.append(f"{wid}: incomplete preparer/approver/releaser metadata")
                continue
            if preparer in approvers:
                failures.append(f"{wid}: preparer '{preparer}' also approved the wire")
            if preparer == releaser:
                failures.append(f"{wid}: preparer '{preparer}' also released the wire")
            if releaser in approvers and len(set(approvers)) <= 1:
                failures.append(f"{wid}: releaser '{releaser}' acted as sole approver")
            if wire.get("override_used") is True:
                failures.append(f"{wid}: manual control override used (override_used=true)")
        if failures:
            return {
                "status": "FAIL",
                "observed": failures,
                "expected_or_threshold": "Distinct preparer, approvers, releaser, and override_used=false",
                "rationale": "; ".join(failures),
            }
        return {
            "status": "PASS",
            "observed": f"{len(wires)} wire transfer(s) verified with strict SoD",
            "expected_or_threshold": "Distinct preparer, approvers, releaser, no overrides",
            "rationale": f"All {len(wires)} treasury wire transfer(s) maintain strict segregation of duties without overrides.",
        }

    # Generic preparer vs approver fallback when wire_transfers absent
    if norm["preparer"] and norm["top_approvers"]:
        approver_ids = {emp for emp, _ in norm["top_approvers"]}
        if str(norm["preparer"]).strip() in approver_ids:
            return {
                "status": "FAIL",
                "observed": {"preparer": norm["preparer"], "approvers": sorted(approver_ids)},
                "expected_or_threshold": "preparer not in approvers",
                "rationale": f"Preparer '{norm['preparer']}' also appears in approvers.",
            }
        return {
            "status": "PASS",
            "observed": {"preparer": norm["preparer"], "approvers": sorted(approver_ids)},
            "expected_or_threshold": "preparer not in approvers",
            "rationale": "Preparer and approvers are distinct.",
        }

    return {
        "status": "FAIL",
        "observed": None,
        "expected_or_threshold": "Wire transfer or preparer/approver SoD evidence",
        "rationale": "Missing required Segregation of Duties evidence.",
    }


def _eval_revenue_and_close(
    rule: dict[str, Any],
    norm: dict[str, Any],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    asc_required = bool(thresholds.get(rule.get("threshold_key", "asc_606_verification_required"), True))
    max_age = int(thresholds.get("max_unreconciled_age_days", 30))

    rev_items = norm["revenue_recognition_items"]
    evidence = norm["control_evidence"]
    failures: list[str] = []

    if asc_required:
        if not rev_items:
            failures.append("Missing revenue_recognition_items for ASC 606 verification")
        else:
            for item in rev_items:
                if not isinstance(item, dict):
                    continue
                cid = str(item.get("contract_id") or "contract")
                if item.get("asc_606_five_step_verified") is not True:
                    failures.append(f"{cid}: asc_606_five_step_verified is not true")
                if item.get("performance_obligations_met") is not True:
                    failures.append(f"{cid}: performance_obligations_met is not true")
                if item.get("signed_contract_on_file") is not True:
                    failures.append(f"{cid}: signed_contract_on_file is not true")
                if item.get("side_letters_detected") is True:
                    failures.append(f"{cid}: undisclosed side letters detected")
                if item.get("cutoff_exception") is True:
                    failures.append(f"{cid}: period-end cutoff exception detected")

    if not evidence:
        failures.append("Missing control_evidence period-close attestation")
    else:
        if evidence.get("bank_reconciliation_completed") is not True:
            failures.append(
                f"bank_reconciliation_completed is {evidence.get('bank_reconciliation_completed')}"
            )
        age = evidence.get("max_unreconciled_age_days")
        if age is None:
            failures.append("max_unreconciled_age_days is missing")
        elif float(age) > max_age:
            failures.append(f"max_unreconciled_age_days ({age}) exceeds {max_age} days")

        suspense = evidence.get("unreconciled_suspense_balance_usd")
        if suspense is None:
            failures.append("unreconciled_suspense_balance_usd is missing")
        elif float(suspense) != 0.0:
            failures.append(f"unreconciled_suspense_balance_usd is ${float(suspense):,.2f} (must be $0.00)")

        if evidence.get("journal_entry_audit_trail_complete") is not True:
            failures.append(
                f"journal_entry_audit_trail_complete is {evidence.get('journal_entry_audit_trail_complete')}"
            )

    if failures:
        return {
            "status": "FAIL",
            "observed": failures,
            "expected_or_threshold": f"ASC 606 verified + complete bank reconciliation with age <= {max_age}d and $0 suspense",
            "rationale": "; ".join(failures),
        }
    return {
        "status": "PASS",
        "observed": f"{len(rev_items)} contract(s) ASC 606 verified; close age {evidence.get('max_unreconciled_age_days')}d",
        "expected_or_threshold": f"ASC 606 verified + age <= {max_age}d + $0 suspense",
        "rationale": "All revenue recognition items pass ASC 606 five-step verification and period-close reconciliations are complete.",
    }


def _eval_declarative_predicate(
    rule: dict[str, Any],
    doc: dict[str, Any],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    field = str(rule.get("field") or rule.get("evaluation_target") or "")
    operator = str(rule.get("operator") or "eq").lower()
    expected = rule.get("value")
    if expected is None:
        expected = rule.get("threshold")
    if expected is None and rule.get("threshold_key"):
        expected = thresholds.get(rule["threshold_key"])

    observed = _resolve_field(doc, field)
    if operator == "exists":
        passed = observed is not None
        return {
            "status": "PASS" if passed else "FAIL",
            "observed": observed,
            "expected_or_threshold": f"{field} exists",
            "rationale": f"Field '{field}' is {'present' if passed else 'missing'}.",
        }

    if observed is None:
        return {
            "status": "FAIL",
            "observed": None,
            "expected_or_threshold": f"{operator} {expected}",
            "rationale": f"Required evidence field '{field}' is missing or null.",
        }

    try:
        if operator == "eq":
            passed = observed == expected
        elif operator == "neq":
            passed = observed != expected
        elif operator == "lt":
            passed = float(observed) < float(expected)
        elif operator == "lte":
            passed = float(observed) <= float(expected)
        elif operator == "gt":
            passed = float(observed) > float(expected)
        elif operator == "gte":
            passed = float(observed) >= float(expected)
        elif operator == "in":
            passed = observed in expected
        elif operator == "not_in":
            passed = observed not in expected
        elif operator == "contains":
            passed = expected in observed
        else:
            passed = False
    except (TypeError, ValueError):
        passed = False

    return {
        "status": "PASS" if passed else "FAIL",
        "observed": observed,
        "expected_or_threshold": f"{operator} {expected}",
        "rationale": (
            f"Field '{field}' ({observed}) satisfies {operator} {expected}."
            if passed
            else f"Field '{field}' ({observed}) failed {operator} {expected}."
        ),
    }


@mcp.tool()
def evaluate_control_matrix(document_json: str, policy_json: str) -> str:
    """Deterministically evaluate SOX/SOC2/FinOps/Treasury controls on an evidence document against a compliance policy."""
    try:
        doc = _unwrap_json_payload(document_json, ("document", "evidence", "content"))
        if not isinstance(doc, dict):
            raise ValueError("document_json must resolve to a JSON object.")
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return json.dumps(
            {
                "error": f"Invalid document_json: {exc}",
                "policy_id": "unknown",
                "policy_version": "unknown",
                "document_id": "unknown",
                "controls_evaluated": [],
                "violations": [],
                "summary": {
                    "total_evaluated": 0,
                    "passed": 0,
                    "failed": 0,
                    "not_applicable": 0,
                    "highest_violation_severity": None,
                },
                "compliant": False,
            }
        )

    try:
        pol = _unwrap_json_payload(policy_json, ("policy", "policy_raw"))
        if not isinstance(pol, dict):
            raise ValueError("policy_json must resolve to a JSON object.")
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return json.dumps(
            {
                "error": f"Invalid policy_json: {exc}",
                "policy_id": "unknown",
                "policy_version": "unknown",
                "document_id": str(_first_present(doc, ("doc_id", "scenario_id", "document_id")) or "unknown"),
                "controls_evaluated": [],
                "violations": [],
                "summary": {
                    "total_evaluated": 0,
                    "passed": 0,
                    "failed": 0,
                    "not_applicable": 0,
                    "highest_violation_severity": None,
                },
                "compliant": False,
            }
        )

    norm = _normalize_document(doc)
    thresholds = pol.get("thresholds") if isinstance(pol.get("thresholds"), dict) else {}
    # Allow top-level threshold overrides for flexible custom policies
    merged_thresholds = {
        **thresholds,
        **{
            k: v
            for k, v in pol.items()
            if k
            in {
                "max_budget_variance_pct",
                "critical_budget_variance_pct",
                "dual_approval_threshold_usd",
                "required_approvals_above_threshold",
                "required_finance_approver_roles",
                "vendor_soc2_required_above_usd",
                "vendor_soc2_required_classifications",
                "segregation_of_duties_enforced",
                "max_unreconciled_age_days",
                "asc_606_verification_required",
            }
        },
    }
    controls = _extract_controls(pol)

    controls_evaluated: list[dict[str, Any]] = []
    for idx, rule in enumerate(controls, start=1):
        cid = str(rule.get("control_id") or rule.get("id") or f"CTRL-{idx:02d}")
        name = str(rule.get("name") or cid)
        framework = str(rule.get("framework") or "INTERNAL-FIN-CTRL")
        severity = str(rule.get("severity") or "HIGH").upper()
        cid_upper = cid.upper()
        target_str = str(rule.get("evaluation_target") or rule.get("field") or "").lower()

        if "FIN-VAR" in cid_upper or "variance" in cid_upper or "budget_variance" in target_str:
            outcome = _eval_budget_variance(rule, norm, merged_thresholds)
        elif "APPR" in cid_upper or "DUAL" in cid_upper or target_str == "approvals":
            outcome = _eval_dual_approval(rule, norm, merged_thresholds)
        elif "VEND" in cid_upper or target_str == "vendor_contracts":
            outcome = _eval_vendor_soc2(rule, norm, merged_thresholds)
        elif "SOD" in cid_upper or "wire_transfers" in target_str:
            outcome = _eval_segregation_of_duties(rule, norm, merged_thresholds)
        elif "REV" in cid_upper or "606" in cid_upper or "revenue_recognition" in target_str:
            outcome = _eval_revenue_and_close(rule, norm, merged_thresholds)
        elif rule.get("operator") and (rule.get("field") or rule.get("evaluation_target")):
            outcome = _eval_declarative_predicate(rule, doc, merged_thresholds)
        else:
            outcome = {
                "status": "FAIL",
                "observed": None,
                "expected_or_threshold": rule.get("description") or "Explicit evidence",
                "rationale": f"No evaluator or field predicate matched control '{cid}'.",
            }

        controls_evaluated.append(
            {
                "control_id": cid,
                "name": name,
                "framework": framework,
                "severity": severity,
                "status": outcome["status"],
                "observed": outcome["observed"],
                "expected_or_threshold": outcome["expected_or_threshold"],
                "rationale": outcome["rationale"],
            }
        )

    violations = [c for c in controls_evaluated if c["status"] == "FAIL"]
    passed_count = sum(1 for c in controls_evaluated if c["status"] == "PASS")
    failed_count = len(violations)
    na_count = sum(1 for c in controls_evaluated if c["status"] == "NOT_APPLICABLE")

    highest_sev: str | None = None
    if violations:
        highest_sev = max(
            (v["severity"] for v in violations),
            key=lambda s: _SEVERITY_RANK.get(s, 0),
        )

    return json.dumps(
        {
            "policy_id": str(pol.get("policy_id") or "adk-compliance-policy-rules"),
            "policy_version": str(pol.get("version") or pol.get("policy_version") or "1.0.0"),
            "document_id": norm["document_id"],
            "controls_evaluated": controls_evaluated,
            "violations": violations,
            "summary": {
                "total_evaluated": len(controls_evaluated),
                "passed": passed_count,
                "failed": failed_count,
                "not_applicable": na_count,
                "highest_violation_severity": highest_sev,
            },
            "compliant": failed_count == 0,
        }
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
