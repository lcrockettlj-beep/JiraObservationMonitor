from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from auth import get_valid_access_token
from jira_client import JiraApiClient
from trends import analyze_historical_trends

BASE_DIR = Path(__file__).resolve().parent
LATEST_RUN_PATH = BASE_DIR / "latest_run.json"
LATEST_RUN_PRETTY_PATH = BASE_DIR / "latest_run_pretty.json"
PARTIAL_RUN_PATH = BASE_DIR / "latest_run_safe_partial.json"
SNAPSHOT_DIR = BASE_DIR / "snapshots"
SNAPSHOT_INDEX_PATH = SNAPSHOT_DIR / "snapshot_index.json"
LATEST_SNAPSHOT_PATH = SNAPSHOT_DIR / "latest_snapshot.json"

LEGACY_IGNORED_SITE_NAMES = [name.strip().lower() for name in os.getenv("JOM_IGNORED_SITE_NAMES", "").split(",") if name.strip()]
MONITOR_ONLY_SITE_NAMES = [name.strip().lower() for name in os.getenv("JOM_MONITOR_ONLY_SITE_NAMES", "").split(",") if name.strip()]
ENABLE_AUDIT_CHECKS = str(os.getenv("JOM_ENABLE_AUDIT_CHECKS", "false")).strip().lower() == "true"
ENABLE_APPLICATION_ROLE_CHECKS = str(os.getenv("JOM_ENABLE_APPLICATION_ROLE_CHECKS", "false")).strip().lower() == "true"
PERMISSIONS_QUERY = os.getenv("JOM_PERMISSIONS_QUERY", "BROWSE_PROJECTS")
SEARCH_MAX_RESULTS = int(os.getenv("JOM_SEARCH_MAX_RESULTS", "1") or 1)

REQUIRED_SCOPES = ["read:jira-user", "read:jira-work"]
OPTIONAL_SCOPES = ["read:jira-project"]


def _now_strings() -> Tuple[str, str]:
    now_utc = datetime.now(timezone.utc)
    run_timestamp_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    collected_at_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    return run_timestamp_local, collected_at_utc



def _print(message: str) -> None:
    print(message, flush=True)



def _safe_json_write(path: Path, data: Dict[str, Any], pretty: bool = False) -> None:
    if pretty:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")



def _site_key_from_name(name: str) -> str:
    return str(name or "site").strip().lower().replace(" ", "-")



def _load_previous_snapshot() -> Dict[str, Any]:
    if not LATEST_SNAPSHOT_PATH.exists():
        return {}
    try:
        return json.loads(LATEST_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}



