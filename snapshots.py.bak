import json
import os
from datetime import datetime


SNAPSHOT_DIR = "snapshots"
LATEST_FILE = os.path.join(SNAPSHOT_DIR, "latest_snapshot.json")
INDEX_FILE = os.path.join(SNAPSHOT_DIR, "snapshot_index.json")


def ensure_snapshot_dir():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)


def _get_timestamp_strings():
    now = datetime.now()
    return {
        "timestamp": now.strftime("%Y-%m-%d_%H-%M-%S"),
        "date_folder": now.strftime("%Y-%m-%d"),
        "run_time_local": now.isoformat()
    }


def _build_snapshot_payload(snapshot_data):
    timestamp_info = _get_timestamp_strings()

    payload = {
        "snapshot_meta": {
            "created_at_local": timestamp_info["run_time_local"],
            "snapshot_timestamp": timestamp_info["timestamp"],
            "snapshot_version": "2.0"
        },
        "site_count": snapshot_data.get("site_count", 0),
        "healthy_count": snapshot_data.get("healthy_count", 0),
        "warning_count": snapshot_data.get("warning_count", 0),
        "critical_count": snapshot_data.get("critical_count", 0),
        "total_risk_score": snapshot_data.get("total_risk_score", 0),
        "average_risk_score": snapshot_data.get("average_risk_score", 0),
        "total_blocking_failures": snapshot_data.get("total_blocking_failures", 0),
        "total_permission_limited_checks": snapshot_data.get("total_permission_limited_checks", 0),
        "sites": snapshot_data.get("sites", [])
    }

    return payload


def _load_index():
    if not os.path.exists(INDEX_FILE):
        return {
            "snapshots": []
        }

    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {
            "snapshots": []
        }


def _save_index(index_data):
    with open(INDEX_FILE, "w", encoding="utf-8") as handle:
        json.dump(index_data, handle, indent=2)


def _append_to_index(timestamp_file, payload):
    index_data = _load_index()

    snapshot_meta = payload.get("snapshot_meta", {})
    entry = {
        "created_at_local": snapshot_meta.get("created_at_local"),
        "snapshot_timestamp": snapshot_meta.get("snapshot_timestamp"),
        "file": timestamp_file,
        "site_count": payload.get("site_count", 0),
        "healthy_count": payload.get("healthy_count", 0),
        "warning_count": payload.get("warning_count", 0),
        "critical_count": payload.get("critical_count", 0),
        "total_risk_score": payload.get("total_risk_score", 0)
    }

    index_data["snapshots"].append(entry)
    _save_index(index_data)


def save_snapshot(snapshot_data):
    ensure_snapshot_dir()

    payload = _build_snapshot_payload(snapshot_data)
    timestamp_info = _get_timestamp_strings()

    # Optional day-based folder structure
    date_folder_path = os.path.join(SNAPSHOT_DIR, timestamp_info["date_folder"])
    os.makedirs(date_folder_path, exist_ok=True)

    timestamp_file = os.path.join(
        date_folder_path,
        f"snapshot_{timestamp_info['timestamp']}.json"
    )

    with open(timestamp_file, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    with open(LATEST_FILE, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    _append_to_index(timestamp_file, payload)

    return {
        "latest_file": LATEST_FILE,
        "timestamp_file": timestamp_file,
        "index_file": INDEX_FILE
    }


def load_latest_snapshot():
    if not os.path.exists(LATEST_FILE):
        return None

    try:
        with open(LATEST_FILE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def load_snapshot_index():
    return _load_index()


def get_latest_snapshot_entry():
    index_data = _load_index()
    snapshots = index_data.get("snapshots", [])

    if not snapshots:
        return None

    return snapshots[-1]


def prune_snapshot_index(max_entries=100):
    """
    Keeps only the most recent index entries.
    Does not delete snapshot files from disk.
    Useful to stop the index file growing forever.
    """
    index_data = _load_index()
    snapshots = index_data.get("snapshots", [])

    if len(snapshots) <= max_entries:
        return {
            "pruned": False,
            "remaining_entries": len(snapshots)
        }

    index_data["snapshots"] = snapshots[-max_entries:]
    _save_index(index_data)

    return {
        "pruned": True,
        "remaining_entries": len(index_data["snapshots"])
    }