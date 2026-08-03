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

from app.runtime.admin_enriched_chain import run_pipeline as run_snapshot
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
# Website-facing backend routes must not use legacy/manual snapshot files as truth.
# Runtime-generated/live contracts may be used, but they must remain explicitly labelled
# by the route contract freshness/status logic.
LEGACY_NON_WEBSITE_TRUTH_FILES = {
    "latest_run.json",
    "latest_run_admin_enriched.json",
    "latest_run_admin_enriched_pretty.json",
    "billing_seats.json",
    "admin_named_access.json",
    "named_access_truth_v2.json",
}

LIVE_WEBSITE_TRUTH_FILES = {
    "admin_enriched_refresh_status.json",
    "admin_truth_v2.json",
    "backend_final_truth_chain_status.json",
    "backend_legacy_truth_eradication_status.json",
    "estate_access_truth.json",
    "estate_admin_site_inventory_v1.json",
    "estate_discovery_authority_v1.json",
    "estate_product_access.json",
    "organisation_auth_source_audit.json",
    "organisation_discovery.json",
    "operational_source_recovery_status.json",
    "product_access_refresh_status.json",
    "runtime_execution_history.json",
    "runtime_execution_status.json",
    "runtime_live_truth_status.json",
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
            "reason": "Legacy/manual snapshot inputs must not feed website-facing routes.",
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


def _live_product_access_snapshot() -> Dict[str, Any]:
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
    live_product = _live_product_access_snapshot()
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
    live_truth = load_json("runtime_live_truth_status.json", {})
    live_product = _live_product_access_snapshot()
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
        "runtime_live_truth_status": _contract_payload("runtime_live_truth_status", live_truth, source_file="runtime/data/runtime_live_truth_status.json", contract_type="generated_live_truth_status", allow_stale=True),
        "live_product_access": product_truth_status,
        "legacy_snapshot_policy": {
            "latest_run_json_is_legacy_reference_only": True,
            "latest_run_admin_enriched_json_is_legacy_reference_only": True,
            "billing_seats_json_is_legacy_reference_only": True,
            "product_access_static_files_are_cache_only": True,
        },
        "runtime_status": compact_runtime_status(),
        "operator_summary": build_operator_summary(),
        "notes": [
            "Live product access status is reported separately so stale generated snapshots do not override current endpoint truth.",
            "Legacy runtime snapshots are explicitly demoted from website truth.",
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
    snapshots. It attempts live collection every time it is requested, writes
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
    return render_template("site.html", **site_context())


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
    return render_template('site.html', site_key=site_key)

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
    inventory_site = _jom_site_review_normalised_inventory_site_v1(site_key)
    if inventory_site:
        return inventory_site
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
    return jsonify(_build_site_review_payload(site_key))

@app.route("/api/site-review/<path:site_key>/decision", methods=["POST"])
def api_site_review_decision(site_key):
    body = request.get_json(silent=True) or {}
    decision = str(body.get("decision") or body.get("state") or "").strip().lower()
    actor = body.get("actor") or "operator"
    if decision in ("approve", "approved", "approval_pending"):
        record, inventory_record, _registry, _inventory = _jom_lifecycle_mark_approval_pending_v1(site_key, actor=actor)
        if record is None and inventory_record is None:
            return jsonify({"ok": False, "error": "site_not_found", "site_key": site_key}), 404
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
    try:
        for rule in app.url_map.iter_rules():
            if str(rule) == route_path:
                fn = app.view_functions.get(rule.endpoint)
                if not callable(fn):
                    return {"available": False, "reason": f"endpoint not callable for {route_path}"}
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
        return {"available": False, "reason": f"route not found: {route_path}"}
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
        "runtime_live_truth_status": _jom_cached_read_json_v1("runtime_live_truth_status.json", {}),
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
    if admin_status and admin_status not in {"aligned", "ok", "healthy"}:
        alerts.append({
            "level": "warning",
            "category": "admin_truth",
            "title": "Administration data requires attention",
            "reason": "JOM has detected that the live administration truth layer is not currently reporting an aligned state.",
            "source": "admin_truth_v2.json",
            "source_label": "Live Admin truth layer",
            "value": admin_status,
            "recommended_action": "Open Admin and review the current governance and access data.",
            "action_label": "Open Admin",
        })
    reg_summary = _jom_cached_registry_summary_v1(registry)
    discovered = reg_summary.get("discovered_count") or 0
    if discovered:
        alerts.append({"level": "info", "category": "registry", "title": "Discovered sites need classification", "reason": "One or more discovered sites are not yet monitored.", "source": "site_registry.json", "value": discovered, "recommended_action": "Review site registry and onboarding decisions"})
    return alerts



def _jom_command_centre_users_metric_contract_payload_v1(user_footprint, product_users):
    payload = dict(user_footprint) if isinstance(user_footprint, dict) else {}
    payload["metric"] = product_users
    payload["metric_label"] = "Live Jira product-access users"
    payload["named_access_detail_guarded"] = True
    payload["source"] = "estate_product_access.summary.total_jira_product_user_count"
    return payload



# === JOM COMMAND CENTRE WORKSPACE TRUTH ALIGNMENT v1 START ===
def _jom_cmdc_truth_inventory_sites_v1(inventory):
    return inventory.get("sites") if isinstance(inventory, dict) and isinstance(inventory.get("sites"), list) else []

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
    if not rows:
        return registry if isinstance(registry, dict) else {}
    registry_map = _jom_cmdc_truth_registry_map_v1(registry)
    sites = [_jom_cmdc_truth_site_from_inventory_v1(row, registry_map) for row in rows if isinstance(row, dict)]
    total = len(sites)
    monitored = len([s for s in sites if s.get("is_monitored") is True])
    pending_review = len([s for s in sites if str(s.get("lifecycle") or "").lower() == "pending_review"])
    registered_review = len([s for s in sites if str(s.get("lifecycle") or "").lower() in {"registered_review", "approval_pending"}])
    discovery_gap = len([s for s in sites if str(s.get("lifecycle") or "").lower() == "discovery_gap"])
    discovered = len([s for s in sites if str(s.get("lifecycle") or "").lower() == "discovered"])
    review_count = pending_review + registered_review
    summary = {
        "total_sites": total,
        "monitored_count": monitored,
        "discovered_count": discovered,
        "pending_review_count": pending_review,
        "registered_review_count": registered_review,
        "discovery_gap_count": discovery_gap,
        "pending_onboarding_count": registered_review,
        "review_count": review_count,
        "coverage_percent": round((monitored / total) * 100) if total else 0,
    }
    return {
        "schema": "jom-site-registry-command-centre-estate-truth-v1",
        "generated_at_utc": inventory.get("generated_utc") or inventory.get("generated_at_utc"),
        "source": "runtime/data/estate_admin_site_inventory_v1.json",
        "source_policy": "Command Centre lifecycle counts aligned to Estate live inventory truth.",
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
        "users_metric": {
            "metric": product_users,
            "metric_label": "Live Jira product-access users",
            "named_access_detail_guarded": True,
            "source": "estate_product_access.summary.total_jira_product_user_count",
        },
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
        users_payload["metric"] = product_users
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
        "users": product_users,
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
        "users_metric": {
            "metric": product_users,
            "metric_label": "Live Jira product-access users",
            "named_access_detail_guarded": True,
            "source": "estate_product_access.summary.total_jira_product_user_count",
        },
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
    if isinstance(existing_sites, list) and existing_sites:
        return existing_sites
    registry_sites = site_registry.get("sites", []) if isinstance(site_registry, dict) else []
    inventory_sites = admin_inventory.get("sites", []) if isinstance(admin_inventory, dict) else []
    inventory_by_key = {}
    for item in inventory_sites if isinstance(inventory_sites, list) else []:
        if not isinstance(item, dict):
            continue
        key = item.get("key") or item.get("site_key") or item.get("cloud_id") or item.get("url") or item.get("name")
        if key:
            inventory_by_key[str(key)] = item
    sites = []
    for site in registry_sites if isinstance(registry_sites, list) else []:
        if not isinstance(site, dict):
            continue
        key = site.get("key") or site.get("site_key") or site.get("cloud_id") or site.get("url") or site.get("name")
        inv = inventory_by_key.get(str(key), {}) if key else {}
        sites.append({
            "key": key,
            "name": site.get("name") or inv.get("name") or key,
            "url": site.get("url") or inv.get("url"),
            "status": site.get("status") or inv.get("status") or "runtime_registry",
            "is_monitored": bool(site.get("is_monitored") or inv.get("is_monitored")),
            "source": "runtime_contract",
            "registry": site,
            "inventory": inv,
        })
    return sites


def _jom_estate_workspace_alignment_summary_v1(site_registry, admin_inventory, sites, existing_summary=None):
    summary = dict(existing_summary) if isinstance(existing_summary, dict) else {}
    registry_summary = site_registry.get("summary", {}) if isinstance(site_registry, dict) else {}
    inventory_summary = admin_inventory.get("summary", {}) if isinstance(admin_inventory, dict) else {}
    total_sites = summary.get("total_sites") or registry_summary.get("total_sites") or registry_summary.get("site_count") or inventory_summary.get("total_sites") or inventory_summary.get("site_count") or len(sites)
    monitored_sites = summary.get("monitored_sites") or registry_summary.get("monitored_sites") or registry_summary.get("monitored_count") or inventory_summary.get("monitored_sites")
    if monitored_sites is None:
        monitored_sites = sum(1 for site in sites if isinstance(site, dict) and site.get("is_monitored"))
    review_items = summary.get("review_items") or registry_summary.get("review_items") or inventory_summary.get("review_items") or 0
    coverage_percent = summary.get("coverage_percent")
    if coverage_percent is None and total_sites:
        try:
            coverage_percent = round((float(monitored_sites or 0) / float(total_sites)) * 100)
        except Exception:
            coverage_percent = None
    return {
        "total_sites": total_sites or 0,
        "monitored_sites": monitored_sites or 0,
        "review_items": review_items or 0,
        "coverage_percent": coverage_percent,
    }


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


# Wrap the existing authorize-url endpoint without relying on its exact source text.
if "api_oauth_authorize_url" in globals() and not getattr(api_oauth_authorize_url, "_jom_oauth_pending_site_wrapped_v1_1", False):
    _jom_original_api_oauth_authorize_url_v1_1 = api_oauth_authorize_url
    def api_oauth_authorize_url(site_key):
        _jom_oauth_store_pending_site_v1_1(site_key)
        return _jom_original_api_oauth_authorize_url_v1_1(site_key)
    api_oauth_authorize_url._jom_oauth_pending_site_wrapped_v1_1 = True
    app.view_functions["api_oauth_authorize_url"] = api_oauth_authorize_url
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

def _jom_register_site_review_truth_wrapper_v1_2():
    try:
        rules = list(app.url_map.iter_rules())
    except Exception:
        return
    for rule in rules:
        rule_text = str(rule)
        if "/api/site-review" not in rule_text:
            continue
        if "<site_key>" not in rule_text and "<path:site_key>" not in rule_text and "<string:site_key>" not in rule_text:
            continue
        if "access-validation" in rule_text or "oauth" in rule_text or "complete" in rule_text:
            continue
        endpoint = rule.endpoint
        original = app.view_functions.get(endpoint)
        if original is None or getattr(original, "_jom_site_review_truth_wrapped_v1_2", False):
            continue
        def make_wrapped(func):
            def wrapped(*args, **kwargs):
                site_key = kwargs.get("site_key") or (args[0] if args else None)
                result = func(*args, **kwargs)
                status = None
                headers = None
                response = result
                if isinstance(result, tuple):
                    response = result[0]
                    if len(result) > 1:
                        status = result[1]
                    if len(result) > 2:
                        headers = result[2]
                try:
                    payload = response.get_json(silent=True) if hasattr(response, "get_json") else None
                except Exception:
                    payload = None
                if not isinstance(payload, dict):
                    return result
                payload = _jom_site_review_align_payload_v1_2(site_key, payload)
                new_response = jsonify(payload)
                if status is not None and headers is not None:
                    return new_response, status, headers
                if status is not None:
                    return new_response, status
                return new_response
            wrapped.__name__ = getattr(func, "__name__", "jom_site_review_truth_wrapped")
            wrapped._jom_site_review_truth_wrapped_v1_2 = True
            return wrapped
        app.view_functions[endpoint] = make_wrapped(original)

_jom_register_site_review_truth_wrapper_v1_2()
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
        "backend_final_truth_chain_status.json", "backend_legacy_truth_eradication_status.json",
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
