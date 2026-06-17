import os
import json
from collections import Counter, defaultdict

from snapshots import load_snapshot_index


def _safe_int(value, default=0):
    if isinstance(value, int):
        return value
    return default


def _safe_float(value, default=0.0):
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _normalise_list(values):
    if not isinstance(values, list):
        return []
    return sorted([str(v) for v in values if v is not None])


def _normalise_site_key_from_name(name):
    if not name:
        return None
    text = str(name).strip().lower()
    mappings = {
        "gli-it-project": "gli-it-project",
        "gli delivery tm": "gli-delivery-tm",
        "gli-delivery-tm": "gli-delivery-tm",
        "gli global technology": "gli-global-technology",
        "gli-global-technology": "gli-global-technology",
        "gli it project": "gli-it-project",
    }
    return mappings.get(text, text.replace(" ", "-"))


def _load_snapshot_file(path):
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def _get_recent_snapshot_entries(index_data, lookback=10):
    snapshots = (index_data or {}).get("snapshots", []) or []
    if not snapshots:
        return []
    return snapshots[-lookback:]


def _build_site_history_from_snapshots(snapshot_entries):
    site_history = defaultdict(list)
    for entry in snapshot_entries:
        snapshot_path = entry.get("file")
        snapshot_data = _load_snapshot_file(snapshot_path)
        if not snapshot_data:
            continue

        snapshot_meta = snapshot_data.get("snapshot_meta", {}) or {}
        snapshot_timestamp = snapshot_meta.get("snapshot_timestamp")
        created_at_local = snapshot_meta.get("created_at_local")

        for site in snapshot_data.get("sites", []) or []:
            cloud_id = site.get("cloud_id")
            site_name = site.get("name")
            site_key = _normalise_site_key_from_name(site_name)
            if not cloud_id and not site_key:
                continue

            history_key = cloud_id or site_key
            site_history[history_key].append({
                "site_key": site_key,
                "cloud_id": cloud_id,
                "snapshot_timestamp": snapshot_timestamp,
                "created_at_local": created_at_local,
                "name": site_name,
                "status": site.get("status"),
                "risk_score": _safe_int(site.get("risk_score", 0)),
                "issue_count_total": _safe_int(site.get("issue_count_total", 0)),
                "issue_count_unresolved": _safe_int(site.get("issue_count_unresolved", 0)),
                "issue_count_updated_last_7d": _safe_int(site.get("issue_count_updated_last_7d", 0)),
                "failed_api_checks": _safe_int(site.get("failed_api_checks", 0)),
                "issue_risk_score": _safe_int(site.get("issue_risk_score", 0)),
                "operational_risk_score": _safe_int(site.get("operational_risk_score", 0)),
                "blocking_failed_checks": _normalise_list(site.get("blocking_failed_checks", [])),
                "permission_limited_checks": _normalise_list(site.get("permission_limited_checks", [])),
                "issue_risk_signals": _normalise_list(site.get("issue_risk_signals", [])),
                "operational_risk_signals": _normalise_list(site.get("operational_risk_signals", [])),
                "collection_duration_seconds": _safe_float(site.get("collection_duration_seconds", 0.0)),
            })
    return dict(site_history)


def _analyse_numeric_trend(history, field_name):
    values = [_safe_float(item.get(field_name, 0)) for item in history]
    if not values:
        return {
            "field": field_name,
            "first": 0,
            "latest": 0,
            "delta": 0,
            "direction": "stable",
            "max": 0,
            "min": 0,
        }
    first = values[0]
    latest = values[-1]
    delta = round(latest - first, 4)
    if delta > 0:
        direction = "up"
    elif delta < 0:
        direction = "down"
    else:
        direction = "stable"
    return {
        "field": field_name,
        "first": first,
        "latest": latest,
        "delta": delta,
        "direction": direction,
        "max": max(values),
        "min": min(values),
    }


def _current_status_streak(history):
    if not history:
        return {"status": None, "length": 0}
    latest_status = history[-1].get("status")
    streak = 0
    for item in reversed(history):
        if item.get("status") == latest_status:
            streak += 1
        else:
            break
    return {"status": latest_status, "length": streak}


def _count_recurring_checks(history, field_name):
    counter = Counter()
    for item in history:
        values = item.get(field_name, []) or []
        for value in values:
            counter[value] += 1
    recurring = [{"name": name, "count": count} for name, count in counter.items()]
    recurring.sort(key=lambda item: (-item["count"], item["name"]))
    return recurring


