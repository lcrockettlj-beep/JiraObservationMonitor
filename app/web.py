from flask import Flask, jsonify
import json
import os

from app.runtime.admin_enriched_chain import run_pipeline as run_snapshot
from app.runtime.operational_source_recovery import run_pipeline as run_recovery

app = Flask(__name__)

DATA_PATH = os.path.join("static", "data")


def load_json(filename):
    path = os.path.join(DATA_PATH, filename)
    if not os.path.exists(path):
        return {"error": f"{filename} not found"}
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


@app.route("/")
def home():
    return jsonify({
        "status": "JOM backend running",
        "mode": "pack_v6_runtime_command_resolution",
        "actions": {
            "refresh": "/runtime/refresh",
            "recover": "/runtime/recover"
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


@app.route("/runtime/refresh")
def runtime_refresh():
    result = run_snapshot()
    return jsonify({"status": "success", "message": "refresh executed", "result": result})


@app.route("/runtime/recover")
def runtime_recover():
    result = run_recovery()
    return jsonify({"status": "success", "message": "recovery executed", "result": result})


@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
