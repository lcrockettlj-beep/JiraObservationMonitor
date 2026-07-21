from __future__ import annotations

from flask import Flask, jsonify, render_template, send_from_directory, request
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.runtime.admin_enriched_chain import run_pipeline as run_snapshot
from app.runtime.operational_source_recovery import run_pipeline as run_recovery
from app.operational.operator_surface import build_alerts, build_operator_surface, build_operator_summary

ROOT = Path(__file__).resolve().parents[1]
app = Flask(
    __name__,
    template_folder=str(ROOT / "templates"),
    static_folder=str(ROOT / "static"),
    static_url_path="/static",
)

DATA_PATH = ROOT / "static" / "data"
RUNTIME_STATUS_PATH = DATA_PATH / "runtime_execution_status.json"
RUNTIME_HISTORY_PATH = DATA_PATH / "runtime_execution_history.json"
_runtime_lock = threading.Lock()


class SafeDict(dict):
    """Dict that returns safe empty values for missing template attributes."""

    def __getattr__(self, item):
        return self.get(item, SafeDict())


def to_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return SafeDict({key: to_safe(val) for key, val in value.items()})
    if isinstance(value, list):
        return [to_safe(item) for item in value]
    return value


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(filename: str, default: Any = None) -> Any:
    if default is None:
        default = {}
    path = DATA_PATH / filename
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"_load_error": str(exc), "_file": filename}


def write_json(path: Path, payload: Any) -> Any:
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def write_runtime_status(payload: Dict[str, Any]) -> Dict[str, Any]:
    return write_json(RUNTIME_STATUS_PATH, payload)


def read_runtime_status() -> Dict[str, Any]:
    payload = load_json("runtime_execution_status.json", {})
    if not isinstance(payload, dict) or not payload:
        return {"state": "idle", "running": False, "source": "runtime_execution_status.json not yet created"}
    return payload


def compact_runtime_status() -> Dict[str, Any]:
    status = read_runtime_status()
    return {
        "state": status.get("state", "unknown"),
        "running": bool(status.get("running", False)),
        "last_action": status.get("last_action"),
        "last_started_at_utc": status.get("last_started_at_utc"),
        "last_finished_at_utc": status.get("last_finished_at_utc"),
        "last_result_status": status.get("last_result_status"),
        "last_error": status.get("last_error"),
    }


def read_runtime_history() -> List[Any]:
    payload = load_json("runtime_execution_history.json", [])
    return payload if isinstance(payload, list) else []


def append_runtime_history(event: Dict[str, Any]) -> List[Any]:
    history = read_runtime_history()
    history.append(event)
    history = history[-100:]
    write_json(RUNTIME_HISTORY_PATH, history)
    return history


def execute_guarded(action_name: str, runner):
    acquired = _runtime_lock.acquire(blocking=False)
    if not acquired:
        current = compact_runtime_status()
        current["state"] = "busy"
        current["running"] = True
        current["rejected_action"] = action_name
        current["rejected_at_utc"] = now_utc()
        return jsonify({"status": "busy", "message": "Runtime execution already in progress", "runtime_status": current}), 409

    started = now_utc()
    write_runtime_status({
        "state": "running",
        "running": True,
        "last_action": action_name,
        "last_started_at_utc": started,
        "last_finished_at_utc": None,
        "last_result_status": None,
        "last_error": None,
    })

    try:
        result = runner()
        finished = now_utc()
        result_status = "success"
        if isinstance(result, dict):
            result_status = result.get("overall_status") or result.get("status") or "success"
        status_payload = write_runtime_status({
            "state": "idle",
            "running": False,
            "last_action": action_name,
            "last_started_at_utc": started,
            "last_finished_at_utc": finished,
            "last_result_status": result_status,
            "last_error": None,
            "last_result": result,
        })
        append_runtime_history({
            "action": action_name,
            "started_at_utc": started,
            "finished_at_utc": finished,
            "status": "success",
            "result_status": result_status,
        })
        return jsonify({"status": "success", "message": f"{action_name} executed", "runtime_status": status_payload, "result": result})
    except Exception as exc:
        finished = now_utc()
        status_payload = write_runtime_status({
            "state": "failed",
            "running": False,
            "last_action": action_name,
            "last_started_at_utc": started,
            "last_finished_at_utc": finished,
            "last_result_status": "failed",
            "last_error": str(exc),
        })
        append_runtime_history({
            "action": action_name,
            "started_at_utc": started,
            "finished_at_utc": finished,
            "status": "failed",
            "error": str(exc),
        })
        return jsonify({"status": "error", "message": str(exc), "runtime_status": status_payload}), 500
    finally:
        _runtime_lock.release()


