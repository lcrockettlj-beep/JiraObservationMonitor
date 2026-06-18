import json
import datetime
import requests
from pathlib import Path

RUNTIME_URL = "http://127.0.0.1:5000/api/data"
SNAPSHOT_FILE = Path("docs/control/runtime_contract_snapshot.json")
LOG_FILE = Path("docs/control/mechanics_change_log.md")
AUDIT_FILE = Path("docs/control/audit_trail.md")


def fetch_runtime():
    response = requests.get(RUNTIME_URL, timeout=10)
    response.raise_for_status()
    return response.json()


def load_snapshot():
    with open(SNAPSHOT_FILE, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def flatten_keys(data, parent_key=""):
    keys = []
    if isinstance(data, dict):
        for k, v in data.items():
            full = f"{parent_key}.{k}" if parent_key else k
            keys.extend(flatten_keys(v, full))
    elif isinstance(data, list):
        for item in data[:3]:
            keys.extend(flatten_keys(item, f"{parent_key}[]"))
    else:
        keys.append(parent_key)
    return keys


def compare(runtime, snapshot):
    r_keys = set(flatten_keys(runtime))
    s_keys = set(flatten_keys(snapshot))
    added = r_keys - s_keys
    removed = s_keys - r_keys
    return added, removed


def append_log(added, removed):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not added and not removed:
        return
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n## {now} — Auto-detected runtime change\n")
        if added:
            f.write("**Added fields:**\n")
            for k in sorted(added):
                f.write(f"- + {k}\n")
        if removed:
            f.write("**Removed fields:**\n")
            for k in sorted(removed):
                f.write(f"- - {k}\n")


def append_audit(added, removed):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not added and not removed:
        return
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n[{now}] CHANGE DETECTED\n")
        f.write(f"  Added: {len(added)} | Removed: {len(removed)}\n")


def main():
    print("🛰 Auto Change Tracker")
    runtime = fetch_runtime()
    snapshot = load_snapshot()
    added, removed = compare(runtime, snapshot)

    if not added and not removed:
        print("✅ No structural changes")
        return

    append_log(added, removed)
    append_audit(added, removed)

    print(f"⚠️ Change detected → Logged ({len(added)} added, {len(removed)} removed)")


if __name__ == "__main__":
    main()