import json
import requests
import sys
from datetime import datetime

RUNTIME_URL = "http://127.0.0.1:5000/api/data"
SNAPSHOT_FILE = "docs/control/runtime_contract_snapshot.json"


def fetch_runtime():
    try:
        response = requests.get(RUNTIME_URL)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("❌ ERROR: Cannot fetch runtime from /api/data")
        print(f"Details: {e}")
        sys.exit(1)


def load_snapshot():
    try:
        with open(SNAPSHOT_FILE, "r", encoding="utf-8-sig") as f:
            snapshot = json.load(f)
        if "data" in snapshot:
            return snapshot["data"]
        return snapshot
    except Exception as e:
        print("❌ ERROR: Cannot load snapshot file")
        print(f"Details: {e}")
        sys.exit(1)


def flatten_keys(data, parent_key=""):
    keys = []
    if isinstance(data, dict):
        for k, v in data.items():
            full_key = f"{parent_key}.{k}" if parent_key else k
            keys.extend(flatten_keys(v, full_key))
    elif isinstance(data, list):
        for item in data[:3]:
            keys.extend(flatten_keys(item, f"{parent_key}[]"))
    else:
        keys.append(parent_key)
    return keys


def main():
    print("🔍 Jira Observation Monitor — Contract Validator\n")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"🕒 Validation time: {now}\n")

    print("📡 Fetching runtime from /api/data ...")
    runtime_data = fetch_runtime()
    print("✅ Runtime fetched\n")

    print("📁 Loading snapshot file ...")
    snapshot_data = load_snapshot()
    print("✅ Snapshot loaded\n")

    runtime_keys = set(flatten_keys(runtime_data))
    snapshot_keys = set(flatten_keys(snapshot_data))

    print(f"🔢 Runtime fields:  {len(runtime_keys)}")
    print(f"🔢 Snapshot fields: {len(snapshot_keys)}\n")

    new_fields = runtime_keys - snapshot_keys
    missing_fields = snapshot_keys - runtime_keys

    if not new_fields and not missing_fields:
        print("✅ NO STRUCTURE CHANGES DETECTED")
        return

    if new_fields:
        print("⚠️ NEW FIELDS DETECTED:")
        for field in sorted(new_fields):
            print(f"  + {field}")
        print()

    if missing_fields:
        print("❌ MISSING FIELDS DETECTED:")
        for field in sorted(missing_fields):
            print(f"  - {field}")
        print()

    print("📌 ACTION REQUIRED:")
    print("- Update mechanics_change_log.md")
    print("- Update JSON contract manual if needed")
    print("- Take new runtime snapshot if change is intentional")


if __name__ == "__main__":
    main()