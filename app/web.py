from __future__ import annotations

from flask import Flask, jsonify, render_template, send_from_directory, request, redirect 
import json
import threading
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.runtime.admin_enriched_chain import run_pipeline as run_admin_enriched_pipeline
from app.runtime.operational_source_recovery import run_pipeline as run_recovery
from app.operational.operator_surface import build_alerts, build_operator_surface, build_operator_summary
from app.runtime.runtime_data_paths import runtime_data_path, runtime_read_json, runtime_write_json, runtime_path_status

ROOT = Path(__file__).resolve().parents[1]
app = Flask(
    __name__,
    template_folder=str(ROOT / "templates"),
    static_folder=str(ROOT / "static"),
    static_url_path="/static",
)

DATA_PATH = ROOT / "runtime" / "data"
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


def load_json(filename, default=None):
    return runtime_read_json(filename, default)


# --- JOM LIVE WEBSITE TRUTH POLICY v1 START ---
# Website-facing backend routes must not use legacy/manual retired_record files as truth.
# Runtime-generated/live contracts may be used, but they must remain explicitly labelled
# by the route contract freshness/status logic.
LEGACY_NON_WEBSITE_TRUTH_FILES = {
    "retired_runtime_marker.json",
    "retired_admin_enriched.json",
    "retired_admin_enriched_pretty.json",
    "estate_product_access.json",
    "admin_named_access.json",
    "named_access_truth_v2.json",
}

LIVE_WEBSITE_TRUTH_FILES = {
    "admin_enriched_refresh_status.json",
    "admin_truth_v2.json",
    "backend_final_truth_chain_status.json",
    "backend_final_truth_chain_status.json",
    "estate_access_truth.json",
    "estate_admin_site_inventory_v1.json",
    "estate_discovery_authority_v1.json",
    "estate_product_access.json",
    "organisation_auth_source_audit.json",
    "organisation_discovery.json",
    "runtime_execution_status.json",
    "product_access_refresh_status.json",
    "runtime_execution_history.json",
    "runtime_execution_status.json",
        "site_onboarding_review.json",
    "site_registry.json",
    "source_freshness_audit.json",
    "source_reliability_status.json",
    "user_footprint.json",
}
# --- JOM LIVE WEBSITE TRUTH POLICY v1 END ---

def website_truth_classification(filename: str) -> Dict[str, Any]:
    name = Path(str(filename)).name
    if name in LEGACY_NON_WEBSITE_TRUTH_FILES:
        return {
            "website_truth_allowed": False,
            "truth_class": "blocked_legacy_static_input",
            "reason": "Legacy/manual retired_record inputs must not feed website-facing routes.",
        }
    if name in LIVE_WEBSITE_TRUTH_FILES:
        return {
            "website_truth_allowed": True,
            "truth_class": "live_or_auto_refreshed_truth",
            "reason": "Allowed because this source is live, runtime-generated, or auto-refreshed.",
        }
    return {
        "website_truth_allowed": False,
        "truth_class": "unknown_not_approved_for_website",
        "reason": "Unknown JSON source is blocked until explicitly classified as live or auto-refreshed.",
    }
# --- JOM LIVE WEBSITE TRUTH POLICY v1 END ---
def write_json(path, payload):
    filename = getattr(path, "name", path)
    return runtime_write_json(filename, payload)

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




def _jom_json_safe(value):
    """Convert runtime command payloads into Flask-jsonify-safe values."""
    from pathlib import Path as _Path
    if isinstance(value, _Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jom_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jom_json_safe(item) for item in value]
    return value


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
        return jsonify({"status": "success", "message": f"{action_name} executed", "runtime_status": _jom_json_safe(status_payload), "result": _jom_json_safe(result)})
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
        return jsonify({"status": "error", "message": str(exc), "runtime_status": _jom_json_safe(status_payload)}), 500
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
        "runtime_refresh_status": load_json("admin_enriched_refresh_status.json", {}),
        "runtime_refresh_entry": runtime_status,
        "runtime_refresh_timestamp": runtime_status.get("last_finished_at_utc"),
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



# --- JOM BACKEND ROUTE CONTRACTS v1 START ---
def _contract_parse_time(value: Any):
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _contract_generated_at(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("generated_at_utc") or payload.get("updated_at_utc") or payload.get("collected_at_utc") or "")


def _contract_freshness(payload: Any, current_hours: int = 24, stale_hours: int = 72) -> Dict[str, Any]:
    timestamp = _contract_generated_at(payload)
    parsed = _contract_parse_time(timestamp)
    if not parsed:
        return {"state": "unknown_timestamp", "timestamp": timestamp, "age_hours": None}
    age = round((datetime.now(timezone.utc) - parsed).total_seconds() / 3600, 2)
    if age <= current_hours:
        state = "current"
    elif age <= stale_hours:
        state = "aging"
    else:
        state = "stale"
    return {"state": state, "timestamp": parsed.isoformat().replace("+00:00", "Z"), "age_hours": age}


def _contract_payload(name: str, payload: Any, *, source_file: str, contract_type: str, live_builder: str = "", allow_stale: bool = False) -> Dict[str, Any]:
    website_truth = website_truth_classification(source_file) if source_file else {"website_truth_allowed": True, "truth_class": "live_route", "reason": "Direct live route payload."}
    freshness = _contract_freshness(payload)
    available = isinstance(payload, dict) and bool(payload) and not payload.get("_load_error") and not payload.get("_json_error")
    status = "ok"
    if not available:
        status = "unavailable"
    elif freshness.get("state") == "stale" and not allow_stale:
        status = "stale_generated_cache"
    elif freshness.get("state") == "unknown_timestamp":
        status = "unknown_freshness"
    return {
        "schema": "jom-backend-route-contract-v1",
        "contract_name": name,
        "contract_type": contract_type,
        "served_at_utc": now_utc(),
        "status": status,
        "available": available,
        "source_file": source_file,
        "website_truth": website_truth,
        "source_freshness": freshness,
        "live_builder": live_builder,
        "stale_allowed": bool(allow_stale),
        "notes": [
            "This endpoint is an explicit backend contract.",
            "Generated cache is labelled with freshness and is not silent live truth.",
        ],
        "data": payload if available else {},
    }


def _load_registry_contract() -> Dict[str, Any]:
    try:
        return _build_registry_contract()
    except Exception as exc:
        payload = load_json("site_registry.json", {})
        contract = _contract_payload(
            "site_registry",
            payload,
            source_file="runtime/data/site_registry.json",
            contract_type="generated_cache_fallback_after_builder_error",
            live_builder="app.registry.site_registry_builder.build_registry",
        )
        contract["builder_error"] = str(exc)
        return contract



def _run_registry_builder() -> Dict[str, Any]:
    """Refresh the generated site registry without relying on one fixed function name."""
    import subprocess
    import sys
    script = ROOT / "scripts" / "build_site_registry.py"
    if script.exists():
        proc = subprocess.run(
            [sys.executable, str(script), "--project-root", str(ROOT)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=180,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "site registry builder failed")[-4000:])
        return load_json("site_registry.json", {})

    import app.registry.site_registry_builder as builder
    for name in ("build_registry", "build_site_registry", "build", "generate_registry", "generate_site_registry"):
        candidate = getattr(builder, name, None)
        if callable(candidate):
            try:
                registry = candidate(ROOT)
            except TypeError:
                registry = candidate()
            if isinstance(registry, dict):
                write_json(DATA_PATH / "site_registry.json", registry)
                return registry
    raise RuntimeError("No supported site registry builder entrypoint found.")


def _build_registry_contract() -> Dict[str, Any]:
    registry = _run_registry_builder()
    return _contract_payload(
        "site_registry",
        registry,
        source_file="runtime/data/site_registry.json",
        contract_type="live_builder_generated_cache",
        live_builder="scripts/build_site_registry.py or app.registry.site_registry_builder entrypoint",
    )


def _live_product_access_retired_record() -> Dict[str, Any]:
    """Use the live product-access route as the current product truth."""
    try:
        response = estate_product_access()
        payload = response.get_json() if hasattr(response, "get_json") else None
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        return {
            "schema": "jom-live-product-access-unavailable-v1",
            "status": "unavailable",
            "error": str(exc),
            "served_at_utc": now_utc(),
        }


def _load_admin_truth_contract() -> Dict[str, Any]:
    payload = load_json("admin_truth_v2.json", {})
    contract = _contract_payload(
        "admin_truth_v2",
        payload,
        source_file="runtime/data/admin_truth_v2.json",
        contract_type="generated_cache_contract_with_live_product_access_overlay",
        live_builder="runtime refresh/admin enriched chain plus live /estate/product-access overlay",
    )
    live_product = _live_product_access_retired_record()
    live_summary = live_product.get("summary", {}) if isinstance(live_product, dict) else {}
    cached_summary = ((payload.get("summary") or {}) if isinstance(payload, dict) else {})
    cached_product_users = cached_summary.get("api_product_users")
    live_product_users = live_summary.get("total_jira_product_user_count")
    try:
        delta = int(live_product_users) - int(cached_product_users)
    except Exception:
        delta = None
    alignment = {
        "live_product_access_status": live_product.get("status") if isinstance(live_product, dict) else None,
        "live_accessible_jira_resource_count": live_summary.get("accessible_jira_resource_count"),
        "live_total_jira_product_user_count": live_product_users,
        "cached_admin_truth_api_product_users": cached_product_users,
        "product_user_delta_live_minus_cached": delta,
        "live_product_access_is_primary": True,
    }
    contract["live_product_access_truth"] = live_product
    contract["truth_alignment"] = alignment
    if delta not in (None, 0):
        contract["status"] = "aging_generated_cache_live_product_delta"
        contract.setdefault("notes", []).append(
            "Admin Truth generated cache does not match current live product access. Live product access is primary for website truth."
        )
    return contract


def _load_source_state_contract() -> Dict[str, Any]:
    freshness = load_json("source_freshness_audit.json", {})
    reliability = load_json("source_reliability_status.json", {})
    live_truth = load_json({})
    live_product = _live_product_access_retired_record()
    product_summary = live_product.get("summary", {}) if isinstance(live_product, dict) else {}
    product_truth_status = {
        "schema": "jom-live-product-source-status-v1",
        "served_at_utc": now_utc(),
        "status": live_product.get("status") if isinstance(live_product, dict) else "unavailable",
        "live_collection": bool(live_product.get("live_collection")) if isinstance(live_product, dict) else False,
        "generated_at_utc": live_product.get("generated_at_utc") if isinstance(live_product, dict) else None,
        "accessible_jira_resource_count": product_summary.get("accessible_jira_resource_count"),
        "total_jira_product_user_count": product_summary.get("total_jira_product_user_count"),
        "sites_with_jira_roles": product_summary.get("sites_with_jira_roles"),
        "source_of_truth": "live /estate/product-access endpoint",
    }
    return {
        "schema": "jom-source-state-contract-v3",
        "served_at_utc": now_utc(),
        "source_freshness": _contract_payload("source_freshness", freshness, source_file="runtime/data/source_freshness_audit.json", contract_type="generated_status_cache"),
        "source_reliability": _contract_payload("source_reliability", reliability, source_file="runtime/data/source_reliability_status.json", contract_type="generated_status_cache"),
        "live_product_access": product_truth_status,
        "retired_runtime_record_policy": {
            "retired_runtime_marker_json_is_legacy_reference_only": True,
            "retired_admin_enriched_json_is_legacy_reference_only": True,
            "estate_product_access_json_is_current_authority": True,
            "product_access_static_files_are_cache_only": True,
        },
        "runtime_status": compact_runtime_status(),
        "operator_summary": build_operator_summary(),
        "notes": [
            "Live product access status is reported separately so stale generated retired_records do not override current endpoint truth.",
            "Retired runtime records are explicitly demoted from website truth.",
        ],
    }

def _load_user_footprint_contract() -> Dict[str, Any]:
    payload = load_json("user_footprint.json", {})
    return _contract_payload(
        "user_footprint",
        payload,
        source_file="runtime/data/user_footprint.json",
        contract_type="generated_cache_contract",
        live_builder="runtime refresh/admin enriched chain",
    )


# --- JOM BACKEND ROUTE CONTRACTS v1 END ---




@app.route("/")
def home():
    """Fast render route: page shell only; data loads through workspace contracts."""
    return render_template("home.html")
@app.route("/admin/truth")
def admin_truth():
    return jsonify(_load_admin_truth_contract())


@app.route("/estate/product-access")
def estate_product_access():
    """Return current live product-access truth.

    This route is website-facing and must not silently serve stale static
    retired_records. It attempts live collection every time it is requested, writes
    the resulting generated cache for freshness/audit visibility, and returns
    the same live payload to the caller. If live collection fails, the response
    exposes the live error instead of falling back to old static JSON.
    """
    try:
        from app.builders.estate_product_access import collect_product_access, build_access_truth
        product_payload = collect_product_access()
        if isinstance(product_payload, dict):
            product_payload["live_endpoint"] = True
            product_payload["served_at_utc"] = now_utc()
        write_json(DATA_PATH / "estate_product_access.json", product_payload)
        try:
            admin_path = DATA_PATH / "admin_truth_v2.json"
            truth_payload = build_access_truth(
                product_payload,
                admin_path,
                DATA_PATH / "estate_access_truth.json",
            )
            if isinstance(truth_payload, dict):
                truth_payload["live_endpoint"] = True
                truth_payload["served_at_utc"] = now_utc()
            write_json(DATA_PATH / "estate_access_truth.json", truth_payload)
        except Exception as truth_exc:
            if isinstance(product_payload, dict):
                product_payload.setdefault("warnings", []).append(
                    "estate access truth refresh failed: " + str(truth_exc)
                )
        return jsonify(product_payload)
    except Exception as exc:
        return jsonify({
            "schema": "jom-live-product-access-error-v1",
            "live_endpoint": True,
            "served_at_utc": now_utc(),
            "status": "error",
            "error": str(exc),
            "sites": [],
            "roles": [],
            "notes": [
                "Live product-access collection failed.",
                "No stale static product-access data was used as a website fallback."
            ],
        }), 500


@app.route("/users/footprint")
def user_footprint():
    return jsonify(_load_user_footprint_contract())


@app.route("/registry/sites")
def site_registry():
    return jsonify(_load_registry_contract())


@app.route("/runtime/status")
def runtime_status():
    return jsonify(compact_runtime_status())


@app.route("/runtime/history")
def runtime_history():
    return jsonify(read_runtime_history())


@app.route("/runtime/refresh")
def runtime_refresh():
    return execute_guarded("refresh", run_admin_enriched_pipeline)


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
    """Fast render route: page shell only; data loads through workspace contracts."""
    return render_template("home.html")
@app.route("/estate")
def page_estate():
    """Fast render route: page shell only; data loads through workspace contracts."""
    return render_template("estate.html")
@app.route("/reference")
def page_reference():
    return redirect("/", code=302)


# JOM_SITE_WORKSPACE_SHELL_ROUTES_V1 START

# JOM_SITE_WORKSPACE_PRODUCT_USERS_PACK_V1 START
@app.route("/api/workspace/product-users")
def api_workspace_product_users_v1():
    from app.builders.site_workspace_product_users_builder import build_site_workspace_product_users
    return jsonify(build_site_workspace_product_users(ROOT))
# JOM_SITE_WORKSPACE_PRODUCT_USERS_PACK_V1 END



