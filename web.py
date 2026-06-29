from flask import Flask, render_template, jsonify, abort, request
from pathlib import Path

from datetime import datetime
import os

from datetime import datetime
from billing_catalog import get_billing_catalog
from project_counts import (
    load_project_counts_from_latest_run,
    load_project_intelligence_from_latest_run,
    build_project_drilldowns_from_latest_run,
)
from change_detection import load_latest_run_change_detection, build_change_detection_drilldowns
from site_discovery import load_site_discovery_from_latest_run, build_site_discovery_drilldowns
from snapshots import load_snapshot_index, get_latest_snapshot_entry, load_latest_snapshot
from trends import analyze_historical_trends, build_trend_drilldowns
from backend.runtime_source_adapter import load_preferred_source_payload
from scripts.snapshot_controller import startup_self_heal as snapshot_startup_self_heal


BASE_DIR = Path(__file__).resolve().parent
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)


def _parse_possible_datetime(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {"never accessed", "never", "-", "none", "n/a"}:
        return None
    formats = [
        "%d %b %Y",
        "%d %B %Y",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
        "%b %d, %Y",
        "%b %d, %Y %H:%M",
        "%B %d, %Y",
        "%B %d, %Y %H:%M",
        "%Y-%m-%d_%H-%M-%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None
    
_STARTUP_SELF_HEAL_DONE = False

def run_startup_self_heal():
    global _STARTUP_SELF_HEAL_DONE
    if _STARTUP_SELF_HEAL_DONE:
        return

    try:
        snapshot_startup_self_heal()
    except Exception as exc:
        print(f"ÃƒÂ¢Ã…Â¡Ã‚Â ÃƒÂ¯Ã‚Â¸Ã‚Â Startup self-heal failed: {exc}")
    finally:
        _STARTUP_SELF_HEAL_DONE = True


def _is_last_seen_field(sort_key):
    if not sort_key:
        return False
    key = str(sort_key).lower()
    return (
        "last_seen" in key
        or "last seen" in key
        or key == "last_active"
        or "last_active" in key
        or key == "created_at_local"
        or key == "snapshot_timestamp"
    )


def _sort_rows(rows, sort_key, order="asc"):
    if not rows or not sort_key:
        return rows
    descending = str(order).lower() == "desc"
    if _is_last_seen_field(sort_key):
        def dt_key(row):
            parsed = _parse_possible_datetime(row.get(sort_key))
            if parsed is None:
                return (1, datetime.min)
            return (0, parsed)
        return sorted(rows, key=dt_key, reverse=descending)

    def text_key(row):
        value = row.get(sort_key, "")
        if value is None:
            value = ""
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        return str(value).lower()

    return sorted(rows, key=text_key, reverse=descending)


def _coerce_sites(data):
    sites = data.get("sites", []) if isinstance(data, dict) else []
    return [site for site in sites if isinstance(site, dict)]


def _site_identity(site):
    if not isinstance(site, dict):
        return None
    return site.get("site") or site.get("site_key") or site.get("cloud_id")


def _apply_source_metadata(data, source_file=None):
    data["source_mode"] = "runtime"
    data["source_file"] = source_file
    source_label = f"Runtime payload: {source_file}" if source_file else "Runtime payload"
    data["users_source_file"] = data.get("users_source_file") or source_label
    data["managed_source_file"] = data.get("managed_source_file") or source_label
    data["users_row_count"] = data.get("users_row_count", 0) or 0
    data["managed_row_count"] = data.get("managed_row_count", 0) or 0
    return data


def _runtime_unavailable_payload(reason, source_file=None):
    return {
        "estate": {
            "total_sites": 0,
            "total_projects": 0,
            "total_users": None,
            "total_active_users": None,
            "total_inactive_users": None,
            "runtime_error": reason,
        },
        "sites": [],
        "critical_sites": [],
        "warning_sites": [],
        "stable_sites": [],
        "org_product_breakdown": [],
        "users_export_breakdown": [],
        "billing_summary": {},
        "change_detection": {},
        "site_discovery": {},
        "project_intelligence": {
            "has_current_run": False,
            "site_map": {},
            "all_projects": [],
            "summary_rows": [],
        },
        "historical_trends": {},
        "snapshot_index": {},
        "latest_snapshot_entry": {},
        "latest_snapshot": {},
        "drilldowns": {},
        "source_mode": "runtime",
        "source_file": source_file,
        "source_error": reason,
        "users_source_file": f"Runtime payload: {source_file}" if source_file else None,
        "managed_source_file": f"Runtime payload: {source_file}" if source_file else None,
        "users_row_count": 0,
        "managed_row_count": 0,
    }


# ============================================================
# JOM registry truth helpers - Home/Estate source-level scope
# ============================================================
def _registry_norm(value):
    text = str(value or "").strip().lower()
    if text.startswith("https://"):
        text = text[len("https://"):]
    if text.startswith("http://"):
        text = text[len("http://"):]
    text = text.split("/")[0]
    if text.endswith(".atlassian.net"):
        text = text[:-len(".atlassian.net")]
    return text.rstrip("/")


def _registry_tokens_for_site(site):
    if not isinstance(site, dict):
        return set()
    keys = ["site", "site_key", "cloud_id", "site_name", "name", "url", "site_url", "base_url"]
    tokens = set()
    for key in keys:
        value = site.get(key)
        if value:
            tokens.add(_registry_norm(value))
    aliases = site.get("aliases")
    if isinstance(aliases, list):
        for alias in aliases:
            if alias:
                tokens.add(_registry_norm(alias))
    return {token for token in tokens if token}


def _load_registry_truth():
    try:
        from backend.site_registry_runtime import build_registry
        registry = build_registry(BASE_DIR)
        if isinstance(registry, dict):
            return registry
    except Exception as exc:
        print(f"JOM registry truth load failed: {exc}")
    return {"summary": {}, "sites": []}


def _apply_registry_scope_to_runtime_data(data):
    """Only registry-monitored sites can appear in Home/Estate operational groupings."""
    registry = _load_registry_truth()
    registry_sites = registry.get("sites", []) if isinstance(registry.get("sites"), list) else []
    monitored_registry_sites = [s for s in registry_sites if s.get("classification") == "monitored"]
    discovered_registry_sites = [s for s in registry_sites if s.get("classification") == "discovered"]
    monitored_tokens = set()
    for site in monitored_registry_sites:
        monitored_tokens.update(_registry_tokens_for_site(site))
    runtime_sites = data.get("sites", []) if isinstance(data.get("sites"), list) else []
    scoped_sites = []
    for site in runtime_sites:
        site_tokens = _registry_tokens_for_site(site)
        if site_tokens and site_tokens.intersection(monitored_tokens):
            site["registry_classification"] = "monitored"
            scoped_sites.append(site)
    data["sites"] = scoped_sites
    data["site_registry"] = registry
    data["registry_monitored_sites"] = monitored_registry_sites
    data["registry_discovered_sites"] = discovered_registry_sites
    data["registry_summary"] = registry.get("summary", {}) if isinstance(registry.get("summary"), dict) else {}
    return data
def _finalise_data(data, *, source_file=None):
    data = data if isinstance(data, dict) else {}
    data["sites"] = _coerce_sites(data)
    data = _apply_source_metadata(data, source_file=source_file)

    data["sites"] = _merge_project_counts(data.get("sites", []))
    project_intelligence = load_project_intelligence_from_latest_run()
    data["project_intelligence"] = project_intelligence
    data["sites"] = _merge_project_intelligence(data.get("sites", []), project_intelligence)

    change_detection = load_latest_run_change_detection()
    data["change_detection"] = change_detection
    data["sites"] = _merge_change_detection(data.get("sites", []), change_detection)

    site_discovery = load_site_discovery_from_latest_run()
    data["site_discovery"] = site_discovery

    historical_trends = analyze_historical_trends(lookback=10)
    data["historical_trends"] = historical_trends
    data["sites"] = _merge_historical_trends(data.get("sites", []), historical_trends)
    data = _apply_registry_scope_to_runtime_data(data)

    snapshot_index = load_snapshot_index()
    latest_snapshot_entry = get_latest_snapshot_entry()
    latest_snapshot = load_latest_snapshot()
    data["snapshot_index"] = snapshot_index
    data["latest_snapshot_entry"] = latest_snapshot_entry or {}
    data["latest_snapshot"] = latest_snapshot or {}

    data["critical_sites"] = [s for s in data["sites"] if s.get("status") == "critical"]
    data["warning_sites"] = [s for s in data["sites"] if s.get("status") == "warning"]
    data["stable_sites"] = [s for s in data["sites"] if s.get("status") == "stable"]

    billing = get_billing_catalog()
    data["billing_summary"] = billing.get("summary", {})

    drilldowns = data.get("drilldowns", {}) if isinstance(data.get("drilldowns"), dict) else {}
    drilldowns.update(billing.get("drilldowns", {}))
    drilldowns.update(build_change_detection_drilldowns(change_detection))
    drilldowns.update(build_project_drilldowns_from_latest_run())
    drilldowns.update(build_site_discovery_drilldowns(site_discovery))
    drilldowns.update(build_trend_drilldowns(lookback=10))
    data["drilldowns"] = drilldowns
    data["drilldowns"].update(_build_intelligence_drilldowns(data))
    data["drilldowns"].update(_build_intelligence_summary_drilldown(data))
    return data


def _merge_project_counts(sites):
    project_counts = load_project_counts_from_latest_run()
    for site in sites:
        site_key = _site_identity(site)
        project_data = project_counts.get(site_key, {})
        if project_data:
            site["project_count"] = project_data.get("project_count", site.get("project_count"))
            site["issue_count_total"] = project_data.get("issue_count_total", site.get("issue_count_total"))
            site["issue_count_unresolved"] = project_data.get("issue_count_unresolved", site.get("issue_count_unresolved"))
            site["issue_count_updated_last_7d"] = project_data.get("issue_count_updated_last_7d", site.get("issue_count_updated_last_7d"))
            site["project_count_delta"] = project_data.get("project_count_delta", site.get("project_count_delta"))
    return sites


def _merge_project_intelligence(sites, project_intelligence):
    site_map = project_intelligence.get("site_map", {}) if isinstance(project_intelligence, dict) else {}
    for site in sites:
        site_key = _site_identity(site)
        info = site_map.get(site_key, {})
        site["sampled_project_rows"] = info.get("sampled_project_rows", site.get("sampled_project_rows", 0))
        site["project_sample_available"] = True if info.get("project_rows") else bool(site.get("project_rows"))
    return sites


def _merge_change_detection(sites, change_detection):
    site_map = change_detection.get("site_map", {}) if isinstance(change_detection, dict) else {}
    for site in sites:
        site_key = _site_identity(site)
        change_data = site_map.get(site_key, {})
        if not change_data:
            continue
        site["growth_status"] = change_data.get("growth_status", site.get("growth_status"))
        site["project_count_delta_live"] = change_data.get("project_count_delta", 0)
        site["total_users_delta"] = change_data.get("total_users_delta", site.get("total_users_delta", 0))
        site["active_users_delta"] = change_data.get("active_users_delta", site.get("active_users_delta", 0))
        site["inactive_users_delta"] = change_data.get("inactive_users_delta", site.get("inactive_users_delta", 0))
        site["licensed_users_estimate"] = change_data.get("licensed_users_estimate", site.get("licensed_users_estimate"))
        site["licensed_users_estimate_delta"] = change_data.get("licensed_users_estimate_delta", site.get("licensed_users_estimate_delta", 0))
        site["audit_status"] = change_data.get("audit_status", site.get("audit_status"))
        site["audit_api_access"] = change_data.get("audit_api_access", site.get("audit_api_access"))
        site["licence_status"] = change_data.get("licence_status", site.get("licence_status"))
        site["licence_api_access"] = change_data.get("licence_api_access", site.get("licence_api_access"))
        site["permission_limited_checks"] = change_data.get("permission_limited_checks", site.get("permission_limited_checks", []))
        site["status_reasons"] = change_data.get("status_reasons", site.get("status_reasons", []))
        site["trend_signals"] = change_data.get("trend_signals", site.get("trend_signals", []))
        site["snapshot_count"] = change_data.get("snapshot_count", site.get("snapshot_count", 0))
        site["trend_score"] = change_data.get("trend_score", site.get("trend_score", 0))
        site["new_site_candidate"] = change_data.get("new_site_candidate", site.get("new_site_candidate", False))
        site["attention_reasons"] = change_data.get("attention_reasons", site.get("attention_reasons", []))
    return sites


def _merge_historical_trends(sites, historical_trends):
    site_trends = historical_trends.get("site_trends", []) if isinstance(historical_trends, dict) else []
    trend_map = {}
    for trend in site_trends:
        site_key = trend.get("site_key") or trend.get("site")
        if site_key:
            trend_map[site_key] = trend
    for site in sites:
        site_key = _site_identity(site)
        trend = trend_map.get(site_key, {})
        unresolved_trend = trend.get("unresolved_trend", {}) or {}
        risk_trend = trend.get("risk_trend", {}) or {}
        failed_api_trend = trend.get("failed_api_trend", {}) or {}
        collection_time_trend = trend.get("collection_time_trend", {}) or {}
        status_streak = trend.get("status_streak", {}) or {}
        site["historical_trend_score"] = trend.get("trend_score", 0)
        site["historical_trend_signals"] = trend.get("trend_signals", []) or []
        site["historical_snapshot_count"] = trend.get("snapshot_count", 0)
        site["historical_risk_delta"] = risk_trend.get("delta", 0)
        site["historical_unresolved_delta"] = unresolved_trend.get("delta", 0)
        site["historical_failed_api_delta"] = failed_api_trend.get("delta", 0)
        site["historical_collection_time_delta"] = collection_time_trend.get("delta", 0)
        site["historical_status_streak_status"] = status_streak.get("status")
        site["historical_status_streak_length"] = status_streak.get("length", 0)
    return sites


def _prettify_label(value):
    text = str(value or "").replace("_", " ").replace("-", " ").strip()
    return text.title() if text else "Value"


def _derive_intelligence_columns(items):
    seen = []
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in item.keys():
            if key not in seen:
                seen.append(key)
    return seen


def _normalise_detail_key_from_action(action):
    text = str(action or "").strip()
    if text.startswith("/detail/"):
        return text[len("/detail/"):]
    return text


def _intelligence_atlassian_area(risk_type):
    mapping = {
        "inactive_users": "Atlassian Administration ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Directory / Product Access",
        "unmanaged_accounts": "Atlassian Administration ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Managed Accounts",
        "orphaned_projects": "Jira Administration ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Projects",
        "unused_apps": "Atlassian Administration ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Connected Apps",
        "tier_capacity": "Atlassian Administration ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Billing / Subscription",
        "seat_capacity": "Atlassian Administration ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Billing / Subscription",
    }
    return mapping.get(risk_type, "Atlassian Administration")


def _build_intelligence_drilldowns(data):
    intelligence = data.get("intelligence", {}) if isinstance(data, dict) else {}
    sites = intelligence.get("sites", []) if isinstance(intelligence, dict) else []
    drilldowns = {}
    for site in sites:
        if not isinstance(site, dict):
            continue
        site_name = site.get("name") or site.get("site_key") or site.get("id") or "Site"
        for risk in site.get("risks", []):
            if not isinstance(risk, dict):
                continue
            detail_key = _normalise_detail_key_from_action(risk.get("action"))
            if not detail_key:
                continue
            details = risk.get("details", {}) if isinstance(risk.get("details"), dict) else {}
            items = details.get("items", []) if isinstance(details.get("items"), list) else []
            rows = [row for row in items if isinstance(row, dict)]
            columns = _derive_intelligence_columns(rows)
            risk_type = risk.get("type", "risk")
            title = f"{site_name} ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â {_prettify_label(risk_type)}"
            reason = risk.get("reason") or f"Operational intelligence detected {_prettify_label(risk_type).lower()}."
            if not rows:
                rows = [{
                    "site": site_name,
                    "severity": risk.get("severity", "warning"),
                    "count": risk.get("count", 0),
                    "reason": reason,
                }]
                columns = _derive_intelligence_columns(rows)
            drilldowns[detail_key] = {
                "title": title,
                "reason": reason,
                "atlassian_area": _intelligence_atlassian_area(risk_type),
                "columns": columns,
                "rows": rows,
            }
    return drilldowns


def _build_intelligence_summary_drilldown(data):
    intelligence = data.get("intelligence", {}) if isinstance(data, dict) else {}
    estate = intelligence.get("estate", {}) if isinstance(intelligence, dict) else {}
    top_risks = estate.get("top_risks", []) if isinstance(estate, dict) else []
    rows = []
    for risk in top_risks:
        if not isinstance(risk, dict):
            continue
        rows.append({
            "type": _prettify_label(risk.get("type", "risk")),
            "severity": risk.get("severity", "warning"),
            "count": risk.get("count", 0),
            "reason": risk.get("reason", ""),
            "action": risk.get("action", ""),
        })
    if not rows:
        rows = [{
            "type": "No Active Risks",
            "severity": "info",
            "count": 0,
            "reason": "No intelligence risks are currently populated.",
            "action": "",
        }]
    return {
        "intelligence::summary": {
            "title": "Operational Intelligence Summary",
            "reason": "Top operational intelligence risks across the estate based on the current backend snapshot.",
            "atlassian_area": "Atlassian Administration",
            "columns": _derive_intelligence_columns(rows),
            "rows": rows,
        }
    }


def _build_data():
    runtime_payload, runtime_meta = load_preferred_source_payload(BASE_DIR)
    if not runtime_payload:
        return _runtime_unavailable_payload(
            reason="No runtime collector payload was found. Run the collector to generate latest_run.json before starting the web app.",
            source_file=runtime_meta.get("file"),
        )

    return _finalise_data(
        runtime_payload,
        source_file=runtime_meta.get("file"),
    )


def _common_template_data(data):
    context = {
        "estate": data.get("estate", {}),
        "sites": data.get("sites", []),
        "critical_sites": data.get("critical_sites", []),
        "warning_sites": data.get("warning_sites", []),
        "stable_sites": data.get("stable_sites", []),
        "org_product_breakdown": data.get("org_product_breakdown", []),
        "users_export_breakdown": data.get("users_export_breakdown", []),
        "billing_summary": data.get("billing_summary", {}),
        "change_detection": data.get("change_detection", {}),
        "site_discovery": data.get("site_discovery", {}),
        "site_registry": data.get("site_registry", {}),
        "registry_summary": data.get("registry_summary", {}),
        "registry_monitored_sites": data.get("registry_monitored_sites", []),
        "registry_discovered_sites": data.get("registry_discovered_sites", []),
        "project_intelligence": data.get("project_intelligence", {}),
        "historical_trends": data.get("historical_trends", {}),
        "snapshot_index": data.get("snapshot_index", {}),
        "latest_snapshot_entry": data.get("latest_snapshot_entry", {}),
        "latest_snapshot": data.get("latest_snapshot", {}),
        "users_source_file": data.get("users_source_file"),
        "managed_source_file": data.get("managed_source_file"),
        "users_row_count": data.get("users_row_count", 0),
        "managed_row_count": data.get("managed_row_count", 0),
        "source_mode": data.get("source_mode", "runtime"),
        "source_file": data.get("source_file"),
        "source_error": data.get("source_error"),
        "intelligence_summary": data.get("intelligence_summary", {}),
        "disabled_users_total": data.get("disabled_users_total", 0),
        "jira_users_total": data.get("jira_users_total", 0),
        "confluence_users_total": data.get("confluence_users_total", 0),
    }
    return context


def _site_matches(site, site_key):
    if not isinstance(site, dict):
        return False
    candidates = [
        site.get("site"),
        site.get("site_key"),
        site.get("cloud_id"),
        site.get("site_name"),
        site.get("name"),
    ]
    key = str(site_key or "").strip().lower()
    for candidate in candidates:
        if candidate is None:
            continue
        if str(candidate).strip().lower() == key:
            return True
    return False


def _as_clean_list(value):
    if isinstance(value, list):
        return [item for item in value if item not in (None, "", [])]
    return []


def _endpoint_state_label(payload):
    if not isinstance(payload, dict):
        return "Unavailable"
    if payload.get("skipped"):
        return "Skipped"
    if payload.get("ok") is True:
        return "OK"
    if payload.get("ok") is False:
        return "Failed"
    return "Unknown"


def _format_elapsed(value):
    if value in (None, ""):
        return "Ã¢â‚¬â€"
    try:
        return f"{float(value):.3f}s"
    except Exception:
        return str(value)


def _build_site_page_view(data, site_key):
    data = data if isinstance(data, dict) else {}
    sites = data.get("sites", []) if isinstance(data.get("sites"), list) else []
    site = next((row for row in sites if _site_matches(row, site_key)), None)
    if not site:
        return None

    project_rows = site.get("project_rows") or site.get("project_sample") or []
    if not isinstance(project_rows, list):
        project_rows = []

    user_summary = site.get("user_summary") if isinstance(site.get("user_summary"), dict) else {}
    licence_summary = site.get("licence_summary") if isinstance(site.get("licence_summary"), dict) else {}

    has_user_data = any(
        user_summary.get(field) is not None or site.get(field) is not None
        for field in ["total_users", "active_users", "inactive_users"]
    )
    has_license_data = any(
        licence_summary.get(field) is not None or site.get(field) is not None
        for field in ["licensed_users_estimate", "remaining_seats", "number_of_seats", "licensed_users"]
    )
    has_issue_data = any(
        site.get(field) is not None
        for field in ["issue_count_total", "issue_count_unresolved", "issue_count_updated_last_7d"]
    )

    endpoint_results = site.get("endpoint_results") if isinstance(site.get("endpoint_results"), dict) else {}
    endpoint_priority = [
        "server_info",
        "myself",
        "my_permissions",
        "projects",
        "issue_total_count",
        "issue_unresolved_count",
        "issue_updated_last_7d_count",
        "application_roles",
        "audit_records",
    ]
    endpoint_rows = []
    for key_name in endpoint_priority:
        payload = endpoint_results.get(key_name)
        if payload is None:
            continue
        endpoint_rows.append({
            "name": key_name.replace("_", " ").title(),
            "state": _endpoint_state_label(payload),
            "status_code": payload.get("status_code") if isinstance(payload, dict) and payload.get("status_code") is not None else "Ã¢â‚¬â€",
            "elapsed": _format_elapsed(payload.get("elapsed_seconds") if isinstance(payload, dict) else None),
        })

    breakdown_rows = [
        {"label": "Project sample", "value": "Available" if project_rows else "No sample rows returned"},
        {"label": "User totals", "value": "Available" if has_user_data else "Hidden until admin enrichment is trustworthy"},
        {"label": "Licence metrics", "value": "Available" if has_license_data else "Hidden until licence enrichment is restored"},
        {"label": "Issue totals", "value": "Visible with caution" if has_issue_data else "Unavailable"},
        {"label": "Audit coverage", "value": str(site.get("audit_status") or "Not available")},
        {"label": "Source mode", "value": str(data.get("source_mode") or "runtime")},
    ]

    trend_rows = []
    for item in _as_clean_list(site.get("status_reasons")):
        trend_rows.append({"text": item, "kind": "chip chip--accent"})
    for item in _as_clean_list(site.get("scope_notes")):
        trend_rows.append({"text": item, "kind": "chip chip--warning"})
    for item in _as_clean_list(site.get("operational_risk_signals")):
        trend_rows.append({"text": item, "kind": "chip chip--accent"})
    for item in _as_clean_list(site.get("issue_risk_signals")):
        trend_rows.append({"text": item, "kind": "chip chip--warning"})
    for item in _as_clean_list(site.get("attention_reasons")):
        trend_rows.append({"text": item, "kind": "chip chip--warning"})
    for item in _as_clean_list(site.get("historical_trend_signals")):
        trend_rows.append({"text": item, "kind": "chip chip--accent"})
    if site.get("historical_status_streak_status"):
        trend_rows.append({
            "text": f"Status streak: {site.get('historical_status_streak_status')} ({site.get('historical_status_streak_length') or 0})",
            "kind": "chip chip--accent",
        })
    if site.get("historical_snapshot_count") is not None:
        trend_rows.append({
            "text": f"Snapshots: {site.get('historical_snapshot_count') or 0}",
            "kind": "chip chip--accent",
        })

    return {
        "site": site,
        "site_title": site.get("site_name") or site.get("name") or site.get("site") or site_key,
        "site_key": site.get("site") or site.get("site_key") or site_key,
        "site_status": str(site.get("status") or "unknown").upper(),
        "site_url": site.get("url") or site.get("site_url") or site.get("base_url"),
        "site_source_file": data.get("source_file"),
        "project_rows": project_rows[:18],
        "endpoint_rows": endpoint_rows,
        "data_quality_breakdown": breakdown_rows,
        "trend_rows": trend_rows,
        "has_user_data": has_user_data,
        "has_license_data": has_license_data,
        "has_issue_data": has_issue_data,
    }

@app.route("/")
def home():
    data = _build_data()
    return render_template("home.html", **_common_template_data(data))


@app.route("/reference")
def reference_page():
    data = _build_data()
    return render_template("reference.html", **_common_template_data(data))


@app.route("/estate")
def estate_page():
    data = _build_data()
    return render_template("estate.html", **_common_template_data(data))


@app.route("/site/<site_key>")
def site_page(site_key: str):
    data = _build_data()
    site_view = _build_site_page_view(data, site_key)
    if not site_view:
        abort(404)
    return render_template(
        "site.html",
        **_common_template_data(data),
        **site_view,
    )

@app.route("/detail/<path:key>")
def detail(key: str):
    data = _build_data()
    item = data.get("drilldowns", {}).get(key)
    if not item:
        abort(404)
    sort_key = request.args.get("sort", "").strip()
    order = request.args.get("order", "").strip().lower()
    rows = item.get("rows", [])
    if sort_key and _is_last_seen_field(sort_key) and order == "":
        order = "desc"
    rows = _sort_rows(rows, sort_key, order)
    return render_template(
        "detail_list.html",
        detail_key=key,
        title=item.get("title", "Detail"),
        reason=item.get("reason", ""),
        atlassian_area=item.get("atlassian_area", "Atlassian Administration"),
        columns=item.get("columns", []),
        rows=rows,
        sort_key=sort_key,
        sort_order=order,
    )

# ============================================================
# Sprint 9 Step 3 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Automation status helpers
# ============================================================

SYNC_LOG_FILE = Path(__file__).resolve().parent / "docs" / "control" / "logs" / "scheduled_sync.log"
SNAPSHOTS_DIR = Path(__file__).resolve().parent / "snapshots"
AUTO_SYNC_FRESHNESS_SECONDS = 15 * 60  # 15 minutes


def _get_last_sync_info():
    """
    Returns metadata about the last automated sync run.

    Reads the mtime of the scheduled_sync.log file written by
    run_sync_for_scheduler.cmd. If the file exists and was modified
    within AUTO_SYNC_FRESHNESS_SECONDS, the auto sync is considered
    active.
    """
    if not SYNC_LOG_FILE.exists():
        return {
            "last_sync_time": None,
            "last_sync_age_seconds": None,
            "auto_sync_active": False,
        }

    try:
        mtime = SYNC_LOG_FILE.stat().st_mtime
        last_dt = datetime.fromtimestamp(mtime)
        age_seconds = int((datetime.now() - last_dt).total_seconds())
        return {
            "last_sync_time": last_dt.isoformat(timespec="seconds"),
            "last_sync_age_seconds": age_seconds,
            "auto_sync_active": age_seconds < AUTO_SYNC_FRESHNESS_SECONDS,
        }
    except Exception:
        return {
            "last_sync_time": None,
            "last_sync_age_seconds": None,
            "auto_sync_active": False,
        }


def _get_anchors_today():
    """
    Returns which daily anchor snapshots exist for today.

    Checks the snapshots directory for files matching:
      snapshot_YYYY-MM-DD_*_anchor_morning.json
      snapshot_YYYY-MM-DD_*_anchor_evening.json
    """
    if not SNAPSHOTS_DIR.exists():
        return {"morning": False, "evening": False}

    today_prefix = datetime.now().strftime("%Y-%m-%d")

    morning_pattern = f"snapshot_{today_prefix}_*_anchor_morning.json"
    evening_pattern = f"snapshot_{today_prefix}_*_anchor_evening.json"

    has_morning = len(list(SNAPSHOTS_DIR.glob(morning_pattern))) > 0
    has_evening = len(list(SNAPSHOTS_DIR.glob(evening_pattern))) > 0

    return {
        "morning": has_morning,
        "evening": has_evening,
    }

@app.route("/api/source-state")
def api_source_state():
    data = _build_data()
    sync_info = _get_last_sync_info()
    anchors_today = _get_anchors_today()

    return jsonify({
        # Existing fields (unchanged)
        "source_mode": data.get("source_mode", "runtime"),
        "source_file": data.get("source_file"),
        "users_source_file": data.get("users_source_file"),
        "managed_source_file": data.get("managed_source_file"),
        "users_row_count": data.get("users_row_count", 0),
        "managed_row_count": data.get("managed_row_count", 0),
        "sites_count": len(data.get("sites", [])),
        "source_error": data.get("source_error"),

        # Sprint 9 Step 3 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Automation status fields
        "last_sync_time": sync_info["last_sync_time"],
        "last_sync_age_seconds": sync_info["last_sync_age_seconds"],
        "auto_sync_active": sync_info["auto_sync_active"],
        "anchors_today": anchors_today,
    })


@app.route("/api/data")
def api_data():
    return jsonify(_build_data())




# --- JOM Site Registry / Discovery API ---
@app.route("/api/site-registry")
def api_site_registry():
    from backend.site_registry_runtime import build_registry
    return jsonify(build_registry(BASE_DIR))

@app.route("/api/site-registry/rebuild", methods=["POST"])
def api_site_registry_rebuild():
    from backend.site_registry_runtime import build_registry
    return jsonify(build_registry(BASE_DIR))

@app.route("/api/site-registry/approve", methods=["POST"])
def api_site_registry_approve():
    from backend.site_registry_runtime import approve_site
    payload = request.get_json(silent=True) or {}
    return jsonify(approve_site(BASE_DIR, payload, approved_by="jom_admin"))

@app.route("/api/site-registry/ignore", methods=["POST"])
def api_site_registry_ignore():
    from backend.site_registry_runtime import ignore_site
    payload = request.get_json(silent=True) or {}
    return jsonify(ignore_site(BASE_DIR, payload, ignored_by="jom_admin"))

@app.route("/api/site-registry/unmonitor", methods=["POST"])
def api_site_registry_unmonitor():
    from backend.site_registry_runtime import unmonitor_site
    payload = request.get_json(silent=True) or {}
    return jsonify(unmonitor_site(BASE_DIR, payload, removed_by="jom_admin"))

# --- End JOM Site Registry / Discovery API ---
if __name__ == "__main__":
    DEBUG_MODE = True
    if not DEBUG_MODE or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        run_startup_self_heal()
    app.run(debug=DEBUG_MODE, host="127.0.0.1", port=5000)





