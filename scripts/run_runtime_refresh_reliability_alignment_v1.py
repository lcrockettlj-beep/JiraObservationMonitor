from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "reports" / "runtime_refresh_reliability_alignment_status.json"
RUNTIME_STATUS = ROOT / "static" / "data" / "runtime_refresh_status.json"
SOURCE_RELIABILITY = ROOT / "static" / "data" / "source_reliability_status.json"
SOURCE_RELIABILITY_SCRIPT = ROOT / "scripts" / "source_reliability_audit.py"
APP_SOURCE_RELIABILITY = ROOT / "app" / "audits" / "source_reliability.py"

EXPECTED_NOTE = "Runtime collector was not requested. Status inferred from latest_run.json freshness."


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
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": str(exc)}


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def runtime_review_is_expected(runtime_status: dict | None) -> tuple[bool, str]:
    if not isinstance(runtime_status, dict):
        return False, "runtime_refresh_status.json is missing or unreadable"
    if runtime_status.get("overall_status") != "review":
        return False, "runtime overall_status is not review"
    if runtime_status.get("run_collector_requested") is not False:
        return False, "run_collector_requested is not false"
    steps = runtime_status.get("steps") or []
    collector_steps = [s for s in steps if isinstance(s, dict) and s.get("key") == "runtime_collector"]
    if not collector_steps:
        return False, "runtime_collector step missing"
    collector = collector_steps[0]
    if collector.get("status") != "review":
        return False, "runtime_collector status is not review"
    note = collector.get("note") or ""
    if EXPECTED_NOTE not in note:
        return False, "runtime_collector review note is not the expected no-collector-requested note"
    return True, "runtime collector review is expected because collector was intentionally not requested"


def align_reliability(runtime_status: dict, reliability: dict) -> tuple[dict, dict]:
    updated = json.loads(json.dumps(reliability))
    summary = updated.setdefault("summary", {})
    issues = updated.get("issues") or []

    retained = []
    converted = []
    for issue in issues:
        if (
            isinstance(issue, dict)
            and issue.get("source") == "Runtime Refresh"
            and issue.get("state") == "review"
            and issue.get("path") == "static/data/runtime_refresh_status.json"
            and EXPECTED_NOTE in (issue.get("reason") or "")
        ):
            advisory = dict(issue)
            advisory["classification"] = "advisory"
            advisory["blocking"] = False
            advisory["alignment_note"] = "Runtime collector was intentionally not requested; latest runtime data freshness remains visible in runtime_refresh_status.json."
            converted.append(advisory)
        else:
            retained.append(issue)

    updated["issues"] = retained
    updated["advisories"] = (updated.get("advisories") or []) + converted
    summary["issue_count"] = len(retained)
    summary["runtime_refresh_overall"] = "ok_with_advisory" if converted else summary.get("runtime_refresh_overall")
    if len(retained) == 0:
        updated["overall_status"] = "ok"
    updated["alignment"] = {
        "runtime_refresh_review_aligned": bool(converted),
        "aligned_at_utc": now_utc(),
        "reason": "Converted expected no-collector-requested runtime refresh review into advisory, not blocking issue.",
    }
    details = {"converted_count": len(converted), "remaining_issue_count": len(retained)}
    return updated, details


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = ROOT / "backups" / f"runtime_refresh_reliability_alignment_v1_{stamp}"
    backup_root.mkdir(parents=True, exist_ok=True)

    backups = []
    for path in [RUNTIME_STATUS, SOURCE_RELIABILITY]:
        if path.exists():
            backup = backup_root / path.relative_to(ROOT)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
            backups.append({"source": str(path), "backup": str(backup)})

    pre_runtime = read_json(RUNTIME_STATUS)
    pre_reliability = read_json(SOURCE_RELIABILITY)
    expected_review, expected_reason = runtime_review_is_expected(pre_runtime)

    runs = []
    # Re-run source reliability first to confirm current issue consistently exists.
    runs.append(run([sys.executable, "scripts/source_reliability_audit.py"]))
    current_reliability = read_json(SOURCE_RELIABILITY) or {}
    current_runtime = read_json(RUNTIME_STATUS) or {}
    expected_review_after_rerun, expected_reason_after_rerun = runtime_review_is_expected(current_runtime)

    aligned = False
    alignment_details = {}
    if expected_review_after_rerun and isinstance(current_reliability, dict):
        updated, alignment_details = align_reliability(current_runtime, current_reliability)
        write_json(SOURCE_RELIABILITY, updated)
        aligned = True

    final_reliability = read_json(SOURCE_RELIABILITY) or {}
    final_summary = final_reliability.get("summary") or {}
    final_issue_count = final_summary.get("issue_count", final_reliability.get("issue_count"))
    final_overall = final_reliability.get("overall_status")
    final_runtime_overall = final_summary.get("runtime_refresh_overall")

    rollback = backup_root / "rollback_runtime_refresh_reliability_alignment_v1.ps1"
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
    lines.append('Write-Host "Runtime refresh reliability alignment rollback complete." -ForegroundColor Green')
    rollback.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok = aligned and final_issue_count == 0 and final_overall == "ok"
    status = {
        "schema": "jom-runtime-refresh-reliability-alignment-v1-status",
        "generated_at_utc": now_utc(),
        "mode": "align_expected_runtime_refresh_review_to_advisory",
        "backup_root": str(backup_root),
        "backups": backups,
        "precheck_expected_review": expected_review,
        "precheck_reason": expected_reason,
        "post_rerun_expected_review": expected_review_after_rerun,
        "post_rerun_reason": expected_reason_after_rerun,
        "runs": runs,
        "aligned": aligned,
        "alignment_details": alignment_details,
        "final_overall_status": final_overall,
        "final_issue_count": final_issue_count,
        "final_runtime_refresh_overall": final_runtime_overall,
        "rollback_script": str(rollback),
        "status": "ok" if ok else "attention",
    }
    write_json(STATUS, status)

    print(json.dumps({
        "status": status["status"],
        "aligned": aligned,
        "final_overall_status": final_overall,
        "final_issue_count": final_issue_count,
        "final_runtime_refresh_overall": final_runtime_overall,
        "status_file": str(STATUS),
        "rollback_script": str(rollback),
    }, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
