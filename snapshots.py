import json
import os
from datetime import datetime

SNAPSHOT_DIR = "snapshots"
LATEST_FILE = os.path.join(SNAPSHOT_DIR, "latest_snapshot.json")


def ensure_snapshot_dir():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)


def save_snapshot(snapshot_data):
    ensure_snapshot_dir()

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    timestamp_file = os.path.join(SNAPSHOT_DIR, f"snapshot_{timestamp}.json")

    with open(timestamp_file, "w", encoding="utf-8") as handle:
        json.dump(snapshot_data, handle, indent=2)

    with open(LATEST_FILE, "w", encoding="utf-8") as handle:
        json.dump(snapshot_data, handle, indent=2)

    return {
        "latest_file": LATEST_FILE,
        "timestamp_file": timestamp_file
    }


def load_latest_snapshot():
    if not os.path.exists(LATEST_FILE):
        return None

    with open(LATEST_FILE, "r", encoding="utf-8") as handle:
        return json.load(handle)
