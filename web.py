
from flask import Flask, render_template, jsonify, abort, request
from pathlib import Path
import csv
import glob
import os

from estate_metrics import build_estate_metrics
from billing_catalog import get_billing_catalog

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


def _sort_rows(rows, sort_key):
    if not rows or not sort_key:
        return rows

    def safe_value(row):
        value = row.get(sort_key, "")
        if value is None:
            return ""
        if isinstance(value, list):
            return ", ".join(str(v) for v in value).lower()
        return str(value).lower()

    return sorted(rows, key=safe_value)


def _build_data():
    users_rows, users_file = _load_csv_rows("export-users*.csv")
    managed_rows, managed_file = _load_csv_rows("*managed_accounts*.csv")

    data = build_estate_metrics(users_rows, managed_rows)
    data["users_source_file"] = users_file
    data["managed_source_file"] = managed_file
    data["users_row_count"] = len(users_rows)
    data["managed_row_count"] = len(managed_rows)

    billing = get_billing_catalog()
    data["billing_summary"] = billing.get("summary", {})

    drilldowns = data.get("drilldowns", {})
    drilldowns.update(billing.get("drilldowns", {}))
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
    rows = _sort_rows(item.get("rows", []), sort_key)

    return render_template(
        "detail_list.html",
        detail_key=key,
        title=item.get("title", "Detail"),
        reason=item.get("reason", ""),
        atlassian_area=item.get("atlassian_area", "Atlassian Administration"),
        columns=item.get("columns", []),
        rows=rows,
        sort_key=sort_key,
    )


@app.route("/api/data")
def api_data():
    return jsonify(_build_data())


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
