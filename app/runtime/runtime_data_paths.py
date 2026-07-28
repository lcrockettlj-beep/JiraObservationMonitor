from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DATA_PATH = ROOT / "runtime" / "data"
STATIC_DATA_PATH = ROOT / "static" / "data"
RUNTIME_DATA_PATH.mkdir(parents=True, exist_ok=True)

def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def runtime_data_path(filename: str | Path, *, for_write: bool = False) -> Path:
    name = Path(filename).name
    runtime_path = RUNTIME_DATA_PATH / name
    static_path = STATIC_DATA_PATH / name
    if for_write:
        return runtime_path
    if runtime_path.exists():
        return runtime_path
    return static_path

def runtime_read_json(filename: str | Path, default: Any = None) -> Any:
    if default is None:
        default = {}
    path = runtime_data_path(filename, for_write=False)
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default
    return default

def runtime_write_json(filename: str | Path, payload: Any) -> Path:
    path = runtime_data_path(filename, for_write=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path

def runtime_path_status(filename: str | Path) -> dict[str, Any]:
    name = Path(filename).name
    runtime_path = RUNTIME_DATA_PATH / name
    static_path = STATIC_DATA_PATH / name
    active_path = runtime_data_path(name, for_write=False)
    def rel(path: Path) -> str:
        try:
            return str(path.relative_to(ROOT)).replace("\\", "/")
        except Exception:
            return str(path)
    return {
        "filename": name,
        "active_path": rel(active_path),
        "runtime_exists": runtime_path.exists(),
        "static_exists": static_path.exists(),
        "using_runtime": runtime_path.exists(),
        "using_static_fallback": (not runtime_path.exists()) and static_path.exists(),
        "migration_state": "runtime" if runtime_path.exists() else ("static_fallback" if static_path.exists() else "missing"),
    }
