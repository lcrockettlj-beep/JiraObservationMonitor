from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
html_path = ROOT / "templates" / "estate_report.html"
js_path = ROOT / "static" / "js" / "jom_estate_report_v1.js"
css_path = ROOT / "static" / "css" / "jom_estate_report_v1.css"
web_path = ROOT / "app" / "web.py"

html = html_path.read_text(encoding="utf-8-sig")
js = js_path.read_text(encoding="utf-8-sig")
css = css_path.read_text(encoding="utf-8-sig")
web = web_path.read_text(encoding="utf-8-sig")

checks = {
    "phase owner": "JOM_ESTATE_REPORT_UX_PHASE1_V1" in html and css.startswith("/* JOM_ESTATE_REPORT_UX_PHASE1_V1 */"),
    "existing API only": set(re.findall(r'"(/api/[^" ]+)"', js)) == {"/api/reporting/estate-report"},
    "exact consumer fields": all(value in js for value in [
        "s.total_sites",
        "s.monitored_sites",
        "s.monitoring_coverage_percent",
        "s.product_access_assignments",
        "s.failed_sources",
        "s.active_users_display",
        "s.commercial_billing_display",
        "d.actions",
        "d.source_health",
    ]),
    "operator posture": all(value in html for value in [
        "Estate sites",
        "Monitored sites",
        "Monitoring coverage",
        "Product assignments",
        "Source issues",
        "Required decisions",
    ]),
    "operational navigation": all(value in html for value in [
        "/estate",
        "/site-workspace",
        "/estate/pending",
        "/estate/monitored",
        "/estate/discovered",
    ]),
    "honest contract boundary": "Per-site ownership and discovery rows" in html and "does not publish a reconciled per-site operational dataset" in html,
    "contained rail": all(value in css for value in [
        "position:fixed",
        "max-height:calc(100vh - var(--er-top) - var(--er-bottom))",
        "overflow-y:auto",
        "scrollbar-gutter:stable",
    ]),
    "fail closed": all(value in js for value in ["er__status--blocked", "Authority unavailable", "cannot be published"]),
    "read only": "Read-only" in html,
    "no invented authority": all(value not in js for value in ["ownership_coverage", "discovery_backlog", "pending_sites", "sites.map"]),
    "no writes polling streaming": all(value not in js for value in ["POST", "PUT", "PATCH", "DELETE", "setInterval", "WebSocket", "EventSource"]),
    "proven page route": "@app.route('/estate-report')" in web and "return render_template('estate_report.html')" in web,
    "proven API route": '@app.route("/api/reporting/estate-report")' in web,
    "no invalid page route": "/reports/estate" not in html and "/reports/estate" not in js,
    "single newline": all(path.read_bytes().endswith(b"\n") and not path.read_bytes().endswith(b"\n\n") for path in [html_path, js_path, css_path]),
}

failures = []
for label, passed in checks.items():
    print(("PASS" if passed else "FAIL") + ": " + label)
    if not passed:
        failures.append(label)

if failures:
    print("VALIDATION FAILED: " + str(len(failures)))
    sys.exit(1)

print("VALIDATION PASS: Estate Report UX Phase 1 uses the proven /estate-report page route and existing Estate Report authority without new backend, collector or runtime claims.")
