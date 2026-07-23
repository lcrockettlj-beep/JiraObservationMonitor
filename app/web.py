from __future__ import annotations

from flask import Flask, jsonify, render_template, send_from_directory, request
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



# --- JOM LIVE WEBSITE TRUTH POLICY v1 START ---
# Website-facing routes may use only live/runtime-refreshed data or generated outputs
# that have a freshness/status contract. Legacy/manual snapshots must not be exposed as website truth.
LIVE_WEBSITE_TRUTH_FILES = {
    "runtime_execution_status.json",
    "runtime_execution_history.json",
    "runtime_live_truth_status.json",
    "runtime_refresh_status.json",
    "source_freshness_audit.json",
    "source_reliability_status.json",
    "admin_enriched_refresh_status.json",
    "product_access_refresh_status.json",
    "site_registry.json",
    "estate_product_access.json",
    "estate_access_truth.json",
    "admin_truth_v2.json",
    "user_footprint.json",
    "site_lifecycle_decisions.json",
    "site_access_validation.json",
    "monitored_sites.json",
    "site_onboarding_review.json",
}

LEGACY_NON_WEBSITE_TRUTH_FILES = {
    "latest_run.json",
    "latest_run_pretty.json",
    "latest_run_safe_partial.json",
    "latest_run_admin_enriched.json",
    "latest_run_admin_enriched_pretty.json",
    "billing_seats.json",
    "latest_snapshot.json",
    "snapshot_index.json",
}

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
            source_file="static/data/site_registry.json",
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
        source_file="static/data/site_registry.json",
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
        source_file="static/data/admin_truth_v2.json",
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
        "source_freshness": _contract_payload("source_freshness", freshness, source_file="static/data/source_freshness_audit.json", contract_type="generated_status_cache"),
        "source_reliability": _contract_payload("source_reliability", reliability, source_file="static/data/source_reliability_status.json", contract_type="generated_status_cache"),
        "runtime_live_truth_status": _contract_payload("runtime_live_truth_status", live_truth, source_file="static/data/runtime_live_truth_status.json", contract_type="generated_live_truth_status", allow_stale=True),
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
        source_file="static/data/user_footprint.json",
        contract_type="generated_cache_contract",
        live_builder="runtime refresh/admin enriched chain",
    )


# --- JOM BACKEND ROUTE CONTRACTS v1 END ---




@app.route("/")
def home():
    return render_template("home.html", **home_context())

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
            admin_path = ROOT / "latest_run_admin_enriched_pretty.json"
            if not admin_path.exists():
                admin_path = ROOT / "latest_run_admin_enriched.json"
            truth_payload = build_access_truth(
                product_payload,
                admin_path,
                ROOT / "static" / "data" / "billing_seats.json",
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
        # rollback_to_discovered_v1: restore site back to discovered everywhere JOM reads lifecycle state.
        registry = load_json("site_registry.json", {})
        target = _normalise_site_key(site_key) if "_normalise_site_key" in globals() else str(site_key).lower()
        for site in registry.get("sites", []) if isinstance(registry, dict) else []:
            if isinstance(site, dict) and str(site.get("site_key") or site.get("key") or site.get("site_name") or site.get("name") or "").lower() == target:
                site["classification"] = "discovered"
                site["is_monitored"] = False
                site["can_approve"] = True
                site["collector_onboarding_status"] = "not_requested"
                site.pop("monitoring_enabled_at_utc", None)
                site.pop("monitoring_enabled_by", None)
        if "_recalculate_registry_summary" in globals():
            _recalculate_registry_summary(registry)
        write_json(DATA_PATH / "site_registry.json", registry)
        monitored_payload = load_json("monitored_sites.json", {})
        if isinstance(monitored_payload, dict):
            monitored_payload["monitored_sites"] = [row for row in monitored_payload.get("monitored_sites", []) if not (isinstance(row, dict) and str(row.get("site_key", "")).lower() == target)]
            monitored_payload.setdefault("ignored_sites", [])
            monitored_payload["updated_at_utc"] = now_utc()
            write_json(DATA_PATH / "monitored_sites.json", monitored_payload)
        validation_payload = load_json("site_access_validation.json", {})
        if isinstance(validation_payload, dict):
            validation_payload.setdefault("validations", {}).pop(site_key, None)
            validation_payload["generated_at_utc"] = now_utc()
            write_json(DATA_PATH / "site_access_validation.json", validation_payload)
        record = {
            "site_key": site_key,
            "decision": "discovered",
            "previous_decision": previous.get("decision"),
            "reason": payload.get("reason") or "rolled back to discovered",
            "actor": payload.get("actor") or "operator",
            "decided_at_utc": now_utc(),
            "reversible": True,
            "requires_credentials": False,
            "next_state": "discovered",
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
        message = "Site rolled back to Discovered. Estate and Command Centre will show it as review work again."
    return jsonify({"ok": True, "message": message, "record": record})

@app.route("/api/site-lifecycle/decisions")
def api_site_lifecycle_decisions():
    payload = load_json("site_lifecycle_decisions.json", {})
    if not isinstance(payload, dict) or not payload:
        payload = {"schema": "jom-site-lifecycle-decisions-v1", "decisions": {}, "history": []}
    payload.setdefault("decisions", {})
    payload.setdefault("history", [])
    return jsonify(payload)



# --- credential_access_validation_v1 START ---
SITE_ACCESS_VALIDATION_PATH = DATA_PATH / "site_access_validation.json"

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
    payload = load_json("site_access_validation.json", {})
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
def api_site_review_access_validation(site_key):
    payload = _load_site_access_validation()
    return jsonify({"ok": True, "site_key": site_key, "validation": payload.get("validations", {}).get(site_key, {})})


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
    validations = _load_site_access_validation() if "_load_site_access_validation" in globals() else load_json("site_access_validation.json", {"validations": {}})
    validation_state = validations.get("validations", {}).get(site_key, {}) if isinstance(validations, dict) else {}
    if validation_state.get("access_valid") is not True:
        return jsonify({"ok": False, "error": "site has not passed access validation", "site_key": site_key, "validation": validation_state}), 409
    oauth_coverage = _oauth_coverage_payload(site_key)
    if oauth_coverage.get("monitoring_allowed") is not True:
        status_code = 409 if oauth_coverage.get("ok") else 404
        return jsonify({
            "ok": False,
            "error": "oauth_authorisation_required",
            "site_key": site_key,
            "coverage": oauth_coverage,
            "message": "OAuth product access must be authorised before monitoring can be enabled.",
        }), status_code
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

@app.route("/api/site-review/<path:site_key>/validate-access")
def api_site_review_validate_access(site_key):
    return jsonify(_jom_site_live_review_contract(site_key))


@app.route("/api/site-review/<path:site_key>/live")
def api_site_review_live_contract(site_key):
    return jsonify(_jom_site_live_review_contract(site_key))


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

if __name__ == "__main__":
    app.run(debug=True, port=5000)