def _translate(value: Any = "") -> str:
    return str(value)


def _registry_parts() -> Dict[str, Any]:
    registry = load_json("site_registry.json", {})
    sites = registry.get("sites", []) if isinstance(registry, dict) else []
    monitored = [site for site in sites if isinstance(site, dict) and site.get("classification") == "monitored"]
    discovered = [site for site in sites if isinstance(site, dict) and site.get("classification") == "discovered"]
    summary = registry.get("summary", {}) if isinstance(registry, dict) else {}
    if not summary:
        summary = {
            "site_count": len(sites),
            "monitored_count": len(monitored),
            "discovered_count": len(discovered),
        }
    return {
        "registry": registry,
        "sites": sites,
        "registry_monitored_sites": monitored,
        "registry_discovered_sites": discovered,
        "registry_summary": summary,
        "site_discovery": discovered,
    }


def _site_parts() -> Dict[str, Any]:
    parts = _registry_parts()
    sites = parts.get("sites", [])
    selected = sites[0] if sites else {}
    if not isinstance(selected, dict):
        selected = {}
    site_key = selected.get("key") or selected.get("site_key") or selected.get("name") or "site"
    site_title = selected.get("title") or selected.get("name") or site_key
    site_url = selected.get("url") or selected.get("site_url") or ""
    site_status = selected.get("status") or selected.get("classification") or "unknown"
    return {
        "site": selected,
        "site_key": site_key,
        "site_title": site_title,
        "site_url": site_url,
        "site_status": site_status,
        "site_source_file": "site_registry.json",
        "source_file": "site_registry.json",
        "project_rows": [],
        "endpoint_rows": [],
        "trend_rows": [],
        "data_quality_breakdown": [],
    }


def base_template_context() -> Dict[str, Any]:
    operator_summary = build_operator_summary()
    operator_surface = build_operator_surface()
    operator_alert_payload = {"count": len(build_alerts()), "alerts": build_alerts()}
    registry_parts = _registry_parts()
    admin_truth = load_json("admin_truth_v2.json", {})
    estate_product_access = load_json("estate_product_access.json", {})
    user_footprint = load_json("user_footprint.json", {})
    runtime_status = compact_runtime_status()

    context = {
        "_": _translate,
        "operator_summary": operator_summary,
        "operator_surface": operator_surface,
        "operator_alerts": operator_alert_payload.get("alerts", []),
        "runtime_status": runtime_status,
        "admin_truth": admin_truth,
        "estate_product_access": estate_product_access,
        "user_footprint": user_footprint,
        "site_registry": registry_parts.get("registry", {}),
        "registry_summary": registry_parts.get("registry_summary", {}),
        "registry_monitored_sites": registry_parts.get("registry_monitored_sites", []),
        "registry_discovered_sites": registry_parts.get("registry_discovered_sites", []),
        "site_discovery": {
            "summary": registry_parts.get("registry_summary", {}),
            "sites": registry_parts.get("sites", []),
            "monitored_sites": registry_parts.get("registry_monitored_sites", []),
            "discovered_sites": registry_parts.get("registry_discovered_sites", []),
        },
        "estate": operator_surface.get("estate", {}) if isinstance(operator_surface, dict) else {},
        "latest_snapshot": load_json("admin_enriched_refresh_status.json", {}),
        "latest_snapshot_entry": runtime_status,
        "latest_snapshot_timestamp": runtime_status.get("last_finished_at_utc"),
        "critical_sites": [],
        "warning_sites": build_alerts(),
        "stable_sites": registry_parts.get("registry_monitored_sites", []),
        "intelligence_sites": registry_parts.get("sites", []),
        "managed_row_count": len(registry_parts.get("registry_monitored_sites", [])),
        "managed_user_count": user_footprint.get("users") if isinstance(user_footprint, dict) else 0,
        "users_row_count": user_footprint.get("users") if isinstance(user_footprint, dict) else 0,
        "total_users_count": user_footprint.get("users") if isinstance(user_footprint, dict) else 0,
        "action_label": "Review",
    }
    return to_safe(context)


