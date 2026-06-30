from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_NOTE = "Runtime collector was not requested. Status inferred from latest_run.json freshness."


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


def align_source_reliability(project_root: Path | str | None = None) -> dict:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    runtime_path = root / "static" / "data" / "runtime_refresh_status.json"
    reliability_path = root / "static" / "data" / "source_reliability_status.json"

    runtime_status = read_json(runtime_path)
    reliability = read_json(reliability_path)
    expected, reason = runtime_review_is_expected(runtime_status)

    if not expected or not isinstance(reliability, dict):
        return {
            "aligned": False,
            "reason": reason,
            "path": str(reliability_path),
        }

    summary = reliability.setdefault("summary", {})
    issues = reliability.get("issues") or []
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

    if not converted:
        return {
            "aligned": False,
            "reason": "No matching Runtime Refresh blocking issue found to convert.",
            "path": str(reliability_path),
        }

    existing_advisories = reliability.get("advisories") or []
    # Prevent duplicate advisory accumulation for the same expected runtime refresh state.
    existing_advisories = [
        item for item in existing_advisories
        if not (
            isinstance(item, dict)
            and item.get("source") == "Runtime Refresh"
            and item.get("path") == "static/data/runtime_refresh_status.json"
            and EXPECTED_NOTE in (item.get("reason") or "")
        )
    ]

    reliability["issues"] = retained
    reliability["advisories"] = existing_advisories + converted
    summary["issue_count"] = len(retained)
    summary["runtime_refresh_overall"] = "ok_with_advisory"
    if len(retained) == 0:
        reliability["overall_status"] = "ok"

    reliability["alignment"] = {
        "runtime_refresh_review_aligned": True,
        "aligned_at_utc": now_utc(),
        "reason": "Converted expected no-collector-requested runtime refresh review into advisory, not blocking issue.",
        "persistence": "scripts/source_reliability_audit.py invokes app.audits.source_reliability_advisory.align_source_reliability after each audit run.",
    }

    write_json(reliability_path, reliability)
    return {
        "aligned": True,
        "converted_count": len(converted),
        "remaining_issue_count": len(retained),
        "overall_status": reliability.get("overall_status"),
        "runtime_refresh_overall": summary.get("runtime_refresh_overall"),
        "path": str(reliability_path),
    }
