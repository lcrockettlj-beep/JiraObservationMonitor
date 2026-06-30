from __future__ import annotations

import json
import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "reports" / "python_import_bootstrap_verify.json"
BOOTSTRAP_STATUS = ROOT / "reports" / "python_import_bootstrap_status.json"


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": str(exc)}


def run(cmd):
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
    }


def main():
    compile_errors = []
    compiled = 0
    for path in sorted((ROOT / "scripts").glob("*.py")):
        try:
            py_compile.compile(str(path), doraise=True)
            compiled += 1
        except Exception as exc:
            compile_errors.append({"file": path.relative_to(ROOT).as_posix(), "error": str(exc)})

    import_probe = run([
        sys.executable,
        "-c",
        "import sys; from pathlib import Path; sys.path.insert(0, str(Path.cwd())); import jira_client; print('jira_client import ok')",
    ])

    build_estate_compile_probe = run([
        sys.executable,
        "-m",
        "py_compile",
        "scripts/build_estate_product_access.py",
    ])

    status = read_json(BOOTSTRAP_STATUS, {}) or {}
    payload = {
        "schema": "jom-python-import-bootstrap-verify-v1",
        "compiled_scripts": compiled,
        "compile_error_count": len(compile_errors),
        "compile_errors": compile_errors,
        "jira_client_import_probe": import_probe,
        "build_estate_product_access_compile_probe": build_estate_compile_probe,
        "bootstrap_status_summary": {
            "patched_count": status.get("patched_count"),
            "skipped_count": status.get("skipped_count"),
            "error_count": status.get("error_count"),
            "backup_root": status.get("backup_root"),
        },
        "safe": len(compile_errors) == 0 and import_probe.get("returncode") == 0 and build_estate_compile_probe.get("returncode") == 0,
    }
    STATUS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({
        "safe": payload["safe"],
        "compiled_scripts": compiled,
        "compile_error_count": len(compile_errors),
        "patched_count": status.get("patched_count"),
        "status_file": str(STATUS),
    }, indent=2))


if __name__ == "__main__":
    main()