def _count_recurring_signals(history, field_name):
    counter = Counter()
    for item in history:
        values = item.get(field_name, []) or []
        for value in values:
            counter[value] += 1
    recurring = [{"name": name, "count": count} for name, count in counter.items()]
    recurring.sort(key=lambda item: (-item["count"], item["name"]))
    return recurring


def _build_trend_signals(history):
    if not history:
        return {"trend_score": 0, "trend_signals": []}

    unresolved_trend = _analyse_numeric_trend(history, "issue_count_unresolved")
    risk_trend = _analyse_numeric_trend(history, "risk_score")
    failed_api_trend = _analyse_numeric_trend(history, "failed_api_checks")
    collection_time_trend = _analyse_numeric_trend(history, "collection_duration_seconds")
    streak = _current_status_streak(history)
    recurring_blocking = _count_recurring_checks(history, "blocking_failed_checks")
    recurring_permission = _count_recurring_checks(history, "permission_limited_checks")
    recurring_issue_signals = _count_recurring_signals(history, "issue_risk_signals")
    recurring_operational_signals = _count_recurring_signals(history, "operational_risk_signals")

    signals = []
    trend_score = 0

    if unresolved_trend["delta"] >= 10:
        trend_score += 2
        signals.append("rising_unresolved_backlog")
    elif unresolved_trend["delta"] >= 3:
        trend_score += 1
        signals.append("mild_unresolved_increase")

    if risk_trend["delta"] >= 5:
        trend_score += 2
        signals.append("rising_risk_score")
    elif risk_trend["delta"] >= 2:
        trend_score += 1
        signals.append("mild_risk_increase")

    if failed_api_trend["delta"] >= 1:
        trend_score += 2
        signals.append("rising_failed_api_checks")

    if collection_time_trend["delta"] >= 2:
        trend_score += 1
        signals.append("slower_collection_trend")

    if streak["status"] == "warning" and streak["length"] >= 2:
        trend_score += 2
        signals.append("warning_streak")
    elif streak["status"] == "critical" and streak["length"] >= 2:
        trend_score += 4
        signals.append("critical_streak")

    if recurring_blocking and recurring_blocking[0]["count"] >= 2:
        trend_score += 2
        signals.append("recurring_blocking_failures")

    if recurring_permission and recurring_permission[0]["count"] >= 3:
        trend_score += 1
        signals.append("persistent_permission_limits")

    if recurring_issue_signals and recurring_issue_signals[0]["count"] >= 2:
        trend_score += 1
        signals.append("recurring_issue_risk_signals")

    if recurring_operational_signals and recurring_operational_signals[0]["count"] >= 2:
        trend_score += 1
        signals.append("recurring_operational_signals")

    return {
        "trend_score": trend_score,
        "trend_signals": signals,
        "unresolved_trend": unresolved_trend,
        "risk_trend": risk_trend,
        "failed_api_trend": failed_api_trend,
        "collection_time_trend": collection_time_trend,
        "status_streak": streak,
        "recurring_blocking_failures": recurring_blocking,
        "recurring_permission_limits": recurring_permission,
        "recurring_issue_signals": recurring_issue_signals,
        "recurring_operational_signals": recurring_operational_signals,
    }


def _summarise_site_trend(history_key, history):
    latest = history[-1] if history else {}
    trend_result = _build_trend_signals(history)
    site_key = latest.get("site_key") or latest.get("cloud_id") or history_key
    return {
        "site_key": site_key,
        "cloud_id": latest.get("cloud_id"),
        "name": latest.get("name"),
        "current_status": latest.get("status"),
        "current_risk_score": latest.get("risk_score", 0),
        "snapshot_count": len(history),
        "trend_score": trend_result["trend_score"],
        "trend_signals": trend_result["trend_signals"],
        "status_streak": trend_result["status_streak"],
        "unresolved_trend": trend_result["unresolved_trend"],
        "risk_trend": trend_result["risk_trend"],
        "failed_api_trend": trend_result["failed_api_trend"],
        "collection_time_trend": trend_result["collection_time_trend"],
        "recurring_blocking_failures": trend_result["recurring_blocking_failures"],
        "recurring_permission_limits": trend_result["recurring_permission_limits"],
        "recurring_issue_signals": trend_result["recurring_issue_signals"],
        "recurring_operational_signals": trend_result["recurring_operational_signals"],
    }


