from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "static" / "data" / "operational_console_status.json"
REPORT_JSON = ROOT / "reports" / "operational_console_ui_alignment_status.json"
REPORT_MD = ROOT / "reports" / "operational_console_ui_alignment_status.md"

EXPECTED_TASK = "JOM_Sync_Runtime"
EXPECTED_SCRIPT = "run_operational_snapshot.py"
EXPECTED_INTERVAL_HINTS = ["Every:                        1 Hour(s), 0 Minute(s)", "PT1H", "3600"]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def run(cmd: list[str], timeout: int = 120) -> dict:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return {
            "cmd": " ".join(cmd),
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-8000:],
            "stderr_tail": (proc.stderr or "")[-4000:],
        }
    except Exception as exc:
        return {"cmd": " ".join(cmd), "returncode": None, "error": str(exc)}


def scheduler_snapshot() -> dict:
    query = run(["schtasks", "/Query", "/TN", EXPECTED_TASK, "/V", "/FO", "LIST"])
    text = query.get("stdout_tail") or ""
    target_ok = EXPECTED_SCRIPT in text and "run_sync_for_scheduler.cmd" not in text and "sync_runtime.py" not in text
    start_in_ok = str(ROOT) in text
    hourly_ok = any(hint in text for hint in EXPECTED_INTERVAL_HINTS)
    return {
        "task_name": EXPECTED_TASK,
        "query_returncode": query.get("returncode"),
        "target_ok": target_ok,
        "start_in_ok": start_in_ok,
        "hourly_interval_ok": hourly_ok,
        "raw_query_tail": text[-4000:],
        "stderr_tail": query.get("stderr_tail"),
    }


def source_reliability_snapshot() -> dict:
    reliability = read_json(ROOT / "static" / "data" / "source_reliability_status.json") or {}
    summary = reliability.get("summary") or {}
    return {
        "overall_status": reliability.get("overall_status"),
        "issue_count": summary.get("issue_count", reliability.get("issue_count")),
        "freshness_overall": summary.get("freshness_overall"),
        "runtime_refresh_overall": summary.get("runtime_refresh_overall"),
        "user_footprint_status": summary.get("user_footprint_status"),
        "issues": reliability.get("issues") or [],
        "advisories": reliability.get("advisories") or [],
        "alignment": reliability.get("alignment") or {},
    }


def runtime_refresh_snapshot() -> dict:
    runtime = read_json(ROOT / "static" / "data" / "runtime_refresh_status.json") or {}
    collector = None
    for step in runtime.get("steps", []) if isinstance(runtime, dict) else []:
        if isinstance(step, dict) and step.get("key") == "runtime_collector":
            collector = step
            break
    return {
        "overall_status": runtime.get("overall_status") if isinstance(runtime, dict) else None,
        "run_collector_requested": runtime.get("run_collector_requested") if isinstance(runtime, dict) else None,
        "runtime_collector_status": collector.get("status") if isinstance(collector, dict) else None,
        "runtime_collector_note": collector.get("note") if isinstance(collector, dict) else None,
        "latest_run_freshness": collector.get("latest_run_freshness") if isinstance(collector, dict) else None,
        "latest_admin_enriched_freshness": collector.get("latest_admin_enriched_freshness") if isinstance(collector, dict) else None,
    }


def site_registry_snapshot() -> dict:
    registry = read_json(ROOT / "static" / "data" / "site_registry.json") or {}
    monitored, discovered = [], []
    if isinstance(registry, dict):
        for site in registry.get("sites", []):
            if not isinstance(site, dict):
                continue
            key = site.get("site_key") or site.get("key") or site.get("site")
            if site.get("is_monitored") is True or site.get("classification") == "monitored":
                monitored.append(key)
            elif site.get("classification") == "discovered":
                discovered.append(key)
    return {
        "schema": registry.get("schema") if isinstance(registry, dict) else None,
        "generated_at_utc": registry.get("generated_at_utc") if isinstance(registry, dict) else None,
        "summary": registry.get("summary") if isinstance(registry, dict) else {},
        "monitored": sorted([x for x in monitored if x]),
        "discovered": sorted([x for x in discovered if x]),
    }


def main() -> int:
    scheduler = scheduler_snapshot()
    reliability = source_reliability_snapshot()
    runtime = runtime_refresh_snapshot()
    registry = site_registry_snapshot()

    blocking_issue_count = reliability.get("issue_count")
    scheduler_ok = bool(scheduler.get("target_ok") and scheduler.get("start_in_ok") and scheduler.get("hourly_interval_ok"))
    reliability_ok = reliability.get("overall_status") == "ok" and blocking_issue_count == 0

    overall_status = "ok" if scheduler_ok and reliability_ok else "attention"

    payload = {
        "schema": "jom-operational-console-status-v1",
        "generated_at_utc": now_utc(),
        "overall_status": overall_status,
        "summary": {
            "scheduler_ok": scheduler_ok,
            "source_reliability_ok": reliability_ok,
            "source_reliability_issue_count": blocking_issue_count,
            "runtime_refresh_overall": reliability.get("runtime_refresh_overall"),
            "runtime_advisory_count": len(reliability.get("advisories") or []),
            "monitored_site_count": len(registry.get("monitored") or []),
            "discovered_site_count": len(registry.get("discovered") or []),
        },
        "cards": {
            "scheduler": scheduler,
            "source_reliability": reliability,
            "runtime_refresh": runtime,
            "site_registry": registry,
        },
        "operator_guidance": [
            "Scheduler should target scripts/run_operational_snapshot.py with project root as Start In.",
            "Source reliability must have issue_count 0 for the operational console to be considered OK.",
            "Runtime refresh review caused by collector not requested is preserved as a non-blocking advisory.",
        ],
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    write_json(OUT_JSON, payload)

    report = {
        "schema": "jom-operational-console-ui-alignment-v1-status",
        "generated_at_utc": now_utc(),
        "status": overall_status,
        "output": str(OUT_JSON),
        "scheduler_ok": scheduler_ok,
        "source_reliability_ok": reliability_ok,
        "summary": payload["summary"],
    }
    write_json(REPORT_JSON, report)

    lines = [
        "# Operational Console UI Alignment Status",
        "",
        f"Generated: `{report['generated_at_utc']}`",
        "",
        f"Status: **{overall_status}**",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- {key}: **{value}**")
    lines += ["", "## Output", "", f"- `{OUT_JSON.relative_to(ROOT).as_posix()}`"]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": overall_status,
        "output": str(OUT_JSON),
        "report": str(REPORT_JSON),
        "scheduler_ok": scheduler_ok,
        "source_reliability_ok": reliability_ok,
        "summary": payload["summary"],
    }, indent=2))
    return 0 if overall_status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
