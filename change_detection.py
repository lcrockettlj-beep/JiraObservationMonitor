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


def load_latest_run_change_detection(file_name="latest_run.json"):
    if not os.path.exists(file_name):
        return {
            "has_current_run": False,
            "source_file": file_name,
            "summary": {},
            "sites": [],
            "site_map": {},
            "comparison_changes": [],
            "excluded_sites": [],
        }

    try:
        with open(file_name, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return {
            "has_current_run": False,
            "source_file": file_name,
            "summary": {},
            "sites": [],
            "site_map": {},
            "comparison_changes": [],
            "excluded_sites": [],
        }

    comparison = data.get("comparison", {}) or {}
    delta_summary = data.get("delta_summary", {}) or {}
    historical = data.get("historical_trends", {}) or {}
    historical_summary = historical.get("summary", {}) or {}
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

    site_results = []
    site_map = {}

    for site in data.get("sites", []) or []:
        if not isinstance(site, dict):
            continue

        site_key = _site_key_for_record(site)
        cloud_id = site.get("cloud_id")
        site_name = site.get("name")

        trend = None
        if cloud_id and cloud_id in trend_map_by_cloud_id:
            trend = trend_map_by_cloud_id.get(cloud_id)
        elif site_name:
            trend = trend_map_by_name.get(str(site_name).strip().lower())

        trend_signals = []
        recurring_permission_limits = []
        recurring_operational_signals = []
        recurring_blocking_failures = []
        snapshot_count = 0

        if trend:
            trend_signals = trend.get("trend_signals", []) or []
            recurring_permission_limits = trend.get("recurring_permission_limits", []) or []
            recurring_operational_signals = trend.get("recurring_operational_signals", []) or []
            recurring_blocking_failures = trend.get("recurring_blocking_failures", []) or []
            snapshot_count = trend.get("snapshot_count", 0) or 0

        new_site_candidate = bool(site.get("snapshot_baseline")) or (
            comparison.get("has_previous_snapshot") and snapshot_count <= 1
        )

        attention_reasons = []
        if new_site_candidate:
            attention_reasons.append("new_site_candidate")
        if (site.get("project_count_delta") or 0) != 0:
            attention_reasons.append("project_count_changed")
        if (site.get("total_users_delta") or 0) != 0:
            attention_reasons.append("total_users_changed")
        if (site.get("active_users_delta") or 0) != 0:
            attention_reasons.append("active_users_changed")
        if (site.get("inactive_users_delta") or 0) != 0:
            attention_reasons.append("inactive_users_changed")
        if site.get("permission_limited_checks"):
            attention_reasons.append("permission_limited_checks")
        if trend_signals:
            attention_reasons.extend(trend_signals)

        site_record = {
            "site": site_key,
            "site_name": site_name,
            "url": site.get("url"),
            "cloud_id": cloud_id,
            "status": site.get("status"),
            "risk_score": site.get("risk_score"),
            "project_count": site.get("project_count"),
            "project_count_delta": site.get("project_count_delta", 0),
            "total_users": (site.get("user_summary", {}) or {}).get("total_users"),
            "total_users_delta": site.get("total_users_delta", 0),
            "active_users": (site.get("user_summary", {}) or {}).get("active_users"),
            "active_users_delta": site.get("active_users_delta", 0),
            "inactive_users": (site.get("user_summary", {}) or {}).get("inactive_users"),
            "inactive_users_delta": site.get("inactive_users_delta", 0),
            "licensed_users_estimate": (site.get("licence_summary", {}) or {}).get("licensed_users_estimate"),
            "licensed_users_estimate_delta": site.get("licensed_users_estimate_delta", 0),
            "growth_status": site.get("growth_status"),
            "audit_status": site.get("audit_status"),
            "audit_api_access": site.get("audit_api_access"),
            "licence_status": site.get("licence_status"),
            "licence_api_access": site.get("licence_api_access"),
            "permission_limited_checks": site.get("permission_limited_checks", []) or [],
            "status_reasons": site.get("status_reasons", []) or [],
            "snapshot_baseline": bool(site.get("snapshot_baseline")),
            "trend_signals": trend_signals,
            "snapshot_count": snapshot_count,
            "new_site_candidate": new_site_candidate,
            "recurring_permission_limits": recurring_permission_limits,
            "recurring_operational_signals": recurring_operational_signals,
            "recurring_blocking_failures": recurring_blocking_failures,
            "attention_reasons": attention_reasons,
        }

        site_results.append(site_record)

        if site_key:
            site_map[site_key] = site_record

    summary = {
        "run_timestamp_local": data.get("run_timestamp_local"),
        "collected_at_utc": raw_collection_summary.get("collected_at_utc"),
        "site_count": (data.get("summary", {}) or {}).get("site_count", 0),
        "excluded_site_count": len(excluded_sites),
        "has_previous_snapshot": bool(comparison.get("has_previous_snapshot", False)),
        "change_count": comparison.get("change_count", 0),
        "info_change_count": comparison.get("info_change_count", 0),
        "warning_change_count": comparison.get("warning_change_count", 0),
        "critical_change_count": comparison.get("critical_change_count", 0),
        "project_delta_total": delta_summary.get("project_delta_total", 0),
        "total_users_delta_total": delta_summary.get("total_users_delta_total", 0),
        "active_users_delta_total": delta_summary.get("active_users_delta_total", 0),
        "inactive_users_delta_total": delta_summary.get("inactive_users_delta_total", 0),
        "licensed_users_estimate_delta_total": delta_summary.get("licensed_users_estimate_delta_total", 0),
        "rising_risk_site_count": historical_summary.get("rising_risk_sites", 0),
        "warning_or_critical_streak_site_count": historical_summary.get("warning_or_critical_streak_sites", 0),
        "recurring_blocking_failure_site_count": historical_summary.get("recurring_blocking_failure_sites", 0),
        "new_site_candidate_count": len([s for s in site_results if s.get("new_site_candidate")]),
    }

    return {
        "has_current_run": True,
        "source_file": file_name,
        "summary": summary,
        "sites": site_results,
        "site_map": site_map,
        "comparison_changes": comparison.get("changes", []) or [],
        "excluded_sites": excluded_sites,
    }