import json
import os


def _normalise_site_key_from_url(url):
    if not url:
        return None
    text = str(url).strip().lower()
    mappings = {
        "gli-it-project.atlassian.net": "gli-it-project",
        "gli-delivery-tm.atlassian.net": "gli-delivery-tm",
        "gli-global-technology.atlassian.net": "gli-global-technology",
    }
    for needle, site_key in mappings.items():
        if needle in text:
            return site_key
    return None


def _normalise_site_key_from_name(name):
    if not name:
        return None
    text = str(name).strip().lower()
    mappings = {
        "gli-it-project": "gli-it-project",
        "gli-delivery-tm": "gli-delivery-tm",
        "gli-global-technology": "gli-global-technology",
        "gli it project": "gli-it-project",
        "gli delivery tm": "gli-delivery-tm",
        "gli global technology": "gli-global-technology",
    }
    return mappings.get(text)


def _site_key_for_record(site):
    site_key = _normalise_site_key_from_url(site.get("url"))
    if site_key:
        return site_key
    return _normalise_site_key_from_name(site.get("name"))


def _site_status_group(status):
    if status in {"critical", "warning", "healthy", "stable"}:
        return status
    return "unknown"


def load_site_discovery_from_latest_run(file_name="latest_run.json"):
    if not os.path.exists(file_name):
        return {
            "has_current_run": False,
            "source_file": file_name,
            "summary": {},
            "tracked_sites": [],
            "excluded_sites": [],
            "discovered_sites": [],
            "new_site_candidates": [],
            "tracked_site_map": {},
        }

    try:
        with open(file_name, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return {
            "has_current_run": False,
            "source_file": file_name,
            "summary": {},
            "tracked_sites": [],
            "excluded_sites": [],
            "discovered_sites": [],
            "new_site_candidates": [],
            "tracked_site_map": {},
        }

    sites = data.get("sites", []) or []
    comparison = data.get("comparison", {}) or {}
    historical = data.get("historical_trends", {}) or {}
    raw_collection_summary = data.get("raw_collection_summary", {}) or {}
    excluded_sites = raw_collection_summary.get("excluded_sites", []) or []

    trend_map_by_cloud_id = {}
    trend_map_by_name = {}
    for trend in historical.get("site_trends", []) or []:
        if not isinstance(trend, dict):
            continue
        cloud_id = trend.get("cloud_id")
        name = str(trend.get("name", "")).strip().lower()
        if cloud_id:
            trend_map_by_cloud_id[cloud_id] = trend
        if name:
            trend_map_by_name[name] = trend

    tracked_sites = []
    tracked_site_map = {}
    new_site_candidates = []

    for site in sites:
        if not isinstance(site, dict):
            continue

        site_name = site.get("name", "")
        site_key = _site_key_for_record(site) or site_name
        cloud_id = site.get("cloud_id", "")
        trend = trend_map_by_cloud_id.get(cloud_id) or trend_map_by_name.get(str(site_name).strip().lower()) or {}
        snapshot_count = trend.get("snapshot_count", 0) or 0
        new_site_candidate = bool(site.get("snapshot_baseline")) or (
            comparison.get("has_previous_snapshot") and snapshot_count <= 1
        )

        record = {
            "site_key": site_key,
            "site_name": site_name,
            "url": site.get("url", ""),
            "cloud_id": cloud_id,
            "scope_classification": "tracked",
            "status": site.get("status", ""),
            "status_group": _site_status_group(site.get("status", "")),
            "risk_score": site.get("risk_score", 0),
            "project_count": site.get("project_count", 0),
            "project_count_delta": site.get("project_count_delta", 0),
            "total_users": (site.get("user_summary", {}) or {}).get("total_users", 0),
            "active_users": (site.get("user_summary", {}) or {}).get("active_users", 0),
            "inactive_users": (site.get("user_summary", {}) or {}).get("inactive_users", 0),
            "audit_status": site.get("audit_status", ""),
            "audit_api_access": "Yes" if bool(site.get("audit_api_access")) else "No",
            "licence_status": site.get("licence_status", ""),
            "licence_api_access": "Yes" if bool(site.get("licence_api_access")) else "No",
            "permission_limited_checks": ", ".join(site.get("permission_limited_checks", []) or []),
            "status_reasons": ", ".join(site.get("status_reasons", []) or []),
            "snapshot_count": snapshot_count,
            "new_site_candidate": "Yes" if new_site_candidate else "No",
        }
        tracked_sites.append(record)
        tracked_site_map[site_key] = record
        if new_site_candidate:
            new_site_candidates.append(record)

    excluded_rows = []
    for site in excluded_sites:
        if not isinstance(site, dict):
            continue
        excluded_rows.append({
            "site_key": _site_key_for_record(site) or site.get("name", ""),
            "site_name": site.get("name", ""),
            "url": site.get("url", ""),
            "cloud_id": site.get("cloud_id", ""),
            "scope_classification": "excluded",
            "status": "excluded",
            "status_group": "excluded",
            "risk_score": "",
            "project_count": "",
            "project_count_delta": "",
            "total_users": "",
            "active_users": "",
            "inactive_users": "",
            "audit_status": "",
            "audit_api_access": "",
            "licence_status": "",
            "licence_api_access": "",
            "permission_limited_checks": "",
            "status_reasons": "outside_current_scope",
            "snapshot_count": "",
            "new_site_candidate": "No",
        })

    discovered_sites = tracked_sites + excluded_rows
    discovered_sites.sort(key=lambda row: (str(row.get("scope_classification", "")).lower(), str(row.get("site_name", "")).lower()))
    tracked_sites.sort(key=lambda row: str(row.get("site_name", "")).lower())
    excluded_rows.sort(key=lambda row: str(row.get("site_name", "")).lower())
    new_site_candidates.sort(key=lambda row: str(row.get("site_name", "")).lower())

    summary = {
        "tracked_site_count": len(tracked_sites),
        "excluded_site_count": len(excluded_rows),
        "discovered_site_count": len(discovered_sites),
        "new_site_candidate_count": len(new_site_candidates),
        "has_previous_snapshot": bool(comparison.get("has_previous_snapshot", False)),
        "run_timestamp_local": data.get("run_timestamp_local"),
        "collected_at_utc": raw_collection_summary.get("collected_at_utc"),
    }

    return {
        "has_current_run": True,
        "source_file": file_name,
        "summary": summary,
        "tracked_sites": tracked_sites,
        "excluded_sites": excluded_rows,
        "discovered_sites": discovered_sites,
        "new_site_candidates": new_site_candidates,
        "tracked_site_map": tracked_site_map,
    }


def build_site_discovery_drilldowns(site_discovery):
    site_discovery = site_discovery or {}
    summary = site_discovery.get("summary", {}) or {}
    tracked_sites = site_discovery.get("tracked_sites", []) or []
    excluded_sites = site_discovery.get("excluded_sites", []) or []
    discovered_sites = site_discovery.get("discovered_sites", []) or []
    new_site_candidates = site_discovery.get("new_site_candidates", []) or []

    common_columns = [
        "site_name",
        "scope_classification",
        "status",
        "risk_score",
        "project_count",
        "project_count_delta",
        "total_users",
        "active_users",
        "inactive_users",
        "audit_status",
        "audit_api_access",
        "licence_status",
        "licence_api_access",
        "permission_limited_checks",
        "new_site_candidate",
        "url",
    ]

    return {
        "discovery::summary": {
            "title": "Dynamic Site Discovery Summary",
            "reason": "This summary shows the current discovered estate split between tracked operational sites and excluded/out-of-scope sites using the latest collector snapshot.",
            "atlassian_area": "Atlassian Administration → Site management / Organisation overview",
            "columns": ["metric", "value"],
            "rows": [
                {"metric": "Tracked site count", "value": summary.get("tracked_site_count", 0)},
                {"metric": "Excluded site count", "value": summary.get("excluded_site_count", 0)},
                {"metric": "Discovered site count", "value": summary.get("discovered_site_count", 0)},
                {"metric": "New site candidate count", "value": summary.get("new_site_candidate_count", 0)},
                {"metric": "Has previous snapshot", "value": "Yes" if summary.get("has_previous_snapshot") else "No"},
                {"metric": "Run timestamp local", "value": summary.get("run_timestamp_local", "")},
                {"metric": "Collected at UTC", "value": summary.get("collected_at_utc", "")},
            ],
        },
        "discovery::tracked_sites": {
            "title": "Dynamic Site Discovery — Tracked Sites",
            "reason": "These sites are currently part of the monitored operational Jira scope and were returned by the latest collector run.",
            "atlassian_area": "Atlassian Administration → Site management / Organisation overview",
            "columns": common_columns,
            "rows": tracked_sites,
        },
        "discovery::excluded_sites": {
            "title": "Dynamic Site Discovery — Excluded Sites",
            "reason": "These sites were discovered by the collector but are currently outside the monitored operational Jira scope.",
            "atlassian_area": "Atlassian Administration → Site management / Organisation overview",
            "columns": ["site_name", "scope_classification", "status_reasons", "url", "cloud_id"],
            "rows": excluded_sites,
        },
        "discovery::all_sites": {
            "title": "Dynamic Site Discovery — All Discovered Sites",
            "reason": "This view combines tracked sites and excluded/out-of-scope sites into one discovered-site registry view based on the latest collector snapshot.",
            "atlassian_area": "Atlassian Administration → Site management / Organisation overview",
            "columns": common_columns,
            "rows": discovered_sites,
        },
        "discovery::new_site_candidates": {
            "title": "Dynamic Site Discovery — New Site Candidates",
            "reason": "These sites may represent newly observed or baseline-only monitored sites based on snapshot history and should be reviewed for operational classification.",
            "atlassian_area": "Atlassian Administration → Site management / Organisation overview",
            "columns": common_columns,
            "rows": new_site_candidates,
        },
    }
