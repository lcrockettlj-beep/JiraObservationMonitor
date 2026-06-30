from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "reports" / "snapshot_scheduler_runtime_review_v1.json"
OUT_MD = ROOT / "reports" / "snapshot_scheduler_runtime_review_v1.md"

FILES = [
    "scripts/snapshot_controller.py",
    "scripts/sync_runtime.py",
    "scripts/run_operational_snapshot.py",
    "scripts/run_sync_for_scheduler.cmd",
    "scripts/register_scheduled_sync.ps1",
    "scripts/check_scheduled_sync.ps1",
    "scripts/unregister_scheduled_sync.ps1",
    "docs/control/scheduled_sync.log",
]

INTERVAL_PATTERNS = [
    ("900_seconds", re.compile(r"\b900\b|PT15M|15\s*minute", re.IGNORECASE)),
    ("3600_seconds", re.compile(r"\b3600\b|PT1H|60\s*minute|1\s*hour", re.IGNORECASE)),
    ("600_seconds", re.compile(r"\b600\b|PT10M|10\s*minute", re.IGNORECASE)),
]

TARGET_PATTERNS = [
    "run_operational_snapshot.py",
    "sync_runtime.py",
    "snapshot_controller.py",
    "run_sync_for_scheduler.cmd",
    "data_collector.py",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def run(cmd: list[str], timeout: int = 90) -> dict:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, shell=False)
        return {
            "cmd": " ".join(cmd),
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-8000:],
            "stderr_tail": (proc.stderr or "")[-4000:],
        }
    except Exception as exc:
        return {"cmd": " ".join(cmd), "returncode": None, "error": str(exc)}


def analyse_file(rel: str) -> dict:
    path = ROOT / rel
    text = read_text(path) if path.exists() else ""
    interval_hits = []
    for label, pattern in INTERVAL_PATTERNS:
        if pattern.search(text):
            interval_hits.append(label)
    target_hits = [target for target in TARGET_PATTERNS if target in text]
    task_name_hits = sorted(set(re.findall(r"JiraObservationMonitor[^\s\"']*|JOM[^\s\"']*", text)))
    schedule_hints = []
    for token in ["New-ScheduledTaskTrigger", "Register-ScheduledTask", "schtasks", "RepetitionInterval", "ScheduledTask", "/SC", "/MO"]:
        if token.lower() in text.lower(): schedule_hints.append(token)
    return {
        "path": rel,
        "exists": path.exists(),
        "line_count": len(text.splitlines()) if text else 0,
        "target_hits": target_hits,
        "interval_hits": interval_hits,
        "task_name_hits": task_name_hits[:20],
        "schedule_hints": schedule_hints,
    }


def parse_schtasks_text(text: str) -> list[dict]:
    tasks = []
    current = {}
    for line in text.splitlines():
        if not line.strip():
            if current:
                tasks.append(current); current = {}
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            current[key.strip()] = value.strip()
    if current:
        tasks.append(current)
    interesting = []
    for task in tasks:
        joined = json.dumps(task, ensure_ascii=False).lower()
        if any(token in joined for token in ["jira", "jom", "observation", "sync_runtime", "snapshot", "run_sync_for_scheduler"]):
            interesting.append(task)
    return interesting


def main() -> int:
    files = [analyse_file(rel) for rel in FILES]
    powershell_review = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "Get-ScheduledTask | Where-Object { $_.TaskName -match 'JOM|Jira|Observation|Snapshot|Sync' -or $_.TaskPath -match 'JOM|Jira|Observation|Snapshot|Sync' } | Select-Object TaskName,TaskPath,State | ConvertTo-Json -Depth 6"])
    schtasks_query = run(["schtasks", "/Query", "/FO", "LIST", "/V"], timeout=180)
    schtasks_matches = parse_schtasks_text(schtasks_query.get("stdout_tail", "")) if schtasks_query.get("returncode") == 0 else []

    all_interval_hits = sorted(set(hit for f in files for hit in f["interval_hits"]))
    all_target_hits = sorted(set(hit for f in files for hit in f["target_hits"]))
    recommendations = []
    if "900_seconds" in all_interval_hits:
        recommendations.append("900-second interval reference found. Review before changing scheduler.")
    if "3600_seconds" not in all_interval_hits:
        recommendations.append("No obvious 3600-second/hourly reference found in reviewed files.")
    if "run_operational_snapshot.py" not in all_target_hits:
        recommendations.append("Reviewed scheduler files do not obviously target run_operational_snapshot.py.")
    if "sync_runtime.py" in all_target_hits or "run_sync_for_scheduler.cmd" in all_target_hits:
        recommendations.append("Legacy scheduler/sync target references detected. Review before migration.")
    if not recommendations:
        recommendations.append("No obvious scheduler conflict detected from static file scan; still review Task Scheduler results.")

    payload = {
        "schema": "jom-snapshot-scheduler-runtime-review-v1",
        "generated_at_utc": now_utc(),
        "mode": "report-only-no-file-moves",
        "summary": {
            "reviewed_file_count": len(files),
            "existing_file_count": sum(1 for f in files if f["exists"]),
            "interval_hits": all_interval_hits,
            "target_hits": all_target_hits,
            "schtasks_returncode": schtasks_query.get("returncode"),
            "interesting_schtasks_count": len(schtasks_matches),
            "powershell_task_query_returncode": powershell_review.get("returncode"),
        },
        "files": files,
        "powershell_scheduled_task_review": powershell_review,
        "schtasks_query": {
            "returncode": schtasks_query.get("returncode"),
            "stderr_tail": schtasks_query.get("stderr_tail"),
            "interesting_matches": schtasks_matches[:30],
        },
        "recommendations": recommendations,
        "next_action": "Review this report before changing registered scheduled tasks or intervals.",
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = ["# Snapshot Scheduler Runtime Review", "", f"Generated: `{payload['generated_at_utc']}`", "", "## Mode", "", "Report-only. No files, scheduled tasks, or intervals were changed.", "", "## Summary", ""]
    for k, v in payload["summary"].items(): lines.append(f"- {k}: **{v}**")
    lines += ["", "## Recommendations", ""]
    for item in recommendations: lines.append(f"- {item}")
    lines += ["", "## Files Reviewed", ""]
    for f in files: lines.append(f"- `{f['path']}` exists={f['exists']} targets={f['target_hits']} intervals={f['interval_hits']}")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status":"ok","json":str(OUT_JSON),"report":str(OUT_MD),"summary":payload["summary"]}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