def analyze_historical_trends(lookback=10):
    index_data = load_snapshot_index()
    recent_entries = _get_recent_snapshot_entries(index_data, lookback=lookback)
    if not recent_entries:
        return {
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
        }

    site_history = _build_site_history_from_snapshots(recent_entries)
    site_trends = []
    warning_or_critical_streak_sites = 0
    rising_unresolved_sites = 0
    rising_risk_sites = 0
    recurring_blocking_failure_sites = 0

    for history_key, history in site_history.items():
        site_trend = _summarise_site_trend(history_key, history)
        site_trends.append(site_trend)

        streak = site_trend.get("status_streak", {}) or {}
        if streak.get("status") in ("warning", "critical") and streak.get("length", 0) >= 2:
            warning_or_critical_streak_sites += 1

        unresolved_trend = site_trend.get("unresolved_trend", {}) or {}
        if unresolved_trend.get("delta", 0) >= 3:
            rising_unresolved_sites += 1

        risk_trend = site_trend.get("risk_trend", {}) or {}
        if risk_trend.get("delta", 0) >= 2:
            rising_risk_sites += 1

        recurring_blocking = site_trend.get("recurring_blocking_failures", []) or []
        if recurring_blocking and recurring_blocking[0].get("count", 0) >= 2:
            recurring_blocking_failure_sites += 1

    site_trends.sort(
        key=lambda site: (
            0 if site.get("current_status") == "critical" else 1 if site.get("current_status") == "warning" else 2,
            -site.get("trend_score", 0),
            -site.get("current_risk_score", 0),
            site.get("name", ""),
        )
    )

    return {
        "has_history": True,
        "lookback_snapshots": len(recent_entries),
        "site_trends": site_trends,
        "summary": {
            "site_count": len(site_trends),
            "warning_or_critical_streak_sites": warning_or_critical_streak_sites,
            "rising_unresolved_sites": rising_unresolved_sites,
            "rising_risk_sites": rising_risk_sites,
            "recurring_blocking_failure_sites": recurring_blocking_failure_sites,
        },
    }


def _build_history_rows(snapshot_entries, site_key):
    rows = []
    site_history = _build_site_history_from_snapshots(snapshot_entries)
    for _, history in site_history.items():
        for item in history:
            if item.get("site_key") != site_key:
                continue
            rows.append({
                "snapshot_timestamp": item.get("snapshot_timestamp", ""),
                "created_at_local": item.get("created_at_local", ""),
                "status": item.get("status", ""),
                "risk_score": item.get("risk_score", 0),
                "issue_count_total": item.get("issue_count_total", 0),
                "issue_count_unresolved": item.get("issue_count_unresolved", 0),
                "issue_count_updated_last_7d": item.get("issue_count_updated_last_7d", 0),
                "failed_api_checks": item.get("failed_api_checks", 0),
                "collection_duration_seconds": item.get("collection_duration_seconds", 0.0),
                "permission_limited_checks": ", ".join(item.get("permission_limited_checks", [])),
                "blocking_failed_checks": ", ".join(item.get("blocking_failed_checks", [])),
                "operational_risk_signals": ", ".join(item.get("operational_risk_signals", [])),
            })
    rows.sort(key=lambda row: str(row.get("snapshot_timestamp", "")))
    return rows


