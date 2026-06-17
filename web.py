from flask import Flask, render_template, jsonify, abort, request
from pathlib import Path
import csv
import glob
import os
from datetime import datetime
from estate_metrics import build_estate_metrics
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
from intelligence_engine import enrich_estate
from backend.intelligence_runtime import attach_intelligence_safe, enrich_context_with_intelligence
from backend.runtime_source_adapter import load_preferred_source_payload

BASE_DIR = Path(__file__).resolve().parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)


def _load_csv_rows(pattern):
    matches = glob.glob(str(BASE_DIR / pattern))
    if not matches:
        return [], None
    latest_file = max(matches, key=os.path.getmtime)
    try:
        with open(latest_file, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
            print(f"✅ Loaded {len(rows)} rows from {os.path.basename(latest_file)}")
            return rows, os.path.basename(latest_file)
    except Exception as e:
        print(f"❌ ERROR READING {latest_file}: {e}")
        return [], os.path.basename(latest_file)


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


def _apply_source_metadata(data, source_mode, source_file=None, users_file=None, managed_file=None, users_rows=None, managed_rows=None):
    data["source_mode"] = source_mode
    data["source_file"] = source_file
    if source_mode == "runtime":
        source_label = f"Runtime payload: {source_file}" if source_file else "Runtime payload"
        data["users_source_file"] = data.get("users_source_file") or source_label
        data["managed_source_file"] = data.get("managed_source_file") or source_label
        data["users_row_count"] = data.get("users_row_count", 0) or len(users_rows or [])
        data["managed_row_count"] = data.get("managed_row_count", 0) or len(managed_rows or [])
    else:
        data["users_source_file"] = users_file
        data["managed_source_file"] = managed_file
        data["users_row_count"] = len(users_rows or [])
        data["managed_row_count"] = len(managed_rows or [])
    return data


def _finalise_data(data, *, source_mode, source_file=None, users_file=None, managed_file=None, users_rows=None, managed_rows=None):
    data = data if isinstance(data, dict) else {}
    data["sites"] = _coerce_sites(data)
    data = _apply_source_metadata(
        data,
        source_mode=source_mode,
        source_file=source_file,
        users_file=users_file,
        managed_file=managed_file,
        users_rows=users_rows,
        managed_rows=managed_rows,
    )
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

    data = attach_intelligence_safe(data)
    data["drilldowns"].update(_build_intelligence_drilldowns(data))
    data["drilldowns"].update(_build_intelligence_summary_drilldown(data))

    # Safe additional intelligence layer from checkpoint e01c306 onward.
    data = enrich_estate(data)

    return data


def _merge_project_counts(sites):
    project_counts = load_project_counts_from_latest_run()
    for site in sites:
        site_key = site.get("site")
        project_data = project_counts.get(site_key, {})
        site["project_count"] = project_data.get("project_count")
        site["issue_count_total"] = project_data.get("issue_count_total")
        site["issue_count_unresolved"] = project_data.get("issue_count_unresolved")
        site["issue_count_updated_last_7d"] = project_data.get("issue_count_updated_last_7d")
        site["project_count_delta"] = project_data.get("project_count_delta")
    return sites


def _merge_project_intelligence(sites, project_intelligence):
    site_map = project_intelligence.get("site_map", {}) if isinstance(project_intelligence, dict) else {}
    for site in sites:
        site_key = site.get("site")
        info = site_map.get(site_key, {})
        site["sampled_project_rows"] = info.get("sampled_project_rows", 0)
        site["project_sample_available"] = True if info.get("project_rows") else False
    return sites


def _merge_change_detection(sites, change_detection):
    site_map = change_detection.get("site_map", {}) if isinstance(change_detection, dict) else {}
    for site in sites:
        site_key = site.get("site")
        change_data = site_map.get(site_key, {})
        site["growth_status"] = change_data.get("growth_status")
        site["project_count_delta_live"] = change_data.get("project_count_delta", 0)
        site["total_users_delta"] = change_data.get("total_users_delta", 0)
        site["active_users_delta"] = change_data.get("active_users_delta", 0)
        site["inactive_users_delta"] = change_data.get("inactive_users_delta", 0)
        site["licensed_users_estimate"] = change_data.get("licensed_users_estimate")
        site["licensed_users_estimate_delta"] = change_data.get("licensed_users_estimate_delta", 0)
        site["audit_status"] = change_data.get("audit_status")
        site["audit_api_access"] = change_data.get("audit_api_access")
        site["licence_status"] = change_data.get("licence_status")
        site["licence_api_access"] = change_data.get("licence_api_access")
        site["permission_limited_checks"] = change_data.get("permission_limited_checks", [])
        site["status_reasons"] = change_data.get("status_reasons", [])
        site["trend_signals"] = change_data.get("trend_signals", [])
        site["snapshot_count"] = change_data.get("snapshot_count", 0)
        site["trend_score"] = change_data.get("trend_score", 0)
        site["new_site_candidate"] = change_data.get("new_site_candidate", False)
        site["attention_reasons"] = change_data.get("attention_reasons", [])
    return sites


def _merge_historical_trends(sites, historical_trends):
    site_trends = historical_trends.get("site_trends", []) if isinstance(historical_trends, dict) else []
    trend_map = {}
    for trend in site_trends:
        site_key = trend.get("site_key")
        if site_key:
            trend_map[site_key] = trend

    for site in sites:
        site_key = site.get("site")
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
        "inactive_users": "Atlassian Administration → Directory / Product Access",
        "unmanaged_accounts": "Atlassian Administration → Managed Accounts",
        "orphaned_projects": "Jira Administration → Projects",
        "unused_apps": "Atlassian Administration → Connected Apps",
        "tier_capacity": "Atlassian Administration → Billing / Subscription",
        "seat_capacity": "Atlassian Administration → Billing / Subscription",
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
            title = f"{site_name} — {_prettify_label(risk_type)}"
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
    if runtime_payload:
        return _finalise_data(
            runtime_payload,
            source_mode="runtime",
            source_file=runtime_meta.get("file"),
        )

    users_rows, users_file = _load_csv_rows("export-users*.csv")
    managed_rows, managed_file = _load_csv_rows("*managed_accounts*.csv")
    data = build_estate_metrics(users_rows, managed_rows)
    return _finalise_data(
        data,
        source_mode="csv",
        users_file=users_file,
        managed_file=managed_file,
        users_rows=users_rows,
        managed_rows=managed_rows,
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
        "project_intelligence": data.get("project_intelligence", {}),
        "historical_trends": data.get("historical_trends", {}),
        "snapshot_index": data.get("snapshot_index", {}),
        "latest_snapshot_entry": data.get("latest_snapshot_entry", {}),
        "latest_snapshot": data.get("latest_snapshot", {}),
        "users_source_file": data.get("users_source_file"),
        "managed_source_file": data.get("managed_source_file"),
        "users_row_count": data.get("users_row_count", 0),
        "managed_row_count": data.get("managed_row_count", 0),
        "source_mode": data.get("source_mode", "csv"),
        "source_file": data.get("source_file"),
        "intelligence_summary": data.get("intelligence_summary", {}),
    }
    return enrich_context_with_intelligence(context, data)


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


@app.route("/api/source-state")
def api_source_state():
    data = _build_data()
    return jsonify({
        "source_mode": data.get("source_mode", "csv"),
        "source_file": data.get("source_file"),
        "users_source_file": data.get("users_source_file"),
        "managed_source_file": data.get("managed_source_file"),
        "users_row_count": data.get("users_row_count", 0),
        "managed_row_count": data.get("managed_row_count", 0),
        "sites_count": len(data.get("sites", [])),
    })


@app.route("/api/data")
def api_data():
    return jsonify(_build_data())


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