def home_context() -> Dict[str, Any]:
    return base_template_context()


def estate_context() -> Dict[str, Any]:
    return base_template_context()


def reference_context() -> Dict[str, Any]:
    context = base_template_context()
    admin_truth = load_json("admin_truth_v2.json", {})
    context.update(to_safe({
        "billing_summary": admin_truth,
        "org_product_breakdown": [],
        "users_export_breakdown": [],
    }))
    return context


def site_context() -> Dict[str, Any]:
    context = base_template_context()
    context.update(to_safe(_site_parts()))
    return context


def detail_list_context() -> Dict[str, Any]:
    items: List[Any] = []
    context = base_template_context()
    context.update(to_safe({
        "title": "Detail list",
        "heading": "Detail list",
        "subtitle": "Runtime generated detail list",
        "description": "No detail selection has been provided.",
        "items": items,
        "entries": items,
        "rows": items,
        "results": items,
        "data": items,
        "count": len(items),
        "record_count": len(items),
    }))
    return context


@app.route("/")
def home():
    return render_template("home.html", **home_context())

@app.route("/admin/truth")
def admin_truth():
    return jsonify(load_json("admin_truth_v2.json"))


@app.route("/estate/product-access")
def estate_product_access():
    return jsonify(load_json("estate_product_access.json"))


@app.route("/users/footprint")
def user_footprint():
    return jsonify(load_json("user_footprint.json"))


@app.route("/registry/sites")
def site_registry():
    return jsonify(load_json("site_registry.json"))


@app.route("/runtime/status")
def runtime_status():
    return jsonify(compact_runtime_status())


@app.route("/runtime/history")
def runtime_history():
    return jsonify(read_runtime_history())


@app.route("/runtime/refresh")
def runtime_refresh():
    return execute_guarded("refresh", run_snapshot)


@app.route("/runtime/recover")
def runtime_recover():
    return execute_guarded("recover", run_recovery)


@app.route("/operator/summary")
def operator_summary():
    return jsonify(build_operator_summary())


@app.route("/operator/alerts")
def operator_alerts():
    alerts = build_alerts()
    return jsonify({"count": len(alerts), "alerts": alerts})


@app.route("/operator/surface")
def operator_surface():
    return jsonify(build_operator_surface())


@app.route("/operator/observability")
def operator_observability():
    return jsonify({"runtime_status": compact_runtime_status(), "runtime_history": read_runtime_history()})


@app.route("/health")
def health():
    runtime = compact_runtime_status()
    summary = build_operator_summary()
    return jsonify({"status": "healthy" if not runtime.get("running") else "busy", "runtime": runtime, "operator_posture": summary.get("posture"), "alert_summary": summary.get("alert_summary")})


@app.route("/home")
def page_home():
    return render_template("home.html", **home_context())


@app.route("/estate")
def page_estate():
    return render_template("estate.html", **estate_context())


@app.route("/reference")
def page_reference():
    return render_template("reference.html", **reference_context())


@app.route("/site")
def page_site():
    return render_template("site.html", **site_context())


@app.route("/detail-list")
def page_detail_list():
    return render_template("detail_list.html", **detail_list_context())



# ============================================================
# LEGACY FRONTEND API COMPATIBILITY ROUTES - PACK v1
# ============================================================
@app.route("/api/source-state")
def api_source_state_legacy():
    return jsonify({
        "schema": "jom-legacy-source-state-compat-v1",
        "source_freshness": load_json("source_freshness_audit.json", {}),
        "source_reliability": load_json("source_reliability_status.json", {}),
        "runtime_status": compact_runtime_status(),
        "operator_summary": build_operator_summary(),
    })