def build_trend_drilldowns(lookback=10):
    index_data = load_snapshot_index()
    recent_entries = _get_recent_snapshot_entries(index_data, lookback=lookback)
    analysis = analyze_historical_trends(lookback=lookback)
    summary = analysis.get("summary", {}) or {}
    site_trends = analysis.get("site_trends", []) or []

    summary_rows = [
        {"metric": "Snapshots in lookback", "value": analysis.get("lookback_snapshots", 0)},
        {"metric": "Tracked sites with history", "value": summary.get("site_count", 0)},
        {"metric": "Warning / critical streak sites", "value": summary.get("warning_or_critical_streak_sites", 0)},
        {"metric": "Rising unresolved sites", "value": summary.get("rising_unresolved_sites", 0)},
        {"metric": "Rising risk sites", "value": summary.get("rising_risk_sites", 0)},
        {"metric": "Recurring blocking failure sites", "value": summary.get("recurring_blocking_failure_sites", 0)},
    ]

    site_rows = []
    risk_riser_rows = []
    for site in site_trends:
        row = {
            "site_name": site.get("name", ""),
            "site_key": site.get("site_key", ""),
            "current_status": site.get("current_status", ""),
            "snapshot_count": site.get("snapshot_count", 0),
            "trend_score": site.get("trend_score", 0),
            "trend_signals": ", ".join(site.get("trend_signals", [])),
            "risk_delta": (site.get("risk_trend", {}) or {}).get("delta", 0),
            "unresolved_delta": (site.get("unresolved_trend", {}) or {}).get("delta", 0),
            "failed_api_delta": (site.get("failed_api_trend", {}) or {}).get("delta", 0),
            "collection_time_delta": (site.get("collection_time_trend", {}) or {}).get("delta", 0),
            "status_streak": f"{(site.get('status_streak', {}) or {}).get('status', '')}:{(site.get('status_streak', {}) or {}).get('length', 0)}",
            "recurring_permission_limits": ", ".join([item.get("name", "") for item in site.get("recurring_permission_limits", [])]),
            "recurring_operational_signals": ", ".join([item.get("name", "") for item in site.get("recurring_operational_signals", [])]),
            "recurring_blocking_failures": ", ".join([item.get("name", "") for item in site.get("recurring_blocking_failures", [])]),
        }
        site_rows.append(row)
        if row["risk_delta"] > 0:
            risk_riser_rows.append({
                "site_name": row["site_name"],
                "site_key": row["site_key"],
                "current_status": row["current_status"],
                "snapshot_count": row["snapshot_count"],
                "trend_score": row["trend_score"],
                "risk_delta": row["risk_delta"],
                "trend_signals": row["trend_signals"],
                "recurring_permission_limits": row["recurring_permission_limits"],
                "recurring_operational_signals": row["recurring_operational_signals"],
            })

    drilldowns = {
        "trend::summary": {
            "title": "Historical Trend Summary",
            "reason": "This summary shows how many recent snapshots are available and where historical trend pressure is building across the monitored Jira sites.",
            "atlassian_area": "Monitoring / Snapshot history / Trend review",
            "columns": ["metric", "value"],
            "rows": summary_rows,
        },
        "trend::sites": {
            "title": "Historical Trend Sites",
            "reason": "This list shows current trend pressure by monitored site using snapshot history, risk direction, recurring permission issues, and recurring operational signals.",
            "atlassian_area": "Monitoring / Snapshot history / Site trend review",
            "columns": [
                "site_name",
                "site_key",
                "current_status",
                "snapshot_count",
                "trend_score",
                "trend_signals",
                "risk_delta",
                "unresolved_delta",
                "failed_api_delta",
                "collection_time_delta",
                "status_streak",
                "recurring_permission_limits",
                "recurring_operational_signals",
                "recurring_blocking_failures",
            ],
            "rows": site_rows,
        },
        "trend::risk_risers": {
            "title": "Sites With Rising Risk",
            "reason": "These sites have a positive risk score trend over the current snapshot lookback window.",
            "atlassian_area": "Monitoring / Snapshot history / Risk review",
            "columns": [
                "site_name",
                "site_key",
                "current_status",
                "snapshot_count",
                "trend_score",
                "risk_delta",
                "trend_signals",
                "recurring_permission_limits",
                "recurring_operational_signals",
            ],
            "rows": risk_riser_rows,
        },
    }

    for site in site_trends:
        site_key = site.get("site_key")
        if not site_key:
            continue
        history_rows = _build_history_rows(recent_entries, site_key)
        drilldowns[f"trend::site::{site_key}"] = {
            "title": f"Historical Trend — {site.get('name', site_key)}",
            "reason": "Snapshot-by-snapshot operational history for this monitored Jira site.",
            "atlassian_area": "Monitoring / Snapshot history / Site timeline",
            "columns": [
                "snapshot_timestamp",
                "created_at_local",
                "status",
                "risk_score",
                "issue_count_total",
                "issue_count_unresolved",
                "issue_count_updated_last_7d",
                "failed_api_checks",
                "collection_duration_seconds",
                "permission_limited_checks",
                "blocking_failed_checks",
                "operational_risk_signals",
            ],
            "rows": history_rows,
        }

    return drilldowns
