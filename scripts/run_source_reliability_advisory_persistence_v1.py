from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "reports" / "source_reliability_advisory_persistence_status.json"
SCRIPT = ROOT / "scripts" / "source_reliability_audit.py"
ADVISORY_MODULE = ROOT / "app" / "audits" / "source_reliability_advisory.py"
RUNTIME_STATUS = ROOT / "static" / "data" / "runtime_refresh_status.json"
SOURCE_RELIABILITY = ROOT / "static" / "data" / "source_reliability_status.json"
EXPECTED_NOTE = "Runtime collector was not requested. Status inferred from latest_run.json freshness."

ADVISORY_MODULE_CONTENT = 'from __future__ import annotations\n\nimport json\nfrom datetime import datetime, timezone\nfrom pathlib import Path\n\nEXPECTED_NOTE = "Runtime collector was not requested. Status inferred from latest_run.json freshness."\n\n\ndef now_utc() -> str:\n    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")\n\n\ndef read_json(path: Path):\n    if not path.exists():\n        return None\n    try:\n        return json.loads(path.read_text(encoding="utf-8"))\n    except Exception as exc:\n        return {"_read_error": str(exc)}\n\n\ndef write_json(path: Path, payload) -> None:\n    path.parent.mkdir(parents=True, exist_ok=True)\n    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")\n\n\ndef runtime_review_is_expected(runtime_status: dict | None) -> tuple[bool, str]:\n    if not isinstance(runtime_status, dict):\n        return False, "runtime_refresh_status.json is missing or unreadable"\n    if runtime_status.get("overall_status") != "review":\n        return False, "runtime overall_status is not review"\n    if runtime_status.get("run_collector_requested") is not False:\n        return False, "run_collector_requested is not false"\n    steps = runtime_status.get("steps") or []\n    collector_steps = [s for s in steps if isinstance(s, dict) and s.get("key") == "runtime_collector"]\n    if not collector_steps:\n        return False, "runtime_collector step missing"\n    collector = collector_steps[0]\n    if collector.get("status") != "review":\n        return False, "runtime_collector status is not review"\n    note = collector.get("note") or ""\n    if EXPECTED_NOTE not in note:\n        return False, "runtime_collector review note is not the expected no-collector-requested note"\n    return True, "runtime collector review is expected because collector was intentionally not requested"\n\n\ndef align_source_reliability(project_root: Path | str | None = None) -> dict:\n    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]\n    runtime_path = root / "static" / "data" / "runtime_refresh_status.json"\n    reliability_path = root / "static" / "data" / "source_reliability_status.json"\n\n    runtime_status = read_json(runtime_path)\n    reliability = read_json(reliability_path)\n    expected, reason = runtime_review_is_expected(runtime_status)\n\n    if not expected or not isinstance(reliability, dict):\n        return {\n            "aligned": False,\n            "reason": reason,\n            "path": str(reliability_path),\n        }\n\n    summary = reliability.setdefault("summary", {})\n    issues = reliability.get("issues") or []\n    retained = []\n    converted = []\n\n    for issue in issues:\n        if (\n            isinstance(issue, dict)\n            and issue.get("source") == "Runtime Refresh"\n            and issue.get("state") == "review"\n            and issue.get("path") == "static/data/runtime_refresh_status.json"\n            and EXPECTED_NOTE in (issue.get("reason") or "")\n        ):\n            advisory = dict(issue)\n            advisory["classification"] = "advisory"\n            advisory["blocking"] = False\n            advisory["alignment_note"] = "Runtime collector was intentionally not requested; latest runtime data freshness remains visible in runtime_refresh_status.json."\n            converted.append(advisory)\n        else:\n            retained.append(issue)\n\n    if not converted:\n        return {\n            "aligned": False,\n            "reason": "No matching Runtime Refresh blocking issue found to convert.",\n            "path": str(reliability_path),\n        }\n\n    existing_advisories = reliability.get("advisories") or []\n    # Prevent duplicate advisory accumulation for the same expected runtime refresh state.\n    existing_advisories = [\n        item for item in existing_advisories\n        if not (\n            isinstance(item, dict)\n            and item.get("source") == "Runtime Refresh"\n            and item.get("path") == "static/data/runtime_refresh_status.json"\n            and EXPECTED_NOTE in (item.get("reason") or "")\n        )\n    ]\n\n    reliability["issues"] = retained\n    reliability["advisories"] = existing_advisories + converted\n    summary["issue_count"] = len(retained)\n    summary["runtime_refresh_overall"] = "ok_with_advisory"\n    if len(retained) == 0:\n        reliability["overall_status"] = "ok"\n\n    reliability["alignment"] = {\n        "runtime_refresh_review_aligned": True,\n        "aligned_at_utc": now_utc(),\n        "reason": "Converted expected no-collector-requested runtime refresh review into advisory, not blocking issue.",\n        "persistence": "scripts/source_reliability_audit.py invokes app.audits.source_reliability_advisory.align_source_reliability after each audit run.",\n    }\n\n    write_json(reliability_path, reliability)\n    return {\n        "aligned": True,\n        "converted_count": len(converted),\n        "remaining_issue_count": len(retained),\n        "overall_status": reliability.get("overall_status"),\n        "runtime_refresh_overall": summary.get("runtime_refresh_overall"),\n        "path": str(reliability_path),\n    }\n'

