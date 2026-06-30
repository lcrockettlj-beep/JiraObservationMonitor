from flask import Flask, jsonify
import json
import os

# ✅ Runtime pipelines
from app.runtime.admin_enriched_chain import run_pipeline as run_snapshot
from app.runtime.operational_source_recovery import run as run_recovery

app = Flask(__name__)

DATA_PATH = os.path.join("static", "data")


def load_json(filename):
    path = os.path.join(DATA_PATH, filename)
    if not os.path.exists(path):
        return {"error": f"{filename} not found"}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# =========================
# ✅ ROOT
# =========================

@app.route("/")
def home():
    return jsonify({
        "status": "JOM backend running",
        "actions": {
            "refresh_full": "/runtime/refresh",
            "recover_sources": "/runtime/recover"
        }
    })


# =========================
# ✅ DATA ENDPOINTS
# =========================

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


# =========================
# ✅ LIVE ACTIONS
# =========================

@app.route("/runtime/refresh")
def runtime_refresh():
    run_snapshot()
    return jsonify({"status": "success", "message": "Full refresh completed"})


@app.route("/runtime/recover")
def runtime_recover():
    try:
        run_recovery()
        return jsonify({"status": "success", "message": "Recovery completed"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# =========================
# ✅ HEALTH
# =========================

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


# =========================
# ✅ RUN SERVER
# =========================

if __name__ == "__main__":
    app.run(debug=True, port=5000)