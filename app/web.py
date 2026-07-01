from flask import Flask, jsonify
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.runtime.admin_enriched_chain import run_pipeline as run_snapshot
from app.runtime.operational_source_recovery import run_pipeline as run_recovery
from app.operational.operator_surface import build_alerts, build_operator_surface

app = Flask(__name__)

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "static" / "data"
RUNTIME_STATUS_PATH = DATA_PATH / "runtime_execution_status.json"
RUNTIME_HISTORY_PATH = DATA_PATH / "runtime_execution_history.json"

_runtime_lock = threading.Lock()


def now_utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(filename):
    path = DATA_PATH / filename
    if not path.exists():
        return {"error": f"{filename} not found"}
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path, payload):
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def write_runtime_status(payload):
    return write_json(RUNTIME_STATUS_PATH, payload)


def read_runtime_status():
    if not RUNTIME_STATUS_PATH.exists():
        return {
            "state": "idle",
            "last_action": None,
            "last_started_at_utc": None,
            "last_finished_at_utc": None,
            "last_result_status": None,
            "last_error": None,
            "running": False,
            "source": "runtime_execution_status.json not yet created"
        }
    try:
        return json.loads(RUNTIME_STATUS_PATH.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"state": "unknown", "running": False, "last_error": f"Unable to read runtime status: {exc}"}


def read_runtime_history():
    if not RUNTIME_HISTORY_PATH.exists():
        return []
    try:
        payload = json.loads(RUNTIME_HISTORY_PATH.read_text(encoding="utf-8-sig"))
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def append_runtime_history(event):
    history = read_runtime_history()
    history.append(event)
    history = history[-100:]
    write_json(RUNTIME_HISTORY_PATH, history)
    return history


def execute_guarded(action_name, runner):
    acquired = _runtime_lock.acquire(blocking=False)
    if not acquired:
        current = read_runtime_status()
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
        "last_error": None
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
            "last_result": result
        })
        append_runtime_history({
            "action": action_name,
            "started_at_utc": started,
            "finished_at_utc": finished,
            "status": "success",
            "result_status": result_status
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
            "last_error": str(exc)
        })
        append_runtime_history({
            "action": action_name,
            "started_at_utc": started,
            "finished_at_utc": finished,
            "status": "failed",
            "error": str(exc)
        })
        return jsonify({"status": "error", "message": str(exc), "runtime_status": status_payload}), 500
    finally:
        _runtime_lock.release()


@app.route("/")
def home():
    return jsonify({
        "status": "JOM backend running",
        "mode": "pack_v1_operator_platform_combined",
        "actions": {
            "refresh": "/runtime/refresh",
            "recover": "/runtime/recover",
            "status": "/runtime/status"
        },
        "operator_endpoints": {
            "surface": "/operator/surface",
            "alerts": "/operator/alerts",
            "observability": "/operator/observability"
        },
        "data_endpoints": {
            "admin_truth": "/admin/truth",
            "estate_product_access": "/estate/product-access",
            "user_footprint": "/users/footprint",
            "site_registry": "/registry/sites"
        }
    })


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
    return jsonify(read_runtime_status())


@app.route("/runtime/history")
def runtime_history():
    return jsonify(read_runtime_history())


@app.route("/runtime/refresh")
def runtime_refresh():
    return execute_guarded("refresh", run_snapshot)


@app.route("/runtime/recover")
def runtime_recover():
    return execute_guarded("recover", run_recovery)


@app.route("/operator/alerts")
def operator_alerts():
    return jsonify({"alerts": build_alerts()})


@app.route("/operator/surface")
def operator_surface():
    return jsonify(build_operator_surface())


@app.route("/operator/observability")
def operator_observability():
    return jsonify({"runtime_status": read_runtime_status(), "runtime_history": read_runtime_history()})


@app.route("/health")
def health():
    status = read_runtime_status()
    surface = build_operator_surface()
    return jsonify({"status": "healthy" if not status.get("running") else "busy", "runtime": status, "operator_posture": surface.get("posture"), "alert_summary": surface.get("alert_summary")})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
