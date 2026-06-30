from __future__ import annotations

import io
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKUP_ROOT = PROJECT_ROOT / "backups" / "latest_runtime"
CURRENT_DIR = BACKUP_ROOT / "current"
HISTORY_DIR = BACKUP_ROOT / "history"
CURRENT_MANIFEST = BACKUP_ROOT / "latest_manifest.json"

FILES_TO_BACKUP: List[Tuple[Path, str]] = [
    (PROJECT_ROOT / "latest_run.json", "latest_run.json"),
    (PROJECT_ROOT / "latest_run_pretty.json", "latest_run_pretty.json"),
    (PROJECT_ROOT / "latest_run_safe_partial.json", "latest_run_safe_partial.json"),
    (PROJECT_ROOT / "latest_run_admin_enriched.json", "latest_run_admin_enriched.json"),
    (PROJECT_ROOT / "latest_run_admin_enriched_pretty.json", "latest_run_admin_enriched_pretty.json"),
    (PROJECT_ROOT / "latest_run_alerted.json", "latest_run_alerted.json"),
    (PROJECT_ROOT / "latest_run_alerted_pretty.json", "latest_run_alerted_pretty.json"),
    (PROJECT_ROOT / "latest_run_intelligence.json", "latest_run_intelligence.json"),
    (PROJECT_ROOT / "latest_run_intelligence_pretty.json", "latest_run_intelligence_pretty.json"),
    (PROJECT_ROOT / "snapshots" / "latest_snapshot.json", "latest_snapshot.json"),
    (PROJECT_ROOT / "snapshots" / "snapshot_index.json", "snapshot_index.json"),
]


def _now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _now_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_backup_dirs() -> None:
    CURRENT_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def _copy_one(source: Path, current_dir: Path, history_dir: Path) -> Dict[str, str]:
    current_target = current_dir / source.name
    history_target = history_dir / source.name
    shutil.copy2(source, current_target)
    shutil.copy2(source, history_target)
    return {
        "source": str(source),
        "current_target": str(current_target),
        "history_target": str(history_target),
        "size_bytes": str(source.stat().st_size),
    }


def backup_runtime_chain() -> Dict[str, object]:
    ensure_backup_dirs()
    stamp = _now_stamp()
    history_dir = HISTORY_DIR / stamp
    history_dir.mkdir(parents=True, exist_ok=True)

    copied: List[Dict[str, str]] = []
    missing: List[str] = []

    for source, _label in FILES_TO_BACKUP:
        if source.exists() and source.is_file():
            copied.append(_copy_one(source, CURRENT_DIR, history_dir))
        else:
            missing.append(str(source))

    manifest: Dict[str, object] = {
        "created_at_local": _now_local(),
        "backup_stamp": stamp,
        "project_root": str(PROJECT_ROOT),
        "current_dir": str(CURRENT_DIR),
        "history_dir": str(history_dir),
        "copied_count": len(copied),
        "missing_count": len(missing),
        "copied_files": copied,
        "missing_files": missing,
    }

    (history_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    CURRENT_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> int:
    manifest = backup_runtime_chain()
    print("📦 Runtime backup complete")
    print(f"Backup stamp: {manifest.get('backup_stamp')}")
    print(f"Copied files: {manifest.get('copied_count', 0)}")
    print(f"Missing files: {manifest.get('missing_count', 0)}")
    print(f"Current backup dir: {manifest.get('current_dir')}")
    print(f"History backup dir: {manifest.get('history_dir')}")
    return 0 if int(manifest.get('copied_count', 0)) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
