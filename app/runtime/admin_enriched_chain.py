from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "runtime/data/admin_enriched_refresh_status.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def tail(value: str, limit: int = 2400) -> str:
    return (value or "")[-limit:]


def write(payload: Dict[str, Any]) -> None:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATUS.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(STATUS)


def read(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def module_exists(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def execute(cmd: List[str], key: str, label: str, timeout: int = 3600) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "key": key,
        "label": label,
        "command": " ".join(cmd),
        "exists": True,
        "started_at_utc": now(),
        "finished_at_utc": None,
        "status": "running",
        "returncode": None,
        "stdout_tail": "",
        "stderr_tail": "",
    }
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        record.update(
            finished_at_utc=now(),
            returncode=proc.returncode,
            stdout_tail=tail(proc.stdout),
            stderr_tail=tail(proc.stderr),
            status="ok" if proc.returncode == 0 else "failed",
        )
    except subprocess.TimeoutExpired as exc:
        record.update(
            finished_at_utc=now(),
            status="timeout",
            error=f"timeout_after_{timeout}_seconds",
            stdout_tail=tail(exc.stdout or ""),
            stderr_tail=tail(exc.stderr or ""),
        )
    except BaseException as exc:
        record.update(
            finished_at_utc=now(),
            status="exception",
            error=f"{type(exc).__name__}: {exc}",
        )
    return record


def resolve(
    candidates: List[Dict[str, str]],
    key: str,
    label: str,
    steps: List[Dict[str, Any]],
    blocked_by: List[str] | None = None,
    timeout: int = 3600,
) -> Dict[str, Any]:
    failed = {step.get("key") for step in steps if step.get("status") != "ok"}
    blockers = sorted(failed.intersection(blocked_by or []))
    if blockers:
        return {
            "key": key,
            "label": label,
            "command": None,
            "exists": True,
            "started_at_utc": now(),
            "finished_at_utc": now(),
            "status": "blocked",
            "returncode": None,
            "stdout_tail": "",
            "stderr_tail": "",
            "blocked_by": blockers,
        }
    for candidate in candidates:
        value = candidate.get("value", "")
        if candidate.get("type") == "module" and value and module_exists(value):
            return execute([sys.executable, "-m", value], key, label, timeout)
        if candidate.get("type") == "script" and value and (ROOT / value).exists():
            return execute([sys.executable, value], key, label, timeout)
    return {
        "key": key,
        "label": label,
        "command": " | ".join(item.get("value", "") for item in candidates),
        "exists": False,
        "started_at_utc": now(),
        "finished_at_utc": now(),
        "status": "missing",
        "returncode": None,
        "stdout_tail": "",
        "stderr_tail": "No command candidate exists",
    }


def enforce(record: Dict[str, Any], gates: Dict[str, bool], reason: str) -> Dict[str, Any]:
    record["postcondition_gates"] = gates
    if not all(gates.values()):
        record["status"] = "failed"
        if record.get("returncode") in (None, 0):
            record["returncode"] = 3
        record["postcondition_reason"] = reason
    return record


def classify_estate_resource_authority(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = read(ROOT / "runtime/data/estate_resource_authority_refresh_status_v1.json")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    gates = {
        "contract_present": bool(payload),
        "status_review": payload.get("status") == "review",
        "no_unexpected_probe_failures": summary.get("unexpected_failed_probe_count") == 0,
    }
    record["postcondition_gates"] = gates
    if all(gates.values()):
        record["status"] = "advisory"
        record["advisory"] = True
        record["advisory_reason"] = (
            "Estate Resource Authority completed with a review outcome and no unexpected probe failures. "
            "Coverage remains visible as advisory evidence and does not block the Users & Access refresh chain."
        )
    return record


def validate_group_expansion(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = read(ROOT / "runtime/data/admin_group_expansion.json")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return enforce(record, {
        "source_generated": payload.get("source_status") == "generated",
        "safe_for_named_access": payload.get("safe_to_use_for_named_access") is True,
        "groups_present": isinstance(payload.get("groups"), list) and len(payload.get("groups")) > 0,
        "assignments_present": isinstance(summary.get("member_assignment_count"), int) and summary.get("member_assignment_count") > 0,
        "mapped_sites_present": isinstance(summary.get("mapped_site_count"), int) and summary.get("mapped_site_count") > 0,
    }, "Group expansion did not pass every approved named-access gate.")


def validate_named_truth(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = read(ROOT / "runtime/data/live_named_access_contract")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return enforce(record, {
        "source_generated": payload.get("source_status") == "generated",
        "group_expansion_safe": summary.get("group_expansion_safe") is True,
        "no_warnings": summary.get("warning_count") == 0,
        "users_present": isinstance(summary.get("unique_users"), int) and summary.get("unique_users") > 0,
        "assignments_present": isinstance(summary.get("total_product_access_assignments"), int) and summary.get("total_product_access_assignments") > 0,
        "records_present": isinstance(payload.get("users"), list) and len(payload.get("users")) > 0,
    }, "Named Access Truth v2 did not pass generated-source and population gates.")


def validate_reconciliation(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = read(ROOT / "reports/named_access_reconciliation_v2.json")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    blockers = payload.get("blockers") if isinstance(payload.get("blockers"), list) else []
    return enforce(record, {
        "contract_present": bool(payload),
        "status_aligned": payload.get("status") == "aligned",
        "safe_for_named_access_ui": payload.get("safe_to_enable_named_access_ui") is True,
        "no_blockers": len(blockers) == 0,
        "unique_users_available": isinstance(summary.get("named_unique_users"), int) and summary.get("named_unique_users") > 0,
        "assignments_available": isinstance(summary.get("named_product_access_assignments"), int) and summary.get("named_product_access_assignments") > 0,
        "group_expansion_safe": summary.get("group_expansion_safe") is True,
    }, "Named-access reconciliation contract is missing, blocked, or unsafe.")


def validate_footprint(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = read(ROOT / "runtime/data/user_footprint.json")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    users = payload.get("users") if isinstance(payload.get("users"), list) else []
    return enforce(record, {
        "source_generated": payload.get("source_status") == "generated",
        "safe_for_named_access_ui": payload.get("safe_to_show_named_access_ui") is True,
        "users_present": len(users) > 0,
        "users_reconciled": isinstance(summary.get("users_analyzed"), int) and summary.get("users_analyzed") == len(users),
        "assignments_present": isinstance(summary.get("total_product_access_assignments"), int) and summary.get("total_product_access_assignments") > 0,
    }, "User Footprint did not pass generated, safe, and non-empty output gates.")


def validate_named_site(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = read(ROOT / "runtime/data/named_site_access_authority_v1.json")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    capabilities = payload.get("capabilities") if isinstance(payload.get("capabilities"), dict) else {}
    return enforce(record, {
        "status_live": payload.get("status") == "live",
        "aggregate_capability": capabilities.get("aggregate_site_user_counts") is True,
        "unique_users_available": isinstance(summary.get("unique_users_with_access"), int),
        "assignments_available": isinstance(summary.get("named_access_assignments"), int),
        "sites_present": isinstance(payload.get("sites"), list) and len(payload.get("sites")) > 0,
    }, "Named Site Access did not pass live aggregate authority gates.")


def validate_identity(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = read(ROOT / "runtime/data/named_user_display_identity_v1.json")
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    quality = payload.get("quality") if isinstance(payload.get("quality"), dict) else {}
    authority = payload.get("authority") if isinstance(payload.get("authority"), dict) else {}
    users = payload.get("users") if isinstance(payload.get("users"), list) else []
    return enforce(record, {
        "status_ok": payload.get("status") == "ok",
        "safe_to_serve": authority.get("safe_to_serve") is True,
        "pagination_complete": quality.get("pagination_complete") is True,
        "display_name_coverage_complete": quality.get("display_name_coverage_complete") is True,
        "full_reconciliation": source.get("named_access_accounts") == source.get("matched_accounts") and source.get("unmatched_accounts") == 0,
        "users_present": len(users) > 0,
    }, "Named User Display Identity did not pass approved coverage and privacy-safe authority gates.")


def validate_actionable(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = read(ROOT / "runtime/data/users_access_actionable_drilldown_v1.json")
    authority = payload.get("authority") if isinstance(payload.get("authority"), dict) else {}
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    categories = payload.get("categories") if isinstance(payload.get("categories"), dict) else {}
    return enforce(record, {
        "status_ok": payload.get("status") == "ok",
        "safe_to_serve": authority.get("safe_to_serve") is True,
        "organisation_pagination_complete": source.get("organisation_pagination_complete") is True,
        "directory_pagination_complete": source.get("directory_pagination_complete") is True,
        "categories_present": len(categories) > 0,
    }, "Actionable Users & Access authority did not pass publish gates.")



def validate_project_inventory(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = read(ROOT / "runtime/data/project_inventory_authority_v1.json")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    authority = payload.get("authority") if isinstance(payload.get("authority"), dict) else {}
    projects = payload.get("projects") if isinstance(payload.get("projects"), list) else []
    sites = payload.get("sites") if isinstance(payload.get("sites"), list) else []
    monitored = summary.get("monitored_site_count")
    successful = summary.get("successful_site_count")
    visible = summary.get("visible_project_count")
    unique_pairs = {
        (str(row.get("site_key") or "").strip().lower(), str(row.get("project_key") or "").strip().upper())
        for row in projects if isinstance(row, dict)
    }
    gates = {
        "contract_present": bool(payload),
        "schema_valid": payload.get("schema") == "jom-project-inventory-authority-v1",
        "status_ok": payload.get("status") == "ok",
        "safe_to_publish": authority.get("safe_to_publish_project_inventory") is True,
        "all_site_pagination_complete": authority.get("pagination_complete_all_sites") is True and all(
            isinstance(site, dict) and site.get("status") == "ok" and site.get("pagination_complete") is True
            for site in sites
        ),
        "all_monitored_sites_successful": isinstance(monitored, int) and monitored > 0 and monitored == successful == len(sites),
        "project_count_reconciled": isinstance(visible, int) and visible == len(projects) == summary.get("collected_project_rows"),
        "no_duplicate_site_project_keys": summary.get("duplicate_site_project_key_count") == 0 and len(unique_pairs) == len(projects),
        "project_keys_complete": all(pair[0] and pair[1] for pair in unique_pairs),
    }
    return enforce(record, gates, "Project Inventory failed monitored-site, pagination, reconciliation, uniqueness, or completeness gates.")

def evidence(name: str) -> Dict[str, Any]:
    path = ROOT / "runtime/data" / name
    if not path.exists():
        return {"exists": False, "state": "MISSING"}
    payload = read(path)
    return {
        "exists": True,
        "state": "PRESENT" if payload else "INVALID_JSON",
        "schema": payload.get("schema"),
        "status": payload.get("status") or payload.get("overall_status") or payload.get("source_status"),
        "timestamp": payload.get("generated_at_utc") or payload.get("updated_at_utc"),
    }


def main() -> Dict[str, Any]:
    started = now()
    steps: List[Dict[str, Any]] = []
    overall = "failed"
    payload: Dict[str, Any] = {
        "schema": "jom-admin-enriched-refresh-status-v5.1",
        "generated_at_utc": started,
        "started_at_utc": started,
        "finished_at_utc": None,
        "running": True,
        "overall_status": "running",
        "dependency_order_enforced": True,
        "direct_module_named_access_chain": True,
        "named_access_postconditions_enforced": True,
        "current_step": None,
        "contracts": {},
        "steps": steps,
    }
    write(payload)
    definitions = [
        ("admin_api_enrichment", "Refresh Admin enrichment", [{"type": "module", "value": "app.builders.admin_enriched_sources"}, {"type": "script", "value": "admin_api_enrichment.py"}], [], None),
        ("admin_directory_users", "Refresh privacy-safe paginated Admin Directory authority", [{"type": "module", "value": "app.access.admin_named_access_endpoint_probe"}], [], None),
        ("admin_truth_v2", "Rebuild Admin Truth v2", [{"type": "module", "value": "app.builders.admin_truth_layer_v2"}, {"type": "script", "value": "scripts/build_admin_truth_layer_v2.py"}], ["admin_directory_users"], None),
        ("estate_resource_authority", "Refresh site-resource and ownership authority", [{"type": "module", "value": "app.builders.estate_resource_authority"}], [], classify_estate_resource_authority),
        ("project_inventory_authority", "Refresh read-only Project Inventory authority", [{"type": "module", "value": "app.builders.project_inventory_authority_v1"}], [], validate_project_inventory),
        ("admin_group_expansion", "Collect group-derived product access", [{"type": "module", "value": "app.access.collect_admin_group_expansion"}], ["admin_directory_users"], validate_group_expansion),
        ("named_access_truth_v2", "Build Named Access Truth v2", [{"type": "module", "value": "app.access.named_access_truth_v2"}], ["admin_group_expansion"], validate_named_truth),
        ("named_access_reconciliation_v2", "Reconcile Named Access Truth v2", [{"type": "module", "value": "app.access.reconcile_named_access_truth_v2"}], ["admin_truth_v2", "named_access_truth_v2"], validate_reconciliation),
        ("user_footprint", "Rebuild guarded User Footprint", [{"type": "module", "value": "app.access.user_footprint_source"}], ["named_access_reconciliation_v2"], validate_footprint),
        ("named_site_access_authority", "Rebuild privacy-minimised Named Site Access authority", [{"type": "module", "value": "app.builders.named_site_access_authority_v1"}], ["user_footprint"], validate_named_site),
        ("named_user_display_identity", "Refresh privacy-approved display identity", [{"type": "module", "value": "app.builders.named_user_display_identity_v1"}], ["admin_directory_users", "user_footprint", "named_site_access_authority"], validate_identity),
        ("verified_active_jira_users", "Refresh verified active Jira users", [{"type": "module", "value": "app.builders.verified_active_jira_users_v1"}], ["admin_directory_users"], None),
        ("users_access_actionable_drilldown", "Refresh actionable Users & Access drill-down authority", [{"type": "module", "value": "app.builders.users_access_actionable_drilldown_v1"}], ["admin_directory_users", "user_footprint", "named_site_access_authority", "named_user_display_identity"], validate_actionable),
        ("source_freshness", "Rebuild source freshness", [{"type": "module", "value": "app.audits.source_freshness"}, {"type": "script", "value": "scripts/audit_source_freshness.py"}], [], None),
        ("source_reliability", "Rebuild source reliability", [{"type": "module", "value": "app.audits.source_reliability"}, {"type": "script", "value": "scripts/source_reliability_audit.py"}], ["source_freshness"], None),
    ]
    try:
        for key, label, candidates, blocked_by, postcondition in definitions:
            payload["current_step"] = key
            payload["generated_at_utc"] = now()
            write(payload)
            print("START " + key, flush=True)
            record = resolve(candidates, key, label, steps, blocked_by=blocked_by)
            if postcondition and (record.get("status") == "ok" or key == "estate_resource_authority"):
                record = postcondition(record)
            steps.append(record)
            payload["steps"] = steps
            payload["generated_at_utc"] = now()
            write(payload)
            print("FINISH " + key + "=" + str(record.get("status")), flush=True)
        required_failures = [
            step for step in steps
            if step.get("status") not in {"ok", "advisory"}
        ]
        advisory_steps = [step for step in steps if step.get("status") == "advisory"]
        payload["advisory_count"] = len(advisory_steps)
        payload["advisories"] = [
            {
                "key": step.get("key"),
                "reason": step.get("advisory_reason"),
                "returncode": step.get("returncode"),
            }
            for step in advisory_steps
        ]
        if required_failures:
            overall = "attention"
        elif advisory_steps:
            overall = "ok_with_advisory"
        else:
            overall = "ok"
    except BaseException as exc:
        payload["fatal_error"] = f"{type(exc).__name__}: {exc}"
        overall = "failed"
    finally:
        names = [
            "admin_directory_users.json",
            "admin_group_expansion.json",
            "user_footprint.json",
            "named_site_access_authority_v1.json",
            "named_user_display_identity_v1.json",
            "verified_active_jira_users_v1.json",
            "users_access_actionable_drilldown_v1.json",
            "project_inventory_authority_v1.json",
        ]
        payload.update(
            generated_at_utc=now(),
            finished_at_utc=now(),
            running=False,
            current_step=None,
            overall_status=overall,
            contracts={name: evidence(name) for name in names},
        )
        write(payload)
    return payload


def run_pipeline() -> Dict[str, Any]:
    return main()


if __name__ == "__main__":
    result = main()
    raise SystemExit(0 if result.get("overall_status") in {"ok", "ok_with_advisory"} else 2)
