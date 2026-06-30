from flask import Flask, jsonify
import json
import os

app = Flask(__name__)

DATA_PATH = os.path.join("static", "data")


def load_json(filename):
    path = os.path.join(DATA_PATH, filename)
    if not os.path.exists(path):
        return {"error": f"{filename} not found"}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ✅ Home (sanity check)
@app.route("/")
def home():
    return jsonify({
        "status": "JOM backend running",
        "services": [
            "/admin/truth",
            "/estate/product-access",
            "/users/footprint",
            "/registry/sites"
        ]
    })


# ✅ Admin Truth
@app.route("/admin/truth")
def admin_truth():
    return jsonify(load_json("admin_truth_v2.json"))


# ✅ Estate Product Access
@app.route("/estate/product-access")
def estate_product_access():
    return jsonify(load_json("estate_product_access.json"))


# ✅ User footprint
@app.route("/users/footprint")
def user_footprint():
    return jsonify(load_json("user_footprint.json"))


# ✅ Site registry
@app.route("/registry/sites")
def site_registry():
    return jsonify(load_json("site_registry.json"))


# ✅ Run server
if __name__ == "__main__":
    app.run(debug=True, port=5000)