@app.route("/api/data")
def api_data_legacy():
    return jsonify({
        "schema": "jom-legacy-data-compat-v1",
        "operator_surface": build_operator_surface(),
        "operator_summary": build_operator_summary(),
        "admin_truth": load_json("admin_truth_v2.json", {}),
        "estate_product_access": load_json("estate_product_access.json", {}),
        "user_footprint": load_json("user_footprint.json", {}),
        "site_registry": load_json("site_registry.json", {}),
    })


@app.route("/api/site-registry")
def api_site_registry_legacy():
    return jsonify(load_json("site_registry.json", {}))


@app.route("/reports/<path:filename>")
def reports_file_legacy(filename):
    reports_root = ROOT / "reports"
    return send_from_directory(str(reports_root), filename)



@app.route('/site/<path:site_key>')
def site_workspace(site_key):
    return render_template('site.html', site_key=site_key)

# --- JOM EXPORT REPORTING ROUTES v1 START ---
try:
    from flask import Response
except Exception:
    Response = None

try:
    from app.reporting.export_reporting import get_report, to_csv, to_html
except Exception:
    get_report = None
    to_csv = None
    to_html = None

@app.route("/reports/generated/<report_kind>/<fmt>")
def jom_generated_report(report_kind, fmt):
    if get_report is None:
        return jsonify({"ok": False, "error": "report generator unavailable"}), 500
    report = get_report(report_kind)
    return _jom_generated_report_response(report_kind, fmt, report)

@app.route("/reports/generated/site/<site_key>/<fmt>")
def jom_generated_site_report(site_key, fmt):
    if get_report is None:
        return jsonify({"ok": False, "error": "report generator unavailable"}), 500
    report = get_report("site", site_key)
    return _jom_generated_report_response("site_" + str(site_key), fmt, report)