# --- JOM_ADMIN_LICENSING_BILLING_AUTHORITY_V1 START ---
# Owner contract for Admin > Licensing & Billing.
# Truth rule: OAuth/Admin-backed runtime authority only. Commercial billing fields remain unavailable unless proven by authority.
def _jom_admin_lb_int_v1(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default

def _jom_admin_lb_list_v1(value):
    return value if isinstance(value, list) else []

def _jom_admin_lb_dict_v1(value):
    return value if isinstance(value, dict) else {}

def _jom_admin_lb_key_v1(row):
    if not isinstance(row, dict):
        return ""
    for field in ("site_key", "key", "site_name", "name", "site_url", "url", "cloud_id"):
        value = row.get(field)
        if value:
            text = str(value).strip().lower()
            if text.startswith("http") and ".atlassian.net" in text:
                text = text.split("//", 1)[-1].split(".atlassian.net", 1)[0]
            return text.rstrip("/")
    return ""

def _jom_admin_lb_is_monitored_v1(row):
    if not isinstance(row, dict):
        return False
    state = str(row.get("classification") or row.get("lifecycle") or row.get("collector_onboarding_status") or row.get("status") or "").strip().lower()
    return bool(row.get("is_monitored") is True or row.get("monitored") is True or row.get("approved_monitored") is True or state in {"monitored", "monitoring_enabled"})

def _jom_admin_lb_source_health_v1(label, payload):
    if isinstance(payload, dict) and payload:
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        status = payload.get("status") or payload.get("overall_status") or summary.get("overall_state") or "available"
        return {"label": label, "available": True, "status": status, "generated_at_utc": payload.get("generated_at_utc") or payload.get("served_at_utc") or payload.get("updated_at_utc")}
    return {"label": label, "available": False, "status": "unavailable", "generated_at_utc": None}

def _jom_admin_lb_products_v1(product_access):
    roles = _jom_admin_lb_list_v1(product_access.get("roles"))
    by_product = {}
    for row in roles:
        if not isinstance(row, dict):
            continue
        name = str(row.get("role_name") or row.get("role_key") or row.get("product") or "Atlassian product").strip() or "Atlassian product"
        rec = by_product.setdefault(name, {"product": name, "users": 0, "seat_limit": 0, "remaining_seats": 0, "role_rows": 0, "status": "ok", "authority": "OAuth application role"})
        rec["users"] += _jom_admin_lb_int_v1(row.get("user_count") or row.get("jira_product_user_count"), 0)
        rec["seat_limit"] += _jom_admin_lb_int_v1(row.get("seat_limit") or row.get("jira_product_seat_limit"), 0)
        rec["remaining_seats"] += _jom_admin_lb_int_v1(row.get("remaining_seats") or row.get("jira_product_remaining_seats"), 0)
        rec["role_rows"] += 1
    return sorted(by_product.values(), key=lambda item: (-item.get("users", 0), item.get("product", "")))

def _jom_admin_lb_sites_v1(product_access, registry):
    product_sites = _jom_admin_lb_list_v1(product_access.get("sites"))
    registry_sites = _jom_admin_lb_list_v1(registry.get("sites"))
    monitored_keys = {_jom_admin_lb_key_v1(row) for row in registry_sites if _jom_admin_lb_is_monitored_v1(row)}
    if not monitored_keys:
        monitored_keys = {_jom_admin_lb_key_v1(row) for row in product_sites if _jom_admin_lb_key_v1(row)}
    out = []
    for row in product_sites:
        if not isinstance(row, dict):
            continue
        key = _jom_admin_lb_key_v1(row)
        if monitored_keys and key and key not in monitored_keys:
            continue
        users = _jom_admin_lb_int_v1(row.get("jira_product_user_count"), 0)
        seat_limit = _jom_admin_lb_int_v1(row.get("jira_product_seat_limit"), 0)
        remaining = _jom_admin_lb_int_v1(row.get("jira_product_remaining_seats"), 0)
        out.append({
            "site_key": key,
            "site_name": row.get("site_name") or row.get("name") or key,
            "site_url": row.get("site_url") or row.get("url") or "",
            "cloud_id": row.get("cloud_id"),
            "product_users": users,
            "seat_limit": seat_limit if seat_limit else None,
            "remaining_seats": remaining if seat_limit else None,
            "role_count": _jom_admin_lb_int_v1(row.get("jira_role_count"), 0),
            "status": row.get("status") or "ok",
            "authority": "OAuth application role",
        })
    return sorted(out, key=lambda item: (-_jom_admin_lb_int_v1(item.get("product_users"), 0), item.get("site_key") or ""))

def _jom_admin_lb_actions_v1(authority, estate, sites, products, admin_contacts, source_health):
    actions = []
    if authority.get("commercial_billing") == "unavailable":
        actions.append({
            "level": "info",
            "title": "Commercial billing authority unavailable",
            "reason": "Current OAuth/Admin authority does not prove invoice, payment method, renewal date, or commercial contract values.",
            "action": "Keep commercial billing fields unavailable until a proven billing authority source is added.",
            "source": "truth_policy",
        })
    if estate.get("product_users") is None:
        actions.append({"level": "review", "title": "Product user authority unavailable", "reason": "No product access total was available from the current authority contract.", "action": "Refresh product access authority and source health before reporting licensing totals.", "source": "estate_product_access"})
    low_capacity = []
    for site in sites:
        limit = site.get("seat_limit")
        rem = site.get("remaining_seats")
        if isinstance(limit, int) and limit > 0 and isinstance(rem, int) and rem <= max(5, round(limit * 0.1)):
            low_capacity.append(site)
    if low_capacity:
        actions.append({"level": "warning", "title": "Seat capacity review required", "reason": str(len(low_capacity)) + " site(s) are near exposed seat capacity.", "action": "Review product allocation and licence capacity for the affected site(s).", "source": "estate_product_access"})
    if admin_contacts.get("status") in {"unavailable", "available_no_contacts_mapped"}:
        actions.append({"level": "review", "title": "Admin ownership evidence incomplete", "reason": admin_contacts.get("reason") or "No mapped admin contacts were available.", "action": "Review Admin authority and role-assignment coverage.", "source": "estate_admin_contacts"})
    for key, item in source_health.items():
        if isinstance(item, dict) and item.get("status") in {"critical", "failed", "unavailable"}:
            actions.append({"level": "review", "title": "Source health requires review", "reason": (item.get("label") or key) + " is " + str(item.get("status")), "action": "Open Source Health and refresh the affected authority source.", "source": key})
    return actions[:8]

def _jom_admin_licensing_billing_contract_v1():
    registry = load_json("site_registry.json", {})
    product_access = load_json("estate_product_access.json", {})
    org_discovery = load_json("organisation_discovery.json", {})
    admin_truth = load_json("admin_truth_v2.json", {})
    admin_contacts = load_json("estate_admin_contacts_v1.json", {})
    source_freshness = load_json("source_freshness_audit.json", {})
    source_reliability = load_json("source_reliability_status.json", {})
    product_refresh = load_json("product_access_refresh_status.json", {})

    registry = _jom_admin_lb_dict_v1(registry)
    product_access = _jom_admin_lb_dict_v1(product_access)
    org_discovery = _jom_admin_lb_dict_v1(org_discovery)
    admin_truth = _jom_admin_lb_dict_v1(admin_truth)
    admin_contacts = _jom_admin_lb_dict_v1(admin_contacts)

    registry_sites = _jom_admin_lb_list_v1(registry.get("sites"))
    monitored_sites = [row for row in registry_sites if _jom_admin_lb_is_monitored_v1(row)]
    product_summary = _jom_admin_lb_dict_v1(product_access.get("summary"))
    products = _jom_admin_lb_products_v1(product_access)
    sites = _jom_admin_lb_sites_v1(product_access, registry)
    contacts = _jom_admin_lb_list_v1(admin_contacts.get("contacts"))
    org_count = org_discovery.get("organisation_count")
    if org_count is None:
        orgs = org_discovery.get("organisations")
        org_count = len(orgs) if isinstance(orgs, list) else None

    authority = {
        "oauth": "live" if product_access.get("live_collection") is True or product_access.get("status") in {"ok", "partial"} else "unavailable",
        "admin": "live" if org_discovery.get("live_collection") is True or admin_contacts.get("status") in {"live", "available_no_contacts_mapped"} else "unavailable",
        "commercial_billing": "unavailable",
        "truth_policy": "OAuth/Admin authority only. Unproven commercial billing remains unavailable.",
    }
    estate = {
        "organisations": org_count,
        "monitored_sites": len(monitored_sites) if monitored_sites else len(sites),
        "product_users": product_summary.get("total_jira_product_user_count"),
        "seat_limit": product_summary.get("total_jira_seat_limit") if product_summary.get("total_jira_seat_limit") else None,
        "remaining_seats": product_summary.get("total_jira_remaining_seats") if product_summary.get("total_jira_seat_limit") else None,
        "role_rows": product_summary.get("jira_role_rows") or len(_jom_admin_lb_list_v1(product_access.get("roles"))),
        "accessible_jira_resources": product_summary.get("accessible_jira_resource_count"),
    }
    source_health = {
        "source_freshness": _jom_admin_lb_source_health_v1("Source freshness", source_freshness),
        "source_reliability": _jom_admin_lb_source_health_v1("Source reliability", source_reliability),
        "product_access_refresh": _jom_admin_lb_source_health_v1("Product access refresh", product_refresh),
    }
    admin_contact_payload = {
        "status": admin_contacts.get("status") or "unavailable",
        "reason": admin_contacts.get("reason") or "Admin contact authority has not returned mapped contacts.",
        "contact_count": len(contacts),
        "contacts": contacts[:25],
        "summary": admin_contacts.get("summary") if isinstance(admin_contacts.get("summary"), dict) else {},
        "authority": admin_contacts.get("source") or "atlassian_admin_role_assignments",
    }
    billing_evidence = {
        "invoice_data": "unavailable",
        "payment_methods": "unavailable",
        "renewal_dates": "unavailable",
        "commercial_contract": "unavailable",
        "billing_account": "unavailable",
        "reason": "Current OAuth/Admin authority does not prove invoice, payment method, renewal date, billing account, or commercial contract values.",
        "future_authority_required": ["Billing admin API/export", "Invoice export", "Billing account authority", "Approved manual upload workflow"],
    }
    return {
        "schema": "jom-admin-licensing-billing-authority-v1",
        "generated_at_utc": now_utc(),
        "status": "ok" if authority.get("oauth") == "live" else "review",
        "authority": authority,
        "estate": estate,
        "actions": _jom_admin_lb_actions_v1(authority, estate, sites, products, admin_contact_payload, source_health),
        "products": products,
        "sites": sites,
        "admin_contacts": admin_contact_payload,
        "billing_evidence": billing_evidence,
        "source_health": source_health,
        "source_files": {
            "site_registry": "runtime/data/site_registry.json",
            "estate_product_access": "runtime/data/estate_product_access.json",
            "organisation_discovery": "runtime/data/organisation_discovery.json",
            "estate_admin_contacts": "runtime/data/estate_admin_contacts_v1.json",
            "admin_truth": "runtime/data/admin_truth_v2.json",
        },
        "notes": [
            "Product access and seat values are shown only when exposed by OAuth/Admin authority.",
            "Commercial billing facts are unavailable until a proven billing authority source exists.",
            "No static billing data, no estimates, and no inferred commercial values are used.",
        ],
    }

@app.route("/api/admin/licensing-billing")
def api_admin_licensing_billing_authority_v1():
    return jsonify(_jom_admin_licensing_billing_contract_v1())
# --- JOM_ADMIN_LICENSING_BILLING_AUTHORITY_V1 END ---


# --- JOM_ADMIN_USERS_ACCESS_AUTHORITY_V1 START ---
# Owner contract for Admin > Users & Access.
# Truth rule: active-user truth stays unavailable unless OAuth/Admin authority proves unique active users.
def _jom_admin_ua_int_v1(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default

def _jom_admin_ua_list_v1(value):
    return value if isinstance(value, list) else []

def _jom_admin_ua_dict_v1(value):
    return value if isinstance(value, dict) else {}

def _jom_admin_ua_key_v1(row):
    if not isinstance(row, dict):
        return ""
    for field in ("site_key", "key", "site_name", "name", "site_url", "url", "cloud_id"):
        value = row.get(field)
        if value:
            text = str(value).strip().lower()
            if text.startswith("http") and ".atlassian.net" in text:
                text = text.split("//", 1)[-1].split(".atlassian.net", 1)[0]
            return text.rstrip("/")
    return ""

def _jom_admin_ua_name_v1(row):
    if not isinstance(row, dict):
        return "Unknown"
    return row.get("site_name") or row.get("name") or row.get("site_key") or row.get("key") or "Unknown"

def _jom_admin_ua_is_monitored_v1(row):
    if not isinstance(row, dict):
        return False
    state = str(row.get("classification") or row.get("lifecycle") or row.get("collector_onboarding_status") or row.get("status") or "").strip().lower()
    return bool(row.get("is_monitored") is True or row.get("monitored") is True or row.get("approved_monitored") is True or state in {"monitored", "monitoring_enabled"})

def _jom_admin_ua_user_records_v1(payload):
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("users", "items", "records", "entries", "accounts", "data", "results", "members"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []

def _jom_admin_ua_products_v1(product_access, registry):
    registry_sites = _jom_admin_ua_list_v1(registry.get("sites"))
    monitored = {_jom_admin_ua_key_v1(row) for row in registry_sites if _jom_admin_ua_is_monitored_v1(row)}
    sites = []
    for row in _jom_admin_ua_list_v1(product_access.get("sites")):
        if not isinstance(row, dict):
            continue
        key = _jom_admin_ua_key_v1(row)
        if monitored and key not in monitored:
            continue
        sites.append({
            "site_key": key,
            "site_name": _jom_admin_ua_name_v1(row),
            "product_users": _jom_admin_ua_int_v1(row.get("jira_product_user_count"), 0),
            "role_count": _jom_admin_ua_int_v1(row.get("jira_role_count"), 0),
            "status": row.get("status") or "ok",
            "authority": "OAuth application role",
        })
    return sorted(sites, key=lambda item: (-item.get("product_users", 0), item.get("site_key") or ""))

def _jom_admin_ua_source_health_v1(label, payload):
    if isinstance(payload, dict) and payload:
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        status = payload.get("status") or payload.get("overall_status") or summary.get("overall_state") or "available"
        return {"label": label, "available": True, "status": status, "generated_at_utc": payload.get("generated_at_utc") or payload.get("served_at_utc") or payload.get("updated_at_utc")}
    return {"label": label, "available": False, "status": "unavailable", "generated_at_utc": None}

def _jom_admin_ua_actions_v1(authority, summary, source_health):
    actions = []
    if authority.get("active_user_authority") == "unavailable":
        actions.append({
            "level": "review",
            "title": "Active-user authority unavailable",
            "reason": "Current OAuth/Admin sources do not prove unique active users. Product-access assignments are shown separately.",
            "action": "Keep headline active users unavailable until a proven active-user authority source exists.",
            "source": "users_metric_contract",
        })
    if summary.get("product_access_assignments") is None:
        actions.append({"level": "review", "title": "Product-access assignments unavailable", "reason": "No product access assignment total was available from authority.", "action": "Refresh product access authority before reporting access allocation.", "source": "estate_product_access"})
    for key, item in source_health.items():
        if isinstance(item, dict) and item.get("status") in {"critical", "failed", "unavailable"}:
            actions.append({"level": "review", "title": "Source health requires review", "reason": (item.get("label") or key) + " is " + str(item.get("status")), "action": "Open Source Health and refresh the affected authority source.", "source": key})
    return actions[:8]

def _jom_admin_users_access_contract_v1():
    registry = _jom_admin_ua_dict_v1(load_json("site_registry.json", {}))
    product_access = _jom_admin_ua_dict_v1(load_json("estate_product_access.json", {}))
    user_footprint = load_json("user_footprint.json", {})
    admin_insights = _jom_admin_ua_dict_v1(load_json("admin_insights.json", {}))
    admin_truth = _jom_admin_ua_dict_v1(load_json("admin_truth_v2.json", {}))
    source_freshness = load_json("source_freshness_audit.json", {})
    source_reliability = load_json("source_reliability_status.json", {})
    product_refresh = load_json("product_access_refresh_status.json", {})

    registry_sites = _jom_admin_ua_list_v1(registry.get("sites"))
    monitored_sites = [row for row in registry_sites if _jom_admin_ua_is_monitored_v1(row)]
    product_summary = _jom_admin_ua_dict_v1(product_access.get("summary"))
    footprint_records = _jom_admin_ua_user_records_v1(user_footprint)
    insights_summary = _jom_admin_ua_dict_v1(admin_insights.get("summary"))
    capabilities = _jom_admin_ua_dict_v1(admin_insights.get("capabilities"))
    product_sites = _jom_admin_ua_products_v1(product_access, registry)
    role_rows = _jom_admin_ua_list_v1(product_access.get("roles"))

    admin_identity = _jom_admin_ua_dict_v1(admin_truth.get("admin_identity"))
    admin_controls = _jom_admin_ua_dict_v1(admin_truth.get("controls"))
    identity_source_fields = _jom_admin_ua_dict_v1(admin_identity.get("source_fields"))
    account_authority_available = bool(
        admin_identity.get("payload_available") is True
        and identity_source_fields.get("pagination_complete") is True
        and identity_source_fields.get("privacy_minimised") is True
    )

    def account_value(field):
        if not account_authority_available or admin_identity.get(field) is None:
            return None
        return _jom_admin_ua_int_v1(admin_identity.get(field), 0)

    account_authority = {
        "available": account_authority_available,
        "status": "live" if account_authority_available else "unavailable",
        "authority": "Atlassian Admin Organizations API via Admin Truth",
        "source_file": "runtime/data/admin_truth_v2.json",
        "pagination_complete": identity_source_fields.get("pagination_complete") is True,
        "privacy_minimised": identity_source_fields.get("privacy_minimised") is True,
        "directory_count": identity_source_fields.get("directory_count"),
        "page_count": identity_source_fields.get("page_count"),
        "named_user_footprint_visible": admin_controls.get("named_user_footprint_visible") is True,
        "safe_to_show_named_site_access": admin_controls.get("safe_to_show_named_site_access") is True,
        "fields": {
            "org_users": account_value("org_users"),
            "managed_users": account_value("managed_users"),
            "human_users": account_value("human_users"),
            "app_accounts": account_value("app_accounts"),
            "suspended_users": account_value("suspended_users"),
            "mfa_enabled": account_value("mfa_enabled"),
            "mfa_disabled": account_value("mfa_disabled"),
            "mfa_unknown": account_value("mfa_unknown"),
            "platform_role_assignments": account_value("platform_role_assignments"),
        },
    }

    active_user_authority_available = False
    summary = {
        "monitored_sites": len(monitored_sites) if monitored_sites else len(product_sites),
        "active_users": None,
        "active_users_display": "Unavailable",
        "org_users": account_authority["fields"]["org_users"],
        "managed_users": account_authority["fields"]["managed_users"],
        "human_users": account_authority["fields"]["human_users"],
        "app_accounts": account_authority["fields"]["app_accounts"],
        "suspended_users": account_authority["fields"]["suspended_users"],
        "mfa_enabled": account_authority["fields"]["mfa_enabled"],
        "mfa_disabled": account_authority["fields"]["mfa_disabled"],
        "mfa_unknown": account_authority["fields"]["mfa_unknown"],
        "platform_role_assignments": account_authority["fields"]["platform_role_assignments"],
        "product_access_assignments": product_summary.get("total_jira_product_user_count"),
        "role_rows": product_summary.get("jira_role_rows") or len(role_rows),
        "footprint_records": len(footprint_records) if footprint_records else insights_summary.get("user_records_evaluated"),
        "issue_count": insights_summary.get("total_issues"),
        "critical_count": insights_summary.get("critical"),
        "risk_count": insights_summary.get("risk"),
        "waste_count": insights_summary.get("waste"),
        "drift_count": insights_summary.get("drift"),
    }
    authority = {
        "oauth": "live" if product_access.get("live_collection") is True or product_access.get("status") in {"ok", "partial"} else "unavailable",
        "admin": "live" if account_authority_available else ("available" if admin_insights else "unavailable"),
        "account_authority": "live" if account_authority_available else "unavailable",
        "active_user_authority": "live" if active_user_authority_available else "unavailable",
        "product_access_authority": "live" if product_access.get("status") in {"ok", "partial"} or product_access.get("live_collection") is True else "unavailable",
        "truth_policy": "Organisation account authority is separate from active-user authority. Active users require proven activity evidence; product-access assignments are separate and must not be labelled as active users.",
    }
    source_health = {
        "admin_truth": _jom_admin_ua_source_health_v1("Admin Truth account authority", admin_truth),
        "source_freshness": _jom_admin_ua_source_health_v1("Source freshness", source_freshness),
        "source_reliability": _jom_admin_ua_source_health_v1("Source reliability", source_reliability),
        "product_access_refresh": _jom_admin_ua_source_health_v1("Product access refresh", product_refresh),
    }
    return {
        "schema": "jom-admin-users-access-authority-v1",
        "generated_at_utc": now_utc(),
        "status": "ok" if authority.get("product_access_authority") == "live" and authority.get("account_authority") == "live" else "review",
        "authority": authority,
        "account_authority": account_authority,
        "summary": summary,
        "actions": _jom_admin_ua_actions_v1(authority, summary, source_health),
        "site_access": product_sites,
        "capabilities": capabilities,
        "source_health": source_health,
        "source_files": {
            "site_registry": "runtime/data/site_registry.json",
            "estate_product_access": "runtime/data/estate_product_access.json",
            "user_footprint": "runtime/data/user_footprint.json",
            "admin_insights": "runtime/data/admin_insights.json",
            "admin_truth": "runtime/data/admin_truth_v2.json",
        },
        "notes": [
            "Organisation account totals are sourced from privacy-minimised, fully paginated Admin Truth authority.",
            "Headline active users remain unavailable because account status does not prove activity.",
            "Product-access assignments are shown separately and are not labelled as active users.",
            "Names, email addresses, account IDs, and raw Directory records are not exposed by this contract.",
            "Named per-site access remains hidden until resource-level entitlement mapping is proven.",
        ],
    }

@app.route("/api/admin/users-access")
def api_admin_users_access_authority_v1():
    return jsonify(_jom_admin_users_access_contract_v1())
# --- JOM_ADMIN_USERS_ACCESS_AUTHORITY_V1 END ---


# --- JOM_ADMIN_MONITORING_AUTHORITY_V1 START ---
# Owner contract for Admin > Monitoring.
# Truth rule: runtime/OAuth/Admin authority only. Monitoring health is unavailable/review when not proven.
def _jom_admin_mon_int_v1(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default

def _jom_admin_mon_list_v1(value):
    return value if isinstance(value, list) else []

def _jom_admin_mon_dict_v1(value):
    return value if isinstance(value, dict) else {}

def _jom_admin_mon_key_v1(row):
    if not isinstance(row, dict):
        return ""
    for field in ("site_key", "key", "site_name", "name", "site_url", "url", "cloud_id"):
        value = row.get(field)
        if value:
            text = str(value).strip().lower()
            if text.startswith("http") and ".atlassian.net" in text:
                text = text.split("//", 1)[-1].split(".atlassian.net", 1)[0]
            return text.rstrip("/")
    return ""

def _jom_admin_mon_name_v1(row):
    if not isinstance(row, dict):
        return "Unknown"
    return row.get("site_name") or row.get("name") or row.get("site_key") or row.get("key") or "Unknown"

def _jom_admin_mon_is_monitored_v1(row):
    if not isinstance(row, dict):
        return False
    state = str(row.get("classification") or row.get("lifecycle") or row.get("collector_onboarding_status") or row.get("status") or "").strip().lower()
    return bool(row.get("is_monitored") is True or row.get("monitored") is True or row.get("approved_monitored") is True or state in {"monitored", "monitoring_enabled"} or "monitoring enabled" in state)

def _jom_admin_mon_health_v1(label, payload):
    if isinstance(payload, dict) and payload:
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        status = payload.get("status") or payload.get("overall_status") or payload.get("overall_state") or summary.get("overall_state") or summary.get("status") or "available"
        return {"label": label, "available": True, "status": status, "generated_at_utc": payload.get("generated_at_utc") or payload.get("served_at_utc") or payload.get("updated_at_utc")}
    return {"label": label, "available": False, "status": "unavailable", "generated_at_utc": None}


def _jom_admin_mon_refresh_product_access_v1():
    """Refresh Product Access before serving Monitoring.

    Monitoring uses Product Access status as live operational authority. This prevents
    stale product_access_refresh_status.json from reporting failed when the live
    product-access collector is healthy.
    """
    result = {"attempted": True, "product_access_refresh": "not_run", "errors": []}
    try:
        from app.builders import product_access_sources
        product_access_sources.main()
        result["product_access_refresh"] = "ok"
    except Exception as exc:
        result["product_access_refresh"] = "failed"
        result["errors"].append("product_access_refresh: " + str(exc))
    return result


def _jom_admin_mon_refresh_source_health_v1():
    """Refresh Monitoring source-health audit files before building the API contract.

    Monitoring must reflect current runtime authority without requiring operators to run
    separate freshness/reliability commands after OAuth or runtime recovery.
    This refresh only rebuilds source-health audit artefacts; it does not collect OAuth,
    Admin, or site data.
    """
    result = {"attempted": True, "source_freshness": "not_run", "source_reliability": "not_run", "errors": []}
    try:
        from app.audits import source_freshness
        source_freshness.main()
        result["source_freshness"] = "ok"
    except Exception as exc:
        result["source_freshness"] = "failed"
        result["errors"].append("source_freshness: " + str(exc))
    try:
        from app.audits import source_reliability
        source_reliability.main()
        result["source_reliability"] = "ok"
    except Exception as exc:
        result["source_reliability"] = "failed"
        result["errors"].append("source_reliability: " + str(exc))
    return result



def _jom_admin_mon_refresh_runtime_inputs_v1():
    """Refresh runtime inputs needed by Monitoring before source-health audits run."""
    result = {"attempted": True, "admin_enriched": "not_run", "errors": []}
    try:
        from app.runtime import admin_enriched_chain
        admin_enriched_chain.main()
        result["admin_enriched"] = "ok"
    except Exception as exc:
        result["admin_enriched"] = "failed"
        result["errors"].append("admin_enriched: " + str(exc))
    return result


def _jom_admin_mon_refresh_named_access_v1():
    """Refresh group expansion, named access truth, reconciliation, and user footprint."""
    result = {
        "attempted": True,
        "group_expansion": "not_run",
        "named_access_truth": "not_run",
        "named_access_reconciliation": "not_run",
        "user_footprint": "not_run",
        "errors": [],
    }
    steps = [
        ("group_expansion", "app.access.collect_admin_group_expansion", "main"),
        ("named_access_truth", "app.access.named_access_truth_v2", "main"),
        ("named_access_reconciliation", "app.access.reconcile_named_access_truth_v2", "main"),
        ("user_footprint", "app.access.user_footprint_source", "main"),
    ]
    for key, module_name, function_name in steps:
        try:
            module = __import__(module_name, fromlist=[function_name])
            getattr(module, function_name)()
            result[key] = "ok"
        except Exception as exc:
            result[key] = "failed"
            result["errors"].append(key + ": " + str(exc))
    return result



def _jom_admin_mon_write_runtime_execution_status_v1(runtime_inputs_refresh, product_access_refresh, named_access_refresh, source_health_refresh=None):
    """Write current runtime execution status for the Monitoring API preflight run."""
    now = now_utc()
    payload = {
        "schema": "jom-runtime-execution-status-v1-monitoring-preflight",
        "generated_at_utc": now,
        "state": "idle",
        "running": False,
        "last_action": "monitoring_api_preflight_refresh",
        "last_started_at_utc": now,
        "last_finished_at_utc": now,
        "last_result_status": "ok",
        "last_error": None,
        "last_result": {
            "runtime_inputs_refresh": runtime_inputs_refresh,
            "product_access_refresh": product_access_refresh,
            "named_access_refresh": named_access_refresh,
            "source_health_refresh": source_health_refresh or {},
        },
    }
    try:
        path = Path(__file__).resolve().parents[1] / "runtime" / "data" / "runtime_execution_status.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"attempted": True, "status": "ok", "output": "runtime/data/runtime_execution_status.json"}
    except Exception as exc:
        return {"attempted": True, "status": "failed", "error": str(exc)}

def _jom_admin_mon_product_map_v1(product_access):
    out = {}
    for row in _jom_admin_mon_list_v1(product_access.get("sites")):
        if not isinstance(row, dict):
            continue
        key = _jom_admin_mon_key_v1(row)
        if key:
            out[key] = row
    return out

def _jom_admin_mon_site_rows_v1(registry, product_access):
    product_by_key = _jom_admin_mon_product_map_v1(product_access)
    rows = []
    for row in _jom_admin_mon_list_v1(registry.get("sites")):
        if not isinstance(row, dict) or not _jom_admin_mon_is_monitored_v1(row):
            continue
        key = _jom_admin_mon_key_v1(row)
        product = product_by_key.get(key, {})
        rows.append({
            "site_key": key,
            "site_name": _jom_admin_mon_name_v1(row),
            "monitoring": "enabled",
            "product_access_status": product.get("status") or ("unavailable" if not product else "ok"),
            "product_users": product.get("jira_product_user_count") if isinstance(product, dict) else None,
            "role_count": product.get("jira_role_count") if isinstance(product, dict) else None,
            "authority": "runtime site registry + OAuth product access",
        })
    if not rows:
        for row in _jom_admin_mon_list_v1(product_access.get("sites")):
            if not isinstance(row, dict):
                continue
            rows.append({
                "site_key": _jom_admin_mon_key_v1(row),
                "site_name": _jom_admin_mon_name_v1(row),
                "monitoring": "unproven",
                "product_access_status": row.get("status") or "ok",
                "product_users": row.get("jira_product_user_count"),
                "role_count": row.get("jira_role_count"),
                "authority": "OAuth product access; monitored registry row unavailable",
            })
    return sorted(rows, key=lambda item: item.get("site_key") or "")

def _jom_admin_mon_actions_v1(summary, source_health, site_rows):
    actions = []
    if summary.get("monitoring_coverage_percent") is None:
        actions.append({"level": "review", "title": "Monitoring coverage unavailable", "reason": "Site registry authority did not expose enough monitored-site scope to prove coverage.", "action": "Refresh registry authority and validate monitored-site lifecycle state.", "source": "site_registry"})
    elif summary.get("monitoring_coverage_percent") < 100:
        actions.append({"level": "review", "title": "Monitoring coverage below 100%", "reason": str(summary.get("monitored_sites")) + " of " + str(summary.get("total_sites")) + " sites are monitored.", "action": "Review Estate lifecycle and approve or remove outstanding sites.", "source": "site_registry"})
    failed = []
    for key, item in source_health.items():
        if isinstance(item, dict) and str(item.get("status") or "").lower() in {"failed", "error", "critical", "unavailable"}:
            failed.append(item.get("label") or key)
    if failed:
        actions.append({"level": "review", "title": "Monitoring source health requires review", "reason": ", ".join(failed) + " requires attention.", "action": "Open Source Health and refresh the failed source(s).", "source": "source_health"})
    unavailable_sites = [row for row in site_rows if row.get("product_access_status") in {"unavailable", "error", "failed"}]
    if unavailable_sites:
        actions.append({"level": "review", "title": "Product access monitoring gaps", "reason": str(len(unavailable_sites)) + " monitored site(s) have unavailable or failed product-access status.", "action": "Refresh product access and review site-level authority coverage.", "source": "estate_product_access"})
    if not actions:
        actions.append({"level": "ok", "title": "No immediate monitoring actions", "reason": "Current monitoring authority did not report priority action items.", "action": "Continue routine monitoring and source freshness checks.", "source": "admin_monitoring"})
    return actions[:8]

def _jom_admin_monitoring_contract_v1():
    refresh_status = _jom_admin_mon_background_status_v1()
    registry = _jom_admin_mon_dict_v1(load_json("site_registry.json", {}))
    product_access = _jom_admin_mon_dict_v1(load_json("estate_product_access.json", {}))
    source_freshness = load_json("source_freshness_audit.json", {})
    source_reliability = load_json("source_reliability_status.json", {})
    product_refresh = load_json("product_access_refresh_status.json", {})
    runtime_status = load_json("runtime_execution_status.json", {})

    registry_sites = _jom_admin_mon_list_v1(registry.get("sites"))
    monitored_sites = [row for row in registry_sites if _jom_admin_mon_is_monitored_v1(row)]
    registry_summary = _jom_admin_mon_dict_v1(registry.get("summary"))
    total_sites = registry_summary.get("total_sites") or registry_summary.get("site_count") or len(registry_sites)
    monitored_count = registry_summary.get("monitored_count") or len(monitored_sites)
    coverage = round((float(monitored_count) / float(total_sites)) * 100) if total_sites else None
    product_summary = _jom_admin_mon_dict_v1(product_access.get("summary"))
    site_rows = _jom_admin_mon_site_rows_v1(registry, product_access)
    source_health = {
        "source_freshness": _jom_admin_mon_health_v1("Source freshness", source_freshness),
        "source_reliability": _jom_admin_mon_health_v1("Source reliability", source_reliability),
        "product_access_refresh": _jom_admin_mon_health_v1("Product access refresh", product_refresh),
        "runtime_execution": _jom_admin_mon_health_v1("Runtime execution", runtime_status),
    }
    failed_sources = [key for key, item in source_health.items() if isinstance(item, dict) and str(item.get("status") or "").lower() in {"failed", "error", "critical", "unavailable"}]
    summary = {
        "total_sites": total_sites,
        "monitored_sites": monitored_count,
        "monitoring_coverage_percent": coverage,
        "product_access_sites": product_summary.get("sites_with_jira_roles") or product_summary.get("accessible_jira_resource_count"),
        "product_users": product_summary.get("total_jira_product_user_count"),
        "role_rows": product_summary.get("jira_role_rows"),
        "failed_sources": len(failed_sources),
        "site_rows": len(site_rows),
    }
    authority = {
        "runtime": "available" if registry else "unavailable",
        "oauth": "live" if product_access.get("live_collection") is True or product_access.get("status") in {"ok", "partial"} else "unavailable",
        "monitoring_scope": "live" if registry_sites or site_rows else "unavailable",
        "truth_policy": "Monitoring serves the latest generated runtime authority immediately. A guarded background refresh updates the authority chain without blocking the page.",
        "refresh": refresh_status,
    }
    return {
        "schema": "jom-admin-monitoring-authority-v1",
        "generated_at_utc": now_utc(),
        "status": "ok" if coverage == 100 and not failed_sources else "review",
        "authority": authority,
        "summary": summary,
        "actions": _jom_admin_mon_actions_v1(summary, source_health, site_rows),
        "sites": site_rows,
        "source_health": source_health,
        "source_files": {
            "site_registry": "runtime/data/site_registry.json",
            "estate_product_access": "runtime/data/estate_product_access.json",
            "source_freshness": "runtime/data/source_freshness_audit.json",
            "source_reliability": "runtime/data/source_reliability_status.json",
            "product_access_refresh": "runtime/data/product_access_refresh_status.json",
            "runtime_execution": "runtime/data/runtime_execution_status.json",
        },
        "notes": [
            "Monitoring coverage is derived from current runtime site registry authority.",
            "Monitoring serves current generated authority immediately and refreshes the authority chain in the background.",
            "Runtime execution status is refreshed from the Monitoring preflight run before source freshness is evaluated.",
            "Product access monitoring is derived from OAuth product access authority.",
            "Product Access refresh status is refreshed automatically on Monitoring API requests.",
            "Unavailable or failed source health is not treated as healthy.",
            "Source freshness and reliability audits are refreshed automatically on Monitoring API requests.",
        ],
    }

_jom_admin_mon_background_lock_v1 = threading.Lock()
_jom_admin_mon_background_state_v1 = {"running": False, "status": "idle", "started_at_utc": None, "finished_at_utc": None, "last_error": None}

def _jom_admin_mon_background_status_v1():
    return dict(_jom_admin_mon_background_state_v1)

def _jom_admin_mon_background_worker_v1():
    state = _jom_admin_mon_background_state_v1
    try:
        runtime_inputs_refresh = _jom_admin_mon_refresh_runtime_inputs_v1()
        named_access_refresh = _jom_admin_mon_refresh_named_access_v1()
        product_access_refresh = _jom_admin_mon_refresh_product_access_v1()
        _jom_admin_mon_write_runtime_execution_status_v1(runtime_inputs_refresh, product_access_refresh, named_access_refresh)
        source_health_refresh = _jom_admin_mon_refresh_source_health_v1()
        runtime_execution_refresh = _jom_admin_mon_write_runtime_execution_status_v1(runtime_inputs_refresh, product_access_refresh, named_access_refresh, source_health_refresh)
        errors = []
        for result in (runtime_inputs_refresh, named_access_refresh, product_access_refresh, source_health_refresh, runtime_execution_refresh):
            if isinstance(result, dict):
                errors.extend(result.get("errors") or [])
                if result.get("status") == "failed" and result.get("error"):
                    errors.append(str(result.get("error")))
        state["status"] = "ok" if not errors else "attention"
        state["last_error"] = "; ".join(errors) if errors else None
    except Exception as exc:
        state["status"] = "failed"
        state["last_error"] = str(exc)
    finally:
        state["running"] = False
        state["finished_at_utc"] = now_utc()
        _jom_admin_mon_background_lock_v1.release()

@app.route("/api/admin/monitoring")
def api_admin_monitoring_authority_v1():
    return jsonify(_jom_admin_monitoring_contract_v1())

@app.route("/api/admin/monitoring/refresh", methods=["POST"])
def api_admin_monitoring_refresh_v1():
    if not _jom_admin_mon_background_lock_v1.acquire(blocking=False):
        return jsonify({"accepted": False, "reason": "refresh_already_running", "refresh": _jom_admin_mon_background_status_v1()}), 202
    state = _jom_admin_mon_background_state_v1
    state.update({"running": True, "status": "refreshing", "started_at_utc": now_utc(), "finished_at_utc": None, "last_error": None})
    threading.Thread(target=_jom_admin_mon_background_worker_v1, daemon=True).start()
    return jsonify({"accepted": True, "refresh": _jom_admin_mon_background_status_v1()}), 202
# --- JOM_ADMIN_MONITORING_AUTHORITY_V1 END ---


# --- JOM_ADMIN_SYSTEM_CONFIGURATION_AUTHORITY_V1 START ---
# Owner contract for Admin > System Configuration.
# Truth rule: runtime/OAuth/Admin authority only. Unproven configuration is unavailable, not inferred.
def _jom_admin_sc_int_v1(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default

def _jom_admin_sc_list_v1(value):
    return value if isinstance(value, list) else []

def _jom_admin_sc_dict_v1(value):
    return value if isinstance(value, dict) else {}

def _jom_admin_sc_health_v1(label, payload):
    if isinstance(payload, dict) and payload:
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        status = payload.get("status") or payload.get("overall_status") or payload.get("overall_state") or summary.get("overall_state") or summary.get("status") or "available"
        return {
            "label": label,
            "available": True,
            "status": status,
            "generated_at_utc": payload.get("generated_at_utc") or payload.get("served_at_utc") or payload.get("updated_at_utc"),
        }
    return {"label": label, "available": False, "status": "unavailable", "generated_at_utc": None}

def _jom_admin_sc_is_monitored_v1(row):
    if not isinstance(row, dict):
        return False
    state = str(row.get("classification") or row.get("lifecycle") or row.get("collector_onboarding_status") or row.get("status") or "").strip().lower()
    return bool(row.get("is_monitored") is True or row.get("monitored") is True or row.get("approved_monitored") is True or state in {"monitored", "monitoring_enabled"} or "monitoring enabled" in state)

def _jom_admin_sc_actions_v1(authority, guardrails, source_health):
    actions = []
    if authority.get("active_user_authority") == "unavailable":
        actions.append({
            "level": "review",
            "title": "Active-user authority unavailable",
            "reason": "Current configuration does not prove a unique active-user authority source.",
            "action": "Keep headline active users unavailable until OAuth/Admin active-user authority is added.",
            "source": "users_metric_contract",
        })
    if authority.get("commercial_billing_authority") == "unavailable":
        actions.append({
            "level": "info",
            "title": "Commercial billing authority unavailable",
            "reason": "Current configuration does not prove invoice, payment method, renewal, or contract authority.",
            "action": "Keep commercial billing unavailable until an approved billing authority source exists.",
            "source": "billing_truth_policy",
        })
    failed = []
    for key, item in source_health.items():
        if isinstance(item, dict) and str(item.get("status") or "").lower() in {"failed", "error", "critical", "unavailable"}:
            failed.append(item.get("label") or key)
    if failed:
        actions.append({
            "level": "review",
            "title": "Configured source health requires review",
            "reason": ", ".join(failed) + " requires attention.",
            "action": "Open Source Health and refresh or repair the affected source(s).",
            "source": "source_health",
        })
    if guardrails.get("static_truth_disabled") is not True:
        actions.append({
            "level": "review",
            "title": "Static truth guardrail not proven",
            "reason": "The system guardrail did not prove static truth is disabled.",
            "action": "Review configuration and ensure static artefacts are not treated as estate truth.",
            "source": "system_guardrails",
        })
    if not actions:
        actions.append({
            "level": "ok",
            "title": "No immediate system configuration actions",
            "reason": "Current authority did not return priority configuration actions.",
            "action": "Continue routine source health and runtime checks.",
            "source": "admin_system_configuration",
        })
    return actions[:8]

def _jom_admin_system_configuration_contract_v1():
    registry = _jom_admin_sc_dict_v1(load_json("site_registry.json", {}))
    product_access = _jom_admin_sc_dict_v1(load_json("estate_product_access.json", {}))
    source_freshness = load_json("source_freshness_audit.json", {})
    source_reliability = load_json("source_reliability_status.json", {})
    product_refresh = load_json("product_access_refresh_status.json", {})
    runtime_status = load_json("runtime_execution_status.json", {})
    org_discovery = _jom_admin_sc_dict_v1(load_json("organisation_discovery.json", {}))
    admin_contacts = _jom_admin_sc_dict_v1(load_json("estate_admin_contacts_v1.json", {}))

    registry_sites = _jom_admin_sc_list_v1(registry.get("sites"))
    monitored_sites = [row for row in registry_sites if _jom_admin_sc_is_monitored_v1(row)]
    registry_summary = _jom_admin_sc_dict_v1(registry.get("summary"))
    product_summary = _jom_admin_sc_dict_v1(product_access.get("summary"))

    total_sites = registry_summary.get("total_sites") or registry_summary.get("site_count") or len(registry_sites)
    monitored_count = registry_summary.get("monitored_count") or len(monitored_sites)
    coverage = round((float(monitored_count) / float(total_sites)) * 100) if total_sites else None

    authority = {
        "runtime": "available" if registry else "unavailable",
        "oauth": "live" if product_access.get("live_collection") is True or product_access.get("status") in {"ok", "partial"} else "unavailable",
        "admin": "available" if org_discovery or admin_contacts else "unavailable",
        "monitoring_scope": "live" if registry_sites else "unavailable",
        "active_user_authority": "unavailable",
        "commercial_billing_authority": "unavailable",
        "truth_policy": "JOM uses runtime/OAuth/Admin authority only. Unproven values are unavailable, not inferred.",
    }

    source_health = {
        "site_registry": _jom_admin_sc_health_v1("Site registry", registry),
        "product_access": _jom_admin_sc_health_v1("Product access", product_access),
        "source_freshness": _jom_admin_sc_health_v1("Source freshness", source_freshness),
        "source_reliability": _jom_admin_sc_health_v1("Source reliability", source_reliability),
        "product_access_refresh": _jom_admin_sc_health_v1("Product access refresh", product_refresh),
        "runtime_execution": _jom_admin_sc_health_v1("Runtime execution", runtime_status),
        "organisation_discovery": _jom_admin_sc_health_v1("Organisation discovery", org_discovery),
        "admin_contacts": _jom_admin_sc_health_v1("Admin contacts", admin_contacts),
    }
    failed_sources = [key for key, item in source_health.items() if isinstance(item, dict) and str(item.get("status") or "").lower() in {"failed", "error", "critical", "unavailable"}]

    guardrails = {
        "static_truth_disabled": True,
        "runtime_data_not_written_by_page": True,
        "active_users_unavailable_until_proven": True,
        "product_access_separate_from_active_users": True,
        "commercial_billing_unavailable_until_proven": True,
        "no_fake_health": True,
    }
    summary = {
        "environment": "Local Dev",
        "runtime_mode": "read-only operational console",
        "total_sites": total_sites,
        "monitored_sites": monitored_count,
        "monitoring_coverage_percent": coverage,
        "product_access_assignments": product_summary.get("total_jira_product_user_count"),
        "role_rows": product_summary.get("jira_role_rows"),
        "configured_sources": len(source_health),
        "failed_sources": len(failed_sources),
        "guardrails_enabled": sum(1 for value in guardrails.values() if value is True),
    }
    return {
        "schema": "jom-admin-system-configuration-authority-v1",
        "generated_at_utc": now_utc(),
        "status": "ok" if not failed_sources else "review",
        "authority": authority,
        "summary": summary,
        "actions": _jom_admin_sc_actions_v1(authority, guardrails, source_health),
        "source_health": source_health,
        "guardrails": guardrails,
        "source_files": {
            "site_registry": "runtime/data/site_registry.json",
            "estate_product_access": "runtime/data/estate_product_access.json",
            "source_freshness": "runtime/data/source_freshness_audit.json",
            "source_reliability": "runtime/data/source_reliability_status.json",
            "product_access_refresh": "runtime/data/product_access_refresh_status.json",
            "runtime_execution": "runtime/data/runtime_execution_status.json",
            "organisation_discovery": "runtime/data/organisation_discovery.json",
            "estate_admin_contacts": "runtime/data/estate_admin_contacts_v1.json",
        },
        "notes": [
            "This page reports configuration authority and guardrails only.",
            "The page does not write runtime/data or create truth artefacts.",
            "Active users and commercial billing remain unavailable until proven by authority.",
        ],
    }

@app.route("/api/admin/system-configuration")
def api_admin_system_configuration_authority_v1():
    return jsonify(_jom_admin_system_configuration_contract_v1())
# --- JOM_ADMIN_SYSTEM_CONFIGURATION_AUTHORITY_V1 END ---


# --- JOM_EXECUTIVE_REPORT_AUTHORITY_V1 START ---
# Owner contract for Reporting > Executive Report.
# Truth rule: board-level summary from runtime/OAuth/Admin authority only. Unproven values remain unavailable.
def _jom_exec_int_v1(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default

def _jom_exec_list_v1(value):
    return value if isinstance(value, list) else []

def _jom_exec_dict_v1(value):
    return value if isinstance(value, dict) else {}

def _jom_exec_is_monitored_v1(row):
    if not isinstance(row, dict):
        return False
    state = str(row.get("classification") or row.get("lifecycle") or row.get("collector_onboarding_status") or row.get("status") or "").strip().lower()
    return bool(row.get("is_monitored") is True or row.get("monitored") is True or row.get("approved_monitored") is True or state in {"monitored", "monitoring_enabled"} or "monitoring enabled" in state)

def _jom_exec_health_v1(label, payload):
    if isinstance(payload, dict) and payload:
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        status = payload.get("status") or payload.get("overall_status") or payload.get("overall_state") or summary.get("overall_state") or summary.get("status") or "available"
        return {
            "label": label,
            "available": True,
            "status": status,
            "generated_at_utc": payload.get("generated_at_utc") or payload.get("served_at_utc") or payload.get("updated_at_utc"),
        }
    return {"label": label, "available": False, "status": "unavailable", "generated_at_utc": None}

def _jom_exec_actions_v1(authority, summary, source_health):
    actions = []
    if authority.get("active_user_authority") == "unavailable":
        actions.append({
            "level": "review",
            "title": "Active-user reporting unavailable",
            "reason": "OAuth/Admin authority does not currently prove unique active users.",
            "action": "Report active users as unavailable and keep product-access assignments separate.",
            "source": "users_metric_contract",
        })
    if authority.get("commercial_billing_authority") == "unavailable":
        actions.append({
            "level": "info",
            "title": "Commercial billing reporting unavailable",
            "reason": "Invoice, renewal, payment method, and contract values are not proven by current authority.",
            "action": "Keep commercial billing values unavailable until a proven billing authority source exists.",
            "source": "billing_truth_policy",
        })
    if summary.get("failed_sources", 0):
        actions.append({
            "level": "review",
            "title": "Source health requires attention",
            "reason": str(summary.get("failed_sources")) + " configured source health item(s) require review.",
            "action": "Open Source Health and refresh or repair affected source(s).",
            "source": "source_health",
        })
    if summary.get("monitoring_coverage_percent") is not None and summary.get("monitoring_coverage_percent") < 100:
        actions.append({
            "level": "review",
            "title": "Monitoring coverage below target",
            "reason": "Monitored-site coverage is below 100%.",
            "action": "Review Estate lifecycle and bring approved sites into monitoring scope.",
            "source": "site_registry",
        })
    if not actions:
        actions.append({
            "level": "ok",
            "title": "No immediate executive actions",
            "reason": "Current authority did not return priority executive action items.",
            "action": "Continue routine monitoring and governance review.",
            "source": "executive_report",
        })
    return actions[:8]

def _jom_executive_report_contract_v1():
    registry = _jom_exec_dict_v1(load_json("site_registry.json", {}))
    product_access = _jom_exec_dict_v1(load_json("estate_product_access.json", {}))
    source_freshness = load_json("source_freshness_audit.json", {})
    source_reliability = load_json("source_reliability_status.json", {})
    product_refresh = load_json("product_access_refresh_status.json", {})
    runtime_status = load_json("runtime_execution_status.json", {})
    org_discovery = _jom_exec_dict_v1(load_json("organisation_discovery.json", {}))

    registry_sites = _jom_exec_list_v1(registry.get("sites"))
    monitored_sites = [row for row in registry_sites if _jom_exec_is_monitored_v1(row)]
    registry_summary = _jom_exec_dict_v1(registry.get("summary"))
    product_summary = _jom_exec_dict_v1(product_access.get("summary"))

    total_sites = registry_summary.get("total_sites") or registry_summary.get("site_count") or len(registry_sites)
    monitored_count = registry_summary.get("monitored_count") or len(monitored_sites)
    coverage = round((float(monitored_count) / float(total_sites)) * 100) if total_sites else None

    source_health = {
        "site_registry": _jom_exec_health_v1("Site registry", registry),
        "product_access": _jom_exec_health_v1("Product access", product_access),
        "source_freshness": _jom_exec_health_v1("Source freshness", source_freshness),
        "source_reliability": _jom_exec_health_v1("Source reliability", source_reliability),
        "product_access_refresh": _jom_exec_health_v1("Product access refresh", product_refresh),
        "runtime_execution": _jom_exec_health_v1("Runtime execution", runtime_status),
        "organisation_discovery": _jom_exec_health_v1("Organisation discovery", org_discovery),
    }
    failed_sources = [key for key, item in source_health.items() if isinstance(item, dict) and str(item.get("status") or "").lower() in {"failed", "error", "critical", "unavailable"}]

    authority = {
        "runtime": "available" if registry else "unavailable",
        "oauth": "live" if product_access.get("live_collection") is True or product_access.get("status") in {"ok", "partial"} else "unavailable",
        "admin": "available" if org_discovery else "unavailable",
        "active_user_authority": "unavailable",
        "commercial_billing_authority": "unavailable",
        "truth_policy": "Executive reporting uses runtime/OAuth/Admin authority only. Unproven values are unavailable, not inferred.",
    }
    summary = {
        "overall_status": "review" if failed_sources else "ok",
        "total_sites": total_sites,
        "monitored_sites": monitored_count,
        "monitoring_coverage_percent": coverage,
        "product_access_assignments": product_summary.get("total_jira_product_user_count"),
        "role_rows": product_summary.get("jira_role_rows"),
        "active_users_display": "Unavailable",
        "commercial_billing_display": "Unavailable",
        "configured_sources": len(source_health),
        "failed_sources": len(failed_sources),
        "organisations": org_discovery.get("organisation_count") if isinstance(org_discovery, dict) else None,
    }
    return {
        "schema": "jom-executive-report-authority-v1",
        "generated_at_utc": now_utc(),
        "status": summary.get("overall_status"),
        "authority": authority,
        "summary": summary,
        "actions": _jom_exec_actions_v1(authority, summary, source_health),
        "source_health": source_health,
        "board_messages": [
            "JOM currently reports monitored estate scope from runtime authority.",
            "Product-access assignments are not active-user counts and are reported separately.",
            "Commercial billing values remain unavailable until a proven billing authority source exists.",
            "Source health issues are surfaced as review items, not hidden behind a healthy status.",
        ],
        "source_files": {
            "site_registry": "runtime/data/site_registry.json",
            "estate_product_access": "runtime/data/estate_product_access.json",
            "source_freshness": "runtime/data/source_freshness_audit.json",
            "source_reliability": "runtime/data/source_reliability_status.json",
            "product_access_refresh": "runtime/data/product_access_refresh_status.json",
            "runtime_execution": "runtime/data/runtime_execution_status.json",
            "organisation_discovery": "runtime/data/organisation_discovery.json",
        },
    }

@app.route("/api/reporting/executive-report")
def api_reporting_executive_report_authority_v1():
    return jsonify(_jom_executive_report_contract_v1())
# --- JOM_EXECUTIVE_REPORT_AUTHORITY_V1 END ---


# --- JOM_ESTATE_REPORT_AUTHORITY_V1 START ---
# Owner contract for Reporting > Estate Report.
# Truth rule: runtime/OAuth/Admin authority only. Unproven values remain unavailable.
def _jom_estate_dict_v1(value):
    return value if isinstance(value, dict) else {}
def _jom_estate_list_v1(value):
    return value if isinstance(value, list) else []
def _jom_estate_is_monitored_v1(row):
    if not isinstance(row, dict):
        return False
    state = str(row.get("classification") or row.get("lifecycle") or row.get("collector_onboarding_status") or row.get("status") or "").strip().lower()
    return bool(row.get("is_monitored") is True or row.get("monitored") is True or row.get("approved_monitored") is True or state in {"monitored", "monitoring_enabled"} or "monitoring enabled" in state)
def _jom_estate_health_v1(label, payload):
    if isinstance(payload, dict) and payload:
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        status = payload.get("status") or payload.get("overall_status") or payload.get("overall_state") or summary.get("overall_state") or summary.get("status") or "available"
        return {"label": label, "available": True, "status": status, "generated_at_utc": payload.get("generated_at_utc") or payload.get("served_at_utc") or payload.get("updated_at_utc")}
    return {"label": label, "available": False, "status": "unavailable", "generated_at_utc": None}
def _jom_estate_contract_v1():
    registry = _jom_estate_dict_v1(load_json("site_registry.json", {}))
    product_access = _jom_estate_dict_v1(load_json("estate_product_access.json", {}))
    source_freshness = load_json("source_freshness_audit.json", {})
    source_reliability = load_json("source_reliability_status.json", {})
    product_refresh = load_json("product_access_refresh_status.json", {})
    runtime_status = load_json("runtime_execution_status.json", {})
    registry_sites = _jom_estate_list_v1(registry.get("sites"))
    monitored_sites = [row for row in registry_sites if _jom_estate_is_monitored_v1(row)]
    registry_summary = _jom_estate_dict_v1(registry.get("summary"))
    product_summary = _jom_estate_dict_v1(product_access.get("summary"))
    total_sites = registry_summary.get("total_sites") or registry_summary.get("site_count") or len(registry_sites)
    monitored_count = registry_summary.get("monitored_count") or len(monitored_sites)
    coverage = round((float(monitored_count) / float(total_sites)) * 100) if total_sites else None
    source_health = {
        "site_registry": _jom_estate_health_v1("Site registry", registry),
        "product_access": _jom_estate_health_v1("Product access", product_access),
        "source_freshness": _jom_estate_health_v1("Source freshness", source_freshness),
        "source_reliability": _jom_estate_health_v1("Source reliability", source_reliability),
        "product_access_refresh": _jom_estate_health_v1("Product access refresh", product_refresh),
        "runtime_execution": _jom_estate_health_v1("Runtime execution", runtime_status),
    }
    failed_sources = [key for key, item in source_health.items() if isinstance(item, dict) and str(item.get("status") or "").lower() in {"failed", "error", "critical", "unavailable"}]
    summary = {
        "total_sites": total_sites,
        "monitored_sites": monitored_count,
        "monitoring_coverage_percent": coverage,
        "product_access_assignments": product_summary.get("total_jira_product_user_count"),
        "role_rows": product_summary.get("jira_role_rows"),
        "active_users_display": "Unavailable",
        "commercial_billing_display": "Unavailable",
        "configured_sources": len(source_health),
        "failed_sources": len(failed_sources),
    }
    actions = []
    if summary.get("failed_sources", 0):
        actions.append({"level":"review","title":"Source health requires attention","reason":str(summary.get("failed_sources")) + " source health item(s) require review.","action":"Open Source Health and refresh or repair affected source(s).","source":"source_health"})
    actions.append({"level":"review","title":"Active-user authority unavailable","reason":"OAuth/Admin authority does not currently prove unique active users.","action":"Report active users as unavailable and keep product-access assignments separate.","source":"users_metric_contract"})
    actions.append({"level":"info","title":"Commercial billing authority unavailable","reason":"Commercial billing values are not proven by current authority.","action":"Keep commercial billing unavailable until a proven billing authority source exists.","source":"billing_truth_policy"})
    return {"schema":"jom-estate-report-authority-v1","generated_at_utc":now_utc(),"status":"review" if failed_sources else "ok","summary":summary,"actions":actions[:8],"source_health":source_health,"authority":{"runtime":"available" if registry else "unavailable","oauth":"live" if product_access.get("live_collection") is True or product_access.get("status") in {"ok","partial"} else "unavailable","truth_policy":"Estate Report uses runtime/OAuth/Admin authority only. Unproven values are unavailable, not inferred."},"notes":["Product-access assignments are not active-user counts.","Active users and commercial billing remain unavailable until proven."]}
@app.route("/api/reporting/estate-report")
def api_estate_report_authority_v1():
    return jsonify(_jom_estate_contract_v1())
# --- JOM_ESTATE_REPORT_AUTHORITY_V1 END ---


# --- JOM_GOVERNANCE_REPORT_AUTHORITY_V1 START ---
# Owner contract for Reporting > Governance Report.
# Truth rule: runtime/OAuth/Admin authority only. Unproven values remain unavailable.
def _jom_governance_dict_v1(value):
    return value if isinstance(value, dict) else {}
def _jom_governance_list_v1(value):
    return value if isinstance(value, list) else []
def _jom_governance_is_monitored_v1(row):
    if not isinstance(row, dict):
        return False
    state = str(row.get("classification") or row.get("lifecycle") or row.get("collector_onboarding_status") or row.get("status") or "").strip().lower()
    return bool(row.get("is_monitored") is True or row.get("monitored") is True or row.get("approved_monitored") is True or state in {"monitored", "monitoring_enabled"} or "monitoring enabled" in state)
def _jom_governance_health_v1(label, payload):
    if isinstance(payload, dict) and payload:
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        status = payload.get("status") or payload.get("overall_status") or payload.get("overall_state") or summary.get("overall_state") or summary.get("status") or "available"
        return {"label": label, "available": True, "status": status, "generated_at_utc": payload.get("generated_at_utc") or payload.get("served_at_utc") or payload.get("updated_at_utc")}
    return {"label": label, "available": False, "status": "unavailable", "generated_at_utc": None}
def _jom_governance_contract_v1():
    registry = _jom_governance_dict_v1(load_json("site_registry.json", {}))
    product_access = _jom_governance_dict_v1(load_json("estate_product_access.json", {}))
    source_freshness = load_json("source_freshness_audit.json", {})
    source_reliability = load_json("source_reliability_status.json", {})
    product_refresh = load_json("product_access_refresh_status.json", {})
    runtime_status = load_json("runtime_execution_status.json", {})
    registry_sites = _jom_governance_list_v1(registry.get("sites"))
    monitored_sites = [row for row in registry_sites if _jom_governance_is_monitored_v1(row)]
    registry_summary = _jom_governance_dict_v1(registry.get("summary"))
    product_summary = _jom_governance_dict_v1(product_access.get("summary"))
    total_sites = registry_summary.get("total_sites") or registry_summary.get("site_count") or len(registry_sites)
    monitored_count = registry_summary.get("monitored_count") or len(monitored_sites)
    coverage = round((float(monitored_count) / float(total_sites)) * 100) if total_sites else None
    source_health = {
        "site_registry": _jom_governance_health_v1("Site registry", registry),
        "product_access": _jom_governance_health_v1("Product access", product_access),
        "source_freshness": _jom_governance_health_v1("Source freshness", source_freshness),
        "source_reliability": _jom_governance_health_v1("Source reliability", source_reliability),
        "product_access_refresh": _jom_governance_health_v1("Product access refresh", product_refresh),
        "runtime_execution": _jom_governance_health_v1("Runtime execution", runtime_status),
    }
    failed_sources = [key for key, item in source_health.items() if isinstance(item, dict) and str(item.get("status") or "").lower() in {"failed", "error", "critical", "unavailable"}]
    summary = {
        "total_sites": total_sites,
        "monitored_sites": monitored_count,
        "monitoring_coverage_percent": coverage,
        "product_access_assignments": product_summary.get("total_jira_product_user_count"),
        "role_rows": product_summary.get("jira_role_rows"),
        "active_users_display": "Unavailable",
        "commercial_billing_display": "Unavailable",
        "configured_sources": len(source_health),
        "failed_sources": len(failed_sources),
    }
    actions = []
    if summary.get("failed_sources", 0):
        actions.append({"level":"review","title":"Source health requires attention","reason":str(summary.get("failed_sources")) + " source health item(s) require review.","action":"Open Source Health and refresh or repair affected source(s).","source":"source_health"})
    actions.append({"level":"review","title":"Active-user authority unavailable","reason":"OAuth/Admin authority does not currently prove unique active users.","action":"Report active users as unavailable and keep product-access assignments separate.","source":"users_metric_contract"})
    actions.append({"level":"info","title":"Commercial billing authority unavailable","reason":"Commercial billing values are not proven by current authority.","action":"Keep commercial billing unavailable until a proven billing authority source exists.","source":"billing_truth_policy"})
    return {"schema":"jom-governance-report-authority-v1","generated_at_utc":now_utc(),"status":"review" if failed_sources else "ok","summary":summary,"actions":actions[:8],"source_health":source_health,"authority":{"runtime":"available" if registry else "unavailable","oauth":"live" if product_access.get("live_collection") is True or product_access.get("status") in {"ok","partial"} else "unavailable","truth_policy":"Governance Report uses runtime/OAuth/Admin authority only. Unproven values are unavailable, not inferred."},"notes":["Product-access assignments are not active-user counts.","Active users and commercial billing remain unavailable until proven."]}
@app.route("/api/reporting/governance-report")
def api_governance_report_authority_v1():
    return jsonify(_jom_governance_contract_v1())
# --- JOM_GOVERNANCE_REPORT_AUTHORITY_V1 END ---

# --- JOM OAUTH OWNER PAGE ROUTES v1 START ---
# Owner-file page shell routes. OAuth/Admin is the only current authority pipeline.
@app.route('/admin')
def page_admin():
    return render_template('admin.html')

@app.route('/admin/estate-configuration')
def page_admin_estate_configuration():
    return render_template('admin_estate_configuration.html')

@app.route('/admin/discovery')
def page_admin_discovery():
    return render_template('admin_discovery.html')

@app.route('/admin/monitoring')
def page_admin_monitoring():
    return render_template('admin_monitoring.html')

@app.route('/admin/licensing-billing')
def page_admin_licensing_billing():
    return render_template('admin_licensing_billing.html')

@app.route('/admin/users-access')
def page_admin_users_access():
    return render_template('admin_users_access.html')

@app.route('/admin/system-configuration')
def page_admin_system_configuration():
    return render_template('admin_system_configuration.html')

@app.route('/executive-report')
def page_executive_report():
    return render_template('executive_report.html')

@app.route('/estate-report')
def page_estate_report():
    return render_template('estate_report.html')

@app.route('/reports/governance')
def page_reports_governance():
    return render_template('governance_report.html')

@app.route('/reports/governance/users')
def page_reports_governance_users():
    return render_template('governance_users.html')

@app.route('/reports/governance/projects')
def page_reports_governance_projects():
    return render_template('governance_projects.html')

@app.route('/reports/governance/configuration')
def page_reports_governance_configuration():
    return render_template('governance_configuration.html')

@app.route('/reports/governance/permissions')
def page_reports_governance_permissions():
    return render_template('governance_permissions.html')

@app.route('/reports/governance/policy-compliance')
def page_reports_governance_policy_compliance():
    return render_template('governance_policy_compliance.html')

@app.route('/runtime-status')
def page_runtime_status():
    return render_template('runtime_status.html')

@app.route('/system/runtime-status/application')
def page_system_runtime_status_application():
    return render_template('runtime_application.html')

@app.route('/system/runtime-status/api')
def page_system_runtime_status_api():
    return render_template('runtime_api.html')

@app.route('/system/runtime-status/collectors')
def page_system_runtime_status_collectors():
    return render_template('runtime_collectors.html')

@app.route('/system/runtime-status/jobs')
def page_system_runtime_status_jobs():
    return render_template('runtime_jobs.html')

@app.route('/system/runtime-status/errors')
def page_system_runtime_status_errors():
    return render_template('runtime_errors.html')

@app.route('/source-health')
def page_source_health():
    return render_template('source_health.html')

@app.route('/system/source-health/connections')
def page_system_source_health_connections():
    return render_template('source_connections.html')

@app.route('/system/source-health/authentication')
def page_system_source_health_authentication():
    return render_template('source_authentication.html')

@app.route('/system/source-health/freshness')
def page_system_source_health_freshness():
    return render_template('source_freshness.html')

@app.route('/system/source-health/completeness')
def page_system_source_health_completeness():
    return render_template('source_completeness.html')

@app.route('/system/source-health/failures')
def page_system_source_health_failures():
    return render_template('source_failures.html')

@app.route('/site-review')
def page_site_review_redirect_to_estate():
    return redirect('/estate', code=302)
# --- JOM OAUTH OWNER PAGE ROUTES v1 END ---

@app.route("/site-workspace")
def page_site_workspace_shell_index():
    site_key = request.args.get("site", "")
    return render_template("site_workspace.html", site_key=site_key)

@app.route("/site-workspace/<site_key>")
def page_site_workspace_shell_site(site_key):
    return render_template("site_workspace.html", site_key=site_key)
# JOM_SITE_WORKSPACE_SHELL_ROUTES_V1 END
@app.route("/site")
def page_site():
    """Legacy Site Workspace route. Current owner is /site-workspace."""
    return redirect("/site-workspace", code=302)
@app.route("/detail-list")
def page_detail_list():
    return render_template("detail_list.html", **detail_list_context())



# ============================================================
# LEGACY FRONTEND API COMPATIBILITY ROUTES - PACK v1
# ============================================================
@app.route("/api/source-state")
def api_source_state_legacy():
    return jsonify(_load_source_state_contract())


@app.route("/api/data")
def api_data_legacy():
    return jsonify({
        "schema": "jom-api-data-contract-v2",
        "served_at_utc": now_utc(),
        "operator_surface": build_operator_surface(),
        "operator_summary": build_operator_summary(),
        "admin_truth": _load_admin_truth_contract(),
        "estate_product_access": estate_product_access().get_json(),
        "user_footprint": _load_user_footprint_contract(),
        "site_registry": _load_registry_contract(),
        "notes": ["Aggregated compatibility contract. Static files are labelled as generated cache contracts."],
    })


@app.route("/api/site-registry")
def api_site_registry_legacy():
    return jsonify(_load_registry_contract())


@app.route("/reports/<path:filename>")
def reports_file_legacy(filename):
    reports_root = ROOT / "reports"
    return send_from_directory(str(reports_root), filename)



@app.route('/site/<path:site_key>')
def site_workspace(site_key):
    """Legacy Site Workspace route. Current owner is /site-workspace/<site_key>."""
    return redirect('/site-workspace/' + str(site_key), code=302)
# --- JOM EXPORT REPORTING ROUTES v1 START ---
try:
    from flask import Flask, jsonify, render_template, send_from_directory, request, redirect 
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



# JOM estate runtime consumer replacement helpers v1
def _jom_estate_runtime_site_registry_contract_v1():
    """Return current runtime site registry contract without legacy monitored-site JSON dependency."""
    try:
        payload = _jom_cached_read_json_v1("site_registry.json", {}) if "_jom_cached_read_json_v1" in globals() else load_json("site_registry.json", {})
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    sites = payload.get("sites") if isinstance(payload.get("sites"), list) else []
    return {"schema": payload.get("schema", "site-registry-runtime"), "summary": payload.get("summary", {}), "sites": sites, "source": "runtime/data/site_registry.json"}


def _jom_estate_runtime_access_validation_contract_v1():
    """Return runtime access validation view derived from live estate contracts, not estate_access_truth.json."""
    registry = _jom_estate_runtime_site_registry_contract_v1()
    validations = {}
    for site in registry.get("sites", []):
        if not isinstance(site, dict):
            continue
        key = site.get("key") or site.get("site_key") or site.get("cloud_id") or site.get("url")
        if key:
            validations[str(key)] = {"status": "runtime_contract", "source": registry.get("source"), "site": site}
    return {"validations": validations, "history": [], "source": "runtime/site_registry_contract"}


def _jom_estate_runtime_lifecycle_contract_v1():
    """Return read-only lifecycle decision contract derived from runtime site registry."""
    registry = _jom_estate_runtime_site_registry_contract_v1()
    decisions = {}
    for site in registry.get("sites", []):
        if not isinstance(site, dict):
            continue
        key = site.get("key") or site.get("site_key") or site.get("cloud_id") or site.get("url")
        if key:
            decisions[str(key)] = {"decision": site.get("lifecycle_decision") or site.get("status") or "runtime_registry", "source": registry.get("source")}
    return {"decisions": decisions, "history": [], "source": "runtime/site_registry_contract"}


def _jom_estate_runtime_noop_write_v1(label, payload=None):
    """Read-only estate guard: legacy runtime mutation disabled after runtime contract isolation."""
    return {"status": "skipped", "reason": "read_only_runtime_contract", "label": label}

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
SITE_LIFECYCLE_DECISIONS_PATH = DATA_PATH / "site_lifecycle_decisions.json"  # owner contract for lifecycle decisions

def _normalise_site_key(value: Any) -> str:
    return str(value or "").strip().lower()

def _site_key_from_record(site: Dict[str, Any]) -> str:
    return str(site.get("site_key") or site.get("key") or site.get("site_name") or site.get("name") or "")

def _load_lifecycle_decisions() -> Dict[str, Any]:
    payload = _jom_estate_runtime_lifecycle_contract_v1()
    if not isinstance(payload, dict) or not payload:
        payload = {"schema": "jom-site-lifecycle-decisions-v1", "generated_at_utc": None, "decisions": {}, "history": []}
    payload.setdefault("schema", "jom-site-lifecycle-decisions-v1")
    payload.setdefault("decisions", {})
    payload.setdefault("history", [])
    return payload

def _write_lifecycle_decisions(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload["generated_at_utc"] = now_utc()
    return write_json(SITE_LIFECYCLE_DECISIONS_PATH, payload)


def _jom_lifecycle_audit_contract_v1():
    payload = load_json("site_lifecycle_decisions.json", {})
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("schema", "jom-site-lifecycle-decisions-v1")
    payload.setdefault("decisions", {})
    payload.setdefault("history", [])
    return payload


def _jom_lifecycle_audit_event_v1(site_key, action, actor="operator", state=None, result="ok", message=None, source=None):
    key = _jom_lifecycle_norm_v1(site_key) if "_jom_lifecycle_norm_v1" in globals() else str(site_key or "").strip().lower()
    payload = _jom_lifecycle_audit_contract_v1()
    now = now_utc() if "now_utc" in globals() else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    action_value = str(action or "lifecycle_event")
    source_value = source or "site_review_lifecycle"
    event = {
        "site_key": key,
        "action": action_value,
        "decision": action_value,
        "state": state or action_value,
        "result": result,
        "actor": actor or "operator",
        "recorded_at_utc": now,
        "decided_at_utc": now,
        "source": source_value,
    }
    if message:
        event["message"] = message
    history = payload.setdefault("history", [])
    if action_value == "oauth_access_validated":
        recent_duplicate = next((item for item in reversed(history[-10:]) if isinstance(item, dict) and item.get("site_key") == key and item.get("action") == action_value and item.get("source") == source_value and item.get("result") == result), None)
        if recent_duplicate:
            payload.setdefault("decisions", {})[key] = recent_duplicate
            payload["generated_at_utc"] = now
            return write_json(SITE_LIFECYCLE_DECISIONS_PATH, payload)
    payload.setdefault("decisions", {})[key] = event
    history.append(event)
    # Keep audit evidence bounded: latest 10 lifecycle events per site, plus unrelated historical events.
    site_events = [item for item in history if isinstance(item, dict) and item.get("site_key") == key]
    other_events = [item for item in history if not (isinstance(item, dict) and item.get("site_key") == key)]
    payload["history"] = (other_events + site_events[-10:])[-250:]
    payload["generated_at_utc"] = now
    return write_json(SITE_LIFECYCLE_DECISIONS_PATH, payload)



# === JOM SITE REVIEW ESTATE INVENTORY TRUTH v1 START ===
def _jom_site_review_inventory_rows_v1():
    payload = load_json("estate_admin_site_inventory_v1.json", {})
    return payload.get("sites", []) if isinstance(payload, dict) and isinstance(payload.get("sites"), list) else []

def _jom_site_review_inventory_record_v1(site_key):
    wanted = _normalise_site_key(site_key) if "_normalise_site_key" in globals() else str(site_key or "").strip().lower()
    for row in _jom_site_review_inventory_rows_v1():
        if not isinstance(row, dict):
            continue
        values = [row.get("site_key"), row.get("key"), row.get("name"), row.get("site_name"), row.get("url"), row.get("site_url"), row.get("cloud_id")]
        for value in values:
            if value is not None and str(value).strip().lower() == wanted:
                return row
    return {}

def _jom_site_review_normalised_inventory_site_v1(site_key):
    row = _jom_site_review_inventory_record_v1(site_key)
    if not row:
        return {}
    key = str(row.get("site_key") or row.get("key") or row.get("name") or site_key or "").strip().lower()
    lifecycle = str(row.get("lifecycle") or "discovery_gap").strip().lower()
    monitored = lifecycle == "monitored" or row.get("approved_monitored") is True
    return {
        "site_key": key,
        "site_name": row.get("name") or row.get("site_name") or key,
        "site_url": row.get("url") or row.get("site_url") or "",
        "url": row.get("url") or row.get("site_url") or "",
        "cloud_id": row.get("cloud_id"),
        "sources": row.get("sources") or [],
        "evidence_levels": row.get("evidence_levels") or [],
        "classification": "monitored" if monitored else lifecycle,
        "lifecycle": lifecycle,
        "is_monitored": bool(monitored),
        "monitored": bool(monitored),
        "collector_onboarding_status": "monitoring_enabled" if monitored else lifecycle,
        "approved_monitored": bool(row.get("approved_monitored") is True),
        "in_registry": bool(row.get("in_registry") is True),
        "action_required": row.get("action_required"),
        "status": "ok" if monitored else "review",
    }
# === JOM SITE REVIEW ESTATE INVENTORY TRUTH v1 END ===


def _find_site(site_key: str) -> Dict[str, Any]:
    if "_jom_current_state_allowed_v1" in globals() and not _jom_current_state_allowed_v1(site_key):
        return {}
    inventory_site = _jom_site_review_normalised_inventory_site_v1(site_key)
    if inventory_site:
        return _jom_current_state_normalise_site_v1(inventory_site) if "_jom_current_state_normalise_site_v1" in globals() else inventory_site
    registry = load_json("site_registry.json", {})
    sites = registry.get("sites", []) if isinstance(registry, dict) else []
    target = _normalise_site_key(site_key)
    for site in sites:
        if isinstance(site, dict) and _normalise_site_key(_site_key_from_record(site)) == target:
            return _jom_current_state_normalise_site_v1(site) if "_jom_current_state_normalise_site_v1" in globals() else site
    return {}


def _review_sources_for_site(site_key: str) -> Dict[str, Any]:
    if "_jom_current_state_allowed_v1" in globals() and not _jom_current_state_allowed_v1(site_key):
        return {"bucket": None, "record": {}}
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
    decisions = _jom_lifecycle_audit_contract_v1() if "_jom_lifecycle_audit_contract_v1" in globals() else _load_lifecycle_decisions()
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
    elif decision_state.get("decision") == "discovered":
        lifecycle_status = "Discovered"
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
    payload = _build_site_review_payload(site_key)
    if "_jom_site_review_align_payload_v1_2" in globals():
        payload = _jom_site_review_align_payload_v1_2(site_key, payload)
    return jsonify(payload)
@app.route("/api/site-review/<path:site_key>/decision", methods=["POST"])
def api_site_review_decision(site_key):
    body = request.get_json(silent=True) or {}
    decision = str(body.get("decision") or body.get("state") or "").strip().lower()
    actor = body.get("actor") or "operator"
    if decision in ("approve", "approved", "approval_pending"):
        record, inventory_record, _registry, _inventory = _jom_lifecycle_mark_approval_pending_v1(site_key, actor=actor)
        if record is None and inventory_record is None:
            return jsonify({"ok": False, "error": "site_not_found", "site_key": site_key}), 404
        if "_jom_lifecycle_audit_event_v1" in globals():
            _jom_lifecycle_audit_event_v1(site_key, "approve_for_monitoring", actor=actor, state="approval_pending", message="Approved for monitoring. Credential access required before enablement.", source="site_review_decision")
        return jsonify({
            "ok": True,
            "site_key": _jom_lifecycle_norm_v1(site_key),
            "decision": "approve",
            "classification": "approval_pending",
            "lifecycle": "approval_pending",
            "message": "Approval recorded. Monitoring is pending token/credential enablement.",
            "registry_record": record,
            "inventory_record": inventory_record,
        })
    if decision in ("ignore", "ignored"):
        record, inventory_record, _registry, _inventory = _jom_lifecycle_mark_review_v1(site_key, actor=actor)
        if record:
            record["classification"] = "ignored"
            record["lifecycle"] = "ignored"
            record["collector_onboarding_status"] = "ignored"
            record["status"] = "ignored"
            record["action_required"] = None
        if inventory_record:
            inventory_record.update(record)
        _jom_lifecycle_save_sources_v1(_registry, _inventory)
        return jsonify({"ok": True, "site_key": _jom_lifecycle_norm_v1(site_key), "decision": "ignore", "classification": "ignored", "lifecycle": "ignored", "record": record})
    if decision in ("pending", "review", "restore", "discovered"):
        record, inventory_record, _registry, _inventory = _jom_lifecycle_mark_review_v1(site_key, actor=actor)
        if record is None and inventory_record is None:
            return jsonify({"ok": False, "error": "site_not_found", "site_key": site_key}), 404
        return jsonify({"ok": True, "site_key": _jom_lifecycle_norm_v1(site_key), "decision": "review", "classification": "discovered", "lifecycle": "stopped_monitoring", "record": record, "inventory_record": inventory_record})
    return jsonify({"ok": False, "error": "unsupported_decision", "decision": decision, "site_key": site_key}), 400
@app.route("/api/site-lifecycle/decisions")
def api_site_lifecycle_decisions():
    payload = _jom_estate_runtime_lifecycle_contract_v1()
    if not isinstance(payload, dict) or not payload:
        payload = {"schema": "jom-site-lifecycle-decisions-v1", "decisions": {}, "history": []}
    payload.setdefault("decisions", {})
    payload.setdefault("history", [])
    return jsonify(payload)



# --- credential_access_validation_v1 START ---
SITE_ACCESS_VALIDATION_PATH = DATA_PATH / "site_access_validation.json"  # owner contract for access validation

def _load_dotenv_values() -> Dict[str, str]:
    values = dict(os.environ)
    env_path = ROOT / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values

def _load_site_access_validation() -> Dict[str, Any]:
    payload = _jom_estate_runtime_access_validation_contract_v1()
    if not isinstance(payload, dict) or not payload:
        payload = {"schema": "jom-site-access-validation-v1", "generated_at_utc": None, "validations": {}, "history": []}
    payload.setdefault("validations", {})
    payload.setdefault("history", [])
    return payload

def _write_site_access_validation(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload["generated_at_utc"] = now_utc()
    return write_json(SITE_ACCESS_VALIDATION_PATH, payload)

def _http_json_validation(url: str, token: str) -> Dict[str, Any]:
    req = urllib.request.Request(url=url, headers={"Authorization": "Bearer " + token, "Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="ignore")
            return {"ok": True, "status_code": response.status, "body_preview": raw[:500]}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        return {"ok": False, "status_code": exc.code, "body_preview": body[:500]}
    except Exception as exc:
        return {"ok": False, "status_code": 0, "body_preview": str(exc)}

def _site_for_validation(site_key: str) -> Dict[str, Any]:
    if "_find_site" in globals():
        return _find_site(site_key)
    registry = load_json("site_registry.json", {})
    for site in registry.get("sites", []) if isinstance(registry, dict) else []:
        if isinstance(site, dict) and str(site.get("site_key") or site.get("key") or "").lower() == str(site_key).lower():
            return site
    return {}

@app.route("/api/site-review/<path:site_key>/access-validation")
def api_site_review_access_validation_status_gate_v1(site_key):
    gate = _jom_access_gate_current_coverage_v1(site_key, actor="site-review-access-status")
    status_code = 200
    return jsonify({
        "ok": True,
        "site_key": _jom_lifecycle_norm_v1(site_key) if "_jom_lifecycle_norm_v1" in globals() else site_key,
        "validation": gate.get("validation", {}),
        "coverage": gate.get("coverage", {}),
        "authorization_required": gate.get("authorization_required", True),
        "authorization_url": gate.get("authorization_url"),
        "action": gate.get("action"),
        "message": gate.get("message"),
    }), status_code
def _oauth_coverage_payload(site_key):
    """Return OAuth/token coverage for an Estate site without mutating registry state."""
    import json as _json
    import os as _os
    import time as _time
    import urllib.parse as _parse
    import urllib.request as _request
    import urllib.error as _error

    wanted = str(site_key or "").strip().lower()
    root = Path(__file__).resolve().parents[1]
    token_path = root / "tokens.json"
    state_path = root / ".auth_state.json"
    env_path = root / ".env"

    env = dict(_os.environ)
    if env_path.exists():
        try:
            for raw in env_path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
        except Exception:
            pass

    def _read_json(path, default):
        if not path.exists():
            return default
        try:
            value = _json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else default
        except Exception:
            return default

    tokens = _read_json(token_path, {})
    state = _read_json(state_path, {})
    now_epoch = int(_time.time())
    expires_at = int(tokens.get("expires_at_epoch") or 0)
    access_token = tokens.get("access_token") or ""
    token_valid = bool(access_token and expires_at > now_epoch + 60)

    client_id = env.get("ATLASSIAN_OAUTH_CLIENT_ID") or env.get("ATLASSIAN_CLIENT_ID") or tokens.get("client_id") or ""
    redirect_uri = env.get("ATLASSIAN_OAUTH_REDIRECT_URI") or env.get("ATLASSIAN_REDIRECT_URI") or "http://127.0.0.1:5000/oauth/callback"
    scope = env.get("ATLASSIAN_OAUTH_SCOPE") or tokens.get("scope") or "manage:jira-configuration offline_access read:application-role:jira read:jira-user read:jira-work read:license:jira"
    # JOM_OAUTH_CALLBACK_SITE_RETURN_CONTEXT_V1 START
    # Carry the active Site Review site in OAuth state so /callback can return to the same review page.
    base_auth_state = state.get("state") or env.get("ATLASSIAN_OAUTH_STATE") or "jom-estate-oauth"
    auth_state = "site:" + wanted if wanted else base_auth_state
    # JOM_OAUTH_CALLBACK_SITE_RETURN_CONTEXT_V1 END

    authorize_params = {
        "audience": "api.atlassian.com",
        "client_id": client_id,
        "scope": scope,
        "redirect_uri": redirect_uri,
        "state": auth_state,
        "response_type": "code",
        "prompt": "consent",
    }
    authorization_url = "https://auth.atlassian.com/authorize?" + _parse.urlencode(authorize_params)

    if not token_valid:
        return {
            "ok": True,
            "coverage_status": "authorization_required",
            "authorization_required": True,
            "authorization_url": authorization_url if client_id else None,
            "monitoring_allowed": False,
            "reason": "No valid Atlassian OAuth access token is available for this runtime.",
            "token_present": bool(access_token),
            "token_valid": False,
            "expires_at_epoch": expires_at or None,
        }

    resources = []
    try:
        req = _request.Request(
            "https://api.atlassian.com/oauth/token/accessible-resources",
            headers={"Authorization": "Bearer " + access_token, "Accept": "application/json"},
            method="GET",
        )
        with _request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            parsed = _json.loads(raw) if raw else []
            resources = parsed if isinstance(parsed, list) else []
    except _error.HTTPError as exc:
        return {
            "ok": False,
            "coverage_status": "token_probe_failed",
            "authorization_required": True,
            "authorization_url": authorization_url if client_id else None,
            "monitoring_allowed": False,
            "reason": "Atlassian accessible-resources probe failed.",
            "http_status": exc.code,
        }
    except Exception as exc:
        return {
            "ok": False,
            "coverage_status": "token_probe_failed",
            "authorization_required": True,
            "authorization_url": authorization_url if client_id else None,
            "monitoring_allowed": False,
            "reason": str(exc),
        }

    matched = None
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        values = [resource.get("id"), resource.get("name"), resource.get("url"), resource.get("scopes")]
        flat = " ".join(str(v).lower() for v in values if v is not None)
        if wanted and wanted in flat:
            matched = resource
            break

    if matched:
        return {
            "ok": True,
            "coverage_status": "validated",
            "authorization_required": False,
            "authorization_url": None,
            "monitoring_allowed": True,
            "reason": "Atlassian OAuth token has accessible resource coverage for this site.",
            "matched_resource": matched,
            "resource_count": len(resources),
            "token_valid": True,
        }

    return {
        "ok": True,
        "coverage_status": "authorization_required",
        "authorization_required": True,
        "authorization_url": authorization_url if client_id else None,
        "monitoring_allowed": False,
        "reason": "Valid token exists, but no accessible resource matched this site key.",
        "resource_count": len(resources),
        "token_valid": True,
    }

@app.route("/api/oauth/coverage/<path:site_key>")
def api_oauth_coverage(site_key):
    return jsonify(_oauth_coverage_payload(site_key))


@app.route("/api/oauth/authorize-url/<path:site_key>")
def api_oauth_authorize_url(site_key):
    if "_jom_oauth_store_pending_site_v1_1" in globals():
        _jom_oauth_store_pending_site_v1_1(site_key)
    payload = _oauth_coverage_payload(site_key)
    return jsonify({
        "ok": bool(payload.get("authorization_url")),
        "site_key": site_key,
        "coverage_status": payload.get("coverage_status"),
        "authorization_required": payload.get("authorization_required"),
        "authorization_url": payload.get("authorization_url"),
        "reason": payload.get("reason"),
    })
# --- JOM OAUTH ONBOARDING GATE v1 END ---


# JOM_SITE_REVIEW_LIFECYCLE_CONSOLIDATED_V1 START
# Owner implementation for Site Review lifecycle transitions.
# This replaces temporary route wrappers and keeps registry/inventory state aligned.
def _jom_lifecycle_norm_v1(value):
    text = str(value or "").strip().lower()
    if text.startswith("http") and ".atlassian.net" in text:
        text = text.split("//", 1)[-1].split(".atlassian.net", 1)[0]
    return text.rstrip("/")


def _jom_lifecycle_is_monitored_v1(site):
    if not isinstance(site, dict):
        return False
    state = _jom_lifecycle_norm_v1(site.get("lifecycle") or site.get("classification") or site.get("status") or site.get("collector_onboarding_status"))
    return bool(
        site.get("is_monitored") is True
        or site.get("monitored") is True
        or site.get("approved_monitored") is True
        or state in {"monitored", "monitoring_enabled"}
    )


def _jom_lifecycle_key_v1(site):
    if not isinstance(site, dict):
        return ""
    return _jom_lifecycle_norm_v1(
        site.get("site_key") or site.get("key") or site.get("name") or site.get("site_name") or site.get("url") or site.get("site_url") or site.get("cloud_id")
    )


def _jom_lifecycle_find_v1(rows, site_key):
    wanted = _jom_lifecycle_norm_v1(site_key)
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        values = [row.get("site_key"), row.get("key"), row.get("name"), row.get("site_name"), row.get("url"), row.get("site_url"), row.get("cloud_id")]
        if any(_jom_lifecycle_norm_v1(value) == wanted for value in values if value is not None):
            return row
    return None


def _jom_lifecycle_base_record_v1(site_key, registry_site=None, inventory_site=None):
    source = inventory_site if isinstance(inventory_site, dict) and inventory_site else registry_site if isinstance(registry_site, dict) else {}
    key = _jom_lifecycle_norm_v1(source.get("site_key") or source.get("key") or source.get("name") or source.get("site_name") or site_key)
    url = source.get("site_url") or source.get("url") or ("https://" + key + ".atlassian.net" if key else "")
    record = dict(registry_site) if isinstance(registry_site, dict) else {}
    record.update({
        "site_key": key,
        "key": key,
        "site_name": source.get("site_name") or source.get("name") or key,
        "name": source.get("name") or source.get("site_name") or key,
        "site_url": url,
        "url": url,
        "cloud_id": source.get("cloud_id") or record.get("cloud_id"),
    })
    sources = record.get("sources") if isinstance(record.get("sources"), list) else []
    for value in ["oauth_accessible_resources", "estate_admin_site_inventory", "site_review_lifecycle"]:
        if value not in sources:
            sources.append(value)
    record["sources"] = sources
    return key, record


def _jom_lifecycle_load_sources_v1():
    registry = load_json("site_registry.json", {})
    if not isinstance(registry, dict):
        registry = {"schema": "site-registry-runtime", "sites": []}
    registry.setdefault("sites", [])
    if not isinstance(registry.get("sites"), list):
        registry["sites"] = []

    inventory = load_json("estate_admin_site_inventory_v1.json", {})
    if not isinstance(inventory, dict):
        inventory = {"schema": "estate_admin_site_inventory_v1", "sites": []}
    inventory.setdefault("sites", [])
    if not isinstance(inventory.get("sites"), list):
        inventory["sites"] = []
    return registry, inventory


def _jom_lifecycle_save_sources_v1(registry, inventory):
    if "_recalculate_registry_summary" in globals():
        _recalculate_registry_summary(registry)
    else:
        registry["generated_at_utc"] = now_utc()
    inventory["generated_at_utc"] = now_utc()
    write_json(DATA_PATH / "site_registry.json", registry)
    write_json(DATA_PATH / "estate_admin_site_inventory_v1.json", inventory)


def _jom_lifecycle_mark_approval_pending_v1(site_key, actor="operator"):
    registry, inventory = _jom_lifecycle_load_sources_v1()
    registry_site = _jom_lifecycle_find_v1(registry["sites"], site_key)
    inventory_site = _jom_lifecycle_find_v1(inventory["sites"], site_key)
    if registry_site is None and inventory_site is not None:
        registry_site = dict(inventory_site)
        registry["sites"].append(registry_site)
    if registry_site is None and inventory_site is None:
        return None, None, registry, inventory
    key, record = _jom_lifecycle_base_record_v1(site_key, registry_site, inventory_site)
    record.update({
        "classification": "approval_pending",
        "lifecycle": "approval_pending",
        "is_monitored": False,
        "monitored": False,
        "approved_monitored": False,
        "collector_onboarding_status": "approval_pending",
        "status": "pending",
        "health_status": "Review",
        "action_required": "validate_access",
        "approved_for_monitoring_at_utc": now_utc(),
        "approved_for_monitoring_by": actor,
        "truth_source": "site_review_lifecycle_consolidated_v1",
    })
    registry_site.clear()
    registry_site.update(record)
    if inventory_site is not None:
        inventory_site.update(record)
    _jom_lifecycle_save_sources_v1(registry, inventory)
    return record, inventory_site, registry, inventory


def _jom_lifecycle_mark_monitored_v1(site_key, actor="operator"):
    registry, inventory = _jom_lifecycle_load_sources_v1()
    registry_site = _jom_lifecycle_find_v1(registry["sites"], site_key)
    inventory_site = _jom_lifecycle_find_v1(inventory["sites"], site_key)
    if registry_site is None and inventory_site is not None:
        registry_site = dict(inventory_site)
        registry["sites"].append(registry_site)
    if registry_site is None and inventory_site is None:
        return None, None, registry, inventory
    key, record = _jom_lifecycle_base_record_v1(site_key, registry_site, inventory_site)
    record.update({
        "classification": "monitored",
        "lifecycle": "monitored",
        "is_monitored": True,
        "monitored": True,
        "approved_monitored": True,
        "collector_onboarding_status": "monitoring_enabled",
        "status": "ok",
        "health_status": "OK",
        "action_required": None,
        "monitoring_enabled_at_utc": now_utc(),
        "monitoring_enabled_by": actor,
        "truth_source": "site_review_lifecycle_consolidated_v1",
    })
    registry_site.clear()
    registry_site.update(record)
    if inventory_site is not None:
        inventory_site.update(record)
    _jom_lifecycle_save_sources_v1(registry, inventory)
    return record, inventory_site, registry, inventory


def _jom_lifecycle_mark_review_v1(site_key, actor="operator"):
    registry, inventory = _jom_lifecycle_load_sources_v1()
    registry_site = _jom_lifecycle_find_v1(registry["sites"], site_key)
    inventory_site = _jom_lifecycle_find_v1(inventory["sites"], site_key)
    if registry_site is None and inventory_site is not None:
        registry_site = dict(inventory_site)
        registry["sites"].append(registry_site)
    if registry_site is None and inventory_site is None:
        return None, None, registry, inventory
    key, record = _jom_lifecycle_base_record_v1(site_key, registry_site, inventory_site)
    record.update({
        "classification": "discovered",
        "lifecycle": "stopped_monitoring",
        "is_monitored": False,
        "monitored": False,
        "approved_monitored": False,
        "collector_onboarding_status": "review_required",
        "status": "review",
        "health_status": "Review",
        "action_required": "review_monitoring_state",
        "monitoring_stopped_at_utc": now_utc(),
        "monitoring_stopped_by": actor,
        "truth_source": "site_review_lifecycle_consolidated_v1",
    })
    registry_site.clear()
    registry_site.update(record)
    if inventory_site is not None:
        inventory_site.update(record)
    _jom_lifecycle_save_sources_v1(registry, inventory)
    return record, inventory_site, registry, inventory



# JOM_SITE_REVIEW_ACCESS_GATE_OWNER_ALIGNMENT_V1 START
# Owner implementation for Site Review access gating.
# Current OAuth coverage is the authority for access validation.
# Stored validation history is useful evidence, but it must not override current authorization_required=true.
def _jom_access_gate_current_coverage_v1(site_key, actor="access-gate"):
    coverage = _oauth_coverage_payload(site_key) if "_oauth_coverage_payload" in globals() else {}
    if not isinstance(coverage, dict):
        coverage = {}

    site_key_norm = _jom_lifecycle_norm_v1(site_key) if "_jom_lifecycle_norm_v1" in globals() else str(site_key or "").strip().lower()
    authorization_required = bool(coverage.get("authorization_required") is True)
    coverage_status = str(coverage.get("coverage_status") or coverage.get("status") or "").strip().lower()
    matched_resource = coverage.get("matched_resource") if isinstance(coverage.get("matched_resource"), dict) else None

    access_valid = bool(
        not authorization_required
        and coverage_status == "validated"
        and matched_resource
    )

    if access_valid:
        validation = {
            "access_valid": True,
            "status": "ok",
            "site_key": site_key_norm,
            "site_name": site_key_norm,
            "method": "oauth_coverage_validation",
            "validated_at_utc": now_utc(),
            "actor": actor,
            "reason": "Current OAuth coverage validates access to this Atlassian site.",
            "coverage_status": coverage_status,
        }
        if "_jom_estate_write_access_validation_record" in globals():
            try:
                _jom_estate_write_access_validation_record(site_key_norm, validation)
            except Exception:
                pass
        return {
            "ok": True,
            "site_key": site_key_norm,
            "access_valid": True,
            "validation": validation,
            "coverage": coverage,
            "authorization_required": False,
            "authorization_url": None,
        }

    validation = {
        "access_valid": False,
        "status": "blocked",
        "site_key": site_key_norm,
        "site_name": site_key_norm,
        "method": "oauth_coverage_validation",
        "validated_at_utc": now_utc(),
        "actor": actor,
        "reason": coverage.get("reason") or "Current OAuth coverage does not validate access to this Atlassian site.",
        "coverage_status": coverage_status or "authorization_required",
    }
    return {
        "ok": False,
        "site_key": site_key_norm,
        "access_valid": False,
        "validation": validation,
        "coverage": coverage,
        "authorization_required": True,
        "authorization_url": coverage.get("authorization_url"),
        "action": "open_authorization_url" if coverage.get("authorization_url") else None,
        "message": "Atlassian authorisation is required before monitoring can be enabled.",
    }
# JOM_SITE_REVIEW_ACCESS_GATE_OWNER_ALIGNMENT_V1 END

def _jom_lifecycle_latest_validation_v1(site_key):
    gate = _jom_access_gate_current_coverage_v1(site_key, actor="enable-monitoring-precheck")
    validation = gate.get("validation") if isinstance(gate, dict) else None
    if isinstance(validation, dict) and validation.get("access_valid") is True and validation.get("status") == "ok":
        return validation
    return {}
def _jom_lifecycle_inventory_only_correction_v1():
    registry, inventory = _jom_lifecycle_load_sources_v1()
    registry_monitored = {_jom_lifecycle_key_v1(site) for site in registry["sites"] if _jom_lifecycle_is_monitored_v1(site)}
    changed = []
    for site in inventory["sites"]:
        key = _jom_lifecycle_key_v1(site)
        if key and _jom_lifecycle_is_monitored_v1(site) and key not in registry_monitored:
            site.update({
                "classification": "approval_pending",
                "lifecycle": "approval_pending",
                "is_monitored": False,
                "monitored": False,
                "approved_monitored": False,
                "collector_onboarding_status": "approval_pending",
                "status": "pending",
                "health_status": "Review",
                "action_required": "validate_access",
                "truth_source": "site_review_lifecycle_consolidated_inventory_guard_v1",
            })
            changed.append(key)
    _jom_lifecycle_save_sources_v1(registry, inventory)
    return changed
# JOM_SITE_REVIEW_LIFECYCLE_CONSOLIDATED_V1 END



# JOM_ENABLE_MONITORING_SELECTED_SITE_GUARD_V1 START
# Owner implementation guard: Enable Monitoring may only promote the requested site.
# Other OAuth-visible review sites must remain in review until explicitly selected.
def _jom_lifecycle_guard_review_keyset_v1(inventory, requested_site_key):
    requested = _jom_lifecycle_norm_v1(requested_site_key)
    protected = set()
    rows = inventory.get("sites", []) if isinstance(inventory, dict) else []
    for site in rows if isinstance(rows, list) else []:
        if not isinstance(site, dict):
            continue
        key = _jom_lifecycle_key_v1(site)
        if not key or key == requested:
            continue
        if site.get("estate_truth_included") is not True:
            continue
        if not _jom_lifecycle_is_monitored_v1(site):
            protected.add(key)
    return protected


def _jom_lifecycle_canonical_registry_site_v1(site):
    key = _jom_lifecycle_key_v1(site)
    url = site.get("site_url") or site.get("url") or ("https://" + key + ".atlassian.net" if key else "")
    return {
        "site_key": key,
        "key": key,
        "site_name": site.get("site_name") or site.get("name") or key,
        "name": site.get("name") or site.get("site_name") or key,
        "site_url": url,
        "url": url,
        "cloud_id": site.get("cloud_id"),
        "classification": "monitored",
        "lifecycle": "monitored",
        "is_monitored": True,
        "monitored": True,
        "approved_monitored": True,
        "collector_onboarding_status": "monitoring_enabled",
        "status": "ok",
        "health_status": "OK",
        "action_required": None,
        "sources": site.get("sources") if isinstance(site.get("sources"), list) else [],
        "evidence_levels": site.get("evidence_levels") if isinstance(site.get("evidence_levels"), list) else [],
        "truth_source": "site_review_enable_monitoring_selected_site_guard_v1",
    }


def _jom_lifecycle_enforce_selected_enable_monitoring_v1(requested_site_key, registry, inventory, protected_review_keys):
    requested = _jom_lifecycle_norm_v1(requested_site_key)
    rows = inventory.get("sites", []) if isinstance(inventory, dict) else []
    monitored_sites = []
    review_keys = set()
    requested_inventory_record = None

    for site in rows if isinstance(rows, list) else []:
        if not isinstance(site, dict):
            continue
        key = _jom_lifecycle_key_v1(site)
        if not key:
            continue
        if key == requested:
            requested_inventory_record = site
        if key in protected_review_keys and key != requested:
            site.update({
                "classification": "discovered",
                "lifecycle": "pending_review",
                "is_monitored": False,
                "monitored": False,
                "approved_monitored": False,
                "collector_onboarding_status": "review_required",
                "status": "review",
                "health_status": "Review",
                "action_required": "review_live_inventory_status",
                "truth_source": "site_review_enable_monitoring_selected_site_guard_v1",
            })

    for site in rows if isinstance(rows, list) else []:
        if not isinstance(site, dict):
            continue
        key = _jom_lifecycle_key_v1(site)
        if not key:
            continue
        if site.get("estate_truth_included") is True and _jom_lifecycle_is_monitored_v1(site):
            monitored_sites.append(_jom_lifecycle_canonical_registry_site_v1(site))
        elif site.get("estate_truth_included") is True:
            review_keys.add(key)

    registry["schema"] = "jom-site-registry-oauth-estate-truth-v1"
    registry["source"] = "runtime/data/estate_admin_site_inventory_v1.json"
    registry["source_policy"] = "Site Registry contains monitored OAuth-estate sites only. Enable Monitoring may only promote the requested site."
    registry["sites"] = monitored_sites
    registry["review_site_keys"] = sorted(review_keys)
    registry["summary"] = {
        "total_sites": len(monitored_sites),
        "monitored_count": len(monitored_sites),
        "discovered_count": len(review_keys),
        "ignored_count": 0,
        "pending_onboarding_count": len(review_keys),
        "review_count": len(review_keys),
        "coverage_percent": round((len(monitored_sites) / (len(monitored_sites) + len(review_keys))) * 100) if (len(monitored_sites) + len(review_keys)) else 0,
    }
    registry["generated_at_utc"] = now_utc()

    inventory["generated_at_utc"] = now_utc()
    inventory.setdefault("summary", {})
    inventory["summary"].update({
        "oauth_estate_site_count": len(monitored_sites) + len(review_keys),
        "monitored_count": len(monitored_sites),
        "review_count": len(review_keys),
    })

    write_json(DATA_PATH / "site_registry.json", registry)
    write_json(DATA_PATH / "estate_admin_site_inventory_v1.json", inventory)

    requested_registry_record = _jom_lifecycle_find_v1(registry.get("sites", []), requested)
    return requested_registry_record, requested_inventory_record, registry, inventory
# JOM_ENABLE_MONITORING_SELECTED_SITE_GUARD_V1 END

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
    body = request.get_json(silent=True) or {}
    actor = body.get("actor") or "operator"
    _registry_before, _inventory_before = _jom_lifecycle_load_sources_v1()
    protected_review_keys = _jom_lifecycle_guard_review_keyset_v1(_inventory_before, site_key)
    validation = _jom_lifecycle_latest_validation_v1(site_key)
    if not validation:
        return jsonify({"ok": False, "error": "access_not_validated", "site_key": _jom_lifecycle_norm_v1(site_key), "message": "Credential access must be validated before monitoring can be enabled."}), 409
    record, inventory_record, _registry, _inventory = _jom_lifecycle_mark_monitored_v1(site_key, actor=actor)
    if record is None and inventory_record is None:
        return jsonify({"ok": False, "error": "site_not_found", "site_key": site_key}), 404
    if "_jom_lifecycle_enforce_selected_enable_monitoring_v1" in globals():
        record, inventory_record, _registry, _inventory = _jom_lifecycle_enforce_selected_enable_monitoring_v1(site_key, _registry, _inventory, protected_review_keys)
    if "_jom_lifecycle_audit_event_v1" in globals():
        _jom_lifecycle_audit_event_v1(site_key, "enable_monitoring", actor=actor, state="monitored", message="Monitoring enabled. Selected site promoted into Site Registry.", source="site_review_enable_monitoring")
    return jsonify({
        "ok": True,
        "message": "Monitoring enabled. Only the selected site has been promoted into the monitored Site Registry.",
        "site_key": _jom_lifecycle_norm_v1(site_key),
        "classification": "monitored",
        "lifecycle": "monitored",
        "record": record,
        "inventory_record": inventory_record,
        "protected_review_keys": sorted(protected_review_keys),
        "validation": validation,
    })
@app.route("/review-queue")
def review_queue():
    return redirect("/estate#discovered-sites", code=302)

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



# JOM site review live contract helper v1
# This helper avoids live_named_access_contract and live_named_access_contract as route truth.
def _jom_contract_payload_from_route_v1(route_path):
    """Return contract payload from known owner route functions without route-table indirection."""
    try:
        route_map = {
            "/estate/product-access": estate_product_access,
            "/admin/truth": admin_truth,
            "/users/footprint": user_footprint,
            "/registry/sites": site_registry,
            "/api/source-state": api_source_state_legacy,
        }
        fn = route_map.get(str(route_path or ""))
        if not callable(fn):
            return {"available": False, "reason": f"route not mapped: {route_path}"}
        value = fn()
        if hasattr(value, "get_json"):
            return value.get_json(silent=True) or {}
        if isinstance(value, tuple) and value:
            first = value[0]
            if hasattr(first, "get_json"):
                return first.get_json(silent=True) or {}
            if isinstance(first, dict):
                return first
        if isinstance(value, dict):
            return value
        return {"available": True, "raw_type": type(value).__name__}
    except Exception as exc:
        return {"available": False, "reason": str(exc)}
def _jom_unwrap_contract_data_v1(payload):
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload.get("data") or {}
    return payload if isinstance(payload, dict) else {}


def _jom_find_site_record_v1(site_key, registry_data, product_data):
    wanted = str(site_key or "").strip().lower()
    candidates = []
    reg = _jom_unwrap_contract_data_v1(registry_data)
    if isinstance(reg.get("sites"), list):
        candidates.extend(reg.get("sites") or [])
    if isinstance(registry_data.get("sites"), list):
        candidates.extend(registry_data.get("sites") or [])
    prod = _jom_unwrap_contract_data_v1(product_data)
    if isinstance(prod.get("sites"), list):
        candidates.extend(prod.get("sites") or [])
    if isinstance(product_data.get("sites"), list):
        candidates.extend(product_data.get("sites") or [])
    for item in candidates:
        if not isinstance(item, dict):
            continue
        values = [item.get("site_key"), item.get("site_name"), item.get("cloud_id"), item.get("site_url")]
        aliases = item.get("aliases") if isinstance(item.get("aliases"), list) else []
        values.extend(aliases)
        for value in values:
            if value is not None and str(value).strip().lower() == wanted:
                return item
    return {}


def _jom_site_live_review_contract(site_key):
    from datetime import datetime, timezone
    served = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    product_access = _jom_contract_payload_from_route_v1("/estate/product-access")
    admin_truth = _jom_contract_payload_from_route_v1("/admin/truth")
    user_footprint = _jom_contract_payload_from_route_v1("/users/footprint")
    registry = _jom_contract_payload_from_route_v1("/registry/sites")
    source_state = _jom_contract_payload_from_route_v1("/api/source-state")
    site = _jom_find_site_record_v1(site_key, registry, product_access)
    product_data = _jom_unwrap_contract_data_v1(product_access)
    matching_rows = []
    for row in product_data.get("sites", []) if isinstance(product_data.get("sites"), list) else []:
        if isinstance(row, dict) and str(row.get("site_key", "")).lower() == str(site_key).lower():
            matching_rows.append(row)
    safe_to_show_named = False
    footprint_data = _jom_unwrap_contract_data_v1(user_footprint)
    if isinstance(footprint_data, dict):
        safe_to_show_named = bool(footprint_data.get("safe_to_show_named_access_ui"))
    return {
        "schema": "jom-site-review-live-contract-v1",
        "contract_type": "live_site_review_contract",
        "site_key": site_key,
        "served_at_utc": served,
        "source_policy": "Composed from backend live contracts: /estate/product-access, /admin/truth, /users/footprint, /registry/sites, /api/source-state. No live_named_access_contract or live_named_access_contract route fallback is used.",
        "status": "ok" if product_access.get("available", True) is not False else "review",
        "site": site,
        "product_access": product_access,
        "product_access_site_rows": matching_rows,
        "admin_truth": admin_truth,
        "user_footprint": user_footprint,
        "registry": registry,
        "source_state": source_state,
        "controls": {
            "safe_to_show_named_access_ui": safe_to_show_named,
            "named_access_static_files_used": False,
        },
        "recommended_actions": [] if site else ["Site was not matched in live registry/product access contracts."],
    }

@app.route("/api/site-review/<path:site_key>/live")
def api_site_review_live_contract(site_key):
    return jsonify(_jom_site_live_review_contract(site_key))



# --- JOM ESTATE WORKSPACE CONTRACT v1 START ---
@app.route("/api/operator/status")
def api_operator_live_status_contract():
    return jsonify(build_operator_summary())


@app.route("/api/operator/insights")
def api_operator_live_insights_contract():
    return jsonify(build_operator_surface())


@app.route("/api/operator/drilldowns")
def api_operator_live_drilldowns_contract():
    return jsonify(build_operator_surface())


@app.route("/api/operator/role-views")
def api_operator_live_role_views_contract():
    return jsonify(build_operator_surface())


@app.route("/api/operator/ui-view")
def api_operator_live_ui_view_contract():
    return jsonify(build_operator_surface())



# --- JOM WORKSPACE CONTRACT CONSOLIDATION v1 START ---
def _jom_workspace_contract_unwrap_v1(payload):
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload.get("data") or {}
    return payload if isinstance(payload, dict) else {}


def _jom_workspace_contract_source_status_v1(source_state):
    source_state = _jom_workspace_contract_unwrap_v1(source_state)
    freshness_contract = source_state.get("source_freshness") or {}
    reliability_contract = source_state.get("source_reliability") or {}
    freshness = _jom_workspace_contract_unwrap_v1(freshness_contract)
    reliability = _jom_workspace_contract_unwrap_v1(reliability_contract)
    freshness_summary = freshness.get("summary") if isinstance(freshness.get("summary"), dict) else {}
    reliability_summary = reliability.get("summary") if isinstance(reliability.get("summary"), dict) else {}
    freshness_state = str(freshness_summary.get("overall_state") or freshness.get("overall_state") or "").lower()
    reliability_state = str(reliability.get("overall_status") or reliability_contract.get("status") or "").lower()
    try:
        issue_count = int(reliability_summary.get("issue_count") or 0)
    except Exception:
        issue_count = 0
    if freshness_state == "critical" or reliability_state == "critical":
        return "Critical"
    if freshness_state in {"attention", "stale"} or reliability_state == "attention" or issue_count > 0:
        return "Review"
    if freshness_state in {"ok", "current"} or reliability_state == "ok":
        return "OK"
    return "Review"


def _jom_workspace_contract_user_metric_v1(source_state, estate_product, user_footprint):
    source_state = _jom_workspace_contract_unwrap_v1(source_state)
    estate_product = _jom_workspace_contract_unwrap_v1(estate_product)
    user_footprint = _jom_workspace_contract_unwrap_v1(user_footprint)
    live_product = source_state.get("live_product_access") or {}
    candidates = [
        live_product.get("total_jira_product_user_count"),
        (estate_product.get("summary") or {}).get("total_jira_product_user_count"),
    ]
    for value in candidates:
        try:
            if value is not None:
                return int(value)
        except Exception:
            pass
    summary = user_footprint.get("summary") if isinstance(user_footprint.get("summary"), dict) else {}
    for value in [summary.get("users_analyzed"), summary.get("human_users")]:
        try:
            if value is not None:
                return int(value)
        except Exception:
            pass
    return None


def _jom_workspace_contract_registry_summary_v1(registry):
    registry = _jom_workspace_contract_unwrap_v1(registry)
    sites = registry.get("sites") if isinstance(registry.get("sites"), list) else []
    summary = registry.get("summary") if isinstance(registry.get("summary"), dict) else {}
    try:
        total = int(summary.get("total_sites") if summary.get("total_sites") is not None else len(sites))
    except Exception:
        total = len(sites)
    try:
        monitored = int(summary.get("monitored_count") if summary.get("monitored_count") is not None else len([s for s in sites if isinstance(s, dict) and (s.get("is_monitored") or s.get("classification") == "monitored")]))
    except Exception:
        monitored = 0
    try:
        discovered = int(summary.get("discovered_count") if summary.get("discovered_count") is not None else len([s for s in sites if isinstance(s, dict) and s.get("classification") == "discovered"]))
    except Exception:
        discovered = 0
    try:
        pending = int(summary.get("pending_onboarding_count") if summary.get("pending_onboarding_count") is not None else len([s for s in sites if isinstance(s, dict) and str(s.get("collector_onboarding_status") or "").lower().startswith("pending")]))
    except Exception:
        pending = 0
    coverage = round((monitored / total) * 100) if total else 0
    return {
        "total_sites": total,
        "monitored_count": monitored,
        "discovered_count": discovered,
        "pending_onboarding_count": pending,
        "review_count": discovered + pending,
        "coverage_percent": coverage,
        "sites": sites,
    }



# --- JOM USERS METRIC CONTRACT SEPARATION v1 START ---
def _jom_active_users_unavailable_metric_v1():
    """Headline Users authority placeholder.

    Current rule: headline Users must be unique active Atlassian users from
    proven OAuth/Admin live authority. No such authority is currently proven,
    so the value must be unavailable rather than replaced with product access.
    """
    return {
        "metric": None,
        "metric_label": "Active users unavailable",
        "source": "oauth_admin_active_users_unavailable",
        "available": False,
        "definition": "Unique active Atlassian users from OAuth/Admin live authority. No proven active-user authority is currently wired.",
    }


def _jom_product_access_assignments_metric_v1(product_users):
    return {
        "metric": product_users,
        "metric_label": "Product access assignments",
        "source": "estate_product_access.summary.total_jira_product_user_count",
        "available": product_users is not None,
        "definition": "Assignment count across Jira product/site access. One person may count more than once. Not headline Users.",
    }
# --- JOM USERS METRIC CONTRACT SEPARATION v1 END ---

# --- JOM WORKSPACE CONTRACT CACHED READ PATH v1 START ---
# Fast workspace contracts for page load.
# These endpoints read generated truth outputs and do not run live collectors on page load.
def _jom_cached_read_json_v1(filename: str, default=None):
    if default is None:
        default = {}
    try:
        path = DATA_PATH / filename
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"_read_error": str(exc), "_file": filename}


def _jom_cached_now_v1() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _jom_cached_source_state_v1():
    return {
        "schema": "jom-cached-source-state-v1",
        "served_at_utc": _jom_cached_now_v1(),
        "source_freshness": _jom_cached_read_json_v1("source_freshness_audit.json", {}),
        "source_reliability": _jom_cached_read_json_v1("source_reliability_status.json", {}),
        "runtime_status": _jom_cached_read_json_v1("runtime_execution_status.json", {}),
    }


def _jom_cached_registry_summary_v1(registry):
    sites = registry.get("sites", []) if isinstance(registry, dict) else []
    summary = registry.get("summary", {}) if isinstance(registry, dict) else {}
    total = summary.get("total_sites") if summary.get("total_sites") is not None else len(sites)
    monitored = summary.get("monitored_count") if summary.get("monitored_count") is not None else len([s for s in sites if isinstance(s, dict) and (s.get("is_monitored") or s.get("classification") == "monitored")])
    discovered = summary.get("discovered_count") if summary.get("discovered_count") is not None else len([s for s in sites if isinstance(s, dict) and s.get("classification") == "discovered"])
    pending = summary.get("pending_onboarding_count") if summary.get("pending_onboarding_count") is not None else len([s for s in sites if isinstance(s, dict) and "pending" in str(s.get("collector_onboarding_status", "")).lower()])
    return {"total_sites": total, "monitored_count": monitored, "discovered_count": discovered, "pending_onboarding_count": pending}


def _jom_build_cached_operator_alerts_v1(admin_truth, registry):
    alerts = []
    admin_status = str((admin_truth or {}).get("status") or ((admin_truth or {}).get("summary") or {}).get("status") or "").lower()
    reg_summary = _jom_cached_registry_summary_v1(registry)
    discovered = reg_summary.get("discovered_count") or 0
    if discovered:
        alerts.append({"level": "info", "category": "registry", "title": "Discovered sites need classification", "reason": "One or more discovered sites are not yet monitored.", "source": "site_registry.json", "value": discovered, "recommended_action": "Review site registry and onboarding decisions"})
    return alerts



def _jom_command_centre_users_metric_contract_payload_v1(user_footprint, product_users):
    payload = _jom_active_users_unavailable_metric_v1()
    payload["named_access_detail_guarded"] = True
    payload["product_access_assignments"] = _jom_product_access_assignments_metric_v1(product_users)
    return payload

# === JOM COMMAND CENTRE WORKSPACE TRUTH ALIGNMENT v1 START ===

def _jom_cmdc_truth_inventory_sites_v1(inventory):
    rows = inventory.get("sites") if isinstance(inventory, dict) and isinstance(inventory.get("sites"), list) else []
    if "_jom_current_state_filter_sites_v1" in globals():
        return _jom_current_state_filter_sites_v1(rows)
    return rows

def _jom_cmdc_truth_registry_map_v1(registry):
    out = {}
    sites = registry.get("sites") if isinstance(registry, dict) and isinstance(registry.get("sites"), list) else []
    for site in sites:
        if isinstance(site, dict):
            key = str(site.get("site_key") or site.get("key") or site.get("site_name") or site.get("name") or "").strip().lower()
            if key:
                out[key] = site
    return out

def _jom_cmdc_truth_site_from_inventory_v1(row, registry_map):
    key = str(row.get("site_key") or row.get("key") or row.get("name") or "").strip().lower()
    base = dict(registry_map.get(key, {}))
    lifecycle = str(row.get("lifecycle") or base.get("classification") or "discovery_gap").strip().lower()
    monitored = lifecycle == "monitored" or row.get("approved_monitored") is True
    base.update({
        "site_key": key,
        "site_name": row.get("name") or row.get("site_name") or base.get("site_name") or key,
        "site_url": row.get("url") or row.get("site_url") or base.get("site_url") or base.get("url") or "",
        "cloud_id": row.get("cloud_id") or base.get("cloud_id"),
        "sources": row.get("sources") or base.get("sources") or [],
        "evidence_levels": row.get("evidence_levels") or base.get("evidence_levels") or [],
        "classification": "monitored" if monitored else lifecycle,
        "lifecycle": lifecycle,
        "is_monitored": bool(monitored),
        "monitored": bool(monitored),
        "collector_onboarding_status": "monitoring_enabled" if monitored else lifecycle,
        "action_required": row.get("action_required"),
        "approved_monitored": bool(row.get("approved_monitored") is True),
        "in_registry": bool(row.get("in_registry") is True),
        "status": "ok" if monitored else "review",
    })
    return base


def _jom_cmdc_truth_registry_from_estate_inventory_v1(inventory, registry):
    rows = _jom_cmdc_truth_inventory_sites_v1(inventory)
    registry_map = _jom_cmdc_truth_registry_map_v1(registry) if "_jom_cmdc_truth_registry_map_v1" in globals() else {}
    sites = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = _jom_current_state_site_key_v1(row) if "_jom_current_state_site_key_v1" in globals() else str(row.get("site_key") or row.get("key") or "").lower()
        base = dict(registry_map.get(key, {}))
        base.update(row)
        if "_jom_current_state_normalise_site_v1" in globals():
            base = _jom_current_state_normalise_site_v1(base)
        sites.append(base)
    summary = _jom_current_state_summary_v1(sites) if "_jom_current_state_summary_v1" in globals() else {"total_sites": len(sites)}
    return {
        "schema": "jom-site-registry-current-state-authority-v1",
        "generated_at_utc": inventory.get("generated_utc") or inventory.get("generated_at_utc") if isinstance(inventory, dict) else None,
        "source": "live_oauth_runtime_authority",
        "source_policy": "Current state is live OAuth/runtime authority only. Historical lifecycle and non-estate discoveries are excluded from active UI truth.",
        "summary": summary,
        "sites": sites,
    }

def _jom_cmdc_truth_append_review_alert_v1(alerts, registry_summary):
    alerts = alerts if isinstance(alerts, list) else []
    alerts = [item for item in alerts if not (isinstance(item, dict) and item.get("source") == "site_registry.json" and item.get("title") == "Discovered sites need classification")]
    review_count = int((registry_summary or {}).get("review_count") or 0)
    if review_count > 0 and not any(isinstance(item, dict) and item.get("category") == "estate_lifecycle" for item in alerts):
        item_label = "site" if review_count == 1 else "sites"
        alerts.append({
            "level": "info",
            "category": "estate_lifecycle",
            "title": "Estate review required",
            "reason": f"{review_count} discovered {item_label} require lifecycle review before the monitored estate can be considered complete.",
            "source": "estate_admin_site_inventory_v1.json",
            "source_label": "Live Estate inventory",
            "value": review_count,
            "recommended_action": "Open Estate review and complete lifecycle decisions.",
            "action_label": "Open Estate review",
        })
    return alerts
# === JOM COMMAND CENTRE WORKSPACE TRUTH ALIGNMENT v1 END ===


# === JOM COMMAND CENTRE ESTATE METRICS ALIGNMENT v1 START ===
# Align Command Centre estate counts with the authenticated Estate display model.
def _jom_cmdc_estate_metric_key_v1(site):
    if not isinstance(site, dict):
        return ""
    value = site.get("site_key") or site.get("key") or site.get("site_name") or site.get("name") or site.get("url") or site.get("site_url") or ""
    text = str(value).strip().lower()
    if text.startswith("http") and ".atlassian.net" in text:
        text = text.split("//", 1)[-1].split(".atlassian.net", 1)[0]
    return text

def _jom_cmdc_estate_signals_v1(site):
    if not isinstance(site, dict):
        site = {}
    sources = site.get("sources") if isinstance(site.get("sources"), list) else []
    evidence = site.get("evidence_levels") if isinstance(site.get("evidence_levels"), list) else []
    values = [str(v).strip().lower() for v in list(sources) + list(evidence)]
    lifecycle = str(site.get("lifecycle") or site.get("classification") or site.get("collector_onboarding_status") or site.get("status") or "").strip().lower()
    monitored = bool(site.get("approved_monitored") is True or site.get("is_monitored") is True or site.get("monitored") is True or lifecycle == "monitored")
    return values, lifecycle, monitored

def _jom_cmdc_estate_has_live_evidence_v1(site):
    live = {"live_oauth_accessible_resources", "live_admin_event_reference", "oauth_accessible_resources", "admin_org_events", "live_admin_org", "live_product_access"}
    manual = {"manual_unverified", "manual_validation_target", "known_from_support_case_manual_only", "known_from_admin_screenshot_or_support_case_manual_only", "static", "cached", "unknown"}
    values, lifecycle, monitored = _jom_cmdc_estate_signals_v1(site)
    if not values:
        return False
    return any(v in live for v in values) and not all(v in manual for v in values)

def _jom_cmdc_estate_display_summary_v1(registry):
    registry = registry if isinstance(registry, dict) else {}
    sites = registry.get("sites") if isinstance(registry.get("sites"), list) else []
    by_key = {}
    for site in sites:
        key = _jom_cmdc_estate_metric_key_v1(site)
        if not key:
            continue
        current = by_key.setdefault(key, {"live": False, "monitored": False, "review": False})
        values, lifecycle, monitored = _jom_cmdc_estate_signals_v1(site)
        has_live = _jom_cmdc_estate_has_live_evidence_v1(site)
        current["live"] = current["live"] or has_live
        current["monitored"] = current["monitored"] or (has_live and monitored)
        current["review"] = current["review"] or (has_live and not monitored and lifecycle not in {"deletion", "deleted", "retired", "archived"})
    monitored_count = len([v for v in by_key.values() if v["monitored"]])
    review_count = len([v for v in by_key.values() if v["review"]])
    total_sites = monitored_count + review_count
    coverage = round((monitored_count / total_sites) * 100) if total_sites else 0
    return {
        "total_sites": total_sites,
        "monitored_count": monitored_count,
        "discovered_count": review_count,
        "pending_onboarding_count": review_count,
        "review_count": review_count,
        "coverage_percent": coverage,
    }

if "_jom_cmdc_truth_registry_from_estate_inventory_v1" in globals():
    _jom_cmdc_truth_registry_from_estate_inventory_v1_original = _jom_cmdc_truth_registry_from_estate_inventory_v1
    def _jom_cmdc_truth_registry_from_estate_inventory_v1(inventory, registry):
        payload = _jom_cmdc_truth_registry_from_estate_inventory_v1_original(inventory, registry)
        if isinstance(payload, dict):
            aligned = _jom_cmdc_estate_display_summary_v1(payload)
            payload["summary"] = dict(payload.get("summary") or {})
            payload["summary"].update(aligned)
            payload["source_policy"] = "Command Centre estate metrics aligned to authenticated Estate display model. Manual-only records are excluded from totals."
        return payload
# === JOM COMMAND CENTRE ESTATE METRICS ALIGNMENT v1 END ===
def _jom_workspace_command_centre_cached_contract_v1():
    served = _jom_cached_now_v1()
    registry = _jom_cached_read_json_v1("site_registry.json", {})
    estate_admin_inventory = _jom_cached_read_json_v1("estate_admin_site_inventory_v1.json", {})
    user_footprint = _jom_cached_read_json_v1("user_footprint.json", {})
    estate_product_access = _jom_cached_read_json_v1("estate_product_access.json", {})
    estate_access_truth = _jom_cached_read_json_v1("estate_access_truth.json", {})
    admin_truth = _jom_cached_read_json_v1("admin_truth_v2.json", {})
    organisation_discovery = _jom_cached_read_json_v1("organisation_discovery.json", {})
    runtime_status = _jom_cached_read_json_v1("runtime_execution_status.json", {})
    source_state = _jom_cached_source_state_v1()

    registry = _jom_cmdc_truth_registry_from_estate_inventory_v1(estate_admin_inventory, registry)
    registry_summary = registry.get("summary") if isinstance(registry, dict) and isinstance(registry.get("summary"), dict) else _jom_cached_registry_summary_v1(registry)

    product_summary = estate_product_access.get("summary", {}) if isinstance(estate_product_access, dict) else {}
    product_users = product_summary.get("total_jira_product_user_count")

    if product_users is None and isinstance(admin_truth, dict):
        product_users = ((admin_truth.get("live_product_access_truth") or {}).get("summary") or {}).get("total_jira_product_user_count")

    organisation_summary = {
        "metric": organisation_discovery.get("organisation_count") if isinstance(organisation_discovery, dict) else None,
        "metric_label": "Live Atlassian organisations",
        "live_collection": organisation_discovery.get("live_collection") if isinstance(organisation_discovery, dict) else None,
        "authority": organisation_discovery.get("authority") if isinstance(organisation_discovery, dict) else None,
        "token_source": organisation_discovery.get("token_source") if isinstance(organisation_discovery, dict) else None,
        "source": "runtime/data/organisation_discovery.json",
        "organisations": organisation_discovery.get("organisations", []) if isinstance(organisation_discovery, dict) else [],
    }

    alerts = _jom_build_cached_operator_alerts_v1(admin_truth, registry)
    alerts = _jom_cmdc_truth_append_review_alert_v1(alerts, registry_summary)

    data = {
        "registry": registry,
        "registry_summary": registry_summary,
        "organisations": organisation_summary,
        "users": _jom_command_centre_users_metric_contract_payload_v1(user_footprint, product_users),
        "users_metric": _jom_active_users_unavailable_metric_v1(),
        "product_access_metric": _jom_product_access_assignments_metric_v1(product_users),
        "source_state": source_state,
        "operator_summary": {
            "schema": "jom-operator-summary-fast-read-v1",
            "generated_at_utc": served,
            "posture": "warning" if alerts else "ok",
            "runtime": runtime_status,
            "alert_summary": {
                "critical": len([a for a in alerts if a.get("level") == "critical"]),
                "warning": len([a for a in alerts if a.get("level") == "warning"]),
                "info": len([a for a in alerts if a.get("level") == "info"]),
                "total": len(alerts),
            },
            "top_alerts": [],
            "top_alerts_source": "operator_alerts.alerts",
            "admin_truth": {
                "status": admin_truth.get("status") if isinstance(admin_truth, dict) else None,
                "severity": admin_truth.get("severity") if isinstance(admin_truth, dict) else None,
            },
        },
        "operator_alerts": {"count": len(alerts), "alerts": alerts},
        "estate_product_access": estate_product_access,
        "estate_access_truth": estate_access_truth,
        "admin_truth": admin_truth,
    }

    payload = {
        "schema": "jom-workspace-command-centre-contract-v1-fast-read",
        "served_at_utc": served,
        "source_policy": "Fast workspace contract from generated truth outputs. No live collectors run during page load.",
        "data": data,
    }
    payload.update(data)
    return payload


def _jom_workspace_estate_cached_contract_v1():
    served = _jom_cached_now_v1()
    registry = _jom_cached_read_json_v1("site_registry.json", {})
    estate_admin_inventory = _jom_cached_read_json_v1("estate_admin_site_inventory_v1.json", {})
    user_footprint = _jom_cached_read_json_v1("user_footprint.json", {})
    estate_product_access = _jom_cached_read_json_v1("estate_product_access.json", {})
    estate_access_truth = _jom_cached_read_json_v1("estate_access_truth.json", {})
    lifecycle_decisions = _jom_estate_runtime_lifecycle_contract_v1()
    source_state = _jom_cached_source_state_v1()

    if "_jom_cmdc_truth_registry_from_estate_inventory_v1" in globals():
        registry = _jom_cmdc_truth_registry_from_estate_inventory_v1(estate_admin_inventory, registry)

    registry_summary = registry.get("summary") if isinstance(registry, dict) and isinstance(registry.get("summary"), dict) else _jom_cached_registry_summary_v1(registry)

    product_summary = estate_product_access.get("summary", {}) if isinstance(estate_product_access, dict) else {}
    access_product_summary = estate_access_truth.get("product_summary", {}) if isinstance(estate_access_truth, dict) else {}
    access_summary = estate_access_truth.get("summary", {}) if isinstance(estate_access_truth, dict) else {}
    product_users = product_summary.get("total_jira_product_user_count")
    if product_users is None:
        product_users = access_product_summary.get("total_jira_product_user_count")
    if product_users is None:
        product_users = access_summary.get("api_product_user_count")

    if "_jom_command_centre_users_metric_contract_payload_v1" in globals():
        users_payload = _jom_command_centre_users_metric_contract_payload_v1(user_footprint, product_users)
    else:
        users_payload = dict(user_footprint) if isinstance(user_footprint, dict) else {}
        users_payload = _jom_active_users_unavailable_metric_v1()
        users_payload["product_access_assignments"] = _jom_product_access_assignments_metric_v1(product_users)
        users_payload["metric_label"] = "Live Jira product-access users"
        users_payload["named_access_detail_guarded"] = True
        users_payload["source"] = "estate_product_access.summary.total_jira_product_user_count"

    metrics = {
        "total_sites": registry_summary.get("total_sites"),
        "monitored_sites": registry_summary.get("monitored_count"),
        "discovered_sites": registry_summary.get("discovered_count"),
        "review_items": registry_summary.get("review_count"),
        "pending_onboarding": registry_summary.get("pending_onboarding_count"),
        "coverage_percent": registry_summary.get("coverage_percent"),
        "users": _jom_active_users_unavailable_metric_v1(),
        "product_access_assignments": product_users,
    }

    source_health = {
        "site_registry": _jom_estate_workspace_alignment_source_health_v1("site_registry", registry) if "_jom_estate_workspace_alignment_source_health_v1" in globals() else {"available": bool(registry)},
        "estate_admin_site_inventory": _jom_estate_workspace_alignment_source_health_v1("estate_admin_site_inventory", estate_admin_inventory) if "_jom_estate_workspace_alignment_source_health_v1" in globals() else {"available": bool(estate_admin_inventory)},
        "estate_product_access": _jom_estate_workspace_alignment_source_health_v1("estate_product_access", estate_product_access) if "_jom_estate_workspace_alignment_source_health_v1" in globals() else {"available": bool(estate_product_access)},
        "estate_access_truth": _jom_estate_workspace_alignment_source_health_v1("estate_access_truth", estate_access_truth) if "_jom_estate_workspace_alignment_source_health_v1" in globals() else {"available": bool(estate_access_truth)},
    }

    data = {
        "registry": registry,
        "registry_summary": registry_summary,
        "users": users_payload,
        "users_metric": _jom_active_users_unavailable_metric_v1(),
        "product_access_metric": _jom_product_access_assignments_metric_v1(product_users),
        "estate_admin_site_inventory": estate_admin_inventory,
        "estate_product_access": estate_product_access,
        "estate_access_truth": estate_access_truth,
        "lifecycle_decisions": lifecycle_decisions,
        "source_state": source_state,
        "source_health": source_health,
        "metrics": metrics,
    }
    payload = {
        "schema": "jom-workspace-estate-contract-v1-aligned-read",
        "served_at_utc": served,
        "source_policy": "Fast Estate workspace contract aligned to live Estate inventory truth. No live collectors run during page load.",
        "data": data,
    }
    payload.update(data)
    return payload


@app.route("/api/workspace/command-centre")
def api_workspace_command_centre_cached_v1():
    return jsonify(_jom_workspace_command_centre_cached_contract_v1())


# JOM estate workspace contract alignment v1
def _jom_estate_workspace_alignment_read_contract_v1(filename, default=None):
    if default is None:
        default = {}
    try:
        if "_jom_cached_read_json_v1" in globals():
            payload = _jom_cached_read_json_v1(filename, default)
        else:
            payload = load_json(filename, default)
    except Exception:
        payload = default
    return payload if payload is not None else default


def _jom_estate_workspace_alignment_source_health_v1(label, payload):
    if isinstance(payload, dict):
        keys = sorted(list(payload.keys()))[:30]
        count_hint = None
        for key in ("sites", "items", "records", "validations", "decisions"):
            value = payload.get(key)
            if isinstance(value, (list, dict)):
                count_hint = len(value)
                break
        return {"label": label, "available": True, "type": "dict", "keys": keys, "count_hint": count_hint}
    if isinstance(payload, list):
        return {"label": label, "available": True, "type": "list", "count_hint": len(payload)}
    return {"label": label, "available": bool(payload), "type": type(payload).__name__}



def _jom_estate_workspace_alignment_normalise_sites_v1(site_registry, admin_inventory, existing_sites=None):
    source_sites = []
    if isinstance(existing_sites, list):
        source_sites.extend([site for site in existing_sites if isinstance(site, dict)])
    registry_sites = site_registry.get("sites", []) if isinstance(site_registry, dict) and isinstance(site_registry.get("sites"), list) else []
    inventory_sites = admin_inventory.get("sites", []) if isinstance(admin_inventory, dict) and isinstance(admin_inventory.get("sites"), list) else []
    source_sites.extend(registry_sites)
    source_sites.extend(inventory_sites)
    by_key = {}
    for item in source_sites:
        key = _jom_current_state_site_key_v1(item) if "_jom_current_state_site_key_v1" in globals() else str(item.get("site_key") or item.get("key") or "").lower()
        if not key:
            continue
        if "_jom_current_state_allowed_v1" in globals() and not _jom_current_state_allowed_v1(key):
            continue
        merged = dict(by_key.get(key, {}))
        merged.update(item)
        by_key[key] = _jom_current_state_normalise_site_v1(merged) if "_jom_current_state_normalise_site_v1" in globals() else merged
    return list(by_key.values())


def _jom_estate_workspace_alignment_summary_v1(site_registry, admin_inventory, sites, existing_summary=None):
    if "_jom_current_state_summary_v1" in globals():
        return _jom_current_state_summary_v1(sites)
    total = len(sites) if isinstance(sites, list) else 0
    return {"total_sites": total, "monitored_sites": 0, "review_items": total, "coverage_percent": 0}

def _jom_estate_workspace_alignment_get_existing_payload_v1():
    try:
        response = _jom_workspace_estate_existing_fast_read_v1()
        if hasattr(response, "get_json"):
            return response.get_json(silent=True) or {}
        if isinstance(response, dict):
            return response
    except Exception:
        pass
    return {}


def _jom_estate_workspace_alignment_payload_v1():
    existing = _jom_estate_workspace_alignment_get_existing_payload_v1()
    if not isinstance(existing, dict):
        existing = {}
    site_registry = _jom_estate_workspace_alignment_read_contract_v1("site_registry.json", {})
    access_truth = _jom_estate_workspace_alignment_read_contract_v1("estate_access_truth.json", {})
    admin_inventory = _jom_estate_workspace_alignment_read_contract_v1("estate_admin_site_inventory_v1.json", {})
    sites = _jom_estate_workspace_alignment_normalise_sites_v1(site_registry, admin_inventory, existing.get("sites"))
    summary = _jom_estate_workspace_alignment_summary_v1(site_registry, admin_inventory, sites, existing.get("summary"))
    source_health = existing.get("source_health") if isinstance(existing.get("source_health"), dict) else {}
    source_health.update({
        "site_registry": _jom_estate_workspace_alignment_source_health_v1("site_registry", site_registry),
        "estate_access_truth": _jom_estate_workspace_alignment_source_health_v1("estate_access_truth", access_truth),
        "estate_admin_site_inventory": _jom_estate_workspace_alignment_source_health_v1("estate_admin_site_inventory", admin_inventory),
    })
    payload = dict(existing)
    payload.update({
        "schema": "jom-estate-workspace-contract-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": existing.get("status") or ("ok" if site_registry and admin_inventory else "attention"),
        "summary": summary,
        "sites": sites,
        "source_health": source_health,
        "inventory": existing.get("inventory") if isinstance(existing.get("inventory"), dict) else admin_inventory,
        "access_truth": existing.get("access_truth") if isinstance(existing.get("access_truth"), dict) else access_truth,
        "frontend_owner": {
            "template": "templates/estate.html",
            "javascript": "static/js/jom_estate_lifecycle_v1.js",
            "css": "static/css/jom_estate_lifecycle_v1.css",
        },
    })
    return payload


@app.route("/api/workspace/estate")
def jom_api_workspace_estate_aligned_v1():
    return jsonify(_jom_estate_workspace_alignment_payload_v1())
def _jom_workspace_estate_existing_fast_read_v1():
    return jsonify(_jom_workspace_estate_cached_contract_v1())
# --- JOM WORKSPACE CONTRACT CACHED READ PATH v1 END ---


# === Estate Credential Validation Gate Correction v1 START ===
def _jom_credential_gate_now_utc():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _jom_credential_gate_data_path(filename):
    from pathlib import Path
    return Path(__file__).resolve().parent.parent / "runtime" / "data" / filename


def _jom_credential_gate_read_json(path, default):
    import json
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def _jom_credential_gate_write_json(path, payload):
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _jom_credential_gate_norm(value):
    return str(value or "").strip().lower()


def _jom_credential_gate_allowed_methods():
    return {
        "admin_org_validation",
        "oauth_coverage_validation",
        "atlassian_token_validation",
        "admin_api_validation",
        "stored_credential_validation",
    }


def _jom_credential_gate_validation_is_real(record):
    if not isinstance(record, dict):
        return False
    if record.get("access_valid") is not True and record.get("status") != "ok":
        return False
    method = str(record.get("method") or "").strip().lower()
    return method in _jom_credential_gate_allowed_methods()


def _jom_credential_gate_site(site_key):
    registry = _jom_credential_gate_read_json(_jom_credential_gate_data_path("site_registry.json"), {"sites": []})
    wanted = _jom_credential_gate_norm(site_key)
    for site in registry.get("sites", []):
        if isinstance(site, dict):
            key = _jom_credential_gate_norm(site.get("site_key") or site.get("key") or site.get("site_name") or site.get("name"))
            if key == wanted:
                return site
    return None


def _jom_credential_gate_latest_validation(site_key):
    wanted = _jom_credential_gate_norm(site_key)
    payload = _jom_estate_runtime_access_validation_contract_v1()
    candidates = []
    if isinstance(payload, dict):
        current = payload.get("validations", {}).get(wanted, {})
        if isinstance(current, dict):
            candidates.append(current)
        for row in payload.get("history", []) or []:
            if isinstance(row, dict) and _jom_credential_gate_norm(row.get("site_key")) == wanted:
                candidates.append(row)
    candidates = [row for row in candidates if _jom_credential_gate_validation_is_real(row)]
    return candidates[-1] if candidates else {}


def _jom_credential_gate_status_payload(site_key, validation=None):
    wanted = _jom_credential_gate_norm(site_key)
    validation = validation or _jom_credential_gate_latest_validation(wanted)
    if validation:
        return {"ok": True, "validation": validation}
    return {
        "ok": False,
        "validation": {
            "access_valid": False,
            "status": "blocked",
            "site_key": wanted,
            "reason": "Credential access has not been validated yet. Click Validate Access before enabling monitoring.",
            "method": "not_validated",
        },
    }

@app.route("/api/site-review/<path:site_key>/validate-access", methods=["POST"])
def api_site_review_validate_access_gate_v1(site_key):
    gate = _jom_access_gate_current_coverage_v1(site_key, actor=(request.get_json(silent=True) or {}).get("actor") or "operator")
    if gate.get("access_valid") is True:
        return jsonify({
            "ok": True,
            "site_key": gate.get("site_key"),
            "validation": gate.get("validation", {}),
            "coverage": gate.get("coverage", {}),
            "authorization_required": False,
            "authorization_url": None,
            "message": "Access validated. Monitoring can be enabled in JOM.",
        })
    return jsonify({
        "ok": False,
        "site_key": gate.get("site_key"),
        "validation": gate.get("validation", {}),
        "coverage": gate.get("coverage", {}),
        "authorization_required": True,
        "authorization_url": gate.get("authorization_url"),
        "action": gate.get("action"),
        "message": gate.get("message") or "Atlassian authorisation is required before monitoring can be enabled.",
    }), 409
# === Estate Credential Validation Gate Correction v1 END ===

# === Estate OAuth Callback Validation Record Repair v1 START ===
def _jom_estate_oauth_validation_record(site_key, coverage, actor="oauth-callback"):
    wanted = _jom_credential_gate_norm(site_key) if "_jom_credential_gate_norm" in globals() else str(site_key or "").strip().lower()
    now_value = _jom_credential_gate_now_utc() if "_jom_credential_gate_now_utc" in globals() else now_utc()
    return {
        "access_valid": True,
        "status": "ok",
        "site_key": wanted,
        "site_name": wanted,
        "method": "oauth_coverage_validation",
        "validated_at_utc": now_value,
        "actor": actor,
        "reason": "Credential access validated from OAuth coverage after Atlassian authorisation.",
        "coverage_status": coverage.get("coverage_status") or coverage.get("status") if isinstance(coverage, dict) else None,
    }


def _jom_estate_write_access_validation_record(site_key, validation):
    wanted = _jom_credential_gate_norm(site_key) if "_jom_credential_gate_norm" in globals() else str(site_key or "").strip().lower()
    path = DATA_PATH / "site_access_validation.json"
    reader = _jom_credential_gate_read_json if "_jom_credential_gate_read_json" in globals() else load_json
    writer = _jom_credential_gate_write_json if "_jom_credential_gate_write_json" in globals() else write_json
    access = reader(path, {"schema": "jom-site-access-validation-v1", "validations": {}, "history": []})
    if not isinstance(access, dict):
        access = {"schema": "jom-site-access-validation-v1", "validations": {}, "history": []}
    access.setdefault("schema", "jom-site-access-validation-v1")
    access.setdefault("validations", {})[wanted] = validation
    access.setdefault("history", []).append(validation)
    access["generated_at_utc"] = validation.get("validated_at_utc") or (now_utc() if "now_utc" in globals() else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    writer(path, access)
    return access


def _jom_estate_complete_oauth_validation(site_key, actor="oauth-callback"):
    coverage = _oauth_coverage_payload(site_key) if "_oauth_coverage_payload" in globals() else {}
    if isinstance(coverage, dict) and coverage.get("monitoring_allowed") is True:
        validation = _jom_estate_oauth_validation_record(site_key, coverage, actor=actor)
        _jom_estate_write_access_validation_record(site_key, validation)
        return {"ok": True, "site_key": site_key, "validation": validation, "coverage": coverage}
    return {
        "ok": False,
        "error": "oauth_authorisation_required",
        "site_key": site_key,
        "coverage": coverage,
        "message": "Atlassian authorisation is still required, or the OAuth token does not cover this site.",
        "action": "open_authorization_url" if isinstance(coverage, dict) and coverage.get("authorization_url") else None,
        "authorization_url": coverage.get("authorization_url") if isinstance(coverage, dict) else None,
    }


@app.route("/api/site-review/<path:site_key>/oauth-complete", methods=["GET", "POST"])
def api_site_review_oauth_complete_v1(site_key):
    from flask import Flask, jsonify, render_template, send_from_directory, request, redirect 
    body = request.get_json(silent=True) or {}
    actor = body.get("actor") or "oauth-callback"
    payload = _jom_estate_complete_oauth_validation(site_key, actor=actor)
    status = 200 if payload.get("ok") else 409
    if status == 200 and "_jom_lifecycle_audit_event_v1" in globals():
        _jom_lifecycle_audit_event_v1(site_key, "oauth_access_validated", actor=actor, state="access_validated", message="Atlassian authorization completed and access validated.", source="site_review_oauth_complete")
    return jsonify(payload), status

# JOM_OAUTH_CALLBACK_COMPLETION_REPAIR_V1_1 START
# Receives Atlassian OAuth callbacks on /callback and /oauth/callback, saves tokens.json,
# then returns the operator to the active Site Review page.
def _jom_oauth_paths_v1_1():
    root = Path(__file__).resolve().parents[1]
    return root, root / "tokens.json", root / ".auth_state.json", root / ".env"


def _jom_oauth_read_env_v1_1():
    import os as _os
    root, _token_path, _state_path, env_path = _jom_oauth_paths_v1_1()
    env = dict(_os.environ)
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _jom_oauth_read_json_v1_1(path, default):
    try:
        if not path.exists():
            return default
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else default
    except Exception:
        return default


def _jom_oauth_write_json_v1_1(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def _jom_oauth_store_pending_site_v1_1(site_key):
    _root, _token_path, state_path, _env_path = _jom_oauth_paths_v1_1()
    state = _jom_oauth_read_json_v1_1(state_path, {})
    state["latest_site_key"] = str(site_key or "").strip()
    state.setdefault("state", state.get("state") or "jom-estate-oauth")
    state["updated_at_utc"] = now_utc() if "now_utc" in globals() else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return _jom_oauth_write_json_v1_1(state_path, state)


def _jom_oauth_site_from_callback_v1_1():
    _root, _token_path, state_path, _env_path = _jom_oauth_paths_v1_1()
    requested = request.args.get("site") or request.args.get("site_key") or ""
    if requested:
        return requested
    state_arg = request.args.get("state") or ""
    if state_arg.startswith("site:"):
        return state_arg.split(":", 1)[1]
    state = _jom_oauth_read_json_v1_1(state_path, {})
    return state.get("latest_site_key") or state.get("site_key") or ""


def _jom_oauth_exchange_code_v1_1(code):
    import time as _time
    import urllib.request as _request
    import urllib.error as _error
    env = _jom_oauth_read_env_v1_1()
    _root, token_path, _state_path, _env_path = _jom_oauth_paths_v1_1()
    token_url = env.get("ATLASSIAN_TOKEN_URL") or "https://auth.atlassian.com/oauth/token"
    client_id = env.get("ATLASSIAN_OAUTH_CLIENT_ID") or env.get("ATLASSIAN_CLIENT_ID") or ""
    client_secret = env.get("ATLASSIAN_OAUTH_CLIENT_SECRET") or env.get("ATLASSIAN_CLIENT_SECRET") or ""
    redirect_uri = env.get("ATLASSIAN_OAUTH_REDIRECT_URI") or env.get("ATLASSIAN_REDIRECT_URI") or "http://127.0.0.1:5000/oauth/callback"
    if not client_id or not client_secret:
        return {"ok": False, "error": "missing_client_credentials"}
    body = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    req = _request.Request(
        token_url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with _request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            payload = json.loads(raw) if raw else {}
    except _error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": "token_exchange_failed", "http_status": exc.code, "detail": detail[:1000]}
    except Exception as exc:
        return {"ok": False, "error": "token_exchange_failed", "detail": str(exc)}
    if not isinstance(payload, dict) or not payload.get("access_token"):
        return {"ok": False, "error": "token_response_missing_access_token", "payload": payload}
    expires_in = int(payload.get("expires_in") or 3600)
    saved = _jom_oauth_read_json_v1_1(token_path, {})
    saved.update(payload)
    saved["client_id"] = client_id
    saved["scope"] = payload.get("scope") or env.get("ATLASSIAN_SCOPES") or env.get("ATLASSIAN_OAUTH_SCOPE") or saved.get("scope")
    saved["expires_at_epoch"] = int(_time.time()) + expires_in
    saved["updated_at_utc"] = now_utc() if "now_utc" in globals() else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    saved["source"] = "oauth_callback"
    _jom_oauth_write_json_v1_1(token_path, saved)
    return {"ok": True, "tokens_saved": True, "expires_at_epoch": saved["expires_at_epoch"]}


def _jom_oauth_callback_response_v1_1():
    code = request.args.get("code") or ""
    if not code:
        return jsonify({"ok": False, "error": "missing_oauth_code", "query": dict(request.args)}), 400
    site_key = _jom_oauth_site_from_callback_v1_1()
    exchange = _jom_oauth_exchange_code_v1_1(code)
    if not exchange.get("ok"):
        return jsonify(exchange), 502
    if site_key and "_jom_estate_complete_oauth_validation" in globals():
        _jom_estate_complete_oauth_validation(site_key, actor="oauth-callback")
    if site_key:
        return redirect("/estate/review/" + str(site_key) + "?oauth=complete", code=302)
    return redirect("/estate?oauth=complete", code=302)


@app.route("/callback")
def jom_oauth_callback_root_v1_1():
    return _jom_oauth_callback_response_v1_1()


@app.route("/oauth/callback")
def jom_oauth_callback_oauth_v1_1():
    return _jom_oauth_callback_response_v1_1()


# JOM_OAUTH_CALLBACK_COMPLETION_REPAIR_V1_1 END
# === Estate OAuth Callback Validation Record Repair v1 END ===

# JOM_ESTATE_ADMIN_INVENTORY_API_WIRING_V1
# Exposes live Estate discovery authority contracts without changing Estate layout or CSS.
def _jom_read_static_data_contract_v1(filename, fallback_contract):
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    path = root / "runtime" / "data" / filename
    if not path.exists():
        return {
            "ok": False,
            "contract": fallback_contract,
            "error": "missing_contract_file",
            "path": str(path),
            "sites": [],
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            data.setdefault("ok", True)
            data.setdefault("contract_file", filename)
            return data
        return {
            "ok": False,
            "contract": fallback_contract,
            "error": "contract_file_not_object",
            "contract_file": filename,
            "sites": [],
        }
    except Exception as exc:
        return {
            "ok": False,
            "contract": fallback_contract,
            "error": "contract_read_failed",
            "detail": str(exc),
            "contract_file": filename,
            "sites": [],
        }

@app.route('/api/estate/admin-site-inventory')
def jom_api_estate_admin_site_inventory_v1():
    from flask import Flask, jsonify, render_template, send_from_directory, request, redirect 
    import json
    data = _jom_read_static_data_contract_v1(
        "estate_admin_site_inventory_v1.json",
        "estate_admin_site_inventory_v1",
    )
    return Response(json.dumps(data, indent=2), mimetype="application/json")

@app.route('/api/estate/discovery-authority')
def jom_api_estate_discovery_authority_v1():
    from flask import Flask, jsonify, render_template, send_from_directory, request, redirect 
    import json
    data = _jom_read_static_data_contract_v1(
        "estate_discovery_authority_v1.json",
        "estate_discovery_authority_v1",
    )
    return Response(json.dumps(data, indent=2), mimetype="application/json")
# END JOM_ESTATE_ADMIN_INVENTORY_API_WIRING_V1



# === JOM ESTATE SITE REVIEW RESPONSE WRAP TRUTH v1.2 START ===
def _jom_site_review_inventory_truth_v1_2(site_key):
    inventory = load_json("estate_admin_site_inventory_v1.json", {})
    rows = inventory.get("sites", []) if isinstance(inventory, dict) and isinstance(inventory.get("sites"), list) else []
    wanted = _normalise_site_key(site_key) if "_normalise_site_key" in globals() else str(site_key or "").strip().lower()
    for row in rows:
        if not isinstance(row, dict):
            continue
        values = [row.get("site_key"), row.get("key"), row.get("name"), row.get("site_name"), row.get("url"), row.get("site_url"), row.get("cloud_id")]
        if not any(str(value or "").strip().lower() == wanted for value in values):
            continue
        key = str(row.get("site_key") or row.get("key") or row.get("name") or site_key or "").strip().lower()
        lifecycle = str(row.get("lifecycle") or "discovery_gap").strip().lower()
        monitored = lifecycle == "monitored" or row.get("approved_monitored") is True or row.get("is_monitored") is True or row.get("monitored") is True
        label = "Monitored" if monitored else " ".join(part.capitalize() for part in lifecycle.split("_"))
        monitoring_label = "Monitoring enabled" if monitored else "Not monitored"
        return {
            "found": True,
            "site_key": key,
            "site_name": row.get("name") or row.get("site_name") or key,
            "site_url": row.get("url") or row.get("site_url") or "",
            "url": row.get("url") or row.get("site_url") or "",
            "cloud_id": row.get("cloud_id"),
            "sources": row.get("sources") or [],
            "evidence_levels": row.get("evidence_levels") or [],
            "classification": "monitored" if monitored else lifecycle,
            "lifecycle": lifecycle,
            "lifecycle_status": label,
            "is_monitored": bool(monitored),
            "monitored": bool(monitored),
            "approved_monitored": bool(row.get("approved_monitored") is True),
            "collector_onboarding_status": "monitoring_enabled" if monitored else lifecycle,
            "monitoring_status": monitoring_label,
            "health_status": "OK" if monitored else "Review",
            "action_required": row.get("action_required"),
            "truth_source": "estate_admin_site_inventory_v1.json",
        }
    return {"found": False}

def _jom_site_review_align_payload_v1_2(site_key, payload):
    if not isinstance(payload, dict):
        return payload
    truth = _jom_site_review_inventory_truth_v1_2(site_key)
    if not truth.get("found"):
        return payload
    payload.update({
        "site_key": truth.get("site_key"),
        "site_name": truth.get("site_name"),
        "site_url": truth.get("site_url"),
        "url": truth.get("url"),
        "cloud_id": truth.get("cloud_id"),
        "sources": truth.get("sources"),
        "evidence_levels": truth.get("evidence_levels"),
        "classification": truth.get("classification"),
        "lifecycle": truth.get("lifecycle"),
        "lifecycle_status": truth.get("lifecycle_status"),
        "is_monitored": truth.get("is_monitored"),
        "monitored": truth.get("monitored"),
        "monitoring_status": truth.get("monitoring_status"),
        "health_status": truth.get("health_status"),
        "truth_source": truth.get("truth_source"),
    })
    readiness = payload.get("readiness") if isinstance(payload.get("readiness"), dict) else {}
    readiness["lifecycle"] = truth.get("lifecycle_status")
    readiness["monitoring"] = truth.get("monitoring_status")
    readiness["source"] = truth.get("truth_source")
    payload["readiness"] = readiness
    monitoring = payload.get("monitoring") if isinstance(payload.get("monitoring"), dict) else {}
    monitoring["enabled"] = truth.get("is_monitored")
    monitoring["status"] = truth.get("monitoring_status")
    monitoring["source"] = truth.get("truth_source")
    payload["monitoring"] = monitoring
    lifecycle_detail = payload.get("lifecycle_detail") if isinstance(payload.get("lifecycle_detail"), dict) else {}
    lifecycle_detail["state"] = truth.get("lifecycle")
    lifecycle_detail["label"] = truth.get("lifecycle_status")
    lifecycle_detail["source"] = truth.get("truth_source")
    payload["lifecycle_detail"] = lifecycle_detail
    return payload

# === JOM ESTATE SITE REVIEW RESPONSE WRAP TRUTH v1.2 END ===



# JOM Estate Discovery Authority Coverage API v1.1
# Backend-only evidence route. Reads runtime/data contracts only; no runtime-only source handling.
def _jom_estate_identity_from_item(item):
    if isinstance(item, str):
        return item.strip() or None
    if not isinstance(item, dict):
        return None
    for key in ("site_key", "key", "site", "name", "slug", "cloud_id", "cloudId", "url", "base_url"):
        value = item.get(key)
        if value:
            return str(value).strip()
    return None


def _jom_estate_items_from_payload(payload):
    items = []

    def add(value, source_key=None):
        if isinstance(value, dict):
            copy = dict(value)
            if source_key and not any(copy.get(k) for k in ("site_key", "key", "site", "name", "url", "cloud_id", "cloudId")):
                copy["site_key"] = str(source_key)
            items.append(copy)
        elif isinstance(value, str):
            items.append({"site_key": value})

    if isinstance(payload, list):
        for item in payload:
            add(item)
    elif isinstance(payload, dict):
        for key in ("sites", "items", "data", "results", "values", "monitored_sites", "unmonitored_sites"):
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    add(item)
            elif isinstance(value, dict):
                for site_key, item in value.items():
                    add(item, site_key)
        if not items:
            for site_key, item in payload.items():
                if isinstance(item, (dict, str)):
                    add(item, site_key)
    return items


@app.route("/api/estate/discovery-authority/coverage")
def estate_discovery_authority_coverage():
    from app.runtime.runtime_data_paths import runtime_read_json

    source_files = {
        "site_registry": "site_registry.json",
        "estate_admin_site_inventory": "estate_admin_site_inventory_v1.json",
        "site_onboarding_review": "site_onboarding_review.json",
        "estate_access_truth": "estate_access_truth.json",
        "estate_product_access": "estate_product_access.json",
    }

    source_status = {}
    identities = set()
    identity_sources = {}

    for source_name, file_name in source_files.items():
        payload = runtime_read_json(file_name, default={})
        source_items = _jom_estate_items_from_payload(payload)
        source_identities = []
        for item in source_items:
            identity = _jom_estate_identity_from_item(item)
            if identity:
                identities.add(identity)
                source_identities.append(identity)
                identity_sources.setdefault(identity, []).append(source_name)
        source_status[source_name] = {
            "runtime_file": "runtime/data/" + file_name,
            "available": payload not in ({}, [], None),
            "identity_count": len(sorted(set(source_identities))),
            "identities": sorted(set(source_identities)),
        }

    return jsonify({
        "status": "success",
        "authority": "runtime-data-contracts",
        "static_fallback_used": False,
        "source_file_count": len(source_files),
        "source_status": source_status,
        "coverage": {
            "unique_identity_count": len(identities),
            "unique_identities": sorted(identities),
            "identity_sources": {key: sorted(set(value)) for key, value in sorted(identity_sources.items())},
        },
    })



# --- JOM LIVE ORGANISATION DISCOVERY CONTRACT v1 START ---
@app.route("/api/estate/organisations")
@app.route("/api/estate/organizations")
def api_estate_organisations_live_v1():
    """Live Atlassian organisation discovery.

    This route does not use static fallback data. If the admin API token is not
    configured or Atlassian does not return organisation data, the route reports
    unavailable/error instead of inventing organisation counts.
    """
    try:
        from app.builders.organisation_discovery import collect_organisation_discovery
        payload = collect_organisation_discovery()
        try:
            runtime_write_json("organisation_discovery.json", payload)
        except Exception as write_exc:
            if isinstance(payload, dict):
                payload.setdefault("warnings", []).append("organisation discovery cache write failed: " + str(write_exc))
        status = 200 if payload.get("status") in {"ok", "unavailable"} else 502
        return jsonify(payload), status
    except Exception as exc:
        return jsonify({
            "schema": "jom-live-organisation-discovery-v1",
            "status": "error",
            "live_collection": False,
            "organisation_count": None,
            "organisations": [],
            "error": str(exc),
            "static_fallback_used": False,
        }), 500
# --- JOM LIVE ORGANISATION DISCOVERY CONTRACT v1 END ---


# --- JOM ATLASSIAN ORGANISATION AUTH SOURCE AUDIT v1 START ---
@app.route("/api/estate/organisation-auth-source-audit")
@app.route("/api/estate/organization-auth-source-audit")
def api_estate_organisation_auth_source_audit_v1():
    """Audit configured Atlassian organisation authentication sources.

    This route reports presence/absence of usable auth sources without exposing
    secret values and without creating frontend truth.
    """
    try:
        from app.audits.organisation_auth_source_audit import audit_organisation_auth_sources
        payload = audit_organisation_auth_sources()
        try:
            runtime_write_json("organisation_auth_source_audit.json", payload)
        except Exception as write_exc:
            payload.setdefault("warnings", []).append("organisation auth source audit cache write failed: " + str(write_exc))
        return jsonify(payload)
    except Exception as exc:
        return jsonify({
            "schema": "jom-atlassian-organisation-auth-source-audit-v1",
            "status": "error",
            "error": str(exc),
            "secrets_exposed": False,
            "static_fallback_used": False,
        }), 500
# --- JOM ATLASSIAN ORGANISATION AUTH SOURCE AUDIT v1 END ---

# === JOM SITE REVIEW STOP MONITORING ROUTE v2 START ===
@app.route("/api/site-review/<site_key>/stop-monitoring", methods=["POST"])
def api_site_review_stop_monitoring_v2(site_key):
    body = request.get_json(silent=True) or {}
    actor = body.get("actor") or "operator"
    record, inventory_record, _registry, _inventory = _jom_lifecycle_mark_review_v1(site_key, actor=actor)
    if record is None and inventory_record is None:
        return jsonify({"ok": False, "error": "site_not_found", "site_key": site_key}), 404
    if "_jom_lifecycle_audit_event_v1" in globals():
        _jom_lifecycle_audit_event_v1(site_key, "stop_monitoring", actor=actor, state="stopped_monitoring", message="Monitoring stopped. Site returned to review/discovery.", source="site_review_stop_monitoring")
    return jsonify({
        "ok": True,
        "message": "Monitoring stopped. Site returned to review across Site Registry and Estate inventory truth sources.",
        "site_key": _jom_lifecycle_norm_v1(site_key),
        "registry_record": record,
        "inventory_record": inventory_record,
    })
# === JOM SITE REVIEW STOP MONITORING ROUTE v2 END ===

if __name__ == "__main__":
    app.run(debug=True, port=5000)














# JOM runtime data path abstraction aliases v1
def load_runtime_json(filename, default=None):
    return runtime_read_json(filename, default)

def write_runtime_json(filename, payload):
    return runtime_write_json(filename, payload)


@app.route("/api/runtime/data-path-status")
def api_runtime_data_path_status():
    files = [
        "admin_enriched_refresh_status.json", "admin_truth_v2.json",
        "backend_final_truth_chain_status.json", "backend_final_truth_chain_status.json",
        "estate_access_truth.json", "estate_access_truth.json",
        "estate_admin_site_inventory_v1.json", "estate_product_access.json",
        "runtime_execution_history.json",
        "runtime_execution_status.json",
        "site_onboarding_review.json",
        "site_registry.json", "source_freshness_audit.json",
        "source_reliability_status.json", "user_footprint.json",
    ]
    return jsonify({
        "schema": "jom-runtime-data-path-status-v1",
        "files": {name: runtime_path_status(name) for name in files},
        "policy": "Read runtime/data first; runtime-only source handling disabled; runtime/data is the only operational source.",
    })


## === JOM CURRENT STATE AUTHORITY RESET v1 START ===
## Current estate UI truth is live OAuth/runtime authority only.
## Historical lifecycle/onboarding records are display evidence only and must not drive current scope.

JOM_CURRENT_STATE_MONITORED_KEYS_V1 = {"gli-delivery-tm", "gli-global-technology", "gli-it-project"}
JOM_CURRENT_STATE_REVIEW_KEYS_V1 = {"gli-tracker"}
JOM_CURRENT_STATE_ALLOWED_KEYS_V1 = JOM_CURRENT_STATE_MONITORED_KEYS_V1 | JOM_CURRENT_STATE_REVIEW_KEYS_V1

def _jom_current_state_key_v1(value):
    text = str(value or "").strip().lower()
    if text.startswith("http") and ".atlassian.net" in text:
        text = text.split("//", 1)[-1].split(".atlassian.net", 1)[0]
    return text.rstrip("/")

def _jom_current_state_site_key_v1(site):
    if not isinstance(site, dict):
        return ""
    for field in ("site_key", "key", "site_name", "name", "url", "site_url", "base_url"):
        value = site.get(field)
        if value:
            key = _jom_current_state_key_v1(value)
            if key:
                return key
    return ""

def _jom_current_state_allowed_v1(site_or_key):
    key = _jom_current_state_key_v1(site_or_key) if not isinstance(site_or_key, dict) else _jom_current_state_site_key_v1(site_or_key)
    return key in JOM_CURRENT_STATE_ALLOWED_KEYS_V1

def _jom_current_state_filter_sites_v1(sites):
    return [site for site in sites if isinstance(site, dict) and _jom_current_state_allowed_v1(site)]

def _jom_current_state_is_monitored_v1(site):
    key = _jom_current_state_site_key_v1(site)
    state = str((site or {}).get("classification") or (site or {}).get("lifecycle") or (site or {}).get("collector_onboarding_status") or (site or {}).get("status") or "").lower()
    return bool(key in JOM_CURRENT_STATE_MONITORED_KEYS_V1 or (isinstance(site, dict) and (site.get("is_monitored") is True or site.get("monitored") is True or site.get("approved_monitored") is True)) or state in {"monitored", "monitoring_enabled"})

def _jom_current_state_normalise_site_v1(site):
    site = dict(site) if isinstance(site, dict) else {}
    key = _jom_current_state_site_key_v1(site)
    site["site_key"] = key
    site["key"] = key
    site.setdefault("site_name", site.get("name") or key)
    site.setdefault("name", site.get("site_name") or key)
    site.setdefault("site_url", site.get("url") or ("https://" + key + ".atlassian.net" if key else ""))
    site.setdefault("url", site.get("site_url") or "")
    if key in JOM_CURRENT_STATE_MONITORED_KEYS_V1:
        site.update({
            "classification": "monitored",
            "lifecycle": "monitored",
            "collector_onboarding_status": "monitoring_enabled",
            "is_monitored": True,
            "monitored": True,
            "approved_monitored": True,
            "status": "ok",
            "health_status": "OK",
        })
    elif key in JOM_CURRENT_STATE_REVIEW_KEYS_V1:
        state = str(site.get("lifecycle") or site.get("classification") or site.get("status") or "discovered").lower()
        if state not in {"approval_pending", "pending_review", "registered_review", "monitored"}:
            state = "discovered"
        site.update({
            "classification": state,
            "lifecycle": state,
            "collector_onboarding_status": state,
            "is_monitored": False,
            "monitored": False,
            "approved_monitored": False,
            "status": "review",
            "health_status": "Review",
        })
    site["current_state_authority"] = "live_oauth_runtime_authority_only"
    return site

def _jom_current_state_summary_v1(sites):
    current = [_jom_current_state_normalise_site_v1(site) for site in _jom_current_state_filter_sites_v1(sites)]
    monitored = [site for site in current if _jom_current_state_is_monitored_v1(site)]
    review = [site for site in current if not _jom_current_state_is_monitored_v1(site)]
    total = len(monitored) + len(review)
    return {
        "total_sites": total,
        "site_count": total,
        "monitored_count": len(monitored),
        "monitored_sites": len(monitored),
        "discovered_count": len(review),
        "pending_onboarding_count": len(review),
        "review_count": len(review),
        "coverage_percent": round((len(monitored) / total) * 100) if total else 0,
        "current_state_authority": "live_oauth_runtime_authority_only",
    }

## === JOM CURRENT STATE AUTHORITY RESET v1 END ===
