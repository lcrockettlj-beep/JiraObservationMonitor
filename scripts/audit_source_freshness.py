from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "static" / "data"
OUT_FRESHNESS = DATA / "source_freshness_audit.json"
OUT_RELIABILITY = DATA / "source_reliability_status.json"

SOURCES = [
    ("site_registry", DATA / "site_registry.json", "Site Registry", "GENERATED_CACHE"),
    ("admin_truth_v2", DATA / "admin_truth_v2.json", "Admin Truth Layer v2", "GENERATED_CACHE"),
    ("estate_product_access", DATA / "estate_product_access.json", "Estate Product Access", "LIVE_CACHE"),
    ("estate_access_truth", DATA / "estate_access_truth.json", "Estate Access Truth", "LIVE_CACHE"),
    ("runtime_live_truth_status", DATA / "runtime_live_truth_status.json", "Runtime Live Truth Status", "LIVE_STATUS"),
    ("user_footprint", DATA / "user_footprint.json", "User Footprint", "GUARDED_CACHE"),
    ("billing_seats", DATA / "billing_seats.json", "Billing Seats", "LEGACY_REFERENCE"),
    ("latest_run", ROOT / "latest_run.json", "Latest Jira Runtime Run", "LEGACY_REFERENCE"),
    ("latest_run_admin_enriched", ROOT / "latest_run_admin_enriched.json", "Latest Admin Enriched Run", "LEGACY_REFERENCE"),
]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"_json_error": str(exc)}


def parse_time(value: Any):
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def get_timestamp(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("generated_at_utc") or payload.get("updated_at_utc") or payload.get("served_at_utc") or payload.get("raw_collection_summary", {}).get("collected_at_utc") or "")


def classify(path: Path, source_type: str, payload: Any) -> Dict[str, Any]:
    exists = path.exists()
    timestamp = get_timestamp(payload) if exists else ""
    parsed = parse_time(timestamp)
    age = None
    if parsed:
        age = round((datetime.now(timezone.utc) - parsed).total_seconds() / 3600, 2)
    if not exists:
        state = "MISSING"
    elif source_type == "LEGACY_REFERENCE":
        state = "REFERENCE_ONLY"
    elif isinstance(payload, dict) and payload.get("live_collection") and payload.get("status") in ("ok", "partial"):
        state = "LIVE"
    elif age is None:
        state = "UNKNOWN_TIMESTAMP"
    elif age <= 24:
        state = "CURRENT"
    elif age <= 72:
        state = "AGING"
    else:
        state = "STALE_CACHE"
    return {"state": state, "timestamp": timestamp, "parsed": parsed.isoformat().replace("+00:00", "Z") if parsed else None, "age_hours": age}


def main() -> int:
    records: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    for key, path, label, source_type in SOURCES:
        payload = read_json(path) if path.exists() else {}
        state = classify(path, source_type, payload)
        counts[state["state"]] = counts.get(state["state"], 0) + 1
        row = {
            "key": key,
            "label": label,
            "path": str(path.relative_to(ROOT)),
            "exists": path.exists(),
            "source_type": source_type,
            "freshness_state": state["state"],
            "timestamp_value": state["timestamp"],
            "parsed_timestamp_utc": state["parsed"],
            "age_hours": state["age_hours"],
            "operator_label": state["state"],
        }
        records.append(row)
        if state["state"] in {"MISSING", "UNKNOWN_TIMESTAMP", "STALE_CACHE"}:
            issues.append({"source": label, "path": str(path.relative_to(ROOT)), "state": state["state"]})

    freshness = {
        "schema": "jom-source-freshness-audit-v2-live-truth-aware",
        "generated_at_utc": now_utc(),
        "policy": {
            "rule": "Live endpoints and explicit route contracts are truth; legacy snapshots are reference-only.",
            "legacy_reference_is_not_failure": True,
            "current_hours": 24,
            "aging_hours": 72,
        },
        "sources": records,
        "summary": {"source_count": len(records), "counts": counts, "overall_state": "OK" if not issues else "ATTENTION"},
    }
    reliability = {
        "schema": "jom-source-reliability-status-v2-live-truth-aware",
        "generated_at_utc": now_utc(),
        "overall_status": "ok" if not issues else "attention",
        "issues": issues,
        "summary": {"issue_count": len(issues), "freshness_overall": freshness["summary"]["overall_state"]},
        "inputs": {"source_freshness": str(OUT_FRESHNESS.relative_to(ROOT))},
    }
    DATA.mkdir(parents=True, exist_ok=True)
    OUT_FRESHNESS.write_text(json.dumps(freshness, indent=2), encoding="utf-8")
    OUT_RELIABILITY.write_text(json.dumps(reliability, indent=2), encoding="utf-8")
    print(json.dumps({"freshness": str(OUT_FRESHNESS), "reliability": str(OUT_RELIABILITY), "issues": len(issues)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