def _jom_generated_report_response(report_name, fmt, report):
    fmt = str(fmt or "json").lower()
    filename = "jom_" + str(report_name).replace("/", "_") + "_report." + fmt
    if fmt == "json":
        return app.response_class(json.dumps(report, indent=2), mimetype="application/json")
    if fmt == "csv":
        body = to_csv(report) if to_csv else "field,value\nerror,csv unavailable\n"
        return Response(body, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=" + filename})
    if fmt == "html":
        body = to_html(report) if to_html else "<h1>Report unavailable</h1>"
        return Response(body, mimetype="text/html")
    return jsonify({"ok": False, "error": "unsupported report format", "format": fmt}), 400
# --- JOM EXPORT REPORTING ROUTES v1 END ---




# --- JOM SITE REVIEW LIFECYCLE DECISION ROUTES v1 START ---
SITE_LIFECYCLE_DECISIONS_PATH = DATA_PATH / "site_lifecycle_decisions.json"

def _normalise_site_key(value: Any) -> str:
    return str(value or "").strip().lower()

def _site_key_from_record(site: Dict[str, Any]) -> str:
    return str(site.get("site_key") or site.get("key") or site.get("site_name") or site.get("name") or "")

def _load_lifecycle_decisions() -> Dict[str, Any]:
    payload = load_json("site_lifecycle_decisions.json", {})
    if not isinstance(payload, dict) or not payload:
        payload = {"schema": "jom-site-lifecycle-decisions-v1", "generated_at_utc": None, "decisions": {}, "history": []}
    payload.setdefault("schema", "jom-site-lifecycle-decisions-v1")
    payload.setdefault("decisions", {})
    payload.setdefault("history", [])
    return payload

def _write_lifecycle_decisions(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload["generated_at_utc"] = now_utc()
    return write_json(SITE_LIFECYCLE_DECISIONS_PATH, payload)

def _find_site(site_key: str) -> Dict[str, Any]:
    registry = load_json("site_registry.json", {})
    sites = registry.get("sites", []) if isinstance(registry, dict) else []
    target = _normalise_site_key(site_key)
    for site in sites:
        if isinstance(site, dict) and _normalise_site_key(_site_key_from_record(site)) == target:
            return site
    for site in sites:
        if isinstance(site, dict) and target in json.dumps(site).lower():
            return site
    return {}

def _review_sources_for_site(site_key: str) -> Dict[str, Any]:
    onboarding = load_json("site_onboarding_review.json", {})
    for bucket in ["pending", "approved", "ignored"]:
        for item in onboarding.get(bucket, []) if isinstance(onboarding, dict) else []:
            if isinstance(item, dict) and _normalise_site_key(item.get("site_key")) == _normalise_site_key(site_key):
                return {"bucket": bucket, "record": item}
    return {"bucket": None, "record": {}}

def _owner_from_known_sources(site_key: str, site: Dict[str, Any]) -> str:
    for key in ["owner", "business_owner", "technical_owner", "contact", "site_owner", "admin_owner"]:
        if site.get(key):
            return str(site.get(key))
    sources_text = json.dumps(site.get("sources") or site.get("source") or "").lower()
    org_admin_managed_sites = {"gli-delivery-tm", "gli-global-technology", "gli-it-project", "gli-tracker"}
    if "named_access" in sources_text or _normalise_site_key(site_key) in org_admin_managed_sites:
        return "Org Admin / Atlassian administration"
    admin_truth = load_json("admin_truth_v2.json", {})
    blocked = admin_truth.get("blocked_resources", []) if isinstance(admin_truth, dict) else []
    for item in blocked:
        if isinstance(item, dict) and _normalise_site_key(item.get("site_key")) == _normalise_site_key(site_key):
            return "Owner not available - access blocked; Atlassian/Product admin required"
    return "Owner not assigned"

def _build_site_review_payload(site_key: str) -> Dict[str, Any]:
    site = _find_site(site_key)
    source_review = _review_sources_for_site(site_key)
    decisions = _load_lifecycle_decisions()
    decision_state = decisions.get("decisions", {}).get(site_key, {})
    history = [item for item in decisions.get("history", []) if isinstance(item, dict) and item.get("site_key") == site_key]
    key = _site_key_from_record(site) or site_key
    url = site.get("site_url") or site.get("url") or source_review.get("record", {}).get("url") or ""
    sources = site.get("sources") or site.get("source") or source_review.get("record", {}).get("source") or "Registry"
    if isinstance(sources, str):
        sources_list = [sources]
    else:
        sources_list = sources if isinstance(sources, list) else ["Registry"]
    classification = site.get("classification") or source_review.get("record", {}).get("classification") or "discovered"
    is_monitored = bool(site.get("monitored") or site.get("is_monitored") or site.get("in_monitoring_scope") or str(classification).lower() == "monitored")
    lifecycle_status = "Monitored" if is_monitored else "Discovered"
    if decision_state.get("decision") == "approve":
        lifecycle_status = "Approval Pending"
    elif decision_state.get("decision") == "ignore":
        lifecycle_status = "Ignored"
    elif decision_state.get("decision") == "pending":
        lifecycle_status = "Pending Review"
    owner = _owner_from_known_sources(key, site)
    access = ", ".join(sources_list)
    admin_truth = load_json("admin_truth_v2.json", {})
    for item in admin_truth.get("blocked_resources", []) if isinstance(admin_truth, dict) else []:
        if isinstance(item, dict) and _normalise_site_key(item.get("site_key")) == _normalise_site_key(key):
            access = "Access blocked - administrator permissions required"
    return {
        "site_key": key,
        "site_name": site.get("site_name") or site.get("name") or key,
        "url": url,
        "site": site,
        "sources": sources_list,
        "classification": classification,
        "lifecycle_status": lifecycle_status,
        "owner": owner,
        "contact_route": ("Atlassian/Product admin required" if "blocked" in access.lower() else ("Org admin / Atlassian admin console" if ("named_access" in access.lower() or "Org Admin" in owner) else "Owner/contact not yet sourced")),
        "readiness": {
            "identity": "URL confirmed" if url else "URL missing",
            "ownership": owner,
            "access": access,
            "monitoring": "Monitoring enabled" if is_monitored else "Not currently monitored",
            "credentials": "Credentials required before monitoring enablement" if not is_monitored else "Monitoring credentials active or not required",
        },
        "decision_state": decision_state,
        "decision_history": history,
        "onboarding_review": source_review,
        "safety_note": "Approve records Approval Pending / Credential Required. It does not create or retrieve tokens automatically.",
    }

@app.route("/api/site-review/<path:site_key>")
def api_site_review(site_key):
    return jsonify(_build_site_review_payload(site_key))

@app.route("/api/site-review/<path:site_key>/decision", methods=["POST"])
def api_site_review_decision(site_key):
    payload = request.get_json(silent=True) or {}
    decision = str(payload.get("decision") or "pending").lower().strip()
    allowed = {"approve", "ignore", "pending", "restore"}
    if decision not in allowed:
        return jsonify({"ok": False, "error": "unsupported decision", "allowed": sorted(allowed)}), 400
    decisions = _load_lifecycle_decisions()
    decisions.setdefault("decisions", {})
    decisions.setdefault("history", [])
    previous = decisions["decisions"].get(site_key, {})
    if decision == "restore":
        record = {
            "site_key": site_key,
            "decision": "pending",
            "previous_decision": previous.get("decision"),
            "reason": payload.get("reason") or "restored to review queue",
            "actor": payload.get("actor") or "operator",
            "decided_at_utc": now_utc(),
            "reversible": True,
            "requires_credentials": False,
        }
    else:
        record = {
            "site_key": site_key,
            "decision": decision,
            "previous_decision": previous.get("decision"),
            "reason": payload.get("reason") or decision,
            "actor": payload.get("actor") or "operator",
            "decided_at_utc": now_utc(),
            "reversible": True,
            "requires_credentials": decision == "approve",
            "next_state": "approval_pending_credential_required" if decision == "approve" else ("ignored" if decision == "ignore" else "pending_review"),
        }
    decisions["decisions"][site_key] = record
    decisions["history"].append(record)
    _write_lifecycle_decisions(decisions)
    message = "Approval recorded. Monitoring is pending token/credential enablement." if decision == "approve" else "Lifecycle decision recorded."
    if decision == "restore":
        message = "Site restored to review queue."
    return jsonify({"ok": True, "message": message, "record": record})

@app.route("/api/site-lifecycle/decisions")
def api_site_lifecycle_decisions():
    payload = load_json("site_lifecycle_decisions.json", {})
    if not isinstance(payload, dict) or not payload:
        payload = {"schema": "jom-site-lifecycle-decisions-v1", "decisions": {}, "history": []}
    payload.setdefault("decisions", {})
    payload.setdefault("history", [])
    return jsonify(payload)


# --- enable_monitoring_via_jom_v1 START ---
def _recalculate_registry_summary(registry: Dict[str, Any]) -> Dict[str, Any]:
    sites = registry.get("sites", []) if isinstance(registry, dict) else []
    monitored = [s for s in sites if isinstance(s, dict) and (s.get("classification") == "monitored" or s.get("is_monitored") is True)]
    ignored = [s for s in sites if isinstance(s, dict) and s.get("classification") == "ignored"]
    pending = [s for s in sites if isinstance(s, dict) and s.get("classification") in ("approval_pending", "pending")]
    discovered = [s for s in sites if isinstance(s, dict) and s.get("classification") == "discovered" and s.get("is_monitored") is not True]
    registry.setdefault("summary", {})
    registry["summary"].update({
        "total_sites": len(sites),
        "monitored_count": len(monitored),
        "discovered_count": len(discovered),
        "ignored_count": len(ignored),
        "pending_onboarding_count": len(pending),
    })
    registry["generated_at_utc"] = now_utc()
    return registry

@app.route("/api/site-review/<path:site_key>/enable-monitoring", methods=["POST"])
def api_site_review_enable_monitoring(site_key):
    payload = request.get_json(silent=True) or {}
    actor = payload.get("actor") or "operator"
    registry = load_json("site_registry.json", {})
    sites = registry.get("sites", []) if isinstance(registry, dict) else []
    target = _normalise_site_key(site_key) if "_normalise_site_key" in globals() else str(site_key).lower()
    site = None
    for item in sites:
        if isinstance(item, dict):
            item_key = str(item.get("site_key") or item.get("key") or item.get("site_name") or item.get("name") or "").lower()
            if item_key == target:
                site = item
                break
    if site is None:
        return jsonify({"ok": False, "error": "site not found", "site_key": site_key}), 404
    decisions = _load_lifecycle_decisions() if "_load_lifecycle_decisions" in globals() else load_json("site_lifecycle_decisions.json", {"decisions": {}, "history": []})
    decision_state = decisions.get("decisions", {}).get(site_key, {})
    if decision_state.get("decision") not in ("approve", "monitored"):
        return jsonify({"ok": False, "error": "site must be approved before monitoring can be enabled", "current_decision": decision_state.get("decision")}), 409
    sources = site.get("sources", []) if isinstance(site.get("sources"), list) else []
    if not sources:
        return jsonify({"ok": False, "error": "site has no source signals to enable", "site_key": site_key}), 409
    now = now_utc()
    site["classification"] = "monitored"
    site["is_monitored"] = True
    site["can_approve"] = False
    site["collector_onboarding_status"] = "enabled_via_jom"
    site["approved_at_utc"] = site.get("approved_at_utc") or now
    site["monitoring_enabled_at_utc"] = now
    site["monitoring_enabled_by"] = actor
    _recalculate_registry_summary(registry)
    write_json(DATA_PATH / "site_registry.json", registry)
    monitored_payload = load_json("monitored_sites.json", {})
    monitored_payload.setdefault("schema", "jom-monitored-sites-v2")
    monitored_payload.setdefault("policy", registry.get("policy", {}))
    monitored_payload.setdefault("monitored_sites", [])
    monitored_payload.setdefault("ignored_sites", [])
    existing = None
    for row in monitored_payload["monitored_sites"]:
        if isinstance(row, dict) and str(row.get("site_key", "")).lower() == target:
            existing = row
            break
    row = {
        "site_key": site.get("site_key") or site_key,
        "site_name": site.get("site_name") or site_key,
        "site_url": site.get("site_url") or site.get("url") or "",
        "status": "monitored",
        "approved_by": actor,
        "approved_at_utc": site.get("approved_at_utc") or now,
        "monitoring_enabled_at_utc": now,
        "collector_onboarding_status": "enabled_via_jom",
    }
    if existing:
        existing.update(row)
    else:
        monitored_payload["monitored_sites"].append(row)
    monitored_payload["ignored_sites"] = [r for r in monitored_payload.get("ignored_sites", []) if not (isinstance(r, dict) and str(r.get("site_key", "")).lower() == target)]
    monitored_payload["updated_at_utc"] = now
    write_json(DATA_PATH / "monitored_sites.json", monitored_payload)
    record = {
        "site_key": site.get("site_key") or site_key,
        "decision": "monitored",
        "previous_decision": decision_state.get("decision"),
        "reason": "monitoring enabled via JOM",
        "actor": actor,
        "decided_at_utc": now,
        "reversible": True,
        "requires_credentials": False,
        "next_state": "monitored",
    }
    decisions.setdefault("decisions", {})[site_key] = record
    decisions.setdefault("history", []).append(record)
    _write_lifecycle_decisions(decisions) if "_write_lifecycle_decisions" in globals() else write_json(DATA_PATH / "site_lifecycle_decisions.json", decisions)
    return jsonify({"ok": True, "message": "Monitoring enabled in JOM configuration. Run runtime refresh to validate live collection.", "site": site, "record": record, "runtime_refresh_required": True})
# --- enable_monitoring_via_jom_v1 END ---

# --- JOM SITE REVIEW LIFECYCLE DECISION ROUTES v1 END ---

@app.route("/review-queue")
def review_queue():
    return render_template("review_queue.html")



@app.route("/estate/review/<site_key>")
def estate_site_review(site_key):
    return render_template("site_review.html", site_key=site_key)

@app.route("/estate/monitored")
def estate_monitored_sites():
    return render_template("estate.html")

@app.route("/estate/discovered")
def estate_discovered_sites():
    return render_template("estate.html")

@app.route("/estate/pending")
def estate_pending_sites():
    return render_template("estate.html")

@app.route("/estate/retired")
def estate_retired_sites():
    return render_template("estate.html")

if __name__ == "__main__":
    app.run(debug=True, port=5000)


