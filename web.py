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
        site["new_site_candidate"] = change_data.get("new_site_candidate", False)
        site["attention_reasons"] = change_data.get("attention_reasons", [])

    return sites


def _build_data():
    users_rows, users_file = _load_csv_rows("export-users*.csv")
    managed_rows, managed_file = _load_csv_rows("*managed_accounts*.csv")

    data = build_estate_metrics(users_rows, managed_rows)
    data["users_source_file"] = users_file
    data["managed_source_file"] = managed_file
    data["users_row_count"] = len(users_rows)
    data["managed_row_count"] = len(managed_rows)

    data["sites"] = _merge_project_counts(data.get("sites", []))

    project_intelligence = load_project_intelligence_from_latest_run()
    data["project_intelligence"] = project_intelligence
    data["sites"] = _merge_project_intelligence(data.get("sites", []), project_intelligence)

    change_detection = load_latest_run_change_detection()
    data["change_detection"] = change_detection
    data["sites"] = _merge_change_detection(data.get("sites", []), change_detection)

    site_discovery = load_site_discovery_from_latest_run()
    data["site_discovery"] = site_discovery

    data["critical_sites"] = [s for s in data["sites"] if s.get("status") == "critical"]
    data["warning_sites"] = [s for s in data["sites"] if s.get("status") == "warning"]
    data["stable_sites"] = [s for s in data["sites"] if s.get("status") == "stable"]

    billing = get_billing_catalog()
    data["billing_summary"] = billing.get("summary", {})

    drilldowns = data.get("drilldowns", {})
    drilldowns.update(billing.get("drilldowns", {}))
    drilldowns.update(build_change_detection_drilldowns(change_detection))
    drilldowns.update(build_project_drilldowns_from_latest_run())
    drilldowns.update(build_site_discovery_drilldowns(site_discovery))
    data["drilldowns"] = drilldowns

    return data


@app.route("/")
def home():
    data = _build_data()
    return render_template(
        "home.html",
        estate=data.get("estate", {}),
        sites=data.get("sites", []),
        critical_sites=data.get("critical_sites", []),
        warning_sites=data.get("warning_sites", []),
        stable_sites=data.get("stable_sites", []),
        org_product_breakdown=data.get("org_product_breakdown", []),
        users_export_breakdown=data.get("users_export_breakdown", []),
        billing_summary=data.get("billing_summary", {}),
        change_detection=data.get("change_detection", {}),
        site_discovery=data.get("site_discovery", {}),
        project_intelligence=data.get("project_intelligence", {}),
        users_source_file=data.get("users_source_file"),
        managed_source_file=data.get("managed_source_file"),
        users_row_count=data.get("users_row_count", 0),
        managed_row_count=data.get("managed_row_count", 0),
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


@app.route("/api/data")
def api_data():
    return jsonify(_build_data())


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)