def _extract_previous_site_map(previous_snapshot: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    site_map: Dict[str, Dict[str, Any]] = {}
    for site in previous_snapshot.get("sites", []) or []:
        cloud_id = site.get("cloud_id")
        if cloud_id:
            site_map[cloud_id] = site
    return site_map



def _save_snapshot(latest_run: Dict[str, Any]) -> Dict[str, Any]:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    created_at_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    snapshot_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    snapshot_path = SNAPSHOT_DIR / f"snapshot_{snapshot_timestamp}.json"

    snapshot_data = {
        "snapshot_meta": {
            "snapshot_timestamp": snapshot_timestamp,
            "created_at_local": created_at_local,
            "source": "data_collector.py (safe mode patch 2.2)",
        },
        "sites": latest_run.get("sites", []),
    }

    _safe_json_write(snapshot_path, snapshot_data, pretty=True)
    _safe_json_write(LATEST_SNAPSHOT_PATH, snapshot_data, pretty=True)

    index_data = {"snapshots": []}
    if SNAPSHOT_INDEX_PATH.exists():
        try:
            index_data = json.loads(SNAPSHOT_INDEX_PATH.read_text(encoding="utf-8"))
        except Exception:
            index_data = {"snapshots": []}

    snapshots = index_data.get("snapshots", []) or []
    snapshots.append({
        "file": str(snapshot_path),
        "snapshot_timestamp": snapshot_timestamp,
        "created_at_local": created_at_local,
    })
    snapshots = snapshots[-50:]
    index_data["snapshots"] = snapshots
    _safe_json_write(SNAPSHOT_INDEX_PATH, index_data, pretty=True)

    return {
        "snapshot_file": str(snapshot_path),
        "latest_snapshot_file": str(LATEST_SNAPSHOT_PATH),
        "snapshot_index_file": str(SNAPSHOT_INDEX_PATH),
    }



def _status_from_risk(risk_score: int) -> str:
    if risk_score >= 6:
        return "critical"
    if risk_score >= 2:
        return "warning"
    return "stable"



def _build_issue_risk_signals(project_count: int, unresolved_total: int, updated_last_7d_total: int) -> List[str]:
    signals: List[str] = []
    if unresolved_total >= 200:
        signals.append("high_unresolved_backlog")
    elif unresolved_total >= 50:
        signals.append("moderate_unresolved_backlog")
    if updated_last_7d_total == 0 and project_count > 0:
        signals.append("no_recent_issue_updates_detected")
    return signals



def _save_partial(run_timestamp_local: str, collected_at_utc: str, processed_sites: List[Dict[str, Any]], accessible_resources: List[Dict[str, Any]]) -> None:
    partial = {
        "run_timestamp_local": run_timestamp_local,
        "raw_collection_summary": {
            "collected_at_utc": collected_at_utc,
            "accessible_resource_count": len(accessible_resources),
            "legacy_ignored_site_names_present_in_env": LEGACY_IGNORED_SITE_NAMES,
            "monitor_only_site_names": MONITOR_ONLY_SITE_NAMES,
            "collector": "data_collector.py (safe mode partial patch 2.2)",
        },
        "summary": {
            "site_count": len(processed_sites),
            "project_count_total": sum(int(site.get("project_count", 0) or 0) for site in processed_sites),
            "issue_count_total": sum(int(site.get("issue_count_total", 0) or 0) for site in processed_sites),
            "issue_count_unresolved_total": sum(int(site.get("issue_count_unresolved", 0) or 0) for site in processed_sites),
            "issue_count_updated_last_7d_total": sum(int(site.get("issue_count_updated_last_7d", 0) or 0) for site in processed_sites),
        },
        "sites": processed_sites,
        "partial": True,
    }
    _safe_json_write(PARTIAL_RUN_PATH, partial, pretty=True)



def _collect_site(resource: Dict[str, Any], client: JiraApiClient, previous_site_map: Dict[str, Dict[str, Any]], first_snapshot: bool) -> Dict[str, Any]:
    site_started = datetime.now(timezone.utc)
    cloud_id = resource.get("id", "")
    site_name = resource.get("name", "")
    site_url = resource.get("url", "")
    site_key = _site_key_from_name(site_name)
    granted_scopes = resource.get("scopes", []) or []
    granted_scope_set = {str(x).strip() for x in granted_scopes}

    permission_limited_checks: List[str] = []
    scope_notes: List[str] = []
    endpoint_results: Dict[str, Any] = {}
    status_reasons: List[str] = []

    missing_required_scopes = [scope for scope in REQUIRED_SCOPES if scope not in granted_scope_set]
    missing_optional_scopes = [scope for scope in OPTIONAL_SCOPES if scope not in granted_scope_set]
    if missing_required_scopes:
        permission_limited_checks.append("missing_required_scopes")
        status_reasons.append(f"Missing required scopes: {', '.join(missing_required_scopes)}")
    if missing_optional_scopes:
        scope_notes.append(f"Optional scopes not present in accessible-resource list: {', '.join(missing_optional_scopes)}")

    _print(f"  -> {site_name}: serverInfo")
    server_info = client.get_server_info(cloud_id)
    endpoint_results["server_info"] = server_info
    if not server_info.get("ok"):
        permission_limited_checks.append("server_info")
        status_reasons.append("Could not read Jira server info.")

    _print(f"  -> {site_name}: myself")
    myself = client.get_myself(cloud_id)
    endpoint_results["myself"] = myself
    if not myself.get("ok"):
        permission_limited_checks.append("myself")
        status_reasons.append("Could not confirm API identity on the site.")

    _print(f"  -> {site_name}: mypermissions ({PERMISSIONS_QUERY})")
    permissions = client.get_my_permissions(cloud_id, permissions=PERMISSIONS_QUERY)
    endpoint_results["my_permissions"] = permissions
    if not permissions.get("ok"):
        permission_limited_checks.append("my_permissions")
    else:
        perms = (permissions.get("data", {}) or {}).get("permissions", {}) or {}
        browse_info = perms.get("BROWSE_PROJECTS", {}) or {}
        if browse_info.get("havePermission") is False:
            permission_limited_checks.append("browse_projects")
            status_reasons.append("Browse projects permission not confirmed for this site context.")

    if ENABLE_APPLICATION_ROLE_CHECKS:
        _print(f"  -> {site_name}: applicationrole")
        application_roles = client.get_application_roles(cloud_id)
        endpoint_results["application_roles"] = application_roles
        if not application_roles.get("ok"):
            permission_limited_checks.append("application_roles")
    else:
        endpoint_results["application_roles"] = {"ok": False, "skipped": True, "reason": "Safe mode patch 2.2 disabled application role checks."}

    if ENABLE_AUDIT_CHECKS:
        _print(f"  -> {site_name}: audit records")
        audit_records = client.get_audit_records(cloud_id)
        endpoint_results["audit_records"] = audit_records
        audit_status = "ok" if audit_records.get("ok") else "permission_limited"
        if not audit_records.get("ok"):
            permission_limited_checks.append("audit_records")
    else:
        endpoint_results["audit_records"] = {"ok": False, "skipped": True, "reason": "Safe mode patch 2.2 disabled audit checks."}
        audit_status = "skipped_safe_mode"

    _print(f"  -> {site_name}: project search")
    projects_result = client.get_projects(cloud_id)
    endpoint_results["projects"] = projects_result
    projects = projects_result.get("data", []) if projects_result.get("ok") else []
    if not projects_result.get("ok"):
        permission_limited_checks.append("project_search")
        status_reasons.append("Could not read Jira project search results.")

    project_rows: List[Dict[str, Any]] = []
    for project in projects[:25]:
        project_rows.append({
            "key": project.get("key", ""),
            "name": project.get("name", ""),
            "projectTypeKey": project.get("projectTypeKey", ""),
            "simplified": project.get("simplified"),
        })

    _print(f"  -> {site_name}: issue total count (search/jql maxResults={SEARCH_MAX_RESULTS})")
    total_result = client.search_issue_count(cloud_id, "order by created DESC")
    endpoint_results["issue_total_count"] = total_result
    if not total_result.get("ok"):
        permission_limited_checks.append("issue_total_count")
    issue_count_total = int((total_result.get("data", {}) or {}).get("total", 0) or 0) if total_result.get("ok") else 0

    _print(f"  -> {site_name}: unresolved count (search/jql maxResults={SEARCH_MAX_RESULTS})")
    unresolved_result = client.search_issue_count(cloud_id, "resolution = Unresolved")
    endpoint_results["issue_unresolved_count"] = unresolved_result
    if not unresolved_result.get("ok"):
        permission_limited_checks.append("issue_unresolved_count")
    issue_count_unresolved = int((unresolved_result.get("data", {}) or {}).get("total", 0) or 0) if unresolved_result.get("ok") else 0

    _print(f"  -> {site_name}: updated last 7d count (search/jql maxResults={SEARCH_MAX_RESULTS})")
    updated_result = client.search_issue_count(cloud_id, "updated >= -7d")
    endpoint_results["issue_updated_last_7d_count"] = updated_result
    if not updated_result.get("ok"):
        permission_limited_checks.append("issue_updated_last_7d_count")
    issue_count_updated_last_7d = int((updated_result.get("data", {}) or {}).get("total", 0) or 0) if updated_result.get("ok") else 0

    issue_risk_signals = _build_issue_risk_signals(len(projects), issue_count_unresolved, issue_count_updated_last_7d)
    operational_risk_signals: List[str] = []
    if permission_limited_checks:
        operational_risk_signals.append("permission_limited_checks_present")
    if not projects_result.get("ok"):
        operational_risk_signals.append("project_visibility_limited")
    if audit_status != "ok" and audit_status != "skipped_safe_mode":
        operational_risk_signals.append("audit_visibility_limited")
    if scope_notes:
        operational_risk_signals.append("optional_scope_notes_present")

    issue_risk_score = 0
    if issue_count_unresolved >= 200:
        issue_risk_score += 4
    elif issue_count_unresolved >= 50:
        issue_risk_score += 2
    if issue_count_updated_last_7d == 0 and len(projects) > 0:
        issue_risk_score += 1

    operational_risk_score = 0
    if permission_limited_checks:
        operational_risk_score += 2
    if missing_required_scopes:
        operational_risk_score += 3

    risk_score = issue_risk_score + operational_risk_score
    status = _status_from_risk(risk_score)
    if not status_reasons:
        if status == "stable":
            status_reasons.append("Safe mode patch 2.2 live Jira collection succeeded with no material risk signals.")
        else:
            status_reasons.append("Safe mode patch 2.2 live Jira collection completed with risk indicators that require review.")

    previous_site = previous_site_map.get(cloud_id, {})
    previous_total = int(previous_site.get("issue_count_total", 0) or 0)
    previous_unresolved = int(previous_site.get("issue_count_unresolved", 0) or 0)
    previous_project_count = int(previous_site.get("project_count", 0) or 0)

    collected_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    collection_duration_seconds = round((datetime.now(timezone.utc) - site_started).total_seconds(), 3)
    failed_api_checks = len(set(permission_limited_checks))

    return {
        "site_key": site_key,
        "name": site_name,
        "url": site_url,
        "cloud_id": cloud_id,
        "collected_at_utc": collected_at_utc,
        "collection_duration_seconds": collection_duration_seconds,
        "project_count": len(projects),
        "project_rows": project_rows,
        "issue_count_total": issue_count_total,
        "issue_count_unresolved": issue_count_unresolved,
        "issue_count_updated_last_7d": issue_count_updated_last_7d,
        "project_count_delta": len(projects) - previous_project_count,
        "total_users_delta": 0,
        "active_users_delta": 0,
        "inactive_users_delta": 0,
        "issue_count_total_delta": issue_count_total - previous_total,
        "issue_count_unresolved_delta": issue_count_unresolved - previous_unresolved,
        "user_summary": {
            "total_users": None,
            "active_users": None,
            "inactive_users": None,
            "source": "Pending Admin API capability or later user-collection expansion",
        },
        "licence_summary": {
            "licensed_users_estimate": None,
            "source": "Pending Admin/API enrichment",
        },
        "risk_score": risk_score,
        "issue_risk_score": issue_risk_score,
        "operational_risk_score": operational_risk_score,
        "status": status,
        "status_reasons": status_reasons,
        "scope_notes": scope_notes,
        "growth_status": "growing" if (len(projects) - previous_project_count) > 0 else "stable",
        "permission_limited_checks": sorted(set(permission_limited_checks)),
        "blocking_failed_checks": sorted(set([x for x in permission_limited_checks if x in ("server_info", "myself", "project_search", "missing_required_scopes", "browse_projects")])),
        "issue_risk_signals": issue_risk_signals,
        "operational_risk_signals": operational_risk_signals,
        "failed_api_checks": failed_api_checks,
        "audit_status": audit_status,
        "audit_api_access": audit_status == "ok",
        "licence_status": "pending_enrichment",
        "licence_api_access": False,
        "snapshot_baseline": first_snapshot,
        "endpoint_results": endpoint_results,
    }



def _build_comparison(current_sites: List[Dict[str, Any]], previous_site_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    changes: List[Dict[str, Any]] = []
    for site in current_sites:
        name = site.get("name", "")
        cloud_id = site.get("cloud_id", "")
        previous = previous_site_map.get(cloud_id)
        if not previous:
            changes.append({
                "severity": "info",
                "change_type": "new_site_snapshot_baseline",
                "site_name": name,
                "detail": f"No previous snapshot found for {name}; baseline established.",
            })
            continue

        if int(site.get("project_count_delta", 0) or 0) != 0:
            changes.append({
                "severity": "info",
                "change_type": "project_count_changed",
                "site_name": name,
                "detail": f"Project count delta = {site.get('project_count_delta', 0)}",
            })

        unresolved_delta = int(site.get("issue_count_unresolved_delta", 0) or 0)
        if unresolved_delta >= 10:
            changes.append({
                "severity": "warning",
                "change_type": "unresolved_backlog_increase",
                "site_name": name,
                "detail": f"Unresolved issue delta = {unresolved_delta}",
            })

        if site.get("status") == "critical":
            changes.append({
                "severity": "critical",
                "change_type": "site_status_critical",
                "site_name": name,
                "detail": "Site is currently scored as critical.",
            })

    return {
        "has_previous_snapshot": bool(previous_site_map),
        "change_count": len(changes),
        "info_change_count": len([x for x in changes if x.get("severity") == "info"]),
        "warning_change_count": len([x for x in changes if x.get("severity") == "warning"]),
        "critical_change_count": len([x for x in changes if x.get("severity") == "critical"]),
        "changes": changes,
    }



def _build_latest_run(client: JiraApiClient) -> Dict[str, Any]:
    run_timestamp_local, collected_at_utc = _now_strings()
    resources = client.list_accessible_resources()
    _print(f"Accessible Jira resources returned: {len(resources)}")

    monitored_resources: List[Dict[str, Any]] = []
    for item in resources:
        site_name = str(item.get("name", "")).strip().lower()
        if MONITOR_ONLY_SITE_NAMES and site_name not in MONITOR_ONLY_SITE_NAMES:
            continue
        monitored_resources.append(item)

    _print(f"Sites selected for safe mode patch 2.2 monitoring: {len(monitored_resources)}")
    previous_snapshot = _load_previous_snapshot()
    previous_site_map = _extract_previous_site_map(previous_snapshot)
    first_snapshot = not bool(previous_site_map)

    site_results: List[Dict[str, Any]] = []
    for index, resource in enumerate(monitored_resources, start=1):
        site_name = resource.get("name", "")
        _print(f"[{index}/{len(monitored_resources)}] Collecting site: {site_name}")
        try:
            site_record = _collect_site(resource, client, previous_site_map, first_snapshot)
        except Exception as exc:
            site_record = {
                "site_key": _site_key_from_name(site_name),
                "name": site_name,
                "url": resource.get("url", ""),
                "cloud_id": resource.get("id", ""),
                "collected_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "collection_duration_seconds": 0,
                "project_count": 0,
                "project_rows": [],
                "issue_count_total": 0,
                "issue_count_unresolved": 0,
                "issue_count_updated_last_7d": 0,
                "project_count_delta": 0,
                "total_users_delta": 0,
                "active_users_delta": 0,
                "inactive_users_delta": 0,
                "issue_count_total_delta": 0,
                "issue_count_unresolved_delta": 0,
                "user_summary": {
                    "total_users": None,
                    "active_users": None,
                    "inactive_users": None,
                    "source": "Collector exception before user enrichment",
                },
                "licence_summary": {
                    "licensed_users_estimate": None,
                    "source": "Collector exception before licence enrichment",
                },
                "risk_score": 8,
                "issue_risk_score": 0,
                "operational_risk_score": 8,
                "status": "critical",
                "status_reasons": [f"Collector exception: {exc}"],
                "scope_notes": [],
                "growth_status": "unknown",
                "permission_limited_checks": ["collector_exception"],
                "blocking_failed_checks": ["collector_exception"],
                "issue_risk_signals": [],
                "operational_risk_signals": ["collector_exception"],
                "failed_api_checks": 1,
                "audit_status": "collector_exception",
                "audit_api_access": False,
                "licence_status": "collector_exception",
                "licence_api_access": False,
                "snapshot_baseline": first_snapshot,
                "endpoint_results": {"collector_exception": str(exc)},
            }
        site_results.append(site_record)
        _save_partial(run_timestamp_local, collected_at_utc, site_results, resources)
        _print(f"Completed site: {site_name} | projects={site_record.get('project_count', 0)} | issues={site_record.get('issue_count_total', 0)} | unresolved={site_record.get('issue_count_unresolved', 0)} | status={site_record.get('status', '')}")

    site_results.sort(key=lambda item: item.get("name", ""))

    summary = {
        "site_count": len(site_results),
        "project_count_total": sum(int(site.get("project_count", 0) or 0) for site in site_results),
        "issue_count_total": sum(int(site.get("issue_count_total", 0) or 0) for site in site_results),
        "issue_count_unresolved_total": sum(int(site.get("issue_count_unresolved", 0) or 0) for site in site_results),
        "issue_count_updated_last_7d_total": sum(int(site.get("issue_count_updated_last_7d", 0) or 0) for site in site_results),
    }

    risk_summary = {
        "stable_site_count": len([site for site in site_results if site.get("status") == "stable"]),
        "warning_site_count": len([site for site in site_results if site.get("status") == "warning"]),
        "critical_site_count": len([site for site in site_results if site.get("status") == "critical"]),
        "permission_limited_site_count": len([site for site in site_results if site.get("permission_limited_checks")]),
    }

    delta_summary = {
        "project_delta_total": sum(int(site.get("project_count_delta", 0) or 0) for site in site_results),
        "total_users_delta_total": 0,
        "active_users_delta_total": 0,
        "inactive_users_delta_total": 0,
        "licensed_users_estimate_delta_total": 0,
    }

    comparison = _build_comparison(site_results, previous_site_map)

    latest_run = {
        "run_timestamp_local": run_timestamp_local,
        "raw_collection_summary": {
            "collected_at_utc": collected_at_utc,
            "accessible_resource_count": len(resources),
            "monitored_site_count": len(site_results),
            "legacy_ignored_site_names_present_in_env": LEGACY_IGNORED_SITE_NAMES,
            "monitor_only_site_names": MONITOR_ONLY_SITE_NAMES,
            "note": "Safe mode patch 2.2 monitors the whole accessible estate by default. Legacy ignored site names are recorded but not automatically excluded.",
            "required_scopes": REQUIRED_SCOPES,
            "optional_scopes": OPTIONAL_SCOPES,
            "permissions_query": PERMISSIONS_QUERY,
            "search_max_results": SEARCH_MAX_RESULTS,
            "safe_mode": True,
            "safe_mode_features": {
                "sequential_site_processing": True,
                "progress_logging": True,
                "partial_file_written": str(PARTIAL_RUN_PATH),
                "audit_checks_enabled": ENABLE_AUDIT_CHECKS,
                "application_role_checks_enabled": ENABLE_APPLICATION_ROLE_CHECKS,
                "per_project_issue_loops": False,
                "search_endpoint": "/rest/api/3/search/jql",
                "mypermissions_fixed": True,
                "search_max_results_fixed": True,
            },
            "collector": "data_collector.py (safe mode patch 2.2)",
        },
        "summary": summary,
        "risk_summary": risk_summary,
        "delta_summary": delta_summary,
        "sites": site_results,
        "comparison": comparison,
        "historical_trends": {},
        "snapshot_files": [],
        "report_files": [],
    }

    snapshot_files = _save_snapshot(latest_run)
    latest_run["snapshot_files"] = [snapshot_files]

    try:
        latest_run["historical_trends"] = analyze_historical_trends(lookback=10)
    except Exception as exc:
        latest_run["historical_trends"] = {
            "has_history": False,
            "lookback_snapshots": 0,
            "site_trends": [],
            "summary": {
                "site_count": 0,
                "warning_or_critical_streak_sites": 0,
                "rising_unresolved_sites": 0,
                "rising_risk_sites": 0,
                "recurring_blocking_failure_sites": 0,
            },
            "error": str(exc),
        }

    return latest_run



def main() -> int:
    _print("Starting Step 2.2 Safe Mode patch live Jira collector...")
    access_token = get_valid_access_token()
    client = JiraApiClient(access_token=access_token)
    latest_run = _build_latest_run(client)
    _safe_json_write(LATEST_RUN_PATH, latest_run, pretty=False)
    _safe_json_write(LATEST_RUN_PRETTY_PATH, latest_run, pretty=True)

    _print("Step 2.2 Safe Mode patch live Jira collection complete.")
    _print(f"Monitored sites: {latest_run.get('summary', {}).get('site_count', 0)}")
    _print(f"Projects total: {latest_run.get('summary', {}).get('project_count_total', 0)}")
    _print(f"Issues total: {latest_run.get('summary', {}).get('issue_count_total', 0)}")
    _print(f"Unresolved total: {latest_run.get('summary', {}).get('issue_count_unresolved_total', 0)}")
    _print(f"latest_run.json: {LATEST_RUN_PATH}")
    _print(f"latest_run_pretty.json: {LATEST_RUN_PRETTY_PATH}")
    _print(f"latest_run_safe_partial.json: {PARTIAL_RUN_PATH}")
    _print(f"latest_snapshot.json: {LATEST_SNAPSHOT_PATH}")
    _print(f"snapshot_index.json: {SNAPSHOT_INDEX_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