PERSISTENT_WRAPPER = 'from __future__ import annotations\n\nfrom _project_bootstrap import ensure_project_root_on_path\nensure_project_root_on_path()\n\nfrom app.audits.source_reliability import main\nfrom app.audits.source_reliability_advisory import align_source_reliability\n\n\nif __name__ == "__main__":\n    result = main()\n    align_source_reliability()\n    raise SystemExit(result if isinstance(result, int) else 0)\n'


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run(cmd: list[str]) -> dict:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=420)
        return {
            "cmd": " ".join(cmd),
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-5000:],
            "stderr_tail": (proc.stderr or "")[-5000:],
        }
    except Exception as exc:
        return {"cmd": " ".join(cmd), "returncode": None, "error": str(exc)}


def read_json(path: Path):
    if not path.exists(): return None
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc: return {"_read_error": str(exc)}


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = ROOT / "backups" / f"source_reliability_advisory_persistence_v1_{stamp}"
    backup_root.mkdir(parents=True, exist_ok=True)
    backups = []
    errors = []

    for path in [SCRIPT, ADVISORY_MODULE, SOURCE_RELIABILITY]:
        if path.exists():
            backup = backup_root / path.relative_to(ROOT)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
            backups.append({"source": str(path), "backup": str(backup)})

    try:
        ADVISORY_MODULE.parent.mkdir(parents=True, exist_ok=True)
        ADVISORY_MODULE.write_text(ADVISORY_MODULE_CONTENT, encoding="utf-8")
        SCRIPT.write_text(PERSISTENT_WRAPPER, encoding="utf-8")
    except Exception as exc:
        errors.append({"stage": "write_files", "error": str(exc)})

    runs = []
    if not errors:
        runs.append(run([sys.executable, "-m", "py_compile", "scripts/source_reliability_audit.py", "app/audits/source_reliability_advisory.py", "app/audits/source_reliability.py"]))
        runs.append(run([sys.executable, "scripts/source_reliability_audit.py"]))
        runs.append(run([sys.executable, "scripts/run_operational_snapshot.py"]))
        runs.append(run([sys.executable, "scripts/source_reliability_audit.py"]))

    reliability = read_json(SOURCE_RELIABILITY) or {}
    summary = reliability.get("summary") or {}
    issue_count = summary.get("issue_count", reliability.get("issue_count"))
    overall = reliability.get("overall_status")
    runtime_overall = summary.get("runtime_refresh_overall")
    advisory_count = len(reliability.get("advisories") or [])
    alignment = reliability.get("alignment") or {}

    rollback = backup_root / "rollback_source_reliability_advisory_persistence_v1.ps1"
    lines = [
        'param([string]$ProjectRoot = "C:\\Users\\Luke_C\\Desktop\\JiraObservationMonitor")',
        '$ErrorActionPreference = "Stop"',
    ]
    for item in backups:
        source_rel = str(Path(item["source"]).relative_to(ROOT)).replace("/", "\\")
        backup_rel = str(Path(item["backup"]).relative_to(ROOT)).replace("/", "\\")
        lines.append(f'$backup = Join-Path $ProjectRoot "{backup_rel}"')
        lines.append(f'$target = Join-Path $ProjectRoot "{source_rel}"')
        lines.append('if (Test-Path $backup) { Copy-Item $backup $target -Force; Write-Host "Restored $target" -ForegroundColor Green }')
    if not ADVISORY_MODULE.exists() or not any(str(ADVISORY_MODULE) == item["source"] for item in backups):
        lines.append('$advisory = Join-Path $ProjectRoot "app\\audits\\source_reliability_advisory.py"')
        lines.append('if (Test-Path $advisory) { Remove-Item $advisory -Force; Write-Host "Removed advisory module" -ForegroundColor Yellow }')
    lines.append('Write-Host "Source reliability advisory persistence rollback complete." -ForegroundColor Green')
    rollback.write_text("\n".join(lines) + "\n", encoding="utf-8")

    validation_ok = all(r.get("returncode") == 0 for r in runs)
    ok = not errors and validation_ok and issue_count == 0 and overall == "ok" and runtime_overall == "ok_with_advisory" and alignment.get("runtime_refresh_review_aligned") is True

    status = {
        "schema": "jom-source-reliability-advisory-persistence-v1-status",
        "generated_at_utc": now_utc(),
        "mode": "persistent_runtime_refresh_advisory_alignment",
        "status": "ok" if ok else "attention",
        "backup_root": str(backup_root),
        "backups": backups,
        "errors": errors,
        "runs": runs,
        "validation_ok": validation_ok,
        "final_overall_status": overall,
        "final_issue_count": issue_count,
        "final_runtime_refresh_overall": runtime_overall,
        "advisory_count": advisory_count,
        "alignment": alignment,
        "rollback_script": str(rollback),
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(status, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": status["status"],
        "validation_ok": validation_ok,
        "final_overall_status": overall,
        "final_issue_count": issue_count,
        "final_runtime_refresh_overall": runtime_overall,
        "advisory_count": advisory_count,
        "status_file": str(STATUS),
        "rollback_script": str(rollback),
    }, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
