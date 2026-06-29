from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
STATUS = ROOT / "reports" / "python_import_bootstrap_status.json"
BOOTSTRAP_IMPORT = "from _project_bootstrap import ensure_project_root_on_path\nensure_project_root_on_path()\n"

EXCLUDE = {
    "_project_bootstrap.py",
    "apply_python_import_bootstrap.py",
    "verify_python_import_bootstrap.py",
}

ROOT_MODULES = {
    p.stem
    for p in ROOT.glob("*.py")
    if p.is_file() and not p.name.startswith(".") and p.stem not in {"__init__"}
}


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def needs_bootstrap(text: str) -> bool:
    if "ensure_project_root_on_path" in text or "_project_bootstrap" in text:
        return False
    for module in sorted(ROOT_MODULES):
        if re.search(rf"(^|\n)\s*import\s+{re.escape(module)}(\s|\n|$)", text):
            return True
        if re.search(rf"(^|\n)\s*from\s+{re.escape(module)}\s+import\s+", text):
            return True
    return False


def insertion_index(lines: list[str]) -> int:
    idx = 0
    if lines and lines[0].startswith("#!"):
        idx = 1
    if idx < len(lines) and "coding" in lines[idx].lower():
        idx += 1
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx < len(lines) and lines[idx].startswith("from __future__ import"):
        idx += 1
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
    return idx


def apply() -> dict:
    backup_root = ROOT / "backups" / f"python_import_bootstrap_v1_{stamp()}"
    backup_root.mkdir(parents=True, exist_ok=True)
    patched = []
    skipped = []
    errors = []

    for path in sorted(SCRIPTS.glob("*.py")):
        if path.name in EXCLUDE:
            skipped.append({"file": path.relative_to(ROOT).as_posix(), "reason": "bootstrap tool file"})
            continue
        try:
            text = read(path)
            if not needs_bootstrap(text):
                skipped.append({"file": path.relative_to(ROOT).as_posix(), "reason": "no root-level import detected or already bootstrapped"})
                continue
            rel = path.relative_to(ROOT)
            backup = backup_root / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
            lines = text.splitlines(True)
            idx = insertion_index(lines)
            insert = ["\n", BOOTSTRAP_IMPORT, "\n"] if idx > 0 and idx < len(lines) and lines[idx-1].strip() else [BOOTSTRAP_IMPORT, "\n"]
            lines[idx:idx] = insert
            write(path, "".join(lines))
            patched.append({"file": rel.as_posix(), "backup": backup.relative_to(ROOT).as_posix()})
        except Exception as exc:
            errors.append({"file": path.relative_to(ROOT).as_posix(), "error": str(exc)})

    payload = {
        "schema": "jom-python-import-bootstrap-status-v1",
        "mode": "source-level-bootstrap-no-runtime-data-change",
        "backup_root": backup_root.as_posix(),
        "root_modules_detected": sorted(ROOT_MODULES),
        "patched_count": len(patched),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "patched": patched,
        "skipped": skipped,
        "errors": errors,
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "ok" if not errors else "attention",
        "patched_count": len(patched),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "status_file": str(STATUS),
    }, indent=2))
    return payload


if __name__ == "__main__":
    apply()
