
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
SNAPSHOT_DIR = BASE_DIR / "snapshots"
LATEST_FILE = SNAPSHOT_DIR / "latest_snapshot.json"
INDEX_FILE = SNAPSHOT_DIR / "snapshot_index.json"
SNAPSHOT_FILE_RE = re.compile(
    r"^snapshot_(?P<ts>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})(?:_anchor_(?P<anchor>[a-zA-Z0-9_-]+))?\.json$"
)


def ensure_snapshot_dir() -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _get_timestamp_strings() -> Dict[str, str]:
    now = datetime.now()
    return {
        "timestamp": now.strftime("%Y-%m-%d_%H-%M-%S"),
        "date_folder": now.strftime("%Y-%m-%d"),
        "run_time_local": now.isoformat(timespec="seconds"),
    }


def _build_snapshot_payload(snapshot_data: Dict[str, Any]) -> Dict[str, Any]:
    timestamp_info = _get_timestamp_strings()
    return {
        "snapshot_meta": {
            "created_at_local": timestamp_info["run_time_local"],
            "snapshot_timestamp": timestamp_info["timestamp"],
            "snapshot_version": "3.0",
        },
        "site_count": snapshot_data.get("site_count", 0),
        "healthy_count": snapshot_data.get("healthy_count", 0),
        "warning_count": snapshot_data.get("warning_count", 0),
        "critical_count": snapshot_data.get("critical_count", 0),
        "total_risk_score": snapshot_data.get("total_risk_score", 0),
        "average_risk_score": snapshot_data.get("average_risk_score", 0),
        "total_blocking_failures": snapshot_data.get("total_blocking_failures", 0),
        "total_permission_limited_checks": snapshot_data.get("total_permission_limited_checks", 0),
        "sites": snapshot_data.get("sites", []),
    }


def _safe_load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _parse_snapshot_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%d_%H-%M-%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _snapshot_file_timestamp(path: Path) -> Optional[datetime]:
    match = SNAPSHOT_FILE_RE.match(path.name)
    if not match:
        return None
    return _parse_snapshot_timestamp(match.group("ts"))


def _discover_snapshot_files() -> List[Path]:
    ensure_snapshot_dir()
    files: List[Path] = []
    for path in SNAPSHOT_DIR.rglob("snapshot_*.json"):
        if path.name in {LATEST_FILE.name, INDEX_FILE.name}:
            continue
        if path.is_file() and SNAPSHOT_FILE_RE.match(path.name):
            files.append(path)
    files.sort(key=lambda p: (_snapshot_file_timestamp(p) or datetime.min, p.stat().st_mtime))
    return files


def _build_entry_from_file(path: Path) -> Dict[str, Any]:
    payload = _safe_load_json(path) or {}
    snapshot_meta = payload.get("snapshot_meta", {}) if isinstance(payload.get("snapshot_meta"), dict) else {}
    parsed_from_name = _snapshot_file_timestamp(path)
    parsed_from_meta = _parse_snapshot_timestamp(snapshot_meta.get("snapshot_timestamp"))
    chosen_dt = parsed_from_meta or parsed_from_name or datetime.fromtimestamp(path.stat().st_mtime)
    created_at_local = snapshot_meta.get("created_at_local")
    if not created_at_local:
        created_at_local = chosen_dt.strftime("%Y-%m-%d %H:%M:%S")
    snapshot_timestamp = snapshot_meta.get("snapshot_timestamp")
    if not snapshot_timestamp:
        snapshot_timestamp = chosen_dt.strftime("%Y-%m-%d_%H-%M-%S")
    return {
        "created_at_local": created_at_local,
        "file": str(path.resolve()),
        "snapshot_timestamp": snapshot_timestamp,
        "site_count": payload.get("site_count", 0),
        "healthy_count": payload.get("healthy_count", 0),
        "warning_count": payload.get("warning_count", 0),
        "critical_count": payload.get("critical_count", 0),
        "total_risk_score": payload.get("total_risk_score", 0),
    }


def _save_index(index_data: Dict[str, Any]) -> None:
    ensure_snapshot_dir()
    INDEX_FILE.write_text(json.dumps(index_data, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_index() -> Dict[str, Any]:
    payload = _safe_load_json(INDEX_FILE)
    if not payload:
        return {"snapshots": []}
    snapshots = payload.get("snapshots")
    if not isinstance(snapshots, list):
        payload["snapshots"] = []
    return payload


def rebuild_snapshot_index_from_disk(save: bool = True) -> Dict[str, Any]:
    entries = [_build_entry_from_file(path) for path in _discover_snapshot_files()]
    index_data = {"snapshots": entries}
    if save:
        _save_index(index_data)
    return index_data


def _sync_latest_file_from_entry(entry: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not entry:
        return None
    file_path = Path(str(entry.get("file", "")))
    payload = _safe_load_json(file_path)
    if payload is None:
        return None
    ensure_snapshot_dir()
    LATEST_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def save_snapshot(snapshot_data: Dict[str, Any], store_in_date_folder: bool = False) -> Dict[str, str]:
    ensure_snapshot_dir()
    payload = _build_snapshot_payload(snapshot_data)
    timestamp_info = _get_timestamp_strings()

    if store_in_date_folder:
        date_folder_path = SNAPSHOT_DIR / timestamp_info["date_folder"]
        date_folder_path.mkdir(parents=True, exist_ok=True)
        timestamp_file = date_folder_path / f"snapshot_{timestamp_info['timestamp']}.json"
    else:
        timestamp_file = SNAPSHOT_DIR / f"snapshot_{timestamp_info['timestamp']}.json"

    timestamp_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    LATEST_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    rebuild_snapshot_index_from_disk(save=True)
    return {
        "latest_file": str(LATEST_FILE),
        "timestamp_file": str(timestamp_file),
        "index_file": str(INDEX_FILE),
    }


def load_latest_snapshot() -> Optional[Dict[str, Any]]:
    entry = get_latest_snapshot_entry()
    if entry:
        payload = _sync_latest_file_from_entry(entry)
        if payload is not None:
            return payload
    return _safe_load_json(LATEST_FILE)


def load_snapshot_index() -> Dict[str, Any]:
    # Disk truth wins: rebuild index from actual snapshot files.
    return rebuild_snapshot_index_from_disk(save=True)


def get_latest_snapshot_entry() -> Optional[Dict[str, Any]]:
    index_data = rebuild_snapshot_index_from_disk(save=True)
    snapshots = index_data.get("snapshots", [])
    if not snapshots:
        return None
    return snapshots[-1]


def prune_snapshot_index(max_entries: int = 100) -> Dict[str, Any]:
    """
    Keeps only the most recent index entries in snapshot_index.json.
    This does not delete snapshot files from disk.
    The next disk rebuild can repopulate the helper index if older files still exist.
    """
    index_data = rebuild_snapshot_index_from_disk(save=False)
    snapshots = index_data.get("snapshots", [])
    if len(snapshots) <= max_entries:
        _save_index(index_data)
        return {"pruned": False, "remaining_entries": len(snapshots)}
    index_data["snapshots"] = snapshots[-max_entries:]
    _save_index(index_data)
    return {"pruned": True, "remaining_entries": len(index_data["snapshots"]) }
