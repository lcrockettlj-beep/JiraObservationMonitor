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


def _safe_join(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if str(v).strip())
    return str(value)


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
    trend_map_by_site_key = {}
    for trend in historical.get("site_trends", []) or []:
        if not isinstance(trend, dict):
            continue
        cloud_id = trend.get("cloud_id")
        name = str(trend.get("name", "")).strip().lower()
        site_key = trend.get("site_key")
        if cloud_id:
            trend_map_by_cloud_id[cloud_id] = trend
        if name:
            trend_map_by_name[name] = trend
        if site_key:
            trend_map_by_site_key[site_key] = trend

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
        elif site_key and site_key in trend_map_by_site_key:
            trend = trend_map_by_site_key.get(site_key)
        elif site_name:
            trend = trend_map_by_name.get(str(site_name).strip().lower())

        trend_signals = []
        recurring_permission_limits = []
        recurring_operational_signals = []
        recurring_blocking_failures = []
        snapshot_count = 0
        trend_score = 0
        if trend:
            trend_signals = trend.get("trend_signals", []) or []
            recurring_permission_limits = trend.get("recurring_permission_limits", []) or []
            recurring_operational_signals = trend.get("recurring_operational_signals", []) or []
            recurring_blocking_failures = trend.get("recurring_blocking_failures", []) or []
            snapshot_count = trend.get("snapshot_count", 0) or 0
            trend_score = trend.get("trend_score", 0) or 0

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
            "trend_score": trend_score,
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
        "history_snapshot_count": historical.get("lookback_snapshots", 0),
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


def build_change_detection_drilldowns(change_detection):
    change_detection = change_detection or {}
    summary = change_detection.get("summary", {}) or {}
    excluded_sites = change_detection.get("excluded_sites", []) or []
    comparison_changes = change_detection.get("comparison_changes", []) or []
    site_rows = change_detection.get("sites", []) or []

    excluded_rows = []
    for site in excluded_sites:
        excluded_rows.append({
            "name": site.get("name", ""),
            "url": site.get("url", ""),
            "cloud_id": site.get("cloud_id", ""),
        })

    comparison_rows = []
    for index, change in enumerate(comparison_changes, start=1):
        if not isinstance(change, dict):
            comparison_rows.append({
                "change_index": index,
                "severity": "info",
                "change_type": "unknown",
                "site": "",
                "detail": str(change),
            })
            continue
        comparison_rows.append({
            "change_index": index,
            "severity": change.get("severity", "info"),
            "change_type": change.get("change_type") or change.get("type") or change.get("category") or "change",
            "site": change.get("site_name") or change.get("site") or change.get("name") or "",
            "detail": _safe_join(change.get("detail") or change.get("message") or change.get("description") or change),
        })

    site_attention_rows = []
    for site in site_rows:
        site_attention_rows.append({
            "site_name": site.get("site_name", ""),
            "status": site.get("status", ""),
            "risk_score": site.get("risk_score", 0),
            "trend_score": site.get("trend_score", 0),
            "growth_status": site.get("growth_status", ""),
            "project_count_delta": site.get("project_count_delta", 0),
            "total_users_delta": site.get("total_users_delta", 0),
            "active_users_delta": site.get("active_users_delta", 0),
            "inactive_users_delta": site.get("inactive_users_delta", 0),
            "snapshot_count": site.get("snapshot_count", 0),
            "new_site_candidate": "Yes" if site.get("new_site_candidate") else "No",
            "permission_limited_checks": _safe_join(site.get("permission_limited_checks", [])),
            "trend_signals": _safe_join(site.get("trend_signals", [])),
            "attention_reasons": _safe_join(site.get("attention_reasons", [])),
        })

    site_attention_rows.sort(key=lambda row: (
        0 if row.get("new_site_candidate") == "Yes" else 1,
        -(row.get("trend_score", 0) or 0),
        -(row.get("risk_score", 0) or 0),
        str(row.get("site_name", "")).lower(),
    ))

    return {
        "change::excluded_sites": {
            "title": "Excluded / Out-of-Scope Sites",
            "reason": "These sites were discovered by the collector but are currently outside the monitored operational Jira scope.",
            "atlassian_area": "Atlassian Administration → Site management / Organisation overview",
            "columns": ["name", "url", "cloud_id"],
            "rows": excluded_rows,
        },
        "change::comparison_changes": {
            "title": "Collector Comparison Changes",
            "reason": "These are the explicit comparison changes returned by the latest collector run against the previous successful snapshot.",
            "atlassian_area": "Monitoring output / Collector comparison",
            "columns": ["change_index", "severity", "change_type", "site", "detail"],
            "rows": comparison_rows,
        },
        "change::site_attention": {
            "title": "Site Change Attention",
            "reason": "This view highlights monitored sites with change signals, permission-limited checks, growth movement, trend pressure, or potential new-site attention markers.",
            "atlassian_area": "Jira operational monitoring / collector intelligence",
            "columns": [
                "site_name",
                "status",
                "risk_score",
                "trend_score",
                "growth_status",
                "project_count_delta",
                "total_users_delta",
                "active_users_delta",
                "inactive_users_delta",
                "snapshot_count",
                "new_site_candidate",
                "permission_limited_checks",
                "trend_signals",
                "attention_reasons",
            ],
            "rows": site_attention_rows,
        },
        "change::summary": {
            "title": "Change Summary Totals",
            "reason": "This summary reflects the latest collector comparison and current trend-linked totals from the backend operational state.",
            "atlassian_area": "Monitoring output / Collector comparison",
            "columns": ["metric", "value"],
            "rows": [
                {"metric": "Detected changes", "value": summary.get("change_count", 0)},
                {"metric": "Info changes", "value": summary.get("info_change_count", 0)},
                {"metric": "Warning changes", "value": summary.get("warning_change_count", 0)},
                {"metric": "Critical changes", "value": summary.get("critical_change_count", 0)},
                {"metric": "Project delta total", "value": summary.get("project_delta_total", 0)},
                {"metric": "Total users delta total", "value": summary.get("total_users_delta_total", 0)},
                {"metric": "Active users delta total", "value": summary.get("active_users_delta_total", 0)},
                {"metric": "Inactive users delta total", "value": summary.get("inactive_users_delta_total", 0)},
                {"metric": "Licensed users estimate delta total", "value": summary.get("licensed_users_estimate_delta_total", 0)},
                {"metric": "Rising risk site count", "value": summary.get("rising_risk_site_count", 0)},
                {"metric": "Warning or critical streak site count", "value": summary.get("warning_or_critical_streak_site_count", 0)},
                {"metric": "Recurring blocking failure site count", "value": summary.get("recurring_blocking_failure_site_count", 0)},
                {"metric": "History snapshots in lookback", "value": summary.get("history_snapshot_count", 0)},
                {"metric": "Excluded site count", "value": summary.get("excluded_site_count", 0)},
                {"metric": "New site candidate count", "value": summary.get("new_site_candidate_count", 0)},
            ],
        },
    }
