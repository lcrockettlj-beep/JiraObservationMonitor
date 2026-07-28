from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DATA_PATH = ROOT / "runtime" / "data"

RUNTIME_DATA_PATH.mkdir(parents=True, exist_ok=True)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def runtime_data_path(filename: str | Path, *, for_write: bool = False) -> Path:
    """Resolve JOM runtime data paths.

    Final runtime rule:
    - all reads use runtime/data only
    - all writes use runtime/data only
    - missing runtime files must be reported by callers/validators instead of falling back
    """
    name = Path(filename).name
    return RUNTIME_DATA_PATH / name


def runtime_read_json(filename: str | Path, default: Any = None) -> Any:
    path = runtime_data_path(filename, for_write=False)
    if default is None:
        default = {}
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

    def rel(path: Path) -> str:
        try:
            return path.relative_to(ROOT).as_posix()
        except Exception:
            return path.as_posix()

    return {
        "filename": name,
        "active_path": rel(runtime_path),
        "runtime_exists": runtime_path.exists(),
        "using_runtime": runtime_path.exists(),
        "migration_state": "runtime" if runtime_path.exists() else "missing",
        "fallback_removed": True,
    }
